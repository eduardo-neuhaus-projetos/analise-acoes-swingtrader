import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    strictPort: true, // porta ocupada deve dar erro, e não abrir o app ligado a um backend antigo
    host: "127.0.0.1",
    proxy: { "/api": process.env.SWING_B3_API ?? "http://127.0.0.1:8000" },
  },
  build: { chunkSizeWarningLimit: 1200 },
});
