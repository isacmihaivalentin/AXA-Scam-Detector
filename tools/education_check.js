// TEST-ONLY checks for /education (AXA for Education preview) and the shared header, against
// tools/ui_fixture_server.py. Reuses the measured audit of tools/ui_check.js.
// Usage: NODE_PATH=$(npm root -g) node tools/education_check.js <out-dir> [base-url]
const fs = require('fs');
const path = require('path');
const { chromium } = require('playwright');
const OUT = process.argv[2] || '/tmp/edu-shots';
const BASE = process.argv[3] || 'http://localhost:8765';
fs.mkdirSync(OUT, { recursive: true });
const src = fs.readFileSync(path.join(__dirname, 'ui_check.js'), 'utf8');
// eslint-disable-next-line no-eval
const audit = eval('(' + src.slice(src.indexOf('async function audit'), src.indexOf('async function firstScreenFacts')) + ')');
const res = { runs: [], checks: {} };
const ok = (name, cond, detail) => { res.checks[name] = cond ? 'PASS' : 'FAIL ' + JSON.stringify(detail === undefined ? '' : detail); };

(async () => {
  const browser = await chromium.launch();
  const open = async (o) => {
    const ctx = await browser.newContext(Object.assign({ reducedMotion: 'reduce' }, o));
    const page = await ctx.newPage();
    const api = [], errors = [];
    page.on('request', r => { if (/\/api\//.test(r.url()) || !r.url().startsWith(BASE)) api.push(r.url()); });
    page.on('pageerror', e => errors.push(e.message));
    page.on('console', m => { if (m.type() === 'error') errors.push(m.text()); });
    return { ctx, page, api, errors };
  };

  // ---- viewport sweep
  const sizes = [[1440, 900], [1280, 800], [1024, 768], [768, 1024], [430, 932], [390, 844], [375, 667], [360, 740], [320, 640]];
  for (const scheme of ['light', 'dark']) {
    for (const [w, h] of sizes) {
      if (scheme === 'dark' && ![1440, 768, 390, 320].includes(w)) continue;
      const { ctx, page, api, errors } = await open({ viewport: { width: w, height: h }, colorScheme: scheme });
      await page.goto(BASE + '/education'); await page.waitForTimeout(300);
      const first = await page.evaluate(() => {
        const y = s => { const e = document.querySelector(s); return e ? Math.round(e.getBoundingClientRect().top) : null; };
        return { header: Math.round(document.querySelector('.top').getBoundingClientRect().height), soon: y('.soon'), h1: y('#edu-h'), lab: y('#previzualizare'), tabs: y('.lab-tabs'), specimen: y('#panel-f .specimen'), page: document.documentElement.scrollHeight };
      });
      await page.screenshot({ path: path.join(OUT, `edu-${scheme}-${w}.png`) });
      for (const t of ['f', 'd']) {
        await page.click('#tab-' + t); await page.waitForTimeout(120);
        res.runs.push({ page: '/education', track: t, scheme, w, first, ...(await audit(page)), errors: [...errors], api: [...api] });
      }
      if (w === 390 || w === 1440) await page.screenshot({ path: path.join(OUT, `edu-${scheme}-${w}-full.png`), fullPage: true });
      await ctx.close();
    }
  }
  // 200% text and the largest A+ step on a phone
  for (const mode of ['200%', 'A+max']) {
    const { ctx, page } = await open({ viewport: { width: 390, height: 844 } });
    await page.goto(BASE + '/education');
    if (mode === '200%') await page.addStyleTag({ content: 'html{font-size:200%!important}' });
    else { await page.click('#disp'); for (let i = 0; i < 4; i++) await page.click('#fp'); await page.click('#disp'); }
    await page.waitForTimeout(150);
    for (const t of ['f', 'd']) { await page.click('#tab-' + t); res.runs.push({ page: '/education', track: t, scheme: 'light', w: 390, mode, ...(await audit(page)), errors: [] }); }
    await page.screenshot({ path: path.join(OUT, `edu-text-${mode.replace('%', 'pct').replace('+', 'plus')}-390.png`), fullPage: true });
    await page.evaluate(() => localStorage.removeItem('axa_zoom'));
    await ctx.close();
  }

  // ---- behaviour
  let { ctx, page, api } = await open({ viewport: { width: 390, height: 844 } });
  await page.goto(BASE + '/education'); await page.waitForTimeout(200);
  const state = () => page.evaluate(() => ({
    sel: [...document.querySelectorAll('[role=tab]')].map(t => t.getAttribute('aria-selected')),
    fHidden: document.getElementById('panel-f').hidden, dHidden: document.getElementById('panel-d').hidden,
    fOn: document.querySelectorAll('#panel-f .cue.on').length, dOn: document.querySelectorAll('#panel-d .cue.on').length,
    dShown: document.querySelectorAll('#panel-d .notes-edu li.shown').length, focus: document.activeElement.id }));
  let s = await state();
  ok('reduced motion: fraud lesson fully visible at once', s.fOn === 3 && !s.fHidden && s.dHidden && s.sel.join() === 'true,false', s);
  await page.click('#tab-d'); s = await state();
  ok('tab switch: misinformation track active, fraud track reset', s.sel.join() === 'false,true' && s.fHidden && !s.dHidden && s.fOn === 0 && s.dOn === 3 && s.dShown === 4, s);
  await page.focus('#tab-d'); await page.keyboard.press('ArrowLeft'); s = await state();
  ok('keyboard: ArrowLeft selects and focuses the fraud tab', s.sel.join() === 'true,false' && s.focus === 'tab-f', s);
  await page.keyboard.press('End'); s = await state();
  ok('keyboard: End selects the last tab', s.sel.join() === 'false,true' && s.focus === 'tab-d', s);
  await page.keyboard.press('Tab');
  ok('keyboard: Tab moves from the tab list into the active panel', await page.evaluate(() => document.activeElement.id) === 'panel-d');
  // menu (narrow header)
  await page.click('#disp');
  const menu = await page.evaluate(() => ({ exp: document.getElementById('disp').getAttribute('aria-expanded'), links: [...document.querySelectorAll('.menu-links a')].filter(a => a.offsetParent).map(a => a.textContent), current: document.querySelector('.menu-links a[aria-current=page]').textContent, name: document.getElementById('disp').innerText.trim() }));
  ok('mobile menu opens with the four links, current page marked', menu.exp === 'true' && menu.links.length === 4 && menu.current === 'AXA for Education' && menu.name === 'Meniu', menu);
  await page.keyboard.press('Escape');
  ok('Escape closes the menu and returns focus', await page.evaluate(() => document.getElementById('disp-panel').hidden && document.activeElement.id === 'disp'));
  await page.click('#disp'); await page.click('input[name=theme][value=dark]');
  ok('Afișare: theme works on /education', await page.evaluate(() => document.documentElement.dataset.theme) === 'dark');
  ok('/education (load, tabs, menu, theme) made no API or third-party requests', api.length === 0, api);
  await page.click('.menu-links a[href="/#semne"]'); await page.waitForURL('**/#semne');
  ok('menu link goes to /#semne with the theme preference kept', await page.evaluate(() => location.pathname + location.hash + ' ' + document.documentElement.dataset.theme) === '/#semne dark');
  await ctx.close();

  // motion allowed: the lesson plays once, then everything stays visible; replay works
  ({ ctx, page } = await open({ viewport: { width: 1440, height: 900 }, reducedMotion: 'no-preference' }));
  await page.goto(BASE + '/education'); await page.waitForTimeout(700);
  const mid = await page.evaluate(() => ({ playing: document.getElementById('previzualizare').classList.contains('playing'), shown: document.querySelectorAll('#panel-f .notes-edu li.shown').length }));
  await page.waitForTimeout(4200);
  const end = await page.evaluate(() => ({ playing: document.getElementById('previzualizare').classList.contains('playing'), shown: document.querySelectorAll('#panel-f .notes-edu li.shown').length, on: document.querySelectorAll('#panel-f .cue.on').length }));
  ok('motion: lesson plays step by step, once, and ends fully visible in under 5 s', mid.playing && mid.shown < 3 && !end.playing && end.shown === 3 && end.on === 3, { mid, end });
  await page.screenshot({ path: path.join(OUT, 'edu-motion-mid.png') });
  await page.click('#replay'); await page.waitForTimeout(500);
  const rp = await page.evaluate(() => ({ playing: document.getElementById('previzualizare').classList.contains('playing'), shown: document.querySelectorAll('#panel-f .notes-edu li.shown').length }));
  ok('replay restarts the lesson', rp.playing && rp.shown < 3, rp);
  await page.click('#tab-d'); await page.waitForTimeout(300);
  const sw = await page.evaluate(() => ({ fOn: document.querySelectorAll('#panel-f .on,#panel-f .shown').length, playing: document.getElementById('previzualizare').classList.contains('playing') }));
  ok('switching mid-lesson resets the other track and restarts cleanly', sw.fOn === 0 && sw.playing, sw);
  await ctx.close();

  // no JavaScript: a complete static preview
  ({ ctx, page } = await open({ viewport: { width: 390, height: 844 }, javaScriptEnabled: false }));
  await page.goto(BASE + '/education');
  const nojs = await page.evaluate(() => ({ tabsShown: !!document.querySelector('.lab-tabs').offsetParent, panels: [...document.querySelectorAll('.lab-panel')].filter(p => p.offsetParent).length, notes: [...document.querySelectorAll('.notes-edu li')].filter(l => getComputedStyle(l).opacity === '1').length }));
  ok('no JS: both lessons and all 7 explanations visible, no inert tabs', !nojs.tabsShown && nojs.panels === 2 && nojs.notes === 7, nojs);
  await page.screenshot({ path: path.join(OUT, 'edu-nojs-390.png'), fullPage: true });
  await ctx.close();

  // navigation smoke tests from the main page
  ({ ctx, page } = await open({ viewport: { width: 1440, height: 900 } }));
  await page.goto(BASE + '/');
  await page.click('.nav a[href="/education"]'); await page.waitForURL('**/education');
  ok('/ → nav "AXA for Education" → /education', page.url().endsWith('/education') && await page.evaluate(() => document.querySelector('.nav a[aria-current=page]').textContent) === 'AXA for Education');
  await page.reload(); ok('direct refresh of /education works', (await page.title()).includes('AXA for Education'));
  await page.click('.logo'); await page.waitForURL(u => new URL(u).pathname === '/');
  ok('logo returns to /', new URL(page.url()).pathname === '/');
  await page.goto(BASE + '/education'); await page.click('.nav a[href="/#confidentialitate"]'); await page.waitForURL('**/#confidentialitate');
  ok('nav "Confidențialitate" from /education lands on /#confidentialitate', await page.evaluate(() => Math.abs(document.getElementById('confidentialitate').getBoundingClientRect().top) < 120));
  await page.goto(BASE + '/education'); await page.click('.help-link'); await page.waitForURL('**/#ajutor');
  ok('"Am pățit deja ceva" from /education lands on /#ajutor', true);
  await page.goto(BASE + '/education'); await page.click('.close-ctas .btn-cta'); await page.waitForURL('**/#verifica');
  ok('closing CTA goes to /#verifica', await page.evaluate(() => !!document.getElementById('t')));
  await page.goto(BASE + '/');
  for (const [href, id] of [['#verifica', 'verifica'], ['#semne', 'semne'], ['#confidentialitate', 'confidentialitate']]) {
    await page.click(`.nav a[href="${href}"]`); await page.waitForTimeout(150);
    ok(`main page anchor ${href} still works`, await page.evaluate(i => location.hash === '#' + i, id));
  }
  await page.click('#disp');
  ok('main page: Afișare still opens display settings at desktop width', await page.evaluate(() => !document.getElementById('disp-panel').hidden && !!document.getElementById('fp').offsetParent && document.getElementById('disp').innerText.trim() === 'Afișare'));
  await ctx.close();
  // main page header at phone/tablet widths
  for (const w of [320, 360, 375, 390, 430, 768, 1024, 1120, 1280]) {
    ({ ctx, page } = await open({ viewport: { width: w, height: 800 } }));
    await page.goto(BASE + '/');
    const hdr = await page.evaluate(() => ({ h: Math.round(document.querySelector('.top').getBoundingClientRect().height), ovf: document.documentElement.scrollWidth - innerWidth, inline: getComputedStyle(document.querySelector('.nav')).display !== 'none' }));
    await page.click('#disp');
    const links = await page.evaluate(() => [...document.querySelectorAll('.menu-links a')].filter(a => a.offsetParent).length);
    res.checks[`main header ${w}px`] = (hdr.h <= 70 && hdr.ovf === 0 && (hdr.inline ? links === 0 : links === 4)) ? 'PASS' : 'FAIL ' + JSON.stringify({ hdr, links });
    if (!hdr.inline) {
      await page.click('.menu-links a[href="#semne"]'); await page.waitForTimeout(150);
      if (!(await page.evaluate(() => document.getElementById('disp-panel').hidden && location.hash === '#semne'))) res.checks[`main menu link ${w}px`] = 'FAIL';
    }
    await page.screenshot({ path: path.join(OUT, `main-header-${w}.png`), clip: { x: 0, y: 0, width: w, height: 420 } });
    await ctx.close();
  }
  await browser.close();
  fs.writeFileSync(path.join(OUT, 'report.json'), JSON.stringify(res, null, 1));
  const bad = res.runs.filter(r => r.overflowX > 0 || r.lowContrastCount || r.smallTextCount || (r.unnamed || []).length || r.headingSkips || (r.errors || []).length || (r.api || []).length);
  console.log(JSON.stringify({ runs: res.runs.length, problems: bad.map(r => ({ t: r.track, s: r.scheme, w: r.w, m: r.mode, o: r.overflowX, lc: r.lowContrast, st: r.smallText, un: r.unnamed, hs: r.headingSkips, e: r.errors, api: r.api })), checks: res.checks,
    firstScreens: res.runs.filter(r => r.first && r.track === 'f').map(r => `${r.scheme} ${r.w}: header ${r.first.header} soon ${r.first.soon} lab ${r.first.lab} tabs ${r.first.tabs} specimen ${r.first.specimen} page ${r.first.page}`) }, null, 1));
})();
