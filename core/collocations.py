"""
lexilab — collocations module
PMI, t-test, chi-square, log-likelihood for bigram collocation detection.
"""

import math
from collections import Counter
from typing import List, Dict, Tuple


# ──────────────────────────────────────────────
# BIGRAM EXTRACTION
# ──────────────────────────────────────────────

def extract_bigrams(tokens: List[str]) -> List[Tuple[str, str]]:
    """Extract all consecutive bigrams from token list."""
    return [(tokens[i], tokens[i + 1]) for i in range(len(tokens) - 1)]


def extract_ngrams(tokens: List[str], n: int = 2) -> List[Tuple]:
    """Extract all n-grams of size n."""
    return [tuple(tokens[i:i + n]) for i in range(len(tokens) - n + 1)]


def bigram_counts(tokens: List[str]) -> Tuple[Counter, Counter, Counter, int]:
    """
    Compute all counts needed for association measures.
    Returns:
        bigram_freq   — Counter of (w1, w2)
        unigram_freq  — Counter of w
        pair_freq     — Counter of (w1, w2) sorted
        N             — total tokens
    """
    unigram_freq = Counter(tokens)
    bigrams      = extract_bigrams(tokens)
    bigram_freq  = Counter(bigrams)
    N            = len(tokens)
    return bigram_freq, unigram_freq, bigram_freq, N


# ──────────────────────────────────────────────
# ASSOCIATION MEASURES
# ──────────────────────────────────────────────

def pmi(w1: str, w2: str,
        bigram_freq: Counter, unigram_freq: Counter, N: int) -> float:
    """
    Pointwise Mutual Information:
        PMI(w1,w2) = log2( P(w1,w2) / (P(w1)*P(w2)) )

    Positive PMI → words co-occur more than by chance.
    """
    f_w1w2 = bigram_freq[(w1, w2)]
    f_w1   = unigram_freq[w1]
    f_w2   = unigram_freq[w2]

    if f_w1w2 == 0 or f_w1 == 0 or f_w2 == 0:
        return float('-inf')

    p_w1w2 = f_w1w2 / (N - 1)
    p_w1   = f_w1 / N
    p_w2   = f_w2 / N

    return math.log2(p_w1w2 / (p_w1 * p_w2))


def npmi(w1: str, w2: str,
         bigram_freq: Counter, unigram_freq: Counter, N: int) -> float:
    """
    Normalized PMI: NPMI = PMI / -log2(P(w1,w2))
    Range: [-1, 1]  — 1 = always together, -1 = never together
    """
    raw_pmi = pmi(w1, w2, bigram_freq, unigram_freq, N)
    if raw_pmi == float('-inf'):
        return -1.0

    f_w1w2 = bigram_freq[(w1, w2)]
    p_w1w2 = f_w1w2 / (N - 1)

    if p_w1w2 <= 0:
        return -1.0

    denom = -math.log2(p_w1w2)
    return raw_pmi / denom if denom != 0 else 0.0


def t_score(w1: str, w2: str,
            bigram_freq: Counter, unigram_freq: Counter, N: int) -> float:
    """
    T-score (t-test for collocations):
        t = (O - E) / sqrt(O)
    where O = observed bigram count, E = expected under independence.

    t > 2.576 → significant at p < 0.01
    """
    O = bigram_freq[(w1, w2)]
    if O == 0:
        return 0.0

    p_w1 = unigram_freq[w1] / N
    p_w2 = unigram_freq[w2] / N
    E    = p_w1 * p_w2 * (N - 1)

    return (O - E) / math.sqrt(O) if O > 0 else 0.0


def chi_square(w1: str, w2: str,
               bigram_freq: Counter, unigram_freq: Counter, N: int) -> float:
    """
    Chi-square test for collocation significance.
    Uses 2x2 contingency table:
        O11 = count(w1, w2)
        O12 = count(w1, NOT w2)
        O21 = count(NOT w1, w2)
        O22 = count(NOT w1, NOT w2)

    χ² > 10.83 → significant at p < 0.001
    """
    O11 = bigram_freq[(w1, w2)]
    O12 = unigram_freq[w1] - O11
    O21 = unigram_freq[w2] - O11
    O22 = N - O11 - O12 - O21

    if O11 == 0:
        return 0.0

    # expected values
    R1 = O11 + O12
    R2 = O21 + O22
    C1 = O11 + O21
    C2 = O12 + O22

    if R1 == 0 or R2 == 0 or C1 == 0 or C2 == 0:
        return 0.0

    E11 = R1 * C1 / N
    E12 = R1 * C2 / N
    E21 = R2 * C1 / N
    E22 = R2 * C2 / N

    def term(O, E):
        return ((O - E) ** 2 / E) if E > 0 else 0.0

    return term(O11, E11) + term(O12, E12) + term(O21, E21) + term(O22, E22)


def log_likelihood(w1: str, w2: str,
                   bigram_freq: Counter, unigram_freq: Counter, N: int) -> float:
    """
    Dunning's Log-Likelihood Ratio (G²).
    More reliable than chi-square for sparse data.
    G² > 10.83 → significant at p < 0.001

    G² = 2 * Σ O * log(O/E)
    """
    O11 = bigram_freq[(w1, w2)]
    O12 = unigram_freq[w1] - O11
    O21 = unigram_freq[w2] - O11
    O22 = N - O11 - O12 - O21

    if O11 == 0:
        return 0.0

    R1 = O11 + O12
    R2 = O21 + O22
    C1 = O11 + O21
    C2 = O12 + O22

    if R1 == 0 or R2 == 0 or C1 == 0 or C2 == 0:
        return 0.0

    E11 = R1 * C1 / N
    E12 = R1 * C2 / N
    E21 = R2 * C1 / N
    E22 = R2 * C2 / N

    def ll_term(O, E):
        if O == 0 or E == 0:
            return 0.0
        return O * math.log(O / E)

    return 2 * (ll_term(O11, E11) + ll_term(O12, E12) +
                ll_term(O21, E21) + ll_term(O22, E22))


# ──────────────────────────────────────────────
# COLLOCATION RANKING
# ──────────────────────────────────────────────

def score_all_bigrams(
    tokens: List[str],
    measure: str = "pmi",
    min_freq: int = 2,
    top_n: int = 30,
) -> List[Dict]:
    """
    Score all bigrams using the chosen association measure.

    Args:
        tokens    — preprocessed token list
        measure   — 'pmi' | 'npmi' | 't_score' | 'chi_square' | 'log_likelihood'
        min_freq  — minimum bigram frequency (filter noise)
        top_n     — return top N collocations

    Returns list of dicts sorted by score descending.
    """
    bigram_freq, unigram_freq, _, N = bigram_counts(tokens)

    if N < 2:
        return []

    measure_fn = {
        "pmi":            pmi,
        "npmi":           npmi,
        "t_score":        t_score,
        "chi_square":     chi_square,
        "log_likelihood": log_likelihood,
    }.get(measure)

    if measure_fn is None:
        raise ValueError(f"Unknown measure: {measure}. "
                         f"Choose from: pmi, npmi, t_score, chi_square, log_likelihood")

    results = []
    for (w1, w2), freq in bigram_freq.items():
        if freq < min_freq:
            continue
        score = measure_fn(w1, w2, bigram_freq, unigram_freq, N)
        results.append({
            "bigram":   (w1, w2),
            "freq":     freq,
            "score":    round(score, 4),
            "measure":  measure,
        })

    results.sort(key=lambda x: x["score"], reverse=True)
    return results[:top_n]


def collocation_report(
    tokens: List[str],
    min_freq: int = 2,
    top_n: int = 20,
) -> Dict:
    """
    Full collocation report using all 5 measures.
    Useful for comparing which measure surfaces different collocations.
    """
    measures = ["pmi", "npmi", "t_score", "chi_square", "log_likelihood"]
    report = {}
    for m in measures:
        report[m] = score_all_bigrams(tokens, measure=m,
                                      min_freq=min_freq, top_n=top_n)
    return report
