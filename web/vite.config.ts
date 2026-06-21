import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      // в dev проксируем API на бэкенд (admin-контейнер на :8000)
      "/api": "http://localhost:8000",
    },
  },
});
