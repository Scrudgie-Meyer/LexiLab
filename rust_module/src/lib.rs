// lexilab — Rust core implementation
// Власна реалізація алгоритмів статистичного аналізу тексту

use pyo3::prelude::*;
use pyo3::wrap_pyfunction;
use std::collections::HashMap;
use unicode_segmentation::UnicodeSegmentation;

// ─────────────────────────────────────────────
// PREPROCESSING
// ─────────────────────────────────────────────

/// Токенізація тексту — власна реалізація
/// Розбиває текст на слова, видаляє пунктуацію, приводить до нижнього регістру
#[pyfunction]
fn tokenize(text: &str) -> Vec<String> {
    text.unicode_words()
        .map(|w| w.to_lowercase())
        .filter(|w| w.chars().count() > 1)
        .filter(|w| w.chars().any(|c| c.is_alphabetic()))
        .collect()
}

/// Детекція мови через whatlang (бібліотечна реалізація для порівняння)
#[pyfunction]
fn detect_language_lib(text: &str) -> String {
    match whatlang::detect(text) {
        Some(info) => match info.lang() {
            whatlang::Lang::Ukr => "ua".to_string(),
            whatlang::Lang::Eng => "en".to_string(),
            other => format!("{:?}", other).to_lowercase(),
        },
        None => "unknown".to_string(),
    }
}

/// Детекція мови — власна реалізація (по частці кириличних символів)
#[pyfunction]
fn detect_language_own(text: &str) -> String {
    let ua_count = text.chars().filter(|c| ('\u{0400}'..='\u{04FF}').contains(c)).count();
    let en_count = text.chars().filter(|c| c.is_ascii_alphabetic()).count();
    let total = ua_count + en_count;

    if total == 0 {
        return "unknown".to_string();
    }
    let ua_ratio = ua_count as f64 / total as f64;
    if ua_ratio > 0.6 {
        "ua".to_string()
    } else if ua_ratio < 0.2 {
        "en".to_string()
    } else {
        "mixed".to_string()
    }
}

// ─────────────────────────────────────────────
// FREQUENCY ANALYSIS — власна реалізація
// ─────────────────────────────────────────────

/// Підрахунок частот слів
/// Повертає словник {слово: кількість}, відсортований за спаданням
#[pyfunction]
fn word_frequency(tokens: Vec<String>) -> HashMap<String, usize> {
    let mut freq: HashMap<String, usize> = HashMap::new();
    for token in &tokens {
        *freq.entry(token.clone()).or_insert(0) += 1;
    }
    freq
}

/// Топ-N найчастіших слів
#[pyfunction]
fn top_n_words(tokens: Vec<String>, n: usize) -> Vec<(String, usize)> {
    let freq = word_frequency(tokens);
    let mut pairs: Vec<(String, usize)> = freq.into_iter().collect();
    pairs.sort_by(|a, b| b.1.cmp(&a.1).then(a.0.cmp(&b.0)));
    pairs.truncate(n);
    pairs
}

/// Статистика словника
#[pyfunction]
fn vocabulary_stats(tokens: Vec<String>) -> HashMap<String, f64> {
    let total = tokens.len();
    if total == 0 {
        return HashMap::new();
    }

    let freq = word_frequency(tokens.clone());
    let vocab = freq.len();
    let hapax = freq.values().filter(|&&c| c == 1).count();
    let dis   = freq.values().filter(|&&c| c == 2).count();

    // Type-Token Ratio
    let ttr = vocab as f64 / total as f64;

    // Hapax ratio
    let hapax_ratio = hapax as f64 / vocab as f64;

    // Yule's K
    let yules_k = yules_k_score(&freq, total);

    let mut stats = HashMap::new();
    stats.insert("total_tokens".to_string(),  total as f64);
    stats.insert("vocabulary_size".to_string(), vocab as f64);
    stats.insert("hapax_legomena".to_string(), hapax as f64);
    stats.insert("dis_legomena".to_string(),  dis as f64);
    stats.insert("ttr".to_string(),           (ttr * 10000.0).round() / 10000.0);
    stats.insert("hapax_ratio".to_string(),   (hapax_ratio * 10000.0).round() / 10000.0);
    stats.insert("yules_k".to_string(),       (yules_k * 100.0).round() / 100.0);
    stats.insert("avg_frequency".to_string(), (total as f64 / vocab as f64 * 100.0).round() / 100.0);
    stats
}

/// Yule's K — міра лексичного багатства
fn yules_k_score(freq: &HashMap<String, usize>, total: usize) -> f64 {
    if total == 0 { return 0.0; }
    let mut freq_of_freq: HashMap<usize, usize> = HashMap::new();
    for &count in freq.values() {
        *freq_of_freq.entry(count).or_insert(0) += 1;
    }
    let sum_m2: f64 = freq_of_freq.iter()
        .map(|(&m, &v)| v as f64 * (m as f64).powi(2))
        .sum();
    let k = 10_000.0 * (sum_m2 - total as f64) / (total as f64).powi(2);
    k.max(0.0)
}

/// Закон Зіпфа — оцінка відповідності
#[pyfunction]
fn zipf_fit(tokens: Vec<String>) -> HashMap<String, f64> {
    let freq = word_frequency(tokens.clone());
    let total = tokens.len();
    if freq.len() < 2 || total == 0 {
        return HashMap::new();
    }

    let mut ranked: Vec<usize> = freq.values().cloned().collect();
    ranked.sort_unstable_by(|a, b| b.cmp(a));

    let c = ranked[0] as f64 / total as f64;

    // MAE між ідеальним Зіпфом і реальним
    let mae: f64 = ranked.iter().enumerate()
        .map(|(i, &f)| {
            let ideal = c / (i + 1) as f64;
            (f as f64 / total as f64 - ideal).abs()
        })
        .sum::<f64>() / ranked.len() as f64;

    // Кореляція Пірсона у log-log шкалі
    let log_ranks: Vec<f64> = (1..=ranked.len()).map(|r| (r as f64).ln()).collect();
    let log_freqs: Vec<f64> = ranked.iter()
        .map(|&f| if f > 0 { (f as f64 / total as f64).ln() } else { 0.0 })
        .collect();
    let corr = pearson(&log_ranks, &log_freqs);

    let mut result = HashMap::new();
    result.insert("zipf_constant".to_string(),      (c * 1_000_000.0).round() / 1_000_000.0);
    result.insert("mae".to_string(),                (mae * 1_000_000.0).round() / 1_000_000.0);
    result.insert("log_log_correlation".to_string(), (corr * 10000.0).round() / 10000.0);
    result.insert("fits_zipf".to_string(),           if corr < -0.85 { 1.0 } else { 0.0 });
    result
}

fn pearson(x: &[f64], y: &[f64]) -> f64 {
    let n = x.len() as f64;
    if n < 2.0 { return 0.0; }
    let mx = x.iter().sum::<f64>() / n;
    let my = y.iter().sum::<f64>() / n;
    let num: f64 = x.iter().zip(y).map(|(xi, yi)| (xi - mx) * (yi - my)).sum();
    let dx: f64 = x.iter().map(|xi| (xi - mx).powi(2)).sum::<f64>().sqrt();
    let dy: f64 = y.iter().map(|yi| (yi - my).powi(2)).sum::<f64>().sqrt();
    if dx * dy == 0.0 { 0.0 } else { num / (dx * dy) }
}

// ─────────────────────────────────────────────
// COLLOCATIONS — власна реалізація
// ─────────────────────────────────────────────

/// Витяг біграмів
fn extract_bigrams(tokens: &[String]) -> Vec<(String, String)> {
    tokens.windows(2)
        .map(|w| (w[0].clone(), w[1].clone()))
        .collect()
}

/// PMI — Pointwise Mutual Information
/// PMI(w1,w2) = log2( P(w1,w2) / (P(w1) * P(w2)) )
#[pyfunction]
fn pmi_score(
    w1: &str, w2: &str,
    bigram_count: usize,
    w1_count: usize,
    w2_count: usize,
    total_tokens: usize,
) -> f64 {
    if bigram_count == 0 || w1_count == 0 || w2_count == 0 || total_tokens < 2 {
        return f64::NEG_INFINITY;
    }
    let p_w1w2 = bigram_count as f64 / (total_tokens - 1) as f64;
    let p_w1   = w1_count as f64 / total_tokens as f64;
    let p_w2   = w2_count as f64 / total_tokens as f64;
    (p_w1w2 / (p_w1 * p_w2)).log2()
}

/// Chi-square для біграму
/// Використовує таблицю 2x2 спостережень
#[pyfunction]
fn chi_square_score(
    w1: &str, w2: &str,
    bigram_count: usize,
    w1_count: usize,
    w2_count: usize,
    total_tokens: usize,
) -> f64 {
    let _ = (w1, w2);
    let o11 = bigram_count as f64;
    let o12 = (w1_count - bigram_count) as f64;
    let o21 = (w2_count - bigram_count) as f64;
    let n   = total_tokens as f64;
    let o22 = n - o11 - o12 - o21;

    if o11 == 0.0 { return 0.0; }

    let r1 = o11 + o12;
    let r2 = o21 + o22;
    let c1 = o11 + o21;
    let c2 = o12 + o22;

    if r1 == 0.0 || r2 == 0.0 || c1 == 0.0 || c2 == 0.0 { return 0.0; }

    let e11 = r1 * c1 / n;
    let e12 = r1 * c2 / n;
    let e21 = r2 * c1 / n;
    let e22 = r2 * c2 / n;

    let term = |o: f64, e: f64| if e > 0.0 { (o - e).powi(2) / e } else { 0.0 };
    term(o11, e11) + term(o12, e12) + term(o21, e21) + term(o22, e22)
}

/// Log-Likelihood Ratio (G²) — метод Даннінга
/// Надійніший за chi-square для розріджених даних
#[pyfunction]
fn log_likelihood_score(
    w1: &str, w2: &str,
    bigram_count: usize,
    w1_count: usize,
    w2_count: usize,
    total_tokens: usize,
) -> f64 {
    let _ = (w1, w2);
    let o11 = bigram_count as f64;
    let o12 = (w1_count.saturating_sub(bigram_count)) as f64;
    let o21 = (w2_count.saturating_sub(bigram_count)) as f64;
    let n   = total_tokens as f64;
    let o22 = (n - o11 - o12 - o21).max(0.0);

    if o11 == 0.0 { return 0.0; }

    let r1 = o11 + o12;
    let r2 = o21 + o22;
    let c1 = o11 + o21;
    let c2 = o12 + o22;

    if r1 == 0.0 || r2 == 0.0 || c1 == 0.0 || c2 == 0.0 { return 0.0; }

    let e11 = r1 * c1 / n;
    let e12 = r1 * c2 / n;
    let e21 = r2 * c1 / n;
    let e22 = r2 * c2 / n;

    let ll = |o: f64, e: f64| if o > 0.0 && e > 0.0 { o * (o / e).ln() } else { 0.0 };
    2.0 * (ll(o11, e11) + ll(o12, e12) + ll(o21, e21) + ll(o22, e22))
}

/// T-score для біграму
#[pyfunction]
fn t_score_score(
    w1: &str, w2: &str,
    bigram_count: usize,
    w1_count: usize,
    w2_count: usize,
    total_tokens: usize,
) -> f64 {
    let _ = (w1, w2);
    let o = bigram_count as f64;
    if o == 0.0 { return 0.0; }
    let p_w1 = w1_count as f64 / total_tokens as f64;
    let p_w2 = w2_count as f64 / total_tokens as f64;
    let e    = p_w1 * p_w2 * (total_tokens - 1) as f64;
    (o - e) / o.sqrt()
}

/// Повний аналіз колокацій — всі 4 міри одразу
/// Повертає топ-N біграмів відсортованих за обраною мірою
#[pyfunction]
fn score_bigrams(
    tokens: Vec<String>,
    measure: &str,
    min_freq: usize,
    top_n: usize,
) -> Vec<(String, String, usize, f64)> {
    let total = tokens.len();
    if total < 2 { return vec![]; }

    // підрахунок частот
    let unigram_freq = word_frequency(tokens.clone());
    let bigrams      = extract_bigrams(&tokens);

    let mut bigram_freq: HashMap<(String, String), usize> = HashMap::new();
    for (w1, w2) in bigrams {
        *bigram_freq.entry((w1, w2)).or_insert(0) += 1;
    }

    // обчислення оцінок
    let mut results: Vec<(String, String, usize, f64)> = bigram_freq.iter()
        .filter(|(_, &count)| count >= min_freq)
        .map(|((w1, w2), &count)| {
            let w1_c = *unigram_freq.get(w1).unwrap_or(&0);
            let w2_c = *unigram_freq.get(w2).unwrap_or(&0);
            let score = match measure {
                "pmi"            => pmi_score(w1, w2, count, w1_c, w2_c, total),
                "chi_square"     => chi_square_score(w1, w2, count, w1_c, w2_c, total),
                "log_likelihood" => log_likelihood_score(w1, w2, count, w1_c, w2_c, total),
                "t_score"        => t_score_score(w1, w2, count, w1_c, w2_c, total),
                _                => pmi_score(w1, w2, count, w1_c, w2_c, total),
            };
            (w1.clone(), w2.clone(), count, (score * 10000.0).round() / 10000.0)
        })
        .filter(|(_, _, _, score)| score.is_finite())
        .collect();

    results.sort_by(|a, b| b.3.partial_cmp(&a.3).unwrap_or(std::cmp::Ordering::Equal));
    results.truncate(top_n);
    results
}

// ─────────────────────────────────────────────
// BENCHMARK — порівняння з Python
// ─────────────────────────────────────────────

/// Повний пайплайн аналізу — для бенчмарку
#[pyfunction]
fn full_pipeline(
    py: Python,
    text: &str,
    measure: &str,
    min_freq: usize,
    top_n: usize,
) -> HashMap<String, PyObject> {
    let tokens = tokenize(text);
    let stats  = vocabulary_stats(tokens.clone());
    let zipf   = zipf_fit(tokens.clone());
    let colls  = score_bigrams(tokens.clone(), measure, min_freq, top_n);
    let top_w  = top_n_words(tokens, top_n);

    let mut result: HashMap<String, PyObject> = HashMap::new();
    result.insert("vocab_stats".to_string(),  stats.into_py(py));
    result.insert("zipf".to_string(),         zipf.into_py(py));
    result.insert("collocations".to_string(), colls.into_py(py));
    result.insert("top_words".to_string(),    top_w.into_py(py));
    result
}

// ─────────────────────────────────────────────
// PYTHON MODULE REGISTRATION
// ─────────────────────────────────────────────

#[pymodule]
#[pyo3(name = "rust_module")]
fn rust_module(_py: Python, m: &PyModule) -> PyResult<()> {
    // preprocessing
    m.add_function(wrap_pyfunction!(tokenize, m)?)?;
    m.add_function(wrap_pyfunction!(detect_language_own, m)?)?;
    m.add_function(wrap_pyfunction!(detect_language_lib, m)?)?;

    // frequency
    m.add_function(wrap_pyfunction!(word_frequency, m)?)?;
    m.add_function(wrap_pyfunction!(top_n_words, m)?)?;
    m.add_function(wrap_pyfunction!(vocabulary_stats, m)?)?;
    m.add_function(wrap_pyfunction!(zipf_fit, m)?)?;

    // collocations
    m.add_function(wrap_pyfunction!(pmi_score, m)?)?;
    m.add_function(wrap_pyfunction!(chi_square_score, m)?)?;
    m.add_function(wrap_pyfunction!(log_likelihood_score, m)?)?;
    m.add_function(wrap_pyfunction!(t_score_score, m)?)?;
    m.add_function(wrap_pyfunction!(score_bigrams, m)?)?;

    // pipeline
    m.add_function(wrap_pyfunction!(full_pipeline, m)?)?;

    Ok(())
}
