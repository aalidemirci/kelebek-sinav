#!/usr/bin/env bash
# =============================================================================
# scripts/gates.sh — Kelebek Sınav kapı koşusu
# =============================================================================
# Test + lint + biçim + tip kontrolünü sırayla Docker konteynerinde çalıştırır.
# Herhangi biri kırmızı olursa betik durur (`set -e`).
#
# Kanıt deseni (F4, 29.08.2026): bu makinede `docker compose run` zincirinin
# çıkış kodunu aralıklı olarak yuttuğu gözlendi (vitest, mypy ve prettier
# adımlarında birer kez). Bu yüzden her adım çıkış koduna EK olarak pozitif
# kanıt üretir: komut konteyner İÇİNDE başarılıysa nöbetçi satırı
# (KAPI_OK_<ad>) basılır ve host tarafında aranır — nöbetçi yoksa kapı
# kırmızıdır (fail-closed). Çıkış kodu denetimi de yerinde durur (pipefail);
# kodların düzgün çalıştığı ortamlarda (Linux/CI) nöbetçi yalnız ek sigortadır.
# =============================================================================
set -euo pipefail

# Git Bash (Windows) MSYS yol dönüşümü `-w /repo` gibi konteyner yollarını
# Windows yoluna çevirip koşuyu kırar; bu değişken dönüşümü kapatır,
# Linux'ta hiçbir etkisi yoktur.
export MSYS_NO_PATHCONV=1

KAPI_LOG="$(mktemp)"
# Depo sızıntı kapısının girdisi: `git ls-files` çıktısı. Liste DEPO KÖKÜNE
# yazılır çünkü konteyner yalnız orayı (/repo) görür; koşu bitince silinir.
DEPO_LISTESI=".ks-depo-listesi.tmp"
trap 'rm -f "$KAPI_LOG" "$DEPO_LISTESI"' EXIT

# kapi <etiket> <nöbetçi> <servis> <komut> [compose run ek bayrakları...]
# Komutu konteynerde koşar; çıkış kodu (pipefail üzerinden) VE nöbetçi kanıtı
# birlikte denetlenir. Nöbetçi yalnız komut konteyner içinde başarılıysa
# basılır; zincir çıkış kodunu yutsa bile kırık adım buradan yakalanır.
kapi() {
  local etiket="$1" nobetci="$2" servis="$3" komut="$4"
  shift 4
  echo "== $etiket =="
  docker compose run --rm "$@" "$servis" sh -c "$komut && echo KAPI_OK_$nobetci" | tee "$KAPI_LOG"
  if ! grep -q "KAPI_OK_$nobetci" "$KAPI_LOG"; then
    echo "HATA: '$etiket' nöbetçi kanıtı üretmedi (çıkış kodu yutulmuş olabilir)" >&2
    exit 1
  fi
}

# KVKK kapısı EN BAŞTA: en ucuz denetim (saniyeler) ve en pahalı hata sınıfı —
# depoya giren kişisel veri `.gitignore` ile geçmişten çıkmaz. Dosya listesini
# HOST üretir: backend imajında git YOKTUR (denendi), betik listeyi okur.
git ls-files -z > "$DEPO_LISTESI"
kapi "depo sızıntısı (KVKK)" depo_sizinti backend "python packaging/depo_sizintisi.py --kok /repo --liste /repo/$DEPO_LISTESI" -w /repo

kapi "pytest" pytest backend "pytest"
kapi "ruff check" ruff backend "ruff check ."
kapi "ruff format --check" ruff_format backend "ruff format --check ."
kapi "mypy" mypy backend "mypy ."

# Masaüstü kabuğu (desktop/) depo kökünde durur ve backend paketlerini import eder;
# bu yüzden `-w /repo` ile koşulur, ruff/mypy yapılandırması backend'den verilir.
# AYRI koşu bilinçli: desktop testleri günlük (logging) yapılandırmasını değiştirdiği
# için backend testleriyle aynı pytest sürecinde koşarlarsa birbirlerini etkilerler.
kapi "desktop + packaging: pytest" desktop_pytest backend \
  "pytest desktop/tests packaging/tests -q --no-cov" -w /repo

kapi "desktop: ruff" desktop_ruff backend \
  "ruff check desktop --config backend/pyproject.toml && ruff format --check desktop --config backend/pyproject.toml" \
  -w /repo

kapi "desktop: mypy" desktop_mypy backend \
  "mypy desktop --config-file backend/pyproject.toml" \
  -w /repo -e MYPYPATH=/repo/backend

kapi "packaging: ruff" packaging_ruff backend \
  "ruff check packaging --config backend/pyproject.toml && ruff format --check packaging --config backend/pyproject.toml" \
  -w /repo

kapi "packaging: mypy" packaging_mypy backend \
  "mypy packaging --config-file backend/pyproject.toml" \
  -w /repo -e MYPYPATH=/repo/backend

kapi "frontend: typecheck" fe_typecheck frontend "npm run typecheck"
kapi "frontend: eslint" fe_eslint frontend "npx eslint src"
kapi "frontend: prettier --check" fe_prettier frontend "npx prettier --check src"

echo "== frontend: vitest =="
# Vitest adımının kanıtı nöbetçiden güçlü: JSON raporu vitest'in KENDİ başarı
# yargısını taşır (nöbetçi, vitest konteyner içinde yanlışlıkla 0 dönerse de
# basılırdı; rapor bu durumu da yakalar). npm sarmalayıcısı zincirden çıkarıldı.
# Rapor yoksa ya da success:true değilse kapı kırmızıdır (fail-closed).
rm -f frontend/vitest-sonuc.json
docker compose run --rm frontend npx vitest run \
  --reporter=default --reporter=json --outputFile=vitest-sonuc.json
if ! grep -Eq '"success": ?true' frontend/vitest-sonuc.json; then
  echo "HATA: frontend test raporu başarı doğrulamadı (çıkış kodu yutulmuş olabilir)" >&2
  exit 1
fi
rm -f frontend/vitest-sonuc.json

echo "== Tüm kapılar yeşil =="
