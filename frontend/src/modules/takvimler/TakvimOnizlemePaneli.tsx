// Sınav Takvimi — Önizleme paneli (F6) — OYS'den UYARLA. Resmî PDF'in
// AÇIKLAMA bloğunu (description_text) ve DİPNOT bloğunu (footnote_text)
// düzenleme (yalnız TASLAK) + "Varsayılan metne dön" + imza bloğuna girecek
// zümrelerin seçimi (B7 revizyonu — seçim yoksa takvimdeki derslerden boş
// imza çizgileri üretilir) + PDF indir + onay bilgisi (B12: onaylayan
// ad-snapshot'ı ve onay zamanı). Yaşam döngüsü butonları üst başlıktadır —
// burada yinelenmez. Tarih-saat yalnız lib/format ile basılır (yerel
// `toLocaleString` kopyası kaldırıldı — docs/sozluk.md §3). M3 token'ları.

import { useEffect, useId, useState } from "react";
import { useMutation, useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";

import { ApiError } from "../../lib/api";
import { saveBlob } from "../../lib/download";
import { formatDateTime } from "../../lib/format";
import Button from "../../ui/Button";
import Icon from "../../ui/Icon";
import { useSnackbar } from "../../ui/SnackbarProvider";
import { okulApi } from "../okul/api";
import type { ExamCalendar } from "./api";
import { calendarPdfFileName, examCalendarApi } from "./api";
import { CalendarStatusBadge } from "./TakvimlerPage";

export default function TakvimOnizlemePaneli({
  calendar,
  editable,
  onSaved,
}: {
  calendar: ExamCalendar;
  editable: boolean;
  onSaved: () => void;
}) {
  const snackbar = useSnackbar();
  const fieldId = useId();
  const footnoteId = useId();
  const [text, setText] = useState(calendar.description_text);
  const [footnote, setFootnote] = useState(calendar.footnote_text);
  const [loadingDefault, setLoadingDefault] = useState(false);
  const [loadingFootnoteDefault, setLoadingFootnoteDefault] = useState(false);

  // Dış kaynaklı değişim (kaydet sonrası invalidate) yeni metni yansıtır.
  useEffect(() => {
    setText(calendar.description_text);
  }, [calendar.description_text]);

  useEffect(() => {
    setFootnote(calendar.footnote_text);
  }, [calendar.footnote_text]);

  const dirty = text !== calendar.description_text;
  const footnoteDirty = footnote !== calendar.footnote_text;

  const departmentsQuery = useQuery({
    queryKey: ["subject-departments"],
    queryFn: () => okulApi.listSubjectDepartments(),
  });

  const saveMutation = useMutation({
    mutationFn: () => examCalendarApi.update(calendar.id, { description_text: text }),
    onSuccess: () => {
      snackbar.success("Açıklama kaydedildi.");
      onSaved();
    },
    onError: (e) => snackbar.error(e instanceof ApiError ? e.message : "Açıklama kaydedilemedi."),
  });

  const footnoteMutation = useMutation({
    mutationFn: () => examCalendarApi.update(calendar.id, { footnote_text: footnote }),
    onSuccess: () => {
      snackbar.success("Dipnot kaydedildi.");
      onSaved();
    },
    onError: (e) => snackbar.error(e instanceof ApiError ? e.message : "Dipnot kaydedilemedi."),
  });

  // Zümre seçimi anında kaydedilir (metin alanlarının aksine "Kaydet" yok —
  // kutucuk işaretlemek zaten kesin bir eylem).
  const departmentMutation = useMutation({
    mutationFn: (ids: number[]) =>
      examCalendarApi.update(calendar.id, { signatory_departments: ids }),
    onSuccess: () => onSaved(),
    onError: (e) =>
      snackbar.error(e instanceof ApiError ? e.message : "İmza zümreleri kaydedilemedi."),
  });

  // Saatin BASILMASI takvim başına ayardır: ikili eğitimde aynı ders saati iki
  // farklı zamana denk geldiği için bazı okullar evrakta yalnız "3. Ders"
  // görmek ister. Kutucuk anında kaydedilir (zümre seçimiyle aynı desen).
  const timeMutation = useMutation({
    mutationFn: (deger: boolean) =>
      examCalendarApi.update(calendar.id, { print_period_times: deger }),
    onSuccess: () => onSaved(),
    onError: (e) => snackbar.error(e instanceof ApiError ? e.message : "Ayar kaydedilemedi."),
  });

  const revertToDefault = async () => {
    setLoadingDefault(true);
    try {
      const { text: def } = await examCalendarApi.defaultDescription();
      setText(def);
      snackbar.show("Varsayılan metin yüklendi — kaydetmeyi unutmayın.");
    } catch (e) {
      snackbar.error(e instanceof ApiError ? e.message : "Varsayılan metin alınamadı.");
    } finally {
      setLoadingDefault(false);
    }
  };

  const revertFootnoteToDefault = async () => {
    setLoadingFootnoteDefault(true);
    try {
      const { text: def } = await examCalendarApi.defaultFootnote();
      setFootnote(def);
      snackbar.show("Varsayılan dipnot yüklendi — kaydetmeyi unutmayın.");
    } catch (e) {
      snackbar.error(e instanceof ApiError ? e.message : "Varsayılan dipnot alınamadı.");
    } finally {
      setLoadingFootnoteDefault(false);
    }
  };

  const toggleDepartment = (id: number, checked: boolean) => {
    const next = checked
      ? [...calendar.signatory_departments, id]
      : calendar.signatory_departments.filter((d) => d !== id);
    departmentMutation.mutate(next);
  };

  const downloadPdf = async () => {
    try {
      const blob = await examCalendarApi.pdfBlob(calendar.id);
      saveBlob(blob, calendarPdfFileName(calendar));
    } catch (e) {
      snackbar.error(e instanceof ApiError ? e.message : "PDF indirilemedi.");
    }
  };

  const departments = departmentsQuery.data ?? [];
  const onayli = calendar.status === "APPROVED";

  return (
    <div className="grid gap-6 lg:grid-cols-3">
      <section className="space-y-6 lg:col-span-2">
        <div>
          <div className="mb-2 flex flex-wrap items-center gap-2">
            <label htmlFor={fieldId} className="text-title-small text-on-surface">
              Takvim açıklaması
            </label>
            {editable ? (
              <Button
                variant="text"
                icon="restart_alt"
                disabled={loadingDefault}
                onClick={() => void revertToDefault()}
              >
                Varsayılan metne dön
              </Button>
            ) : null}
          </div>
          <p className="mb-2 text-body-small text-on-surface-variant">
            Bu metin resmî sınav takvimi PDF'inin alt bölümünde madde madde yer alır (konu soru
            dağılım tablosu, günde en çok iki sınav, mazeret ve puan giriş süreleri vb.).
          </p>
          <textarea
            id={fieldId}
            rows={16}
            value={text}
            readOnly={!editable}
            onChange={(e) => setText(e.target.value)}
            className={`w-full rounded-shape-xs border border-outline bg-surface px-3 py-2 text-body-medium text-on-surface focus:border-primary focus:outline-none focus-visible:ring-2 focus-visible:ring-primary ${
              editable ? "" : "opacity-80"
            }`}
          />
          {editable ? (
            <div className="mt-2 flex items-center gap-2">
              <Button
                icon="save"
                disabled={!dirty || saveMutation.isPending}
                onClick={() => saveMutation.mutate()}
              >
                Kaydet
              </Button>
              {dirty ? (
                <span className="text-body-small text-on-surface-variant">
                  Kaydedilmemiş değişiklik var.
                </span>
              ) : null}
            </div>
          ) : (
            <p className="mt-2 inline-flex items-center gap-1 text-body-small text-on-surface-variant">
              <Icon name="lock" size="sm" /> Açıklama yalnız taslak durumda düzenlenir.
            </p>
          )}
        </div>

        <div>
          <div className="mb-2 flex flex-wrap items-center gap-2">
            <label htmlFor={footnoteId} className="text-title-small text-on-surface">
              Takvim dipnotu
            </label>
            {editable ? (
              <Button
                variant="text"
                icon="restart_alt"
                disabled={loadingFootnoteDefault}
                onClick={() => void revertFootnoteToDefault()}
              >
                Varsayılan dipnota dön
              </Button>
            ) : null}
          </div>
          <p className="mb-2 text-body-small text-on-surface-variant">
            Açıklamaların altına “DİPNOT” başlığıyla basılır. Varsayılan metin, okulda yapılan
            sınavların mazeret sınavlarının takvimi izleyen hafta içinde; Bakanlık ya da İl/İlçe
            Millî Eğitim Müdürlüğü sınavlarının ise ilgili kılavuzda ilan edilen tarih ve saatlerde
            yapılacağını söyler. Okulunuzun uygulamasına göre değiştirebilirsiniz.
          </p>
          <textarea
            id={footnoteId}
            rows={5}
            value={footnote}
            readOnly={!editable}
            onChange={(e) => setFootnote(e.target.value)}
            className={`w-full rounded-shape-xs border border-outline bg-surface px-3 py-2 text-body-medium text-on-surface focus:border-primary focus:outline-none focus-visible:ring-2 focus-visible:ring-primary ${
              editable ? "" : "opacity-80"
            }`}
          />
          {editable ? (
            <div className="mt-2 flex items-center gap-2">
              <Button
                icon="save"
                disabled={!footnoteDirty || footnoteMutation.isPending}
                onClick={() => footnoteMutation.mutate()}
              >
                Dipnotu kaydet
              </Button>
              {footnoteDirty ? (
                <span className="text-body-small text-on-surface-variant">
                  Kaydedilmemiş değişiklik var.
                </span>
              ) : null}
            </div>
          ) : null}
        </div>

        <div>
          <h3 className="text-title-small text-on-surface">İmza bloğundaki zümreler</h3>
          <p className="mb-2 mt-1 text-body-small text-on-surface-variant">
            PDF'in imza bölümünde hangi zümrelerin yer alacağını seçin. Zümreler ve başkanları{" "}
            <Link
              to="/ayarlar?tab=zumreler"
              className="text-primary underline-offset-4 hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary"
            >
              Ayarlar → Zümreler
            </Link>{" "}
            ekranında tanımlanır. Hiç zümre seçilmezse takvimdeki her ders için boş bir imza çizgisi
            basılır.
          </p>
          {departments.length === 0 ? (
            <p className="rounded-shape-sm bg-surface-container px-3 py-2 text-body-small text-on-surface-variant">
              Henüz zümre tanımlanmamış.
            </p>
          ) : (
            <div className="flex flex-wrap gap-x-6 gap-y-1">
              {departments.map((d) => (
                <label
                  key={d.id}
                  className="flex min-h-9 items-center gap-2 text-body-medium text-on-surface"
                >
                  <input
                    type="checkbox"
                    className="h-5 w-5 accent-primary"
                    checked={calendar.signatory_departments.includes(d.id)}
                    disabled={!editable || departmentMutation.isPending}
                    onChange={(e) => toggleDepartment(d.id, e.target.checked)}
                  />
                  <span>
                    {d.name}
                    {d.head_name ? (
                      <span className="text-on-surface-variant"> — {d.head_name}</span>
                    ) : null}
                  </span>
                </label>
              ))}
            </div>
          )}
          {!editable ? (
            <p className="mt-2 inline-flex items-center gap-1 text-body-small text-on-surface-variant">
              <Icon name="lock" size="sm" /> İmza zümreleri yalnız taslak durumda değiştirilir.
            </p>
          ) : null}
        </div>

        <div>
          <p className="mb-2 text-title-small text-on-surface">Evrakta ders saati</p>
          <label className="flex min-h-9 items-center gap-2 text-body-medium text-on-surface">
            <input
              type="checkbox"
              className="h-5 w-5 accent-primary"
              checked={calendar.print_period_times}
              disabled={!editable || timeMutation.isPending}
              onChange={(e) => timeMutation.mutate(e.target.checked)}
            />
            <span>Ders saatinin yanına zamanı da yazdır (ör. “3. Ders · 10:10”)</span>
          </label>
          <p className="mt-1 text-body-small text-on-surface-variant">
            Kapalıyken evrakta yalnız ders saati adı basılır. Zamanlar Ayarlar → Ders Saatleri
            ekranından gelir; ikili eğitimde sınava giren şubenin oturumuna göre yazılır.
          </p>
        </div>
      </section>

      <aside className="flex flex-col gap-3 self-start rounded-shape-lg bg-surface-container-low p-4 shadow-elevation-1">
        <h3 className="text-title-small text-on-surface">Onay bilgisi</h3>
        <div className="flex items-center gap-2">
          <span className="text-body-small text-on-surface-variant">Durum:</span>
          <CalendarStatusBadge status={calendar.status} />
        </div>
        {/* Onay damgası YALNIZ onaylı takvimde gösterilir: taslağa alınan takvimde
            backend eski damgayı tarihçe olarak saklar, ama ekranda "Onaylandı:
            <tarih>" yazması taslağı onaylı sandırırdı. Tek "Onayla" akışında
            sunum anı onayla aynıdır; ayrı satırı yalnız eski veride (ONAYA
            SUNULDU'da kalmış takvim) anlam taşır. */}
        <dl className="space-y-2 text-body-small">
          {calendar.status === "SUBMITTED" ? (
            <div className="flex justify-between gap-2">
              <dt className="text-on-surface-variant">Onaya sunuldu</dt>
              <dd className="text-on-surface">{formatDateTime(calendar.submitted_at)}</dd>
            </div>
          ) : null}
          <div className="flex justify-between gap-2">
            <dt className="text-on-surface-variant">Onaylayan</dt>
            <dd className="text-on-surface">{onayli ? calendar.approved_by_name || "—" : "—"}</dd>
          </div>
          <div className="flex justify-between gap-2">
            <dt className="text-on-surface-variant">Onay tarihi</dt>
            <dd className="text-on-surface">
              {onayli ? formatDateTime(calendar.approved_at) : "—"}
            </dd>
          </div>
        </dl>
        <Button variant="outlined" icon="picture_as_pdf" onClick={() => void downloadPdf()}>
          PDF indir
        </Button>
        <p className="text-body-small text-on-surface-variant">
          Onaylanmamış takvimin PDF'inde “TASLAK” filigranı bulunur; filigransız resmî çıktı yalnız
          onaydan sonra üretilir.
        </p>
      </aside>
    </div>
  );
}
