import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import path from 'path'

export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      '@': path.resolve(__dirname, './src'),
    },
  },
  build: {
    outDir: 'static/landing',
    emptyOutDir: true,
    rollupOptions: {
      input: 'src/landing/main.tsx',
      output: {
        entryFileNames: 'js/landing.js',
        chunkFileNames: 'js/[name].js',
        assetFileNames: (info) => {
          if (info.name?.endsWith('.css')) return 'css/landing.css'
          return 'assets/[name][extname]'
        },
      },
    },
  },
})
