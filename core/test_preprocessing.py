"""
Quick tests for preprocessing module.
Run: python test_preprocessing.py
"""

import sys
sys.path.insert(0, '..')

from core.preprocessing import (
    detect_language, clean_text, tokenize,
    lemmatize, remove_stopwords, preprocess
)

# ── test texts ──────────────────────────────────
TEXT_UA = """
Статистичний аналіз текстів є важливим інструментом сучасної лінгвістики.
Дослідники використовують різноманітні методи для виявлення закономірностей
у великих текстових корпусах. Методи машинного навчання дозволяють автоматично
виявляти статистичні залежності між словами та реченнями.
"""

TEXT_EN = """
Statistical text analysis is an important tool in modern linguistics.
Researchers use various methods to discover patterns in large text corpora.
Machine learning methods allow automatic detection of statistical dependencies
between words and sentences.
"""

TEXT_MIXED = "Метод PMI (pointwise mutual information) широко використовується в NLP задачах."


def test(name, result, expected=None):
    status = "✓" if (expected is None or result == expected) else "✗"
    print(f"  {status} {name}: {result}")


def run_tests():
    print("\n=== LANGUAGE DETECTION ===")
    test("UA text",   detect_language(TEXT_UA),    "ua")
    test("EN text",   detect_language(TEXT_EN),    "en")
    test("mixed",     detect_language(TEXT_MIXED))

    print("\n=== CLEAN TEXT ===")
    dirty = "Привіт! Це тест-рядок, з числами 123 та URL https://example.com."
    cleaned = clean_text(dirty)
    test("cleaned", cleaned)
    test("no digits", any(c.isdigit() for c in cleaned), False)
    test("lowercase", cleaned == cleaned.lower(), True)

    print("\n=== TOKENIZE ===")
    tokens_ua = tokenize(TEXT_UA)
    tokens_en = tokenize(TEXT_EN)
    test("UA token count > 10", len(tokens_ua) > 10, True)
    test("EN token count > 10", len(tokens_en) > 10, True)
    test("no single chars", all(len(t) > 1 for t in tokens_ua), True)
    print(f"  • UA sample tokens: {tokens_ua[:8]}")
    print(f"  • EN sample tokens: {tokens_en[:8]}")

    print("\n=== LEMMATIZE ===")
    test_ua_words = ["дослідники", "використовують", "закономірностей", "методами"]
    lemmas_ua = lemmatize(test_ua_words, lang="ua")
    test("UA lemmatized", lemmas_ua)

    test_en_words = ["researchers", "dependencies", "running", "quickly", "statistical"]
    lemmas_en = lemmatize(test_en_words, lang="en")
    test("EN lemmatized", lemmas_en)

    print("\n=== REMOVE STOPWORDS ===")
    tokens = tokenize(TEXT_UA)
    filtered = remove_stopwords(tokens, lang="ua")
    test("fewer tokens after stopwords", len(filtered) < len(tokens), True)
    test("'і' removed", "і" not in filtered, True)
    test("'та' removed", "та" not in filtered, True)

    print("\n=== FULL PIPELINE ===")
    result_ua = preprocess(TEXT_UA)
    print(f"  • lang: {result_ua['lang']}")
    print(f"  • raw tokens: {len(result_ua['tokens_raw'])}")
    print(f"  • final tokens: {result_ua['token_count']}")
    print(f"  • unique: {result_ua['unique_count']}")
    print(f"  • sample: {result_ua['tokens'][:10]}")

    result_en = preprocess(TEXT_EN)
    print(f"\n  • lang: {result_en['lang']}")
    print(f"  • raw tokens: {len(result_en['tokens_raw'])}")
    print(f"  • final tokens: {result_en['token_count']}")
    print(f"  • unique: {result_en['unique_count']}")
    print(f"  • sample: {result_en['tokens'][:10]}")

    print("\n=== DONE ===\n")


if __name__ == "__main__":
    run_tests()
