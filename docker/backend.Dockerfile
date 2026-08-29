# =============================================================================
# docker/backend.Dockerfile — Kelebek Sınav backend (geliştirme imajı)
# =============================================================================
# OYS (backend/Dockerfile) referans alınmıştır ancak WeasyPrint 63, cairo/
# gdk-pixbuf KULLANMAZ (53. sürümden itibaren saf-Python render motoruna geçti);
# bu yüzden OYS'nin libpangocairo-1.0-0 / libgdk-pixbuf-2.0-0 mirası BURAYA
# TAŞINMADI — yalnız pango metin dizilimi + harfbuzz + fontconfig + DejaVu.
# =============================================================================

FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    TZ=Europe/Istanbul

# WeasyPrint 63 minimal sistem bağımlılıkları (cairo/gdk-pixbuf YOK):
#  - libpango-1.0-0 + libpangoft2-1.0-0: metin dizilimi + font motoru
#  - libharfbuzz0b + libharfbuzz-subset0: harf şekillendirme
#  - libfontconfig1 + libglib2.0-0: font keşfi / temel glib
#  - fonts-dejavu-core: Türkçe karakterler (ç/ş/ğ/ü/ö) tam kapsama
RUN apt-get update && apt-get install -y --no-install-recommends \
        libpango-1.0-0 \
        libpangoft2-1.0-0 \
        libharfbuzz0b \
        libharfbuzz-subset0 \
        libfontconfig1 \
        libglib2.0-0 \
        fonts-dejavu-core \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Bağımlılıkları önce kopyala (katman önbelleği).
COPY requirements.txt requirements-dev.txt /app/
RUN pip install -r requirements-dev.txt

# Kod geliştirmede bind-mount ile gelir (docker-compose.yml); imajda da bir
# kopya bulunsun (bind-mount olmadan da çalışabilsin).
COPY . /app

CMD ["python", "manage.py", "runserver", "0.0.0.0:8000"]
