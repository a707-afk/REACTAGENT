import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  base: "/app/",
  build: {
    outDir: "../static/app",
    emptyOutDir: true,
  },
  server: {
    port: 5173,
    proxy: {
      "/retrieve": "http://127.0.0.1:8000",
      "/chat": "http://127.0.0.1:8000",
      "/agent": "http://127.0.0.1:8000",
      "/health": "http://127.0.0.1:8000",
    },
  },
});
