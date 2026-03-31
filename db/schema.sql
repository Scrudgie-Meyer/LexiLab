-- lexilab database schema

-- ─────────────────────────────────────────────
-- USERS (anonymous sessions or registered)
-- ─────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS users (
    id         SERIAL PRIMARY KEY,
    session_id VARCHAR(64) UNIQUE NOT NULL,   -- anonymous session token
    created_at TIMESTAMP DEFAULT NOW()
);

-- ─────────────────────────────────────────────
-- DATASETS
-- ─────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS datasets (
    id           SERIAL PRIMARY KEY,
    user_id      INTEGER REFERENCES users(id) ON DELETE SET NULL,
    name         VARCHAR(255) NOT NULL,
    lang         VARCHAR(10),                 -- 'ua', 'en', 'mixed'
    raw_text     TEXT NOT NULL,
    token_count  INTEGER,
    unique_count INTEGER,
    is_public    BOOLEAN DEFAULT TRUE,
    is_research  BOOLEAN DEFAULT FALSE,       -- research dataset (pre-loaded)
    created_at   TIMESTAMP DEFAULT NOW()
);

-- migration: add is_research if upgrading existing DB
ALTER TABLE datasets ADD COLUMN IF NOT EXISTS is_research BOOLEAN DEFAULT FALSE;

-- ─────────────────────────────────────────────
-- ANALYSES  (one per dataset)
-- ─────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS analyses (
    id             SERIAL PRIMARY KEY,
    dataset_id     INTEGER REFERENCES datasets(id) ON DELETE CASCADE,
    ttr            FLOAT,
    yules_k        FLOAT,
    hapax_count    INTEGER,
    zipf_constant  FLOAT,
    zipf_corr      FLOAT,
    fits_zipf      BOOLEAN,
    top_words      JSONB,   -- [{"word": "...", "count": N}, ...]
    freq_bands     JSONB,
    created_at     TIMESTAMP DEFAULT NOW()
);

-- ─────────────────────────────────────────────
-- COLLOCATIONS  (per dataset × measure)
-- ─────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS collocations (
    id         SERIAL PRIMARY KEY,
    dataset_id INTEGER REFERENCES datasets(id) ON DELETE CASCADE,
    measure    VARCHAR(20) NOT NULL,  -- pmi | npmi | t_score | chi_square | log_likelihood
    w1         VARCHAR(100) NOT NULL,
    w2         VARCHAR(100) NOT NULL,
    freq       INTEGER,
    score      FLOAT,
    rank       INTEGER,
    created_at TIMESTAMP DEFAULT NOW()
);

-- ─────────────────────────────────────────────
-- BENCHMARKS  (own vs libraries)
-- ─────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS benchmarks (
    id         SERIAL PRIMARY KEY,
    dataset_id INTEGER REFERENCES datasets(id) ON DELETE CASCADE,
    method     VARCHAR(50) NOT NULL,   -- lexilab_pmi | nltk_collocations | ...
    time_ms    FLOAT,
    memory_kb  FLOAT,
    available  BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT NOW()
);

-- ─────────────────────────────────────────────
-- INDEXES
-- ─────────────────────────────────────────────
CREATE INDEX IF NOT EXISTS idx_datasets_user     ON datasets(user_id);
CREATE INDEX IF NOT EXISTS idx_datasets_lang     ON datasets(lang);
CREATE INDEX IF NOT EXISTS idx_analyses_dataset  ON analyses(dataset_id);
CREATE INDEX IF NOT EXISTS idx_colls_dataset     ON collocations(dataset_id);
CREATE INDEX IF NOT EXISTS idx_colls_measure     ON collocations(measure);
CREATE INDEX IF NOT EXISTS idx_bench_dataset     ON benchmarks(dataset_id);