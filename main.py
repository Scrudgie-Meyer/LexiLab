"""
lexilab — FastAPI application entry point
"""

import sys, os, hashlib, asyncio
sys.path.insert(0, os.path.dirname(__file__))

from contextlib import asynccontextmanager
from pathlib import Path
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from dotenv import load_dotenv

load_dotenv()

from db.database import init_db, AsyncSessionLocal
from db.models import Dataset, User, Analysis, Collocation, Benchmark
from sqlalchemy import select
from api.routes.datasets import router as datasets_router
from api.routes.analyze  import router as analyze_router
from api.routes.stats    import router as stats_router
from middleware import LexilabMiddleware

DATASETS_DIR   = Path(__file__).parent / "datasets"
RESEARCH_SESSION = "research-loader-auto"
MEASURES       = ["pmi", "log_likelihood", "chi_square", "t_score"]


# ── research dataset auto-loader ─────────────────
async def sync_research_datasets():
    """
    При старті сервера перевіряє папку datasets/
    і завантажує нові або змінені файли в БД.
    """
    from core.preprocessing import preprocess
    from core.frequency      import frequency_report
    from core.collocations   import score_all_bigrams
    from core.comparison.baselines import run_comparison, comparison_summary

    lang_dirs = [
        (DATASETS_DIR / "ua",    "ua"),
        (DATASETS_DIR / "en",    "en"),
        (DATASETS_DIR / "mixed", "mixed"),
    ]

    files = []
    for folder, lang in lang_dirs:
        if folder.exists():
            for f in sorted(folder.glob("*.txt")):
                files.append((f, lang))

    if not files:
        return

    print(f"\n[research] Found {len(files)} dataset files in datasets/")

    async with AsyncSessionLocal() as session:
        # get or create research user
        res = await session.execute(
            select(User).where(User.session_id == RESEARCH_SESSION)
        )
        user = res.scalar_one_or_none()
        if not user:
            user = User(session_id=RESEARCH_SESSION)
            session.add(user)
            await session.flush()

        loaded = skipped = 0

        for path, lang_hint in files:
            name = path.stem.replace("_", " ").title()
            text = path.read_text(encoding="utf-8").strip()
            file_hash = hashlib.md5(path.read_bytes()).hexdigest()

            # check if already loaded with same hash
            res = await session.execute(
                select(Dataset).where(
                    Dataset.name == name,
                    Dataset.is_research == True,
                )
            )
            existing = res.scalar_one_or_none()

            if existing:
                # check hash stored in analysis top_words
                res2 = await session.execute(
                    select(Analysis).where(Analysis.dataset_id == existing.id)
                )
                existing_analysis = res2.scalar_one_or_none()
                stored_hash = None
                if existing_analysis and existing_analysis.top_words:
                    for item in existing_analysis.top_words:
                        if isinstance(item, dict) and item.get("_hash"):
                            stored_hash = item["_hash"]
                            break
                if stored_hash == file_hash:
                    skipped += 1
                    continue
                # file changed — delete old and re-add
                await session.delete(existing)
                await session.flush()

            # preprocess — без лемматизації щоб не обрізати слова
            prep   = preprocess(text, do_lemmatize=False, do_remove_stopwords=True)
            tokens = prep["tokens"]
            if len(tokens) < 5:
                continue

            # frequency
            freq  = frequency_report(tokens, top=30)
            vs    = freq["vocab_stats"]
            zf    = freq["zipf"]
            bands = freq["freq_bands"]

            # top_words with embedded hash
            top_words = [{"word": w, "count": c} for w, c in vs.get("top_10", [])]
            top_words.append({"_hash": file_hash})

            # save dataset
            ds = Dataset(
                user_id=user.id, name=name, lang=prep["lang"],
                raw_text=text, token_count=prep["token_count"],
                unique_count=prep["unique_count"],
                is_public=True, is_research=True,
            )
            session.add(ds)
            await session.flush()

            # save analysis
            session.add(Analysis(
                dataset_id=ds.id,
                ttr=vs.get("ttr"), yules_k=vs.get("yules_k"),
                hapax_count=vs.get("hapax_legomena"),
                zipf_constant=zf.get("zipf_constant"),
                zipf_corr=zf.get("log_log_correlation"),
                fits_zipf=zf.get("fits_zipf"),
                top_words=top_words, freq_bands=bands,
            ))

            # collocations
            for measure in MEASURES:
                for rank, item in enumerate(
                    score_all_bigrams(tokens, measure=measure, min_freq=2, top_n=30), 1
                ):
                    session.add(Collocation(
                        dataset_id=ds.id, measure=measure,
                        w1=item["bigram"][0], w2=item["bigram"][1],
                        freq=item["freq"], score=item["score"], rank=rank,
                    ))

            # benchmark
            try:
                comp = run_comparison(tokens)
                for method, stats in comparison_summary(comp).items():
                    session.add(Benchmark(
                        dataset_id=ds.id, method=method,
                        time_ms=stats.get("time_ms"),
                        memory_kb=stats.get("memory_kb"),
                        available=stats.get("has_result", False),
                    ))
            except Exception:
                pass

            await session.flush()
            print(f"[research] ✓ {name} ({prep['lang']}, {prep['token_count']} tokens)")
            loaded += 1

        await session.commit()

    print(f"[research] Done: {loaded} loaded, {skipped} skipped\n")


# ── lifespan ──────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    asyncio.create_task(sync_research_datasets())
    yield


# ── app ──────────────────────────────────────────
app = FastAPI(
    title="lexilab API",
    description="Statistical text dependency analysis — own algorithm vs NLTK/spaCy/Gensim",
    version="0.1.0",
    lifespan=lifespan,
)

# ── CORS ─────────────────────────────────────────
ALLOWED_ORIGINS = os.getenv("ALLOWED_ORIGINS", "*").split(",")
app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Rate limiting + size limits ───────────────────
app.add_middleware(LexilabMiddleware)

# ── API routers ───────────────────────────────────
app.include_router(datasets_router)
app.include_router(analyze_router)
app.include_router(stats_router)


@app.get("/api", tags=["health"])
async def root():
    return {"service": "lexilab", "version": "0.1.0", "status": "ok", "docs": "/docs"}


@app.get("/health", tags=["health"])
async def health():
    return {"status": "ok"}


# ── Static frontend ───────────────────────────────
FRONTEND_DIR = os.path.join(os.path.dirname(__file__), "frontend")
if os.path.isdir(FRONTEND_DIR):
    app.mount("/static", StaticFiles(directory=FRONTEND_DIR), name="static")

    @app.get("/", include_in_schema=False)
    async def serve_frontend():
        return FileResponse(os.path.join(FRONTEND_DIR, "index.html"))