# Evrak şablonları

F4'te OYS `templates/sinav_islemleri/` setinden taşındı (AYNEN; yalnız ad
alanı `sinav_islemleri/` → `sinav/` yol düzeltmesi):

- `print/_design.css` — "Kurumsal Sade" baskı tasarım dili (bayt-eş kopya).
  `base.html` içine Django `{% include %}` ile gömülür; `text-transform`
  YASAK, DejaVu Sans, `--pr-*` token'ları.
- `print/_bilesenler.css` + `print/_imza.html` + `print/_imza_seridi.html` —
  01.10.2026'dan beri iki evrak ailesinin ORTAK imza dili: her iki taban da
  CSS'i `_design.css`in ardından gömer, imza hücresi `_imza.html` ile basılır
  (`only` ile; değişkenler parçanın başında). Takvim ve mazeret takvimi imza
  şeridini paylaşır.
- `sinav/reports/` — 11 şablon (base, _head, r1-r4, r6-r9, room_layout).
  R6 gözetmen şablonu F7'de, `room_layout.html` oturumsuz boş plan içindir.
- `sinav/booklet_overlay.html` — kitapçık bandı (F5'te `booklet.py`
  `render_pdf` çağrısına bağlandı; bant üst 4mm + 32mm ≤ 40mm invariantı ve
  296mm sayfa yüksekliği `test_booklets.py` ile korunur).
- `sinav/calendar_pdf.html` — F6 takvim PDF'i; `documents/base.html`'i
  extends eder. 01.10.2026'dan beri tek A4 düzenidir: ölçüler (yön, punto,
  boşluk) şablonda değil `services_calendar.CalendarPdfFit`te durur; servis
  varyantları dizip tek sayfaya sığan ilkini basar.

PyInstaller spec bu ağacı pakete kaynak olarak kopyalar.
