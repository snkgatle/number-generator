import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
import fs from 'fs';

// Auto-detect container runtime (Podman creates /run/.containerenv, Docker creates /.dockerenv)
const isContainer = fs.existsSync('/run/.containerenv') || fs.existsSync('/.dockerenv');
const backendTarget = process.env.BACKEND_URL || (isContainer ? 'http://backend:8000' : 'http://localhost:8000');

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    host: true,
    proxy: {
      '/api': {
        target: backendTarget,
        changeOrigin: true,
      },
    },
  },
});
