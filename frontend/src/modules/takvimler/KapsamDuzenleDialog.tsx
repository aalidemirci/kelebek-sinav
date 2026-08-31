// Havuzdaki bir takvim girdisinin katılımcı kapsamını SONRADAN düzeltir.
// Neden (31.08.2026 denetimi): kapsam yalnız "Seçmeli ders seç" dialog'unda
// seçiliyordu; ders bir kez havuza girince orada işaretli+kilitli geliyor,
// havuz tablosunda ise kapsam salt okunur duruyordu. Yanlış şube seçen idareci
// girdiyi silip yeniden eklemek (yerleşmişse önce yerleşimi kaldırmak) zorunda
// kalıyordu — oysa backend PATCH kapsam alanlarını zaten kabul ediyor.
// Emsal: aynı tablodaki satır içi "Hazırlayan" seçimi.
//
// Yalnız TASLAK takvimde açılır (`editable`); backend de `_ensure_draft` ile
// aynı kuralı uygular. Küme çipi şubeleri seçime EKLER (SubeKapsamSecici).

import { useMemo, useState } from "react";
import { useMutation, useQuery } from "@tanstack/react-query";

import { ApiError } from "../../lib/api";
import { gradeLevelLabel } from "../../lib/gradeLevels";
import Button from "../../ui/Button";
import Dialog from "../../ui/Dialog";
import Select from "../../ui/Select";
import { useSnackbar } from "../../ui/SnackbarProvider";
import { okulApi } from "../okul/api";
import type { ParticipantTypeCode } from "../oturumlar/api";
import type { ExamCalendarEntryRow } from "./api";
import { examCalendarApi } from "./api";
import SubeSecici, { KAPSAM_SECENEKLERI } from "./SubeKapsamSecici";

export default function KapsamDuzenleDialog({
  entry,
  onClose,
  onSaved,
}: {
  entry: ExamCalendarEntryRow;
  onClose: () => void;
  onSaved: () => void;
}) {
  const snackbar = useSnackbar();
  const [ptype, setPtype] = useState<ParticipantTypeCode>(entry.participant_type);
  const [sectionIds, setSectionIds] = useState<number[]>([...entry.section_ids]);

  // Sihirbaz + seçmeli dialog'uyla AYNI queryKey — aynı oturumda tekrar inmez.
  const sectionGroups = useQuery({
    queryKey: ["class-section-groups"],
    queryFn: () => okulApi.listClassSectionGroups(),
  });
  const sections = useQuery({
    queryKey: ["class-sections"],
    queryFn: () => okulApi.listClassSections(),
  });

  // Girdi TEK seviyeye bağlıdır; başka seviyenin şubesi backend'de reddedilir.
  const seviyeSubeleri = useMemo(
    () => (sections.data ?? []).filter((s) => s.class_level === entry.level),
    [sections.data, entry.level],
  );

  const applyGroup = (groupId: number) => {
    const ids = (sections.data ?? [])
      .filter((s) => s.group === groupId && s.class_level === entry.level)
      .map((s) => s.id);
    setSectionIds((prev) => [...new Set([...prev, ...ids])]);
  };

  const saveMutation = useMutation({
    mutationFn: () =>
      examCalendarApi.patchEntry(entry.id, {
        participant_type: ptype,
        // LEVEL kapsamda şube listesi TAŞINMAZ — backend de boş liste yazar.
        section_ids: ptype === "SECTIONS" ? sectionIds : [],
      }),
    onSuccess: () => {
      snackbar.success("Katılımcı kapsamı güncellendi.");
      onSaved();
    },
    onError: (e) => snackbar.error(e instanceof ApiError ? e.message : "Kapsam güncellenemedi."),
  });

  const eksikSube = ptype === "SECTIONS" && sectionIds.length === 0;

  return (
    <Dialog
      open
      onClose={onClose}
      title="Katılımcı kapsamını düzenle"
      actions={
        <>
          <Button variant="text" onClick={onClose} disabled={saveMutation.isPending}>
            Vazgeç
          </Button>
          <Button
            icon="check"
            onClick={() => saveMutation.mutate()}
            disabled={eksikSube || saveMutation.isPending}
          >
            {saveMutation.isPending ? "Kaydediliyor…" : "Kaydet"}
          </Button>
        </>
      }
    >
      <div className="flex flex-col gap-3">
        <p className="text-body-medium text-on-surface-variant">
          {entry.course_name} — {gradeLevelLabel(entry.level)}: sınav ya seviyenin tamamına ya da
          seçilen şubelere yapılır.
        </p>
        <div className="w-44">
          <Select
            label="Kapsam"
            aria-label={`${entry.course_name} katılımcı kapsamı`}
            options={KAPSAM_SECENEKLERI}
            value={ptype}
            onChange={(e) => {
              const yeni = e.target.value as ParticipantTypeCode;
              setPtype(yeni);
              // LEVEL'e dönüşte şube seçimi bırakılmaz (seçmeli dialog deseni).
              if (yeni === "LEVEL") setSectionIds([]);
            }}
          />
        </div>
        {ptype === "SECTIONS" ? (
          <SubeSecici
            adPreki={entry.course_name}
            sectionIds={sectionIds}
            sections={seviyeSubeleri}
            groups={(sectionGroups.data ?? []).map((g) => ({ id: g.id, name: g.name }))}
            onToggleSection={(id) =>
              setSectionIds((prev) =>
                prev.includes(id) ? prev.filter((v) => v !== id) : [...prev, id],
              )
            }
            onApplyGroup={applyGroup}
          />
        ) : null}
        {eksikSube ? (
          <p role="alert" className="text-body-medium text-error">
            En az bir şube seçin ya da kapsamı “Seviye geneli” yapın.
          </p>
        ) : null}
      </div>
    </Dialog>
  );
}
