// Строка актёра для поиска: карточка актёра должна показывать правду обо всей фильмографии,
// а не только о тех тайтлах, что попали в короткий список для ленты.
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { actorSearchRow } from '../src/lib/data.js';

const role = (id, y, pp, imdb, v = 50000) => ({ f: { id, y, pp, imdb, v } });

test('годы и лучший фильм — по всем ролям, лента — 24 самых популярных', () => {
  const roles = [];
  for (let i = 0; i < 30; i++) roles.push(role('tt' + (100 + i), 2000 + i % 10, 100 + i, 7));
  roles.push(role('tt900', 1985, 1, 8.9)); // ранний, малоизвестный и лучший по рейтингу
  roles.push(role('tt901', 1990, 2, 9.4, 5000)); // рейтинг выше, но оценок мало — не «лучший»
  const row = actorSearchRow({ n: 'Имя Фамилия', slug: 'imya', p: '/p.jpg', roles });
  assert.equal(row.ids.length, 24);
  assert.equal(row.ids[0], 129, 'первым — самый популярный');
  assert.equal(row.total, 32);
  assert.deepEqual([row.y0, row.y1], [1985, 2009]);
  assert.equal(row.best, 900);
});

test('где смотреть сразу: подписка, потом бесплатно, потом с рекламой; аренда и покупка — нет', async () => {
  const { watchNow } = await import('../src/lib/data.js');
  assert.deepEqual(watchNow({ s: [[1, 'Okko', '/o.png']], f: [[2, 'Иви', '/i.png']] }), ['Okko', '/o.png', 's']);
  assert.deepEqual(watchNow({ a: [[3, 'Wink', '/w.png']], b: [[4, 'Apple TV Store', '/a.png']] }), ['Wink', '/w.png', 'a']);
  assert.equal(watchNow({ r: [[4, 'Apple TV Store', '/a.png']] }), 0);
  assert.equal(watchNow(null), 0);
});
