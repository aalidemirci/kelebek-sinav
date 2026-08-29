/// <reference types="vitest" />
import react from "@vitejs/plugin-react";
import path from "node:path";
import { defineConfig } from "vitest/config";

// Vitest yapılandırması — OYS `frontend/vitest.config.ts`'ten UYARLANMIŞTIR
// (Görev 3). `__OYS_VERSION__` define'ı yok (vite.config.ts'te de kaldırıldı).
export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      "@": path.resolve(__dirname, "./src"),
    },
  },
  test: {
    globals: true, // describe/it/expect global
    environment: "jsdom", // DOM API'leri React component testleri için
    setupFiles: ["./src/test/setup.ts"],
    css: false, // Tailwind .css import'ları test'te yüklenmez
    include: ["src/**/*.{test,spec}.{ts,tsx}"],
    exclude: ["node_modules", "dist"],
    coverage: {
      provider: "v8",
      reporter: ["text", "html", "json", "lcov"],
      include: ["src/**/*.{ts,tsx}"],
      exclude: ["src/**/*.test.{ts,tsx}", "src/test/**", "src/main.tsx", "src/vite-env.d.ts"],
    },
  },
});
