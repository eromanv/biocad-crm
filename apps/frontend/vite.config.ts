import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

const apiTarget = process.env.VITE_PROXY_TARGET ?? "http://localhost:8001";

export default defineConfig({
  plugins: [react()],
  server: {
    host: "0.0.0.0",
    port: 5174,
    strictPort: true,
    hmr: {
      clientPort: 5174,
    },
    watch: {
      usePolling: true,
    },
    proxy: {
      "/api": {
        target: apiTarget,
        changeOrigin: true,
      },
      "/health": {
        target: apiTarget,
        changeOrigin: true,
      },
    },
  },
});
