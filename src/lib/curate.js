// Подборка «на сегодня»: не просто самое популярное, а смесь проверенных хитов, находок
// (высокий рейтинг при небольшой известности) и — если есть история — того, что по вкусу.
// Плюс разнообразие: одна франшиза — одно место, похожие подряд не идут.
// Работает и в браузере, и в Node (для проверки на всей базе).

import { affinity } from './taste.js';

const clamp = (x, a = 0, b = 1) => Math.max(a, Math.min(b, x));

// Рейтинг с небольшой поправкой на число оценок: в отличие от топ-250 IMDb (поправка 100 тыс.)
// не душит фильмы с 15–50 тыс. оценок — среди них и прячутся находки
export const rating = (f) => (f.v * f.imdb + 25000 * 6.9) / (f.v + 25000);
const quality = (f) => clamp((rating(f) - 6.6) / 2.4);

// Насколько настроение — главное в тайтле: чистая комедия «смешнее» драмы с юмором
function moodFit(f, mood) {
  if (mood === 'any') return 1;
  if (!f.m.includes(mood)) return 0;
  return 0.45 + 0.55 / f.m.length;
}

// Насколько длительность заполняет свободное время: фильм на 70 минут при двух часах — так себе
function timeFit(f, time) {
  if (f.k) return 0.8; // у сериала время считается по серии — смотрят сколько успеют
  if (time >= 999) return clamp(0.6 + (f.min - 90) / 150, 0.6, 1); // весь вечер — можно и эпопею
  const r = f.min / time;
  return clamp(1 - Math.abs(0.88 - r) * 1.6);
}

// Франшиза: «Матрица: Перезагрузка», «Крёстный отец 2», «Чужой 3» → одна и та же
export function franchise(f) {
  return f.t.toLowerCase().replace(/ё/g, 'е')
    .replace(/[:.!?—–-].*$/, '')
    .replace(/\s+(\d+|[ivx]+|часть\s+\S+)$/i, '')
    .trim();
}

// Похожесть двух тайтлов для разнообразия ленты: франшиза, режиссёр, тот же набор жанров и десятилетие
const sameFranchise = (x, y) => x === y || (Math.min(x.length, y.length) >= 5 && (x.startsWith(y + ' ') || y.startsWith(x + ' ')));

function sameness(a, b) {
  if (sameFranchise(franchise(a), franchise(b))) return 1;
  if ((a.d || []).some((x) => (b.d || []).includes(x))) return 0.8;
  const ga = new Set(a.genres), inter = b.genres.filter((g) => ga.has(g)).length;
  const jac = inter / (ga.size + b.genres.length - inter || 1);
  return jac * 0.6 + (Math.floor(a.y / 10) === Math.floor(b.y / 10) ? 0.2 : 0) + (!a.k === !b.k ? 0.1 : 0);
}

function rng(seed) {
  let h = 2166136261;
  for (const c of seed) h = Math.imul(h ^ c.charCodeAt(0), 16777619);
  return () => {
    h += 0x6d2b79f5;
    let t = h;
    t = Math.imul(t ^ (t >>> 15), t | 1);
    t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

// Главная функция. list — уже отфильтрованное по времени, настроению и типу.
// Возвращает { items: [{ f, why }], rest } — 12 отобранных с пометкой, откуда они, и всё остальное.
export function curate(list, { time = 999, mood = 'any', prof = null, day = '', n = 12 } = {}) {
  if (!list.length) return { items: [], rest: [] };
  const rand = rng(day + '|' + time + '|' + mood);
  const maxPop = Math.log1p(Math.max(1, ...list.map((f) => f.pp)));
  const pop = (f) => Math.log1p(f.pp) / maxPop;
  const hasTaste = prof && prof.n > 0;
  const seen = hasTaste ? prof.seen : new Set();
  // скромный порог качества: в подборку не попадает то, за что стыдно
  const ok = list.filter((f) => rating(f) >= 6.6 && !seen.has(f.id));
  const pool = ok.length >= n ? ok : list;

  const fit = (f) => moodFit(f, mood) * 0.6 + timeFit(f, time) * 0.4;
  const jitter = new Map(pool.map((f) => [f.id, rand()]));
  const year = new Date().getFullYear();
  const score = {
    // хиты — запасной вариант, когда других не хватает: качество и известность
    hit: (f) => 0.5 * quality(f) + 0.3 * pop(f) + 0.2 * fit(f) + 0.04 * jitter.get(f.id),
    // свежее и громкое: последние пять лет, хорошо оценено и на слуху
    fresh: (f) => 0.45 * quality(f) + 0.35 * pop(f) + 0.2 * fit(f) + 0.06 * jitter.get(f.id),
    // классика: до 2000 года, с сильным рейтингом; каждый день — другая
    classic: (f) => 0.6 * quality(f) + 0.15 * pop(f) + 0.25 * fit(f) + 0.1 * jitter.get(f.id),
    // находки: сильный рейтинг при небольшой известности; меняются каждый день
    gem: (f) => (0.55 * quality(f) + 0.25 * fit(f)) * (1.15 - pop(f)) + 0.25 * jitter.get(f.id),
    // по вкусу: схожесть с историей, но тоже не ниже приличного качества
    taste: (f) => (hasTaste ? 0.65 * affinity(f, prof) : 0) + 0.25 * quality(f) + 0.1 * fit(f) + 0.03 * jitter.get(f.id),
  };
  // находка — заметно менее известное, чем хиты, но хорошо оценённое. С русским названием и от 20 тыс.
  // оценок: так отсеиваются рейтинги, накрученные национальным голосованием, и то, чего у нас не найти.
  // Документальное — только когда хочется подумать или вдохновиться.
  const popCut = pop([...pool].sort((a, b) => b.pp - a.pp)[Math.min(pool.length - 1, 40)]);
  const ru = (f) => /[а-яё]/i.test(f.t);
  const docOk = (f) => !f.genres.includes('документальный') || mood === 'think' || mood === 'inspire';
  const isGem = (f) => pop(f) < popCut && f.imdb >= 7.3 && f.v >= 20000 && ru(f) && docOk(f);
  const sorted = (xs, k) => xs.sort((a, b) => score[k](b) - score[k](a));

  const ranked = {
    hit: sorted([...pool], 'hit'),
    fresh: sorted(pool.filter((f) => f.y >= year - 5 && rating(f) >= 7 && ru(f) && docOk(f)), 'fresh'),
    classic: sorted(pool.filter((f) => f.y < 2000 && f.imdb >= 7.8 && ru(f) && docOk(f)), 'classic'),
    gem: sorted(pool.filter(isGem), 'gem'),
    taste: hasTaste ? sorted([...pool], 'taste') : [],
  };
  // порядок мест в ленте: больше всего находок, немного свежего и классики, «по вкусу» — когда есть история
  const plan = hasTaste
    ? ['taste', 'gem', 'fresh', 'taste', 'gem', 'classic', 'taste', 'gem', 'fresh', 'gem', 'taste', 'gem']
    : ['fresh', 'gem', 'gem', 'classic', 'fresh', 'gem', 'gem', 'fresh', 'gem', 'classic', 'gem', 'gem'];

  const chosen = [], used = new Set(), seenFr = [];
  const take = (kind) => {
    const src = ranked[kind].length ? ranked[kind] : ranked.hit;
    let best = null, bestScore = -Infinity;
    // смотрим первых 25 свободных и берём лучшего с поправкой на непохожесть на уже выбранные
    let looked = 0;
    for (const f of src) {
      if (used.has(f.id) || seenFr.some((x) => sameFranchise(x, franchise(f)))) continue;
      const sim = chosen.slice(-4).reduce((m, c) => Math.max(m, sameness(f, c.f)), 0);
      const s = score[src === ranked[kind] ? kind : 'hit'](f) - 0.35 * sim;
      if (s > bestScore) { best = f; bestScore = s; }
      if (++looked >= 25) break;
    }
    if (best) {
      chosen.push({ f: best, why: src === ranked[kind] ? kind : 'hit' });
      used.add(best.id);
      seenFr.push(franchise(best));
    }
  };
  for (const kind of plan.slice(0, n)) take(kind);

  const rest = list.filter((f) => !used.has(f.id)).sort((a, b) => score.hit(b) - score.hit(a));
  return { items: chosen, rest };
}

// Из кого выбирается выбор дня: до четырёх лучших находок (или «по вкусу») с рейтингом от 7,2.
// Уже выбранное раньше не предлагаем; открытое — только если отложено в «Мой список».
export function dailyCandidates(list, { time = 999, mood = 'any', prof = null, watch = [], day = '' } = {}) {
  const wl = new Set(watch);
  const seen = prof?.seen || new Set(), picked = prof?.picked || new Set();
  const cand = list.filter((f) => f.imdb >= 7.2 && !picked.has(f.id) && (wl.has(f.id) || !seen.has(f.id)));
  // curate прячет всё открытое раньше — отложенное в «Мой список» для выбора дня открытым не считаем
  const forPick = prof && { ...prof, seen: new Set([...seen].filter((id) => !wl.has(id) || picked.has(id))) };
  const { items } = curate(cand, { time, mood, prof: forPick, day: day + '|pick' });
  const best = items.filter((x) => x.why === 'gem' || x.why === 'taste');
  return (best.length ? best : items).slice(0, 4).map((x) => x.f);
}

// Выбор дня: меняется в полночь по времени зрителя, при тех же фильтрах весь день один и тот же.
// Обычно это находка (или по вкусу) — что-то, о чём человек мог не знать.
export function dailyPick(list, { time = 999, mood = 'any', kind = 'any', prof = null, watch = [] } = {}) {
  const day = new Date().toDateString();
  const key = `${time}|${mood}|${kind}`;
  const store = typeof localStorage === 'undefined' ? null : localStorage;
  let saved = {};
  try { saved = JSON.parse(store?.getItem('knv-daily') || '{}'); } catch {}
  if (saved.day !== day) saved = { day };
  const keep = saved[key] && list.find((f) => f.id === saved[key]);
  if (keep) return keep;

  const from = dailyCandidates(list, { time, mood, prof, watch, day });
  if (!from.length) return null;
  const f = from[Math.floor(rng(day + key)() * from.length)];
  saved[key] = f.id;
  try { store?.setItem('knv-daily', JSON.stringify(saved)); } catch {}
  return f;
}

// «Популярное сейчас»: самое обсуждаемое по TMDB, но не ниже 7 на IMDb — сайт обещает хорошее, а не поток.
// exclude — уже показанное выше на странице; kind — 'any' | 'movie' | 'series'.
export function popularNow(list, { kind = 'any', exclude = new Set(), n = 12 } = {}) {
  return list
    .filter((f) => f.imdb >= 7 && !exclude.has(f.id) && (kind === 'any' || (kind === 'series') === !!f.k))
    .sort((a, b) => b.pp - a.pp)
    .slice(0, n);
}
