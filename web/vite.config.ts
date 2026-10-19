import tailwindcss from "@tailwindcss/vite";
import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

// Em desenvolvimento, /api vai para o FastAPI local (make rodar). Mesma origem para o
// navegador: o cookie SameSite=Strict e a CSP continuam valendo como em produção.
export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    port: 5173,
    proxy: {
      "/api": { target: "http://localhost:8000", changeOrigin: false, ws: true },
    },
  },
  build: { outDir: "dist", sourcemap: false },
});
