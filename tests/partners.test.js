// «Где посмотреть»: только кинотеатры, где тайтл можно посмотреть, и куда ведёт каждая кнопка:
// партнёрская ссылка → страница фильма → поиск фильма на сайте кинотеатра → страница TMDB.
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { watchLink, watchRows, providerName, PARTNERS } from '../src/lib/partners.js';

const f = { id: 'tt0108778', t: 'Друзья', o: 'Friends', k: 's', wp: { l: 'https://www.themoviedb.org/tv/1668/watch?locale=RU' } };

test('известный кинотеатр — поиск фильма прямо на его сайте, по русскому названию', () => {
  assert.equal(watchLink(f, 115), 'https://okko.tv/search/' + encodeURIComponent('Друзья'));
});

test('незнакомый кинотеатр — страница «Где посмотреть» TMDB', () => {
  assert.equal(watchLink(f, 2555), f.wp.l);
});

test('партнёрская ссылка важнее поиска', () => {
  PARTNERS[115] = 'https://partner.example/okko?sub={id}&q={q}';
  try { assert.equal(watchLink(f, 115), 'https://partner.example/okko?sub=tt0108778&q=' + encodeURIComponent('Друзья')); }
  finally { delete PARTNERS[115]; }
});

test('кинотеатр под незнакомым номером узнаётся по названию', () => {
  assert.ok(watchLink(f, 99999, 'Кинопоиск').startsWith('https://www.kinopoisk.ru/'));
});

test('названия кинотеатров по-русски: TMDB пишет латиницей', () => {
  assert.equal(providerName(117, 'Kinopoisk'), 'Кинопоиск');
  assert.equal(providerName(116, 'Amediateka'), 'Амедиатека');
  assert.equal(providerName(2555, 'Bloodstream'), 'Bloodstream');
});

test('Кинопоиск — прямо страница фильма, когда известен его номер; иначе поиск', () => {
  assert.equal(watchLink({ ...f, kp: 77044 }, 117), 'https://www.kinopoisk.ru/film/77044/');
  assert.ok(watchLink(f, 117).includes('kp_query='));
});

test('один кинотеатр — одна строка со всеми способами; FLEX — страница из каталога', () => {
  const film = { ...f, kp: 77044, ln: { flex: 'https://kinoflex.ru/movie/friends' },
    wp: { l: 'x', s: [[115, 'Okko', '/okko.png'], [117, 'Kinopoisk', '/kp.png']], r: [[2, 'Apple TV Store', '/a.png']], b: [[2, 'Apple TV Store', '/a.png']] } };
  const rows = watchRows(film, {});
  assert.deepEqual(rows.map((r) => [r.name, r.sub]), [['Okko', 'По подписке'], ['Кинопоиск', 'По подписке'], ['Apple TV', 'Аренда, покупка'], ['FLEX', 'Страница сериала']]);
  assert.equal(rows[1].url, 'https://www.kinopoisk.ru/film/77044/', 'Кинопоиск из JustWatch — сразу на страницу фильма');
  assert.equal(rows[3].url, 'https://kinoflex.ru/movie/friends');
});

test('только где можно посмотреть: страница Кинопоиска по номеру без данных JustWatch — не строка', () => {
  assert.deepEqual(watchRows({ ...f, kp: 77044, wp: null }, { 117: '/kp.png' }), []);
  assert.deepEqual(watchRows({ id: 'tt1', t: 'Фильм', wp: null }, {}), []);
});

test('страницы из каталогов: кинотеатр из JustWatch ведёт сразу на фильм, остальные — своей строкой', () => {
  const film = { ...f, ln: { ivi: 'https://www.ivi.ru/watch/druzya', start: 'https://start.ru/watch/druzya', kion: 'https://kion.ru/serial/druzya' },
    wp: { l: 'x', s: [[9113, 'ivi', '/ivi.png']] } };
  assert.deepEqual(watchRows(film, {}).map((r) => [r.name, r.sub, r.url]), [
    ['ivi', 'По подписке', 'https://www.ivi.ru/watch/druzya'],
    ['Start', 'Страница сериала', 'https://start.ru/watch/druzya'],
    ['KION', 'Страница сериала', 'https://kion.ru/serial/druzya'],
  ]);
  assert.equal(watchLink(film, 9113, 'ivi'), 'https://www.ivi.ru/watch/druzya');
  assert.equal(watchRows({ ...film, k: undefined }, {})[1].sub, 'Страница фильма');
});

test('без страницы из каталога FLEX не показываем: угаданный адрес бывает пустым', () => {
  assert.ok(!watchRows({ ...f, wp: null }, {}).some((r) => r.name === 'FLEX'));
});

test('свой логотип кинотеатра без логотипа в TMDB — по ключу: FLEX, Иви', () => {
  const film = { ...f, ln: { flex: 'https://kinoflex.ru/movie/friends', kion: 'https://kion.ru/serial/druzya' }, wp: { l: 'x', s: [[115, 'Okko', '/okko.png']] } };
  const rows = watchRows(film, {}, { flex: 'flex.png' });
  assert.equal(rows.find((r) => r.name === 'FLEX').icon, 'flex.png');
  assert.equal(rows.find((r) => r.name === 'KION').icon, undefined, 'нет файла — буква, как раньше');
  assert.equal(rows.find((r) => r.name === 'Okko').icon, undefined, 'логотип TMDB остаётся');
});
