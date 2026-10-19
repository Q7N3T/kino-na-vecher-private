// Актёры для поиска: имя, адрес страницы, фото.
import { load } from '../lib/data.js';

export function GET() {
  const rows = load().actors.map((a) => [a.n, a.slug, a.p]);
  return new Response(JSON.stringify(rows), { headers: { 'Content-Type': 'application/json; charset=utf-8' } });
}
