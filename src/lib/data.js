// Данные сайта: читает data/films.js и data/syn/*.json (их собирает scripts/build_films.py)
// один раз за сборку и раздаёт страницам.
import fs from 'node:fs';
import path from 'node:path';

// сборка запускается из корня проекта (npm run build); путь от файла после сборки указывал бы в dist/
const ROOT = process.cwd();
const YEAR = new Date().getFullYear();

const TR = { а: 'a', б: 'b', в: 'v', г: 'g', д: 'd', е: 'e', ё: 'e', ж: 'zh', з: 'z', и: 'i', й: 'y', к: 'k', л: 'l', м: 'm', н: 'n', о: 'o', п: 'p', р: 'r', с: 's', т: 't', у: 'u', ф: 'f', х: 'h', ц: 'ts', ч: 'ch', ш: 'sh', щ: 'sch', ъ: '', ы: 'y', ь: '', э: 'e', ю: 'yu', я: 'ya' };

export function slugify(s) {
  return [...String(s).toLowerCase()].map((c) => (c in TR ? TR[c] : c)).join('')
    .normalize('NFKD').replace(/[̀-ͯ]/g, '')
    .replace(/[^a-z0-9]+/g, '-').replace(/^-+|-+$/g, '').slice(0, 80);
}

let cache;

export function load() {
  if (cache) return cache;
  const src = fs.readFileSync(path.join(ROOT, 'data/films.js'), 'utf8');
  const films = JSON.parse(src.slice(src.indexOf('['), src.lastIndexOf(']') + 1));

  const extra = {};
  const dir = path.join(ROOT, 'data/syn');
  for (const name of fs.readdirSync(dir)) {
    if (!name.endsWith('.json')) continue;
    for (const [id, x] of Object.entries(JSON.parse(fs.readFileSync(path.join(dir, name), 'utf8'))))
      extra[id] = typeof x === 'string' ? { s: x } : x;
  }

  // популярность: настоящая из TMDB, если есть, иначе приближение по IMDb
  const tmdbPop = films.some((f) => f.pop);
  const used = new Set();
  for (const f of films) {
    f.s = (f.v * f.imdb + 100000 * 6.8) / (f.v + 100000); // взвешенный рейтинг, как в топ-250 IMDb
    const last = f.ye || (f.k ? YEAR : f.y);
    f.pp = tmdbPop ? f.pop || 0 : f.v / Math.pow(Math.max(0, YEAR - last) + 1, 1.3);
    let slug = `${slugify(f.t) || slugify(f.o || '') || 'title'}-${f.y}`;
    if (used.has((f.k ? 's/' : 'f/') + slug)) slug += '-' + f.id.slice(2);
    used.add((f.k ? 's/' : 'f/') + slug);
    f.slug = slug;
    const x = extra[f.id] || {};
    f.syn = x.s || '';
    f.crew = (x.c || []).filter((c) => c[0]).map(([n, r, p]) => ({ n, r: r || '', p: p || '' }));
    f.sx = x.x || [];
    f.wp = x.w || null; // где посмотреть в России: {l, s, f, a, r, b}
    if (!f.crew.length) f.crew = (f.cast || []).map((c) => ({ n: c.n, r: c.r || '', p: '' }));
  }
  films.sort((a, b) => b.pp - a.pp);

  // актёры: страница у тех, кто есть хотя бы в трёх тайтлах базы (иначе сайт за 1 ГБ лимита Pages)
  const people = new Map();
  for (const f of films)
    f.crew.forEach((c, i) => {
      const key = slugify(c.n);
      if (!key) return;
      let a = people.get(key);
      if (!a) people.set(key, (a = { slug: key, n: c.n, p: '', roles: [], score: 0 }));
      if (!a.p && c.p) a.p = c.p;
      a.roles.push({ f, r: c.r, i });
      a.score += f.pp / (i + 1);
    });
  const actors = [...people.values()].filter((a) => a.roles.length >= 3).sort((a, b) => b.score - a.score);
  const actorBySlug = new Map(actors.map((a) => [a.slug, a]));
  for (const f of films) for (const c of f.crew) c.slug = actorBySlug.has(slugify(c.n)) ? slugify(c.n) : '';

  cache = { films, byId: new Map(films.map((f) => [f.id, f])), actors, actorBySlug };
  return cache;
}

// Похожие: общие жанры весят больше общих настроений, плюс бонус за рейтинг и тот же тип.
// Кандидаты — лучшие по рейтингу в каждом жанре, чтобы не сравнивать 15 тысяч со всеми.
let genreTop;
export function similar(f, n = 6) {
  const { films } = load();
  if (!genreTop) {
    genreTop = new Map();
    for (const x of [...films].sort((a, b) => b.s - a.s))
      for (const g of x.genres) {
        const l = genreTop.get(g) || genreTop.set(g, []).get(g);
        if (l.length < 400) l.push(x);
      }
  }
  const cand = new Set();
  for (const g of f.genres) for (const x of genreTop.get(g) || []) cand.add(x);
  const score = (x) => x.genres.filter((g) => f.genres.includes(g)).length * 2 + x.m.filter((m) => f.m.includes(m)).length + (x.s - 7) * 2 + (!x.k === !f.k ? 3 : 0);
  return [...cand].filter((x) => x.id !== f.id).map((x) => [score(x), x]).sort((a, b) => b[0] - a[0]).slice(0, n).map((x) => x[1]);
}

export const COLLECTIONS = [
  { slug: 'komedii-na-poltora-chasa', title: 'Комедии на полтора часа', sub: 'Успеете до конца вечера', hue: 36,
    pick: (f) => !f.k && f.m.includes('laugh') && f.min <= 105, sort: 's' },
  { slug: 'serialy-na-odin-vecher', title: 'Сериалы на один вечер', sub: 'Мини-сериалы до пяти часов', hue: 215,
    pick: (f) => f.k === 'ms' && f.ep && f.ep * f.min <= 300, sort: 's' },
  { slug: 'novinki', title: 'Новинки', sub: `Вышли в ${YEAR - 1}–${YEAR}`, hue: 160,
    pick: (f) => (f.k ? f.y : f.y) >= YEAR - 1, sort: 'pp' },
  { slug: 'zavershyonnye-serialy', title: 'Сериалы, которые можно досмотреть', sub: 'Завершены, рейтинг от 8', hue: 280,
    pick: (f) => f.k === 's' && (f.ts === 'Ended' || (!f.ts && f.ye && !f.ann)) && f.imdb >= 8, sort: 's' },
  { slug: 'trillery', title: 'Понервничать за два часа', sub: 'Триллеры и детективы', hue: 350,
    pick: (f) => !f.k && f.m.includes('nerve') && f.min <= 120, sort: 's' },
  { slug: 'korotkie-serii', title: 'Короткие серии', sub: 'Комедийные сериалы по полчаса', hue: 50,
    pick: (f) => f.k && f.min <= 30 && f.m.includes('laugh'), sort: 's' },
  { slug: 'dlya-vsey-semi', title: 'Для всей семьи', sub: 'Мультфильмы и семейное кино', hue: 120,
    pick: (f) => f.genres.includes('семейный'), sort: 's' },
  { slug: 'klassika', title: 'Классика с рейтингом 8+', sub: 'Фильмы до 1980 года', hue: 20,
    pick: (f) => !f.k && f.y < 1980 && f.imdb >= 8, sort: 's' },
];

export function collection(c, limit = 120) {
  return load().films.filter(c.pick).sort((a, b) => b[c.sort] - a[c.sort]).slice(0, limit);
}

// Лёгкий индекс для браузера: подбор, каталог, поиск, избранное. Массивы вместо объектов — так втрое меньше.
export const INDEX_FIELDS = ['id', 'slug', 't', 'o', 'y', 'k', 'min', 'm', 'genres', 'imdb', 'v', 'pp', 'p', 'ss', 'ye', 'ann', 'ts', 'la', 'ep', 'd'];
export function indexRows() {
  return load().films.map((f) => INDEX_FIELDS.map((k) => (k === 'pp' ? Math.round(f.pp * 10) / 10 : f[k] ?? 0)));
}
