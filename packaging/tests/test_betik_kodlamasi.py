"""Paketleme betiklerinin kodlama kapısı.

Windows PowerShell 5.1 (`powershell.exe`) BOM'suz bir `.ps1` dosyasını UTF-8
DEĞİL, sistemin ANSI kod sayfası sanır. Türkçe karakterler bozulur ve bozulan
bayt dizgiyi kapatan tırnağı yiyerek betiği ayrıştırma hatasıyla düşürür —
CI'ın ilk Windows koşusunda tam olarak bu oldu:

    Write-Adim "bitti â€” Ã§Ä±ktÄ±lar: $Output"
    The string is missing the terminator: ".

Çözüm: ASCII dışı karakter içeren `.ps1` dosyaları UTF-8 **BOM ile** yazılır
(PowerShell 5.1 ve 7 ikisi de doğru okur). Bu test kuralı yazıya değil kapıya
bağlar; aynı sınıf hata okulapp'ta kabuk heredoc'unda da yaşanmıştı.
"""

from __future__ import annotations

from pathlib import Path

UTF8_BOM = b"\xef\xbb\xbf"
PAKET_KOKU = Path(__file__).resolve().parent.parent


def _ps1_dosyalari() -> list[Path]:
    return sorted(PAKET_KOKU.rglob("*.ps1"))


def test_turkce_iceren_ps1_dosyalari_bom_tasir() -> None:
    eksik: list[str] = []
    for yol in _ps1_dosyalari():
        ham = yol.read_bytes()
        ascii_disi = any(bayt > 0x7F for bayt in ham)
        if ascii_disi and not ham.startswith(UTF8_BOM):
            eksik.append(str(yol.relative_to(PAKET_KOKU)))
    assert eksik == [], (
        "ASCII dışı karakter içeren .ps1 dosyaları UTF-8 BOM taşımalı "
        f"(PowerShell 5.1 aksi hâlde ANSI sanıp bozar): {eksik}"
    )


def test_ps1_dosyalari_gecerli_utf8() -> None:
    """BOM'lu dosya da olsa içerik gerçekten UTF-8 çözülebilmeli."""
    for yol in _ps1_dosyalari():
        ham = yol.read_bytes().removeprefix(UTF8_BOM)
        ham.decode("utf-8")  # UnicodeDecodeError → test kırılır


def test_debian_bakim_betikleri_ascii() -> None:
    """postinst/prerm `/bin/sh` (dash) ile koşar; ASCII kuralı kapıya bağlanır.

    Kural packaging/README.md'de yazılıydı ama F0 kimlik değişimi başlıklara
    Türkçe `ı` sokmuştu ve hiçbir test yakalamıyordu (F9 denetim bulgusu).
    """
    for ad in ("postinst", "prerm"):
        yol = PAKET_KOKU / "linux" / ad
        ascii_disi = [bayt for bayt in yol.read_bytes() if bayt > 0x7F]
        assert ascii_disi == [], f"packaging/linux/{ad} ASCII olmalı (dash uyumu)"
