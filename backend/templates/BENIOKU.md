# Evrak şablonları

F4'te OYS `templates/sinav_islemleri/` setinden taşındı (AYNEN; yalnız ad
alanı `sinav_islemleri/` → `sinav/` yol düzeltmesi):

- `print/_design.css` — "Kurumsal Sade" baskı tasarım dili (bayt-eş kopya).
  `base.html` içine Django `{% include %}` ile gömülür; `text-transform`
  YASAK, DejaVu Sans, `--pr-*` token'ları.
- `sinav/reports/` — 11 şablon (base, _head, r1-r4, r6-r9, room_layout).
  R6 gözetmen şablonu F7'de, `room_layout.html` oturumsuz boş plan içindir.
- `sinav/booklet_overlay.html` — F5 kitapçık bandı (henüz bağlanmadı).
- `sinav/calendar_pdf.html` — F6 takvim PDF'i; `documents/base.html`'i
  extends eder, o taban F6'da taşınacak (bilinçli açık uç).

PyInstaller spec bu ağacı pakete kaynak olarak kopyalar.
