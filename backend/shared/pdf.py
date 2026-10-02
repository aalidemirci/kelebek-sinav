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
from collections.abc import Iterable
from typing import Any, NamedTuple

_lock = threading.Lock()
_font_config: Any = None


def _shared_font_config() -> Any:
    """Paylaşılan yazı tipi yapılandırması — yalnız kilit ALTINDA çağrılır."""
    global _font_config
    if _font_config is None:
        from weasyprint.text.fonts import FontConfiguration

        _font_config = FontConfiguration()
    return _font_config


def html_to_pdf(html: str) -> bytes:
    """HTML'i PDF'e çevirir — kilit altında, paylaşılan yazı tipi yapılandırmasıyla."""
    from weasyprint import HTML  # tembel import — ağır bağımlılık (DLL'ler)

    with _lock:
        return bytes(HTML(string=html).write_pdf(font_config=_shared_font_config()))


class FittedPdf(NamedTuple):
    """`html_to_pdf_fit` sonucu: basılan PDF, varyantın SIRASI (`variant`) ve sayfa sayısı."""

    pdf: bytes
    variant: int
    pages: int


def html_to_pdf_fit(variants: Iterable[str], *, max_pages: int = 1) -> FittedPdf:
    """Varyantları SIRAYLA dizer; `max_pages`e sığan İLKİNİ basar.

    Sayfaya sığdırma için vardır (sınav takvimi, 01.10.2026): çağıran aynı
    belgenin rahattan sıkıya dizili varyantlarını verir, sığan ilk varyant
    basılır. Hiçbiri sığmazsa EN AZ sayfalı olan basılır (eşitlikte öndeki —
    çağıranın sırası okunurluk tercihidir).

    Ölçüm yaklaşık değil, gerçek dizimdir (`render()` — PDF'e yazmadan sayfa
    sayısı). Varyantlar tembel üretilebilir (üreteç): yalnız gereken kadarı
    şablondan geçer — üretim de kilit altında koşar. Tek kapı kuralı burada da
    geçerlidir: kilit bütün denemeleri kapsar, yazı tipi yapılandırması paylaşılır.
    """
    from weasyprint import HTML  # tembel import — ağır bağımlılık (DLL'ler)

    with _lock:
        font_config = _shared_font_config()
        best: tuple[int, int, Any] | None = None  # (sayfa, sıra, belge)
        for index, html in enumerate(variants):
            document = HTML(string=html).render(font_config=font_config)
            pages = len(document.pages)
            if pages <= max_pages:
                return FittedPdf(bytes(document.write_pdf()), index, pages)
            if best is None or pages < best[0]:
                best = (pages, index, document)
        if best is None:
            raise ValueError("Basılacak varyant verilmedi.")
        pages, index, document = best
        return FittedPdf(bytes(document.write_pdf()), index, pages)
