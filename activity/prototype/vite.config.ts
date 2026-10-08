import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

// PROTOTYPE — satu tunnel menunjuk ke Vite; Vite mem-proxy /api (REST + WS)
// ke backend Python. Pola ini disalin dari preseden multiplayer resmi
// (colyseus/discord-activity) dan membuat Activity bekerja tanpa perubahan
// baik di dalam Discord maupun di browser biasa.
//
// HMR lewat tunnel harus menembak port 443. Di browser biasa, port 3000.
// Set VITE_HMR_PORT=443 saat memakai tunnel (dilakukan skrip run-prototype).
const hmrPort = process.env.VITE_HMR_PORT ? Number(process.env.VITE_HMR_PORT) : 3000;

export default defineConfig({
  plugins: [react()],
  server: {
    port: 3000,
    strictPort: true,
    host: true,
    // Hostname quick tunnel berubah tiap restart — izinkan semua subdomainnya.
    allowedHosts: ['.trycloudflare.com', 'localhost', '127.0.0.1'],
    hmr: { clientPort: hmrPort },
    proxy: {
      '/api': {
        target: 'http://127.0.0.1:8000',
        changeOrigin: true,
        // ws: true meneruskan upgrade WebSocket ke backend — inti sinkronisasi.
        ws: true,
      },
    },
  },
});
