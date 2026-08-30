"""Masaüstü kabuğu — Kelebek Sınav'ı yerel bir pencerede çalıştırır.

Bu paket Django uygulamasının DIŞINDADIR: `backend/` içindeki hiçbir modül
buraya bağımlı değildir (tek istisna `config/settings.py`'deki koşullu oturum
belirteci middleware kaydı — yalnız `KS_SESSION_TOKEN` doluyken devreye girer).
Böylece geliştirme/test koşusu masaüstü bağımlılıkları (pywebview) olmadan da
yeşil kalır.

Açılış sırası `main.py`'de; tasarım §5.3 "Çalışma zamanı düzeni".
"""

from __future__ import annotations
