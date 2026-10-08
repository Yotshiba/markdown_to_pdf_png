/* md2doc in-page renderer. Classic script, runs at the end of <body>.
 * Order: math (sync) -> fonts -> Mermaid -> PlantUML -> images -> 2 animation frames.
 * Sets window.__renderDone = true exactly once and exposes window.__renderReport. Never throws:
 * every failure becomes an inline error card plus an entry in report.errors. */
(function () {
  'use strict';
  const t0 = performance.now();
  const cfgEl = document.getElementById('md2doc-config');
  const CFG = cfgEl ? JSON.parse(cfgEl.textContent) : {};
  const report = (window.__renderReport = {
    errors: [], warnings: [], diagrams: [], math: { count: 0, errors: 0 }, ms: 0, fatal: null,
  });
  window.__renderDone = false;

  const esc = (s) => String(s).replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
  const nextFrame = () => new Promise((r) => requestAnimationFrame(() => r()));
  const lineOf = (el) => { const h = el.closest && el.closest('[data-line]'); return h ? Number(h.getAttribute('data-line')) + 1 : null; };
  const remaining = () => Math.max(0, (CFG.deadlineMs || 120000) - (performance.now() - t0));
  const withTimeout = (p, ms, what) => {
    let timer;
    const t = new Promise((_, rej) => { timer = setTimeout(() => rej(new Error(what + ' timed out after ' + Math.round(ms / 1000) + ' s')), ms); });
    return Promise.race([p, t]).finally(() => clearTimeout(timer));
  };
  const addError = (kind, el, message) => report.errors.push({ kind, line: el ? lineOf(el) : null, message: String(message).slice(0, 600) });

  function errorCard(kind, title, message, src) {
    return '<div class="diagram-error" role="alert"><div class="diagram-error-title">' + esc(title) + '</div>' +
      '<pre class="diagram-error-msg">' + esc(message) + '</pre>' +
      (src ? '<details><summary>diagram source</summary><pre class="diagram-error-src">' + esc(src) + '</pre></details>' : '') + '</div>';
  }

  /* ---------- math (KaTeX) ---------- */
  function renderMath() {
    const K = window.katex;
    const els = document.querySelectorAll('.math');
    report.math.count = els.length;
    if (!els.length) return;
    if (!K) { addError('math', null, 'KaTeX is not installed. Run: md2doc setup'); return; }
    const macros = Object.assign({}, CFG.katexMacros || {});
    els.forEach((el) => {
      if (el.dataset.rendered) return;
      const tex = el.textContent.trim();
      const display = !el.classList.contains('inline');
      try {
        K.render(tex, el, { displayMode: display, throwOnError: false, errorColor: '#cc0000', strict: 'ignore',
          trust: false, output: CFG.katexOutput || 'html', macros: macros, maxExpand: 1000 });
        el.dataset.rendered = '1';
        const bad = el.querySelector('.katex-error, [style*="color:#cc0000"]');
        if (bad) { report.math.errors++; addError('math', el, bad.getAttribute('title') || ('unknown or invalid command: ' + bad.textContent.slice(0, 80))); }
      } catch (e) {
        el.textContent = tex; el.classList.add('math-fatal'); report.math.errors++; addError('math', el, e);
      }
    });
  }

  /* shrink display equations that are wider than the text column */
  function fitMath() {
    document.querySelectorAll('.math.block, .math.display, .math.amsmath').forEach((el) => {
      const inner = el.querySelector('.katex-html') || el.querySelector('.katex');
      if (!inner) return;
      // natural width = widest formula row (equation-number columns are positioned outside this measure)
      const rows = Array.from(inner.children).filter((c) => c.classList.contains('base'));
      const natural = rows.length ? Math.max.apply(null, rows.map((c) => c.getBoundingClientRect().width)) : inner.getBoundingClientRect().width;
      const avail = el.clientWidth;
      if (natural > avail + 1) {
        const pct = Math.max(55, Math.floor((avail / natural) * 100));
        el.style.fontSize = pct + '%';
        report.warnings.push({ kind: 'math', line: lineOf(el), message: 'equation was wider than the page; shrunk to ' + pct + '%' });
      }
    });
  }

  /* ---------- fonts ---------- */
  async function loadFonts() {
    const fam = CFG.fontFamilies || [];
    const wts = CFG.fontWeights || [400, 700];
    await Promise.allSettled(fam.flatMap((f) => wts.map((w) => document.fonts.load(w + ' 16px "' + f + '"', 'Abc 123'))));
    await document.fonts.ready;
  }

  /* ---------- Mermaid ---------- */
  async function renderMermaid() {
    const hosts = Array.from(document.querySelectorAll('pre.mermaid-src'));
    if (!hosts.length) return;
    if (!window.mermaid) {
      hosts.forEach((pre) => { addError('mermaid', pre, 'Mermaid is not installed. Run: md2doc setup'); pre.outerHTML = errorCard('mermaid', 'Mermaid is not installed', 'Run: md2doc setup', ''); });
      return;
    }
    mermaid.initialize(Object.assign({ startOnLoad: false, suppressErrorRendering: true }, CFG.mermaid || {}));
    for (let i = 0; i < hosts.length; i++) {
      const pre = hosts[i];
      const src = pre.textContent.trim();
      const host = document.createElement('div');
      host.className = 'mermaid-host';
      pre.replaceWith(host);
      if (remaining() < 500) { host.innerHTML = errorCard('mermaid', 'Mermaid diagram ' + (i + 1) + ' skipped', 'export time budget used up', src); addError('mermaid', host, 'skipped: time budget used up'); continue; }
      try {
        const budget = Math.min(remaining(), CFG.mermaidTimeoutMs || 20000);
        const { svg, bindFunctions, diagramType } = await withTimeout(mermaid.render('mmd-' + i, src, host), budget, 'diagram ' + (i + 1));
        host.innerHTML = svg;
        if (bindFunctions) bindFunctions(host);
        host.dataset.state = 'ok';
        const el = host.querySelector('svg');
        const vb = el && el.viewBox && el.viewBox.baseVal;
        const r = el && el.getBoundingClientRect();
        const scale = vb && vb.width && vb.height ? Math.min(r.width / vb.width, r.height / vb.height) : 1;
        report.diagrams.push({ kind: 'mermaid', index: i, type: diagramType, scale: Math.round(scale * 100) / 100 });
        if (scale < 0.6) report.warnings.push({ kind: 'mermaid', line: lineOf(host), message: 'diagram 1:' + Math.round(scale * 100) + ' scale is small; consider a vertical layout or a landscape page' });
      } catch (e) {
        const msg = (e && (e.message || e.str)) || String(e);
        host.dataset.state = 'error';
        host.innerHTML = errorCard('mermaid', 'Mermaid diagram ' + (i + 1) + ' could not be rendered', msg, src);
        addError('mermaid', host, msg);
      }
    }
  }

  /* ---------- PlantUML (JS engine) ---------- */
  function isolateSvg(svgText, uid) {
    const doc = new DOMParser().parseFromString(svgText, 'image/svg+xml');
    const svg = doc.documentElement;
    if (!svg || svg.nodeName.toLowerCase() !== 'svg') return null;
    svg.querySelectorAll('script,foreignObject').forEach((n) => n.remove());
    const ids = new Set(Array.from(svg.querySelectorAll('[id]')).map((n) => n.id));
    [svg].concat(Array.from(svg.querySelectorAll('*'))).forEach((el) => {
      Array.from(el.attributes).forEach((a) => {
        if (/^on/i.test(a.name)) { el.removeAttribute(a.name); return; }
        if (a.name === 'href' || a.name === 'xlink:href') {
          if (/^\s*javascript:/i.test(a.value)) el.removeAttribute(a.name);
          else if (a.value.startsWith('#') && ids.has(a.value.slice(1))) el.setAttribute(a.name, '#' + uid + '-' + a.value.slice(1));
        } else if (a.value.indexOf('url(#') >= 0) {
          el.setAttribute(a.name, a.value.replace(/url\(#([^)\s]+)\)/g, (m, id) => (ids.has(id) ? 'url(#' + uid + '-' + id + ')' : m)));
        }
      });
      if (el.id && ids.has(el.id)) el.id = uid + '-' + el.id;
    });
    svg.style.background = '';
    return new XMLSerializer().serializeToString(svg);
  }

  function pumlRender(source) {
    return new Promise((resolve) => {
      try {
        window.__plantuml.renderToString(source.split(/\r\n|\r|\n/),
          (svg) => resolve({ ok: true, svg }), (msg) => resolve({ ok: false, error: String(msg) }));
      } catch (e) { resolve({ ok: false, error: String(e) }); }
    });
  }

  async function renderPlantUml() {
    const hosts = Array.from(document.querySelectorAll('pre.plantuml-src'));
    if (!hosts.length) return;
    if (!window.__plantuml) {
      hosts.forEach((pre) => { addError('plantuml', pre, 'PlantUML engine is not installed. Run: md2doc setup'); pre.outerHTML = errorCard('plantuml', 'PlantUML is not installed', 'Run: md2doc setup', ''); });
      return;
    }
    for (let i = 0; i < hosts.length; i++) {
      const pre = hosts[i];
      const src = pre.textContent;
      const orig = pre.dataset.orig || src;
      const host = document.createElement('div');
      host.className = 'plantuml-host';
      pre.replaceWith(host);
      if (remaining() < 500) { host.innerHTML = errorCard('plantuml', 'PlantUML diagram ' + (i + 1) + ' skipped', 'export time budget used up', src); addError('plantuml', host, 'skipped: time budget used up'); continue; }
      const res = await withTimeout(pumlRender(src), Math.min(remaining(), CFG.plantumlTimeoutMs || 30000), 'diagram ' + (i + 1)).catch((e) => ({ ok: false, error: e.message }));
      let svg = null, syntax = null;
      if (res.ok && /\[From (textarea|string)|Syntax Error\?/i.test(res.svg)) {
        // the engine returns an error picture instead of failing: turn it into our own card
        const texts = Array.from(new DOMParser().parseFromString(res.svg, 'image/svg+xml').querySelectorAll('text')).map((t) => t.textContent.trim()).filter(Boolean);
        const k = texts.findIndex((t) => /Syntax Error|Error line/i.test(t));
        syntax = 'PlantUML syntax error' + (k > 0 ? ' near: "' + texts[k - 1] + '"' : '') + (k >= 0 ? ' (' + texts[k].replace(/^Syntax Error\?\s*/i, '').replace(/[()]/g, '') + ')' : '');
        res.ok = false; res.error = syntax;
      }
      if (res.ok) { try { svg = isolateSvg(res.svg, 'pu' + i); } catch (e) { svg = null; } }
      if (svg) {
        host.innerHTML = svg;
        host.dataset.state = 'ok';
        report.diagrams.push({ kind: 'plantuml', index: i });
      } else {
        const msg = res.ok ? 'the engine returned no SVG' : res.error;
        host.dataset.state = 'error';
        host.innerHTML = errorCard('plantuml', 'PlantUML diagram ' + (i + 1) + ' could not be rendered', msg, orig);
        addError('plantuml', host, msg);
      }
    }
  }

  async function settleImages() {
    document.querySelectorAll('img[loading="lazy"]').forEach((i) => { i.loading = 'eager'; });
    await Promise.all(Array.from(document.images).map((i) =>
      i.complete ? (i.naturalWidth ? i.decode().catch(() => {}) : (report.warnings.push({ kind: 'image', line: lineOf(i), message: 'image failed to load: ' + (i.getAttribute('alt') || i.src.slice(-60)) }), null))
        : new Promise((r) => { i.onload = i.onerror = r; })));
  }

  async function main() {
    renderMath();
    await loadFonts();
    await renderMermaid();
    await renderPlantUml();
    await document.fonts.ready;
    fitMath();
    await settleImages();
    await nextFrame(); await nextFrame();
  }

  main().catch((e) => { report.fatal = (e && e.stack) || String(e); })
    .finally(() => { report.ms = Math.round(performance.now() - t0); window.__renderDone = true; });
})();
