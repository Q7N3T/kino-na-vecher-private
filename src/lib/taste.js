// Вкус зрителя: что он открывал, добавлял в «Мой список» и выбирал «Смотрю сегодня».
// Всё хранится только в этом браузере. Из истории собирается профиль — жанры, настроения,
// фильм или сериал, десятилетия, режиссёры, — и подбор поднимает похожее по духу,
// а не точное совпадение жанров: схожесть смешивается с рейтингом и популярностью.

const KEY = 'knv-taste';
const WEIGHT = { view: 1, watch: 3, tonight: 4 };
const HALF_LIFE = 21 * 864e5; // старые действия весят меньше: вдвое за три недели
const MAX_EVENTS = 300;

function read() {
  try { return JSON.parse(localStorage.getItem(KEY) || '[]'); } catch { return []; }
}

export function record(id, kind = 'view') {
  const ev = read().filter((e) => !(e.id === id && e.k === kind)); // повторный просмотр той же страницы — освежаем, а не копим
  ev.push({ id, k: kind, t: Date.now() });
  try { localStorage.setItem(KEY, JSON.stringify(ev.slice(-MAX_EVENTS))); } catch {}
}

export function forget() {
  try { localStorage.removeItem(KEY); localStorage.removeItem('knv-daily'); } catch {}
}

const dec = (y) => Math.floor(y / 10) * 10;
const bump = (m, k, w) => m.set(k, (m.get(k) || 0) + w);
const norm = (m) => { const mx = Math.max(0, ...m.values()); if (mx) for (const [k, v] of m) m.set(k, v / mx); return m; };

// Профиль: веса жанров, настроений, типа, десятилетий и режиссёров; confidence — насколько ему верить
export function profile(byId) {
  const now = Date.now();
  const p = { g: new Map(), m: new Map(), k: new Map(), y: new Map(), d: new Map(), seen: new Set(), picked: new Set(), n: 0 };
  for (const e of read()) {
    const f = byId.get(e.id);
    if (!f) continue;
    const w = WEIGHT[e.k] * Math.pow(0.5, (now - e.t) / HALF_LIFE);
    p.n += WEIGHT[e.k];
    p.seen.add(f.id);
    if (e.k === 'tonight') p.picked.add(f.id);
    for (const g of f.genres) bump(p.g, g, w / f.genres.length);
    for (const m of f.m) bump(p.m, m, w / Math.max(1, f.m.length));
    bump(p.k, f.k ? 's' : 'm', w);
    bump(p.y, dec(f.y), w);
    for (const d of f.d || []) bump(p.d, d, w);
  }
  [p.g, p.m, p.k, p.y, p.d].forEach(norm);
  p.confidence = Math.min(1, p.n / 10); // после пары-тройки действий подбор начинает заметно подстраиваться
  return p;
}

// Насколько тайтл похож на вкус, от 0 до 1. Частичное совпадение жанров даёт частичный балл.
export function affinity(f, p) {
  if (!p.n) return 0;
  const gs = f.genres.map((g) => p.g.get(g) || 0);
  const ms = f.m.map((m) => p.m.get(m) || 0);
  const g = gs.length ? 0.6 * Math.max(...gs) + 0.4 * gs.reduce((a, b) => a + b, 0) / gs.length : 0;
  const m = ms.length ? Math.max(...ms) : 0;
  const k = p.k.get(f.k ? 's' : 'm') || 0;
  const d0 = dec(f.y);
  const y = Math.max(p.y.get(d0) || 0, 0.5 * (p.y.get(d0 - 10) || 0), 0.5 * (p.y.get(d0 + 10) || 0));
  const d = (f.d || []).some((x) => p.d.has(x)) ? 1 : 0;
  return 0.45 * g + 0.2 * m + 0.1 * k + 0.1 * y + 0.15 * d;
}
