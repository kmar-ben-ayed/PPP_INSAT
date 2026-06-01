import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      // Approach A — FastAPI proxy to Hugging Face Spaces on port 8002
      "/api-a": {
        target: "http://localhost:8002",
        changeOrigin: true,
        rewrite: (path) => path.replace(/^\/api-a/, ""),
      },
      // Approach B — Qwen FastAPI (Ollama local on port 8000)
      "/api-b": {
        target: "http://localhost:8000",
        changeOrigin: true,
        rewrite: (path) => path.replace(/^\/api-b/, ""),
      },
      "/api-c": {
        target: "http://localhost:8081",
        changeOrigin: true,
        rewrite: (path) => path.replace(/^\/api-c/, ""),
      },
      // Generic fallback — also points to Approach B during local dev
      "/api": {
        target: "http://localhost:8000",
        changeOrigin: true,
        rewrite: (path) => path.replace(/^\/api/, ""),
      },
    },
  },
});
