const trackEl      = document.getElementById('track');
const conceptsWrap = document.getElementById('concepts');
const daysEl       = document.getElementById('days');
const resultsEl    = document.getElementById('results');
const refreshBtn   = document.getElementById('refresh');
const clearBtn     = document.getElementById('clear');
const exportBtn    = document.getElementById('exportAnki');

const conceptsToggle = document.getElementById('conceptsToggle');
const conceptsPopover= document.getElementById('conceptPopover');
const conceptsClose  = document.getElementById('conceptsClose');
const selectAllBtn   = document.getElementById('selectAll');
const selectNoneBtn  = document.getElementById('selectNone');
const selectedCountEl= document.getElementById('selectedCount');

// Keep the latest fetched items here (for export)
let lastItems = [];

// ---- Auth badge in header
async function renderAuth() {
  try {
    // Same-origin fetch: cookies will be sent automatically
    const res = await fetch('/api/session', { credentials: 'include' });
    const data = await res.json();
    const el = document.getElementById('authArea');
    if (!el) return;

    if (data.authenticated) {
      const u = data.user || {};
      el.innerHTML = `
        <span class="inline-flex items-center gap-2">
          <span>Hi, ${u.name || u.login}</span>
          <form method="post" action="/logout">
            <button class="ml-2 text-red-600 hover:underline" type="submit">Logout</button>
          </form>
        </span>`;
    } else {
      el.innerHTML = `<a href="/login.html" class="text-blue-600 hover:underline">Sign in</a>`;
    }
  } catch (e) {
    // fall back silently
  }
}

function openPopover() {
  conceptsPopover.classList.remove('hidden');
  conceptsToggle.setAttribute('aria-expanded', 'true');
}
function closePopover() {
  conceptsPopover.classList.add('hidden');
  conceptsToggle.setAttribute('aria-expanded', 'false');
}
function togglePopover() {
  conceptsPopover.classList.contains('hidden') ? openPopover() : closePopover();
}

function updateSelectedCount() {
  const n = document.querySelectorAll('input[name="concept"]:checked').length;
  if (selectedCountEl) selectedCountEl.textContent = `${n} selected`;
}

// Onboarding prefs bootstrap
const savedPrefs = JSON.parse(localStorage.getItem('benkyou:prefs') || 'null');
if (savedPrefs) {
  if (savedPrefs.track) trackEl.value = savedPrefs.track;
  if (savedPrefs.days)  daysEl.value  = savedPrefs.days;
}

async function loadConcepts() {
  const t = trackEl.value;
  const qs = t === 'all' ? '' : `?track=${t}`;
  const res = await fetch(`/api/concepts${qs}`);
  const data = await res.json();
  conceptsWrap.innerHTML = data.concepts.map(c => `
    <label class="flex items-center gap-2 text-sm">
      <input type="checkbox" name="concept" value="${c}" class="accent-blue-600">
      <span>${c.replaceAll('_',' ')}</span>
    </label>
  `).join('');
  updateSelectedCount();
}

function getSelectedConcepts() {
  return Array.from(document.querySelectorAll('input[name="concept"]:checked'))
              .map(el => el.value);
}

async function fetchExamples() {
  const params = new URLSearchParams();
  const t = trackEl.value;
  if (t !== 'all') params.set('track', t);
  getSelectedConcepts().forEach(c => params.append('concept', c));
  const d = parseInt(daysEl.value || '7', 10);
  params.set('days', String(Math.min(365, Math.max(1, d))));
  params.set('limit', '30');

  resultsEl.innerHTML = '<div class="text-slate-500">Loading…</div>';
  const res = await fetch(`/api/examples?${params.toString()}`);
  const items = await res.json();

  lastItems = items; // <-- NEW: remember what’s shown

  resultsEl.innerHTML = items.length
    ? items.map(renderCard).join('')
    : '<div class="text-slate-500">No matches. Try more concepts or increase days.</div>';
}

function renderCard(item) {
  const date = item.published ? new Date(item.published).toLocaleString() : '—';
  const badges = (item.concepts || []).map(c => `<span class="px-2 py-1 text-xs rounded-full bg-slate-100 border">${c.replaceAll('_',' ')}</span>`).join(' ');
  return `
  <article class="p-4 rounded-xl bg-white border shadow-sm">
    <div class="flex justify-between gap-2">
      <div class="text-xs text-slate-500">${item.source}</div>
      <div class="text-xs text-slate-500">${date}</div>
    </div>
    <h3 class="mt-1 font-bold"><a class="hover:underline" href="${item.url}" target="_blank" rel="noopener">${item.title || 'Untitled'}</a></h3>
    <p class="mt-2 text-slate-700">${escapeHtml(item.summary || '')}</p>
    <div class="mt-3 flex flex-wrap gap-2">${badges}</div>
  </article>`;
}

function escapeHtml(str) {
  return str.replace(/[&<>"]/g, s => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[s]));
}

// --- Anki CSV export helpers ---
function csvEscape(v) {
  // Proper CSV quoting for commas/quotes/newlines
  const s = String(v ?? '');
  return `"${s.replace(/"/g, '""')}"`;
}

function wordCount(s) {
  return (String(s || '').trim().match(/\S+/g) || []).length;
}

function toHumanConcept(c) {
  return String(c || '').replaceAll('_', ' ');
}

function buildAnkiCsvRows(items) {
  // Two columns: Question (title), Answer (concepts)
  const rows = [];
  for (const it of items) {
    const title = it.title || '';
    const concepts = Array.isArray(it.concepts) ? it.concepts : [];

    // Title must be > 5 words; require at least one concept
    if (wordCount(title) <= 5 || concepts.length === 0) continue;

    const q = title.trim();
    const a = concepts.map(toHumanConcept).join(' ; '); // semicolons inside a CSV cell

    rows.push(`${csvEscape(q)},${csvEscape(a)}`);
  }
  return rows;
}

function downloadCsv(filename, content) {
  const blob = new Blob([content], { type: 'text/csv;charset=utf-8;' });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(url);
}

// Export button
exportBtn?.addEventListener('click', () => {
  if (!lastItems || lastItems.length === 0) {
    resultsEl.insertAdjacentHTML('afterbegin',
      '<div class="text-amber-700 bg-amber-50 border border-amber-200 rounded-md p-2 mb-3">Nothing to export yet. Fetch some results first.</div>');
    return;
  }
  const rows = buildAnkiCsvRows(lastItems);
  if (rows.length === 0) {
    resultsEl.insertAdjacentHTML('afterbegin',
      '<div class="text-amber-700 bg-amber-50 border border-amber-200 rounded-md p-2 mb-3">No titles longer than 5 words with concepts to export.</div>');
    return;
  }
  const csv = rows.join('\r\n'); // no header row for Anki
  const ts = new Date().toISOString().slice(0,10);
  downloadCsv(`benkyou-anki-${ts}.csv`, csv);
});


// Events
trackEl.addEventListener('change', loadConcepts);
refreshBtn.addEventListener('click', () => { closePopover(); fetchExamples(); });
clearBtn.addEventListener('click', () => { resultsEl.innerHTML = ''; });

conceptsToggle.addEventListener('click', (e) => { e.stopPropagation(); togglePopover(); });
conceptsClose.addEventListener('click', (e) => { e.preventDefault(); closePopover(); });
document.addEventListener('click', (e) => {
  if (!conceptsPopover.classList.contains('hidden') &&
      !conceptsPopover.contains(e.target) &&
      !conceptsToggle.contains(e.target)) {
    closePopover();
  }
});
document.addEventListener('keydown', (e) => { if (e.key === 'Escape') closePopover(); });

// Delegate changes inside the popover to keep count live
conceptsWrap.addEventListener('change', (e) => {
  if (e.target && e.target.name === 'concept') updateSelectedCount();
});
selectAllBtn.addEventListener('click', () => {
  document.querySelectorAll('input[name="concept"]').forEach(el => el.checked = true);
  updateSelectedCount();
});
selectNoneBtn.addEventListener('click', () => {
  document.querySelectorAll('input[name="concept"]').forEach(el => el.checked = false);
  updateSelectedCount();
});

// init
await renderAuth();
await loadConcepts();

if (savedPrefs?.concepts?.length) {
  const set = new Set(savedPrefs.concepts);
  document.querySelectorAll('input[name="concept"]').forEach(el => { el.checked = set.has(el.value); });
  updateSelectedCount();
}

await fetchExamples();
