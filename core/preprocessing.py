"""
lexilab — preprocessing module
Tokenization, lemmatization, stopword filtering for UA/EN texts.
"""

import re
import unicodedata
from typing import List, Optional


# ──────────────────────────────────────────────
# STOP WORDS
# ──────────────────────────────────────────────

STOPWORDS_EN = {
    "a", "an", "the", "and", "or", "but", "if", "in", "on", "at", "to",
    "for", "of", "with", "by", "from", "is", "are", "was", "were", "be",
    "been", "being", "have", "has", "had", "do", "does", "did", "will",
    "would", "could", "should", "may", "might", "shall", "can", "need",
    "it", "its", "this", "that", "these", "those", "i", "you", "he",
    "she", "we", "they", "me", "him", "her", "us", "them", "my", "your",
    "his", "our", "their", "what", "which", "who", "not", "no", "so",
    "as", "up", "out", "about", "into", "than", "then", "there", "when",
    "where", "how", "all", "also", "just", "more", "some", "such",
}

STOPWORDS_UA = {
    "і", "й", "та", "або", "але", "якщо", "в", "у", "на", "до", "від",
    "з", "із", "зі", "за", "по", "при", "про", "для", "як", "що", "це",
    "той", "та", "ця", "ці", "він", "вона", "вони", "ми", "ви", "я",
    "його", "її", "їх", "нас", "вас", "мене", "тебе", "собі", "свій",
    "своя", "своє", "свої", "є", "був", "була", "були", "буде", "бути",
    "не", "ні", "так", "вже", "ще", "теж", "також", "тільки", "навіть",
    "більш", "менш", "дуже", "весь", "вся", "все", "всі", "який", "яка",
    "яке", "які", "де", "коли", "хто", "чого", "того", "цього", "після",
    "через", "між", "над", "під", "без", "перед", "коло", "біля", "проти",
}


# ──────────────────────────────────────────────
# LANGUAGE DETECTION (simple heuristic)
# ──────────────────────────────────────────────

def detect_language(text: str) -> str:
    """
    Simple UA/EN detection based on character frequency.
    Returns 'ua', 'en', or 'mixed'.
    Mixed = significant presence of both scripts (>15% each).
    """
    ua_chars = sum(1 for c in text if '\u0400' <= c <= '\u04FF')
    en_chars = sum(1 for c in text if 'a' <= c.lower() <= 'z')
    total = ua_chars + en_chars

    if total == 0:
        return "unknown"

    ua_ratio = ua_chars / total
    en_ratio = en_chars / total

    # mixed: both scripts present significantly
    if ua_ratio >= 0.15 and en_ratio >= 0.15:
        return "mixed"
    if ua_ratio > 0.5:
        return "ua"
    return "en"


# ──────────────────────────────────────────────
# CLEANING
# ──────────────────────────────────────────────

def clean_text(text: str) -> str:
    """
    Remove URLs, punctuation, digits, extra whitespace.
    Preserve Cyrillic and Latin letters.
    """
    # normalize unicode (e.g. combining characters)
    text = unicodedata.normalize("NFC", text)
    # remove URLs
    text = re.sub(r'https?://\S+|www\.\S+', ' ', text)
    # remove email addresses
    text = re.sub(r'\S+@\S+', ' ', text)
    # remove digits
    text = re.sub(r'\d+', ' ', text)
    # keep only letters (Cyrillic + Latin) and spaces
    text = re.sub(r'[^\w\s]', ' ', text, flags=re.UNICODE)
    text = re.sub(r'_+', ' ', text)
    # collapse whitespace
    text = re.sub(r'\s+', ' ', text).strip()
    return text.lower()


# ──────────────────────────────────────────────
# TOKENIZATION
# ──────────────────────────────────────────────

def tokenize(text: str) -> List[str]:
    """
    Split cleaned text into tokens (words).
    Filters out single-character tokens.
    """
    text = clean_text(text)
    tokens = text.split()
    return [t for t in tokens if len(t) > 1]


# ──────────────────────────────────────────────
# SIMPLE LEMMATIZATION (rule-based for UA)
# ──────────────────────────────────────────────

# Ukrainian noun/adjective endings → base form suffixes
UA_ENDINGS = [
    # longest first (greedy match)
    ("ського", "ський"), ("ської", "ський"), ("ськими", "ський"),
    ("ськими", "ський"), ("ського", "ський"),
    ("ення", "ення"), ("ання", "ання"),
    ("ують", "увати"), ("юють", "ювати"),
    ("ується", "уватися"), ("юється", "юватися"),
    ("ували", "увати"), ("юнали", "ювати"),
    ("ують", "увати"),
    ("ають", "ати"), ("яють", "яти"),
    ("ають", "ати"),
    ("ами", "а"), ("ями", "я"),
    ("ові", "о"), ("еві", "е"), ("єві", "є"),
    ("ого", "ий"), ("ому", "ий"), ("ому", "е"),
    ("ого", "е"),
    ("ість", "ість"),
    ("істю", "ість"),
    ("ості", "ість"),
    ("ою", "а"), ("ею", "я"), ("єю", "я"),
    ("ах", "а"), ("ях", "я"),
    ("ів", "о"), ("ей", "е"),
    ("ів", ""), ("їв", ""),
    ("ою", "а"),
    ("ти", "ти"),   # infinitive — keep as-is
    ("ся", "ся"),
    ("ів", ""),
    ("и", ""), ("і", ""), ("е", ""), ("а", ""), ("я", ""),
    ("у", ""), ("ю", ""),
]


def lemmatize_ua_word(word: str) -> str:
    """
    Rule-based lemmatization for Ukrainian.
    Strips common inflectional endings.
    Only applies when word is long enough to avoid over-stemming.
    """
    if len(word) < 5:
        return word
    for ending, replacement in UA_ENDINGS:
        if word.endswith(ending) and len(word) - len(ending) >= 3:
            return word[:-len(ending)] + replacement
    return word


def lemmatize(tokens: List[str], lang: str = "auto") -> List[str]:
    """
    Apply lemmatization to token list.
    For EN: simple suffix stripping (Porter-lite).
    For UA: rule-based ending removal.
    """
    if lang == "auto":
        sample = " ".join(tokens[:50])
        lang = detect_language(sample)

    if lang == "en":
        return [_porter_lite(t) for t in tokens]
    elif lang == "ua":
        return [lemmatize_ua_word(t) for t in tokens]
    else:
        # mixed: detect per-token
        result = []
        for t in tokens:
            if detect_language(t) == "ua":
                result.append(lemmatize_ua_word(t))
            else:
                result.append(_porter_lite(t))
        return result


def _porter_lite(word: str) -> str:
    """
    Minimal Porter-like stemmer for English.
    Handles the most common suffixes only.
    """
    if len(word) < 4:
        return word
    suffixes = [
        ("ational", "ate"), ("tional", "tion"), ("enci", "ence"),
        ("anci", "ance"), ("izer", "ize"), ("ising", "ise"),
        ("izing", "ize"), ("ational", "ate"), ("alism", "al"),
        ("iveness", "ive"), ("fulness", "ful"), ("ousness", "ous"),
        ("aliti", "al"), ("iviti", "ive"), ("biliti", "ble"),
        ("nesses", ""), ("ments", ""), ("ement", ""),
        ("ments", ""), ("ation", "ate"), ("ators", "ate"),
        ("alism", "al"), ("ation", ""), ("ators", ""),
        ("ing", ""), ("ings", ""), ("edly", ""), ("edly", "ed"),
        ("ingly", ""), ("ingly", "ing"),
        ("ness", ""), ("less", ""), ("tion", "te"), ("sion", "se"),
        ("ment", ""), ("able", ""), ("ible", ""), ("ance", ""),
        ("ence", ""), ("ful", ""), ("ous", ""), ("ive", ""),
        ("ize", ""), ("ise", ""), ("ate", ""), ("al", ""),
        ("ed", ""), ("es", ""), ("er", ""), ("ly", ""),
        ("'s", ""), ("s", ""),
    ]
    for suffix, replacement in suffixes:
        if word.endswith(suffix) and len(word) - len(suffix) >= 3:
            return word[:-len(suffix)] + replacement
    return word


# ──────────────────────────────────────────────
# STOPWORD FILTERING
# ──────────────────────────────────────────────

def remove_stopwords(
    tokens: List[str],
    lang: str = "auto",
    extra_stopwords: Optional[set] = None
) -> List[str]:
    """
    Remove stopwords from token list.
    """
    if lang == "auto":
        sample = " ".join(tokens[:50])
        lang = detect_language(sample)

    if lang == "ua":
        stops = STOPWORDS_UA
    elif lang == "en":
        stops = STOPWORDS_EN
    else:
        stops = STOPWORDS_UA | STOPWORDS_EN

    if extra_stopwords:
        stops = stops | extra_stopwords

    return [t for t in tokens if t not in stops]


# ──────────────────────────────────────────────
# FULL PIPELINE
# ──────────────────────────────────────────────

def preprocess(
    text: str,
    lang: str = "auto",
    do_lemmatize: bool = True,
    do_remove_stopwords: bool = True,
    min_token_len: int = 2,
    extra_stopwords: Optional[set] = None,
) -> dict:
    """
    Full preprocessing pipeline.

    Returns:
        {
            "lang": detected language,
            "tokens_raw": tokens before lemmatization/filtering,
            "tokens": final processed tokens,
            "token_count": int,
            "unique_count": int,
        }
    """
    detected_lang = detect_language(text) if lang == "auto" else lang

    tokens_raw = tokenize(text)

    tokens = tokens_raw.copy()

    if do_lemmatize:
        tokens = lemmatize(tokens, lang=detected_lang)

    if do_remove_stopwords:
        tokens = remove_stopwords(tokens, lang=detected_lang, extra_stopwords=extra_stopwords)

    # min length filter after lemmatization
    tokens = [t for t in tokens if len(t) >= min_token_len]

    return {
        "lang": detected_lang,
        "tokens_raw": tokens_raw,
        "tokens": tokens,
        "token_count": len(tokens),
        "unique_count": len(set(tokens)),
    }