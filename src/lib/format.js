// Общие функции: работают и при сборке страниц, и в браузере.

export const MOODS = [
  { v: 'laugh', word: 'посмеяться', tag: 'Смешно' },
  { v: 'nerve', word: 'понервничать', tag: 'Напряжённо' },
  { v: 'sad', word: 'погрустить', tag: 'Грустно' },
  { v: 'think', word: 'подумать', tag: 'Заставляет думать' },
  { v: 'inspire', word: 'вдохновиться', tag: 'Вдохновляет' },
];

export const TIMES = [
  { v: 105, word: 'полтора часа', chip: 'Около 1,5 часа' },
  { v: 130, word: 'часа два', chip: 'Часа два' },
  { v: 999, word: 'весь вечер', chip: 'Весь вечер' },
];

export const KINDS = [
  { v: 'any', word: 'что угодно', chip: 'Неважно', forms: ['фильм или сериал', 'фильма и сериала', 'фильмов и сериалов'] },
  { v: 'movie', word: 'фильм', chip: 'Фильм', forms: ['фильм', 'фильма', 'фильмов'] },
  { v: 'series', word: 'сериал', chip: 'Сериал', forms: ['сериал', 'сериала', 'сериалов'] },
];

export const pad = (n) => String(n).padStart(2, '0');

export function plural(n, a, b, c) {
  const m10 = n % 10, m100 = n % 100;
  if (m10 === 1 && m100 !== 11) return a;
  if (m10 >= 2 && m10 <= 4 && (m100 < 10 || m100 >= 20)) return b;
  return c;
}

export function num(n) {
  return String(n).replace(/\B(?=(\d{3})+(?!\d))/g, ' ');
}

export function dur(min) {
  const h = Math.floor(min / 60), m = min % 60;
  return ((h ? h + ' ч ' : '') + (m ? m + ' мин' : '')).trim();
}

export function esc(s) {
  return String(s ?? '').replace(/[&<>"]/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' })[c]);
}

export const cap = (s) => (s ? s[0].toUpperCase() + s.slice(1) : s);

export function hue(s) {
  let h = 0;
  for (const c of String(s)) h = (h * 31 + c.charCodeAt(0)) % 360;
  return h;
}

export function votes(v) {
  if (v >= 1e6) return (v / 1e6).toFixed(1).replace('.', ',').replace(',0', '') + ' млн';
  if (v >= 1e3) return Math.round(v / 1e3) + ' тыс.';
  return String(v);
}

export function kindName(f) {
  return f.k === 'ms' ? 'Мини-сериал' : f.k ? 'Сериал' : 'Фильм';
}

// у продлённых сериалов IMDb иногда ставит год окончания — тогда «с …»
export function years(f) {
  if (!f.k || (f.ye === f.y && !f.ann)) return String(f.y);
  return f.ye && !f.ann ? f.y + '–' + f.ye : 'с ' + f.y;
}

export function seasons(f) {
  return f.ss ? `${f.ss} ${plural(f.ss, 'сезон', 'сезона', 'сезонов')}` : '';
}

// Статус сериала. on: true — выходит, false — завершён, null — неизвестно.
export function status(f, year = new Date().getFullYear()) {
  if (!f.k) return null;
  const ts = f.ts;
  if (ts === 'Ended') return { on: false, label: f.k === 'ms' ? 'Вышел целиком' : 'Завершён', more: f.ye ? `в ${f.ye}` : '' };
  if (ts === 'Canceled') return { on: false, label: 'Закрыт', more: f.ye || f.la ? `в ${f.ye || f.la}` : '' };
  if (['Returning Series', 'In Production', 'Planned'].includes(ts) || (!ts && (f.ann || (!f.ye && f.la >= year - 1))))
    return { on: true, label: 'Продолжается', more: f.ann ? `продлён ещё на ${f.ann} ${plural(f.ann, 'сезон', 'сезона', 'сезонов')}` : '' };
  if (f.ye) return { on: false, label: f.k === 'ms' ? 'Вышел целиком' : 'Завершён', more: `в ${f.ye}` };
  return f.la ? { on: null, label: `Новых серий нет с ${f.la}`, more: '' } : null;
}

// Постеры и фото TMDB идут через прокси wsrv.nl: image.tmdb.org открывается не везде,
// а wsrv заодно сжимает в WebP нужного размера.
export function tmdbImg(path, w, size = 'w500') {
  return 'https://wsrv.nl/?url=' + encodeURIComponent('https://image.tmdb.org/t/p/' + size + path) + '&w=' + w + '&output=webp';
}

export function titleUrl(base, f) {
  return `${base}${f.k ? 'serial' : 'film'}/${f.slug}/`;
}

export function initials(n) {
  return n.split(/\s+/).filter(Boolean).slice(0, 2).map((w) => w[0]).join('').toUpperCase();
}

// Строка про время. Фильм — «финал в 22:40». Сериал при известном свободном времени — сколько серий
// успеете и когда закончите; иначе — длительность серии. Время считает браузер, до этого блок .fin скрыт.
export const EVENING = 240; // «весь вечер» в минутах — для подсчёта серий
// Сколько серий успеть за свободное время: хотя бы одну и не больше, чем вышло
export const episodesFor = (f, time) => Math.max(1, Math.min(f.ep || Infinity, Math.floor((time >= 999 ? EVENING : time) / f.min)));
// Когда закончите: фильм — целиком; сериал при известном времени — столько серий, сколько успеете.
// null — для сериала время не задано, считать нечего.
export function finish(f, time = 0) {
  if (!f.k) return { text: 'финал в', min: f.min };
  if (!time) return null;
  const n = episodesFor(f, time);
  return { text: `успеете ${n} ${plural(n, 'серию', 'серии', 'серий')}, закончите в`, min: n * f.min };
}

export function timeLine(f, time = 0) {
  const e = finish(f, time);
  return e ? `<span class="fin"> · ${e.text} <b data-end="${e.min}"></b></span>` : ` · серия ${dur(f.min)}`;
}

const WATCH_NOW = { s: 'по подписке', f: 'бесплатно', a: 'бесплатно с рекламой' };

// Карточка — одна разметка для страниц, собранных заранее, и для карточек, которые рисует браузер.
// На постере — одна метка: почему тайтл в подборке (why); статус сериала — в мелкой строке.
// time — свободное время зрителя в минутах, если известно (для сериалов: сколько серий успеет).
export function cardHTML(f, base, { i = 0, why = '', time = 0 } = {}) {
  const st = status(f);
  const meta = f.k
    ? [f.k === 'ms' ? `Мини-сериал · ${years(f)}` : seasons(f), st && `<span class="st${st.on ? ' on' : ''}">${st.label.toLowerCase()}</span>`].filter(Boolean).join(' · ')
    : `${f.y} · ${dur(f.min)}`;
  const img = f.p
    ? `<img src="${tmdbImg(f.p, 342)}" alt="" loading="lazy" decoding="async" onerror="knvImg(this)">`
    : '';
  return `<a class="card" href="${titleUrl(base, f)}" data-id="${f.id}" style="--i:${Math.min(i, 12)}">
  <div class="poster" style="--h:${hue(f.id)}">${img}<span class="ph" aria-hidden="true">${esc(f.t)}</span>${why ? `<span class="why">${why}</span>` : ''}</div>
  <span class="card-t">${esc(f.t)}</span>
  <span class="card-m">${meta}</span>
  <span class="card-e">IMDb ${f.imdb.toFixed(1)}${timeLine(f, time)}${f.w ? `<span class="card-w">${f.w[1] ? `<img src="${tmdbImg(f.w[1], 32, 'w92')}" alt="" width="16" height="16" loading="lazy" onerror="knvImg(this)">` : ''}<span class="sr">${esc(f.w[0])} · ${WATCH_NOW[f.w[2]]}</span></span>` : ''}</span>
</a>`;
}
