"""
lexilab — /stats routes
Global aggregated statistics across all datasets.
"""

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from db.database import get_db
from db.models import Dataset, Analysis, Collocation, Benchmark

router = APIRouter(prefix="/stats", tags=["stats"])


@router.get("/global")
async def global_stats(db: AsyncSession = Depends(get_db)):
    """
    Aggregated stats across all public datasets.
    Used for the scientific comparison dashboard.
    """

    # ── dataset counts ──
    total_datasets = (await db.execute(
        select(func.count(Dataset.id)).where(Dataset.is_public == True)
    )).scalar()

    total_tokens = (await db.execute(
        select(func.sum(Dataset.token_count)).where(Dataset.is_public == True)
    )).scalar() or 0

    # ── language distribution ──
    lang_rows = (await db.execute(
        select(Dataset.lang, func.count(Dataset.id))
        .where(Dataset.is_public == True)
        .group_by(Dataset.lang)
    )).all()
    lang_dist = {lang: count for lang, count in lang_rows if lang}

    # ── avg TTR and Yule's K ──
    avg_ttr, avg_k = (await db.execute(
        select(func.avg(Analysis.ttr), func.avg(Analysis.yules_k))
        .join(Dataset)
        .where(Dataset.is_public == True)
    )).one()

    # ── top-10 global collocations by PMI ──
    top_colls = (await db.execute(
        select(
            Collocation.w1, Collocation.w2,
            func.avg(Collocation.score).label("avg_score"),
            func.sum(Collocation.freq).label("total_freq"),
        )
        .join(Dataset)
        .where(Dataset.is_public == True)
        .where(Collocation.measure == "pmi")
        .group_by(Collocation.w1, Collocation.w2)
        .order_by(func.avg(Collocation.score).desc())
        .limit(10)
    )).all()

    # ── benchmark summary: avg time per method ──
    bench_rows = (await db.execute(
        select(
            Benchmark.method,
            func.avg(Benchmark.time_ms).label("avg_time_ms"),
            func.avg(Benchmark.memory_kb).label("avg_memory_kb"),
        )
        .join(Dataset)
        .where(Dataset.is_public == True)
        .where(Benchmark.available == True)
        .group_by(Benchmark.method)
        .order_by(func.avg(Benchmark.time_ms))
    )).all()

    return {
        "total_datasets":    total_datasets,
        "total_tokens":      total_tokens,
        "avg_ttr":           round(avg_ttr or 0, 4),
        "avg_yules_k":       round(avg_k or 0, 2),
        "lang_distribution": lang_dist,
        "top_collocations_pmi": [
            {
                "bigram":     [w1, w2],
                "avg_score":  round(score, 4),
                "total_freq": freq,
            }
            for w1, w2, score, freq in top_colls
        ],
        "benchmark_summary": {
            method: {
                "avg_time_ms":   round(t or 0, 3),
                "avg_memory_kb": round(m or 0, 2),
            }
            for method, t, m in bench_rows
        },
    }


@router.get("/per-dataset")
async def per_dataset_stats(
    lang: str = None,
    limit: int = 50,
    db: AsyncSession = Depends(get_db),
):
    """
    Per-dataset breakdown for scatter plots and comparison tables.
    """
    query = (
        select(
            Dataset.id,
            Dataset.name,
            Dataset.lang,
            Dataset.token_count,
            Analysis.ttr,
            Analysis.yules_k,
            Analysis.hapax_count,
            Analysis.zipf_corr,
            Analysis.fits_zipf,
        )
        .join(Analysis, Dataset.id == Analysis.dataset_id)
        .where(Dataset.is_public == True)
    )
    if lang:
        query = query.where(Dataset.lang == lang)

    query = query.order_by(Dataset.created_at.desc()).limit(limit)
    rows  = (await db.execute(query)).all()

    return {
        "datasets": [
            {
                "id":          r.id,
                "name":        r.name,
                "lang":        r.lang,
                "token_count": r.token_count,
                "ttr":         round(r.ttr or 0, 4),
                "yules_k":     round(r.yules_k or 0, 2),
                "hapax_count": r.hapax_count,
                "zipf_corr":   round(r.zipf_corr or 0, 4),
                "fits_zipf":   r.fits_zipf,
            }
            for r in rows
        ]
    }


@router.get("/research")
async def research_datasets(
    lang: str = None,
    db: AsyncSession = Depends(get_db),
):
    """
    Research datasets — pre-loaded by authors for diploma research.
    Returns full stats for each dataset grouped by language.
    """
    query = (
        select(
            Dataset.id,
            Dataset.name,
            Dataset.lang,
            Dataset.token_count,
            Dataset.unique_count,
            Analysis.ttr,
            Analysis.yules_k,
            Analysis.hapax_count,
            Analysis.zipf_corr,
            Analysis.fits_zipf,
            Analysis.top_words,
        )
        .join(Analysis, Dataset.id == Analysis.dataset_id)
        .where(Dataset.is_research == True)
        .where(Dataset.is_public == True)
    )
    if lang:
        query = query.where(Dataset.lang == lang)
    query = query.order_by(Dataset.lang, Dataset.name)
    rows = (await db.execute(query)).all()

    # групуємо по мові
    grouped: dict = {}
    for r in rows:
        lg = r.lang or "unknown"
        if lg not in grouped:
            grouped[lg] = []
        grouped[lg].append({
            "id":           r.id,
            "name":         r.name,
            "lang":         r.lang,
            "token_count":  r.token_count,
            "unique_count": r.unique_count,
            "ttr":          round(r.ttr or 0, 4),
            "yules_k":      round(r.yules_k or 0, 2),
            "hapax_count":  r.hapax_count,
            "zipf_corr":    round(r.zipf_corr or 0, 4),
            "fits_zipf":    r.fits_zipf,
            "top_words":    (r.top_words or [])[:5],
        })

    # агрегована статистика по мові
    summary = {}
    for lg, items in grouped.items():
        ttrs = [i["ttr"] for i in items if i["ttr"]]
        yks  = [i["yules_k"] for i in items if i["yules_k"]]
        summary[lg] = {
            "count":    len(items),
            "avg_ttr":  round(sum(ttrs) / len(ttrs), 4) if ttrs else 0,
            "avg_yules_k": round(sum(yks) / len(yks), 2) if yks else 0,
            "total_tokens": sum(i["token_count"] or 0 for i in items),
        }

    return {
        "total":   len(rows),
        "summary": summary,
        "by_lang": grouped,
    }