import path from 'node:path'
import tailwindcss from '@tailwindcss/vite'
import react from '@vitejs/plugin-react'
import { defineConfig, type Plugin } from 'vite'

const MEDIA_URL = '/api/v1/portfolio/medias'
const MEDIA_ROOT = path.resolve(import.meta.dirname, '../content/portfolio/medias')

/** mock 모드는 백엔드가 없으므로 백엔드 대신 원본 미디어 파일을 내준다. */
function mockMedia(): Plugin {
  return {
    name: 'mock-media',
    apply: (_, env) => env.command === 'serve' && env.mode === 'mock',
    configureServer(server) {
      server.middlewares.use(MEDIA_URL, (req, res, next) => {
        const file = path.resolve(MEDIA_ROOT, '.' + decodeURIComponent((req.url ?? '').split('?')[0]))
        if (!file.startsWith(MEDIA_ROOT + path.sep)) return next()
        res.writeHead(302, { Location: `/@fs${file}` })
        res.end()
      })
    },
  }
}

export default defineConfig({
  plugins: [react(), tailwindcss(), mockMedia()],
  resolve: {
    alias: {
      '@': path.resolve(import.meta.dirname, './src'),
      '@contracts': path.resolve(import.meta.dirname, '../contracts'),
      '@content': path.resolve(import.meta.dirname, '../content'),
    },
  },
  server: {
    fs: { allow: ['..'] },
    proxy: {
      '/api': { target: process.env.API_PROXY_TARGET ?? 'http://localhost:8000', changeOrigin: true },
    },
  },
})
