import path from "node:path";
import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// Build a dev-time proxy to the FastAPI service so the SPA can hit
// /api/v1/* without worrying about CORS during `npm run dev`.
// In production the SPA is served from the same origin (or a reverse
// proxy is configured in front of both).
const BACKEND_URL = process.env.VITE_BACKEND_URL ?? "http://localhost:8000";

export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      "@": path.resolve(__dirname, "./src"),
    },
  },
  server: {
    port: 5173,
    proxy: {
      "/api": {
        target: BACKEND_URL,
        changeOrigin: true,
      },
    },
  },
  test: {
    globals: true,
    environment: "jsdom",
    setupFiles: ["./src/test/setup.ts"],
    css: false,
  },
});
