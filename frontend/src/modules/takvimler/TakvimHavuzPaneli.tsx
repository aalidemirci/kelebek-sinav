// Sınav Takvimi — Havuz paneli (F6) — OYS TakvimHavuzPaneli'nden UYARLA.
// Havuz iki yoldan dolar: "Dersleri ekle" (fill-pool ucu — ortak + YAZILI
// dersler ve ŞUBESİ TANIMLI yazılı seçmeliler; uygulama sınavı ve sınavsız
// dersler dışarıda) ve "Seçmeli ders seç" dialog'u (seviye seviye, katılımcı
// kapsamıyla — kutular ders havuzundaki tanımdan ön dolar). Kaynak
// hâlâ aktif ders kataloğu × öğrencisi olan seviyeler (KS sapması B6/B8:
// program verisi yok). Elle ekleme formu kenar durumlar için kalır: kelebek
// olmayan sınav, uygulama sınavı, üst makam sınavı. Katılımcı sayısı/kapsam
// dipnotu önizleme; "Kapsam" hücresi taslakta DÜZENLEME yoludur
// (KapsamDuzenleDialog — seçmeli dialog havuzdaki dersi kilitli gösterir). Yalnız taslakta düzenlenebilir; round 3 havuzunda otomatik
// doldurma yoktur ama seçmeli seçimi çalışır (backend tekil ekleme yolu).

import { useCallback, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { ApiError } from "../../lib/api";
import { gradeLevelLabel } from "../../lib/gradeLevels";
import Autocomplete from "../../ui/Autocomplete";
import Button from "../../ui/Button";
import DataTable from "../../ui/DataTable";
import EmptyState from "../../ui/EmptyState";
import Icon from "../../ui/Icon";
import Select from "../../ui/Select";
import { SkeletonList } from "../../ui/Skeleton";
import { useConfirm } from "../../ui/ConfirmProvider";
import { useSnackbar } from "../../ui/SnackbarProvider";
import type { Course } from "../dersler/api";
import { derslerApi } from "../dersler/api";
import { PARTICIPANT_TYPE_TR } from "../oturumlar/api";
import type { ExamAuthorityCode, ExamCalendarEntryRow, ExamKindCode } from "./api";
import { EXAM_AUTHORITY_TR, examCalendarApi } from "./api";
import KapsamDuzenleDialog from "./KapsamDuzenleDialog";
import SecmeliDersSecimDialog from "./SecmeliDersSecimDialog";

export default function TakvimHavuzPaneli({
  calendarId,
  round,
  editable,
  onChanged,
}: {
  calendarId: number;
  round: number;
  editable: boolean;
  onChanged: () => void;
}) {
  const snackbar = useSnackbar();
  const confirm = useConfirm();
  const queryClient = useQueryClient();
  const [course, setCourse] = useState<Course | null>(null);
  const [level, setLevel] = useState("9");
  const [kind, setKind] = useState<ExamKindCode>("WRITTEN");
  const [butterfly, setButterfly] = useState(true);
  const [authority, setAuthority] = useState<ExamAuthorityCode>("SCHOOL");
  const [electiveOpen, setElectiveOpen] = useState(false);
  // Kapsamı düzenlenen havuz girdisi (null = dialog kapalı).
  const [kapsamEntry, setKapsamEntry] = useState<ExamCalendarEntryRow | null>(null);
  // Dialog odak efekti onClose kimliğine bağlı — sabit referans şart.
  const closeElective = useCallback(() => setElectiveOpen(false), []);

  const entriesQuery = useQuery({
    queryKey: ["exam-calendar-entries", calendarId],
    queryFn: () => examCalendarApi.entries(calendarId),
  });
  const previewQuery = useQuery({
    queryKey: ["exam-calendar-preview", calendarId],
    queryFn: () => examCalendarApi.participantPreview(calendarId),
  });
  // Seviye seçenekleri ızgaranın dinamik seviye listesinden (Hazırlık opt-in
  // okulda 0 dahil). Aynı queryKey Yerleştirme paneliyle paylaşılır.
  const gridQuery = useQuery({
    queryKey: ["exam-calendar-grid", calendarId],
    queryFn: () => examCalendarApi.grid(calendarId),
    enabled: editable,
  });

  const invalidate = () => {
    void queryClient.invalidateQueries({ queryKey: ["exam-calendar-entries", calendarId] });
    void queryClient.invalidateQueries({ queryKey: ["exam-calendar-preview", calendarId] });
    // Seçmeli listesindeki `in_pool` havuzla birlikte kayar — tazelenmezse
    // dialog yeniden açıldığında eklenen ders hâlâ "kilitsiz" görünürdü.
    void queryClient.invalidateQueries({
      queryKey: ["exam-calendar-elective-options", calendarId],
    });
    onChanged();
  };

  const addMutation = useMutation({
    mutationFn: () =>
      examCalendarApi.addEntry(calendarId, {
        course: (course as Course).id,
        level: Number(level),
        exam_kind: kind,
        is_butterfly: butterfly,
        authority,
      }),
    onSuccess: () => {
      snackbar.success("Ders havuza eklendi.");
      setCourse(null);
      invalidate();
    },
    onError: (e) => snackbar.error(e instanceof ApiError ? e.message : "Ders eklenemedi."),
  });

  const removeMutation = useMutation({
    mutationFn: (entryId: number) => examCalendarApi.removeEntry(entryId),
    onSuccess: invalidate,
    onError: (e) => snackbar.error(e instanceof ApiError ? e.message : "Kaldırılamadı."),
  });

  // Var olan girdinin makamı satır içinde değişir (Bakanlık/MEM duyurusu
  // takvim hazırlandıktan sonra gelebilir — girdiyi silip yeniden eklemek
  // yerleşimi de kaybettirirdi).
  const authorityMutation = useMutation({
    mutationFn: (p: { entryId: number; authority: ExamAuthorityCode }) =>
      examCalendarApi.patchEntry(p.entryId, { authority: p.authority }),
    onSuccess: invalidate,
    onError: (e) => snackbar.error(e instanceof ApiError ? e.message : "Makam değiştirilemedi."),
  });

  // Zorunlu (ortak + YAZILI) dersleri ekle — idempotent (var olan atlanır);
  // skipped sessiz düşmez, uyarıyla raporlanır.
  const fillMutation = useMutation({
    mutationFn: () => examCalendarApi.fillPool(calendarId),
    onSuccess: (result) => {
      const base = `${result.created.length} ders eklendi, ${result.existed.length} zaten vardı.`;
      if (result.skipped.length > 0) {
        // Tek birleşik mesaj (snackbar kuyruklu — iki mesaj sırayla beklerdi).
        snackbar.error(
          `${base} ${result.skipped.length} ders atlandı: ${result.skipped
            .slice(0, 3)
            .join("; ")}${result.skipped.length > 3 ? "…" : ""}`,
        );
      } else {
        snackbar.success(base);
      }
      invalidate();
    },
    onError: (e) => snackbar.error(e instanceof ApiError ? e.message : "Havuz doldurulamadı."),
  });

  const canFill = editable && round !== 3;
  const handleFill = () => {
    void confirm({
      title: "Dersleri havuza ekle",
      message:
        "Ders havuzundaki ZORUNLU (ortak) ve sınavı YAZILI dersler, öğrencisi olan " +
        "seviyeler bazında takvim havuzuna eklenecek; var olan girdiler atlanır. " +
        "Şubeleri Ders Havuzu ekranında girilmiş SEÇMELİ dersler de kapsamlarıyla " +
        "birlikte eklenir — şubesi girilmemiş seçmeli atlanır ve raporlanır, " +
        "“Seçmeli ders seç” ile elle işaretleyebilirsiniz. Uygulama sınavı yapılan " +
        "ve sınavı olmayan dersler eklenmez. Hazırlayan makam varsayılanı Okul — " +
        "Bakanlık/MEM sınavlarını taslakta işaretleyin.",
      confirmLabel: "Ekle",
    }).then((ok) => ok && fillMutation.mutate());
  };

  const searchCourses = (q: string): Promise<Course[]> => derslerApi.listCourses({ q });

  const entries = entriesQuery.data?.results ?? [];
  const preview = previewQuery.data ?? {};

  return (
    <div>
      {editable ? (
        <div className="mb-3 flex flex-wrap justify-end gap-2">
          {canFill ? (
            <Button
              variant="tonal"
              icon="auto_awesome"
              disabled={fillMutation.isPending}
              onClick={handleFill}
            >
              Dersleri ekle
            </Button>
          ) : null}
          {/* Seçmeli seçimi 3. turda da açık: tekil ekleme yolunu kullanır,
              fill-pool'un round 3 yasağı buraya işlemez. */}
          <Button variant="tonal" icon="checklist" onClick={() => setElectiveOpen(true)}>
            Seçmeli ders seç
          </Button>
        </div>
      ) : null}
      {editable ? (
        <div className="mb-4 flex flex-wrap items-end gap-3 rounded-shape-lg bg-surface-container p-4">
          <div className="min-w-56 grow">
            <Autocomplete<Course>
              label="Ders"
              placeholder="Ders ara…"
              selected={course}
              search={searchCourses}
              onSelect={(c) => {
                setCourse(c);
                // Ders havuzunda "Uygulama" işaretli dersin türü kendiliğinden
                // Uygulama'ya gelir; idareci her seferinde elle çevirmesin.
                setKind(c.exam_mode === "PRACTICE" ? "PRACTICE" : "WRITTEN");
              }}
              onClear={() => setCourse(null)}
              getLabel={(c) => c.name}
              getSublabel={(c) => `${c.level_labels.join(", ")} · ${c.exam_mode_label}`}
              getKey={(c) => c.id}
            />
          </div>
          <div className="w-36">
            <Select
              label="Seviye"
              options={
                gridQuery.data?.levels.map((l) => ({
                  value: String(l.value),
                  label: l.display_label,
                })) ?? [9, 10, 11, 12].map((l) => ({ value: String(l), label: gradeLevelLabel(l) }))
              }
              value={level}
              onChange={(e) => setLevel(e.target.value)}
            />
          </div>
          <div className="w-36">
            <Select
              label="Tür"
              options={[
                { value: "WRITTEN", label: "Yazılı" },
                { value: "PRACTICE", label: "Uygulama" },
              ]}
              value={kind}
              onChange={(e) => setKind(e.target.value as ExamKindCode)}
            />
          </div>
          <div className="w-44">
            <Select
              label="Hazırlayan"
              options={Object.entries(EXAM_AUTHORITY_TR).map(([value, label]) => ({
                value,
                label,
              }))}
              value={authority}
              onChange={(e) => setAuthority(e.target.value as ExamAuthorityCode)}
              helperText="Bakanlık/MEM sınavı takvimde ayrı görünür."
            />
          </div>
          <label className="flex min-h-9 items-center gap-2 text-body-medium text-on-surface">
            <input
              type="checkbox"
              className="h-5 w-5 accent-primary"
              checked={!butterfly}
              onChange={(e) => setButterfly(!e.target.checked)}
            />
            Kelebek değil
          </label>
          <Button
            icon="add"
            disabled={!course || addMutation.isPending}
            onClick={() => addMutation.mutate()}
          >
            Havuza ekle
          </Button>
        </div>
      ) : null}

      {entriesQuery.isPending ? (
        <SkeletonList rows={4} />
      ) : entriesQuery.isError ? (
        // Hata durumu "Havuz boş" gibi sunulmaz — mesaj gösterilir.
        <p role="alert" className="text-body-medium text-error">
          Havuz listesi yüklenemedi:{" "}
          {entriesQuery.error instanceof ApiError
            ? entriesQuery.error.message
            : "beklenmeyen hata."}
        </p>
      ) : entries.length === 0 ? (
        <EmptyState
          icon="playlist_add"
          title="Havuz boş"
          description={
            canFill
              ? "Zorunlu dersleri ve şubesi tanımlı seçmelileri tek tıkla ekleyin; kalan seçmelileri seviye seviye seçin, kenar durumlar için yukarıdaki form kalır."
              : editable
                ? "Seçmeli dersleri seçin ya da yukarıdan elle ekleyin."
                : "Bu takvime ders eklenmemiş."
          }
          action={
            canFill ? (
              <Button icon="auto_awesome" disabled={fillMutation.isPending} onClick={handleFill}>
                Dersleri ekle
              </Button>
            ) : editable ? (
              <Button icon="checklist" onClick={() => setElectiveOpen(true)}>
                Seçmeli ders seç
              </Button>
            ) : undefined
          }
        />
      ) : (
        <DataTable
          rows={entries}
          columns={[
            {
              header: "Ders",
              cell: (e: ExamCalendarEntryRow) => (
                <span>
                  {e.course_name}
                  {e.exam_kind === "PRACTICE" ? " [Uygulama]" : ""}
                  {!e.is_butterfly ? (
                    <span className="ml-2 rounded-full bg-surface-container-high px-2 py-0.5 text-label-small text-on-surface-variant">
                      Kelebek değil
                    </span>
                  ) : null}
                </span>
              ),
            },
            { header: "Seviye", cell: (e) => gradeLevelLabel(e.level) },
            {
              // Kapsam sayısı katılımcı SAYISINDAN ayrı sütun: "3 şube" ile
              // "78 öğrenci" aynı hücrede okunamıyordu. Taslakta hücre aynı
              // zamanda DÜZELTME yoludur (31.08.2026 denetimi): seçmeli dialog
              // havuzdaki dersi kilitli gösterdiğinden yanlış şube seçimi
              // eskiden ancak girdiyi silip yeniden ekleyerek düzeliyordu.
              header: "Kapsam",
              cell: (e: ExamCalendarEntryRow) => {
                const etiket =
                  e.participant_label ||
                  (e.participant_type === "SECTIONS"
                    ? `${e.section_ids.length} şube`
                    : PARTICIPANT_TYPE_TR.LEVEL);
                // Kapsamın KAYNAĞI ders havuzudur; buradaki değişiklik o
                // takvime mahsus bir istisnadır ve rozetle görünür kalır
                // (03.09.2026) — sessizce ayrışmasın.
                const rozet = e.scope_differs_from_catalog ? (
                  <span
                    className="ml-1 rounded-shape-sm bg-tertiary-container px-1.5 py-0.5 text-label-small text-on-tertiary-container"
                    title="Bu takvimde ders havuzundaki şube tanımından farklı bir kapsam seçilmiş."
                  >
                    özel
                  </span>
                ) : null;
                return editable ? (
                  <span className="inline-flex items-center">
                    <Button
                      variant="text"
                      icon="edit"
                      aria-label={`${e.course_name} katılımcı kapsamını düzenle`}
                      onClick={() => setKapsamEntry(e)}
                    >
                      {etiket}
                    </Button>
                    {rozet}
                  </span>
                ) : (
                  <span className="inline-flex items-center">
                    {etiket}
                    {rozet}
                  </span>
                );
              },
            },
            {
              header: "Hazırlayan",
              cell: (e: ExamCalendarEntryRow) =>
                editable ? (
                  <Select
                    label=""
                    aria-label={`${e.course_name} hazırlayan makam`}
                    options={Object.entries(EXAM_AUTHORITY_TR).map(([value, label]) => ({
                      value,
                      label,
                    }))}
                    value={e.authority}
                    disabled={authorityMutation.isPending}
                    onChange={(ev) =>
                      authorityMutation.mutate({
                        entryId: e.id,
                        authority: ev.target.value as ExamAuthorityCode,
                      })
                    }
                  />
                ) : (
                  <span
                    className={
                      e.authority === "SCHOOL"
                        ? "text-on-surface-variant"
                        : "rounded-full bg-tertiary-container px-2 py-0.5 text-label-small text-on-tertiary-container"
                    }
                  >
                    {EXAM_AUTHORITY_TR[e.authority]}
                  </span>
                ),
            },
            {
              header: "Katılımcı",
              cell: (e) => {
                const p = preview[String(e.id)];
                if (!p) return "—";
                const foot = p.whole ? "" : ` (${p.groups.join(", ")})`;
                return `${p.student_count}${foot}`;
              },
            },
            {
              header: "Durum",
              cell: (e) =>
                e.placed_date ? (
                  <span className="inline-flex items-center gap-1 text-primary">
                    <Icon name="event_available" size="sm" /> Yerleştirildi
                  </span>
                ) : (
                  <span className="text-on-surface-variant">Havuzda</span>
                ),
            },
            ...(editable
              ? [
                  {
                    header: "",
                    align: "right" as const,
                    cell: (e: ExamCalendarEntryRow) => (
                      <Button
                        variant="text"
                        icon="delete"
                        aria-label={`${e.course_name} girdisini kaldır`}
                        disabled={e.placed_date !== null || removeMutation.isPending}
                        onClick={() => removeMutation.mutate(e.id)}
                      >
                        Kaldır
                      </Button>
                    ),
                  },
                ]
              : []),
          ]}
        />
      )}

      {kapsamEntry !== null ? (
        <KapsamDuzenleDialog
          entry={kapsamEntry}
          onClose={() => setKapsamEntry(null)}
          onSaved={() => {
            setKapsamEntry(null);
            invalidate();
          }}
        />
      ) : null}

      {electiveOpen ? (
        <SecmeliDersSecimDialog
          calendarId={calendarId}
          onClose={closeElective}
          onSaved={() => {
            setElectiveOpen(false);
            invalidate();
          }}
        />
      ) : null}
    </div>
  );
}
