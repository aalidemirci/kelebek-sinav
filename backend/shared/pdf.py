"""WeasyPrint ile PDF üretiminin TEK kapısı (19.09.2026 çöküş tanısı).

WeasyPrint'in C katmanı (Pango, fontconfig, FreeType) aynı süreçte AYNI ANDA
iki belge dizildiğinde yerel belleği bozabiliyor. 19.09.2026'da paketlenmiş
program "Tümünü indir" sırasında `libpangoft2` içinde erişim ihlaliyle kapandı
(Pango NULL yazı tipi döndürdü; Python istisnası olmadığı için günlüğe iz
düşmedi). Aynı DLL'ler ve gerçek evrak şablonlarıyla Windows'ta koşulan tanıda
iki iş parçacığının eşzamanlı basımı yığın bozulmasıyla (0xC0000374) düştü,
sıralı basım hiç düşmedi. Gömülü sunucu (waitress) altı iş parçacığıyla çalışır
ve salon evrakı, kitapçık bandı, takvim PDF'i birbirinden bağımsız isteklerdir:
kilit yoksa çakışabilirler — en uzunu "Tümünü indir"dir.

Bu modül iki şey yapar:

1. **Süreç genelinde TEK kilit** — her `write_pdf` sırayla koşar. Tek
   kullanıcılı programda bedeli, ikinci PDF işinin birincinin bitmesini
   beklemesidir (tanıda kilit süreyi uzatmadı: iş zaten Python kilidine bağlı).
2. **TEK yazı tipi yapılandırması** — `FontConfiguration` ilk kullanımda kurulur
   ve kilit altında paylaşılır. Aksi hâlde WeasyPrint her belgede fontconfig'i
   baştan kurar; Windows paketinde fontconfig önbelleği hiç yazılmadığından
   (`cache/fontconfig` boş kalıyor) bu, her belgede yazı tiplerinin yeniden
   taranması demekti. Belgede `@font-face` YOKTUR (yalnız gömülü DejaVu);
   olsaydı paylaşılan yapılandırma belgeler arasında taşırdı.

Kural: WeasyPrint'e yalnız buradan gidilir. Koruma testi
`shared/tests/test_pdf.py` uygulama kodunda başka `write_pdf` çağrısına izin
vermez — yeni bir PDF yolu kilidi atlayamasın. (Paket teşhis kipi
`packaging/pyinstaller/giris.py --pdf-duman` sunucu açılmadan tek başına koşar;
kapsam dışıdır.)
"""

from __future__ import annotations

import threading
from typing import Any

_lock = threading.Lock()
_font_config: Any = None


def html_to_pdf(html: str) -> bytes:
    """HTML'i PDF'e çevirir — kilit altında, paylaşılan yazı tipi yapılandırmasıyla."""
    from weasyprint import HTML  # tembel import — ağır bağımlılık (DLL'ler)

    global _font_config
    with _lock:
        if _font_config is None:
            from weasyprint.text.fonts import FontConfiguration

            _font_config = FontConfiguration()
        return bytes(HTML(string=html).write_pdf(font_config=_font_config))
