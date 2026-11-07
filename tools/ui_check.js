/* TEST-ONLY visual + accessibility sweep against tools/ui_fixture_server.py (MOCK Gemini readings).
   node tools/ui_check.js <outDir> [--quick]
   Writes PNG screenshots and report.json with measured checks per state/viewport/theme. */
const { chromium } = require('playwright');
const fs = require('fs');
const path = require('path');
const BASE = process.env.AXA_URL || 'http://localhost:8765';
const OUT = process.argv[2] || 'ui-shots';
const QUICK = process.argv.includes('--quick');
fs.mkdirSync(OUT, { recursive: true });

const T = {};
const STATES = [
  { id: 'benign', key: 'Te asteptam in Cargus' },
  { id: 'marketing', key: 'Distreaza-te la Pinata' },
  { id: 'suspicious', key: 'DPD: Livrarea a esuat' },
  { id: 'critical', key: 'ALERTĂ BCR' },
  { id: 'family', key: 'Salut mami' },
  { id: 'inconclusive', key: 'Nu trimite parola' },
  { id: 'protective', key: 'Atenție: angajații' },
  { id: 'badurl', key: 'Verifică https://[bad' },
  { id: 'ai_timeout', key: 'ALERTĂ BCR', mode: 'ai_timeout' },
  { id: 'ai_off', key: 'Te asteptam in Cargus', mode: 'ai_not_configured' },
];
const VIEWPORTS = QUICK ? [[390, 844], [1440, 900]] : [[320, 700], [390, 844], [768, 1024], [1440, 900], [1920, 1080]];

async function fixture(page, mode) {
  await page.evaluate(m => fetch('/__fixture', { method: 'POST', body: JSON.stringify({ mode: m }) }), mode || 'normal');
}

async function audit(page) {
  return page.evaluate(() => {
    const doc = document.documentElement;
    const parse = c => { const m = c.match(/rgba?\(([^)]+)\)/); if (!m) return null; const p = m[1].split(/[ ,/]+/).filter(Boolean).map(Number); return { r: p[0], g: p[1], b: p[2], a: p.length > 3 ? p[3] : 1 }; };
    const lum = c => { const f = v => { v /= 255; return v <= 0.03928 ? v / 12.92 : Math.pow((v + 0.055) / 1.055, 2.4); }; return 0.2126 * f(c.r) + 0.7152 * f(c.g) + 0.0722 * f(c.b); };
    const bgOf = el => { let bgs = []; for (let e = el; e; e = e.parentElement) { const c = parse(getComputedStyle(e).backgroundColor); if (c && c.a > 0) { bgs.push(c); if (c.a >= 1) break; } } let base = parse(getComputedStyle(document.body).backgroundColor) || { r: 255, g: 255, b: 255, a: 1 }; for (const c of bgs.reverse()) base = { r: c.r * c.a + base.r * (1 - c.a), g: c.g * c.a + base.g * (1 - c.a), b: c.b * c.a + base.b * (1 - c.a), a: 1 }; return base; };
    const visible = el => { const r = el.getBoundingClientRect(); const s = getComputedStyle(el); return r.width > 0 && r.height > 0 && s.visibility !== 'hidden' && s.display !== 'none' && +s.opacity !== 0 && !el.closest('[hidden],details:not([open]) > :not(summary)'); };
    const lowContrast = [], smallText = [];
    const walker = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
    const seen = new Set();
    while (walker.nextNode()) {
      const n = walker.currentNode; const el = n.parentElement;
      if (!el || seen.has(el) || !n.textContent.trim() || !visible(el) || el.closest('.sr,.skip,svg')) continue;
      seen.add(el);
      const s = getComputedStyle(el); const fg = parse(s.color); if (!fg) continue;
      const bg = bgOf(el); const l1 = lum(fg), l2 = lum(bg); const ratio = (Math.max(l1, l2) + 0.05) / (Math.min(l1, l2) + 0.05);
      const size = parseFloat(s.fontSize), bold = +s.fontWeight >= 700; const large = size >= 24 || (bold && size >= 18.66);
      if (ratio < (large ? 3 : 4.5)) lowContrast.push({ text: n.textContent.trim().slice(0, 40), ratio: +ratio.toFixed(2), size });
      if (size < 14) smallText.push({ text: n.textContent.trim().slice(0, 40), size });
    }
    const controls = [...document.querySelectorAll('button, a[href], input, select, textarea, summary, [tabindex="0"]')].filter(visible);
    const smallTargets = controls.filter(e => { const r = e.getBoundingClientRect(); return (r.width < 24 || r.height < 24) && !(e.tagName === 'A' && getComputedStyle(e).display === 'inline'); }).map(e => (e.id || e.className || e.tagName) + ':' + Math.round(e.getBoundingClientRect().width) + 'x' + Math.round(e.getBoundingClientRect().height));
    const under44 = controls.filter(e => { const r = e.getBoundingClientRect(); return r.height < 44 && !['A'].includes(e.tagName) && e.type !== 'checkbox'; }).length;
    const unnamed = controls.filter(e => { const name = (e.getAttribute('aria-label') || e.textContent || e.getAttribute('title') || (e.labels && e.labels[0] && e.labels[0].textContent) || '').trim(); return !name && e.type !== 'file'; }).map(e => e.id || e.tagName);
    const headings = [...document.querySelectorAll('h1,h2,h3,h4')].filter(visible).map(h => +h.tagName[1]);
    const skips = headings.filter((h, i) => i && h - headings[i - 1] > 1).length;
    const anims = [...document.querySelectorAll('*')].filter(e => { const s = getComputedStyle(e); return s.animationName !== 'none' && s.animationIterationCount === 'infinite'; }).length;
    return { overflowX: doc.scrollWidth - doc.clientWidth, lowContrast: lowContrast.slice(0, 12), lowContrastCount: lowContrast.length,
      smallTextCount: smallText.length, smallText: smallText.slice(0, 6), smallTargets, controlsUnder44: under44, controls: controls.length,
      unnamed, headingSkips: skips, h1: document.querySelectorAll('h1').length, infiniteAnimations: anims, pageHeight: doc.scrollHeight };
  });
}

async function firstScreenFacts(page) {
  // Where do verdict, primary action and recovery entry sit relative to the result top (first mobile screen?)
  return page.evaluate(() => {
    const out = document.getElementById('out'); if (!out || out.hidden) return null;
    const top = out.getBoundingClientRect().top + scrollY;
    const pos = sel => { const e = out.querySelector(sel); return e ? Math.round(e.getBoundingClientRect().top + scrollY - top) : null; };
    return { verdict: pos('h2'), action: pos('[data-role="action"], .act'), recovery: pos('[data-role="recovery"]'), spectrum: pos('[data-role="spectrum"]'), resultHeight: Math.round(out.getBoundingClientRect().height), viewport: innerHeight };
  });
}

(async () => {
  const browser = await chromium.launch();
  // The sweep measures the interface after the GDPR consent was given; consent itself is covered by tools/consent_check.js.
  const newContext = browser.newContext.bind(browser);
  browser.newContext = async opts => {
    const c = await newContext(opts);
    await c.addInitScript(() => { try { localStorage.setItem('axa_consent_v1', JSON.stringify({ granted: true, at: '2026-01-01T00:00:00Z', version: 1 })); } catch (e) { /* ignore */ } });
    return c;
  };
  const report = { base: BASE, note: 'MOCK Gemini readings via tools/ui_fixture_server.py; deterministic layers real.', runs: [] };
  const fixtures = await (await fetch(BASE + '/__fixtures')).json();
  const textFor = key => fixtures.texts.find(t => t.startsWith(key));
  for (const theme of ['light', 'dark']) {
    for (const [w, h] of (theme === 'dark' ? [[390, 844], [1440, 900]] : VIEWPORTS)) {
      const ctx = await browser.newContext({ viewport: { width: w, height: h }, colorScheme: theme, reducedMotion: 'reduce', deviceScaleFactor: 1 });
      const page = await ctx.newPage();
      const errors = []; page.on('pageerror', e => errors.push(e.message)); page.on('console', m => { if (m.type() === 'error' && !/fonts|ERR_TUNNEL|ERR_NAME/.test(m.text())) errors.push(m.text()); });
      await page.goto(BASE + '/'); await page.waitForTimeout(300);
      const tag = `${theme}-${w}`;
      await page.screenshot({ path: path.join(OUT, `home-${tag}.png`), fullPage: false });
      report.runs.push({ state: 'home', theme, w, ...(await audit(page)), errors: [...errors] });
      const states = (theme === 'dark' || (w !== 390 && w !== 1440 && w !== 320)) ? STATES.filter(s => ['critical', 'benign', 'inconclusive'].includes(s.id)) : STATES;
      for (const st of states) {
        await fixture(page, st.mode);
        await page.fill('#t', textFor(st.key));
        await page.click('#go');
        await page.waitForFunction(() => { const o = document.getElementById('out'); return o && !o.hidden && o.getAttribute('aria-busy') !== 'true' && o.textContent.length > 50; }, null, { timeout: 15000 });
        await page.waitForTimeout(250);
        const facts = await firstScreenFacts(page);
        await page.evaluate(() => document.getElementById('out').scrollIntoView());
        await page.screenshot({ path: path.join(OUT, `${st.id}-${tag}.png`), fullPage: false });
        if (!QUICK && (w === 390 || w === 1440) && theme === 'light') await page.screenshot({ path: path.join(OUT, `${st.id}-${tag}-full.png`), fullPage: true });
        report.runs.push({ state: st.id, theme, w, firstScreen: facts, ...(await audit(page)), errors: [...errors] });
        if (['critical', 'benign', 'inconclusive'].includes(st.id) && (w === 390 || w === 1440)) {
          // Expanded view: every disclosure open, recovery panel open with one situation chosen, one evidence selected.
          await page.evaluate(() => document.querySelectorAll('#out details').forEach(d => { d.open = true; }));
          if (await page.$('#recb')) { await page.click('#recb'); await page.waitForTimeout(100); await page.click('#out .tile'); }
          if (await page.$('#evm-1')) await page.click('#evm-1');
          await page.waitForTimeout(150);
          await page.evaluate(() => document.getElementById('out').scrollIntoView());
          await page.screenshot({ path: path.join(OUT, `${st.id}-${tag}-expanded.png`), fullPage: true });
          report.runs.push({ state: st.id + '-expanded', theme, w, ...(await audit(page)), errors: [...errors] });
        }
        await fixture(page, 'normal');
      }
      await ctx.close();
    }
  }
  // 200% text and 400% zoom equivalent (320 CSS px), plus error and OCR paths at 390
  const ctx = await browser.newContext({ viewport: { width: 390, height: 844 }, reducedMotion: 'reduce' });
  const page = await ctx.newPage();
  await page.goto(BASE + '/');
  await page.addStyleTag({ content: 'html{font-size:200% !important}' });
  await page.fill('#t', textFor('ALERTĂ BCR')); await page.click('#go');
  await page.waitForFunction(() => !document.getElementById('out').hidden && document.getElementById('out').getAttribute('aria-busy') !== 'true');
  await page.screenshot({ path: path.join(OUT, `text200-critical-390.png`) });
  report.runs.push({ state: 'text200-critical', w: 390, ...(await audit(page)) });
  for (const mode of ['server_error', 'ocr_fail']) {
    await page.goto(BASE + '/'); await fixture(page, mode);
    const text = textFor('DPD:');
    await page.fill('#t', text);
    if (mode === 'server_error') { await page.click('#go'); }
    else { const [chooser] = await Promise.all([page.waitForEvent('filechooser'), page.click('#up')]); await chooser.setFiles({ name: 'x.png', mimeType: 'image/png', buffer: Buffer.from('89504e470d0a1a0a0000', 'hex') }); }
    await page.waitForTimeout(800);
    const kept = await page.inputValue('#t');
    await page.screenshot({ path: path.join(OUT, `error-${mode}-390.png`) });
    const err = await page.evaluate(() => { const e = document.querySelector('#err, [data-role="error"]'); return e ? { text: e.textContent.trim(), role: e.getAttribute('role'), focused: document.activeElement && (document.activeElement.id || document.activeElement.tagName) } : null; });
    report.runs.push({ state: 'error-' + mode, w: 390, inputPreserved: kept === text, err });
    await fixture(page, 'normal');
  }
  // OCR success path
  await page.goto(BASE + '/');
  { const [chooser] = await Promise.all([page.waitForEvent('filechooser'), page.click('#up')]); await chooser.setFiles({ name: 'x.png', mimeType: 'image/png', buffer: Buffer.from('89504e470d0a1a0a0000', 'hex') }); }
  await page.waitForFunction(() => !document.getElementById('out').hidden, null, { timeout: 10000 }).catch(() => {});
  await page.evaluate(() => scrollTo(0, 0)); await page.screenshot({ path: path.join(OUT, `ocr-done-390.png`) });
  report.runs.push({ state: 'ocr-done', w: 390, ...(await audit(page)) });
  // keyboard journey: tab order from top to the submit button, then to first evidence
  await page.goto(BASE + '/');
  const order = [];
  for (let i = 0; i < 16; i++) { await page.keyboard.press('Tab'); order.push(await page.evaluate(() => { const a = document.activeElement; return (a.id || a.getAttribute('data-role') || a.tagName) + (a.textContent ? ':' + a.textContent.trim().slice(0, 18) : ''); })); }
  report.keyboard = order;
  // motion: with motion allowed, count infinite animations while busy
  const ctx2 = await browser.newContext({ viewport: { width: 1440, height: 900 }, reducedMotion: 'no-preference' });
  const p2 = await ctx2.newPage(); await p2.goto(BASE + '/'); await fixture(p2, 'slow');
  await p2.fill('#t', textFor('DPD:')); await p2.click('#go'); await p2.waitForTimeout(600);
  report.motionWhileBusy = await p2.evaluate(() => [...document.querySelectorAll('*')].filter(e => getComputedStyle(e).animationIterationCount === 'infinite').map(e => e.id || e.className).slice(0, 5));
  await p2.screenshot({ path: path.join(OUT, `busy-1440.png`) });
  await p2.waitForTimeout(2500); await fixture(p2, 'normal');
  await browser.close();
  fs.writeFileSync(path.join(OUT, 'report.json'), JSON.stringify(report, null, 1));
  const sum = report.runs.reduce((acc, r) => { acc.overflow += r.overflowX > 0 ? 1 : 0; acc.lowContrast += r.lowContrastCount || 0; acc.small += r.smallTextCount || 0; acc.unnamed += (r.unnamed || []).length; acc.errors += (r.errors || []).length; acc.infinite += r.infiniteAnimations || 0; return acc; }, { overflow: 0, lowContrast: 0, small: 0, unnamed: 0, errors: 0, infinite: 0 });
  console.log(JSON.stringify({ runs: report.runs.length, ...sum, motionWhileBusy: report.motionWhileBusy }));
})();
