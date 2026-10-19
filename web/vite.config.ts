import tailwindcss from "@tailwindcss/vite";
import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

// Em desenvolvimento, /api vai para o FastAPI local (make rodar; outra porta: API_URL=...).
// Mesma origem para o navegador: o cookie SameSite=Strict e a CSP valem como em produção.
const API = process.env.API_URL ?? "http://localhost:8000";
export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    port: 5173,
    proxy: {
      "/api": { target: API, changeOrigin: false, ws: true },
    },
  },
  build: { outDir: "dist", sourcemap: false },
});
