// Партнёрские ссылки онлайн-кинотеатров. Когда кинотеатр или партнёрская сеть выдаст ссылку,
// впишите её сюда по номеру провайдера TMDB; {q} заменится названием фильма.
// Например: 115: 'https://partner.example/okko?sub={id}&q={q}'.
// Пока для провайдера ссылки нет, кнопка ведёт на страницу «Где посмотреть» TMDB / JustWatch.
// Номер провайдера можно посмотреть в data/syn/*.json: w → [номер, название, логотип].
export const PARTNERS = {};

export function watchLink(f, providerId) {
  const t = PARTNERS[providerId];
  return t ? t.replaceAll('{q}', encodeURIComponent(f.t)).replaceAll('{id}', f.id) : f.wp.l;
}
