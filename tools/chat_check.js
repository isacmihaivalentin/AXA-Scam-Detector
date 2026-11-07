// TEST-ONLY sweep for the "AXA în chat" concept page (/chat), against tools/ui_fixture_server.py
// (real pipeline, MOCK Gemini readings). Reuses the measured checks of tools/ui_check.js.
// Usage: NODE_PATH=$(npm root -g) node tools/chat_check.js <out-dir> [base-url]
const fs = require('fs');
const path = require('path');
const { chromium } = require('playwright');

const OUT = process.argv[2] || '/tmp/chat-shots';
const BASE = process.argv[3] || 'http://localhost:8765';
fs.mkdirSync(OUT, { recursive: true });
const src = fs.readFileSync(path.join(__dirname, 'ui_check.js'), 'utf8');
// eslint-disable-next-line no-eval
const audit = eval('(' + src.slice(src.indexOf('async function audit'), src.indexOf('async function firstScreenFacts')) + ')');

const STATES = [
  { id: 'critical', key: 'ALERTĂ BCR', zone: 'strong', chips: ['De ce?', 'Ce e cu linkul?', 'Am apăsat deja / am trimis date'] },
  { id: 'suspicious', key: 'DPD: Livrarea', zone: 'suspect', chips: ['Ce ai verificat?', 'Cum ar continua?'] },
  { id: 'benign', key: 'Te asteptam in Cargus', zone: 'clear', chips: ['Ce e cu linkul?', 'Detalii tehnice'] },
  { id: 'inconclusive', key: 'Nu trimite parola', zone: null, chips: ['De ce?'] },
  { id: 'ai_off', key: 'Te asteptam in Cargus', mode: 'ai_not_configured', zone: null, chips: ['Ce ai verificat?'] },
  { id: 'ai_timeout', key: 'ALERTĂ BCR', mode: 'ai_timeout', zone: 'strong', chips: [] },
];

(async () => {
  const browser = await chromium.launch();
  // The sweep measures the interface after the GDPR consent was given; consent itself is covered by tools/consent_check.js.
  const newContext = browser.newContext.bind(browser);
  browser.newContext = async opts => {
    const c = await newContext(opts);
    await c.addInitScript(() => { try { localStorage.setItem('axa_consent_v1', JSON.stringify({ granted: true, at: '2026-01-01T00:00:00Z', version: 1 })); } catch (e) { /* ignore */ } });
    return c;
  };
  const fx = await (await fetch(BASE + '/__fixtures')).json();
  const textFor = k => fx.texts.find(t => t.startsWith(k));
  const setMode = m => fetch(BASE + '/__fixture', { method: 'POST', body: JSON.stringify({ mode: m || 'normal' }) });
  const report = { note: 'MOCK Gemini readings; deterministic layers real.', runs: [], checks: {} };
  for (const theme of ['light', 'dark']) {
    for (const [w, h] of (theme === 'light' ? [[320, 640], [390, 844], [768, 1000], [1440, 900]] : [[390, 844], [1440, 900]])) {
      const ctx = await browser.newContext({ viewport: { width: w, height: h }, colorScheme: theme, reducedMotion: 'reduce' });
      const page = await ctx.newPage();
      const errors = []; page.on('pageerror', e => errors.push(e.message));
      const tag = `${theme}-${w}`;
      await setMode('normal');
      await page.goto(BASE + '/chat'); await page.waitForTimeout(300);
      await page.screenshot({ path: path.join(OUT, `chat-home-${tag}.png`) });
      report.runs.push({ state: 'home', theme, w, ...(await audit(page)), errors: [...errors] });
      const states = (w === 390 && theme === 'light') || (w === 1440 && theme === 'light') ? STATES : STATES.slice(0, 4);
      for (const st of states) {
        await setMode(st.mode);
        await page.click('#reset');
        await page.fill('#msg', textFor(st.key));
        await page.click('#send');
        await page.waitForSelector('.verdict', { timeout: 15000 });
        await page.waitForTimeout(200);
        const facts = await page.evaluate(() => {
          const s = document.querySelector('.verdict [data-role="spectrum"]');
          return { status: s && s.dataset.status, position: s && s.dataset.position || null, marker: !!(s && s.querySelector('.sp-marker')),
            lamps: [...document.querySelectorAll('.verdict .lights i.on')].map(i => i.className), action: !!document.querySelector('.act .a'),
            title: document.querySelector('.v-title').textContent };
        });
        await page.screenshot({ path: path.join(OUT, `chat-${st.id}-${tag}.png`) });
        for (const c of st.chips) {
          const b = page.locator('#chips .chip', { hasText: c }).first();
          if (await b.count()) { await b.click(); await page.waitForTimeout(150); }
          if (c.startsWith('Am apăsat')) { await page.locator('.pick').first().click(); await page.waitForTimeout(150); }
        }
        if (st.chips.length) await page.screenshot({ path: path.join(OUT, `chat-${st.id}-${tag}-asked.png`) });
        report.runs.push({ state: st.id, theme, w, facts, ...(await audit(page)), errors: [...errors] });
        if (st.zone === null && facts.lamps.length) report.checks['lamp_lit_without_estimate_' + st.id] = facts;
        if (st.zone && !facts.lamps.join(' ').includes({ clear: 'l-g', suspect: 'l-a', strong: 'l-r' }[st.zone])) report.checks['wrong_lamp_' + st.id] = facts;
      }
      await setMode('normal');
      await ctx.close();
    }
  }
  // error + retry keeps the text
  const ctx = await browser.newContext({ viewport: { width: 390, height: 844 }, reducedMotion: 'reduce' });
  const page = await ctx.newPage();
  await page.goto(BASE + '/chat');
  await setMode('server_error');
  await page.fill('#msg', 'text scris de mine'); await page.click('#send');
  await page.waitForSelector('.fail');
  report.checks.errorKeepsText = await page.inputValue('#msg');
  await page.screenshot({ path: path.join(OUT, 'chat-error-light-390.png') });
  await setMode('normal');
  await page.locator('#chips .chip', { hasText: 'Încearcă din nou' }).click();
  await page.waitForSelector('.verdict');
  report.checks.retryWorks = true;
  // keyboard: Enter sends (fine pointer), focus lands on the verdict
  await page.click('#reset'); await page.fill('#msg', textFor('DPD: Livrarea')); await page.press('#msg', 'Enter');
  await page.waitForSelector('.verdict'); await page.waitForTimeout(100);
  report.checks.focusAfterResult = await page.evaluate(() => !!document.activeElement.querySelector('.verdict'));
  report.checks.noStorageOfText = await page.evaluate(() => Object.keys(localStorage).filter(k => (localStorage.getItem(k) || '').includes('DPD')));
  await setMode('normal');
  await ctx.close();
  // motion on: marker glides
  const mctx = await browser.newContext({ viewport: { width: 390, height: 844 }, reducedMotion: 'no-preference' });
  const mp = await mctx.newPage();
  await mp.goto(BASE + '/chat'); await mp.fill('#msg', textFor('ALERTĂ BCR')); await mp.click('#send');
  await mp.waitForSelector('.sp-run');
  const x = () => mp.evaluate(() => new DOMMatrix(getComputedStyle(document.querySelector('.sp-run')).transform).m41);
  const early = await x(); await mp.waitForTimeout(900); const late = await x();
  report.checks.markerGlide = { early: Math.round(early), late: Math.round(late) };
  await mctx.close();
  await browser.close();
  fs.writeFileSync(path.join(OUT, 'report.json'), JSON.stringify(report, null, 1));
  const bad = report.runs.filter(r => r.overflowX > 0 || r.lowContrastCount || r.smallTextCount || r.unnamed.length || r.headingSkips || r.errors.length);
  console.log(JSON.stringify({ runs: report.runs.length, problems: bad.map(r => ({ s: r.state, t: r.theme, w: r.w, o: r.overflowX, lc: r.lowContrast, st: r.smallText, un: r.unnamed, e: r.errors })), checks: report.checks }, null, 1));
})();
