// Подборка «Подходит на сегодня» и «Выбор на сегодня»: свойства, которые видит зритель.
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { curate, dailyPick, dailyCandidates, franchise } from '../src/lib/curate.js';

let n = 0;
const film = (t, o = {}) => ({ id: 'tt' + ++n, t, y: 2010, imdb: 7.6, v: 60000, pp: 50, min: 100, m: ['laugh'], genres: ['комедия'], d: ['реж ' + n], ...o });

function base() {
  n = 0;
  const list = [];
  for (let i = 0; i < 40; i++) list.push(film('Комедия ' + 'абвгдежзиклмнопрстуфхцчшщыэюя'[i % 29] + i, { imdb: 7 + (i % 20) / 10, pp: 5 + i * 3, y: 1985 + (i % 40) }));
  list.push(film('Матрица', { imdb: 8.7, pp: 400 }), film('Матрица: Перезагрузка', { imdb: 8.5, pp: 390 }), film('Матрица 3', { imdb: 8.4, pp: 380 }));
  list.push(film('Провал', { imdb: 4.1, v: 90000, pp: 900 }));
  return list;
}

test('франшиза узнаётся по названию', () => {
  assert.equal(franchise({ t: 'Крёстный отец 2' }), 'крестный отец');
  assert.equal(franchise({ t: 'Матрица: Перезагрузка' }), 'матрица');
  assert.equal(franchise({ t: 'Чужой III' }), 'чужой');
});

test('12 разных тайтлов, а всё остальное — в хвосте', () => {
  const list = base();
  const { items, rest } = curate(list, { time: 130, mood: 'laugh', day: 'd1' });
  const ids = items.map((x) => x.f.id);
  assert.equal(items.length, 12);
  assert.equal(new Set(ids).size, 12, 'без повторов');
  assert.equal(items.length + rest.length, list.length);
  assert.ok(rest.every((f) => !ids.includes(f.id)));
});

test('одна франшиза — одно место', () => {
  const { items } = curate(base(), { time: 130, mood: 'laugh', day: 'd1' });
  assert.ok(items.filter((x) => x.f.t.startsWith('Матрица')).length <= 1);
});

test('слабое не попадает, когда хорошего хватает', () => {
  const { items } = curate(base(), { time: 130, mood: 'laugh', day: 'd1' });
  assert.ok(!items.some((x) => x.f.t === 'Провал'));
});

test('порог качества: громкий провал не занимает место, даже когда больше нечем заполнить ленту', () => {
  n = 0;
  // только «хиты» (латинские названия не идут в находки, свежее и классику) — решает порог
  const list = Array.from({ length: 13 }, (_, i) => film('Title ' + i, { imdb: 7.2, pp: 5, y: 2010 + (i % 5) }));
  list.push(film('Flop', { imdb: 3.9, v: 200000, pp: 5000 }));
  const { items } = curate(list, { time: 130, mood: 'laugh', day: 'd1' });
  assert.ok(!items.some((x) => x.f.t === 'Flop'));
});

test('в один и тот же день подборка одна и та же', () => {
  const a = curate(base(), { time: 130, mood: 'laugh', day: 'd1' }).items.map((x) => x.f.t);
  const b = curate(base(), { time: 130, mood: 'laugh', day: 'd1' }).items.map((x) => x.f.t);
  assert.deepEqual(a, b);
});

test('пустой список — пустая подборка', () => {
  assert.deepEqual(curate([], {}), { items: [], rest: [] });
});

test('выбор дня: устойчив в течение дня и не повторяет уже выбранное', () => {
  const list = base();
  const first = dailyPick(list, { time: 130, mood: 'laugh' });
  assert.ok(first);
  assert.equal(dailyPick(list, { time: 130, mood: 'laugh' }).id, first.id);
  const again = dailyPick(list, { time: 130, mood: 'laugh', prof: { n: 1, seen: new Set([first.id]), picked: new Set([first.id]), g: new Map(), m: new Map(), k: new Map(), y: new Map(), d: new Map() } });
  assert.notEqual(again.id, first.id);
});

const taste = (seen, picked = []) => ({ n: 3, seen: new Set(seen), picked: new Set(picked), g: new Map(), m: new Map(), k: new Map(), y: new Map(), d: new Map() });
function withGem() {
  n = 0;
  // единственная находка в списке; остальное средненькое и громкое
  const list = Array.from({ length: 50 }, (_, i) => film('Обычная ' + 'абвгдежзиклмн'[i % 13] + i, { imdb: 7.2, pp: 300 + i }));
  const gem = film('Любимая находка', { imdb: 8.9, v: 50000, pp: 2 });
  return { list: [...list, gem], gem };
}

test('выбор дня: открытый раньше, но отложенный в «Хочу посмотреть» фильм — среди кандидатов', () => {
  const { list, gem } = withGem();
  const from = dailyCandidates(list, { time: 130, mood: 'laugh', prof: taste([gem.id]), watch: [gem.id] });
  assert.ok(from.some((f) => f.id === gem.id));
});

test('выбор дня: открытый и не отложенный — не предлагается', () => {
  const { list, gem } = withGem();
  assert.ok(!dailyCandidates(list, { time: 130, mood: 'laugh', prof: taste([gem.id]) }).some((f) => f.id === gem.id));
});

test('выбор дня: уже выбранный раньше не возвращается, даже из «Хочу посмотреть»', () => {
  const { list, gem } = withGem();
  const from = dailyCandidates(list, { time: 130, mood: 'laugh', prof: taste([gem.id], [gem.id]), watch: [gem.id] });
  assert.ok(from.length > 0 && !from.some((f) => f.id === gem.id));
});

test('выбор дня: в маленьком списке уже выбранное тоже не возвращается', () => {
  n = 0;
  const a = film('Первая', { imdb: 8.1 }), b = film('Вторая', { imdb: 7.9 }), c = film('Третья', { imdb: 7.7 });
  const from = dailyCandidates([a, b, c], { time: 130, mood: 'laugh', prof: taste([a.id], [a.id]), watch: [a.id] });
  assert.ok(from.length > 0 && !from.some((f) => f.id === a.id));
});

test('популярное сейчас: по популярности, от 7 на IMDb, без уже показанного, нужного типа', async () => {
  const { popularNow } = await import('../src/lib/curate.js');
  n = 0;
  const list = [film('Хит', { pp: 900, imdb: 7.4 }), film('Провал', { pp: 990, imdb: 2.4 }), film('Сериал', { pp: 800, imdb: 8.1, k: 's' }),
    film('Показан', { pp: 950, imdb: 8 }), film('Тихий', { pp: 10, imdb: 7.9 })];
  const t = (xs) => xs.map((f) => f.t);
  assert.deepEqual(t(popularNow(list, { exclude: new Set([list[3].id]) })), ['Хит', 'Сериал', 'Тихий']);
  assert.deepEqual(t(popularNow(list, { kind: 'movie' })), ['Показан', 'Хит', 'Тихий']);
  assert.deepEqual(t(popularNow(list, { kind: 'series' })), ['Сериал']);
  assert.equal(popularNow(list, { n: 2 }).length, 2);
});
