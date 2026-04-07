import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import tailwindcss from '@tailwindcss/vite'
import { fileURLToPath, URL } from 'node:url'

// https://vite.dev/config/
export default defineConfig({
  plugins: [
    vue(),
    tailwindcss()
  ],
  resolve: {
    alias: {
      // Usa fileURLToPath para evitar separadores específicos de plataforma.
      // ⚠️ NO sustituir por `path/win32` — eso rompe la build de Linux/Vercel.
      '@': fileURLToPath(new URL('./src', import.meta.url)),
    },
  },
})
