"""Uygulama parolası — konsol kurtarma aracı (tasarım §6).

Arayüz açılamadığında (yarım kalmış geçiş, kayıp güvenlik dosyası şüphesi,
kilitli veriyle destek çağrısı) tek çıkış yolu budur. Program tek kullanıcılı
olduğundan yetki denetimi yoktur; komut yalnız veri klasörüne erişebilen kişi
tarafından çalıştırılabilir.

Kullanım (paketlenmiş kurulumda `manage.py` yoktur; bu araç geliştirme ve
destek senaryosu içindir):

    python manage.py app_password status
    python manage.py app_password enable            # parolayı sorar, kurtarma anahtarı basar
    python manage.py app_password resume            # yarım kalan geçişi tamamlar
    python manage.py app_password disable           # parolayı kaldırır, alanları çözer
    python manage.py app_password recover           # kurtarma anahtarıyla yeni parola

Parolalar VARSAYILAN OLARAK gizli istemle (getpass) alınır — komut satırı
geçmişine ve süreç listesine düşmez. `--password/--new-password/--recovery-key`
seçenekleri yalnız otomasyon/test içindir ve bu riski taşır.
"""

from __future__ import annotations

from getpass import getpass
from typing import Any

from django.core.management.base import BaseCommand, CommandError, CommandParser

from apps.okul.services import app_password

ACTIONS = ("status", "enable", "resume", "disable", "recover")


class Command(BaseCommand):
    help = "Uygulama parolasını kurar, açar, kaldırır veya yarım kalan geçişi tamamlar."

    def add_arguments(self, parser: CommandParser) -> None:
        parser.add_argument("action", choices=ACTIONS, help="Yapılacak işlem.")
        parser.add_argument("--password", default=None, help="Parola (otomasyon; risklidir).")
        parser.add_argument("--new-password", default=None, help="Yeni parola (otomasyon).")
        parser.add_argument("--recovery-key", default=None, help="Kurtarma anahtarı (otomasyon).")
        parser.add_argument(
            "--force",
            action="store_true",
            help="resume: damga 'tamam' dese bile şifreleme geçişini yeniden koşar.",
        )

    def handle(self, *args: Any, **options: Any) -> None:
        action = str(options["action"])
        try:
            getattr(self, f"_{action}")(options)
        except app_password.AppPasswordError as exc:
            raise CommandError(str(exc)) from exc

    # -- işlemler ----------------------------------------------------------
    def _status(self, options: dict[str, Any]) -> None:
        durum = app_password.status()
        self.stdout.write(f"Parola kurulu    : {'evet' if durum['password_set'] else 'hayır'}")
        self.stdout.write(f"Kilitli          : {'evet' if durum['locked'] else 'hayır'}")
        self.stdout.write(
            "Yarım geçiş      : " + (durum["transition"] or "yok")  # SIFRELENIYOR / COZULUYOR / yok
        )
        self.stdout.write("Korunan alanlar  : " + ", ".join(durum["protected_fields"]))
        self.stdout.write(f"Güvenlik dosyası : {app_password.state_path()}")

    def _enable(self, options: dict[str, Any]) -> None:
        parola = self._ask(options, "password", "Yeni uygulama parolası: ", confirm=True)
        kurtarma = app_password.enable(password=parola)
        self.stdout.write(self.style.SUCCESS("Parola kuruldu; hassas alanlar şifrelendi."))
        self.stdout.write("")
        self.stdout.write("KURTARMA ANAHTARI (bir daha gösterilmez — yazdırın ve saklayın):")
        self.stdout.write(self.style.WARNING(f"    {kurtarma}"))

    def _resume(self, options: dict[str, Any]) -> None:
        parola = self._ask(options, "password", "Uygulama parolası: ")
        app_password.unlock(password=parola)  # açılışta yarım geçiş kendiliğinden tamamlanır
        sonuc = app_password.resume_pending(force=bool(options.get("force")))
        if sonuc["resumed"]:
            self.stdout.write(
                self.style.SUCCESS(f"Geçiş tamamlandı ({sonuc['rows']} kayıt yeniden yazıldı).")
            )
        else:
            self.stdout.write("Tamamlanacak geçiş yok.")

    def _disable(self, options: dict[str, Any]) -> None:
        parola = self._ask(options, "password", "Uygulama parolası: ")
        app_password.disable(password=parola)
        self.stdout.write(self.style.SUCCESS("Parola kaldırıldı; alanlar düz metne döndürüldü."))
        self.stdout.write(
            "Not: eski yedekler hâlâ eski anahtarla şifrelidir; arşivlenen "
            "guvenlik-arsiv-*.json dosyasını silmeyin."
        )

    def _recover(self, options: dict[str, Any]) -> None:
        anahtar = options.get("recovery_key") or input("Kurtarma anahtarı: ")
        yeni = self._ask(options, "new_password", "Yeni uygulama parolası: ", confirm=True)
        app_password.unlock_with_recovery(recovery_key=anahtar, new_password=yeni)
        self.stdout.write(self.style.SUCCESS("Kurtarma başarılı; yeni parola geçerli."))

    # -- yardımcı ----------------------------------------------------------
    def _ask(self, options: dict[str, Any], key: str, prompt: str, *, confirm: bool = False) -> str:
        verilen = options.get(key)
        if verilen:
            return str(verilen)
        deger = getpass(prompt)
        if confirm and deger != getpass("Parolayı yeniden girin: "):
            raise CommandError("Parolalar eşleşmedi.")
        return deger
