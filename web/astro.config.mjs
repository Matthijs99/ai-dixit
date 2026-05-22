import { defineConfig } from 'astro/config';

export default defineConfig({
  // Hosted as a GitHub Pages project page at /ai-dixit/. All internal
  // links must include this prefix — see import.meta.env.BASE_URL.
  site: 'https://matthijs99.github.io',
  base: '/ai-dixit',
  output: 'static',
  trailingSlash: 'never',
  build: { format: 'directory' },
});
