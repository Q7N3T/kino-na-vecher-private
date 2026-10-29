// Куда ведут кнопки кинотеатров. По порядку:
// 1) партнёрская ссылка — когда кинотеатр или партнёрская сеть выдаст её, впишите в PARTNERS
//    по номеру провайдера TMDB: {q} — название фильма, {id} — номер IMDb, {slug} — оригинальное
//    название латиницей без пробелов и знаков (так устроены адреса FLEX: kinoflex.ru/movie/thesopranos);
// 2) страница фильма на сайте кинотеатра: Кинопоиск — по номеру из Wikidata (f.kp), FLEX, Иви,
//    Start и KION — из их карт сайта (f.ln, собирает scripts/cinemas.py);
// 3) поиск этого фильма прямо на сайте кинотеатра (SEARCH) — по русскому названию;
// 4) страница «Где посмотреть» TMDB / JustWatch — для остальных.
// Номер провайдера — в data/syn/*.json: w → [номер, название, логотип].
// Адреса поиска собраны вручную и могут поменяться на стороне кинотеатра — проверяйте кликом.
export const PARTNERS = {};

// прямая страница фильма, когда кинотеатр известен по номеру из открытых данных:
// Кинопоиск — номер из Wikidata (P2603), его подтягивает scripts/build_films.py в поле kp
const DIRECT = {
  117: (f) => f.kp && `https://www.kinopoisk.ru/film/${f.kp}/`,
};
// кинотеатры, чьи страницы фильмов найдены в карте сайта (f.ln по этим ключам), — как они называются
const SITEMAP = { flex: 'FLEX', ivi: 'Иви', start: 'Start', kion: 'KION', premier: 'Premier' };
const sitemapKey = (name) => ({ иви: 'ivi', ivi: 'ivi', kion: 'kion', start: 'start', flex: 'flex', premier: 'premier' })[name.toLowerCase()];

const SEARCH = {
  117: ['Кинопоиск', 'https://www.kinopoisk.ru/index.php?kp_query={q}'],
  115: ['Okko', 'https://okko.tv/search/{q}'],
  557: ['More TV', 'https://more.tv/search?query={q}'],
  570: ['Premier', 'https://premier.one/search?query={q}'],
  116: ['Амедиатека', 'https://www.amediateka.ru/search?q={q}'],
  577: ['Tvigle', 'https://www.tvigle.ru/search/?q={q}'],
  2: ['Apple TV', 'https://tv.apple.com/ru/search?term={q}'],
  350: ['Apple TV', 'https://tv.apple.com/ru/search?term={q}'],
  3: ['Google Play', 'https://play.google.com/store/search?q={q}&c=movies'],
  11: ['MUBI', 'https://mubi.com/ru/search/films?query={q}'],
  283: ['Crunchyroll', 'https://www.crunchyroll.com/ru/search?q={q}'],
};
// кинотеатр в данных TMDB под незнакомым номером — узнаём по названию
const BY_NAME = {
  'кинопоиск': 'https://www.kinopoisk.ru/index.php?kp_query={q}', 'kinopoisk': 'https://www.kinopoisk.ru/index.php?kp_query={q}',
  'иви': 'https://www.ivi.ru/search/?q={q}', 'ivi': 'https://www.ivi.ru/search/?q={q}',
  'wink': 'https://wink.ru/search?query={q}', 'kion': 'https://kion.ru/search?text={q}', 'start': 'https://start.ru/search?q={q}',
};
const slug = (f) => String(f.o || f.t).toLowerCase().replace(/[^a-z0-9]+/g, '');
const fill = (t, f) => t.replaceAll('{q}', encodeURIComponent(f.t)).replaceAll('{id}', f.id).replaceAll('{slug}', slug(f));
const direct = (f, providerId, name = '') => DIRECT[providerId]?.(f) || f.ln?.[sitemapKey(name)];

// название для людей: по-русски, если кинотеатр знаком (TMDB пишет «Kinopoisk», «Amediateka»)
export const providerName = (providerId, name) => SEARCH[providerId]?.[0] || name;

export function watchLink(f, providerId, name = '') {
  if (!PARTNERS[providerId] && direct(f, providerId, name)) return direct(f, providerId, name);
  const t = PARTNERS[providerId] || SEARCH[providerId]?.[1] || BY_NAME[name.toLowerCase()];
  return t ? fill(t, f) : f.wp.l;
}

// Строки блока «Где посмотреть» — только кинотеатры, где тайтл можно посмотреть: есть в данных
// JustWatch или его страница нашлась в каталоге самого кинотеатра (FLEX, Иви, KION…; страница
// Кинопоиска по номеру из Wikidata — не значит, что там можно смотреть, — отдельно не показываем).
// Один кинотеатр — одна строка со всеми способами.
// logos — логотипы кинотеатров по номеру, собранные по всей базе; icons — свои логотипы тех, кого
// нет в TMDB (ключ → файл в public/logos): строка получает icon, его показывают вместо буквы.
const KINDS = [['s', 'по подписке'], ['f', 'бесплатно'], ['a', 'бесплатно с рекламой'], ['r', 'аренда'], ['b', 'покупка']];
const cap = (s) => s[0].toUpperCase() + s.slice(1);

export function watchRows(f, logos = {}, icons = {}) {
  const byPid = new Map();
  for (const [k, label] of KINDS)
    for (const [pid, name, logo] of f.wp?.[k] || []) {
      const key = SEARCH[pid]?.[0] || pid; // Apple TV Store и Apple TV — один кинотеатр
      const row = byPid.get(key) || byPid.set(key, { pid, name: providerName(pid, name), logo: logo || logos[pid], kinds: [], url: watchLink(f, pid, name) }).get(key);
      if (!row.kinds.includes(label)) row.kinds.push(label);
    }
  const rows = [...byPid.values()].map(({ kinds, ...r }) => ({ ...r, sub: cap(kinds.join(', ')) }));
  for (const [k, name] of Object.entries(SITEMAP))
    if (f.ln?.[k] && !rows.some((r) => sitemapKey(r.name) === k))
      rows.push({ pid: k, name, logo: null, sub: f.k ? 'Страница сериала' : 'Страница фильма', url: f.ln[k] });
  for (const r of rows) if (!r.logo && icons[sitemapKey(r.name)]) r.icon = icons[sitemapKey(r.name)];
  return rows;
}
