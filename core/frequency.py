"""
lexilab — frequency analysis module
Word frequency, Zipf's law, TF, rank-frequency distribution.
"""

import math
from collections import Counter
from typing import List, Dict, Tuple, Optional


# ──────────────────────────────────────────────
# CORE FREQUENCY
# ──────────────────────────────────────────────

def word_frequency(tokens: List[str]) -> Dict[str, int]:
    """
    Raw word frequency count.
    Returns dict sorted by frequency descending.
    """
    counts = Counter(tokens)
    return dict(counts.most_common())


def relative_frequency(tokens: List[str]) -> Dict[str, float]:
    """
    Relative frequency: count(w) / total_tokens.
    """
    total = len(tokens)
    if total == 0:
        return {}
    raw = word_frequency(tokens)
    return {w: c / total for w, c in raw.items()}


def term_frequency(tokens: List[str]) -> Dict[str, float]:
    """
    TF = count(w) / max_count  (normalized by most frequent term).
    Avoids bias toward longer documents.
    """
    if not tokens:
        return {}
    raw = Counter(tokens)
    max_count = raw.most_common(1)[0][1]
    return {w: c / max_count for w, c in raw.items()}


# ──────────────────────────────────────────────
# RANK-FREQUENCY (ZIPF)
# ──────────────────────────────────────────────

def rank_frequency(tokens: List[str]) -> List[Tuple[int, str, int, float]]:
    """
    Build rank-frequency table.
    Returns list of (rank, word, count, relative_freq).
    Zipf's law: frequency ∝ 1/rank
    """
    counts = Counter(tokens)
    ranked = counts.most_common()
    total = len(tokens)
    return [
        (rank + 1, word, count, count / total)
        for rank, (word, count) in enumerate(ranked)
    ]


def zipf_fit(tokens: List[str]) -> Dict:
    """
    Measure how well the corpus fits Zipf's law.
    Ideal Zipf: freq(rank) = C / rank
    
    Returns:
        - zipf_constant C
        - mean_absolute_error between ideal and actual
        - correlation coefficient
    """
    rf = rank_frequency(tokens)
    if len(rf) < 2:
        return {}

    ranks   = [r[0] for r in rf]
    freqs   = [r[2] for r in rf]
    total   = len(tokens)

    # estimate C from rank-1 word
    C = freqs[0] * 1  # rank=1 → freq = C/1

    ideal   = [C / r for r in ranks]
    errors  = [abs(f - i) for f, i in zip(freqs, ideal)]
    mae     = sum(errors) / len(errors)

    # Pearson correlation on log-log scale
    log_ranks = [math.log(r) for r in ranks]
    log_freqs = [math.log(f) if f > 0 else 0 for f in freqs]
    correlation = _pearson(log_ranks, log_freqs)

    return {
        "zipf_constant": round(C, 6),
        "mae": round(mae, 6),
        "log_log_correlation": round(correlation, 4),
        "fits_zipf": correlation < -0.85,   # strong negative log-log correlation
    }


def _pearson(x: List[float], y: List[float]) -> float:
    n = len(x)
    if n < 2:
        return 0.0
    mx, my = sum(x) / n, sum(y) / n
    num = sum((xi - mx) * (yi - my) for xi, yi in zip(x, y))
    den = math.sqrt(
        sum((xi - mx) ** 2 for xi in x) *
        sum((yi - my) ** 2 for yi in y)
    )
    return num / den if den != 0 else 0.0


# ──────────────────────────────────────────────
# VOCABULARY STATS
# ──────────────────────────────────────────────

def vocabulary_stats(tokens: List[str]) -> Dict:
    """
    Rich vocabulary statistics for a token list.
    """
    if not tokens:
        return {}

    counts  = Counter(tokens)
    total   = len(tokens)
    vocab   = len(counts)
    hapax   = sum(1 for c in counts.values() if c == 1)   # words appearing once
    dis     = sum(1 for c in counts.values() if c == 2)   # words appearing twice

    # Type-Token Ratio (TTR) — lexical richness
    ttr = vocab / total

    # Hapax Legomena ratio
    hapax_ratio = hapax / vocab if vocab else 0

    # Yule's K — measure of vocabulary richness (lower = richer)
    yule_k = _yules_k(counts, total)

    # Average frequency
    avg_freq = total / vocab if vocab else 0

    return {
        "total_tokens": total,
        "vocabulary_size": vocab,
        "hapax_legomena": hapax,
        "dis_legomena": dis,
        "ttr": round(ttr, 4),
        "hapax_ratio": round(hapax_ratio, 4),
        "yules_k": round(yule_k, 2),
        "avg_frequency": round(avg_freq, 2),
        "top_10": counts.most_common(10),
    }


def _yules_k(counts: Counter, total: int) -> float:
    """
    Yule's K statistic: K = 10^4 * (Σ V(m,N)*m^2 - N) / N^2
    Lower K = richer vocabulary.
    """
    if total == 0:
        return 0.0
    freq_of_freq = Counter(counts.values())
    sum_m2 = sum(v * (m ** 2) for m, v in freq_of_freq.items())
    k = 10_000 * (sum_m2 - total) / (total ** 2)
    return max(k, 0.0)


# ──────────────────────────────────────────────
# TOP-N HELPERS
# ──────────────────────────────────────────────

def top_n(tokens: List[str], n: int = 20) -> List[Tuple[str, int]]:
    """Return top-N most frequent tokens."""
    return Counter(tokens).most_common(n)


def frequency_bands(tokens: List[str]) -> Dict[str, int]:
    """
    Split vocabulary into frequency bands:
      high  — top 10% most frequent words
      mid   — next 40%
      low   — bottom 50% (rare words)
    """
    counts = Counter(tokens)
    ranked = counts.most_common()
    v = len(ranked)
    high_cut = max(1, int(v * 0.10))
    mid_cut  = max(1, int(v * 0.50))

    return {
        "high_frequency": sum(c for _, c in ranked[:high_cut]),
        "mid_frequency":  sum(c for _, c in ranked[high_cut:mid_cut]),
        "low_frequency":  sum(c for _, c in ranked[mid_cut:]),
        "high_words": high_cut,
        "mid_words":  mid_cut - high_cut,
        "low_words":  v - mid_cut,
    }


# ──────────────────────────────────────────────
# FULL FREQUENCY REPORT
# ──────────────────────────────────────────────

def frequency_report(tokens: List[str], top: int = 20) -> Dict:
    """
    Complete frequency analysis report.
    """
    return {
        "vocab_stats":   vocabulary_stats(tokens),
        "zipf":          zipf_fit(tokens),
        "top_words":     top_n(tokens, top),
        "freq_bands":    frequency_bands(tokens),
        "rank_freq":     rank_frequency(tokens)[:top],   # first N ranks
    }
