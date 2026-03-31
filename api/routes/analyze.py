"""
lexilab — /analyze route
Main endpoint: submit text → run full analysis → save to DB → return results.
"""

import sys, os, time, tracemalloc
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../.."))

from fastapi import APIRouter, Depends, Header, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from db.database import get_db
from db.models import Dataset, User, Analysis, Collocation, Benchmark
from api.schemas import AnalyzeRequest, AnalysisOut, CollocationAllOut, BenchmarkOut
from api.routes.datasets import get_or_create_user
from api.limits import check_rate_limit, validate_text, RATE_LIMIT_ANALYZE

from core.preprocessing import preprocess
from core.frequency      import frequency_report
from core.collocations   import score_all_bigrams
from core.comparison.baselines import run_comparison, comparison_summary

# ── спроба імпорту Rust модуля ───────────────────
try:
    import rust_module
    RUST_AVAILABLE = True
except ImportError:
    RUST_AVAILABLE = False

router = APIRouter(prefix="/analyze", tags=["analyze"])


def bench_fn(fn, *args, runs=200):
    """Замір часу і пам'яті для функції."""
    tracemalloc.start()
    t0 = time.perf_counter()
    for _ in range(runs):
        result = fn(*args)
    t1 = time.perf_counter()
    _, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    return {
        "result":    result,
        "time_ms":   round((t1 - t0) * 1000 / runs, 4),
        "memory_kb": round(peak / 1024, 2),
        "has_result": result is not None,
    }


# ─────────────────────────────────────────────
# POST /analyze
# ─────────────────────────────────────────────
@router.post("/")
async def analyze_text(
    payload: AnalyzeRequest,
    request: Request,
    x_session_id: str = Header(..., alias="X-Session-Id"),
    db: AsyncSession = Depends(get_db),
):
    # ── rate limit ──
    ip = request.client.host if request.client else "unknown"
    check_rate_limit(ip, "analyze", RATE_LIMIT_ANALYZE)

    # ── validate text size ──
    validate_text(payload.text)

    # ── 1. user ──
    user = await get_or_create_user(x_session_id, db)

    # ── 2. preprocess ──
    prep   = preprocess(payload.text, do_lemmatize=True, do_remove_stopwords=True)
    tokens = prep["tokens"]

    if len(tokens) < 5:
        raise HTTPException(status_code=422, detail="Text too short after preprocessing")

    # ── 3. frequency report ──
    freq  = frequency_report(tokens, top=payload.top_n)
    vs    = freq["vocab_stats"]
    zf    = freq["zipf"]
    bands = freq["freq_bands"]

    # ── 4. save dataset ──
    dataset = Dataset(
        user_id      = user.id,
        name         = payload.name,
        lang         = prep["lang"],
        raw_text     = payload.text,
        token_count  = prep["token_count"],
        unique_count = prep["unique_count"],
        is_public    = payload.is_public,
        is_research  = payload.is_research,
    )
    db.add(dataset)
    await db.flush()

    # ── 5. save analysis ──
    analysis = Analysis(
        dataset_id    = dataset.id,
        ttr           = vs.get("ttr"),
        yules_k       = vs.get("yules_k"),
        hapax_count   = vs.get("hapax_legomena"),
        zipf_constant = zf.get("zipf_constant"),
        zipf_corr     = zf.get("log_log_correlation"),
        fits_zipf     = zf.get("fits_zipf"),
        top_words     = [{"word": w, "count": c} for w, c in vs.get("top_10", [])],
        freq_bands    = bands,
    )
    db.add(analysis)

    # ── 6. collocations ──
    coll_results = {}
    for measure in payload.measures:
        scored = score_all_bigrams(
            tokens,
            measure=measure,
            min_freq=payload.min_collocation_freq,
            top_n=payload.top_n,
        )
        coll_results[measure] = scored
        for rank, item in enumerate(scored, 1):
            db.add(Collocation(
                dataset_id = dataset.id,
                measure    = measure,
                w1         = item["bigram"][0],
                w2         = item["bigram"][1],
                freq       = item["freq"],
                score      = item["score"],
                rank       = rank,
            ))

    # ── 7. benchmark ──
    bench_summary = {}
    if payload.run_benchmark:
        # Python власний
        comparison    = run_comparison(tokens, text=payload.text)
        bench_summary = comparison_summary(comparison)

        # Rust власний
        if RUST_AVAILABLE:
            rust_tokens = rust_module.tokenize(payload.text)
            rust_benches = {
                "rust_own_frequency": bench_fn(
                    rust_module.vocabulary_stats, rust_tokens
                ),
                "rust_own_pmi": bench_fn(
                    rust_module.score_bigrams, rust_tokens, "pmi",
                    payload.min_collocation_freq, payload.top_n
                ),
                "rust_own_log_likelihood": bench_fn(
                    rust_module.score_bigrams, rust_tokens, "log_likelihood",
                    payload.min_collocation_freq, payload.top_n
                ),
                "rust_own_chi_square": bench_fn(
                    rust_module.score_bigrams, rust_tokens, "chi_square",
                    payload.min_collocation_freq, payload.top_n
                ),
                "rust_own_t_score": bench_fn(
                    rust_module.score_bigrams, rust_tokens, "t_score",
                    payload.min_collocation_freq, payload.top_n
                ),
            }
            # прибираємо result з bench щоб не засмічувати відповідь
            for k, v in rust_benches.items():
                bench_summary[k] = {
                    "time_ms":   v["time_ms"],
                    "memory_kb": v["memory_kb"],
                    "has_result": v["has_result"],
                }

        # зберігаємо всі бенчмарки в БД
        for method, stats in bench_summary.items():
            db.add(Benchmark(
                dataset_id = dataset.id,
                method     = method,
                time_ms    = stats.get("time_ms"),
                memory_kb  = stats.get("memory_kb"),
                available  = stats.get("has_result", False),
            ))

    await db.flush()
    await db.refresh(dataset)

    # ── 8. return ──
    return {
        "dataset": {
            "id":           dataset.id,
            "name":         dataset.name,
            "lang":         dataset.lang,
            "token_count":  dataset.token_count,
            "unique_count": dataset.unique_count,
        },
        "preprocessing": {
            "raw_tokens":   len(prep["tokens_raw"]),
            "final_tokens": prep["token_count"],
            "unique":       prep["unique_count"],
            "sample":       tokens[:10],
        },
        "vocab_stats": vs,
        "zipf":        zf,
        "freq_bands":  bands,
        "top_words":   freq["top_words"],
        "rust_available": RUST_AVAILABLE,
        "collocations": {
            measure: [
                {
                    "bigram": list(item["bigram"]),
                    "freq":   item["freq"],
                    "score":  item["score"],
                    "rank":   i + 1,
                }
                for i, item in enumerate(items)
            ]
            for measure, items in coll_results.items()
        },
        "benchmarks": bench_summary,
    }


# ─────────────────────────────────────────────
# GET /analyze/{dataset_id}
# ─────────────────────────────────────────────
@router.get("/{dataset_id}")
async def get_analysis(
    dataset_id: int,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Analysis).where(Analysis.dataset_id == dataset_id)
    )
    analysis = result.scalar_one_or_none()
    if not analysis:
        raise HTTPException(status_code=404, detail="Analysis not found")

    colls = await db.execute(
        select(Collocation)
        .where(Collocation.dataset_id == dataset_id)
        .order_by(Collocation.measure, Collocation.rank)
    )
    colls = colls.scalars().all()

    benches = await db.execute(
        select(Benchmark).where(Benchmark.dataset_id == dataset_id)
    )
    benches = benches.scalars().all()

    coll_by_measure = {}
    for c in colls:
        coll_by_measure.setdefault(c.measure, []).append({
            "bigram": [c.w1, c.w2],
            "freq":   c.freq,
            "score":  c.score,
            "rank":   c.rank,
        })

    return {
        "dataset_id":    dataset_id,
        "ttr":           analysis.ttr,
        "yules_k":       analysis.yules_k,
        "hapax_count":   analysis.hapax_count,
        "zipf_constant": analysis.zipf_constant,
        "zipf_corr":     analysis.zipf_corr,
        "fits_zipf":     analysis.fits_zipf,
        "top_words":     analysis.top_words,
        "freq_bands":    analysis.freq_bands,
        "collocations":  coll_by_measure,
        "benchmarks": [
            {
                "method":    b.method,
                "time_ms":   b.time_ms,
                "memory_kb": b.memory_kb,
                "available": b.available,
            }
            for b in benches
        ],
    }