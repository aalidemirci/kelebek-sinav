#!/usr/bin/env bash
# =============================================================================
# scripts/gates.sh — Kelebek Sınav kapı koşusu (backend)
# =============================================================================
# Test + lint + biçim + tip kontrolünü sırayla Docker konteynerinde çalıştırır.
# Herhangi biri kırmızı olursa betik durur (`set -e`).
# =============================================================================
set -euo pipefail

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
docker compose run --rm frontend npm test -- --run

echo "== Tüm kapılar yeşil =="
