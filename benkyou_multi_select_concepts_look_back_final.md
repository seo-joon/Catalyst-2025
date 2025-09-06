# Project files

```
student-bloomberg/
├─ main.py
└─ public/
   ├─ index.html
   └─ main.js
```

---

## main.py
```python
from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
import feedparser
from dateutil import parser as dtparse
from datetime import datetime, timedelta, timezone
import re

app = FastAPI(title="benkyou")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Health check
@app.get("/ping")
def ping():
    return {"ok": True}

# --- Sources (RSS/Atom feeds) ---
SOURCES = [
    ("Reuters Business", "https://feeds.reuters.com/reuters/businessNews"),
    ("ACCC Media Releases", "https://www.accc.gov.au/rss/media_releases.xml"),
    ("RBA Media Releases", "https://www.rba.gov.au/rss/rss-cb-media-releases.xml"),
]

# --- Concept taxonomy: commerce + arts ---
CONCEPTS = {
    "commerce": {
        "oligopoly": ["cartel", "price fixing", "collusion", "duopoly", "oligopoly", "ACCC", "OPEC", "petrol", "fuel"],
        "monopoly": ["monopoly", "dominant position", "market power", "antitrust", "competition watchdog", "Section 46"],
        "mergers_and_acquisitions": ["merger", "acquisition", "takeover", "M&A", "scheme of arrangement", "bid"],
        "inflation": ["inflation", "CPI", "consumer price index", "price pressures", "disinflation", "headline inflation"],
        "monetary_policy": ["interest rate", "cash rate", "RBA", "rate hike", "rate cut", "QE", "QT", "policy decision"],
        "fiscal_policy": ["budget deficit", "surplus", "spending", "tax cut", "stimulus", "fiscal"],
        "externalities": ["externality", "pollution", "carbon", "emissions", "tax credit", "subsidy"],
        "asymmetric_information": ["information asymmetry", "insider", "adverse selection", "moral hazard"],
        "price_discrimination": ["price discrimination", "dynamic pricing", "surge pricing", "loyalty pricing"],
        "competition_policy": ["ACCC", "antitrust", "competition authority", "undertaking", "court-enforceable"],
        "game_theory": ["tacit collusion", "Nash equilibrium", "strategic", "coordination", "prisoners' dilemma"],
    },
    "arts": {
        "copyright": ["copyright", "intellectual property", "royalties", "licensing", "fair use", "IP"],
        "censorship": ["censor", "ban", "content moderation", "free speech", "classification board"],
        "cultural_policy": ["arts funding", "grant", "Creative Australia", "cultural policy", "museum"],
        "labour_unions": ["strike", "union", "industrial action", "actors guild"],
    },
}

# Flatten for quick lookup
ALL_CONCEPTS = {**CONCEPTS["commerce"], **CONCEPTS["arts"]}

# --- Helpers ---
TAG_RE = re.compile(r"<[^>]+>")

def strip_html(text: str) -> str:
    return TAG_RE.sub("", text or "").strip()

def match_concepts(text: str):
    text_l = (text or "").lower()
    matched = set()
    for concept, kws in ALL_CONCEPTS.items():
        for kw in kws:
            if kw.lower() in text_l:
                matched.add(concept)
                break
    return sorted(matched)

# --- API ---
@app.get("/api/concepts")
def list_concepts(track: str | None = Query(None, description="commerce or arts")):
    if track in ("commerce", "arts"):
        return {"track": track, "concepts": sorted(CONCEPTS[track].keys())}
    return {"track": "all", "concepts": sorted(ALL_CONCEPTS.keys())}

@app.get("/api/examples")
def examples(
    concept: list[str] | None = Query(None, description="one or more concept ids (e.g. &concept=oligopoly&concept=monetary_policy)"),
    track: str | None = Query(None, description="commerce or arts"),
    days: int = Query(7, ge=1, le=365),
    limit: int = Query(30, ge=1, le=100),
):
    """
    Filters:
    - track: 'commerce' or 'arts'
    - concept: must include ALL selected concepts (if any)
    - days: look-back window up to 365
    """
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    selected = set(concept or [])
    results = []

    for source_name, feed_url in SOURCES:
        try:
            feed = feedparser.parse(feed_url)
        except Exception:
            continue

        for e in getattr(feed, "entries", []):
            title = (e.get("title") or "").strip()
            summary = (e.get("summary") or "").strip()
            text = f"{title} {summary}"

            concepts = match_concepts(text)

            # Track filter
            if track in ("commerce", "arts"):
                concepts = [c for c in concepts if c in CONCEPTS[track]]

            # Concept filter: require ALL selected concepts (if any)
            if selected and not set(concepts).issuperset(selected):
                continue

            # Published time
            published_raw = e.get("published") or e.get("updated") or ""
            published = None
            if published_raw:
                try:
                    published = dtparse.parse(published_raw)
                except Exception:
                    published = None
            if published and published.tzinfo is None:
                published = published.replace(tzinfo=timezone.utc)
            if published and published < cutoff:
                continue

            results.append({
                "source": source_name,
                "title": title,
                "url": e.get("link"),
                "published": published.isoformat() if published else None,
                "concepts": concepts,
                "summary": strip_html(summary)[:300] + ("…" if len(strip_html(summary)) > 300 else "")
            })

    results.sort(key=lambda x: (x["published"] or "", x["title"] or ""), reverse=True)
    return results[:limit]

# Serve frontend from ./public
app.mount("/", StaticFiles(directory="public", html=True), name="static")
```

---

## public/index.html
```html
<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>benkyou — Student Bloomberg</title>
  <script src="https://cdn.tailwindcss.com"></script>
</head>
<body class="min-h-screen bg-slate-50 text-slate-800">
  <header class="sticky top-0 z-10 bg-white/80 backdrop-blur border-b">
    <div class="max-w-5xl mx-auto px-4 py-3 flex items-center justify-between">
      <h1 class="text-xl font-extrabold">benkyou</h1>
      <nav class="text-xs text-slate-600">RSS-powered · Localhost</nav>
    </div>
  </header>

  <section class="border-b bg-white/80 backdrop-blur">
    <div class="max-w-5xl mx-auto px-4 py-3">
      <div class="grid gap-3 md:grid-cols-12 items-end">
        <div class="md:col-span-3">
          <label class="block text-xs font-medium text-slate-600">Subject</label>
          <select id="track" class="mt-1 w-full rounded-md border p-2 text-sm">
            <option value="all">All</option>
            <option value="commerce">Commerce</option>
            <option value="arts">Arts</option>
          </select>
        </div>
        <div class="md:col-span-3">
          <label class="block text-xs font-medium text-slate-600">Look-back (days)</label>
          <input id="days" type="number" value="7" min="1" max="365" class="mt-1 w-full rounded-md border p-2 text-sm" />
        </div>
        <div class="md:col-span-6">
          <details class="rounded-md border bg-white p-3" id="conceptsPanel">
            <summary class="cursor-pointer select-none text-sm font-semibold">Concepts (multi-select)</summary>
            <div class="mt-2 flex items-center gap-2">
              <button type="button" id="selectAll" class="px-2 py-1 rounded border text-xs">Select all</button>
              <button type="button" id="selectNone" class="px-2 py-1 rounded border text-xs">None</button>
            </div>
            <div id="concepts" class="mt-2 grid gap-x-4 gap-y-1 grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 text-sm leading-tight">
              <!-- checkboxes injected by main.js -->
            </div>
          </details>
        </div>
        <div class="md:col-span-12 flex gap-2">
          <button id="refresh" type="button" class="px-4 py-2 rounded-md bg-blue-600 text-white text-sm font-semibold">Fetch</button>
          <button id="clear" type="button" class="px-4 py-2 rounded-md border text-sm">Clear</button>
        </div>
      </div>
    </div>
  </section>

  <main class="max-w-5xl mx-auto px-4 py-6 space-y-6">
    <section>
      <h2 class="text-lg font-bold mb-3">Results</h2>
      <div id="results" class="grid gap-3"><!-- cards injected by main.js --></div>
    </section>
    <section class="text-sm text-slate-500">
      <p>Sources: Reuters Business, ACCC, RBA. Extend by editing <code>SOURCES</code> in <code>main.py</code>.</p>
    </section>
  </main>

  <script type="module" src="/main.js"></script>
</body>
</html>
```

---

## public/main.js
```js
// Hardcode the API base so Live Server (5500) or file:// works reliably.
const API_BASE = 'http://127.0.0.1:8000';

const trackEl        = document.getElementById('track');
const conceptsWrap   = document.getElementById('concepts');
const daysEl         = document.getElementById('days');
const resultsEl      = document.getElementById('results');
const refreshBtn     = document.getElementById('refresh');
const clearBtn       = document.getElementById('clear');
const selectAllBtn   = document.getElementById('selectAll');
const selectNoneBtn  = document.getElementById('selectNone');

async function loadConcepts() {
  const t  = trackEl.value;
  const qs = t === 'all' ? '' : `?track=${encodeURIComponent(t)}`;
  resultsEl.innerHTML = '';

  try {
    const res = await fetch(`${API_BASE}/api/concepts${qs}`);
    if (!res.ok) throw new Error(`HTTP ${res.status} while loading concepts`);
    const data = await res.json();

    conceptsWrap.innerHTML = data.concepts.map(c => `
      <label class="flex items-center gap-2 text-sm">
        <input type="checkbox" name="concept" value="${c}" class="accent-blue-600">
        <span>${c.replaceAll('_',' ')}</span>
      </label>
    `).join('');
  } catch (e) {
    console.error(e);
    conceptsWrap.innerHTML = '<div class="text-slate-500">Failed to load concepts.</div>';
  }
}

function getSelectedConcepts() {
  return Array.from(document.querySelectorAll('input[name="concept"]:checked'))
              .map(el => el.value);
}

async function fetchExamples() {
  const params = new URLSearchParams();
  const t = trackEl.value;
  if (t !== 'all') params.set('track', t);

  // Append multiple concept params (?concept=a&concept=b)
  getSelectedConcepts().forEach(c => params.append('concept', c));

  const d = Math.min(365, Math.max(1, parseInt(daysEl.value || '7', 10)));
  params.set('days', String(d));
  params.set('limit', '30');

  resultsEl.innerHTML = '<div class="text-slate-500">Loading…</div>';

  try {
    const res = await fetch(`${API_BASE}/api/examples?${params.toString()}`);
    if (!res.ok) {
      const msg = await res.text();
      throw new Error(`HTTP ${res.status} fetching results: ${msg}`);
    }
    const items = await res.json();

    resultsEl.innerHTML = items.length
      ? items.map(renderCard).join('')
      : '<div class="text-slate-500">No matches. Try more concepts or increase days.</div>';
  } catch (e) {
    console.error(e);
    resultsEl.innerHTML = '<div class="text-red-600">Error fetching results.</div>';
  }
}

function renderCard(item) {
  const date = item.published ? new Date(item.published).toLocaleString() : '—';
  const badges = (item.concepts || [])
    .map(c => `<span class="px-2 py-1 text-xs rounded-full bg-slate-100 border">${c.replaceAll('_',' ')}</span>`)
    .join(' ');

  return `
  <article class="p-4 rounded-xl bg-white border shadow-sm">
    <div class="flex justify-between gap-2">
      <div class="text-xs text-slate-500">${escapeHtml(item.source || '')}</div>
      <div class="text-xs text-slate-500">${date}</div>
    </div>
    <h3 class="mt-1 font-bold">
      <a class="hover:underline" href="${item.url}" target="_blank" rel="noopener">
        ${escapeHtml(item.title || 'Untitled')}
      </a>
    </h3>
    <p class="mt-2 text-slate-700">${escapeHtml(item.summary || '')}</p>
    <div class="mt-3 flex flex-wrap gap-2">${badges}</div>
  </article>`;
}

function escapeHtml(str) {
  return String(str).replace(/[&<>"]/g, s => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[s]));
}

// Events
trackEl.addEventListener('change', loadConcepts);
refreshBtn.addEventListener('click', fetchExamples);
clearBtn.addEventListener('click', () => { resultsEl.innerHTML = ''; });
selectAllBtn?.addEventListener('click', () => {
  document.querySelectorAll('input[name="concept"]').forEach(el => el.checked = true);
});
selectNoneBtn?.addEventListener('click', () => {
  document.querySelectorAll('input[name="concept"]').forEach(el => el.checked = false);
});

// init
await loadConcepts();
await fetchExamples();
```

