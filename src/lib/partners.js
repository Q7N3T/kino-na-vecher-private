// Куда ведут кнопки кинотеатров. По порядку:
// 1) партнёрская ссылка — когда кинотеатр или партнёрская сеть выдаст её, впишите в PARTNERS
//    по номеру провайдера TMDB: {q} — название фильма, {id} — номер IMDb, {slug} — оригинальное
//    название латиницей без пробелов и знаков (так устроены адреса FLEX: kinoflex.ru/movie/thesopranos);
// 2) поиск этого фильма прямо на сайте кинотеатра (SEARCH) — ссылок на саму карточку фильма
//    TMDB не даёт, поиск по русскому названию — ближайшее к ней;
// 3) страница «Где посмотреть» TMDB / JustWatch — для остальных.
// Номер провайдера — в data/syn/*.json: w → [номер, название, логотип].
// Адреса поиска собраны вручную и могут поменяться на стороне кинотеатра — проверяйте кликом.
export const PARTNERS = {};

// прямая страница фильма, когда кинотеатр известен по номеру из открытых данных:
// Кинопоиск — номер из Wikidata (P2603), его подтягивает scripts/build_films.py в поле kp
const DIRECT = {
  117: (f) => f.kp && `https://www.kinopoisk.ru/film/${f.kp}/`,
};

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
// крупные кинотеатры, которых нет в данных JustWatch, — для строки «Поискать в кинотеатрах»
const ELSEWHERE = [
  [117],
  ['ivi', 'Иви', 'https://www.ivi.ru/search/?q={q}'],
  [115], ['wink', 'Wink', 'https://wink.ru/search?query={q}'], ['kion', 'KION', 'https://kion.ru/search?text={q}'],
  ['start', 'Start', 'https://start.ru/search?q={q}'], [570], [116], [557],
  ['flex', 'FLEX', 'https://kinoflex.ru/movie/{slug}'], // адрес страницы угадан по примеру — у части фильмов может не совпасть
];

const slug = (f) => String(f.o || f.t).toLowerCase().replace(/[^a-z0-9]+/g, '');
const fill = (t, f) => t.replaceAll('{q}', encodeURIComponent(f.t)).replaceAll('{id}', f.id).replaceAll('{slug}', slug(f));

// название для людей: по-русски, если кинотеатр знаком (TMDB пишет «Kinopoisk», «Amediateka»)
export const providerName = (providerId, name) => SEARCH[providerId]?.[0] || name;

export function watchLink(f, providerId, name = '') {
  if (!PARTNERS[providerId] && DIRECT[providerId]?.(f)) return DIRECT[providerId](f);
  const t = PARTNERS[providerId] || SEARCH[providerId]?.[1] || BY_NAME[name.toLowerCase()];
  return t ? fill(t, f) : f.wp.l;
}

// shown — номера и названия (в нижнем регистре) кинотеатров, которые уже есть в «Где посмотреть»
export function searchLinks(f, shown = []) {
  return ELSEWHERE.filter(([k, name, url]) => !shown.includes(k) && !shown.includes((name || SEARCH[k][0]).toLowerCase())
      && !(url?.includes('{slug}') && !slug(f))) // нет латинского названия — нет адреса FLEX
    .map(([k, name, url]) => (typeof k === 'number' ? { name: SEARCH[k][0], url: watchLink(f, k) } : { name, url: fill(url, f) }));
}

// Строки блока «Где посмотреть». rows — кинотеатры, где фильм есть точно (JustWatch) или где известна
// его страница (Кинопоиск по номеру из Wikidata, FLEX по оригинальному названию); один кинотеатр —
// одна строка со всеми способами. more — остальные кинотеатры, туда ведёт поиск по названию.
// logos — логотипы кинотеатров по номеру, собранные по всей базе.
const KINDS = [['s', 'по подписке'], ['f', 'бесплатно'], ['a', 'бесплатно с рекламой'], ['r', 'аренда'], ['b', 'покупка']];
const cap = (s) => s[0].toUpperCase() + s.slice(1);

export function watchRows(f, logos = {}) {
  const byPid = new Map();
  for (const [k, label] of KINDS)
    for (const [pid, name, logo] of f.wp?.[k] || []) {
      const key = SEARCH[pid]?.[0] || pid; // Apple TV Store и Apple TV — один кинотеатр
      const row = byPid.get(key) || byPid.set(key, { pid, name: providerName(pid, name), logo: logo || logos[pid], kinds: [], url: watchLink(f, pid, name) }).get(key);
      if (!row.kinds.includes(label)) row.kinds.push(label);
    }
  const rows = [...byPid.values()].map(({ kinds, ...r }) => ({ ...r, sub: cap(kinds.join(', ')) }));
  if (f.kp && !rows.some((r) => r.pid === 117))
    rows.push({ pid: 117, name: 'Кинопоиск', logo: logos[117], sub: 'Страница фильма', url: DIRECT[117](f) });
  if (slug(f)) rows.push({ pid: 'flex', name: 'FLEX', logo: null, sub: 'Страница фильма', url: fill('https://kinoflex.ru/movie/{slug}', f) });
  const shown = rows.flatMap((r) => [r.pid, r.name.toLowerCase()]);
  return { rows, more: searchLinks(f, shown) };
}
