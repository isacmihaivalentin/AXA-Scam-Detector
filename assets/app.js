/* AXA Scam Detector — interface (v2.1.1 "Evidence Desk, alive").
   The backend decides; this file only presents. Every server or user string goes through esc().
   Submitted links are never rendered as clickable links. No message text is ever stored.
   The risk scale is drawn only from analysis.ui.spectrum; the browser never computes a position. */
(function () {
'use strict';
const $ = id => document.getElementById(id);
const esc = s => String(s == null ? '' : s).replace(/[&<>"']/g, m => ({'&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'}[m]));
const reduce = () => matchMedia('(prefers-reduced-motion: reduce)').matches;
const MS = {local: 220, major: 320};
const EASE = 'cubic-bezier(.22,1,.36,1)';
const store = {
  get(k, d) { try { const v = localStorage.getItem(k); return v ? JSON.parse(v) : d; } catch (e) { return d; } },
  set(k, v) { try { localStorage.setItem(k, JSON.stringify(v)); } catch (e) { /* storage unavailable */ } },
  del(k) { try { localStorage.removeItem(k); } catch (e) { /* ignore */ } }
};

const EXAMPLES = [
  'SAMEDAY: Coletul dvs. RO492819 nu a putut fi livrat din cauza unei adrese incomplete. Actualizați datele în maxim 24 de ore pentru a evita returnarea și plata unei taxe de depozitare: https://sameday-livrare-ro.example/tracking',
  'ALERTĂ BCR: Stimate client, contul dvs. a fost suspendat în urma unei tranzacții suspecte. Pentru deblocare imediată validați identitatea și introduceți datele cardului aici: http://bcr-verifica-cont.example/login',
  'Bună! Am văzut anunțul tău și am achitat deja produsul. Intră pe linkul generat de curier ca să îți introduci datele cardului și codul CVV pentru a încasa banii imediat: https://o1x-plata-sigura.example/incasare',
  'Salut mami, mi-am schimbat numărul, telefonul meu s-a stricat. Te rog urgent să faci un transfer de 2.300 lei în contul pe care ți-l dau acum, că am o problemă. Nu spune nimănui, îți explic mai târziu.',
  'Felicitări, ai fost selectat pentru postul de operator date de acasă, 4.500 lei/lună. Înainte de prima zi trebuie achitată taxa de echipament de 199 lei prin transfer, apoi primești contractul. Răspunde azi, locurile sunt limitate.',
  'Salut! Comanda ta eMAG #4029182 a fost predată curierului și va fi livrată astăzi. Poți vedea statusul în aplicația ta sau pe https://www.emag.ro.'
];

/* ---------------------------------------------------------------- vocabulary */
const MARKS = {
  // Shape + word carry the meaning; colour only reinforces it.
  strong: '<svg viewBox="0 0 48 48" aria-hidden="true"><path d="M16 3h16l13 13v16L32 45H16L3 32V16z" fill="currentColor"/><path d="M24 12v15" stroke="var(--paper-2)" stroke-width="5" stroke-linecap="round"/><circle cx="24" cy="35" r="3" fill="var(--paper-2)"/></svg>',
  suspect: '<svg viewBox="0 0 48 48" aria-hidden="true"><path d="M24 4 46 43H2z" fill="currentColor"/><path d="M24 17v13" stroke="var(--paper-2)" stroke-width="5" stroke-linecap="round"/><circle cx="24" cy="37" r="2.8" fill="var(--paper-2)"/></svg>',
  no_clear_signs: '<svg viewBox="0 0 48 48" aria-hidden="true"><circle cx="20" cy="20" r="13" fill="none" stroke="currentColor" stroke-width="4.5"/><path d="M30 30l13 13" stroke="currentColor" stroke-width="5.5" stroke-linecap="round"/></svg>',
  unable: '<svg viewBox="0 0 48 48" aria-hidden="true"><rect x="4" y="4" width="40" height="40" rx="6" fill="none" stroke="currentColor" stroke-width="3.5" stroke-dasharray="7 5"/><path d="M18 18.5a6 6 0 1 1 8.6 5.4c-1.7.9-2.6 2-2.6 3.8V30" fill="none" stroke="currentColor" stroke-width="4" stroke-linecap="round"/><circle cx="24" cy="36" r="2.6" fill="currentColor"/></svg>'
};
const EYEBROW = {strong: 'Alertă', suspect: 'Atenție', no_clear_signs: 'Rezultat', unable: 'Fără verdict'};
const ICON = {
  bad: '<svg viewBox="0 0 20 20" aria-hidden="true"><path d="M10 2 19 18H1z" fill="currentColor"/></svg>',
  warn: '<svg viewBox="0 0 20 20" aria-hidden="true"><circle cx="10" cy="10" r="8" fill="none" stroke="currentColor" stroke-width="2.5"/><path d="M10 5.5v5.5" stroke="currentColor" stroke-width="2.5" stroke-linecap="round"/><circle cx="10" cy="14.5" r="1.4" fill="currentColor"/></svg>',
  ok: '<svg viewBox="0 0 20 20" aria-hidden="true"><path d="M4 10.5l4 4 8-9" fill="none" stroke="currentColor" stroke-width="2.6" stroke-linecap="round" stroke-linejoin="round"/></svg>',
  unk: '<svg viewBox="0 0 20 20" aria-hidden="true"><circle cx="10" cy="10" r="8" fill="none" stroke="currentColor" stroke-width="2" stroke-dasharray="3 2.5"/></svg>',
  ai: '<svg viewBox="0 0 20 20" aria-hidden="true"><path d="M3 4h14v9H8l-4 3v-3H3z" fill="none" stroke="currentColor" stroke-width="2" stroke-linejoin="round"/></svg>',
  tech: '<svg viewBox="0 0 20 20" aria-hidden="true"><path d="M3 5h14M3 10h14M3 15h9" stroke="currentColor" stroke-width="2" stroke-linecap="round"/></svg>',
  chev: '<svg viewBox="0 0 20 20" aria-hidden="true"><path d="M5 7.5l5 5 5-5" fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round"/></svg>'
};
const KIND = {alarm: 'Îngrijorător', attention: 'De reținut', note: 'Informativ', protective: 'Protector'};
const SOURCE = {gemini: 'interpretare AI', rules: 'reguli locale', static_url: 'analiza linkului', catalog: 'catalogul de domenii', google_web_risk: 'Google Web Risk', policy: 'politica AXA'};
const STATUS = {supported: 'Susținut de text', tentative: 'Neconfirmat în text', contradicted: 'Contrazis de text', context: 'Context', corroborating: 'Confirmă'};
const CONF = {high: 'mare', medium: 'medie', low: 'mică'};
const AI_FAIL = {not_configured: 'nu este configurată pe server', busy: 'serverul era ocupat', timeout: 'nu a răspuns la timp', rate_limited: 's-a atins limita de cereri', authentication_or_access: 'cheia de acces a fost respinsă', model_unavailable: 'modelul nu este disponibil', invalid_output: 'răspunsul nu a putut fi citit', invalid_request: 'cererea a fost respinsă', blocked: 'răspunsul a fost blocat de furnizor', provider_unavailable: 'furnizorul nu este disponibil', failed: 'nu a răspuns'};
const TITLES = {strong: 'Indicii puternice de tentativă de fraudă', suspect: 'Mesaj suspect', no_clear_signs: 'Nu am găsit indicii clare de fraudă', unable: 'Nu putem evalua suficient mesajul'};
const STATE_OF = {critical: 'strong', suspicious: 'suspect', low: 'no_clear_signs', marketing: 'no_clear_signs', protective: 'no_clear_signs', inconclusive: 'unable'};
const URL_WORD = {official: 'în lista domeniilor oficiale', deceptive: 'structură înșelătoare', third: 'domeniul altei companii', unknown: 'necunoscut nouă', invalid: 'adresă care nu poate fi citită'};

let ctl = null, busy = false, ocrMode = false, tick = null, aiOn = null, lastSpeech = '', fileName = '';

/* ---------------------------------------------------------------- motion helpers (all skip under reduced motion) */
function animateHeight(el, from, to, done) {
  if (el._anim) el._anim.cancel();
  el.style.overflow = 'hidden';
  const anim = el.animate({height: [from + 'px', to + 'px']}, {duration: MS.local, easing: EASE});
  el._anim = anim;
  const end = () => { if (el._anim === anim) { el._anim = null; el.style.overflow = ''; } };
  anim.onfinish = () => { end(); if (done) done(); };
  anim.oncancel = end;
}
// <details class="disc">: smooth, interruptible height; native toggle when motion is reduced.
function wireDisc(d) {
  const sum = d.querySelector(':scope > summary');
  sum.addEventListener('click', e => {
    if (reduce() || !d.animate) return;
    e.preventDefault();
    const from = d.getBoundingClientRect().height;
    const opening = !d.open || d.dataset.closing === '1';
    if (d._anim) { d._anim.oncancel = null; d._anim.cancel(); d._anim = null; }
    if (opening) {
      d.dataset.closing = '';
      d.open = true;
      const to = d.getBoundingClientRect().height;
      animateHeight(d, from, to);
      const body = d.querySelector(':scope > .body');
      if (body) body.animate({opacity: [0, 1], transform: ['translateY(6px)', 'none']}, {duration: MS.local, easing: EASE});
    } else {
      d.dataset.closing = '1';
      const to = sum.getBoundingClientRect().height + (d.offsetHeight - d.clientHeight);
      animateHeight(d, from, to, () => { d.open = false; d.dataset.closing = ''; });
    }
  });
}
// A plain region shown/hidden with the same height motion.
function reveal(el, show) {
  if (reduce() || !el.animate) { el.hidden = !show; return; }
  const from = el.hidden ? 0 : el.getBoundingClientRect().height;
  if (el._anim) { el._anim.oncancel = null; el._anim.cancel(); el._anim = null; }
  el.hidden = false;
  const full = el.getBoundingClientRect().height;
  animateHeight(el, from, show ? full : 0, () => { if (!show) el.hidden = true; });
}

/* ---------------------------------------------------------------- server status → honest privacy line */
function loadStatus() {
  fetch('/api/status').then(r => r.ok ? r.json() : null).then(s => {
    if (!s) return;
    aiOn = s.semantic_ai === 'configured';
    $('privtext').textContent = aiOn
      ? 'la serverul AXA și la Google Gemini, care îl interpretează.'
      : 'doar la serverul AXA. Analiza AI nu este activă acum, așa că rezultatul va folosi numai verificări locale.';
    if (!aiOn) { $('up').disabled = true; $('up').setAttribute('aria-describedby', 'privacy'); $('up').textContent = 'Captura necesită analiza AI'; $('drophint').hidden = true; }
  }).catch(() => { /* keep the default, which names both possible recipients */ });
}

/* ---------------------------------------------------------------- requests */
function setBusy(on, what) {
  busy = on;
  $('go').disabled = on;
  if (aiOn !== false) $('up').disabled = on;
  $('go').innerHTML = on ? '<span class="spin" aria-hidden="true"></span>Se verifică…' : 'Verifică mesajul';
  const out = $('out');
  out.classList.toggle('stale', on && !out.hidden);
  out.setAttribute('aria-busy', on ? 'true' : 'false');
  clearInterval(tick);
  if (!on) { $('busy').innerHTML = ''; return; }
  const t0 = Date.now();
  const paint = () => {
    const s = Math.round((Date.now() - t0) / 1000);
    const note = s >= 25 ? `Durează mai mult decât de obicei (${s} s).` : s >= 4 ? `Încă lucrăm (${s} s).` : '';
    $('busy').innerHTML = `<span>${esc(what)} ${esc(note)}</span><button class="btn-text" type="button" id="cancel">Anulează</button>`;
    $('cancel').onclick = () => ctl && ctl.abort('user');
  };
  paint(); tick = setInterval(() => { if (busy && $('cancel') !== document.activeElement) paint(); }, 1000);
}
async function post(url, body, isForm) {
  ctl = new AbortController();
  const limit = setTimeout(() => ctl.abort('timeout'), 90000);
  try {
    const res = await fetch(url, {method: 'POST', body: isForm ? body : JSON.stringify(body), headers: isForm ? {} : {'Content-Type': 'application/json'}, signal: ctl.signal});
    let data = null; try { data = await res.json(); } catch (e) { /* not JSON */ }
    if (!res.ok) {
      const d = data && data.detail;
      const err = new Error(typeof d === 'string' ? d : res.status === 413 ? 'Mesajul sau imaginea este prea mare.' : 'Serverul nu a putut finaliza verificarea.');
      err.status = res.status; throw err;
    }
    return data;
  } catch (e) {
    if (e.name === 'AbortError' || ctl.signal.aborted) { const err = new Error(ctl.signal.reason === 'user' ? 'cancel' : 'timeout'); err.kind = ctl.signal.reason === 'user' ? 'cancel' : 'timeout'; throw err; }
    if (e instanceof TypeError) { const err = new Error('Nu am putut contacta serverul AXA. Verifică conexiunea la internet.'); err.kind = 'network'; throw err; }
    throw e;
  } finally { clearTimeout(limit); }
}
function showError(title, text, actions) {
  const box = $('err');
  box.innerHTML = `<h2>${esc(title)}</h2><p>${esc(text)}</p>${actions && actions.length ? `<div class="btns">${actions.map((a, i) => `<button class="btn ${i ? 'btn-ghost' : 'btn-cta'}" type="button" data-a="${i}">${esc(a.label)}</button>`).join('')}</div>` : ''}`;
  box.hidden = false;
  (actions || []).forEach((a, i) => { box.querySelector(`[data-a="${i}"]`).onclick = a.run; });
  box.focus();
}
function clearError() { $('err').hidden = true; $('err').innerHTML = ''; $('t').removeAttribute('aria-invalid'); }

/* ---------------------------------------------------------------- GDPR consent: nothing is sent before an explicit "da" */
const CK = 'axa_consent_v1';
const consentGiven = () => { const c = store.get(CK, null); return !!(c && c.granted === true); };
function askConsent() {
  if (consentGiven()) return Promise.resolve('yes');
  const dlg = $('consent');
  if (!dlg || typeof dlg.showModal !== 'function') return Promise.resolve('no');  // no dialog support: never send silently
  return new Promise(resolve => {
    dlg.returnValue = '';
    dlg.addEventListener('close', () => {
      const v = dlg.returnValue || 'no';  // Escape or closing without a choice = refusal
      if (v === 'yes') store.set(CK, {granted: true, at: new Date().toISOString(), version: 1});
      showConsent();
      resolve(v);
    }, {once: true});
    dlg.showModal();
  });
}
function goGdpr() { $('gdpr').scrollIntoView({behavior: reduce() ? 'auto' : 'smooth'}); $('gdpr-h').focus({preventScroll: true}); }
function consentStopped(choice) {
  $('busy').innerHTML = '';
  showError('Verificarea s-a oprit', choice === 'info'
    ? 'Nu am trimis nimic. Citește informarea despre prelucrarea datelor, apoi apasă din nou „Verifică mesajul” dacă vrei să continui.'
    : 'Nu ai fost de acord cu prelucrarea datelor, așa că nu am trimis nimic. Ce ai scris a rămas doar pe acest dispozitiv.',
    [{label: 'Citește informarea GDPR', run: goGdpr}]);
  if (choice === 'info') goGdpr();
}
function showConsent() {
  const c = store.get(CK, null), el = $('gdpr-state');
  if (!el) return;
  const on = !!(c && c.granted === true);
  el.textContent = on
    ? `Ți-ai dat acordul pe ${new Date(c.at).toLocaleString('ro-RO', {dateStyle: 'long', timeStyle: 'short'})}. Îl poți retrage oricând.`
    : 'Nu ți-ai dat acordul. Îți vom cere acordul înainte de prima verificare și nu trimitem nimic fără el.';
  $('gdpr-revoke').hidden = !on;
}

async function run() {
  if (busy) return;
  const text = $('t').value.trim();
  clearError();
  if (!text) {
    $('t').setAttribute('aria-invalid', 'true');
    showError('Caseta este goală', 'Lipește mai întâi mesajul primit sau un link, apoi apasă „Verifică mesajul”.', [{label: 'Mergi la casetă', run: () => $('t').focus()}]);
    return;
  }
  const choice = await askConsent();
  if (choice !== 'yes') { consentStopped(choice); return; }
  setBusy(true, 'Analizăm mesajul. De obicei durează câteva secunde.');
  try {
    const r = await post('/api/analyze', {text, ocr_reviewed: ocrMode ? $('ocrok').checked : null});
    setBusy(false); render(r); remember(r);
  } catch (e) {
    setBusy(false);
    if (e.kind === 'cancel') { $('busy').textContent = 'Verificarea a fost anulată. Textul a rămas în casetă.'; $('out').classList.remove('stale'); return; }
    showError(e.kind === 'timeout' ? 'Verificarea a durat prea mult' : 'Nu am putut finaliza verificarea',
      (e.kind === 'timeout' ? 'Serverul nu a răspuns în 90 de secunde. ' : e.message + ' ') + 'Textul tău a rămas în casetă.',
      [{label: 'Încearcă din nou', run}, {label: 'Mergi la casetă', run: () => $('t').focus()}]);
    $('out').classList.remove('stale');
  }
}
function paintChip(state) {
  const chip = $('chip');
  if (!state) { chip.hidden = true; chip.innerHTML = ''; return; }
  chip.innerHTML = state === 'reading'
    ? `<span>Citim captura <b>${esc(fileName)}</b>…</span>`
    : `<span>Captură citită: <b>${esc(fileName)}</b></span><button class="btn-text" type="button" id="chip-re">Înlocuiește</button><button class="btn-text" type="button" id="chip-rm">Elimină captura</button>`;
  chip.hidden = false;
  if (state === 'done') {
    $('chip-re').onclick = () => $('file').click();
    $('chip-rm').onclick = () => { clearAll(); $('live').textContent = 'Captura și textul citit din ea au fost eliminate.'; $('t').focus(); };
  }
}
async function upload(file) {
  if (!file || busy) return;
  clearError();
  if (aiOn === false) { showError('Captura necesită analiza AI', 'Pe acest server analiza AI nu este activă, deci nu putem citi capturi. Lipește textul manual.', [{label: 'Mergi la casetă', run: () => $('t').focus()}]); return; }
  if (!/^image\/(png|jpeg|webp)$/.test(file.type)) { showError('Format neacceptat', 'Poți încărca o captură PNG, JPEG sau WebP.', [{label: 'Alege altă captură', run: () => $('file').click()}]); return; }
  const choice = await askConsent();
  if (choice !== 'yes') { consentStopped(choice); $('file').value = ''; return; }
  if (file.size > 5 * 1024 * 1024) { showError('Imagine prea mare', 'Captura poate avea cel mult 5 MB. Poți decupa doar mesajul.', [{label: 'Alege altă captură', run: () => $('file').click()}]); return; }
  const fd = new FormData(); fd.append('file', file);
  const prevName = fileName, wasOcr = ocrMode;
  fileName = file.name || 'captură';
  paintChip('reading');
  setBusy(true, 'Citim textul din captură și îl analizăm.');
  try {
    const r = await post('/api/analyze-image', fd, true);
    setBusy(false);
    $('t').value = r.text; ocrMode = true; $('ocrnote').hidden = false; $('ocrok').checked = false; syncClear();
    paintChip('done');
    render(r); remember(r);
  } catch (e) {
    setBusy(false);
    fileName = prevName; paintChip(wasOcr ? 'done' : null);
    if (e.kind === 'cancel') { $('busy').textContent = 'Citirea capturii a fost anulată. Ce era în casetă a rămas neschimbat.'; return; }
    showError('Nu am putut citi captura', (e.message || 'Poți încerca din nou.') + ' Ce era în casetă a rămas neschimbat.',
      [{label: 'Încearcă din nou', run: () => upload(file)}, {label: 'Alege altă captură', run: () => $('file').click()}, {label: 'Lipește textul manual', run: () => $('t').focus()}]);
  } finally { $('file').value = ''; }
}

/* ---------------------------------------------------------------- evidence: message exhibit */
function exhibit(text, hs) {
  let html = '', at = 0, k = 0;
  const linked = [], unlinked = [];
  hs.slice().sort((a, b) => a.start - b.start || b.end - a.end).forEach(h => {
    if (h.end > text.length || h.end <= h.start) return;
    if (h.start < at) { unlinked.push(h); return; }
    k += 1; h.k = k; linked.push(h);
    html += esc(text.slice(at, h.start)) +
      `<a class="ev ev-${esc(h.severity)}" href="#ev-${k}" id="evm-${k}" data-k="${k}">${esc(text.slice(h.start, h.end))}<sup aria-hidden="true">${k}</sup><span class="sr"> (indiciul ${k}: ${esc(KIND[h.severity] || '')})</span></a>`;
    at = h.end;
  });
  html += esc(text.slice(at));
  const note = h => `<span class="kind">${esc(KIND[h.severity] || 'Indiciu')}${h.notes.length ? ': ' + esc(h.notes.map(n => n.title).join(' · ')) : ''}</span>` +
    `<span class="q">„${esc(h.text.length > 140 ? h.text.slice(0, 140) + '…' : h.text)}”</span>` +
    h.notes.map(n => `<span class="m">${esc(n.meaning)}</span>`).join('');
  const items = linked.map(h => `<li id="ev-${h.k}" class="n-${esc(h.severity)}" tabindex="-1" data-k="${h.k}"><span class="n" aria-hidden="true">${h.k}</span>${note(h)}<span class="src">Sursa: ${esc(SOURCE[h.source] || h.source)}${h.match === 'normalized' ? ', potrivit în text fără diacritice' : ''} · <a href="#evm-${h.k}">Vezi în mesaj</a></span></li>`)
    .concat(unlinked.map(h => `<li class="n-${esc(h.severity)}"><span class="n" aria-hidden="true">–</span>${note(h)}<span class="src">Fragment suprapus cu altul, nemarcat separat în mesaj.</span></li>`));
  const kinds = [...new Set(linked.concat(unlinked).map(h => h.severity))];
  return {html, list: items.join(''), n: linked.length + unlinked.length, kinds};
}
function selectEvidence(k, from) {
  document.querySelectorAll('#out .sel').forEach(e => { e.classList.remove('sel'); e.removeAttribute('aria-current'); });
  const mark = $('evm-' + k), item = $('ev-' + k);
  if (!mark || !item) return;
  mark.classList.add('sel'); mark.setAttribute('aria-current', 'true'); item.classList.add('sel');
  const target = from === 'mark' ? item : mark;
  target.scrollIntoView({block: 'nearest', behavior: reduce() ? 'auto' : 'smooth'});
  if (from === 'mark') item.focus({preventScroll: true});
}

/* ---------------------------------------------------------------- links: domain anatomy */
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
function urlCard(u, claims, i, many) {
  const cls = urlClass(u), t = u.typosquatting || {};
  if (cls === 'invalid') {
    return `<article class="url u-unknown"><p class="url-k">Adresă care nu poate fi interpretată</p><code>${esc(u.original_url)}</code>
      <p>Nu am putut citi această adresă, așa că destinația ei rămâne necunoscută. Nu o deschide.</p></article>`;
  }
  const rd = u.registrable_domain || u.domain;
  const sub = u.registrable_domain && u.subdomain ? u.subdomain + '.' : '';
  let userinfo = '';
  if (u.userinfo_present) { const m = u.original_url.match(/^(?:[a-z][a-z0-9+.-]*:\/\/|\/\/)?([^/?#]*)@/i); userinfo = m ? m[1] + '@' : '…@'; }
  const rest = (u.port ? ':' + u.port : '') + (u.path && u.path !== '/' ? u.path : '') + (u.query_present ? '?…' : '') + (u.fragment_present ? '#…' : '');
  const showAnatomy = userinfo || sub || rest;
  const anatomy = (u.protocol ? `<span class="a-mute">${esc(u.protocol)}://</span>` : '') +
    (userinfo ? `<span class="a-user">${esc(middle(userinfo, 48))}</span><span class="sr"> (partea dinainte de @ este ignorată de browser) </span>` : '') +
    `<span class="a-mute">${esc(sub)}</span><span class="a-rd">${esc(rd)}</span><span class="a-mute">${esc(middle(rest, 56))}</span>`;
  // Facts refer to "acest domeniu": the domain itself is printed once, large.
  const facts = [];
  const add = (kind, text) => facts.push(`<li class="f-${kind}">${ICON[kind]}<span>${text}</span></li>`);
  if (cls === 'official') add('ok', `Apare în lista noastră pentru ${esc(t.brand)} (${t.verified_match ? 'catalog verificat' : 'listă statică, neverificată recent'}). Asta nu confirmă cine a trimis mesajul.`);
  if (t.is_typosquatting) add('bad', `Seamănă cu <b>${esc(t.target)}</b>, dar este alt domeniu.`);
  if (u.userinfo_present) add('bad', 'Textul dinainte de „@” este doar decor. Browserul îl ignoră și deschide domeniul de mai sus.');
  if (u.embedded_destination_hint) add('bad', 'Adresa conține în interior o altă adresă, ca să pară altceva. Destinația reală este cea de mai sus.');
  if (t.brand_on_third_party) add('warn', `Numele ${esc(t.brand)} apare pe domeniul altei companii. Poate fi un serviciu folosit de ${esc(t.brand)} sau o imitație: relația nu este verificată.`);
  if (cls === 'unknown') add('unk', 'Nu avem informații despre acest domeniu. Asta nu înseamnă nici că e sigur, nici că e periculos.');
  (claims || []).forEach(c => (c.destinations || []).forEach(d => {
    if (d.host !== u.domain) return;
    if (d.status === 'outside_known_domains') add('warn', `Mesajul spune că vine de la ${esc(c.claim)}, dar linkul nu este pe un domeniu cunoscut al acestei organizații.`);
    if (d.status === 'verification_incomplete') add('unk', `Nu avem domeniile oficiale pentru ${esc(c.claim)}, deci nu putem compara.`);
  }));
  if (u.is_shortened) add('warn', 'Link scurtat: nu se vede unde duce de fapt.');
  if ((u.domain || '').split('.').some(l => l.startsWith('xn--'))) add('warn', `Conține caractere internaționale. Browserul îl citește ca <b>${esc(u.domain)}</b>; unele litere pot semăna între ele.`);
  const rep = (u.reputation || {}).status;
  if (rep === 'threat_match') add('bad', 'Google Web Risk a raportat această adresă ca periculoasă.');
  else if (rep === 'no_known_match') add('unk', 'Google Web Risk nu are o raportare pentru ea. Asta nu garantează că e sigură.');
  return `<article class="url u-${cls}" aria-labelledby="url-${i}">
    <p class="url-k" id="url-${i}">${many ? `Linkul ${i + 1}: domeniul real` : 'Domeniul real, adică cine controlează pagina'}</p>
    <p class="url-real"><span class="a-mute">${esc(sub)}</span><span class="rd">${esc(rd)}</span></p>
    ${showAnatomy ? `<p class="anatomy" aria-label="Adresa, descompusă">${anatomy}</p>` : ''}
    <ul class="url-facts">${facts.join('')}</ul>
    <details><summary>Adresa completă, scrisă fără să poată fi deschisă</summary><code>${esc(defang(u.original_url))}</code>
      <button class="btn-text" type="button" data-copy="${esc(defang(u.original_url))}">Copiază adresa (nu devine link)</button></details>
  </article>`;
}

/* ---------------------------------------------------------------- provenance: three zones */
function provenance(r, a) {
  const interp = a.interpretation, ai = a.checks.semantic_ai, c = a.checks;
  const aiZone = interp
    ? `<section class="zone z-ai" aria-labelledby="z1"><h3 id="z1">${ICON.ai}Ce înțelege AI din mesaj</h3><p class="tagline">Interpretare automată (Gemini). Nu este o verificare.</p>
       <dl><dt>Ce vrea de la tine</dt><dd>${esc(interp.wants_summary)}</dd>
       ${interp.claimed_sender && interp.claimed_sender.name ? `<dt>Se prezintă ca</dt><dd>${esc(interp.claimed_sender.name)} (neconfirmat)</dd>` : ''}</dl></section>`
    : `<section class="zone z-ai" aria-labelledby="z1"><h3 id="z1">${ICON.ai}Interpretarea AI</h3><p>Nu a fost disponibilă: ${esc(AI_FAIL[ai.failure || ai.status] || 'indisponibilă')}. Am folosit doar verificările locale.</p></section>`;
  const tech = [];
  if (c.urls_detected) tech.push(`Am analizat ${c.urls_analyzed} ${c.urls_analyzed === 1 ? 'link' : 'linkuri'} ca text, fără să ${c.urls_analyzed === 1 ? 'îl' : 'le'} deschidem.`);
  else tech.push('Mesajul nu conține linkuri.');
  tech.push(c.database === 'unavailable_static_fallback' ? 'Catalogul de domenii: am folosit lista de rezervă.' : 'Catalogul de domenii oficiale a fost consultat.');
  if (['threat_match', 'no_known_match', 'partial'].includes(c.threat_intelligence)) tech.push('Reputația linkurilor a fost căutată în Google Web Risk.');
  tech.push('Regulile locale pentru limba română au rulat.');
  const unv = ['Cine a trimis cu adevărat mesajul.'];
  if (c.urls_detected) unv.push('Ce conține pagina linkului și unde redirecționează.', 'Cine deține domeniul și de când există.');
  if (c.urls_detected && !['threat_match', 'no_known_match', 'partial'].includes(c.threat_intelligence)) unv.push('Reputația externă a linkurilor (serviciul nu este configurat sau adresa nu e eligibilă).');
  if (ai.status !== 'completed') unv.push(`Interpretarea AI (${esc(AI_FAIL[ai.failure || ai.status] || 'indisponibilă')}).`);
  if (ai.truncated) unv.push('Finalul unui mesaj foarte lung (AI a citit doar începutul).');
  if (c.ocr === 'transcribed_unverified') unv.push('Exactitatea textului citit din captură.');
  const html = aiZone +
    `<section class="zone z-tech" aria-labelledby="z2"><h3 id="z2">${ICON.tech}Ce am verificat tehnic</h3><ul>${tech.map(x => `<li>${x}</li>`).join('')}</ul></section>` +
    `<section class="zone z-unv" aria-labelledby="z3"><h3 id="z3">${ICON.unk}Ce nu am putut verifica</h3><ul>${unv.map(x => `<li>${x}</li>`).join('')}</ul></section>`;
  const sub = `${ai.status === 'completed' ? 'Interpretare AI' : 'Fără interpretare AI'} · ${tech.length} verificări tehnice · ${unv.length} lucruri neverificate`;
  return {html, sub};
}

/* ---------------------------------------------------------------- the restored risk scale (data from analysis.ui.spectrum only) */
function spectrumHtml(sp) {
  if (!sp || !sp.zones) return '';
  const placed = sp.status === 'placed';
  const zones = sp.zones.map(z => `<span class="${placed && z.key === sp.zone ? 'on' : ''}">${esc(z.label)}</span>`).join('');
  const note = placed ? `Indicator orientativ: ${esc(sp.indicator)} din 100, nu o probabilitate.` : sp.note;
  return `<div class="spectrum ${placed ? 'placed' : 'unplaced'}" data-role="spectrum" data-status="${esc(sp.status)}"${placed ? ` data-position="${esc(sp.position)}"` : ''}>
    <p class="sr">${esc(sp.label)}</p>
    <div class="sp-track" aria-hidden="true">${placed ? '<div class="sp-run"><span class="sp-marker"></span></div>' : ''}</div>
    <div class="sp-zones" aria-hidden="true">${zones}</div>
    <p class="sp-note" aria-hidden="true">${esc(note)}</p>
  </div>`;
}
function glideMarker(root) {
  const sp = root.querySelector('.spectrum.placed');
  if (!sp) return;
  const run = sp.querySelector('.sp-run'), pos = Math.max(0, Math.min(100, Number(sp.dataset.position)));
  if (reduce()) { run.style.setProperty('--to', pos + '%'); return; }
  run.style.setProperty('--to', '0%');
  requestAnimationFrame(() => requestAnimationFrame(() => run.style.setProperty('--to', pos + '%')));
}

/* ---------------------------------------------------------------- recovery inside the result: choose → steps */
function recoveryPanel(suggested) {
  const order = suggested || [];
  const items = [...$('recovery').querySelectorAll('details')].map(d => ({k: d.dataset.k, label: d.querySelector('summary').textContent.trim()}))
    .sort((x, y) => { const ix = order.indexOf(x.k), iy = order.indexOf(y.k); return (ix < 0 ? 99 : ix) - (iy < 0 ? 99 : iy); });
  return `<div class="rec-panel" id="recp" hidden>
    <p>Alege ce s-a întâmplat. Pașii apar aici, fără să pierzi rezultatul.</p>
    <div class="tiles" role="group" aria-label="Ce s-a întâmplat">${items.map(x => `<button class="tile" type="button" data-rk="${esc(x.k)}" aria-expanded="false" aria-controls="steps"><span>${esc(x.label)}</span>${order.includes(x.k) ? '<span class="fit">potrivit aici</span>' : ''}</button>`).join('')}</div>
    <div class="steps-out" id="steps" tabindex="-1" hidden></div>
  </div>`;
}
function showSteps(k, btn) {
  const src = $('recovery').querySelector(`details[data-k="${k}"]`), out = $('steps');
  const already = btn.getAttribute('aria-expanded') === 'true';
  document.querySelectorAll('#out .tile').forEach(t => t.setAttribute('aria-expanded', 'false'));
  if (already) { out.hidden = true; return; }
  btn.setAttribute('aria-expanded', 'true');
  out.innerHTML = `<h3>${esc(src.querySelector("summary").textContent.trim())}</h3>${src.querySelector('ol').outerHTML}<p class="always">${esc($('recovery').querySelector('.always').textContent.trim())}</p>`;
  out.hidden = false;
  out.classList.remove('swap'); void out.offsetWidth; if (!reduce()) out.classList.add('swap');
  out.scrollIntoView({block: 'nearest', behavior: reduce() ? 'auto' : 'smooth'});
}

/* ---------------------------------------------------------------- result */
function uiOf(a) {
  if (a.ui) return a.ui;  // older backends: minimal, truthful fallback from the label alone (no scale drawn)
  const st = STATE_OF[a.assessment.label] || 'unable';
  return {state: st, title: TITLES[st], reason: a.summary, action: a.headline.action, action_detail: '', recovery_suggested: st === 'no_clear_signs' ? [] : ['opened', 'code', 'paid'], partial: a.checks.semantic_ai.status !== 'completed', partial_note: null, mechanism: a.assessment.mechanism && a.assessment.mechanism.label, spectrum: null};
}
const disc = (id, title, sub, body, open, extra) =>
  `<details class="disc${extra ? ' ' + extra : ''}" id="${id}"${open ? ' open' : ''}><summary><span class="t">${title}</span>${sub ? `<span class="s">${sub}</span>` : ''}<span class="chev" aria-hidden="true">${ICON.chev}</span></summary><div class="body">${body}</div></details>`;

function render(r) {
  const a = r.analysis, s = a.assessment, u = uiOf(a);
  const alert = u.state === 'strong' || u.state === 'suspect';
  lastSpeech = [u.title, u.reason, 'Ce faci acum: ' + u.action, u.action_detail].filter(Boolean).join(' ');
  const ex = exhibit(r.text, a.highlights || []);
  const shareUrl = encodeURIComponent(a.share_text);
  const qual = alert && u.mechanism ? `Seamănă cu: ${u.mechanism.toLowerCase()}` : (u.qualifier || '');
  const recLabel = u.state === 'no_clear_signs' ? 'Ai apăsat totuși pe ceva? Vezi ce faci' : 'Am apăsat deja, am trimis date sau am plătit';

  // 1 · why
  const legend = ex.kinds.length ? `<p class="legend" aria-hidden="true">${ex.kinds.map(k => `<span><i class="l-${esc(k)}"></i>${esc(KIND[k] || k)}</span>`).join('')}</p>` : '';
  const whySub = ex.n ? `${ex.n} ${ex.n === 1 ? 'fragment marcat' : 'fragmente marcate'} în mesajul tău, cu explicații` : 'Mesajul tău, așa cum l-am citit';
  const whyBody = `<div class="ev-grid"><div><div class="exhibit" id="msg">${ex.html}</div></div><div class="ev-side">
      ${legend}
      ${ex.n ? `<ol class="notes" aria-label="Explicațiile fragmentelor">${ex.list}</ol>` : `<p>${a.checks.semantic_ai.status === 'completed' ? 'Nu am marcat fragmente: interpretarea nu a indicat părți relevante.' : 'Nu am marcat fragmente: fără analiza AI marcăm doar ce recunosc regulile locale.'}</p>`}
    </div></div>`;
  // 2 · link
  const urls = r.url_reports || [];
  const firstOk = urls.find(x => urlClass(x) !== 'invalid');
  const linkSub = urls.length === 1
    ? (firstOk ? `Duce pe <b>${esc(firstOk.registrable_domain || firstOk.domain)}</b> · ${esc(URL_WORD[urlClass(firstOk)])}` : esc(URL_WORD.invalid))
    : `${urls.length} linkuri: ${urls.map(x => x.domain ? `<b>${esc(x.registrable_domain || x.domain)}</b>` : 'o adresă ilizibilă').join(', ')}`;
  const linkBody = `<p class="disclaimer">Doar proprietarul domeniului real controlează pagina. Tot ce e scris înaintea lui poate fi ales de oricine.</p>${urls.map((x, i) => urlCard(x, a.domain_assessment, i, urls.length > 1)).join('')}`;
  // 3 · checked
  const prov = provenance(r, a);
  // advanced
  const scenario = a.scenario && alert ? disc('d-scen', 'Cum ar putea continua? <span class="sr">(exemplu ipotetic)</span>', 'Exemplu ipotetic, ca să recunoști pașii următori', `
      <p class="scenario-disc"><strong>Exemplu ipotetic, nu ce s-a întâmplat.</strong> ${esc(a.scenario.disclaimer)}</p>
      <ol class="story">${a.scenario.steps.map(x => `<li><b>${esc(x.title)}<span class="hyp">ipotetic</span></b><span>${esc(x.text)}</span></li>`).join('')}</ol>
      <p><strong>Cum arată varianta legitimă:</strong> ${esc(a.scenario.real_world)}</p>
      ${a.scenario.personalized_from && a.scenario.personalized_from.length ? `<p class="disclaimer">Adaptat după ce am găsit în mesaj: ${esc(a.scenario.personalized_from.join(', '))}. Restul pașilor sunt generali.</p>` : ''}`, false, 'mini') : '';
  const ledger = (a.evidence || []).map(e => `<tr><td>${esc(SOURCE[e.source] || e.source)}</td><td>${esc(STATUS[e.status] || e.status)}</td><td>${e.tier >= 70 ? 'ridicat' : e.tier >= 35 ? 'mediu' : e.tier > 0 ? 'scăzut' : '—'}</td><td>${esc(e.reason || e.label || '')}${e.quote ? ` <q>${esc(e.quote.length > 80 ? e.quote.slice(0, 80) + '…' : e.quote)}</q>` : ''}</td></tr>`).join('');
  const indicator = s.risk_estimate == null ? 'neestimat (dovezile sunt insuficiente sau contradictorii)' : `${s.risk_estimate} din 100. Rezumă puterea indiciilor găsite; nu este o probabilitate de fraudă.`;
  const tech = disc('d-tech', 'Detalii tehnice', 'Jurnalul dovezilor, pentru cine vrea să verifice', `
      <dl class="kv"><dt>Indicator intern</dt><dd>${esc(indicator)}</dd>
      <dt>Încredere în interpretare</dt><dd>${esc(CONF[s.confidence] || s.confidence)} (separată de nivelul de risc)</dd>
      ${s.mechanism ? `<dt>Mecanism</dt><dd>${esc(s.mechanism.label)}</dd>` : ''}
      <dt>Ce a rulat</dt><dd>${esc(a.engine_used)} · ${esc(a.timings_ms.analysis)} ms</dd></dl>
      ${a.uncertainties.length ? `<p><strong>Limite</strong></p><ul>${a.uncertainties.map(x => `<li>${esc(x)}</li>`).join('')}</ul>` : ''}
      ${ledger ? `<div class="tbl"><table class="ledger"><caption class="sr">Jurnalul dovezilor</caption><thead><tr><th scope="col">Sursă</th><th scope="col">Stare</th><th scope="col">Nivel</th><th scope="col">Explicație</th></tr></thead><tbody>${ledger}</tbody></table></div>` : ''}
      <p class="disclaimer">Interpretările AI contează doar dacă fragmentul citat se găsește în text. Faptele tehnice vin din analiza statică, catalog sau furnizorul de reputație.</p>`, false, 'mini');

  const out = $('out');
  out.innerHTML = `
  <article class="vcard v-${esc(u.state)}" aria-labelledby="res-h">
    <div class="v-head">
      <div class="v-top"><span class="mark">${MARKS[u.state]}</span><span class="eyebrow">${esc(EYEBROW[u.state])}</span></div>
      <h2 id="res-h" tabindex="-1">${esc(u.title)}</h2>
      ${qual ? `<p class="qual">${esc(qual)}</p>` : ''}
      ${spectrumHtml(u.spectrum)}
      <p class="reason">${esc(u.reason)}</p>
      ${u.partial ? `<p class="partial"><strong>Analiză parțială.</strong> ${esc(u.partial_note || 'Interpretarea AI nu a fost disponibilă.')}</p>` : ''}
    </div>
    <div class="v-act" data-role="action">
      <p class="k"><span class="slash" aria-hidden="true"></span>Ce faci acum</p>
      <p class="act">${esc(u.action)}</p>
      ${u.action_detail ? `<p class="act-d">${esc(u.action_detail)}</p>` : ''}
      <div data-role="recovery"><button class="btn rec-btn" type="button" id="recb" aria-expanded="false" aria-controls="recp"><span>${esc(recLabel)}</span><span class="chev" aria-hidden="true">${ICON.chev}</span></button></div>
    </div>
    ${recoveryPanel(u.recovery_suggested)}
    <div class="v-more">
      <button class="btn btn-ghost" type="button" id="nw">Verifică alt mesaj</button>
      ${alert ? `<a class="btn btn-ghost" target="_blank" rel="noopener noreferrer" href="https://wa.me/?text=${shareUrl}">Avertizează pe cineva</a>` : ''}
      <button class="btn btn-ghost" type="button" id="cp">Copiază rezumatul</button>
      <button class="btn btn-ghost" type="button" id="sp" hidden>Citește cu voce tare</button>
      <p class="note">Rezumatul copiat sau trimis nu conține textul mesajului, linkuri, numere sau coduri.</p>
    </div>
  </article>

  <div class="disc-list">
    <p class="lbl"><span class="slash" aria-hidden="true"></span>Vrei să înțelegi mai mult?</p>
    ${disc('d-why', 'De ce am ajuns la această concluzie?', esc(whySub), whyBody, alert)}
    ${urls.length ? disc('d-link', urls.length === 1 ? 'Ce știm despre link?' : 'Ce știm despre linkuri?', linkSub, linkBody, false) : ''}
    ${disc('d-chk', 'Ce am verificat și ce nu', esc(prov.sub), `<div class="zones">${prov.html}</div>`, false)}
    ${scenario}
    ${tech}
  </div>`;
  out.hidden = false;
  out.classList.remove('stale', 'enter');
  if (!reduce()) { void out.offsetWidth; out.classList.add('enter'); }
  glideMarker(out);

  out.querySelectorAll('details.disc').forEach(wireDisc);
  out.querySelectorAll('.ev').forEach(m => m.addEventListener('click', e => { e.preventDefault(); selectEvidence(m.dataset.k, 'mark'); }));
  out.querySelectorAll('.notes li[data-k]').forEach(li => li.addEventListener('click', e => {
    if (e.target.closest('a')) { e.preventDefault(); selectEvidence(li.dataset.k, 'note'); $('evm-' + li.dataset.k).focus({preventScroll: true}); return; }
    selectEvidence(li.dataset.k, 'note');
  }));
  out.querySelectorAll('[data-copy]').forEach(b => b.onclick = () => copy(b.dataset.copy, b));
  $('recb').onclick = e => { const open = e.currentTarget.getAttribute('aria-expanded') !== 'true'; e.currentTarget.setAttribute('aria-expanded', String(open)); reveal($('recp'), open); if (open && !reduce()) setTimeout(() => $('recp').scrollIntoView({block: 'nearest', behavior: 'smooth'}), MS.local); };
  out.querySelectorAll('.tile').forEach(t => t.onclick = () => showSteps(t.dataset.rk, t));
  $('cp').onclick = e => copy([a.share_text, '', 'Ce să faci: ' + u.action, u.action_detail].filter(x => x !== undefined).join('\n'), e.currentTarget);
  $('nw').onclick = () => { clearAll(); scrollTo({top: 0, behavior: reduce() ? 'auto' : 'smooth'}); $('t').focus({preventScroll: true}); };
  if (window.speechSynthesis) {
    $('sp').hidden = false;
    $('sp').onclick = e => { const synth = speechSynthesis; if (synth.speaking) { synth.cancel(); e.currentTarget.textContent = 'Citește cu voce tare'; return; } const ut = new SpeechSynthesisUtterance(lastSpeech); ut.lang = 'ro-RO'; ut.rate = 0.9; ut.onend = () => { $('sp') && ($('sp').textContent = 'Citește cu voce tare'); }; synth.speak(ut); e.currentTarget.textContent = 'Oprește citirea'; };
  }
  $('res-h').focus({preventScroll: true});
  out.scrollIntoView({block: 'start', behavior: reduce() ? 'auto' : 'smooth'});
  $('live').textContent = '';
  setTimeout(() => { $('live').textContent = `Rezultat: ${u.title}. Ce faci acum: ${u.action}`; }, 60);
}

function copy(s, b) {
  const t = b.textContent;
  const ok = () => { b.textContent = 'Copiat'; setTimeout(() => b.textContent = t, 1600); };
  const bad = () => { b.textContent = 'Copierea nu a mers'; setTimeout(() => b.textContent = t, 2000); };
  try { navigator.clipboard.writeText(s).then(ok, bad); } catch (e) { bad(); }
}
function syncClear() { $('cl').hidden = !$('t').value; }
function clearAll() {
  if (ctl && busy) ctl.abort('user');
  if (window.speechSynthesis) speechSynthesis.cancel();
  $('t').value = ''; $('out').hidden = true; $('out').innerHTML = ''; clearError(); $('busy').innerHTML = '';
  ocrMode = false; fileName = ''; $('ocrnote').hidden = true; paintChip(null); syncClear();
}

/* ---------------------------------------------------------------- opt-in history: never stores message text */
const HK = 'axa_history_v3';
function remember(r) {
  const h = store.get(HK, {on: false, items: []});
  if (!h.on) return;
  const u = uiOf(r.analysis);
  h.items.unshift({t: new Date().toISOString(), title: u.title, src: r.analysis.checks.ocr !== 'not_requested' ? 'captură' : 'text'});
  h.items = h.items.slice(0, 8); store.set(HK, h); showHistory();
}
function showHistory() {
  const h = store.get(HK, {on: false, items: []});
  $('hon').checked = !!h.on; $('hc').hidden = !h.items.length;
  $('hl').innerHTML = h.items.map(x => `<li>${esc(x.title)}<small>${esc(new Date(x.t).toLocaleString('ro-RO'))} · ${esc(x.src)}</small></li>`).join('');
}

/* ---------------------------------------------------------------- display preferences */
const Z = [100, 112.5, 125, 140, 160];
let zoom = Math.max(0, Math.min(4, store.get('axa_zoom', 0)));
const applyZoom = () => { document.documentElement.style.fontSize = Z[zoom] + '%'; $('fz').textContent = Z[zoom] + '%'; $('fm').disabled = zoom === 0; $('fp').disabled = zoom === 4; };
const applyTheme = (v, animate) => {
  const html = document.documentElement;
  if (animate && !reduce()) { html.classList.add('theme-anim'); setTimeout(() => html.classList.remove('theme-anim'), 380); }
  if (v === 'light' || v === 'dark') html.dataset.theme = v; else delete html.dataset.theme;
};
function setPanel(open) {
  const p = $('disp-panel');
  p.hidden = !open; $('disp').setAttribute('aria-expanded', String(open));
  p.classList.remove('opening'); if (open && !reduce()) { void p.offsetWidth; p.classList.add('opening'); }
}

/* ---------------------------------------------------------------- wiring */
$('form').addEventListener('submit', e => { e.preventDefault(); run(); });
$('cl').onclick = () => { clearAll(); $('t').focus(); };
$('up').onclick = () => $('file').click();
$('file').onchange = e => upload(e.target.files[0]);
$('t').addEventListener('keydown', e => { if (e.key === 'Enter' && (e.ctrlKey || e.metaKey)) { e.preventDefault(); run(); } });
$('t').addEventListener('input', () => { syncClear(); if ($('t').getAttribute('aria-invalid')) clearError(); });
$('t').addEventListener('paste', e => {
  const f = [...((e.clipboardData && e.clipboardData.files) || [])].find(x => /^image\//.test(x.type));
  if (f) { e.preventDefault(); upload(f); }
});
// Drag-and-drop a screenshot onto the desk.
let dragDepth = 0;
const desk = $('form');
const hasFile = e => e.dataTransfer && [...e.dataTransfer.types].includes('Files');
desk.addEventListener('dragenter', e => { if (!hasFile(e)) return; e.preventDefault(); dragDepth += 1; desk.classList.add('drag'); });
desk.addEventListener('dragover', e => { if (!hasFile(e)) return; e.preventDefault(); e.dataTransfer.dropEffect = 'copy'; });
desk.addEventListener('dragleave', () => { dragDepth = Math.max(0, dragDepth - 1); if (!dragDepth) desk.classList.remove('drag'); });
desk.addEventListener('drop', e => { if (!hasFile(e)) return; e.preventDefault(); dragDepth = 0; desk.classList.remove('drag'); upload(e.dataTransfer.files[0]); });
document.querySelectorAll('[data-p]').forEach(b => b.onclick = () => { ocrMode = false; fileName = ''; paintChip(null); $('ocrnote').hidden = true; $('t').value = EXAMPLES[+b.dataset.p]; syncClear(); run(); });
$('hon').onchange = e => { const h = store.get(HK, {on: false, items: []}); h.on = e.target.checked; if (!h.on) h.items = []; store.set(HK, h); showHistory(); };
$('hc').onclick = () => { store.del(HK); showHistory(); };
$('disp').onclick = () => setPanel($('disp-panel').hidden);
document.querySelectorAll('.menu-links a').forEach(a => a.addEventListener('click', () => setPanel(false)));
$('fm').onclick = () => { zoom = Math.max(0, zoom - 1); applyZoom(); store.set('axa_zoom', zoom); };
$('fp').onclick = () => { zoom = Math.min(4, zoom + 1); applyZoom(); store.set('axa_zoom', zoom); };
document.querySelectorAll('input[name=theme]').forEach(r => r.onchange = () => { applyTheme(r.value, true); store.set('axa_theme', r.value); });
const savedTheme = store.get('axa_theme', 'auto');
applyTheme(savedTheme);
const themeInput = document.querySelector(`input[name=theme][value="${savedTheme}"]`); if (themeInput) themeInput.checked = true;
document.addEventListener('keydown', e => { if (e.key === 'Escape' && !$('disp-panel').hidden) { setPanel(false); $('disp').focus(); } });
$('gdpr-revoke').onclick = () => { store.del(CK); showConsent(); $('gdpr-state').focus(); };
$('consent-info').onclick = () => $('consent').close('info');
applyZoom(); showHistory(); loadStatus(); syncClear(); showConsent();
})();
