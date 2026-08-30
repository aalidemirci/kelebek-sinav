"""`apps.okul.normalize` — saf normalize ediciler (KS: sınıf/şube + ad bölme).

DD'nin TCKN/telefon/tarih/cinsiyet testleri kalktı (fonksiyonlar alınmadı —
kelebek o verileri toplamaz, tasarım §5).
"""

from __future__ import annotations

from apps.okul import normalize


class TestAsciiUpper:
    def test_turkce_harfler_katlanir(self) -> None:
        assert normalize._ascii_upper("şğüiıöç") == "SGUIIOC"

    def test_ascii_degismez(self) -> None:
        assert normalize._ascii_upper("abc") == "ABC"


class TestClassSection:
    def test_bicim_varyantlari(self) -> None:
        for ham in ("10/A", "10-A", "10 A", " 10 / A "):
            assert normalize.normalize_class_section(ham) == (10, "A")

    def test_turkce_sube_harfi_korunur(self) -> None:
        """Şube harfi ASCII'ye KATLANMAZ — Türk alfabesindeki harf aynen kalır."""
        assert normalize.normalize_class_section("9/Ş") == (9, "Ş")
        assert normalize.normalize_class_section("9/ş") == (9, "Ş")

    def test_i_ile_nokta_siz_i_ayri_subelerdir(self) -> None:
        """KORUMA TESTİ: 10/I ile 10/İ aynı okulda iki AYRI şubedir.

        e-Okul sınıf listesi şubeleri Türk alfabesi sırasıyla açar (…H, I, İ,
        J…); bu iki harfi ASCII'ye katlayan bir normalize edici iki sınıfın
        öğrencilerini sessizce tek şubede toplar (gerçek ihraçta yakalandı).
        """
        assert normalize.normalize_class_section("10/I") == (10, "I")
        assert normalize.normalize_class_section("10/İ") == (10, "İ")
        assert normalize.normalize_class_section("10/i") == (10, "İ")
        assert normalize.normalize_class_section("10/ı") == (10, "I")
        assert normalize.normalize_class_section("10/I") != normalize.normalize_class_section(
            "10/İ"
        )

    def test_turk_alfabesi_siralamasi(self) -> None:
        """Şube harfi katlanmadığı için sıralama da Türkçe olmalı ('Ç' < 'D')."""
        subeler = ["Z", "İ", "I", "Ç", "C", "Ş", "S", "Ğ", "G", "A"]
        assert sorted(subeler, key=normalize.tr_sort_key) == [
            "A",
            "C",
            "Ç",
            "G",
            "Ğ",
            "I",
            "İ",
            "S",
            "Ş",
            "Z",
        ]

    def test_turkce_harfler_z_den_sonraya_dusmez(self) -> None:
        """KORUMA TESTİ: kod noktası sırasında Ç/Ğ/İ/Ö/Ş/Ü, 'Z'den BÜYÜKTÜR."""
        assert "Ç" > "Z" and "İ" > "Z"  # ham karşılaştırma (yanlış sıra)
        assert normalize.tr_sort_key("Ç") < normalize.tr_sort_key("Z")
        assert normalize.tr_sort_key("İ") < normalize.tr_sort_key("Z")
        assert normalize.tr_sort_key("I") < normalize.tr_sort_key("İ")

    def test_kume_disi_seviye_none(self) -> None:
        assert normalize.normalize_class_section("8/A") is None
        assert normalize.normalize_class_section("13/A") is None

    def test_kume_parametriktir(self) -> None:
        assert normalize.normalize_class_section("5/A", valid_levels=(5, 6, 7, 8)) == (5, "A")
        assert normalize.normalize_class_section("9/A", valid_levels=(5, 6, 7, 8)) is None

    def test_hazirlik_yalniz_kumede_varsa(self) -> None:
        assert normalize.normalize_class_section("HAZIRLIK/A", valid_levels=(0, 9, 10, 11, 12)) == (
            0,
            "A",
        )
        assert normalize.normalize_class_section("HAZ B", valid_levels=(0, 9)) == (0, "B")
        assert normalize.normalize_class_section("Hz-C", valid_levels=(0, 9)) == (0, "C")
        assert normalize.normalize_class_section("HAZIRLIK/A") is None  # varsayılan 9-12

    def test_bos_ve_cozumsuz_none(self) -> None:
        assert normalize.normalize_class_section(None) is None
        assert normalize.normalize_class_section("") is None
        assert normalize.normalize_class_section("sınıfsız") is None


class TestSplitFullName:
    def test_son_kelime_soyad(self) -> None:
        assert normalize.split_full_name("EMRE CAN YILMAZ") == ("EMRE CAN", "YILMAZ")

    def test_tek_kelime(self) -> None:
        assert normalize.split_full_name("YILMAZ") == ("YILMAZ", "")

    def test_bos_ve_none(self) -> None:
        assert normalize.split_full_name("") == ("", "")
        assert normalize.split_full_name(None) == ("", "")

    def test_ham_birakilir_title_case_uygulanmaz(self) -> None:
        """TR büyük harf tuzağı: görüntü biçimi başka katmanda (CLAUDE.md §2)."""
        assert normalize.split_full_name("emre can yılmaz") == ("emre can", "yılmaz")
