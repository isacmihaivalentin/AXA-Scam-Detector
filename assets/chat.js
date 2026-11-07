/* AXA în chat — messaging-style concept (additive page; the main interface is untouched).
   Uses the same endpoints and the same analysis data as the main page. The backend decides;
   this file only presents. Every server or user string goes through esc(). Submitted links are
   never clickable. No message text is stored. The semaphore and the scale are drawn only from
   analysis.ui.spectrum: nothing is lit or placed that the backend did not estimate. */
(function () {
'use strict';
const $ = id => document.getElementById(id);
const esc = s => String(s == null ? '' : s).replace(/[&<>"']/g, m => ({'&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'}[m]));
const reduce = () => matchMedia('(prefers-reduced-motion: reduce)').matches;
const read = (k, d) => { try { const v = localStorage.getItem(k); return v ? JSON.parse(v) : d; } catch (e) { return d; } };

const EXAMPLES = [
  ['Colet', 'SAMEDAY: Coletul dvs. RO492819 nu a putut fi livrat din cauza unei adrese incomplete. Actualizați datele în maxim 24 de ore pentru a evita returnarea și plata unei taxe de depozitare: https://sameday-livrare-ro.example/tracking'],
  ['Bancă', 'ALERTĂ BCR: Stimate client, contul dvs. a fost suspendat în urma unei tranzacții suspecte. Pentru deblocare imediată validați identitatea și introduceți datele cardului aici: http://bcr-verifica-cont.example/login'],
  ['Vânzare online', 'Bună! Am văzut anunțul tău și am achitat deja produsul. Intră pe linkul generat de curier ca să îți introduci datele cardului și codul CVV pentru a încasa banii imediat: https://o1x-plata-sigura.example/incasare'],
  ['Rudă în necaz', 'Salut mami, mi-am schimbat numărul, telefonul meu s-a stricat. Te rog urgent să faci un transfer de 2.300 lei în contul pe care ți-l dau acum, că am o problemă. Nu spune nimănui, îți explic mai târziu.'],
  ['Notificare obișnuită', 'Salut! Comanda ta eMAG #4029182 a fost predată curierului și va fi livrată astăzi. Poți vedea statusul în aplicația ta sau pe https://www.emag.ro.']
];
const PILL = {strong: 'Alertă', suspect: 'Atenție', no_clear_signs: 'Rezultat', unable: 'Fără verdict'};
const TITLES = {strong: 'Indicii puternice de tentativă de fraudă', suspect: 'Mesaj suspect', no_clear_signs: 'Nu am găsit indicii clare de fraudă', unable: 'Nu putem evalua suficient mesajul'};
const STATE_OF = {critical: 'strong', suspicious: 'suspect', low: 'no_clear_signs', marketing: 'no_clear_signs', protective: 'no_clear_signs', inconclusive: 'unable'};
const KIND = {alarm: 'Îngrijorător', attention: 'De reținut', note: 'Informativ', protective: 'Protector'};
const SOURCE = {gemini: 'interpretare AI', rules: 'reguli locale', static_url: 'analiza linkului', catalog: 'catalogul de domenii', google_web_risk: 'Google Web Risk', policy: 'politica AXA'};
const STATUS = {supported: 'susținut de text', tentative: 'neconfirmat în text', contradicted: 'contrazis de text', context: 'context', corroborating: 'confirmă'};
const CONF = {high: 'mare', medium: 'medie', low: 'mică'};
const AI_FAIL = {not_configured: 'nu este configurată pe server', busy: 'serverul era ocupat', timeout: 'nu a răspuns la timp', rate_limited: 's-a atins limita de cereri', authentication_or_access: 'cheia de acces a fost respinsă', model_unavailable: 'modelul nu este disponibil', invalid_output: 'răspunsul nu a putut fi citit', invalid_request: 'cererea a fost respinsă', blocked: 'răspunsul a fost blocat de furnizor', provider_unavailable: 'furnizorul nu este disponibil', failed: 'nu a răspuns'};
const URL_WORD = {official: 'în lista domeniilor oficiale', deceptive: 'structură înșelătoare', third: 'domeniul altei companii', unknown: 'necunoscut nouă', invalid: 'adresă care nu poate fi citită'};
const ICON = {
  bad: '<svg viewBox="0 0 20 20" aria-hidden="true"><path d="M10 2 19 18H1z" fill="currentColor"/></svg>',
  warn: '<svg viewBox="0 0 20 20" aria-hidden="true"><circle cx="10" cy="10" r="8" fill="none" stroke="currentColor" stroke-width="2.5"/><path d="M10 5.5v5.5" stroke="currentColor" stroke-width="2.5" stroke-linecap="round"/><circle cx="10" cy="14.5" r="1.4" fill="currentColor"/></svg>',
  ok: '<svg viewBox="0 0 20 20" aria-hidden="true"><path d="M4 10.5l4 4 8-9" fill="none" stroke="currentColor" stroke-width="2.6" stroke-linecap="round" stroke-linejoin="round"/></svg>',
  unk: '<svg viewBox="0 0 20 20" aria-hidden="true"><circle cx="10" cy="10" r="8" fill="none" stroke="currentColor" stroke-width="2" stroke-dasharray="3 2.5"/></svg>',
  ai: '<svg viewBox="0 0 20 20" aria-hidden="true"><path d="M3 4h14v9H8l-4 3v-3H3z" fill="none" stroke="currentColor" stroke-width="2" stroke-linejoin="round"/></svg>',
  tech: '<svg viewBox="0 0 20 20" aria-hidden="true"><path d="M3 5h14M3 10h14M3 15h9" stroke="currentColor" stroke-width="2" stroke-linecap="round"/></svg>'
};
const TICK1 = '<svg class="ticks" viewBox="0 0 18 12" aria-hidden="true"><path d="M2 6.5l3.5 3.5L13 2.5" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"/></svg>';
const TICK2 = '<svg class="ticks read" viewBox="0 0 18 12" aria-hidden="true"><path d="M1 6.5l3.5 3.5L12 2.5M7.5 9.5l.5.5L15.5 2.5" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"/></svg>';

let busy = false, ctl = null, aiOn = null, cur = null, asked = new Set(), seq = 0, recovery = null;
const wall = $('wall'), log = $('log');

/* ---------------------------------------------------------------- display preferences shared with the main page (read only) */
(function prefs() {
  const t = read('axa_theme', 'auto');
  if (t === 'light' || t === 'dark') document.documentElement.dataset.theme = t;
  const Z = [100, 112.5, 125, 140, 160], z = Math.max(0, Math.min(4, read('axa_zoom', 0)));
  document.documentElement.style.fontSize = Z[z] + '%';
})();

/* ---------------------------------------------------------------- recovery steps: read from the main page so both stay identical */
function loadRecovery() {
  return fetch('/').then(r => r.ok ? r.text() : Promise.reject()).then(html => {
    const doc = new DOMParser().parseFromString(html, 'text/html');  // parsed only; no script runs
    const box = doc.getElementById('recovery');
    if (!box) return null;
    return {
      items: [...box.querySelectorAll('details')].map(d => ({k: d.dataset.k, label: d.querySelector('summary').textContent.trim(), steps: [...d.querySelectorAll('ol li')].map(li => li.textContent.trim())})),
      always: (box.querySelector('.always') || {textContent: ''}).textContent.trim()
    };
  }).catch(() => null);
}

/* ---------------------------------------------------------------- bubbles */
const time = () => new Date().toLocaleTimeString('ro-RO', {hour: '2-digit', minute: '2-digit'});
function lastSide() { const b = [...log.children].reverse().find(e => e.classList.contains('b')); return b ? (b.classList.contains('b-out') ? 'out' : 'in') : null; }
function bubble(side, html, o) {
  o = o || {};
  const el = document.createElement('div');
  el.className = `b b-${side}${lastSide() !== side ? ' first' : ''}${o.wide ? ' b-wide' : ''}${o.cls ? ' ' + o.cls : ''}`;
  el.id = 'm' + (++seq);
  el.tabIndex = -1;
  el.innerHTML = `<span class="sr">${side === 'in' ? 'AXA:' : 'Tu:'} </span>` + html +
    `<span class="meta"><span class="t">${time()}</span>${side === 'out' ? `<span class="tk">${TICK1}</span>` : ''}</span>`;
  log.appendChild(el);
  return el;
}
const sys = text => { const el = document.createElement('p'); el.className = 'sys'; el.textContent = text; log.appendChild(el); return el; };
function scrollTo(el, block) {
  requestAnimationFrame(() => {
    if (block === 'end') wall.scrollTo({top: wall.scrollHeight, behavior: reduce() ? 'auto' : 'smooth'});
    else wall.scrollTo({top: el.offsetTop - 8, behavior: reduce() ? 'auto' : 'smooth'});
  });
}
function typing(on, what) {
  const old = $('typing'); if (old) old.remove();
  $('presence').textContent = on ? 'scrie…' : 'asistent anti-fraudă · simulare';
  if (!on) return;
  const el = document.createElement('div');
  el.className = 'typing'; el.id = 'typing';
  el.innerHTML = `<i aria-hidden="true"></i><i aria-hidden="true"></i><i aria-hidden="true"></i><span>${esc(what)}</span>`;
  log.appendChild(el); scrollTo(el, 'end');
}
function chips(list) {
  const box = $('chips');
  box.innerHTML = '';
  list.forEach(c => {
    const b = document.createElement('button');
    b.type = 'button'; b.className = 'chip' + (c.key ? ' key' : ''); b.textContent = c.label;
    b.onclick = () => {
      if (busy && !c.whileBusy) return;
      if (c.echo !== false) bubble('out', `<p>${esc(c.say || c.label)}</p>`).querySelector('.tk').innerHTML = TICK2;
      box.innerHTML = '';
      c.run();
    };
    box.appendChild(b);
  });
}
function answer(el) { scrollTo(el); el.focus({preventScroll: true}); }

/* ---------------------------------------------------------------- semaphore + scale (data from analysis.ui.spectrum only) */
function lights(sp) {
  const placed = sp && sp.status === 'placed';
  const lit = k => placed && sp.zone === k ? ' on' : '';
  return `<span class="lights${placed ? '' : ' off'}" aria-hidden="true"><i class="l-g${lit('clear')}"></i><i class="l-a${lit('suspect')}"></i><i class="l-r${lit('strong')}"></i></span>`;
}
function scale(sp) {
  if (!sp || !sp.zones) return '';
  const placed = sp.status === 'placed';
  return `<div class="spectrum ${placed ? 'placed' : 'unplaced'}" data-role="spectrum" data-status="${esc(sp.status)}"${placed ? ` data-position="${esc(sp.position)}"` : ''}>
    <p class="sr">${esc(sp.label)}</p>
    <div class="sp-track" aria-hidden="true">${placed ? '<div class="sp-run"><span class="sp-marker"></span></div>' : ''}</div>
    <div class="sp-zones" aria-hidden="true">${sp.zones.map(z => `<span class="${placed && z.key === sp.zone ? 'on' : ''}">${esc(z.label)}</span>`).join('')}</div>
    <p class="sp-note" aria-hidden="true">${esc(placed ? `Indicator orientativ: ${sp.indicator} din 100, nu o probabilitate.` : sp.note)}</p>
  </div>`;
}
function glide(root) {
  const sp = root.querySelector('.spectrum.placed'); if (!sp) return;
  const run = sp.querySelector('.sp-run'), pos = Math.max(0, Math.min(100, Number(sp.dataset.position)));
  if (reduce()) { run.style.setProperty('--to', pos + '%'); return; }
  run.style.setProperty('--to', '0%');
  requestAnimationFrame(() => requestAnimationFrame(() => run.style.setProperty('--to', pos + '%')));
}

/* ---------------------------------------------------------------- evidence highlights inside the message bubble */
function marked(text, hs) {
  let html = '', at = 0, k = 0;
  const linked = [], unlinked = [];
  (hs || []).slice().sort((a, b) => a.start - b.start || b.end - a.end).forEach(h => {
    if (h.end > text.length || h.end <= h.start) return;
    if (h.start < at) { unlinked.push(h); return; }
    k += 1; linked.push(Object.assign({k}, h));
    html += esc(text.slice(at, h.start)) +
      `<span class="ev ev-${esc(h.severity)}" role="button" tabindex="0" data-k="${k}">${esc(text.slice(h.start, h.end))}<sup aria-hidden="true">${k}</sup><span class="sr"> (indiciul ${k}: ${esc(KIND[h.severity] || '')})</span></span>`;
    at = h.end;
  });
  return {html: html + esc(text.slice(at)), linked, unlinked};
}
function select(k, from) {
  document.querySelectorAll('.ev.sel,.notes li.sel').forEach(e => e.classList.remove('sel'));
  const mark = cur && cur.target && cur.target.querySelector(`.ev[data-k="${k}"]`);
  const notes = [...document.querySelectorAll(`.notes li[data-k="${k}"]`)];
  const note = notes[notes.length - 1];
  if (mark) mark.classList.add('sel');
  if (note) note.classList.add('sel');
  const target = from === 'mark' ? note : mark;
  if (target) target.scrollIntoView({block: 'nearest', behavior: reduce() ? 'auto' : 'smooth'});
}

/* ---------------------------------------------------------------- server */
function loadStatus() {
  return fetch('/api/status').then(r => r.ok ? r.json() : null).then(s => {
    if (!s) return;
    aiOn = s.semantic_ai === 'configured';
    if (!aiOn) { $('attach').disabled = true; $('attach').setAttribute('aria-label', 'Capturile necesită analiza AI, care nu este activă'); }
  }).catch(() => {});
}
async function post(url, body, isForm) {
  ctl = new AbortController();
  const limit = setTimeout(() => ctl.abort('timeout'), 90000);
  try {
    const res = await fetch(url, {method: 'POST', body: isForm ? body : JSON.stringify(body), headers: isForm ? {} : {'Content-Type': 'application/json'}, signal: ctl.signal});
    let data = null; try { data = await res.json(); } catch (e) { /* not JSON */ }
    if (!res.ok) { const d = data && data.detail; throw Object.assign(new Error(typeof d === 'string' ? d : res.status === 413 ? 'Mesajul sau imaginea este prea mare.' : 'Serverul nu a putut finaliza verificarea.'), {status: res.status}); }
    return data;
  } catch (e) {
    if (e.name === 'AbortError' || ctl.signal.aborted) throw Object.assign(new Error(ctl.signal.reason === 'user' ? 'Verificarea a fost anulată.' : 'Serverul nu a răspuns în 90 de secunde.'), {kind: ctl.signal.reason === 'user' ? 'cancel' : 'timeout'});
    if (e instanceof TypeError) throw Object.assign(new Error('Nu am putut contacta serverul AXA. Verifică conexiunea la internet.'), {kind: 'network'});
    throw e;
  } finally { clearTimeout(limit); }
}
function setBusy(on, what) {
  busy = on;
  $('send').disabled = on;
  if (aiOn !== false) $('attach').disabled = on;
  typing(on, what);
  if (on) chips([{label: 'Anulează verificarea', echo: false, whileBusy: true, run: () => ctl && ctl.abort('user')}]);
}

/* ---------------------------------------------------------------- conversation */
function greet() {
  log.innerHTML = ''; cur = null; asked = new Set();
  const day = document.createElement('p'); day.className = 'day'; day.textContent = 'Astăzi'; log.appendChild(day);
  sys('Simulare de interfață, nu un serviciu WhatsApp. Ce trimiți ajunge la serverul AXA și, dacă analiza AI e activă, la Google Gemini. Nu deschidem linkurile și nu păstrăm mesajul.');
  bubble('in', '<p>Bună! Sunt asistentul AXA. 👋</p><p>Trimite-mi mesajul care ți se pare ciudat (SMS, email, WhatsApp sau un link) ori o captură de ecran. Îți spun ce cere, ce am găsit și ce să faci acum.</p><p class="hint">Poți șterge din text codurile, numerele de card sau CNP-ul. Nu contează pentru verificare.</p>');
  exampleChips();
}
function exampleChips() {
  chips(EXAMPLES.map(([label, text]) => ({label: 'Exemplu: ' + label, echo: false, run: () => send(text)})));
}

/* ---------------------------------------------------------------- GDPR consent (shared with the main page): nothing is sent before an explicit "da" */
const CK = 'axa_consent_v1';
function askConsent() {
  const c = read(CK, null);
  if (c && c.granted === true) return Promise.resolve('yes');
  const dlg = $('consent');
  if (!dlg || typeof dlg.showModal !== 'function') return Promise.resolve('no');
  return new Promise(resolve => {
    dlg.returnValue = '';
    dlg.addEventListener('close', () => {
      const v = dlg.returnValue || 'no';
      if (v === 'yes') { try { localStorage.setItem(CK, JSON.stringify({granted: true, at: new Date().toISOString(), version: 1})); } catch (e) { /* storage unavailable: ask again next time */ } }
      resolve(v);
    }, {once: true});
    dlg.showModal();
  });
}
function refused(text, choice) {
  if (text) { $('msg').value = text; grow(); }
  const el = bubble('in', `<p><b>Am oprit verificarea.</b> Fără acordul tău pentru prelucrarea datelor nu trimit nimic.</p>${text ? '<p>Mesajul a rămas în caseta de jos, doar pe dispozitivul tău.</p>' : ''}`);
  answer(el);
  chips([{label: 'Citește informarea GDPR', echo: false, run: () => { window.open('/#gdpr', '_blank', 'noopener'); refusedChips(text); }},
         {label: 'M-am răzgândit, verifică', key: true, echo: false, run: () => (text ? send(text) : $('attach').click())}]);
  if (choice === 'info') window.open('/#gdpr', '_blank', 'noopener');
}
function refusedChips(text) {
  chips([{label: 'M-am răzgândit, verifică', key: true, echo: false, run: () => (text ? send(text) : $('attach').click())}, {label: 'Exemple', echo: false, run: exampleChips}]);
}

async function send(text) {
  if (busy) return;
  text = (text || '').trim();
  if (!text) { $('msg').focus(); return; }
  const choice = await askConsent();
  if (choice !== 'yes') { refused(text, choice); return; }
  $('msg').value = ''; grow();
  const mine = bubble('out', `<p class="msgtext">${esc(text)}</p>`);
  scrollTo(mine, 'end');
  setBusy(true, 'Verific mesajul…');
  try {
    const r = await post('/api/analyze', {text, ocr_reviewed: null});
    setBusy(false);
    mine.querySelector('.tk').innerHTML = TICK2;
    result(r, mine.querySelector('.msgtext'));
  } catch (e) {
    setBusy(false);
    failed(mine, e, () => { mine.remove(); send(text); }, text);
  }
}
async function sendImage(file) {
  if (!file || busy) return;
  if (aiOn === false) { bubble('in', '<p>Pe acest server analiza AI nu este activă, așa că nu pot citi capturi. Lipește textul mesajului.</p>'); return; }
  if (!/^image\/(png|jpeg|webp)$/.test(file.type)) { answer(bubble('in', '<p>Pot citi doar capturi PNG, JPEG sau WebP.</p>')); return; }
  if (file.size > 5 * 1024 * 1024) { answer(bubble('in', '<p>Captura poate avea cel mult 5 MB. Poți decupa doar mesajul.</p>')); return; }
  const choice = await askConsent();
  if (choice !== 'yes') { $('file').value = ''; refused('', choice); return; }
  const url = URL.createObjectURL(file);
  const mine = bubble('out', `<img alt="Captura trimisă: ${esc(file.name || 'imagine')}"><p class="hint">${esc(file.name || 'captură')}</p>`);
  mine.querySelector('img').src = url;
  scrollTo(mine, 'end');
  const fd = new FormData(); fd.append('file', file);
  setBusy(true, 'Citesc captura…');
  try {
    const r = await post('/api/analyze-image', fd, true);
    setBusy(false);
    mine.querySelector('.tk').innerHTML = TICK2;
    const ocr = bubble('in', `<p><b>Am citit din captură acest text.</b> Compară-l cu imaginea, mai ales cifrele și adresele:</p><p class="msgtext">${esc(r.text)}</p>`, {wide: true});
    result(r, ocr.querySelector('.msgtext'), true);
  } catch (e) {
    setBusy(false);
    failed(mine, e, () => { mine.remove(); sendImage(file); });
  } finally { $('file').value = ''; }
}
function failed(mine, e, retry, text) {
  if (e.kind === 'cancel') {
    mine.classList.add('failed');
    mine.insertAdjacentHTML('beforeend', '<p class="fail">Anulat</p>');
    if (text) { $('msg').value = text; grow(); }
    answer(bubble('in', `<p>Am oprit verificarea.${text ? ' Textul tău e din nou în caseta de jos.' : ''}</p>`));
    exampleChips(); return;
  }
  mine.classList.add('failed');
  mine.insertAdjacentHTML('beforeend', `<p class="fail">${ICON.warn} Nu s-a putut verifica</p>`);
  if (text) { $('msg').value = text; grow(); }
  const el = bubble('in', `<p><b>N-am putut finaliza verificarea.</b> ${esc(e.message)}</p>${text ? '<p>Textul tău e din nou în caseta de jos, nu se pierde nimic.</p>' : ''}`);
  answer(el);
  chips([{label: 'Încearcă din nou', key: true, run: retry}, {label: 'Scriu altceva', echo: false, run: () => $('msg').focus()}]);
}

function uiOf(a) {
  if (a.ui) return a.ui;  // older backends: minimal fallback from the label, no semaphore lit
  const st = STATE_OF[a.assessment.label] || 'unable';
  return {state: st, title: TITLES[st], reason: a.summary, action: a.headline.action, action_detail: '', recovery_suggested: st === 'no_clear_signs' ? [] : ['opened', 'code', 'paid'], partial: a.checks.semantic_ai.status !== 'completed', partial_note: null, mechanism: a.assessment.mechanism && a.assessment.mechanism.label, spectrum: null};
}
function result(r, target, fromOcr) {
  const a = r.analysis, u = uiOf(a), alert = u.state === 'strong' || u.state === 'suspect';
  const m = marked(r.text, a.highlights);
  target.innerHTML = m.html;
  cur = {r, a, u, alert, target, m, fromOcr};
  asked = new Set();
  target.querySelectorAll('.ev').forEach(ev => {
    ev.onclick = () => { if (!document.querySelector('.notes')) why(true); select(ev.dataset.k, 'mark'); };
    ev.onkeydown = e => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); ev.click(); } };
  });
  const qual = alert && u.mechanism ? `Seamănă cu: ${u.mechanism.toLowerCase()}` : (u.qualifier || '');
  const v = bubble('in', `<div class="verdict v-${esc(u.state)}">
      <div class="v-top">${lights(u.spectrum)}<span class="pill">${esc(PILL[u.state])}</span></div>
      <p class="v-title">${esc(u.title)}</p>
      ${qual ? `<p class="v-qual">${esc(qual)}</p>` : ''}
      ${scale(u.spectrum)}
      <p class="v-reason">${esc(u.reason)}</p>
      ${u.partial ? `<p class="v-partial"><b>Analiză parțială.</b> ${esc(u.partial_note || 'Interpretarea AI nu a fost disponibilă.')}</p>` : ''}
    </div>`, {wide: true});
  glide(v);
  bubble('in', `<div class="act"><p class="k">Ce faci acum</p><p class="a">${esc(u.action)}</p>${u.action_detail ? `<p>${esc(u.action_detail)}</p>` : ''}</div>`, {wide: true});
  if (m.linked.length) bubble('in', `<p class="hint">Am subliniat ${m.linked.length === 1 ? 'un fragment' : m.linked.length + ' fragmente'} în ${fromOcr ? 'textul citit' : 'mesajul tău'}. Atinge-${m.linked.length === 1 ? 'l' : 'le'} sau întreabă „De ce?”.</p>`);
  answer(v);
  menu();
}

function menu() {
  if (!cur) { exampleChips(); return; }
  const {a, u, alert, r} = cur, urls = r.url_reports || [];
  const list = [];
  const add = (id, label, run, o) => { if (!asked.has(id) || (o && o.again)) list.push(Object.assign({label, run: () => { asked.add(id); run(); }}, o || {})); };
  if (alert) add('rec', 'Am apăsat deja / am trimis date', recoveryAsk, {key: true, again: true});
  add('why', 'De ce?', () => why(false), {say: 'De ce ai ajuns la concluzia asta?'});
  if (urls.length) add('link', urls.length === 1 ? 'Ce e cu linkul?' : 'Ce e cu linkurile?', link, {say: urls.length === 1 ? 'Ce știi despre link?' : 'Ce știi despre linkuri?'});
  add('chk', 'Ce ai verificat?', checked, {say: 'Ce ai verificat și ce nu?'});
  if (alert && a.scenario) add('scen', 'Cum ar continua?', scenario, {say: 'Cum ar putea continua? (exemplu ipotetic)'});
  if (!alert) add('rec', 'Am apăsat totuși pe ceva', recoveryAsk, {again: true});
  if (alert) add('warn', 'Avertizează pe cineva', warn, {say: 'Vreau să avertizez pe cineva.'});
  add('tech', 'Detalii tehnice', tech);
  add('copy', 'Copiază rezumatul', copySummary, {again: true, echo: false});
  if (cur.fromOcr) add('fix', 'Corectez textul citit', () => { $('msg').value = r.text; grow(); $('msg').focus(); bubble('in', '<p>Am pus textul citit în caseta de jos. Corectează-l și trimite-l din nou.</p>'); }, {echo: false});
  add('new', 'Verifică alt mesaj', () => { answer(bubble('in', '<p>Sigur. Trimite-mi următorul mesaj sau o captură.</p>')); cur = null; exampleChips(); $('msg').focus(); }, {again: true});
  chips(list);
}

/* ---------------------------------------------------------------- answers (all the data from the main page, one question at a time) */
function why(silent) {
  const {m, a, fromOcr} = cur;
  const note = h => `<span class="kind">${esc(KIND[h.severity] || 'Indiciu')}${h.notes.length ? ': ' + esc(h.notes.map(n => n.title).join(' · ')) : ''}</span>` +
    `<span class="q">„${esc(h.text.length > 140 ? h.text.slice(0, 140) + '…' : h.text)}”</span>` + h.notes.map(n => `<span>${esc(n.meaning)}</span>`).join('');
  const items = m.linked.map(h => `<li class="n-${esc(h.severity)}" data-k="${h.k}" tabindex="0" role="button"><span class="n" aria-hidden="true">${h.k}</span>${note(h)}<span class="src">Sursa: ${esc(SOURCE[h.source] || h.source)}${h.match === 'normalized' ? ', potrivit în text fără diacritice' : ''}</span></li>`)
    .concat(m.unlinked.map(h => `<li class="n-${esc(h.severity)}"><span class="n" aria-hidden="true">–</span>${note(h)}<span class="src">Fragment suprapus cu altul, nesubliniat separat.</span></li>`));
  const n = items.length;
  const html = n
    ? `<p>${n === 1 ? 'Un fragment a contat' : n + ' fragmente au contat'} ${fromOcr ? 'în textul citit' : 'în mesajul tău'}. Atinge o explicație ca să vezi fragmentul.</p><ol class="notes">${items.join('')}</ol>`
    : `<p>${a.checks.semantic_ai.status === 'completed' ? 'N-am marcat fragmente: interpretarea nu a indicat părți relevante.' : 'N-am marcat fragmente: fără analiza AI marchez doar ce recunosc regulile locale.'}</p><p>${esc(cur.u.reason)}</p>`;
  const el = bubble('in', html, {wide: true});
  el.querySelectorAll('.notes li[data-k]').forEach(li => {
    li.onclick = () => select(li.dataset.k, 'note');
    li.onkeydown = e => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); li.click(); } };
  });
  asked.add('why');
  if (!silent) answer(el);
  menu();
}
function urlClass(u) {
  const t = u.typosquatting || {}, rep = (u.reputation || {}).status;
  if (u.inspection_status !== 'passive_only' || !u.domain) return 'invalid';
  if (rep === 'threat_match' || t.is_typosquatting || u.userinfo_present || u.embedded_destination_hint) return 'deceptive';
  if (t.is_official) return 'official';
  if (t.brand_on_third_party) return 'third';
  return 'unknown';
}
const middle = (s, n) => s.length <= n ? s : s.slice(0, Math.ceil(n * 0.6)) + '…' + s.slice(-Math.floor(n * 0.4));
const defang = s => s.replace(/^http/i, 'hxxp').replace(/\./g, '[.]');
function urlHtml(u, claims, i, many) {
  const cls = urlClass(u), t = u.typosquatting || {};
  if (cls === 'invalid') return `<p><b>${many ? `Linkul ${i + 1}: ` : ''}adresă care nu poate fi interpretată.</b> Destinația ei rămâne necunoscută. Nu o deschide.</p><code class="def">${esc(defang(u.original_url))}</code>`;
  const rd = u.registrable_domain || u.domain, sub = u.registrable_domain && u.subdomain ? u.subdomain + '.' : '';
  let userinfo = '';
  if (u.userinfo_present) { const mm = u.original_url.match(/^(?:[a-z][a-z0-9+.-]*:\/\/|\/\/)?([^/?#]*)@/i); userinfo = mm ? mm[1] + '@' : '…@'; }
  const rest = (u.port ? ':' + u.port : '') + (u.path && u.path !== '/' ? u.path : '') + (u.query_present ? '?…' : '') + (u.fragment_present ? '#…' : '');
  const facts = [], add = (k, x) => facts.push(`<li class="f-${k}">${ICON[k]}<span>${x}</span></li>`);
  if (cls === 'official') add('ok', `Apare în lista noastră pentru ${esc(t.brand)} (${t.verified_match ? 'catalog verificat' : 'listă statică, neverificată recent'}). Asta nu confirmă cine a trimis mesajul.`);
  if (t.is_typosquatting) add('bad', `Seamănă cu <b>${esc(t.target)}</b>, dar este alt domeniu.`);
  if (u.userinfo_present) add('bad', 'Textul dinainte de „@” e doar decor. Browserul îl ignoră și deschide domeniul de mai sus.');
  if (u.embedded_destination_hint) add('bad', 'Adresa conține în interior o altă adresă, ca să pară altceva.');
  if (t.brand_on_third_party) add('warn', `Numele ${esc(t.brand)} apare pe domeniul altei companii. Relația nu este verificată.`);
  if (cls === 'unknown') add('unk', 'Nu avem informații despre acest domeniu. Asta nu înseamnă nici că e sigur, nici că e periculos.');
  (claims || []).forEach(c => (c.destinations || []).forEach(d => {
    if (d.host !== u.domain) return;
    if (d.status === 'outside_known_domains') add('warn', `Mesajul spune că vine de la ${esc(c.claim)}, dar linkul nu este pe un domeniu cunoscut al acestei organizații.`);
    if (d.status === 'verification_incomplete') add('unk', `Nu avem domeniile oficiale pentru ${esc(c.claim)}, deci nu putem compara.`);
  }));
  if (u.is_shortened) add('warn', 'Link scurtat: nu se vede unde duce de fapt.');
  if ((u.domain || '').split('.').some(l => l.startsWith('xn--'))) add('warn', `Conține caractere internaționale. Browserul îl citește ca <b>${esc(u.domain)}</b>.`);
  const rep = (u.reputation || {}).status;
  if (rep === 'threat_match') add('bad', 'Google Web Risk a raportat această adresă ca periculoasă.');
  else if (rep === 'no_known_match') add('unk', 'Google Web Risk nu are o raportare pentru ea. Asta nu garantează că e sigură.');
  const anatomy = (userinfo || sub || rest) ? `<p class="anatomy" aria-label="Adresa, descompusă">${u.protocol ? `<span class="mute">${esc(u.protocol)}://</span>` : ''}${userinfo ? `<span class="user">${esc(middle(userinfo, 40))}</span>` : ''}<span class="mute">${esc(sub)}</span><span class="rd">${esc(rd)}</span><span class="mute">${esc(middle(rest, 44))}</span></p>` : '';
  return `<p class="hint">${many ? `Linkul ${i + 1}: domeniul real` : 'Domeniul real, adică cine controlează pagina'}</p>
    <p class="url-real u-${cls}"><span class="mute">${esc(sub)}</span><span class="rd">${esc(rd)}</span></p>${anatomy}
    <ul class="facts">${facts.join('')}</ul>
    <code class="def" aria-label="Adresa completă, scrisă fără să poată fi deschisă">${esc(defang(u.original_url))}</code>
    <button class="btn-in" type="button" data-copy="${esc(defang(u.original_url))}">Copiază adresa (nu devine link)</button>`;
}
function link() {
  const urls = cur.r.url_reports || [];
  const first = bubble('in', '<p>Doar proprietarul domeniului real controlează pagina. Tot ce e scris înaintea lui poate fi ales de oricine. N-am deschis linkul.</p>');
  urls.forEach((u, i) => {
    const el = bubble('in', urlHtml(u, cur.a.domain_assessment, i, urls.length > 1), {wide: true});
    el.querySelectorAll('[data-copy]').forEach(b => b.onclick = () => copy(b.dataset.copy, b));
  });
  answer(first); menu();
}
function checked() {
  const {a} = cur, interp = a.interpretation, ai = a.checks.semantic_ai, c = a.checks;
  const tech = [];
  if (c.urls_detected) tech.push(`Am analizat ${c.urls_analyzed} ${c.urls_analyzed === 1 ? 'link' : 'linkuri'} ca text, fără să ${c.urls_analyzed === 1 ? 'îl' : 'le'} deschid.`);
  else tech.push('Mesajul nu conține linkuri.');
  tech.push(c.database === 'unavailable_static_fallback' ? 'Catalogul de domenii: am folosit lista de rezervă.' : 'Catalogul de domenii oficiale a fost consultat.');
  if (['threat_match', 'no_known_match', 'partial'].includes(c.threat_intelligence)) tech.push('Reputația linkurilor a fost căutată în Google Web Risk.');
  tech.push('Regulile locale pentru limba română au rulat.');
  const unv = ['Cine a trimis cu adevărat mesajul.'];
  if (c.urls_detected) unv.push('Ce conține pagina linkului și unde redirecționează.', 'Cine deține domeniul și de când există.');
  if (c.urls_detected && !['threat_match', 'no_known_match', 'partial'].includes(c.threat_intelligence)) unv.push('Reputația externă a linkurilor (serviciul nu este configurat sau adresa nu e eligibilă).');
  if (ai.status !== 'completed') unv.push(`Interpretarea AI (${AI_FAIL[ai.failure || ai.status] || 'indisponibilă'}).`);
  if (ai.truncated) unv.push('Finalul unui mesaj foarte lung (AI a citit doar începutul).');
  if (c.ocr === 'transcribed_unverified') unv.push('Exactitatea textului citit din captură.');
  const aiPart = interp
    ? `<p class="sec">${ICON.ai}Ce înțelege AI din mesaj</p><p class="hint">Interpretare automată (Gemini), nu o verificare.</p><p><b>Ce vrea de la tine:</b> ${esc(interp.wants_summary)}</p>${interp.claimed_sender && interp.claimed_sender.name ? `<p><b>Se prezintă ca:</b> ${esc(interp.claimed_sender.name)} (neconfirmat)</p>` : ''}`
    : `<p class="sec">${ICON.ai}Interpretarea AI</p><p>Nu a fost disponibilă: ${esc(AI_FAIL[ai.failure || ai.status] || 'indisponibilă')}. Am folosit doar verificările locale.</p>`;
  const el = bubble('in', aiPart +
    `<p class="sec">${ICON.tech}Ce am verificat tehnic</p><ul>${tech.map(x => `<li>${esc(x)}</li>`).join('')}</ul>` +
    `<p class="sec">${ICON.unk}Ce nu am putut verifica</p><ul>${unv.map(x => `<li>${esc(x)}</li>`).join('')}</ul>`, {wide: true});
  answer(el); menu();
}
function recoveryAsk() {
  if (!recovery) {
    answer(bubble('in', '<p>Nu am putut încărca pașii aici. Îi găsești pe pagina principală, în secțiunea „Ai apăsat, ai trimis date sau ai plătit?”.</p><a class="btn-in" href="/#ajutor">Deschide pașii de ajutor</a>'));
    menu(); return;
  }
  const order = (cur && cur.u.recovery_suggested) || [];
  const items = recovery.items.slice().sort((x, y) => { const ix = order.indexOf(x.k), iy = order.indexOf(y.k); return (ix < 0 ? 99 : ix) - (iy < 0 ? 99 : iy); });
  const el = bubble('in', `<p>Se întâmplă oricui. Contează ce faci acum. <b>Ce s-a întâmplat?</b></p><div class="picks" role="group" aria-label="Ce s-a întâmplat">${items.map(x => `<button class="pick" type="button" data-rk="${esc(x.k)}"><span>${esc(x.label)}</span>${order.includes(x.k) ? '<span class="fit">potrivit aici</span>' : ''}</button>`).join('')}</div>`, {wide: true});
  el.querySelectorAll('.pick').forEach(b => b.onclick = () => {
    const it = recovery.items.find(x => x.k === b.dataset.rk);
    bubble('out', `<p>${esc(it.label)}</p>`).querySelector('.tk').innerHTML = TICK2;
    const s = bubble('in', `<p><b>${esc(it.label)}</b>. Fă asta acum:</p><ol>${it.steps.map(x => `<li>${esc(x)}</li>`).join('')}</ol><p class="hint">${esc(recovery.always)}</p>`, {wide: true});
    answer(s); menu();
  });
  answer(el); menu();
}
function scenario() {
  const sc = cur.a.scenario;
  const el = bubble('in', `<p><b>Exemplu ipotetic, nu ce s-a întâmplat.</b> ${esc(sc.disclaimer)}</p>
    <ol>${sc.steps.map(x => `<li><b>${esc(x.title)}</b><span class="hyp">ipotetic</span><br>${esc(x.text)}</li>`).join('')}</ol>
    <p><b>Cum arată varianta legitimă:</b> ${esc(sc.real_world)}</p>
    ${sc.personalized_from && sc.personalized_from.length ? `<p class="hint">Adaptat după ce am găsit în mesaj: ${esc(sc.personalized_from.join(', '))}. Restul pașilor sunt generali.</p>` : ''}`, {wide: true});
  answer(el); menu();
}
function tech() {
  const {a} = cur, s = a.assessment;
  const indicator = s.risk_estimate == null ? 'neestimat (dovezile sunt insuficiente sau contradictorii)' : `${s.risk_estimate} din 100. Rezumă puterea indiciilor găsite; nu este o probabilitate de fraudă.`;
  const ledger = (a.evidence || []).map(e => `<li><b>${esc(SOURCE[e.source] || e.source)}</b> · ${esc(STATUS[e.status] || e.status)} · ${e.tier >= 70 ? 'nivel ridicat' : e.tier >= 35 ? 'nivel mediu' : e.tier > 0 ? 'nivel scăzut' : 'fără nivel'}<br>${esc(e.reason || e.label || '')}${e.quote ? ` <q>${esc(e.quote.length > 80 ? e.quote.slice(0, 80) + '…' : e.quote)}</q>` : ''}</li>`).join('');
  const el = bubble('in', `<dl class="kv"><dt>Indicator intern</dt><dd>${esc(indicator)}</dd>
      <dt>Încredere în interpretare</dt><dd>${esc(CONF[s.confidence] || s.confidence)} (separată de nivelul de risc)</dd>
      ${s.mechanism ? `<dt>Mecanism</dt><dd>${esc(s.mechanism.label)}</dd>` : ''}
      <dt>Ce a rulat</dt><dd>${esc(a.engine_used)} · ${esc(a.timings_ms.analysis)} ms</dd></dl>
      ${a.uncertainties.length ? `<p class="sec">Limite</p><ul>${a.uncertainties.map(x => `<li>${esc(x)}</li>`).join('')}</ul>` : ''}
      ${ledger ? `<p class="sec">Jurnalul dovezilor</p><ul class="ledger">${ledger}</ul>` : ''}
      <p class="hint">Interpretările AI contează doar dacă fragmentul citat se găsește în text. Faptele tehnice vin din analiza statică, catalog sau furnizorul de reputație.</p>`, {wide: true});
  answer(el); menu();
}
function warn() {
  const share = cur.a.share_text;
  const el = bubble('in', `<p>Poți trimite mai departe acest avertisment. <b>Nu conține textul mesajului, linkuri, numere sau coduri.</b></p><p class="msgtext">${esc(share)}</p>
    <div class="btn-row"><a class="btn-in" target="_blank" rel="noopener noreferrer" href="https://wa.me/?text=${encodeURIComponent(share)}">Trimite avertismentul</a><button class="btn-in" type="button" id="cpw${seq}">Copiază</button></div>`, {wide: true});
  el.querySelector('button').onclick = e => copy(share, e.currentTarget);
  answer(el); menu();
}
function copySummary() {
  const {a, u} = cur;
  copy([a.share_text, '', 'Ce să faci: ' + u.action, u.action_detail].filter(x => x !== undefined).join('\n'), null);
  answer(bubble('in', '<p>Am copiat rezumatul. Nu conține textul mesajului, linkuri, numere sau coduri.</p>'));
  menu();
}
function copy(s, b) {
  const t = b && b.textContent;
  const done = msg => { if (b) { b.textContent = msg; setTimeout(() => { b.textContent = t; }, 1600); } };
  try { navigator.clipboard.writeText(s).then(() => done('Copiat'), () => done('Copierea nu a mers')); } catch (e) { done('Copierea nu a mers'); }
}

/* ---------------------------------------------------------------- composer */
function grow() { const m = $('msg'); m.style.height = 'auto'; m.style.height = Math.min(m.scrollHeight, 144) + 'px'; }
$('composer').addEventListener('submit', e => { e.preventDefault(); send($('msg').value); });
$('msg').addEventListener('input', grow);
$('msg').addEventListener('keydown', e => {
  if (e.key === 'Enter' && !e.shiftKey && !e.isComposing && !matchMedia('(pointer: coarse)').matches) { e.preventDefault(); send($('msg').value); }
});
$('msg').addEventListener('paste', e => {
  const f = [...((e.clipboardData && e.clipboardData.files) || [])].find(x => /^image\//.test(x.type));
  if (f) { e.preventDefault(); sendImage(f); }
});
$('attach').onclick = () => $('file').click();
$('file').onchange = e => sendImage(e.target.files[0]);
$('consent-info').onclick = () => $('consent').close('info');
$('reset').onclick = () => { if (ctl && busy) ctl.abort('user'); greet(); $('msg').focus(); };
const phone = document.querySelector('.phone');
let depth = 0;
const hasFile = e => e.dataTransfer && [...e.dataTransfer.types].includes('Files');
phone.addEventListener('dragenter', e => { if (!hasFile(e)) return; e.preventDefault(); depth += 1; phone.classList.add('drag'); });
phone.addEventListener('dragover', e => { if (hasFile(e)) { e.preventDefault(); e.dataTransfer.dropEffect = 'copy'; } });
phone.addEventListener('dragleave', () => { depth = Math.max(0, depth - 1); if (!depth) phone.classList.remove('drag'); });
phone.addEventListener('drop', e => { if (!hasFile(e)) return; e.preventDefault(); depth = 0; phone.classList.remove('drag'); sendImage(e.dataTransfer.files[0]); });

greet();
loadStatus();
loadRecovery().then(x => { recovery = x; });
})();
