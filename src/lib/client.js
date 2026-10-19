// Браузерная часть: индекс всех фильмов и сериалов, фильтры, «Хочу посмотреть».
import { cardHTML } from './format.js';

export const base = document.body.dataset.base || '/';

let indexPromise;
// индекс (~2 МБ, в сжатом виде ~600 КБ) грузится один раз и только там, где нужен
export function loadIndex() {
  if (!indexPromise)
    indexPromise = fetch(`${base}index.json`)
      .then((r) => r.json())
      .then(({ fields, rows }) => rows.map((r) => Object.fromEntries(fields.map((k, i) => [k, r[i]]))));
  return indexPromise;
}

export const norm = (s) => String(s || '').toLowerCase().replace(/ё/g, 'е');
const TR = { а: 'a', б: 'b', в: 'v', г: 'g', д: 'd', е: 'e', ж: 'zh', з: 'z', и: 'i', й: 'y', к: 'k', л: 'l', м: 'm', н: 'n', о: 'o', п: 'p', р: 'r', с: 's', т: 't', у: 'u', ф: 'f', х: 'h', ц: 'ts', ч: 'ch', ш: 'sh', щ: 'sch', ъ: '', ы: 'y', ь: '', э: 'e', ю: 'yu', я: 'ya' };
export const translit = (s) => [...s].map((c) => (c in TR ? TR[c] : c)).join('');

export function matches(f, { time = 999, mood = 'any', kind = 'any', genre = '', from = 0, to = 9999 }) {
  return f.min <= time
    && (mood === 'any' || f.m.includes(mood))
    && (kind === 'any' || (kind === 'series') === !!f.k)
    && (!genre || f.genres.includes(genre))
    && f.y >= from && f.y <= to;
}

export const SORTS = {
  pop: (a, b) => b.pp - a.pp,
  rating: (a, b) => (b.v * b.imdb + 6.8e5) / (b.v + 1e5) - (a.v * a.imdb + 6.8e5) / (a.v + 1e5),
  new: (a, b) => b.y - a.y || b.pp - a.pp,
};

// Сетка с кнопкой «Показать ещё»: первые first карточек сразу, дальше по step
export function pager(grid, button, left, list, { first = 18, step = 24 } = {}) {
  let shown = 0;
  const more = (n) => {
    const next = list.slice(shown, shown + n);
    grid.insertAdjacentHTML('beforeend', next.map((f, i) => cardHTML(f, base, i)).join(''));
    shown += next.length;
    const rest = list.length - shown;
    button.hidden = rest <= 0;
    button.textContent = 'Показать ещё ' + Math.min(step, rest);
    if (left) left.textContent = rest > 0 ? 'осталось ' + rest.toLocaleString('ru-RU') : '';
  };
  grid.innerHTML = '';
  button.onclick = () => more(step);
  more(first);
}

// «Хочу посмотреть» — пока в браузере; с аккаунтами переедет на сервер
const KEY = 'knv-watch';
export function watchlist() {
  try { return JSON.parse(localStorage.getItem(KEY) || '[]'); } catch { return []; }
}
export function toggleWatch(id) {
  const l = watchlist();
  const i = l.indexOf(id);
  i >= 0 ? l.splice(i, 1) : l.unshift(id);
  try { localStorage.setItem(KEY, JSON.stringify(l)); } catch {}
  return i < 0;
}
