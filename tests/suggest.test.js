// Подсказки в поиске: три отдельные группы, начало названия важнее середины, латиница находит русское.
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { suggest, mark } from '../src/lib/suggest.js';
import { esc } from '../src/lib/format.js';

const F = (t, k, pp, o = t) => ({ t, o, k, pp });
const films = [
  F('Тёмный рыцарь', 0, 50, 'The Dark Knight'),
  F('Рыцарь дня', 0, 20, 'Knight and Day'),
  F('Тёмный рыцарь: Возрождение легенды', 0, 40, 'The Dark Knight Rises'),
  F('Рыцари справедливости', 0, 5),
  F('Рыцарь Семи Королевств', 's', 90, 'A Knight of the Seven Kingdoms'),
  F('Пыцарь', 0, 99),
];
const actors = [{ n: 'Кристиан Бейл' }, { n: 'Christian Slater' }, { n: 'Рыцарев Иван' }];

test('актёры, фильмы и сериалы — отдельно', () => {
  const s = suggest('рыцар', films, actors);
  assert.deepEqual(s.series.map((f) => f.t), ['Рыцарь Семи Королевств']);
  assert.ok(s.movies.every((f) => !f.k));
  assert.deepEqual(s.actors.map((a) => a.n), ['Рыцарев Иван']);
});

test('сначала начинается с запроса, потом слово с запроса, потом середина; при равенстве — популярное', () => {
  const s = suggest('рыцар', films, actors);
  assert.deepEqual(s.movies.map((f) => f.t), ['Рыцарь дня', 'Рыцари справедливости', 'Тёмный рыцарь', 'Тёмный рыцарь: Возрождение легенды']);
});

test('ё и регистр не важны; оригинальное название тоже ищется', () => {
  assert.equal(suggest('темный', films, actors).movies[0].t, 'Тёмный рыцарь');
  assert.equal(suggest('dark knight rises', films, actors).movies[0].t, 'Тёмный рыцарь: Возрождение легенды');
});

test('у каждой группы свой предел; одна буква — ничего', () => {
  assert.equal(suggest('рыцар', films, actors, { n: 2 }).movies.length, 2);
  assert.deepEqual(suggest('р', films, actors), { q: 'р', actors: [], movies: [], series: [] });
});

test('актёры: порядок известности при равном совпадении', () => {
  assert.deepEqual(suggest('christ', films, actors).actors.map((a) => a.n), ['Christian Slater']);
  assert.deepEqual(suggest('крист', films, actors).actors.map((a) => a.n), ['Кристиан Бейл']);
});

test('совпадение выделяется, остальное экранируется', () => {
  assert.equal(mark('Тёмный рыцарь', 'рыц', esc), 'Тёмный <mark>рыц</mark>арь');
  assert.equal(mark('<b>', 'zz', esc), '&lt;b&gt;');
});
