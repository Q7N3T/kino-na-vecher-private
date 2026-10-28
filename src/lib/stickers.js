// Стикеры: маленькие эмоции настроений, фильм или сериал, сколько есть времени.
// Одна линия цвета акцента на тёплой подложке; viewBox 32×32, без заливок, кроме мелких деталей.
const face = (inner) => `<circle cx="16" cy="16" r="11"/>${inner}`;
const dot = (x, y) => `<circle cx="${x}" cy="${y}" r="1.4" fill="currentColor" stroke="none"/>`;
const star = (x, y, r) => `<path d="M${x} ${y - r}l${r * .3} ${r * .7} ${r * .7} ${r * .3}-${r * .7} ${r * .3}-${r * .3} ${r * .7}-${r * .3}-${r * .7}-${r * .7}-${r * .3} ${r * .7}-${r * .3}z" fill="currentColor" stroke="none"/>`;
// доля вечера (4 часа) закрашена на циферблате
const wedge = (deg) => {
  const a = ((deg - 90) * Math.PI) / 180, x = (16 + 7 * Math.cos(a)).toFixed(2), y = (16 + 7 * Math.sin(a)).toFixed(2);
  return `<circle cx="16" cy="16" r="11"/><path d="M16 16V9A7 7 0 ${deg > 180 ? 1 : 0} 1 ${x} ${y}Z" fill="currentColor" stroke="none" opacity=".55"/>`;
};

export const STICKERS = {
  // настроения
  laugh: face('<path d="M10.5 13.5q1.5-1.8 3 0M18.5 13.5q1.5-1.8 3 0"/><path d="M10.5 18h11a5.5 5.5 0 0 1-11 0z"/>'),
  nerve: face(dot(12.5, 14) + dot(19.5, 14) + '<path d="M11 21l2-1.5 2 1.5 2-1.5 2 1.5 2-1.5"/><path d="M26 4.5s2.4 2.9 2.4 4.4a2.4 2.4 0 0 1-4.8 0c0-1.5 2.4-4.4 2.4-4.4z"/>'),
  sad: face('<path d="M10.5 13.8q1.5 1.6 3 0M18.5 13.8q1.5 1.6 3 0"/><path d="M12.8 21.8q3.2-2.8 6.4 0"/><path d="M22.4 16.4s1.3 1.7 1.3 2.6a1.3 1.3 0 0 1-2.6 0c0-.9 1.3-2.6 1.3-2.6z" fill="currentColor" stroke="none"/>'),
  think: face(dot(13, 13) + dot(19, 13) + '<path d="M13 20.5h5"/>' + '<circle cx="25.5" cy="6.5" r="1.6" fill="currentColor" stroke="none"/><circle cx="28.5" cy="2.8" r="1" fill="currentColor" stroke="none"/>'),
  inspire: face(star(12.5, 13.5, 2.6) + star(19.5, 13.5, 2.6) + '<path d="M11.5 19q4.5 4 9 0"/>'),
  anyMood: face(dot(12.5, 14) + dot(19.5, 14) + '<path d="M12.5 19.5q3.5 2.6 7 0"/>'),
  // что смотрим
  movie: '<rect x="5" y="13" width="22" height="13" rx="2.5"/><path d="M5.6 13 5 9.4l20.6-3.3.6 3.6M11 8.5l2.4 3.6M17 7.6l2.4 3.6"/>',
  series: '<rect x="5" y="9" width="22" height="16" rx="3"/><path d="M12 4l4 5 4-5M14 14v6l5-3z"/>',
  anyKind: '<path d="M8.5 13.5h15l-2 13h-11z"/><path d="M13.5 13.5l.4 13M18.5 13.5l-.4 13"/><path d="M9 13.5a3 3 0 0 1 4-4.3 3.4 3.4 0 0 1 6 0 3 3 0 0 1 4 4.3"/>',
  // время
  t105: wedge(135),
  t130: wedge(180),
  evening: '<path d="M21 5.5a11 11 0 1 0 6.5 16 8.6 8.6 0 0 1-6.5-16z"/>' + star(9.5, 8.5, 2.4) + star(26.5, 11, 1.6),
  anyLen: '<circle cx="16" cy="16" r="11"/><path d="M16 10v6l4 2.5"/>',
};

// по значению фильтра — ключ стикера
const KEY = { any: 'anyMood', movie: 'movie', series: 'series', 105: 't105', 130: 't130', 999: 'evening' };
export const stickerFor = (kind, v) => kind === 'mood' ? (v === 'any' ? 'anyMood' : v) : kind === 'kind' ? (v === 'any' ? 'anyKind' : KEY[v]) : KEY[v];

export function sticker(name, cls = '') {
  const svg = STICKERS[name];
  return svg ? `<span class="stk${cls ? ' ' + cls : ''}" aria-hidden="true"><svg viewBox="0 0 32 32" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">${svg}</svg></span>` : '';
}
