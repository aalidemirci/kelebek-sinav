// Sınav Takvimi — Önizleme paneli (F6) — OYS'den UYARLA. Resmi PDF'in
// AÇIKLAMA bloğunu (description_text) düzenleme (yalnız TASLAK) + "Varsayılan
// metne dön" + PDF indir + onay akışı özeti (sunum/onay damgaları — B12:
// onaylayan ad-snapshot'ı da gösterilir). Yaşam döngüsü butonları üst
// başlıktadır — burada yinelenmez. M3 token'ları.

import { useEffect, useId, useState } from "react";
import { useMutation } from "@tanstack/react-query";

import { ApiError } from "../../lib/api";
import { saveBlob } from "../../lib/download";
import Button from "../../ui/Button";
import Icon from "../../ui/Icon";
import { useSnackbar } from "../../ui/SnackbarProvider";
import type { ExamCalendar } from "./api";
import { examCalendarApi } from "./api";
import { CalendarStatusBadge } from "./TakvimlerPage";

function formatDateTime(iso: string | null): string {
  if (!iso) return "—";
  const d = new Date(iso);
  return Number.isNaN(d.getTime()) ? iso : d.toLocaleString("tr-TR");
}

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
  const [text, setText] = useState(calendar.description_text);
  const [loadingDefault, setLoadingDefault] = useState(false);

  // Dış kaynaklı değişim (kaydet sonrası invalidate) yeni metni yansıtır.
  useEffect(() => {
    setText(calendar.description_text);
  }, [calendar.description_text]);

  const dirty = text !== calendar.description_text;

  const saveMutation = useMutation({
    mutationFn: () => examCalendarApi.update(calendar.id, { description_text: text }),
    onSuccess: () => {
      snackbar.success("Açıklama kaydedildi.");
      onSaved();
    },
    onError: (e) => snackbar.error(e instanceof ApiError ? e.message : "Açıklama kaydedilemedi."),
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

  const downloadPdf = async () => {
    try {
      const blob = await examCalendarApi.pdfBlob(calendar.id);
      saveBlob(blob, `sinav_takvimi_${calendar.id}.pdf`);
    } catch (e) {
      snackbar.error(e instanceof ApiError ? e.message : "PDF indirilemedi.");
    }
  };

  return (
    <div className="grid gap-6 lg:grid-cols-3">
      <section className="lg:col-span-2">
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
          Bu metin resmi sınav takvimi PDF'inin alt bölümünde madde madde yer alır (KSD, günde en
          çok iki sınav, mazeret ve puan giriş süreleri vb.).
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
      </section>

      <aside className="flex flex-col gap-3 rounded-shape-lg bg-surface-container-low p-4 shadow-elevation-1">
        <h3 className="text-title-small text-on-surface">Onay akışı</h3>
        <div className="flex items-center gap-2">
          <span className="text-body-small text-on-surface-variant">Durum:</span>
          <CalendarStatusBadge status={calendar.status} />
        </div>
        <dl className="space-y-2 text-body-small">
          <div className="flex justify-between gap-2">
            <dt className="text-on-surface-variant">Onaya sunuldu</dt>
            <dd className="text-on-surface">{formatDateTime(calendar.submitted_at)}</dd>
          </div>
          <div className="flex justify-between gap-2">
            <dt className="text-on-surface-variant">Onaylayan</dt>
            <dd className="text-on-surface">{calendar.approved_by_name || "—"}</dd>
          </div>
          <div className="flex justify-between gap-2">
            <dt className="text-on-surface-variant">Onaylandı</dt>
            <dd className="text-on-surface">{formatDateTime(calendar.approved_at)}</dd>
          </div>
        </dl>
        <Button variant="outlined" icon="picture_as_pdf" onClick={() => void downloadPdf()}>
          PDF indir
        </Button>
        <p className="text-body-small text-on-surface-variant">
          Taslak ve onaya sunulmuş takvimlerin PDF'inde "TASLAK" filigranı bulunur; filigransız
          resmi çıktı yalnız onaydan sonra üretilir.
        </p>
      </aside>
    </div>
  );
}
