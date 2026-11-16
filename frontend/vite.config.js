import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import { viteSingleFile } from 'vite-plugin-singlefile'
// gera um unico index.html em ../web/dist; em desenvolvimento, /api vai para o backend Python
export default defineConfig({ plugins: [react(), viteSingleFile()], build: { outDir: '../web/dist', emptyOutDir: true },
  server: { proxy: { '/api': 'http://127.0.0.1:8000' } } })
