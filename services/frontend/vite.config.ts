import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

// Порт dev-сервера внутри контейнера и внешний порт, на котором nginx
// принимает HMR-соединения (см. nginx/nginx.conf и docker-compose.yml).
const serverPort = Number(process.env.VITE_PORT ?? 5173);
const hmrClientPort = Number(process.env.VITE_HMR_CLIENT_PORT ?? 80);

export default defineConfig({
  plugins: [react()],
  server: {
    host: true,
    port: serverPort,
    // В dev-контейнере сервер доступен через reverse-proxy под разными именами.
    allowedHosts: true,
    hmr: {
      clientPort: hmrClientPort,
    },
  },
});
