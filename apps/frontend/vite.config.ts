import { defineConfig } from 'vite'
import { devtools } from '@tanstack/devtools-vite'
import viteReact from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

import { tanstackRouter } from '@tanstack/router-plugin/vite'
import { fileURLToPath, URL } from 'node:url'

// https://vitejs.dev/config/
export default defineConfig({
  plugins: [
    devtools(),
    tanstackRouter({
      target: 'react',
      autoCodeSplitting: true,
      routeFileIgnorePattern: '(FileUpload|FilePreview|OCRPage|OCRResults|testImage|testData)\\.',
    }),
    viteReact(),
    tailwindcss(),
  ],
  resolve: {
    alias: {
      '@': fileURLToPath(new URL('./src', import.meta.url)),
    },
  },
  server: {
    // Escuchar en todas las direcciones para facilitar el acceso desde otros dispositivos
    host: '0.0.0.0',
    // Proxy de peticiones al backend para evitar problemas de CORS y conexión
    proxy: {
      '/api': {
        target: 'http://127.0.0.1:8000',
        changeOrigin: true,
        // No reescribir la ruta; mantener /api/v1/...
        rewrite: (path) => path,
      },
    },

  },

})
