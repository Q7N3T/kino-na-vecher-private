// Подсказки при наборе в поиске: отдельно актёры, фильмы и сериалы — по нескольку лучших.
// Сначала то, что начинается с запроса, потом где с запроса начинается слово, потом остальное;
// при равенстве — популярное. Работает и в браузере, и в Node (тесты).
import { norm, translit } from './format.js';

// 0 — название начинается с запроса, 1 — с него начинается слово, 2 — просто содержит; null — нет
function rank(text, qs) {
  const s = norm(text);
  let best = null;
  for (const q of qs) {
    const i = s.indexOf(q);
    if (i < 0) continue;
    const r = i === 0 ? 0 : /[\s\-:.,«"(]/.test(s[i - 1]) ? 1 : 2;
    if (best === null || r < best) best = r;
  }
  return best;
}

// films — индекс (index.json), actors — разобранные строки aktery.json в их порядке (по известности)
export function suggest(raw, films, actors, { n = 4, nActors = 3 } = {}) {
  const q = norm(raw).trim();
  if (q.length < 2) return { q, actors: [], movies: [], series: [] };
  const qs = [...new Set([q, translit(q)])];
  const titles = [];
  for (const f of films) {
    const r = Math.min(rank(f.t, qs) ?? 9, rank(f.o, qs) ?? 9);
    if (r < 9) titles.push({ f, r });
  }
  titles.sort((a, b) => a.r - b.r || b.f.pp - a.f.pp);
  const people = [];
  actors.forEach((a, i) => { const r = rank(a.n, qs); if (r !== null) people.push({ a, r, i }); });
  people.sort((x, y) => x.r - y.r || x.i - y.i);
  return {
    q,
    actors: people.slice(0, nActors).map((x) => x.a),
    movies: titles.filter((x) => !x.f.k).slice(0, n).map((x) => x.f),
    series: titles.filter((x) => x.f.k).slice(0, n).map((x) => x.f),
  };
}

// выделить совпадение в названии: «Тёмный <mark>рыц</mark>арь»
export function mark(text, raw, esc) {
  const q = norm(raw).trim(), s = norm(text);
  const i = q ? s.indexOf(q) : -1;
  if (i < 0) return esc(text);
  return esc(text.slice(0, i)) + '<mark>' + esc(text.slice(i, i + q.length)) + '</mark>' + esc(text.slice(i + q.length));
}
