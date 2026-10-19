// Лёгкий индекс всех фильмов и сериалов для подбора, каталога, поиска и избранного.
import { INDEX_FIELDS, indexRows } from '../lib/data.js';

export function GET() {
  return new Response(JSON.stringify({ fields: INDEX_FIELDS, rows: indexRows() }), {
    headers: { 'Content-Type': 'application/json; charset=utf-8' },
  });
}
