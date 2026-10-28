// То, что зритель видит на карточках и страницах: числа со словами, длительность, годы, статус сериала.
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { plural, dur, years, status, votes, cardHTML } from '../src/lib/format.js';

const forms = (n) => `${n} ${plural(n, 'фильм', 'фильма', 'фильмов')}`;

test('число и слово согласуются', () => {
  assert.deepEqual([1, 2, 5, 11, 12, 21, 22, 25, 111].map(forms),
    ['1 фильм', '2 фильма', '5 фильмов', '11 фильмов', '12 фильмов', '21 фильм', '22 фильма', '25 фильмов', '111 фильмов']);
});

test('длительность — часы и минуты без пустых частей', () => {
  assert.equal(dur(90), '1 ч 30 мин');
  assert.equal(dur(60), '1 ч');
  assert.equal(dur(45), '45 мин');
});

test('годы: фильм, завершённый сериал, продлённый сериал', () => {
  assert.equal(years({ y: 2008 }), '2008');
  assert.equal(years({ k: 's', y: 2008, ye: 2013 }), '2008–2013');
  assert.equal(years({ k: 's', y: 2008, ye: 2008 }), '2008');
  assert.equal(years({ k: 's', y: 2008, ann: 2 }), 'с 2008');
  assert.equal(years({ k: 's', y: 2024, ye: 2024, ann: 1 }), 'с 2024', 'продлён после первого сезона — год окончания IMDb не верим');
});

test('статус сериала по данным TMDB', () => {
  assert.equal(status({ y: 2010 }), null, 'у фильма статуса нет');
  assert.deepEqual(status({ k: 's', ts: 'Ended', ye: 2013 }), { on: false, label: 'Завершён', more: 'в 2013' });
  assert.equal(status({ k: 'ms', ts: 'Ended' }).label, 'Вышел целиком');
  assert.equal(status({ k: 's', ts: 'Canceled', la: 2019 }).label, 'Закрыт');
  assert.deepEqual(status({ k: 's', ts: 'Returning Series', ann: 2 }), { on: true, label: 'Продолжается', more: 'продлён ещё на 2 сезона' });
});

test('статус без данных TMDB — по годам IMDb', () => {
  assert.equal(status({ k: 's', la: 2025 }, 2026).on, true, 'серии выходили в прошлом году');
  assert.equal(status({ k: 's', ye: 2015, la: 2015 }, 2026).label, 'Завершён');
  assert.equal(status({ k: 's', la: 2012 }, 2026).label, 'Новых серий нет с 2012');
});

test('оценки коротко', () => {
  assert.equal(votes(1500000), '1,5 млн');
  assert.equal(votes(2000000), '2 млн');
  assert.equal(votes(25300), '25 тыс.');
  assert.equal(votes(800), '800');
});

const movie = { id: 'tt1', slug: 'x', t: 'Фильм', y: 2020, min: 100, imdb: 7.5, m: [], genres: [] };
const show = { id: 'tt2', slug: 'y', t: 'Сериал', k: 's', y: 2015, ye: 2019, ss: 4, ep: 40, min: 45, imdb: 8.6, ts: 'Ended', m: [], genres: [] };
const text = (html) => html.replace(/<[^>]+>/g, ' ').replace(/\s+/g, ' ').trim();

test('карточка не вставляет название как разметку', () => {
  const html = cardHTML({ ...movie, t: '<b>Взлом</b>' }, '/');
  assert.ok(!html.includes('<b>Взлом</b>'));
  assert.ok(html.includes('&lt;b&gt;Взлом&lt;/b&gt;'));
  assert.ok(html.includes('href="/film/x/"'));
});

test('фильм: рейтинг, а время финала — отдельным блоком, который прячется, пока не посчитан', () => {
  const html = cardHTML(movie, '/');
  assert.match(html, /<span class="fin">[^<]*финал в <b data-end="100"><\/b><\/span>/);
  assert.ok(text(html).includes('IMDb 7.5'));
  assert.ok(!/финал в\s*$/.test(text(html).split('IMDb')[0]), 'никакого «финал в» перед рейтингом');
});

test('сериал при заданном времени: сколько серий успеете и когда закончите', () => {
  assert.ok(text(cardHTML(show, '/', { time: 105 })).includes('успеете 2 серии, закончите в'));
  assert.ok(cardHTML(show, '/', { time: 105 }).includes('data-end="90"'));
  assert.ok(text(cardHTML(show, '/', { time: 40 })).includes('успеете 1 серию'), 'хотя бы одна');
  assert.ok(text(cardHTML(show, '/', { time: 999 })).includes('успеете 5 серий'), 'весь вечер — четыре часа');
  assert.ok(text(cardHTML({ ...show, ep: 3 }, '/', { time: 999 })).includes('успеете 3 серии'), 'не больше, чем вышло');
});

test('сериал без заданного времени: длительность серии, без «финала»', () => {
  const t = text(cardHTML(show, '/'));
  assert.ok(t.includes('серия 45 мин'));
  assert.ok(!t.includes('финал') && !t.includes('успеете'));
});

test('одна метка на постере: «почему в подборке» важнее статуса, статус — в мелкой строке', () => {
  const html = cardHTML(show, '/', { why: 'Находка' });
  assert.equal((html.match(/class="(why|badge)/g) || []).length, 1);
  assert.ok(html.includes('class="why"'));
  assert.ok(text(html).includes('4 сезона · завершён'));
  assert.equal((cardHTML(show, '/').match(/class="(why|badge)/g) || []).length, 0);
});

test('заглушка постера не читается скринридером второй раз', () => {
  assert.match(cardHTML(movie, '/'), /<span class="ph" aria-hidden="true">/);
});

test('кинотеатр на карточке: логотип, название и способ — для скринридера', () => {
  const html = cardHTML({ ...movie, w: ['Okko', '/okko.png', 's'] }, '/');
  assert.ok(text(html).includes('Okko · по подписке'));
  assert.ok(html.includes('class="card-w"'));
  assert.ok(text(cardHTML({ ...movie, w: ['Иви', '/ivi.png', 'f'] }, '/')).includes('Иви · бесплатно'));
  assert.ok(!cardHTML(movie, '/').includes('card-w'), 'нет данных — нет строки');
});
