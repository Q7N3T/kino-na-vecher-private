// Всплывающие подсказки под полем поиска: «Актёры», «Фильмы», «Сериалы» — отдельными группами,
// внизу «Все результаты». Стрелки ↑↓ выбирают, Enter открывает, Esc закрывает.
// Индекс и актёры грузятся при первом фокусе в поле — не на каждой странице заранее.
import { loadIndex, base } from './client.js';
import { suggest, mark } from './suggest.js';
import { esc, hue, initials, plural, tmdbImg, years } from './format.js';

let actors;
const loadActors = () => (actors ||= fetch(`${base}aktery.json`).then((r) => r.json())
  .then((rows) => rows.map(([n, slug, p, , total, y0, y1]) => ({ n, slug, p, total, y0, y1 }))));

const img = (p, w, size) => (p ? `<img src="${tmdbImg(p, w, size)}" alt="" loading="lazy" onerror="knvImg(this)">` : '');

function actorHTML(a, q) {
  const yrs = a.y0 === a.y1 ? a.y0 : `${a.y0}–${a.y1}`;
  return `<a class="sg-i" role="option" href="${base}akter/${a.slug}/">
    <span class="sg-av" style="--h:${hue(a.n)}"><b aria-hidden="true">${esc(initials(a.n))}</b>${img(a.p, 80, 'w185')}</span>
    <span class="sg-t"><b>${mark(a.n, q, esc)}</b><small>${a.total} ${plural(a.total, 'тайтл', 'тайтла', 'тайтлов')} · ${yrs}</small></span></a>`;
}

function titleHTML(f, q) {
  const alt = f.o && f.o !== f.t ? ` · ${esc(f.o)}` : '';
  return `<a class="sg-i" role="option" href="${base}${f.k ? 'serial' : 'film'}/${f.slug}/">
    <span class="sg-p">${img(f.p, 64, 'w92')}</span>
    <span class="sg-t"><b>${mark(f.t, q, esc)}</b><small>${years(f)}${f.imdb ? ` · IMDb ${f.imdb.toFixed(1)}` : ''}${alt}</small></span></a>`;
}

export function attachSuggest(input) {
  if (!input) return;
  const form = input.form;
  const box = document.createElement('div');
  box.className = 'sugg';
  box.id = input.id + '-sugg';
  box.setAttribute('role', 'listbox');
  box.hidden = true;
  form.append(box);
  input.setAttribute('role', 'combobox');
  input.setAttribute('aria-controls', box.id);
  input.setAttribute('aria-expanded', 'false');
  input.setAttribute('aria-autocomplete', 'list');

  let active = -1, timer, data;
  const items = () => [...box.querySelectorAll('[role="option"]')];
  const open = (on) => { box.hidden = !on; input.setAttribute('aria-expanded', String(on)); if (!on) setActive(-1); };
  const setActive = (i) => {
    const all = items();
    active = i < 0 || !all.length ? -1 : i % all.length;
    all.forEach((el, j) => { el.classList.toggle('on', j === active); el.id = `${box.id}-${j}`; });
    if (active >= 0) { input.setAttribute('aria-activedescendant', all[active].id); all[active].scrollIntoView({ block: 'nearest' }); }
    else input.removeAttribute('aria-activedescendant');
  };
  const load = () => (data ||= Promise.all([loadIndex(), loadActors()]));

  async function render() {
    const raw = input.value;
    if (raw.trim().length < 2) return open(false);
    if (!box.innerHTML) { box.innerHTML = '<p class="sg-empty">Ищем…</p>'; open(true); }
    const [films, ppl] = await load();
    if (raw !== input.value) return; // пока грузилось, набрали дальше
    const s = suggest(raw, films, ppl);
    const group = (h, list, html) => (list.length ? `<div class="sg-g"><p class="sg-h">${h}</p>${list.map((x) => html(x, raw)).join('')}</div>` : '');
    const body = group('Актёры', s.actors, actorHTML) + group('Фильмы', s.movies, titleHTML) + group('Сериалы', s.series, titleHTML);
    box.innerHTML = (body || '<p class="sg-empty">Ничего не нашлось</p>')
      + `<a class="sg-all" role="option" href="${base}poisk/?q=${encodeURIComponent(raw.trim())}">Все результаты для «${esc(raw.trim())}»</a>`;
    active = -1;
    open(true);
  }

  input.addEventListener('focus', () => { load(); if (input.value.trim().length >= 2) render(); });
  input.addEventListener('input', () => { clearTimeout(timer); timer = setTimeout(render, 90); });
  input.addEventListener('keydown', (e) => {
    if (box.hidden) return;
    if (e.key === 'ArrowDown') { e.preventDefault(); setActive(active + 1); }
    else if (e.key === 'ArrowUp') { e.preventDefault(); setActive(active < 0 ? items().length - 1 : active - 1); } // с первой — обратно в поле
    else if (e.key === 'Enter' && active >= 0) { e.preventDefault(); items()[active].click(); }
    else if (e.key === 'Escape') { open(false); }
  });
  // клик мимо — закрыть; по подсказке — переход по ссылке (mousedown не уводит фокус раньше клика)
  box.addEventListener('mousedown', (e) => e.preventDefault());
  document.addEventListener('click', (e) => { if (!form.contains(e.target)) open(false); });
  input.addEventListener('blur', () => setTimeout(() => { if (!form.contains(document.activeElement)) open(false); }, 150));
}
