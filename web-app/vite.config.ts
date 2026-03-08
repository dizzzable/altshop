import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'
import path from 'path'

const enableSourcemap = process.env.VITE_SOURCEMAP === 'true'

// https://vite.dev/config/
export default defineConfig({
  plugins: [
    react(),
    tailwindcss(),
  ],
  base: '/webapp/',
  resolve: {
    alias: {
      '@': path.resolve(__dirname, './src'),
    },
  },
  server: {
    port: 3000,
    proxy: {
      '/api': {
        target: 'http://localhost:5000',
        changeOrigin: true,
      },
    },
  },
  build: {
    outDir: 'dist',
    sourcemap: enableSourcemap,
    rollupOptions: {
      output: {
        manualChunks(id) {
          const normalizedId = id.replace(/\\/g, '/')
          if (!normalizedId.includes('/node_modules/')) {
            return undefined
          }

          if (
            normalizedId.includes('/react/') ||
            normalizedId.includes('/react-dom/') ||
            normalizedId.includes('/react-router-dom/')
          ) {
            return 'react-vendor'
          }

          if (
            normalizedId.includes('/@tanstack/react-query/') ||
            normalizedId.includes('/zustand/')
          ) {
            return 'state-vendor'
          }

          if (
            normalizedId.includes('/react-hook-form/') ||
            normalizedId.includes('/zod/') ||
            normalizedId.includes('/@hookform/resolvers/')
          ) {
            return 'form-vendor'
          }

          if (normalizedId.includes('/@radix-ui/')) {
            return 'radix-vendor'
          }

          if (normalizedId.includes('/lucide-react/')) {
            return 'icons-vendor'
          }

          if (normalizedId.includes('/axios/') || normalizedId.includes('/jwt-decode/')) {
            return 'network-vendor'
          }

          return undefined
        },
      },
    },
  },
})
