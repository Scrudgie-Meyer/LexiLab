"""
lexilab — Pydantic schemas
Request/response validation for FastAPI endpoints.
"""

from datetime import datetime
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field


# ──────────────────────────────────────────────
# DATASET
# ──────────────────────────────────────────────

class DatasetCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    text: str = Field(..., min_length=10)
    is_public: bool = True


class DatasetOut(BaseModel):
    id: int
    name: str
    lang: Optional[str]
    token_count: Optional[int]
    unique_count: Optional[int]
    is_public: bool
    is_research: bool = False
    created_at: datetime

    model_config = {"from_attributes": True}


class DatasetListOut(BaseModel):
    total: int
    items: List[DatasetOut]


# ──────────────────────────────────────────────
# ANALYSIS
# ──────────────────────────────────────────────

class VocabStats(BaseModel):
    total_tokens: int
    vocabulary_size: int
    hapax_legomena: int
    ttr: float
    yules_k: float
    avg_frequency: float
    top_10: List[List[Any]]


class ZipfStats(BaseModel):
    zipf_constant: float
    mae: float
    log_log_correlation: float
    fits_zipf: bool


class FreqBands(BaseModel):
    high_frequency: int
    mid_frequency: int
    low_frequency: int
    high_words: int
    mid_words: int
    low_words: int


class AnalysisOut(BaseModel):
    dataset_id: int
    vocab_stats: VocabStats
    zipf: ZipfStats
    freq_bands: FreqBands
    top_words: List[List[Any]]
    created_at: datetime

    model_config = {"from_attributes": True}


# ──────────────────────────────────────────────
# COLLOCATIONS
# ──────────────────────────────────────────────

class CollocationItem(BaseModel):
    bigram: List[str]
    freq: int
    score: float
    measure: str
    rank: int


class CollocationOut(BaseModel):
    dataset_id: int
    measure: str
    collocations: List[CollocationItem]


class CollocationAllOut(BaseModel):
    dataset_id: int
    results: Dict[str, List[CollocationItem]]


# ──────────────────────────────────────────────
# BENCHMARK
# ──────────────────────────────────────────────

class BenchmarkItem(BaseModel):
    method: str
    time_ms: Optional[float]
    memory_kb: Optional[float]
    available: bool


class BenchmarkOut(BaseModel):
    dataset_id: int
    benchmarks: List[BenchmarkItem]


# ──────────────────────────────────────────────
# AGGREGATE STATS (global, across all datasets)
# ──────────────────────────────────────────────

class GlobalStats(BaseModel):
    total_datasets: int
    total_tokens: int
    avg_ttr: float
    avg_yules_k: float
    lang_distribution: Dict[str, int]
    top_collocations_pmi: List[CollocationItem]
    benchmark_summary: Dict[str, Dict[str, float]]


# ──────────────────────────────────────────────
# ANALYZE REQUEST (submit text for analysis)
# ──────────────────────────────────────────────

class AnalyzeRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    text: str = Field(..., min_length=50, max_length=100_000)
    is_public: bool = True
    is_research: bool = False
    measures: List[str] = ["pmi", "log_likelihood", "chi_square"]
    min_collocation_freq: int = Field(default=2, ge=1, le=20)
    top_n: int = Field(default=20, ge=5, le=100)
    run_benchmark: bool = True