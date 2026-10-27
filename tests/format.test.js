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

test('карточка не вставляет название как разметку', () => {
  const html = cardHTML({ id: 'tt1', slug: 'x', t: '<b>Взлом</b>', y: 2020, min: 100, imdb: 7.5, m: [], genres: [] }, '/');
  assert.ok(!html.includes('<b>Взлом</b>'));
  assert.ok(html.includes('&lt;b&gt;Взлом&lt;/b&gt;'));
  assert.ok(html.includes('href="/film/x/"'));
});
