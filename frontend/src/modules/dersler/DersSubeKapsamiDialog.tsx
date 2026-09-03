// Seçmeli dersin şube kapsamı — KAYNAK ekran (03.09.2026).
//
// "Bu dersi hangi şubeler alıyor" bilgisi burada BİR KEZ girilir; sınav takvimi
// havuzu ondan beslenir (kapsamsız seçmeli havuza kendiliğinden girmez) ve
// seçmeli seçim diyaloğu şube kutularını buradan dolu getirir. Takvim girdisi
// yine kendi kopyasını tutar — onaylanmış takvimin kapsamı katalog sonradan
// değişince geriye dönük kaymaz (CLAUDE.md §3).
//
// Kaydetme TAM DEĞİŞTİRMEDİR: diyalog dersin bütün seviyelerini birlikte
// gösterir, boş bırakılan seviyenin kaydı silinir.

import { useEffect, useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { ApiError } from "../../lib/api";
import Button from "../../ui/Button";
import Dialog from "../../ui/Dialog";
import { SkeletonList } from "../../ui/Skeleton";
import { useSnackbar } from "../../ui/SnackbarProvider";
import { okulApi } from "../okul/api";
import SubeSecici from "../okul/SubeKapsamSecici";
import type { Course } from "./api";
import { derslerApi } from "./api";

export default function DersSubeKapsamiDialog({
  course,
  onClose,
  onSaved,
}: {
  course: Course;
  onClose: () => void;
  onSaved: () => void;
}) {
  const snackbar = useSnackbar();
  const queryClient = useQueryClient();
  const [secim, setSecim] = useState<Record<number, number[]>>({});

  const kapsamQuery = useQuery({
    queryKey: ["course-sections", course.id],
    queryFn: () => derslerApi.courseSections(course.id),
  });
  // Şube kataloğu + kümeler okul modülünden — takvim diyaloglarıyla AYNI
  // queryKey'ler, aynı oturumda ikinci kez indirilmez.
  const sections = useQuery({
    queryKey: ["class-sections"],
    queryFn: () => okulApi.listClassSections(),
  });
  const sectionGroups = useQuery({
    queryKey: ["class-section-groups"],
    queryFn: () => okulApi.listClassSectionGroups(),
  });

  // Kayıtlı kapsam gelince forma yazılır (kullanıcı dokunduysa üzerine yazmaz).
  const yuklendi = kapsamQuery.data;
  useEffect(() => {
    if (!yuklendi) return;
    setSecim((prev) =>
      Object.keys(prev).length > 0
        ? prev
        : Object.fromEntries(yuklendi.offerings.map((o) => [o.level, o.section_ids])),
    );
  }, [yuklendi]);

  const seviyeler = useMemo(
    () => [...(course.levels ?? [])].sort((a, b) => a - b),
    [course.levels],
  );

  const kumeSubeleri = (groupId: number, level: number): number[] =>
    (sections.data ?? [])
      .filter((s) => s.group === groupId && s.class_level === level)
      .map((s) => s.id);

  const kaydet = useMutation({
    mutationFn: () =>
      derslerApi.setCourseSections(
        course.id,
        seviyeler
          .map((level) => ({ level, section_ids: secim[level] ?? [] }))
          .filter((o) => o.section_ids.length > 0),
      ),
    onSuccess: () => {
      snackbar.success(`'${course.name}' şube kapsamı kaydedildi.`);
      // Takvim havuzu ve seçmeli seçim diyaloğu aynı kaynaktan besleniyor.
      void queryClient.invalidateQueries({ queryKey: ["course-section-offerings"] });
      onSaved();
    },
    onError: (e) =>
      snackbar.error(e instanceof ApiError ? e.message : "Şube kapsamı kaydedilemedi."),
  });

  const yukleniyor = kapsamQuery.isPending || sections.isPending;

  return (
    <Dialog
      open
      onClose={onClose}
      title={`${course.name} — şubeler`}
      actions={
        <>
          <Button variant="text" onClick={onClose} disabled={kaydet.isPending}>
            Vazgeç
          </Button>
          <Button icon="check" onClick={() => kaydet.mutate()} disabled={kaydet.isPending}>
            {kaydet.isPending ? "Kaydediliyor…" : "Kaydet"}
          </Button>
        </>
      }
    >
      <p className="mb-3 text-body-small text-on-surface-variant">
        Bu seçmeli dersi hangi şubelerin aldığını işaretleyin. Sınav takvimi havuzu bu bilgiyi
        kullanır: kapsamı girilmiş seçmeliler havuza kendiliğinden girer, takvimde tekrar şube
        seçmezsiniz. Bir seviyeyi boş bırakırsanız o seviyede kapsam tanımsız kalır.
      </p>
      {yukleniyor ? (
        <SkeletonList rows={3} />
      ) : seviyeler.length === 0 ? (
        <p className="text-body-medium text-on-surface-variant">
          Bu dersin seviyesi tanımlı değil — önce “Düzenle” ile okutulduğu sınıf düzeylerini girin.
        </p>
      ) : (
        <div className="flex flex-col gap-4">
          {seviyeler.map((level) => {
            const seviyeSubeleri = (sections.data ?? []).filter((s) => s.class_level === level);
            const secili = secim[level] ?? [];
            return (
              <section key={level}>
                <p className="mb-1 text-label-large text-on-surface">
                  {level === 0 ? "Hazırlık" : `${level}. Sınıf`}
                  <span className="ml-2 text-body-small text-on-surface-variant">
                    {secili.length > 0 ? `${secili.length} şube` : "kapsam girilmedi"}
                  </span>
                </p>
                <SubeSecici
                  adPreki={`${course.name} ${level === 0 ? "Hazırlık" : `${level}. sınıf`}`}
                  sectionIds={secili}
                  sections={seviyeSubeleri.map((s) => ({ id: s.id, class_label: s.class_label }))}
                  groups={(sectionGroups.data ?? []).map((g) => ({ id: g.id, name: g.name }))}
                  onToggleSection={(id) =>
                    setSecim((prev) => {
                      const mevcut = prev[level] ?? [];
                      return {
                        ...prev,
                        [level]: mevcut.includes(id)
                          ? mevcut.filter((x) => x !== id)
                          : [...mevcut, id],
                      };
                    })
                  }
                  onApplyGroup={(groupId) =>
                    setSecim((prev) => ({
                      ...prev,
                      [level]: [
                        ...new Set([...(prev[level] ?? []), ...kumeSubeleri(groupId, level)]),
                      ],
                    }))
                  }
                />
              </section>
            );
          })}
        </div>
      )}
    </Dialog>
  );
}
