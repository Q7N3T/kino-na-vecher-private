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

const SEARCH = {
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
  ['kinopoisk', 'Кинопоиск', 'https://www.kinopoisk.ru/index.php?kp_query={q}'],
  ['ivi', 'Иви', 'https://www.ivi.ru/search/?q={q}'],
  [115], ['wink', 'Wink', 'https://wink.ru/search?query={q}'], ['kion', 'KION', 'https://kion.ru/search?text={q}'],
  ['start', 'Start', 'https://start.ru/search?q={q}'], [570], [116], [557],
  ['flex', 'FLEX', 'https://kinoflex.ru/movie/{slug}'], // адрес страницы угадан по примеру — у части фильмов может не совпасть
];

const slug = (f) => String(f.o || f.t).toLowerCase().replace(/[^a-z0-9]+/g, '');
const fill = (t, f) => t.replaceAll('{q}', encodeURIComponent(f.t)).replaceAll('{id}', f.id).replaceAll('{slug}', slug(f));

export function watchLink(f, providerId, name = '') {
  const t = PARTNERS[providerId] || SEARCH[providerId]?.[1] || BY_NAME[name.toLowerCase()];
  return t ? fill(t, f) : f.wp.l;
}

// shown — номера и названия (в нижнем регистре) кинотеатров, которые уже есть в «Где посмотреть»
export function searchLinks(f, shown = []) {
  return ELSEWHERE.filter(([k, name, url]) => !shown.includes(k) && !shown.includes((name || SEARCH[k][0]).toLowerCase())
      && !(url?.includes('{slug}') && !slug(f))) // нет латинского названия — нет адреса FLEX
    .map(([k, name, url]) => (typeof k === 'number' ? { name: SEARCH[k][0], url: watchLink(f, k) } : { name, url: fill(url, f) }));
}
