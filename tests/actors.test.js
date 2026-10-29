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

test('состав тайтла: актёр без фото здесь получает фото из других тайтлов, один актёр — одна карточка', async () => {
  const { load } = await import('../src/lib/data.js');
  const { films } = load();
  const bleach = films.find((f) => f.id === 'tt14986406'); // «Блич: Тысячелетняя кровавая война»: в составе TMDB фото не у всех
  assert.ok(bleach.crew.find((c) => c.n === 'Noriaki Sugiyama').p, 'фото Сугиямы — с других его тайтлов');
  for (const f of films) {
    const names = f.crew.map((c) => c.n);
    assert.equal(new Set(names).size, names.length, `${f.t}: актёр повторяется`);
  }
});
