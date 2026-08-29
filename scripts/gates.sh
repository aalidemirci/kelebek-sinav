#!/usr/bin/env bash
# =============================================================================
# scripts/gates.sh — Kelebek Sınav kapı koşusu (backend)
# =============================================================================
# Test + lint + biçim + tip kontrolünü sırayla Docker konteynerinde çalıştırır.
# Herhangi biri kırmızı olursa betik durur (`set -e`).
# =============================================================================
set -euo pipefail

# Git Bash (Windows) MSYS yol dönüşümü `-w /repo` gibi konteyner yollarını
# Windows yoluna çevirip koşuyu kırar; bu değişken dönüşümü kapatır,
# Linux'ta hiçbir etkisi yoktur.
export MSYS_NO_PATHCONV=1

echo "== pytest =="
docker compose run --rm backend pytest

echo "== ruff check =="
docker compose run --rm backend ruff check .

echo "== ruff format --check =="
docker compose run --rm backend ruff format --check .

echo "== mypy =="
docker compose run --rm backend mypy .

# Masaüstü kabuğu (desktop/) depo kökünde durur ve backend paketlerini import eder;
# bu yüzden `-w /repo` ile koşulur, ruff/mypy yapılandırması backend'den verilir.
# AYRI koşu bilinçli: desktop testleri günlük (logging) yapılandırmasını değiştirdiği
# için backend testleriyle aynı pytest sürecinde koşarlarsa birbirlerini etkilerler.
echo "== desktop + packaging: pytest =="
docker compose run --rm -w /repo backend pytest desktop/tests packaging/tests -q --no-cov

echo "== desktop: ruff =="
docker compose run --rm -w /repo backend sh -c \
  "ruff check desktop --config backend/pyproject.toml && ruff format --check desktop --config backend/pyproject.toml"

echo "== desktop: mypy =="
docker compose run --rm -w /repo -e MYPYPATH=/repo/backend backend mypy desktop --config-file backend/pyproject.toml

echo "== packaging: ruff =="
docker compose run --rm -w /repo backend sh -c \
  "ruff check packaging --config backend/pyproject.toml && ruff format --check packaging --config backend/pyproject.toml"

echo "== packaging: mypy =="
docker compose run --rm -w /repo -e MYPYPATH=/repo/backend backend mypy packaging --config-file backend/pyproject.toml

echo "== frontend: typecheck =="
docker compose run --rm frontend npm run typecheck

echo "== frontend: eslint =="
docker compose run --rm frontend npx eslint src

echo "== frontend: prettier --check =="
docker compose run --rm frontend npx prettier --check src

echo "== frontend: vitest =="
# Kapı deliği önlemi (F4, 29.08.2026): tam takım koşusunda testler kırmızıyken
# zincir (vitest kapanışı → npm → docker compose run --rm) bir kez 0 döndürdü;
# yarış yeniden üretilemedi. Kapı artık çıkış koduna güvenmez: vitest JSON
# raporu host'ta okunur ve `success:true` kanıtı aranır — rapor yoksa ya da
# başarı doğrulanamazsa kapı kırmızıdır (fail-closed). npm sarmalayıcısı da
# zincirden çıkarıldı (bir katman az).
rm -f frontend/vitest-sonuc.json
docker compose run --rm frontend npx vitest run \
  --reporter=default --reporter=json --outputFile=vitest-sonuc.json
if ! grep -Eq '"success": ?true' frontend/vitest-sonuc.json; then
  echo "HATA: frontend test raporu başarı doğrulamadı (çıkış kodu yutulmuş olabilir)" >&2
  exit 1
fi
rm -f frontend/vitest-sonuc.json

echo "== Tüm kapılar yeşil =="
