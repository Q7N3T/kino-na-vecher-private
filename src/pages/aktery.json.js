// Актёры для поиска: имя, адрес страницы, фото и номера IMDb их тайтлов (без «tt», по популярности) —
// чтобы по имени актёра находились и его фильмы; не больше 24 (полная фильмография — на странице актёра), и сколько их всего.
import { load } from '../lib/data.js';

export function GET() {
  const rows = load().actors.map((a) => [a.n, a.slug, a.p, [...a.roles].sort((x, y) => y.f.pp - x.f.pp).slice(0, 24).map((r) => +r.f.id.slice(2)), a.roles.length]);
  return new Response(JSON.stringify(rows), { headers: { 'Content-Type': 'application/json; charset=utf-8' } });
}
