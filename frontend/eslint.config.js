// ESLint v9 flat config (Tur 43). React + TypeScript + react-hooks + Prettier uyumu.
// Eski `.eslintrc.*` formatı v9'da yer almıyor; flat config kullanılır.

import js from "@eslint/js";
import tseslint from "typescript-eslint";
import reactPlugin from "eslint-plugin-react";
import reactHooks from "eslint-plugin-react-hooks";
import prettierConfig from "eslint-config-prettier";
import globals from "globals";

export default [
  // Hariç tutulanlar
  {
    ignores: ["dist", "build", "coverage", "node_modules", ".vite"],
  },

  // Temel JS önerileri
  js.configs.recommended,

  // TypeScript önerileri (recommended-type-checked yerine recommended — hız için)
  ...tseslint.configs.recommended,

  // React + hooks
  {
    files: ["**/*.{ts,tsx}"],
    languageOptions: {
      ecmaVersion: 2020,
      globals: {
        ...globals.browser,
        ...globals.node,
      },
      parserOptions: {
        ecmaFeatures: { jsx: true },
      },
    },
    plugins: {
      react: reactPlugin,
      "react-hooks": reactHooks,
    },
    settings: {
      react: { version: "18.3" },
    },
    rules: {
      // React 17+ JSX runtime — `import React from "react"` gerekmez.
      "react/react-in-jsx-scope": "off",
      "react/prop-types": "off",
      ...reactHooks.configs.recommended.rules,
      // TS strict zaten unused param/local'i yakalıyor; çift uyarı yapmayalım.
      "@typescript-eslint/no-unused-vars": [
        "warn",
        { argsIgnorePattern: "^_", varsIgnorePattern: "^_" },
      ],
      // Mevcut kod tabanında `any` az kullanılıyor ama varlığını ESLint hatası
      // yapmak Tur 43 kapsamını aşar — uyarı olarak kalsın, ileride sertleşir.
      "@typescript-eslint/no-explicit-any": "warn",
    },
  },

  // Test dosyalarında daha gevşek
  {
    files: ["**/*.test.{ts,tsx}", "src/test/**"],
    languageOptions: {
      globals: {
        ...globals.browser,
        ...globals.node,
      },
    },
    rules: {
      "@typescript-eslint/no-explicit-any": "off",
    },
  },

  // Prettier çatışmalarını sustur (en sona koyulmalı)
  prettierConfig,
];
