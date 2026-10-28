// У каждого варианта фразы и фильтров — свой стикер: добавили настроение — нарисуйте и стикер.
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { sticker, stickerFor } from '../src/lib/stickers.js';
import { MOODS, TIMES, KINDS } from '../src/lib/format.js';

test('стикер есть у каждого настроения, вида и времени', () => {
  const all = [...[...MOODS.map((m) => m.v), 'any'].map((v) => ['mood', v]), ...KINDS.map((k) => ['kind', k.v]), ...TIMES.map((t) => ['time', t.v])];
  for (const [kind, v] of all) assert.match(sticker(stickerFor(kind, v)), /<svg[^>]*>.+<\/svg>/, `${kind}:${v}`);
  assert.equal(new Set(all.map(([k, v]) => stickerFor(k, v))).size, all.length, 'у разных вариантов — разные стикеры');
});

test('стикер — декорация: скринридер его не читает', () => {
  assert.match(sticker('laugh'), /^<span class="stk" aria-hidden="true">/);
  assert.equal(sticker('нет такого'), '');
});
