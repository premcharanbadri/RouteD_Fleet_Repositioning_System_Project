import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// Proxy API + WebSocket traffic to the FastAPI backend during development so the
// frontend can use same-origin relative paths.
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      "/api": "http://localhost:8000",
      "/ws": { target: "ws://localhost:8000", ws: true },
    },
  },
});
