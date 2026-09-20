import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

// Build trafia do web/static — FastAPI montuje ten katalog na końcu, po trasach API.
// W trybie dev Vite proxuje API do uvicorna, żeby dało się pracować nad UI bez budowania.
const BACKEND = process.env.VIDEOMAT_API ?? 'http://127.0.0.1:8000'

export default defineConfig({
  plugins: [react(), tailwindcss()],
  build: { outDir: '../web/static', emptyOutDir: true },
  server: {
    port: 5173,
    proxy: {
      '/api': { target: BACKEND, changeOrigin: true },
      '/out': { target: BACKEND, changeOrigin: true },
      '/work': { target: BACKEND, changeOrigin: true },
      '/media': { target: BACKEND, changeOrigin: true },
    },
  },
})
