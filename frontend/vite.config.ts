import react from "@vitejs/plugin-react";
import path from "node:path";
import { defineConfig } from "vite";

// Vite yapılandırması — OYS `frontend/vite.config.ts`'ten UYARLANMIŞTIR (Görev 3).
// __OYS_VERSION__ gömme mekanizması ve vendor chunk bölme (OYS'ye özgü, ADR-0033)
// ÇIKARILDI — tek kullanıcılı masaüstü uygulamada gerek yok. Build çıktısı
// standart `dist/` bırakılır (nginx yerine masaüstü paketleme — pywebview —
// bu dizini kopyalayacak; bkz. README "Mimari").
export default defineConfig({
  plugins: [react()],
  resolve: {
    // `@/lib/api` → `src/lib/api`. tsconfig.json `paths` ile birebir eşleşmeli.
    alias: {
      "@": path.resolve(__dirname, "./src"),
    },
  },
  server: {
    host: "0.0.0.0", // container dışından erişilebilsin
    port: 5173,
    strictPort: true,
    // Geliştirmede backend Docker Compose ağında `backend` servis adıyla erişilir.
    // Container DIŞINDA (host'tan doğrudan `vite dev` — YASAK, CLAUDE.md/README
    // "saf Docker" kuralı — yalnız referans için) `http://127.0.0.1:8000` olurdu.
    proxy: {
      "/api": { target: "http://backend:8000", changeOrigin: true },
    },
    // Windows bind-mount'ta dosya olayları güvenilmez — HMR için polling şart.
    watch: { usePolling: true },
  },
  preview: {
    host: "0.0.0.0",
    port: 5173,
  },
});
