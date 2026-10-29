// Куда ведёт кнопка кинотеатра: партнёрская ссылка → поиск фильма на сайте кинотеатра → страница TMDB.
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { watchLink, searchLinks, PARTNERS } from '../src/lib/partners.js';

const f = { id: 'tt0108778', t: 'Друзья', o: 'Friends', wp: { l: 'https://www.themoviedb.org/tv/1668/watch?locale=RU' } };

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

test('поискать в других кинотеатрах: без тех, что уже есть в «Где посмотреть», с Кинопоиском', () => {
  const links = searchLinks(f, [115]);
  assert.ok(links.length >= 5);
  assert.ok(!links.some((l) => l.name === 'Okko'));
  assert.ok(links.some((l) => l.name === 'Иви' && l.url.includes(encodeURIComponent('Друзья'))));
  assert.ok(links.some((l) => l.name === 'Кинопоиск' && l.url.includes('kinopoisk.ru')));
  assert.ok(!links.some((l) => l.name === 'FLEX'), 'у FLEX нет поиска по адресу, а угаданная страница бывает пустой');
});

test('кинотеатр под незнакомым номером узнаётся по названию; в «Поискать ещё» не повторяется', () => {
  assert.ok(watchLink(f, 99999, 'Кинопоиск').startsWith('https://www.kinopoisk.ru/'));
  assert.ok(!searchLinks(f, [99999, 'кинопоиск']).some((l) => l.name === 'Кинопоиск'));
});

test('названия кинотеатров по-русски: TMDB пишет латиницей', async () => {
  const { providerName } = await import('../src/lib/partners.js');
  assert.equal(providerName(117, 'Kinopoisk'), 'Кинопоиск');
  assert.equal(providerName(116, 'Amediateka'), 'Амедиатека');
  assert.equal(providerName(2555, 'Bloodstream'), 'Bloodstream');
  assert.ok(watchLink(f, 117).startsWith('https://www.kinopoisk.ru/'));
});

test('Кинопоиск — прямо страница фильма, когда известен его номер; иначе поиск', () => {
  assert.equal(watchLink({ ...f, kp: 77044 }, 117), 'https://www.kinopoisk.ru/film/77044/');
  assert.equal(searchLinks({ ...f, kp: 77044 }).find((l) => l.name === 'Кинопоиск').url, 'https://www.kinopoisk.ru/film/77044/');
  assert.ok(watchLink(f, 117).includes('kp_query='));
});

test('строки «Где посмотреть»: один кинотеатр — одна строка со всеми способами; Кинопоиск и FLEX — страница фильма', async () => {
  const { watchRows } = await import('../src/lib/partners.js');
  const film = { ...f, o: 'Friends', kp: 77044, ln: { flex: 'https://kinoflex.ru/movie/friends' },
    wp: { l: 'x', s: [[115, 'Okko', '/okko.png']], r: [[2, 'Apple TV Store', '/a.png']], b: [[2, 'Apple TV Store', '/a.png']] } };
  const { rows, more } = watchRows(film, { 117: '/kp.png' });
  assert.deepEqual(rows.map((r) => [r.name, r.sub]), [['Okko', 'По подписке'], ['Apple TV', 'Аренда, покупка'], ['Кинопоиск', 'Страница фильма'], ['FLEX', 'Страница фильма']]);
  assert.equal(rows[2].logo, '/kp.png', 'логотип из общей таблицы, даже если JustWatch о фильме не знает');
  assert.equal(rows[2].url, 'https://www.kinopoisk.ru/film/77044/');
  assert.equal(rows[3].url, 'https://kinoflex.ru/movie/friends');
  assert.ok(!more.some((l) => ['Okko', 'Кинопоиск', 'FLEX'].includes(l.name)), 'в «Поискать» — только остальные');
  assert.ok(more.some((l) => l.name === 'Иви'));
});

test('страницы из карт сайта: кинотеатр из JustWatch ведёт сразу на фильм, остальные — отдельной строкой', async () => {
  const { watchRows } = await import('../src/lib/partners.js');
  const film = { ...f, ln: { ivi: 'https://www.ivi.ru/watch/druzya', start: 'https://start.ru/watch/druzya', kion: 'https://kion.ru/serial/druzya' },
    wp: { l: 'x', s: [[9113, 'ivi', '/ivi.png']] } };
  const { rows, more } = watchRows(film, {});
  assert.deepEqual(rows.map((r) => [r.name, r.sub, r.url]), [
    ['ivi', 'По подписке', 'https://www.ivi.ru/watch/druzya'],
    ['Start', 'Страница фильма', 'https://start.ru/watch/druzya'],
    ['KION', 'Страница фильма', 'https://kion.ru/serial/druzya'],
  ]);
  assert.ok(!more.some((l) => ['Иви', 'Start', 'KION'].includes(l.name)));
  assert.equal(watchLink(film, 9113, 'ivi'), 'https://www.ivi.ru/watch/druzya');
});

test('без страницы из карты сайта FLEX не показываем: угаданный адрес бывает пустым', async () => {
  const { watchRows } = await import('../src/lib/partners.js');
  assert.ok(!watchRows({ ...f, wp: null }, {}).rows.some((r) => r.name === 'FLEX'));
});

test('строки «Где посмотреть» без данных: только то, что знаем точно, остальное — поиск', async () => {
  const { watchRows } = await import('../src/lib/partners.js');
  const { rows, more } = watchRows({ id: 'tt1', t: 'Фильм', wp: null }, {});
  assert.equal(rows.length, 0);
  assert.ok(more.some((l) => l.name === 'Кинопоиск' && l.url.includes('kp_query=')));
});

test('свой логотип кинотеатра без логотипа в TMDB — по ключу: FLEX, Иви', async () => {
  const { watchRows } = await import('../src/lib/partners.js');
  const film = { ...f, ln: { flex: 'https://kinoflex.ru/movie/friends', kion: 'https://kion.ru/serial/druzya' }, wp: { l: 'x', s: [[115, 'Okko', '/okko.png']] } };
  const { rows } = watchRows(film, {}, { flex: 'flex.png' });
  assert.equal(rows.find((r) => r.name === 'FLEX').icon, 'flex.png');
  assert.equal(rows.find((r) => r.name === 'KION').icon, undefined, 'нет файла — буква, как раньше');
  assert.equal(rows.find((r) => r.name === 'Okko').icon, undefined, 'логотип TMDB остаётся');
  const { more } = watchRows({ ...f, wp: null }, { 117: '/kp.png' }, { ivi: 'ivi.png', wink: 'wink.svg' });
  assert.equal(more.find((l) => l.name === 'Иви').icon, 'ivi.png', 'в «Поискать в» — тоже с логотипами');
  assert.equal(more.find((l) => l.name === 'Кинопоиск').logo, '/kp.png');
  assert.ok(!more.find((l) => l.name === 'Start').icon, 'нет файла — без значка');
});
