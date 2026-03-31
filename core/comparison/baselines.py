"""
lexilab — comparison baselines
Same tasks via NLTK, spaCy, Gensim for numerical comparison.
"""

import time
import tracemalloc
from typing import List, Dict, Optional


# ──────────────────────────────────────────────
# BENCHMARK WRAPPER
# ──────────────────────────────────────────────

def benchmark(fn, *args, **kwargs) -> Dict:
    """
    Run a function and measure time + memory.
    Returns {"result": ..., "time_ms": ..., "memory_kb": ...}
    """
    tracemalloc.start()
    t0 = time.perf_counter()

    result = fn(*args, **kwargs)

    t1 = time.perf_counter()
    _, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()

    return {
        "result":    result,
        "time_ms":   round((t1 - t0) * 1000, 3),
        "memory_kb": round(peak / 1024, 2),
    }


# ──────────────────────────────────────────────
# NLTK BASELINE
# ──────────────────────────────────────────────

def nltk_frequency(tokens: List[str]) -> Optional[Dict]:
    """Word frequency via NLTK FreqDist."""
    try:
        from nltk import FreqDist
        fd = FreqDist(tokens)
        return dict(fd.most_common(20))
    except ImportError:
        return None


def nltk_collocations(tokens: List[str], top_n: int = 20) -> Optional[List]:
    """Top bigram collocations via NLTK BigramAssocMeasures."""
    try:
        from nltk.collocations import BigramCollocationFinder
        from nltk.metrics import BigramAssocMeasures

        finder = BigramCollocationFinder.from_words(tokens)
        finder.apply_freq_filter(2)
        scored = finder.score_ngrams(BigramAssocMeasures.pmi)
        return [(list(bg), round(score, 4)) for bg, score in scored[:top_n]]
    except ImportError:
        return None


def nltk_trigrams(tokens: List[str], top_n: int = 20) -> Optional[List]:
    """Top trigram collocations via NLTK."""
    try:
        from nltk.collocations import TrigramCollocationFinder
        from nltk.metrics import TrigramAssocMeasures

        finder = TrigramCollocationFinder.from_words(tokens)
        finder.apply_freq_filter(2)
        scored = finder.score_ngrams(TrigramAssocMeasures.pmi)
        return [(list(tg), round(score, 4)) for tg, score in scored[:top_n]]
    except ImportError:
        return None


# ──────────────────────────────────────────────
# SPACY BASELINE
# ──────────────────────────────────────────────

def spacy_tokenize(text: str, model: str = "en_core_web_sm") -> Optional[Dict]:
    """
    Tokenize + lemmatize via spaCy.
    Returns tokens, lemmas, pos tags.
    """
    try:
        import spacy
        nlp = spacy.load(model)
        doc = nlp(text)
        return {
            "tokens": [t.text for t in doc if not t.is_punct and not t.is_space],
            "lemmas": [t.lemma_ for t in doc if not t.is_punct and not t.is_space],
            "pos":    [(t.text, t.pos_) for t in doc if not t.is_punct and not t.is_space],
        }
    except (ImportError, OSError):
        return None


def spacy_noun_chunks(text: str, model: str = "en_core_web_sm") -> Optional[List]:
    """Extract noun phrases (potential collocations) via spaCy."""
    try:
        import spacy
        nlp = spacy.load(model)
        doc = nlp(text)
        return [chunk.text.lower() for chunk in doc.noun_chunks]
    except (ImportError, OSError):
        return None


# ──────────────────────────────────────────────
# GENSIM BASELINE
# ──────────────────────────────────────────────

def gensim_phrases(sentences: List[List[str]], min_count: int = 2) -> Optional[List]:
    """
    Detect phrases (collocations) via Gensim Phrases.
    Input: list of token lists (sentences).
    """
    try:
        from gensim.models import Phrases
        from gensim.models.phrases import Phraser

        phrases_model = Phrases(sentences, min_count=min_count, threshold=10)
        phraser = Phraser(phrases_model)

        result = []
        for sent in sentences:
            phrased = phraser[sent]
            for token in phrased:
                if '_' in token:
                    result.append(token.replace('_', ' '))
        return list(set(result))
    except ImportError:
        return None


def gensim_tfidf(corpus_tokens: List[List[str]], top_n: int = 20) -> Optional[List]:
    """
    TF-IDF scoring via Gensim.
    Input: list of documents, each a list of tokens.
    Returns top-N terms by TF-IDF for first document.
    """
    try:
        from gensim import corpora, models

        dictionary = corpora.Dictionary(corpus_tokens)
        bow_corpus  = [dictionary.doc2bow(doc) for doc in corpus_tokens]
        tfidf       = models.TfidfModel(bow_corpus)

        scored = sorted(
            tfidf[bow_corpus[0]],
            key=lambda x: x[1],
            reverse=True
        )[:top_n]

        return [(dictionary[tid], round(score, 4)) for tid, score in scored]
    except ImportError:
        return None


# ──────────────────────────────────────────────
# FULL COMPARISON RUNNER
# ──────────────────────────────────────────────

def run_comparison(
    tokens: List[str],
    text: str = "",
    sentences: Optional[List[List[str]]] = None,
) -> Dict:
    """
    Run lexilab vs NLTK vs spaCy vs Gensim on same input.
    Returns benchmarked results for all methods.
    """
    from core.frequency    import frequency_report
    from core.collocations import score_all_bigrams

    results = {}

    # ── lexilab (own) ──
    results["lexilab_frequency"] = benchmark(frequency_report, tokens)
    results["lexilab_pmi"]       = benchmark(score_all_bigrams, tokens, "pmi")
    results["lexilab_ll"]        = benchmark(score_all_bigrams, tokens, "log_likelihood")
    results["lexilab_chi2"]      = benchmark(score_all_bigrams, tokens, "chi_square")

    # ── NLTK ──
    results["nltk_frequency"]    = benchmark(nltk_frequency, tokens)
    results["nltk_collocations"] = benchmark(nltk_collocations, tokens)

    # ── spaCy ──
    if text:
        results["spacy_tokenize"]    = benchmark(spacy_tokenize, text)
        results["spacy_noun_chunks"] = benchmark(spacy_noun_chunks, text)

    # ── Gensim ──
    if sentences:
        results["gensim_phrases"] = benchmark(gensim_phrases, sentences)
        results["gensim_tfidf"]   = benchmark(gensim_tfidf, sentences)

    return results


def comparison_summary(comparison: Dict) -> Dict:
    """
    Extract just timing + memory for each method.
    Useful for the benchmark table in the thesis.
    """
    summary = {}
    for method, data in comparison.items():
        summary[method] = {
            "time_ms":   data.get("time_ms"),
            "memory_kb": data.get("memory_kb"),
            "has_result": data.get("result") is not None,
        }
    return summary
