// Актёры для поиска. Строка — массив, а не объект: так файл вдвое меньше; порядок полей —
// тот же, что разбирает страница поиска (toActor в src/pages/poisk/index.astro).
import { load, actorSearchRow } from '../lib/data.js';

export function GET() {
  const rows = load().actors.map(actorSearchRow).map((r) => [r.n, r.slug, r.p, r.ids, r.total, r.y0, r.y1, r.best]);
  return new Response(JSON.stringify(rows), { headers: { 'Content-Type': 'application/json; charset=utf-8' } });
}
