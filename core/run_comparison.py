"""
lexilab — main comparison test
Runs own algorithm vs NLTK vs spaCy vs Gensim and prints results table.
Run: python run_comparison.py
"""

import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

from core.preprocessing import preprocess
from core.frequency     import frequency_report
from core.collocations  import collocation_report, score_all_bigrams
from core.comparison.baselines import run_comparison, comparison_summary

# ──────────────────────────────────────────────
# SAMPLE DATASETS
# ──────────────────────────────────────────────

TEXT_UA = """
Статистичний аналіз текстів є важливим інструментом сучасної лінгвістики та
комп'ютерної обробки природної мови. Дослідники використовують різноманітні
методи для виявлення закономірностей у великих текстових корпусах.
Методи машинного навчання дозволяють автоматично виявляти статистичні
залежності між словами та реченнями. Частотний аналіз слів показує розподіл
лексичних одиниць у тексті. Колокації є стійкими словосполученнями, які
зустрічаються частіше ніж очікується при незалежному розподілі слів.
Метод PMI дозволяє виявляти такі стійкі словосполучення на основі
статистичної взаємної інформації між словами тексту.
Тематичне моделювання дозволяє виявляти приховані тематичні структури
у великих колекціях документів та текстових масивах даних.
Лінгвістичний аналіз тексту включає морфологічний та синтаксичний аналіз.
Статистичні методи обробки тексту знаходять широке застосування в інформаційному
пошуку, машинному перекладі та автоматичному реферуванні текстових документів.
"""

TEXT_EN = """
Statistical text analysis is an important tool in modern linguistics and
natural language processing. Researchers use various methods to discover
patterns in large text corpora. Machine learning methods allow automatic
detection of statistical dependencies between words and sentences.
Frequency analysis of words shows the distribution of lexical units in text.
Collocations are fixed word combinations that occur more frequently than
expected under independent word distribution. The PMI method allows detecting
such stable word combinations based on statistical mutual information.
Topic modeling allows discovering hidden thematic structures in large
document collections. Linguistic text analysis includes morphological and
syntactic analysis. Statistical text processing methods find wide application
in information retrieval, machine translation, and automatic text summarization.
"""


def print_separator(char="─", width=60):
    print(char * width)


def print_table(headers, rows, col_widths=None):
    if col_widths is None:
        col_widths = [max(len(str(r[i])) for r in [headers] + rows)
                      for i in range(len(headers))]
    fmt = "  ".join(f"{{:<{w}}}" for w in col_widths)
    print(fmt.format(*headers))
    print("  ".join("─" * w for w in col_widths))
    for row in rows:
        print(fmt.format(*[str(x) for x in row]))


def run():
    print("\n" + "═" * 60)
    print("  LEXILAB — Comparison Run")
    print("═" * 60)

    for lang, text in [("UA", TEXT_UA), ("EN", TEXT_EN)]:
        print(f"\n{'─'*60}")
        print(f"  Language: {lang}")
        print(f"{'─'*60}")

        # ── preprocessing ──
        prep = preprocess(text, do_lemmatize=True, do_remove_stopwords=True)
        tokens = prep["tokens"]

        print(f"\n  Preprocessing:")
        print(f"    detected lang : {prep['lang']}")
        print(f"    raw tokens    : {len(prep['tokens_raw'])}")
        print(f"    final tokens  : {prep['token_count']}")
        print(f"    unique tokens : {prep['unique_count']}")

        # ── frequency report ──
        freq = frequency_report(tokens, top=10)
        vs   = freq["vocab_stats"]
        zf   = freq["zipf"]

        print(f"\n  Vocabulary Statistics:")
        print_table(
            ["Metric", "Value"],
            [
                ["total tokens",    vs.get("total_tokens")],
                ["vocabulary size", vs.get("vocabulary_size")],
                ["hapax legomena",  vs.get("hapax_legomena")],
                ["TTR",             vs.get("ttr")],
                ["Yule's K",        vs.get("yules_k")],
                ["avg frequency",   vs.get("avg_frequency")],
            ],
            [22, 12]
        )

        print(f"\n  Zipf's Law Fit:")
        print_table(
            ["Metric", "Value"],
            [
                ["zipf constant C",      zf.get("zipf_constant")],
                ["MAE",                  zf.get("mae")],
                ["log-log correlation",  zf.get("log_log_correlation")],
                ["fits Zipf",            zf.get("fits_zipf")],
            ],
            [22, 12]
        )

        print(f"\n  Top-10 Words:")
        print_table(
            ["#", "Word", "Count"],
            [[i+1, w, c] for i, (w, c) in enumerate(freq["top_words"])],
            [4, 22, 8]
        )

        # ── collocations ──
        print(f"\n  Top-10 Collocations by PMI:")
        pmi_colls = score_all_bigrams(tokens, measure="pmi", min_freq=2, top_n=10)
        if pmi_colls:
            print_table(
                ["#", "Bigram", "Freq", "PMI"],
                [[i+1, f"{r['bigram'][0]} + {r['bigram'][1]}", r['freq'], r['score']]
                 for i, r in enumerate(pmi_colls)],
                [4, 30, 6, 10]
            )
        else:
            print("    (not enough data — need larger text)")

        print(f"\n  Top-10 Collocations by Log-Likelihood:")
        ll_colls = score_all_bigrams(tokens, measure="log_likelihood", min_freq=2, top_n=10)
        if ll_colls:
            print_table(
                ["#", "Bigram", "Freq", "G²"],
                [[i+1, f"{r['bigram'][0]} + {r['bigram'][1]}", r['freq'], r['score']]
                 for i, r in enumerate(ll_colls)],
                [4, 30, 6, 10]
            )
        else:
            print("    (not enough data)")

        # ── benchmark vs NLTK ──
        print(f"\n  Benchmark vs NLTK (time + memory):")
        comparison = run_comparison(tokens, text=text)
        summary    = comparison_summary(comparison)

        bench_rows = []
        for method, stats in summary.items():
            available = "✓" if stats["has_result"] else "✗ (not installed)"
            bench_rows.append([
                method,
                stats["time_ms"],
                stats["memory_kb"],
                available,
            ])

        print_table(
            ["Method", "Time ms", "Mem KB", "Available"],
            bench_rows,
            [28, 10, 10, 18]
        )

    print("\n" + "═" * 60)
    print("  Done.")
    print("═" * 60 + "\n")


if __name__ == "__main__":
    run()
