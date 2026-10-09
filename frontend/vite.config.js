import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// In development the Python server (port 8000) serves /api and /files.
export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      "/api": "http://127.0.0.1:8000",
      "/files": "http://127.0.0.1:8000",
    },
  },
});
