// Cross-page transitions: use View Transitions when available; otherwise CSS fallback
(function () {
  const html = document.documentElement;
  const reduce = window.matchMedia('(prefers-reduced-motion: reduce)').matches;

  // Fade-in on load (fallback path)
  if (!reduce) html.classList.add('is-preload');
  window.addEventListener('pageshow', () => {
    if (!reduce) {
      html.classList.remove('is-preload');
      requestAnimationFrame(() => html.classList.add('anim-in'));
    }
  });

  function isLocal(url) {
    try {
      const u = new URL(url, location.href);
      return u.origin === location.origin && u.pathname !== location.pathname && !u.hash;
    } catch { return false; }
  }

  function go(url) {
    // Prefer native View Transitions if present
    if (!reduce && document.startViewTransition) {
      document.startViewTransition(() => { location.href = url; });
      return;
    }
    // Fallback CSS fade-out
    if (!reduce) {
      html.classList.remove('anim-in');
      html.classList.add('anim-out');
      setTimeout(() => { location.href = url; }, 120);
    } else {
      location.href = url;
    }
  }

  // Intercept internal link clicks
  document.addEventListener('click', (e) => {
    const a = e.target.closest('a[href]');
    if (!a) return;
    if (a.target && a.target !== '_self') return;
    if (a.hasAttribute('download') || a.getAttribute('rel') === 'external') return;

    const href = a.getAttribute('href');
    if (!isLocal(href)) return;

    e.preventDefault();
    go(new URL(href, location.href).href);
  });

  // Intercept same-origin form submits (e.g. login)
  document.addEventListener('submit', (e) => {
    const form = e.target;
    try {
      const u = new URL(form.action || location.href, location.href);
      if (u.origin !== location.origin) return;
    } catch { return; }

    if (!reduce && !document.startViewTransition) {
      html.classList.remove('anim-in');
      html.classList.add('anim-out');
    }
    // Let the submit proceed; the next page shows the enter animation
  });
})();
