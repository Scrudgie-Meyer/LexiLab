/**
 * lexilab — frontend app.js
 * All UI logic, API communication, chart rendering.
 */

// On Railway the frontend is served by the same app — use relative URLs.
// For local dev override via: window.LEXILAB_API = 'http://localhost:8000'
const API = window.LEXILAB_API || '';

// ── session id (anonymous user) ──────────────────
const SESSION_ID = (() => {
  let id = localStorage.getItem('lexilab_session');
  if (!id) {
    id = crypto.randomUUID ? crypto.randomUUID()
       : Math.random().toString(36).slice(2) + Date.now().toString(36);
    localStorage.setItem('lexilab_session', id);
  }
  return id;
})();

// ── state ────────────────────────────────────────
let state = {
  lastResult:     null,
  activeMeasure:  'pmi',
  freqChart:      null,
  zipfChart:      null,
  bandsChart:     null,
  benchChart:     null,
  scatterChart:   null,
};

// ── sample texts ─────────────────────────────────
const SAMPLES = {
  ua: {
    name: 'UA NLP Text',
    text: `Статистичний аналіз текстів є важливим інструментом сучасної лінгвістики та комп'ютерної обробки природної мови. Дослідники використовують різноманітні методи для виявлення закономірностей у великих текстових корпусах. Методи машинного навчання дозволяють автоматично виявляти статистичні залежності між словами та реченнями. Частотний аналіз слів показує розподіл лексичних одиниць у тексті. Колокації є стійкими словосполученнями, які зустрічаються частіше ніж очікується при незалежному розподілі слів. Метод PMI дозволяє виявляти такі стійкі словосполучення на основі статистичної взаємної інформації між словами тексту. Тематичне моделювання дозволяє виявляти приховані тематичні структури у великих колекціях документів та текстових масивах даних. Лінгвістичний аналіз тексту включає морфологічний та синтаксичний аналіз речень. Статистичні методи обробки тексту знаходять широке застосування в інформаційному пошуку, машинному перекладі та автоматичному реферуванні текстових документів. Природна мова є складним об'єктом дослідження через велику кількість виключень та нерегулярностей.`
  },
  en: {
    name: 'EN Linguistics Text',
    text: `Statistical text analysis is an important tool in modern linguistics and natural language processing. Researchers use various methods to discover patterns in large text corpora. Machine learning methods allow automatic detection of statistical dependencies between words and sentences. Frequency analysis of words shows the distribution of lexical units in text. Collocations are fixed word combinations that occur more frequently than expected under independent word distribution. The PMI method allows detecting such stable word combinations based on statistical mutual information. Topic modeling allows discovering hidden thematic structures in large document collections. Linguistic text analysis includes morphological and syntactic sentence analysis. Statistical text processing methods find wide application in information retrieval, machine translation, and automatic text summarization. Natural language is a complex research object due to the large number of exceptions and irregularities in its structure.`
  },
  mixed: {
    name: 'Mixed UA/EN Text',
    text: `Natural language processing (NLP) та обробка природної мови є активними галузями досліджень. Методи machine learning дозволяють автоматично аналізувати тексти. Statistical analysis та статистичний аналіз використовуються для виявлення patterns у текстових корпусах. Word embeddings та векторні представлення слів знаходять широке застосування в сучасних NLP системах. Deep learning моделі, зокрема transformer architecture, революціонізували обробку природної мови. Алгоритми text classification та класифікації текстів застосовуються у sentiment analysis та тематичному моделюванні.`
  }
};

// ══════════════════════════════════════════════════
// NAVIGATION
// ══════════════════════════════════════════════════

function switchView(viewId) {
  document.querySelectorAll('.view').forEach(v => v.classList.remove('active'));
  document.querySelectorAll('.nav-item').forEach(n => n.classList.remove('active'));

  const view = document.getElementById(`view-${viewId}`);
  if (view) { view.classList.add('active'); view.classList.add('fade-in'); }

  document.querySelectorAll('.nav-item').forEach(n => {
    if (n.dataset.view === viewId) n.classList.add('active');
  });

  if (viewId === 'datasets') loadDatasets();
  if (viewId === 'global')   loadGlobal();
}

document.querySelectorAll('.nav-item').forEach(item => {
  item.addEventListener('click', () => switchView(item.dataset.view));
});

// ══════════════════════════════════════════════════
// TABS
// ══════════════════════════════════════════════════

document.querySelectorAll('.tab').forEach(tab => {
  tab.addEventListener('click', () => {
    const panel = tab.closest('.panel');
    panel.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
    panel.querySelectorAll('.tab-panel').forEach(p => p.classList.remove('active'));
    tab.classList.add('active');
    const target = panel.querySelector(`#tab-${tab.dataset.tab}`);
    if (target) target.classList.add('active');
  });
});

// ══════════════════════════════════════════════════
// SAMPLE TEXTS
// ══════════════════════════════════════════════════

function loadSample(lang) {
  const s = SAMPLES[lang];
  document.getElementById('ds-name').value = s.name;
  document.getElementById('ds-text').value = s.text;
}

// ══════════════════════════════════════════════════
// ANALYZE
// ══════════════════════════════════════════════════

document.getElementById('btn-analyze').addEventListener('click', runAnalysis);
document.getElementById('btn-clear').addEventListener('click', () => {
  document.getElementById('ds-name').value = '';
  document.getElementById('ds-text').value = '';
  document.getElementById('analyze-status').textContent = '';
});

async function runAnalysis() {
  const name = document.getElementById('ds-name').value.trim();
  const text = document.getElementById('ds-text').value.trim();

  if (!name) { setStatus('⚠ Enter a dataset name', 'var(--accent3)'); return; }
  if (text.length < 50) { setStatus('⚠ Text is too short (min 50 chars)', 'var(--accent3)'); return; }

  const selectEl = document.getElementById('ds-measures');
  const measures = Array.from(selectEl.selectedOptions).map(o => o.value);

  const payload = {
    name,
    text,
    is_public: true,
    measures,
    min_collocation_freq: parseInt(document.getElementById('ds-minfreq').value) || 2,
    top_n: parseInt(document.getElementById('ds-topn').value) || 20,
    run_benchmark: true,
  };

  const btn = document.getElementById('btn-analyze');
  const overlay = document.getElementById('analyze-loading');
  const stepEl = document.getElementById('loading-step');

  btn.disabled = true;
  overlay.classList.add('show');

  const steps = ['preprocessing...', 'frequency analysis...', 'collocations...', 'benchmark...', 'saving...'];
  let stepIdx = 0;
  const stepInterval = setInterval(() => {
    stepEl.textContent = steps[stepIdx % steps.length];
    stepIdx++;
  }, 600);

  try {
    // Try real API first, fall back to mock
    let result;
    try {
      const resp = await fetch(`${API}/analyze/`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-Session-Id': SESSION_ID,
        },
        body: JSON.stringify(payload),
      });
      if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
      result = await resp.json();
    } catch (e) {
      console.warn('API not available, using mock data:', e.message);
      result = mockAnalysis(payload);
    }

    state.lastResult = result;
    renderResults(result);
    setStatus(`✓ Analyzed: dataset #${result.dataset?.id || 'local'}`, 'var(--accent)');
    switchView('results');

  } catch (err) {
    setStatus(`✗ Error: ${err.message}`, 'var(--accent3)');
  } finally {
    clearInterval(stepInterval);
    overlay.classList.remove('show');
    btn.disabled = false;
  }
}

function setStatus(msg, color) {
  const el = document.getElementById('analyze-status');
  el.textContent = msg;
  el.style.color = color;
}

// ══════════════════════════════════════════════════
// RENDER RESULTS
// ══════════════════════════════════════════════════

function renderResults(data) {
  const vs = data.vocab_stats || {};
  const zf = data.zipf || {};

  // stat cards
  animateValue('s-tokens', vs.total_tokens || data.dataset?.token_count || 0);
  animateValue('s-vocab',  vs.vocabulary_size || data.dataset?.unique_count || 0);
  document.getElementById('s-ttr').textContent   = (vs.ttr   || 0).toFixed(3);
  document.getElementById('s-yule').textContent  = (vs.yules_k || 0).toFixed(1);
  document.getElementById('s-hapax').textContent = vs.hapax_legomena || 0;
  document.getElementById('s-zipf').textContent  = zf.fits_zipf ? '✓ yes' : '✗ no';
  document.getElementById('s-zipf').style.color  = zf.fits_zipf ? 'var(--accent)' : 'var(--text2)';
  document.getElementById('s-zipf-corr').textContent = `r = ${(zf.log_log_correlation || 0).toFixed(3)}`;

  document.querySelectorAll('.stat-card').forEach((c,i) => {
    setTimeout(() => c.classList.add('loaded'), i * 80);
  });

  // frequency table
  renderFreqTable(data.top_words || vs.top_10 || []);

  // frequency chart
  renderFreqChart(data.top_words || vs.top_10 || []);

  // collocations
  const colls = data.collocations || {};
  renderMeasurePills(Object.keys(colls));
  renderCollTable(colls, state.activeMeasure);

  // zipf chart
  renderZipfChart(data);

  // bands chart
  renderBandsChart(data.freq_bands || {});

  // benchmark
  if (data.benchmarks) {
    renderBenchTable(data.benchmarks);
    renderBenchChart(data.benchmarks);
  }
}

// ── frequency table ──────────────────────────────
function renderFreqTable(topWords) {
  const tbody = document.getElementById('freq-tbody');
  const total = topWords.reduce((s, [,c]) => s + c, 0) || 1;

  tbody.innerHTML = topWords.slice(0, 15).map(([word, count], i) => `
    <tr>
      <td class="rank">${i + 1}</td>
      <td class="word">${word}</td>
      <td>${count}</td>
      <td style="color:var(--text3)">${((count / total) * 100).toFixed(1)}%</td>
    </tr>
  `).join('');
}

// ── frequency bar chart ──────────────────────────
function renderFreqChart(topWords) {
  const ctx = document.getElementById('freq-chart').getContext('2d');
  if (state.freqChart) state.freqChart.destroy();

  const top15 = topWords.slice(0, 15);
  state.freqChart = new Chart(ctx, {
    type: 'bar',
    data: {
      labels: top15.map(([w]) => w),
      datasets: [{
        data: top15.map(([,c]) => c),
        backgroundColor: top15.map((_, i) =>
          i === 0 ? 'rgba(0,229,180,0.8)' :
          i < 3   ? 'rgba(0,229,180,0.5)' :
                    'rgba(124,111,255,0.35)'
        ),
        borderColor: 'transparent',
        borderRadius: 3,
      }]
    },
    options: {
      responsive: true, maintainAspectRatio: false,
      plugins: { legend: { display: false } },
      scales: {
        x: { ticks: { color: '#8888aa', font: { family: 'JetBrains Mono', size: 10 } }, grid: { display: false } },
        y: { ticks: { color: '#8888aa', font: { family: 'JetBrains Mono', size: 10 } }, grid: { color: '#2a2a3a' } },
      }
    }
  });
}

// ── collocation pills ────────────────────────────
function renderMeasurePills(measures) {
  const pills = document.getElementById('measure-pills');
  pills.innerHTML = measures.map(m => `
    <div class="pill ${m === state.activeMeasure ? 'active' : ''}"
         onclick="selectMeasure('${m}')">${m}</div>
  `).join('');
}

function selectMeasure(m) {
  state.activeMeasure = m;
  document.querySelectorAll('#measure-pills .pill').forEach(p => {
    p.classList.toggle('active', p.textContent === m);
  });
  if (state.lastResult) renderCollTable(state.lastResult.collocations || {}, m);
}

// ── collocation table ────────────────────────────
function renderCollTable(colls, measure) {
  const tbody = document.getElementById('coll-tbody');
  const items = colls[measure] || [];

  if (!items.length) {
    tbody.innerHTML = `<tr><td colspan="5" style="color:var(--text3);text-align:center;padding:24px">
      No collocations found. Try lower min-frequency or longer text.
    </td></tr>`;
    return;
  }

  const maxScore = Math.max(...items.map(r => Math.abs(r.score)));

  tbody.innerHTML = items.map((r, i) => {
    const pct = maxScore > 0 ? (Math.abs(r.score) / maxScore * 100).toFixed(1) : 0;
    return `
    <tr>
      <td class="rank">${r.rank || i + 1}</td>
      <td class="bigram">${r.bigram[0]} <span style="color:var(--text3)">+</span> ${r.bigram[1]}</td>
      <td style="color:var(--text3)">${r.freq}</td>
      <td class="score">${r.score.toFixed(4)}</td>
      <td>
        <div class="score-bar-wrap">
          <div class="score-bar">
            <div class="score-bar-fill" style="width:${pct}%"></div>
          </div>
        </div>
      </td>
    </tr>`;
  }).join('');
}

// ── zipf chart ───────────────────────────────────
function renderZipfChart(data) {
  const ctx = document.getElementById('zipf-chart').getContext('2d');
  if (state.zipfChart) state.zipfChart.destroy();

  const vs = data.vocab_stats || {};
  const total = vs.total_tokens || 1;

  // build rank-freq from top_words (approximate)
  const topWords = data.top_words || vs.top_10 || [];
  const points = topWords.slice(0, 30).map(([,count], i) => ({
    x: Math.log10(i + 1),
    y: Math.log10(count / total),
  }));

  // ideal Zipf line
  const C = topWords[0] ? topWords[0][1] / total : 0.1;
  const zipfLine = points.map(p => ({
    x: p.x,
    y: Math.log10(C) - p.x,
  }));

  state.zipfChart = new Chart(ctx, {
    type: 'scatter',
    data: {
      datasets: [
        {
          label: 'Actual',
          data: points,
          backgroundColor: 'rgba(0,229,180,0.7)',
          pointRadius: 4,
          pointHoverRadius: 6,
        },
        {
          label: 'Ideal Zipf',
          data: zipfLine,
          type: 'line',
          borderColor: 'rgba(124,111,255,0.6)',
          borderWidth: 1.5,
          borderDash: [4, 4],
          pointRadius: 0,
          fill: false,
        }
      ]
    },
    options: {
      responsive: true, maintainAspectRatio: false,
      plugins: {
        legend: { labels: { color: '#8888aa', font: { family: 'JetBrains Mono', size: 10 } } }
      },
      scales: {
        x: { title: { display: true, text: 'log(rank)', color: '#55556a', font: { family: 'JetBrains Mono', size: 10 } },
             ticks: { color: '#8888aa', font: { family: 'JetBrains Mono', size: 10 } }, grid: { color: '#2a2a3a' } },
        y: { title: { display: true, text: 'log(freq)', color: '#55556a', font: { family: 'JetBrains Mono', size: 10 } },
             ticks: { color: '#8888aa', font: { family: 'JetBrains Mono', size: 10 } }, grid: { color: '#2a2a3a' } },
      }
    }
  });
}

// ── bands chart ───────────────────────────────────
function renderBandsChart(bands) {
  const content = document.getElementById('bands-content');
  content.innerHTML = `
    <div style="display:grid;grid-template-columns:1fr 1fr 1fr;gap:12px;margin-bottom:16px;">
      ${[
        ['HIGH FREQ', bands.high_frequency || 0, bands.high_words || 0, 'var(--accent)'],
        ['MID FREQ',  bands.mid_frequency  || 0, bands.mid_words  || 0, 'var(--accent2)'],
        ['LOW FREQ',  bands.low_frequency  || 0, bands.low_words  || 0, 'var(--text3)'],
      ].map(([label, tokens, words, color]) => `
        <div style="padding:10px;background:var(--bg3);border-radius:4px;border:1px solid var(--border)">
          <div style="font-size:10px;color:var(--text3);letter-spacing:1px">${label}</div>
          <div style="font-size:18px;font-family:var(--sans);font-weight:700;color:${color};margin:4px 0">${tokens}</div>
          <div style="font-size:10px;color:var(--text3)">${words} word types</div>
        </div>
      `).join('')}
    </div>
  `;

  const ctx = document.getElementById('bands-chart').getContext('2d');
  if (state.bandsChart) state.bandsChart.destroy();

  state.bandsChart = new Chart(ctx, {
    type: 'doughnut',
    data: {
      labels: ['High Freq', 'Mid Freq', 'Low Freq'],
      datasets: [{
        data: [bands.high_frequency||0, bands.mid_frequency||0, bands.low_frequency||0],
        backgroundColor: ['rgba(0,229,180,0.7)', 'rgba(124,111,255,0.7)', 'rgba(85,85,106,0.5)'],
        borderColor: 'var(--bg2)',
        borderWidth: 2,
      }]
    },
    options: {
      responsive: true, maintainAspectRatio: false,
      plugins: {
        legend: { labels: { color: '#8888aa', font: { family: 'JetBrains Mono', size: 10 }, boxWidth: 10 } }
      }
    }
  });
}

// ── benchmark table ───────────────────────────────
function renderBenchTable(benchmarks) {
  const tbody = document.getElementById('bench-tbody');
  if (!benchmarks || !Object.keys(benchmarks).length) return;

  const rows = typeof benchmarks === 'object' && !Array.isArray(benchmarks)
    ? Object.entries(benchmarks).map(([method, stats]) => ({
        method, ...stats, available: stats.has_result
      }))
    : benchmarks;

  const maxTime = Math.max(...rows.map(r => r.time_ms || 0)) || 1;

  // визначаємо тип методу
  function getType(method) {
    if (method.startsWith('rust_own')) return 'rust_own';
    if (method.startsWith('lexilab')) return 'python_own';
    return 'python_lib';
  }

  function getBadge(r) {
    if (!r.available) return ['na', 'N/A'];
    const t = getType(r.method);
    if (t === 'rust_own')    return ['rust', '🦀 Rust'];
    if (t === 'python_own')  return ['own',  '🐍 Python'];
    return ['lib', 'library'];
  }

  // додаємо CSS для rust badge якщо ще немає
  if (!document.getElementById('rust-badge-style')) {
    const s = document.createElement('style');
    s.id = 'rust-badge-style';
    s.textContent = `.bench-badge.rust { background: rgba(255,150,50,0.15); color: #ff9632; }
    .time-bar-fill.rust { background: #ff9632; }`;
    document.head.appendChild(s);
  }

  // групуємо: спочатку Python власний, потім Rust власний, потім бібліотеки
  const order = { python_own: 0, rust_own: 1, python_lib: 2 };
  rows.sort((a, b) => order[getType(a.method)] - order[getType(b.method)]);

  // вставляємо роздільники груп
  let lastGroup = null;
  const html = rows.map(r => {
    const group = getType(r.method);
    const pct = ((r.time_ms || 0) / maxTime * 100).toFixed(1);
    const [badgeClass, badgeText] = getBadge(r);
    const barClass = group === 'rust_own' ? 'rust' : group === 'python_own' ? 'own' : 'lib';

    let separator = '';
    if (group !== lastGroup) {
      lastGroup = group;
      const labels = { python_own: '— Python власний —', rust_own: '— Rust власний —', python_lib: '— Python бібліотеки —' };
      separator = `<tr><td colspan="5" style="padding:10px 12px 4px;font-size:10px;color:var(--text3);letter-spacing:1px;text-transform:uppercase">${labels[group]}</td></tr>`;
    }

    return separator + `
    <tr>
      <td class="bench-method">${r.method.replace('rust_own_','').replace('lexilab_','').replace('nltk_','nltk: ').replace('spacy_','spacy: ').replace('gensim_','gensim: ')}</td>
      <td><span class="bench-badge ${badgeClass}">${badgeText}</span></td>
      <td>
        <div class="time-bar-wrap">
          <span style="min-width:52px;color:var(--text2)">${(r.time_ms||0).toFixed(3)}</span>
          <div class="time-bar">
            <div class="time-bar-fill ${barClass}" style="width:${pct}%"></div>
          </div>
        </div>
      </td>
      <td style="color:var(--text3)">${(r.memory_kb||0).toFixed(1)}</td>
      <td style="color:${r.available ? 'var(--accent)' : 'var(--accent3)'}">
        ${r.available ? '✓' : '✗ not installed'}
      </td>
    </tr>`;
  }).join('');
}

// ── benchmark chart ───────────────────────────────
function renderBenchChart(benchmarks) {
  const ctx = document.getElementById('bench-chart').getContext('2d');
  if (state.benchChart) state.benchChart.destroy();

  const rows = typeof benchmarks === 'object' && !Array.isArray(benchmarks)
    ? Object.entries(benchmarks)
        .filter(([, s]) => s.has_result)
        .map(([m, s]) => ({ method: m, time_ms: s.time_ms, memory_kb: s.memory_kb }))
    : benchmarks.filter(r => r.available);

  if (!rows.length) return;

  state.benchChart = new Chart(ctx, {
    type: 'bar',
    data: {
      labels: rows.map(r => r.method.replace('rust_own_','rs:').replace('lexilab_','py:').replace('nltk_','nltk:').replace('spacy_','spacy:')),
      datasets: [
        {
          label: 'Time (ms)',
          data: rows.map(r => r.time_ms || 0),
          backgroundColor: rows.map(r =>
            r.method.startsWith('rust_own')  ? 'rgba(255,150,50,0.8)' :
            r.method.startsWith('lexilab')   ? 'rgba(0,229,180,0.7)'  :
                                               'rgba(124,111,255,0.5)'
          ),
          borderColor: 'transparent',
          borderRadius: 3,
          yAxisID: 'y',
        },
        {
          label: 'Memory (KB)',
          data: rows.map(r => r.memory_kb || 0),
          backgroundColor: rows.map(r =>
            r.method.startsWith('lexilab') ? 'rgba(0,229,180,0.2)' : 'rgba(124,111,255,0.2)'
          ),
          borderColor: rows.map(r =>
            r.method.startsWith('lexilab') ? 'rgba(0,229,180,0.5)' : 'rgba(124,111,255,0.4)'
          ),
          borderWidth: 1,
          borderRadius: 3,
          yAxisID: 'y1',
        }
      ]
    },
    options: {
      responsive: true, maintainAspectRatio: false,
      plugins: {
        legend: { labels: { color: '#8888aa', font: { family: 'JetBrains Mono', size: 10 }, boxWidth: 10 } }
      },
      scales: {
        x: { ticks: { color: '#8888aa', font: { family: 'JetBrains Mono', size: 10 }, maxRotation: 35 }, grid: { display: false } },
        y:  { ticks: { color: '#8888aa', font: { family: 'JetBrains Mono', size: 10 } }, grid: { color: '#2a2a3a' }, title: { display: true, text: 'ms', color: '#55556a' } },
        y1: { position: 'right', ticks: { color: '#8888aa', font: { family: 'JetBrains Mono', size: 10 } }, grid: { display: false }, title: { display: true, text: 'KB', color: '#55556a' } },
      }
    }
  });
}

// ══════════════════════════════════════════════════
// DATASETS LIST
// ══════════════════════════════════════════════════

let dsState = { page: 0, sort: 'newest', lang: '', total: 0, limit: 20 };

async function loadDatasets(reset = true) {
  if (reset) { dsState.page = 0; }

  const el = document.getElementById('datasets-list');
  el.innerHTML = `<div style="display:flex;justify-content:center;padding:32px"><div class="spinner"></div></div>`;

  const skip = dsState.page * dsState.limit;
  const params = new URLSearchParams({
    skip, limit: dsState.limit, sort: dsState.sort,
  });
  if (dsState.lang) params.set('lang', dsState.lang);

  try {
    const resp = await fetch(`${API}/datasets/?${params}`);
    if (!resp.ok) throw new Error('API unavailable');
    const data = await resp.json();
    dsState.total = data.total;

    const controls = `
      <div style="display:flex;gap:8px;align-items:center;margin-bottom:12px;flex-wrap:wrap;">
        <select class="form-select" style="width:auto;padding:5px 8px;font-size:11px" onchange="dsState.sort=this.value;loadDatasets()">
          <option value="newest" ${dsState.sort==='newest'?'selected':''}>↓ Newest</option>
          <option value="oldest" ${dsState.sort==='oldest'?'selected':''}>↑ Oldest</option>
          <option value="lang"   ${dsState.sort==='lang'  ?'selected':''}>A-Z Lang</option>
        </select>
        <select class="form-select" style="width:auto;padding:5px 8px;font-size:11px" onchange="dsState.lang=this.value;loadDatasets()">
          <option value=""      ${dsState.lang===''     ?'selected':''}>All langs</option>
          <option value="ua"    ${dsState.lang==='ua'   ?'selected':''}>🇺🇦 UA</option>
          <option value="en"    ${dsState.lang==='en'   ?'selected':''}>🇬🇧 EN</option>
          <option value="mixed" ${dsState.lang==='mixed'?'selected':''}>⚡ Mixed</option>
        </select>
        <span style="color:var(--text3);font-size:11px;margin-left:auto">${data.total} datasets</span>
      </div>`;

    if (!data.items.length) {
      el.innerHTML = controls + `<div class="empty-state"><div class="glyph">⊞</div><p>No datasets found.</p></div>`;
      return;
    }

    const rows = data.items.map(ds => `
      <div class="dataset-row" onclick="viewDataset(${ds.id})">
        <div>
          <div class="dataset-name">${ds.name}</div>
          <div class="dataset-meta">${ds.token_count || 0} tokens · ${ds.unique_count || 0} unique · ${formatDate(ds.created_at)}</div>
        </div>
        <span class="dataset-lang">${ds.lang || '?'}</span>
      </div>
    `).join('');

    // pagination
    const totalPages = Math.ceil(dsState.total / dsState.limit);
    const pagination = totalPages > 1 ? `
      <div style="display:flex;align-items:center;justify-content:center;gap:8px;margin-top:12px">
        <button class="btn btn-ghost" style="padding:5px 12px;font-size:11px"
          ${dsState.page === 0 ? 'disabled' : ''}
          onclick="dsState.page--;loadDatasets(false)">← Prev</button>
        <span style="color:var(--text3);font-size:11px">${dsState.page+1} / ${totalPages}</span>
        <button class="btn btn-ghost" style="padding:5px 12px;font-size:11px"
          ${dsState.page >= totalPages-1 ? 'disabled' : ''}
          onclick="dsState.page++;loadDatasets(false)">Next →</button>
      </div>` : '';

    el.innerHTML = controls + rows + pagination;

  } catch {
    el.innerHTML = `<div class="empty-state"><div class="glyph">⚠</div><p>Could not load datasets. Make sure the API is running.</p></div>`;
  }
}

async function viewDataset(id) {
  try {
    const resp = await fetch(`${API}/analyze/${id}`);
    if (!resp.ok) throw new Error();
    const data = await resp.json();

    // rebuild result shape for renderResults
    const result = {
      dataset: { id, token_count: 0 },
      vocab_stats: {
        total_tokens: 0,
        vocabulary_size: 0,
        ttr: data.ttr,
        yules_k: data.yules_k,
        hapax_legomena: data.hapax_count,
        top_10: (data.top_words || []).map(w => [w.word, w.count]),
      },
      zipf: { fits_zipf: data.fits_zipf, log_log_correlation: data.zipf_corr },
      top_words: (data.top_words || []).map(w => [w.word, w.count]),
      collocations: data.collocations,
      freq_bands: data.freq_bands,
      benchmarks: data.benchmarks,
    };

    state.lastResult = result;
    renderResults(result);
    switchView('results');
  } catch {
    alert('Could not load dataset analysis.');
  }
}

// ══════════════════════════════════════════════════
// GLOBAL STATS
// ══════════════════════════════════════════════════

async function loadGlobal() {
  try {
    const [globalResp, perResp] = await Promise.all([
      fetch(`${API}/stats/global`),
      fetch(`${API}/stats/per-dataset`),
    ]);

    if (!globalResp.ok) throw new Error();
    const g = await globalResp.json();

    document.getElementById('g-datasets').textContent = g.total_datasets;
    document.getElementById('g-tokens').textContent   = fmtNum(g.total_tokens);
    document.getElementById('g-ttr').textContent      = (g.avg_ttr || 0).toFixed(3);
    document.getElementById('g-yule').textContent     = (g.avg_yules_k || 0).toFixed(1);

    // language distribution
    const langEl = document.getElementById('lang-dist');
    const total  = Object.values(g.lang_distribution).reduce((a,b) => a+b, 0) || 1;
    langEl.innerHTML = Object.entries(g.lang_distribution).map(([lang, count]) => `
      <div class="lang-bar-row">
        <span class="lang-label">${lang}</span>
        <div class="lang-bar"><div class="lang-bar-fill ${lang}" style="width:${(count/total*100).toFixed(1)}%"></div></div>
        <span class="lang-count">${count}</span>
      </div>
    `).join('');

    // top global collocations
    const tbody = document.getElementById('global-colls');
    tbody.innerHTML = (g.top_collocations_pmi || []).map((c, i) => `
      <tr>
        <td class="rank">${i+1}</td>
        <td class="bigram">${c.bigram[0]} + ${c.bigram[1]}</td>
        <td class="score">${c.avg_score.toFixed(4)}</td>
      </tr>
    `).join('');

    // scatter chart
    if (perResp.ok) {
      const per = await perResp.json();
      renderScatterChart(per.datasets || []);
    }

  } catch {
    // silently fail — API not running
  }
}

function renderScatterChart(datasets) {
  const ctx = document.getElementById('scatter-chart').getContext('2d');
  if (state.scatterChart) state.scatterChart.destroy();

  const byLang = { ua: [], en: [], mixed: [] };
  datasets.forEach(d => {
    const lang = d.lang || 'mixed';
    if (byLang[lang]) byLang[lang].push({ x: d.token_count, y: d.ttr, label: d.name });
  });

  const colors = { ua: 'rgba(0,229,180,0.7)', en: 'rgba(124,111,255,0.7)', mixed: 'rgba(255,107,107,0.7)' };

  state.scatterChart = new Chart(ctx, {
    type: 'scatter',
    data: {
      datasets: Object.entries(byLang).filter(([,pts]) => pts.length).map(([lang, pts]) => ({
        label: lang.toUpperCase(),
        data: pts,
        backgroundColor: colors[lang],
        pointRadius: 6,
        pointHoverRadius: 8,
      }))
    },
    options: {
      responsive: true, maintainAspectRatio: false,
      plugins: {
        legend: { labels: { color: '#8888aa', font: { family: 'JetBrains Mono', size: 10 }, boxWidth: 10 } },
        tooltip: { callbacks: { label: ctx => `${ctx.raw.label}: tokens=${ctx.raw.x}, TTR=${ctx.raw.y}` } }
      },
      scales: {
        x: { title: { display: true, text: 'Token Count', color: '#55556a', font: { family: 'JetBrains Mono', size: 10 } },
             ticks: { color: '#8888aa', font: { family: 'JetBrains Mono', size: 10 } }, grid: { color: '#2a2a3a' } },
        y: { title: { display: true, text: 'TTR', color: '#55556a', font: { family: 'JetBrains Mono', size: 10 } },
             ticks: { color: '#8888aa', font: { family: 'JetBrains Mono', size: 10 } }, grid: { color: '#2a2a3a' } },
      }
    }
  });
}

// ══════════════════════════════════════════════════
// MOCK DATA (when API is not running)
// ══════════════════════════════════════════════════

function mockAnalysis(payload) {
  const words = payload.text.toLowerCase().replace(/[^\w\s]/g,'').split(/\s+/).filter(w => w.length > 2);
  const freq = {};
  words.forEach(w => { freq[w] = (freq[w]||0) + 1; });
  const sorted = Object.entries(freq).sort((a,b) => b[1]-a[1]);
  const top10  = sorted.slice(0, 10);
  const total  = words.length;
  const unique = Object.keys(freq).length;
  const hapax  = Object.values(freq).filter(c => c === 1).length;

  // generate mock collocations
  const mockColls = {};
  ['pmi','npmi','log_likelihood','chi_square','t_score'].forEach(m => {
    mockColls[m] = top10.slice(0,5).map((([w1],i) => ({
      bigram: [w1, top10[(i+1)%10][0]],
      freq: Math.max(2, top10[i][1] - 1),
      score: parseFloat((Math.random() * 5 + 1).toFixed(4)),
      rank: i + 1,
    })));
  });

  return {
    dataset: { id: 'local', name: payload.name, token_count: total, unique_count: unique },
    vocab_stats: {
      total_tokens: total,
      vocabulary_size: unique,
      hapax_legomena: hapax,
      ttr: parseFloat((unique / total).toFixed(4)),
      yules_k: parseFloat((10000 * unique / (total * total)).toFixed(2)),
      avg_frequency: parseFloat((total / unique).toFixed(2)),
      top_10: top10,
    },
    zipf: {
      zipf_constant: parseFloat((top10[0]?.[1]/total || 0.1).toFixed(6)),
      mae: 0.45,
      log_log_correlation: -0.91,
      fits_zipf: true,
    },
    top_words: top10,
    freq_bands: {
      high_frequency: Math.round(total * 0.4),
      mid_frequency:  Math.round(total * 0.35),
      low_frequency:  Math.round(total * 0.25),
      high_words: Math.round(unique * 0.1),
      mid_words:  Math.round(unique * 0.4),
      low_words:  Math.round(unique * 0.5),
    },
    collocations: mockColls,
    benchmarks: {
      lexilab_frequency:   { time_ms: 0.54, memory_kb: 10.1, has_result: true },
      lexilab_pmi:         { time_ms: 0.07, memory_kb:  9.4, has_result: true },
      lexilab_ll:          { time_ms: 0.06, memory_kb:  9.3, has_result: true },
      lexilab_chi2:        { time_ms: 0.06, memory_kb:  9.3, has_result: true },
      nltk_frequency:      { time_ms: 0,    memory_kb:  0,   has_result: false },
      nltk_collocations:   { time_ms: 0,    memory_kb:  0,   has_result: false },
    }
  };
}

// ══════════════════════════════════════════════════
// UTILS
// ══════════════════════════════════════════════════

function animateValue(id, target) {
  const el = document.getElementById(id);
  if (!el) return;
  const start = 0;
  const duration = 600;
  const t0 = performance.now();
  function step(now) {
    const p = Math.min((now - t0) / duration, 1);
    el.textContent = Math.round(start + (target - start) * easeOut(p));
    if (p < 1) requestAnimationFrame(step);
  }
  requestAnimationFrame(step);
}

function easeOut(t) { return 1 - Math.pow(1 - t, 3); }

function fmtNum(n) {
  if (n >= 1e6) return (n/1e6).toFixed(1) + 'M';
  if (n >= 1e3) return (n/1e3).toFixed(1) + 'K';
  return n;
}

function formatDate(iso) {
  if (!iso) return '';
  const d = new Date(iso);
  return d.toLocaleDateString('uk-UA', { day:'2-digit', month:'2-digit', year:'numeric' });
}

// ── init: auto-load sample ───────────────────────
loadSample('ua');

// ══════════════════════════════════════════════════
// INTERNATIONALIZATION (UA / EN)
// ══════════════════════════════════════════════════

let currentLang = 'ua';

const i18n = {
  ua: {
    // sidebar
    'nav.analysis':    'Аналіз',
    'nav.analyze':     'Аналізувати текст',
    'nav.results':     'Результати',
    'nav.data':        'Дані',
    'nav.datasets':    'Датасети',
    'nav.global':      'Глобальна статистика',
    'nav.compare':     'Порівняння',
    'nav.benchmark':   'Бенчмарк',
    'nav.research_section': 'Дослідження',
    'nav.research':    'Research датасети',
    // analyze form
    'form.name.label': 'НАЗВА ДАТАСЕТУ',
    'form.name.placeholder': 'напр. Новинна стаття, Наукова стаття...',
    'form.text.label': 'ТЕКСТ — вставте україномовний або англомовний текст',
    'form.text.placeholder': 'Вставте текст для аналізу...\n\nМінімум 50 слів для якісних результатів.',
    'form.measures.label': 'МІРИ КОЛОКАЦІЙ',
    'form.minfreq.label': 'МІН. ЧАСТОТА КОЛОКАЦІЙ',
    'form.topn.label': 'ТОП N РЕЗУЛЬТАТІВ',
    'btn.analyze': 'Запустити аналіз',
    'btn.clear': 'Очистити',
    'panel.submit': 'Надіслати текст для аналізу',
    'panel.samples': 'Зразки текстів',
    // results
    'stat.tokens': 'ТОКЕНИ',
    'stat.vocab': 'СЛОВНИК',
    'stat.ttr': 'КТТ',
    'stat.ttr.sub': 'коефіцієнт типів-токенів',
    'stat.yule': 'YULE\'S K',
    'stat.yule.sub': 'лексичне багатство',
    'stat.hapax': 'HAPAX',
    'stat.hapax.sub': 'одноразові слова',
    'stat.zipf': 'ZIPF',
    'tab.freq': 'Частоти',
    'tab.colls': 'Колокації',
    'tab.zipf': 'Grafік Zipf',
    'tab.bands': 'Частотні зони',
    'table.topwords': 'ТОП СЛОВА',
    'table.distribution': 'РОЗПОДІЛ',
    // datasets
    'panel.datasets': 'Всі датасети',
    'btn.refresh': '↺ Оновити',
    'empty.datasets': 'Поки немає датасетів. Проаналізуйте текст щоб створити перший.',
    // global
    'stat.total_datasets': 'ВСЬОГО ДАТАСЕТІВ',
    'stat.total_tokens': 'ВСЬОГО ТОКЕНІВ',
    'stat.avg_ttr': 'СЕРЕДНІЙ КТТ',
    'stat.avg_yule': 'СЕРЕДНІЙ YULE\'S K',
    'panel.lang_dist': 'Розподіл мов',
    'panel.top_colls': 'Топ глобальні колокації (PMI)',
    'panel.per_dataset': 'Порівняння датасетів',
    // benchmark
    'panel.bench': 'lexilab vs NLTK vs spaCy vs Gensim',
    'col.method': 'Метод',
    'col.type': 'Тип',
    'col.time': 'Час (мс)',
    'col.memory': "Пам'ять (КБ)",
    'col.status': 'Статус',
    'panel.bench_chart': 'Графік порівняння часу',
    // research
    'panel.research': 'Research датасети',
    'tab.all': 'Всі',
    'stat.research_corpus': 'дослідницький корпус',
    'research.click_hint': 'Натисніть на рядок датасету щоб побачити його колокації',
    'panel.ttr_chart': 'КТТ по датасетах',
    'panel.yule_chart': 'Yule\'s K по датасетах',
    'panel.colls_per': 'Топ колокації датасету',
    'col.word': 'Слово',
    'col.count': 'Кількість',
    'col.bigram': 'Біграм',
    'col.freq': 'Частота',
    'col.score': 'Оцінка',
    'col.avg_pmi': 'Сер. PMI',
    'zipf.description': 'Лог-лог графік рангу vs частоти. Закон Зіпфа передбачає пряму лінію з нахилом ≈ −1.',
    'bands.title': 'РОЗПОДІЛ ПО ЧАСТОТНИХ ЗОНАХ',
  },
  en: {
    'nav.analysis':    'Analysis',
    'nav.analyze':     'Analyze Text',
    'nav.results':     'Results',
    'nav.data':        'Data',
    'nav.datasets':    'Datasets',
    'nav.global':      'Global Stats',
    'nav.compare':     'Compare',
    'nav.benchmark':   'Benchmark',
    'nav.research_section': 'Research',
    'nav.research':    'Research Datasets',
    'form.name.label': 'DATASET NAME',
    'form.name.placeholder': 'e.g. UA News Article, Research Paper...',
    'form.text.label': 'TEXT — paste any Ukrainian or English text',
    'form.text.placeholder': 'Paste text for analysis...\n\nMinimum 50 words for quality results.',
    'form.measures.label': 'COLLOCATION MEASURES',
    'form.minfreq.label': 'MIN COLLOCATION FREQ',
    'form.topn.label': 'TOP N RESULTS',
    'btn.analyze': 'Run Analysis',
    'btn.clear': 'Clear',
    'panel.submit': 'Submit Text for Analysis',
    'panel.samples': 'Sample Texts',
    'stat.tokens': 'TOKENS',
    'stat.vocab': 'VOCABULARY',
    'stat.ttr': 'TTR',
    'stat.ttr.sub': 'type-token ratio',
    'stat.yule': "YULE'S K",
    'stat.yule.sub': 'lexical richness',
    'stat.hapax': 'HAPAX',
    'stat.hapax.sub': 'once-only words',
    'stat.zipf': 'ZIPF FIT',
    'tab.freq': 'Frequency',
    'tab.colls': 'Collocations',
    'tab.zipf': 'Zipf Chart',
    'tab.bands': 'Freq Bands',
    'table.topwords': 'TOP WORDS',
    'table.distribution': 'DISTRIBUTION',
    'panel.datasets': 'All Datasets',
    'btn.refresh': '↺ Refresh',
    'empty.datasets': 'No datasets yet. Analyze a text to create your first dataset.',
    'stat.total_datasets': 'TOTAL DATASETS',
    'stat.total_tokens': 'TOTAL TOKENS',
    'stat.avg_ttr': 'AVG TTR',
    'stat.avg_yule': "AVG YULE'S K",
    'panel.lang_dist': 'Language Distribution',
    'panel.top_colls': 'Top Global Collocations (PMI)',
    'panel.per_dataset': 'Per-Dataset Comparison',
    'panel.bench': 'lexilab vs NLTK vs spaCy vs Gensim',
    'col.method': 'Method',
    'col.type': 'Type',
    'col.time': 'Time (ms)',
    'col.memory': 'Memory (KB)',
    'col.status': 'Status',
    'panel.bench_chart': 'Time Comparison Chart',
    'panel.research': 'Research Datasets',
    'tab.all': 'All',
    'stat.research_corpus': 'research corpus',
    'research.click_hint': 'Click a dataset row above to see its collocations',
    'panel.ttr_chart': 'TTR by Dataset',
    'panel.yule_chart': "Yule's K by Dataset",
    'panel.colls_per': 'Top Collocations per Dataset',
    'col.word': 'Word',
    'col.count': 'Count',
    'col.bigram': 'Bigram',
    'col.freq': 'Freq',
    'col.score': 'Score',
    'col.avg_pmi': 'Avg PMI',
    'zipf.description': 'Log-log plot of rank vs frequency. Zipf\'s law predicts a straight line with slope ≈ −1.',
    'bands.title': 'FREQUENCY BAND BREAKDOWN',
  }
};

function t(key) {
  return i18n[currentLang]?.[key] || i18n.en[key] || key;
}

function setLang(lang) {
  currentLang = lang;
  document.getElementById('lang-ua').classList.toggle('active', lang === 'ua');
  document.getElementById('lang-en').classList.toggle('active', lang === 'en');
  applyTranslations();
}

function applyTranslations() {
  // головний механізм — всі елементи з data-i18n
  document.querySelectorAll('[data-i18n]').forEach(el => {
    const key = el.dataset.i18n;
    const val = t(key);
    if (val) el.textContent = val;
  });

  // placeholder окремо бо це атрибут
  document.querySelectorAll('[data-i18n-placeholder]').forEach(el => {
    el.placeholder = t(el.dataset.i18nPlaceholder);
  });

  // sidebar sections
  const sections = document.querySelectorAll('.sidebar-section');
  const sectionKeys = ['nav.analysis', 'nav.data', 'nav.compare', 'nav.research_section'];
  sections.forEach((s, i) => { if (sectionKeys[i]) s.textContent = t(sectionKeys[i]); });

  // nav items — зберігаємо іконку
  const navMap = {
    'analyze':   'nav.analyze',
    'results':   'nav.results',
    'datasets':  'nav.datasets',
    'global':    'nav.global',
    'benchmark': 'nav.benchmark',
    'research':  'nav.research',
  };
  document.querySelectorAll('.nav-item[data-view]').forEach(el => {
    const key = navMap[el.dataset.view];
    if (key) {
      const icon = el.querySelector('.icon')?.textContent || '';
      el.innerHTML = `<span class="icon">${icon}</span> ${t(key)}`;
    }
  });

  // placeholders для textarea і input
  const dsName = document.getElementById('ds-name');
  if (dsName) dsName.placeholder = t('form.name.placeholder');
  const dsText = document.getElementById('ds-text');
  if (dsText) dsText.placeholder = t('form.text.placeholder');

  // кнопки
  const btnAnalyze = document.getElementById('btn-analyze');
  if (btnAnalyze) btnAnalyze.innerHTML = `<span>◎</span> ${t('btn.analyze')}`;
  const btnClear = document.getElementById('btn-clear');
  if (btnClear) btnClear.textContent = t('btn.clear');
}

// ══════════════════════════════════════════════════
// RESEARCH DATASETS VIEW
// ══════════════════════════════════════════════════

let researchData   = null;
let researchFilter = 'all';
let selectedResearchId = null;
let researchTtrChart  = null;
let researchYuleChart = null;

// ── nav trigger ──────────────────────────────────
const _origSwitchView = switchView;
// НЕ перевизначаємо switchView — просто додаємо хук через nav-item clicks
document.querySelectorAll('.nav-item').forEach(item => {
  item.addEventListener('click', () => {
    if (item.dataset.view === 'research') loadResearch();
  });
});

// ── lang tab clicks ──────────────────────────────
document.querySelectorAll('[data-rtab]').forEach(tab => {
  tab.addEventListener('click', () => {
    document.querySelectorAll('[data-rtab]').forEach(t => t.classList.remove('active'));
    tab.classList.add('active');
    researchFilter = tab.dataset.rtab;
    if (researchData) renderResearchTable(researchData);
  });
});

// ── load from API ────────────────────────────────
async function loadResearch() {
  const wrap = document.getElementById('research-table-wrap');
  wrap.innerHTML = `<div style="display:flex;justify-content:center;padding:32px"><div class="spinner"></div></div>`;

  try {
    const resp = await fetch(`${API}/stats/research`);
    if (!resp.ok) throw new Error('API error');
    researchData = await resp.json();
    renderResearchSummary(researchData);
    renderResearchTable(researchData);
    renderResearchCharts(researchData);
  } catch {
    wrap.innerHTML = `<div class="empty-state"><div class="glyph">⚠</div><p>Could not load research datasets. Make sure the API is running and datasets are loaded.</p></div>`;
  }
}

// ── summary stat cards ───────────────────────────
function renderResearchSummary(data) {
  const el = document.getElementById('research-summary-cards');
  const summary = data.summary || {};
  const total   = data.total || 0;

  const langCounts = Object.entries(summary);
  const totalTokens = langCounts.reduce((s, [, v]) => s + (v.total_tokens || 0), 0);
  const avgTtr = langCounts.length
    ? (langCounts.reduce((s, [,v]) => s + v.avg_ttr, 0) / langCounts.length).toFixed(3)
    : '—';
  const avgYule = langCounts.length
    ? (langCounts.reduce((s,[,v]) => s + v.avg_yules_k, 0) / langCounts.length).toFixed(1)
    : '—';

  el.innerHTML = `
    <div class="stat-card loaded"><div class="stat-label">DATASETS</div><div class="stat-value accent">${total}</div><div class="stat-sub">research corpus</div></div>
    <div class="stat-card loaded"><div class="stat-label">TOTAL TOKENS</div><div class="stat-value">${fmtNum(totalTokens)}</div></div>
    <div class="stat-card loaded"><div class="stat-label">AVG TTR</div><div class="stat-value accent2">${avgTtr}</div><div class="stat-sub">type-token ratio</div></div>
    <div class="stat-card loaded"><div class="stat-label">AVG YULE'S K</div><div class="stat-value">${avgYule}</div></div>
    ${langCounts.map(([lang, v]) => `
      <div class="stat-card loaded">
        <div class="stat-label">${lang.toUpperCase()} DATASETS</div>
        <div class="stat-value" style="font-size:18px">${v.count}</div>
        <div class="stat-sub">TTR ${v.avg_ttr} · K ${v.avg_yules_k}</div>
      </div>
    `).join('')}
  `;
}

// ── table ────────────────────────────────────────
function renderResearchTable(data) {
  const wrap = document.getElementById('research-table-wrap');
  const byLang = data.by_lang || {};

  // flatten + filter
  let rows = [];
  for (const [lang, items] of Object.entries(byLang)) {
    for (const item of items) rows.push({ ...item, lang });
  }
  if (researchFilter !== 'all') {
    rows = rows.filter(r => r.lang === researchFilter);
  }

  if (!rows.length) {
    wrap.innerHTML = `<div class="empty-state"><div class="glyph">⚗</div><p>No datasets for this language yet.</p></div>`;
    return;
  }

  const langBadge = (lang) => {
    const cls = lang === 'en' ? 'en' : lang === 'mixed' ? 'mixed' : '';
    const label = lang === 'ua' ? '🇺🇦 ua' : lang === 'en' ? '🇬🇧 en' : '⚡ mixed';
    return `<span class="research-lang-badge ${cls}">${label}</span>`;
  };

  wrap.innerHTML = `
    <div class="research-row header">
      <div>Name</div>
      <div style="text-align:right">Tokens</div>
      <div style="text-align:right">TTR</div>
      <div style="text-align:right">Yule K</div>
      <div style="text-align:right">Zipf r</div>
      <div style="text-align:right">Lang</div>
    </div>
    ${rows.map(r => `
      <div class="research-row ${r.id === selectedResearchId ? 'selected' : ''}"
           onclick="selectResearchDataset(${r.id})">
        <div class="research-name">${r.name}</div>
        <div class="research-val">${fmtNum(r.token_count || 0)}</div>
        <div class="research-val">${(r.ttr || 0).toFixed(3)}</div>
        <div class="research-val">${(r.yules_k || 0).toFixed(1)}</div>
        <div class="research-val" style="color:${r.fits_zipf ? 'var(--accent)' : 'var(--text3)'}">
          ${(r.zipf_corr || 0).toFixed(3)}
        </div>
        <div style="text-align:right">${langBadge(r.lang)}</div>
      </div>
    `).join('')}
  `;
}

// ── select dataset → show collocations ──────────
async function selectResearchDataset(id) {
  selectedResearchId = id;
  if (researchData) renderResearchTable(researchData);

  const wrap = document.getElementById('research-colls-wrap');
  wrap.innerHTML = `<div style="display:flex;justify-content:center;padding:24px"><div class="spinner"></div></div>`;

  try {
    const resp = await fetch(`${API}/analyze/${id}`);
    if (!resp.ok) throw new Error();
    const data = await resp.json();

    const colls = data.collocations || {};
    const measures = Object.keys(colls);
    if (!measures.length) {
      wrap.innerHTML = `<div class="empty-state"><div class="glyph">◎</div><p>No collocations stored for this dataset.</p></div>`;
      return;
    }

    // show PMI by default, pills to switch
    let activeMeasure = measures.includes('pmi') ? 'pmi' : measures[0];

    wrap.innerHTML = `
      <div style="margin-bottom:8px;font-size:11px;color:var(--text3)">
        Dataset id=${id}
      </div>
      <div class="pills" id="research-coll-pills">
        ${measures.map(m => `<div class="pill ${m===activeMeasure?'active':''}" data-measure="${m}">${m}</div>`).join('')}
      </div>
      <div id="research-coll-table">${renderCollsTable(colls, activeMeasure)}</div>
    `;

    // зберігаємо colls у closure і вішаємо обробники
    document.querySelectorAll('#research-coll-pills .pill').forEach(pill => {
      pill.addEventListener('click', () => {
        document.querySelectorAll('#research-coll-pills .pill').forEach(p => p.classList.remove('active'));
        pill.classList.add('active');
        document.getElementById('research-coll-table').innerHTML = renderCollsTable(colls, pill.dataset.measure);
      });
    });
  } catch {
    wrap.innerHTML = `<div class="empty-state"><div class="glyph">⚠</div><p>Could not load dataset analysis.</p></div>`;
  }
}

function renderCollsTable(colls, m) {
  const items = colls[m] || [];
  if (!items.length) return '<div style="color:var(--text3);padding:12px">No collocations for this measure.</div>';
  const max = Math.max(...items.map(i => Math.abs(i.score || 0))) || 1;
  return `
    <table class="data-table" style="margin-top:10px">
      <thead><tr><th>#</th><th>Bigram</th><th>Freq</th><th style="text-align:right">Score</th><th style="min-width:100px"></th></tr></thead>
      <tbody>
        ${items.slice(0, 15).map((r, i) => {
          const pct = (Math.abs(r.score || 0) / max * 100).toFixed(1);
          return `<tr>
            <td class="rank">${r.rank || i+1}</td>
            <td class="bigram">${r.bigram[0]} <span style="color:var(--text3)">+</span> ${r.bigram[1]}</td>
            <td style="color:var(--text3)">${r.freq}</td>
            <td class="score">${(r.score||0).toFixed(4)}</td>
            <td><div class="score-bar"><div class="score-bar-fill" style="width:${pct}%"></div></div></td>
          </tr>`;
        }).join('')}
      </tbody>
    </table>`;
}

// ── TTR + Yule charts ────────────────────────────
function renderResearchCharts(data) {
  const byLang = data.by_lang || {};
  const colors = { ua: 'rgba(0,229,180,0.7)', en: 'rgba(124,111,255,0.7)', mixed: 'rgba(255,107,107,0.7)' };

  const allRows = Object.entries(byLang).flatMap(([lang, items]) =>
    items.map(i => ({ ...i, lang }))
  );

  const labels = allRows.map(r => r.name.length > 18 ? r.name.slice(0,16)+'…' : r.name);
  const bgColors = allRows.map(r => colors[r.lang] || 'rgba(136,136,170,0.5)');

  const chartOpts = (title) => ({
    responsive: true, maintainAspectRatio: false,
    plugins: {
      legend: { display: false },
      tooltip: { callbacks: { title: (ctx) => allRows[ctx[0].dataIndex]?.name } }
    },
    scales: {
      x: { ticks: { color: '#8888aa', font: { family: 'JetBrains Mono', size: 9 }, maxRotation: 45 }, grid: { display: false } },
      y: { ticks: { color: '#8888aa', font: { family: 'JetBrains Mono', size: 9 } }, grid: { color: '#2a2a3a' },
           title: { display: true, text: title, color: '#55556a', font: { size: 9 } } }
    }
  });

  // TTR chart
  if (researchTtrChart) researchTtrChart.destroy();
  researchTtrChart = new Chart(
    document.getElementById('research-ttr-chart').getContext('2d'),
    { type: 'bar', data: { labels, datasets: [{ data: allRows.map(r => r.ttr), backgroundColor: bgColors, borderRadius: 3 }] }, options: chartOpts('TTR') }
  );

  // Yule chart
  if (researchYuleChart) researchYuleChart.destroy();
  researchYuleChart = new Chart(
    document.getElementById('research-yule-chart').getContext('2d'),
    { type: 'bar', data: { labels, datasets: [{ data: allRows.map(r => r.yules_k), backgroundColor: bgColors, borderRadius: 3 }] }, options: chartOpts("Yule's K") }
  );
}

// застосовуємо UA переклад одразу при завантаженні
applyTranslations();