"""Türkçe metin yardımcıları (`shared/text.py`) — tek uygulama, iki tüketici.

`tr_title` ders adlarında (`dersler.text.titlecase_tr`) ve branştan üretilen zümre
adlarında (`okul.services.departments`) kullanılır; kural burada sabitlenir.
"""

from __future__ import annotations

from shared.text import tr_lower, tr_title, tr_upper


def test_tr_upper_ve_tr_lower_i_harflerini_korur() -> None:
    assert tr_upper("istanbul ılıca") == "İSTANBUL ILICA"
    assert tr_lower("İSTANBUL ILICA") == "istanbul ılıca"


def test_tr_title_baslik_bicimi() -> None:
    assert tr_title("TÜRK DİLİ VE EDEBİYATI") == "Türk Dili ve Edebiyatı"
    assert tr_title("ingilizce") == "İngilizce"
    assert tr_title("  BİLİŞİM   TEKNOLOJİLERİ ") == "Bilişim Teknolojileri"
    # '/' parçaları ayrı ayrı başlıklaşır; bağlaç kelime başında büyür.
    assert tr_title("SPOR/GÖRSEL SANATLAR") == "Spor/Görsel Sanatlar"
    assert tr_title("VE ÖTESİ") == "Ve Ötesi"
    assert tr_title("") == ""
