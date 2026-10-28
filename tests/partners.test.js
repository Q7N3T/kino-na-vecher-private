// Куда ведёт кнопка кинотеатра: партнёрская ссылка → поиск фильма на сайте кинотеатра → страница TMDB.
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { watchLink, searchLinks, PARTNERS } from '../src/lib/partners.js';

const f = { id: 'tt0108778', t: 'Друзья', wp: { l: 'https://www.themoviedb.org/tv/1668/watch?locale=RU' } };

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

test('поискать в других кинотеатрах: без тех, что уже есть в «Где посмотреть», и без сервисов Яндекса', () => {
  const links = searchLinks(f, [115]);
  assert.ok(links.length >= 5);
  assert.ok(!links.some((l) => l.name === 'Okko'));
  assert.ok(links.some((l) => l.name === 'Иви' && l.url.includes(encodeURIComponent('Друзья'))));
  assert.ok(!links.some((l) => /кинопоиск|яндекс|kinopoisk|yandex/i.test(l.name + l.url)));
});
