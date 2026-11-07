// TEST-ONLY: GDPR consent gate on / and /chat, against tools/ui_fixture_server.py.
// Verifies that nothing reaches /api/analyze* before an explicit "da", that refusal stops everything,
// and that consent can be withdrawn. Usage: NODE_PATH=$(npm root -g) node tools/consent_check.js <out-dir>
const fs = require('fs');
const path = require('path');
const { chromium } = require('playwright');
const OUT = process.argv[2] || '/tmp/consent-shots';
const BASE = process.argv[3] || 'http://localhost:8765';
fs.mkdirSync(OUT, { recursive: true });
const PNG = Buffer.from('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8DwHwAFBQIAX8jx0gAAAABJRU5ErkJggg==', 'base64');
const results = {};
const ok = (name, cond, detail) => { results[name] = cond ? 'PASS' : 'FAIL ' + JSON.stringify(detail === undefined ? '' : detail); };

(async () => {
  const browser = await chromium.launch();
  await fetch(BASE + '/__fixture', { method: 'POST', body: JSON.stringify({ mode: 'normal' }) });
  const fresh = async (opts) => {
    const ctx = await browser.newContext(Object.assign({ viewport: { width: 390, height: 844 }, reducedMotion: 'reduce' }, opts || {}));
    const page = await ctx.newPage();
    const sent = [];
    page.on('request', r => { if (r.url().includes('/api/analyze')) sent.push(r.url()); });
    return { ctx, page, sent };
  };
  const consent = p => p.evaluate(() => localStorage.getItem('axa_consent_v1'));

  // ---- main page
  let { ctx, page, sent } = await fresh();
  await page.goto(BASE + '/');
  await page.fill('#t', 'Mesaj de test: trimite codul primit prin SMS.');
  await page.click('#go');
  await page.waitForSelector('#consent[open]');
  ok('main: dialog opens before any request', sent.length === 0, sent);
  ok('main: focus starts on the dialog heading', await page.evaluate(() => document.activeElement.id) === 'cs-h');
  await page.screenshot({ path: path.join(OUT, 'consent-main-light-390.png') });
  await page.click('#consent button[value="no"]');
  await page.waitForTimeout(200);
  ok('main: refusal sends nothing', sent.length === 0, sent);
  ok('main: refusal explains and keeps the text', (await page.textContent('#err')).includes('nu am trimis nimic') && (await page.inputValue('#t')).startsWith('Mesaj de test'));
  ok('main: refusal is not stored', (await consent(page)) === null);
  await page.click('#go'); await page.waitForSelector('#consent[open]'); await page.keyboard.press('Escape'); await page.waitForTimeout(150);
  ok('main: Escape counts as refusal', sent.length === 0 && !(await page.isVisible('#consent')));
  await page.click('#go'); await page.waitForSelector('#consent[open]'); await page.click('#consent-info'); await page.waitForTimeout(400);
  ok('main: "read first" sends nothing and goes to the GDPR section', sent.length === 0 && await page.evaluate(() => document.activeElement.id) === 'gdpr-h');
  await page.setInputFiles('#file', { name: 'c.png', mimeType: 'image/png', buffer: PNG });
  await page.waitForSelector('#consent[open]'); await page.click('#consent button[value="no"]'); await page.waitForTimeout(150);
  ok('main: screenshot refused sends nothing', sent.length === 0, sent);
  await page.click('#go'); await page.waitForSelector('#consent[open]'); await page.click('#consent button[value="yes"]');
  await page.waitForSelector('#res-h');
  ok('main: agreement continues the check', sent.length === 1, sent);
  ok('main: agreement is recorded with a timestamp', JSON.parse(await consent(page) || '{}').granted === true);
  await page.click('#nw'); await page.fill('#t', 'Alt mesaj de test.'); await page.click('#go'); await page.waitForTimeout(600);
  ok('main: no second prompt after agreement', !(await page.isVisible('#consent')) && sent.length === 2, sent);
  await page.evaluate(() => document.getElementById('gdpr').scrollIntoView());
  ok('main: GDPR section shows the consent state', (await page.textContent('#gdpr-state')).includes('Ți-ai dat acordul'));
  await page.screenshot({ path: path.join(OUT, 'gdpr-section-light-390.png') });
  await page.click('#gdpr-revoke');
  ok('main: withdrawal clears the record', (await consent(page)) === null && (await page.textContent('#gdpr-state')).includes('Nu ți-ai dat acordul'));
  await page.click('#go'); await page.waitForTimeout(200);
  ok('main: after withdrawal the dialog returns', await page.isVisible('#consent'));
  await page.keyboard.press('Escape');
  await ctx.close();

  // ---- chat page
  ({ ctx, page, sent } = await fresh());
  await page.goto(BASE + '/chat');
  await page.fill('#msg', 'Mesaj de test din chat.'); await page.click('#send');
  await page.waitForSelector('#consent[open]');
  await page.screenshot({ path: path.join(OUT, 'consent-chat-light-390.png') });
  await page.click('#consent button[value="no"]'); await page.waitForTimeout(200);
  ok('chat: refusal sends nothing and adds no user bubble', sent.length === 0 && (await page.$$('.b-out')).length === 0, sent);
  ok('chat: refusal keeps the text in the composer', (await page.inputValue('#msg')) === 'Mesaj de test din chat.');
  await page.screenshot({ path: path.join(OUT, 'consent-chat-refused-light-390.png') });
  await page.locator('.chip', { hasText: 'M-am răzgândit' }).click();
  await page.waitForSelector('#consent[open]'); await page.click('#consent button[value="yes"]');
  await page.waitForSelector('.verdict');
  ok('chat: agreement continues the check', sent.length === 1, sent);
  await page.goto(BASE + '/');
  await page.fill('#t', 'Test comun.'); await page.click('#go'); await page.waitForTimeout(600);
  ok('shared: consent from the chat applies on the main page', !(await page.isVisible('#consent')) && sent.length === 2, sent);
  await ctx.close();

  // ---- dark + desktop renders of the dialog
  for (const [w, h, scheme] of [[1440, 900, 'light'], [1440, 900, 'dark'], [390, 844, 'dark']]) {
    ({ ctx, page } = await fresh({ viewport: { width: w, height: h }, colorScheme: scheme }));
    await page.goto(BASE + '/'); await page.fill('#t', 'x'); await page.click('#go'); await page.waitForSelector('#consent[open]');
    await page.screenshot({ path: path.join(OUT, `consent-main-${scheme}-${w}.png`) });
    await ctx.close();
  }
  await browser.close();
  fs.writeFileSync(path.join(OUT, 'report.json'), JSON.stringify(results, null, 1));
  console.log(JSON.stringify(results, null, 1));
})();
