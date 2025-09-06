const trackEl = document.getElementById('track');
const conceptEl = document.getElementById('concept');
const daysEl = document.getElementById('days');
const resultsEl = document.getElementById('results');
const refreshBtn = document.getElementById('refresh');
const clearBtn = document.getElementById('clear');

async function loadConcepts() {
  const t = trackEl.value;
  const qs = t === 'all' ? '' : `?track=${t}`;
  const res = await fetch(`/api/concepts${qs}`);
  const data = await res.json();
  conceptEl.innerHTML = '<option value="">(Any)</option>' +
    data.concepts.map(c => `<option value="${c}">${c.replaceAll('_',' ')}</option>`).join('');
}

async function fetchExamples() {
  const params = new URLSearchParams();
  const t = trackEl.value;
  if (t !== 'all') params.set('track', t);
  const c = conceptEl.value;
  if (c) params.set('concept', c);
  const d = parseInt(daysEl.value || '7', 10);
  params.set('days', Math.min(60, Math.max(1, d)));
  params.set('limit', '30');

  resultsEl.innerHTML = '<div class="text-slate-500">Loading…</div>';
  const res = await fetch(`/api/examples?${params.toString()}`);
  const items = await res.json();
  if (!items.length) {
    resultsEl.innerHTML = '<div class="text-slate-500">No matches. Try another concept or increase days.</div>';
    return;
  }
  resultsEl.innerHTML = items.map(renderCard).join('');
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

trackEl.addEventListener('change', () => loadConcepts());
refreshBtn.addEventListener('click', () => fetchExamples());
clearBtn.addEventListener('click', () => { resultsEl.innerHTML = ''; });

// init
await loadConcepts();
await fetchExamples();