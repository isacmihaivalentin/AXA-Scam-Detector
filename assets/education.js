/* AXA for Education — preview page behaviour. Static and local: no network requests, no storage
   of anything except the shared display preferences (theme, text size) the main page already uses. */
(function () {
'use strict';
const $ = id => document.getElementById(id);
const reduce = () => matchMedia('(prefers-reduced-motion: reduce)').matches;
const store = {
  get(k, d) { try { const v = localStorage.getItem(k); return v ? JSON.parse(v) : d; } catch (e) { return d; } },
  set(k, v) { try { localStorage.setItem(k, JSON.stringify(v)); } catch (e) { /* storage unavailable */ } }
};
document.body.classList.add('js');

/* ---------------------------------------------------------------- Afișare / Meniu (same keys and behaviour as the main page) */
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
$('disp').onclick = () => setPanel($('disp-panel').hidden);
document.querySelectorAll('.menu-links a').forEach(a => a.addEventListener('click', () => setPanel(false)));
$('fm').onclick = () => { zoom = Math.max(0, zoom - 1); applyZoom(); store.set('axa_zoom', zoom); };
$('fp').onclick = () => { zoom = Math.min(4, zoom + 1); applyZoom(); store.set('axa_zoom', zoom); };
document.querySelectorAll('input[name=theme]').forEach(r => r.onchange = () => { applyTheme(r.value, true); store.set('axa_theme', r.value); });
const savedTheme = store.get('axa_theme', 'auto');
applyTheme(savedTheme);
const themeInput = document.querySelector(`input[name=theme][value="${savedTheme}"]`); if (themeInput) themeInput.checked = true;
document.addEventListener('keydown', e => { if (e.key === 'Escape' && !$('disp-panel').hidden) { setPanel(false); $('disp').focus(); } });
applyZoom();

/* ---------------------------------------------------------------- the two-track conceptual preview */
const lab = $('previzualizare');
const tabs = [...lab.querySelectorAll('[role="tab"]')];
const panels = tabs.map(t => $(t.getAttribute('aria-controls')));
const STEP_MS = 1100;  // 3–4 observations: the whole lesson plays in under 5 s, once
let timer = null, current = null, visible = false, pending = true;

lab.querySelector('.lab-tabs').hidden = false;
lab.querySelector('.lab-ctrl').hidden = false;
panels.forEach((p, i) => { p.setAttribute('role', 'tabpanel'); p.setAttribute('aria-labelledby', tabs[i].id); p.tabIndex = 0; });

function paint(panel, step, total) {
  panel.querySelectorAll('.cue').forEach(c => { const n = +c.dataset.step; c.classList.toggle('on', n <= step); c.classList.toggle('now', n === step && step < total + 1 && lab.classList.contains('playing')); });
  panel.querySelectorAll('.notes-edu li').forEach(li => { const n = +li.dataset.step; li.classList.toggle('shown', n <= step); li.classList.toggle('now', n === step && lab.classList.contains('playing')); });
  const spec = panel.querySelector('.specimen');
  spec.classList.toggle('verify', panel.dataset.track === 'd' && step >= 4);
  spec.classList.toggle('s2', panel.dataset.track === 'd' && step >= 2);
}
function showAll(panel) {
  clearTimeout(timer); timer = null;
  lab.classList.remove('playing');
  const total = panel.querySelectorAll('.notes-edu li').length;
  paint(panel, total, total);
}
function play(panel) {
  clearTimeout(timer); timer = null;
  const total = panel.querySelectorAll('.notes-edu li').length;
  if (reduce()) { showAll(panel); return; }
  lab.classList.add('playing');
  let step = 0;
  paint(panel, 0, total);
  const next = () => {
    if (!visible) { showAll(panel); return; }  // never leave half a lesson behind offscreen
    step += 1;
    paint(panel, step, total);
    if (step < total) timer = setTimeout(next, STEP_MS);
    else timer = setTimeout(() => showAll(panel), STEP_MS);
  };
  timer = setTimeout(next, 350);
}
function select(i, focus) {
  tabs.forEach((t, j) => { t.setAttribute('aria-selected', String(i === j)); t.tabIndex = i === j ? 0 : -1; });
  panels.forEach((p, j) => {
    p.hidden = i !== j;
    // reset the inactive track completely: no stale highlights from the other lesson
    if (i !== j) { p.querySelectorAll('.on,.now,.shown,.verify,.s2').forEach(e => e.classList.remove('on', 'now', 'shown', 'verify', 's2')); p.querySelector('.specimen').classList.remove('verify', 's2'); }
  });
  current = panels[i];
  current.classList.remove('enter'); if (!reduce()) { void current.offsetWidth; current.classList.add('enter'); }
  if (focus) tabs[i].focus();
  const n = current.querySelectorAll('.notes-edu li').length;
  $('lab-status').textContent = `Lecția „${tabs[i].textContent.trim()}”: ${n} observații, exemplu fictiv.`;
  if (visible || !('IntersectionObserver' in window)) { pending = false; play(current); } else { pending = true; showAll(current); }
}
tabs.forEach((t, i) => {
  t.addEventListener('click', () => select(i, false));
  t.addEventListener('keydown', e => {
    const k = e.key; let j = null;
    if (k === 'ArrowRight' || k === 'ArrowDown') j = (i + 1) % tabs.length;
    if (k === 'ArrowLeft' || k === 'ArrowUp') j = (i - 1 + tabs.length) % tabs.length;
    if (k === 'Home') j = 0;
    if (k === 'End') j = tabs.length - 1;
    if (j !== null) { e.preventDefault(); select(j, true); }
  });
});
$('replay').onclick = () => { visible = true; play(current); };

// Play once when the preview comes into view; stop (showing everything) when it leaves.
if ('IntersectionObserver' in window) {
  new IntersectionObserver(entries => entries.forEach(en => {
    visible = en.isIntersecting;
    if (visible && pending) { pending = false; play(current); }
    if (!visible && lab.classList.contains('playing')) showAll(current);
  }), {threshold: 0.35}).observe(lab);
} else { visible = true; }
select(0, false);
})();
