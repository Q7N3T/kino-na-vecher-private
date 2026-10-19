import { defineConfig } from 'astro/config';

// Сайт живёт на GitHub Pages в подпапке репозитория. Для своего домена:
// SITE=https://example.ru BASE=/ npm run build
export default defineConfig({
  site: process.env.SITE || 'https://q7n3t.github.io',
  base: process.env.BASE || '/kino-na-vecher-private/',
  trailingSlash: 'always',
  build: { format: 'directory', concurrency: 4 },
  vite: { build: { assetsInlineLimit: 0 } },
});
