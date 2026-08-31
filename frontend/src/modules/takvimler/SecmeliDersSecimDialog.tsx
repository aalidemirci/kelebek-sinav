// Sınav Takvimi — Seçmeli ders seçimi (F6 sadeleştirmesi).
// Neden ayrı bir dialog: "Katalogdan Doldur" tüm kataloğu (ortak + seçmeli)
// bütün seviyelere basıyordu; Anadolu Lisesi kataloğunda ~175 girdi doğuyor,
// idareci gerçekte sınavı yapılacak ~30 satır kalana dek TEK TEK siliyordu.
// Yeni akış: zorunlu (ortak + YAZILI) dersler tek düğmeyle, seçmeliler burada
// seviye seviye işaretlenerek eklenir.
//
// Katılımcı kapsamı burada da seçilir (seviye geneli / şube şube). Şube kümesi
// çipi şubeleri seçime EKLER, AYRI DURUM TUTMAZ — "gruptan gelen" ile "elle
// seçilen" için ikinci kaynak-gerçek doğardı; emsal SinavSihirbazi.applyGroup.
// Küme kimliği hiçbir takvim kaydına yazılmaz (CLAUDE.md §3).

import { useEffect, useMemo, useState } from "react";
import { useMutation, useQuery } from "@tanstack/react-query";

import { ApiError } from "../../lib/api";
import Button from "../../ui/Button";
import Dialog from "../../ui/Dialog";
import Select from "../../ui/Select";
import { SkeletonList } from "../../ui/Skeleton";
import Tabs, { tabPanelProps } from "../../ui/Tabs";
import { useSnackbar } from "../../ui/SnackbarProvider";
import { okulApi } from "../okul/api";
import type { ParticipantTypeCode } from "../oturumlar/api";
import type { BulkEntryItem } from "./api";
import { examCalendarApi } from "./api";
import SubeSecici, { KAPSAM_SECENEKLERI } from "./SubeKapsamSecici";

/** Bir dersin seçimdeki kapsamı — anahtar `"<seviye>:<ders id>"`. */
interface Kapsam {
  ptype: ParticipantTypeCode;
  sectionIds: number[];
}

const secimAnahtari = (level: number, courseId: number) => `${level}:${courseId}`;

export default function SecmeliDersSecimDialog({
  calendarId,
  onClose,
  onSaved,
}: {
  calendarId: number;
  onClose: () => void;
  onSaved: () => void;
}) {
  const snackbar = useSnackbar();
  const [activeLevel, setActiveLevel] = useState("");
  const [secim, setSecim] = useState<Record<string, Kapsam>>({});
  // Toplu kapsam paneli AKTİF SEVİYEYE aittir: şubeler tek seviyeye bağlıdır,
  // seviyeler arası ortak bir şube listesi anlamsız olurdu.
  const [topluPtype, setTopluPtype] = useState<ParticipantTypeCode>("LEVEL");
  const [topluSections, setTopluSections] = useState<number[]>([]);

  const optionsQuery = useQuery({
    queryKey: ["exam-calendar-elective-options", calendarId],
    queryFn: () => examCalendarApi.electiveOptions(calendarId),
  });
  // Şube kataloğu + kümeler okul modülünden (F1) — sihirbazla aynı queryKey'ler,
  // aynı oturumda iki kez indirilmez.
  const sectionGroups = useQuery({
    queryKey: ["class-section-groups"],
    queryFn: () => okulApi.listClassSectionGroups(),
  });
  const sections = useQuery({
    queryKey: ["class-sections"],
    queryFn: () => okulApi.listClassSections(),
  });

  const levels = useMemo(() => optionsQuery.data ?? [], [optionsQuery.data]);

  // İlk seviye sekmesi veri gelince açılır (kullanıcı seçtiyse dokunulmaz).
  useEffect(() => {
    if (activeLevel === "" && levels.length > 0) setActiveLevel(String(levels[0].value));
  }, [activeLevel, levels]);

  const aktif = levels.find((l) => String(l.value) === activeLevel) ?? null;
  const aktifSeviye = aktif?.value ?? null;

  const seviyeSubeleri = useMemo(
    () =>
      (sections.data ?? []).filter((s) => aktifSeviye !== null && s.class_level === aktifSeviye),
    [sections.data, aktifSeviye],
  );

  const toggleCourse = (level: number, courseId: number) => {
    const key = secimAnahtari(level, courseId);
    setSecim((prev) => {
      if (!(key in prev)) return { ...prev, [key]: { ptype: "LEVEL", sectionIds: [] } };
      const next = { ...prev };
      delete next[key];
      return next;
    });
  };

  const setKapsam = (key: string, patch: Partial<Kapsam>) =>
    setSecim((prev) => (key in prev ? { ...prev, [key]: { ...prev[key], ...patch } } : prev));

  const toggleSection = (key: string, sectionId: number) =>
    setSecim((prev) => {
      const mevcut = prev[key];
      if (!mevcut) return prev;
      const ids = mevcut.sectionIds.includes(sectionId)
        ? mevcut.sectionIds.filter((v) => v !== sectionId)
        : [...mevcut.sectionIds, sectionId];
      return { ...prev, [key]: { ...mevcut, sectionIds: ids } };
    });

  /**
   * Küme çipi: kümedeki şubeleri seçime EKLER (çıkarmaz, ayrı durum tutmaz).
   * Aktif seviyeyle KESİŞTİRİLİR — "Eşit Ağırlık" 10-11-12'yi kapsayabilir ama
   * takvim girdisi TEK seviyeye bağlıdır (backend karışık seviyeyi reddeder).
   */
  const kumeSubeleri = (groupId: number): number[] =>
    (sections.data ?? [])
      .filter((s) => s.group === groupId && aktifSeviye !== null && s.class_level === aktifSeviye)
      .map((s) => s.id);

  const applyGroup = (key: string, groupId: number) => {
    const ids = kumeSubeleri(groupId);
    setSecim((prev) => {
      const mevcut = prev[key];
      if (!mevcut) return prev;
      return {
        ...prev,
        [key]: { ...mevcut, sectionIds: [...new Set([...mevcut.sectionIds, ...ids])] },
      };
    });
  };

  const applyGroupToplu = (groupId: number) =>
    setTopluSections((prev) => [...new Set([...prev, ...kumeSubeleri(groupId)])]);

  /** Aktif seviyede işaretli (havuzda olmayan) derslerin seçim anahtarları. */
  const aktifSeviyeAnahtarlari = useMemo(() => {
    if (aktif === null) return [];
    return aktif.courses
      .filter((c) => !c.in_pool)
      .map((c) => secimAnahtari(aktif.value, c.id))
      .filter((key) => key in secim);
  }, [aktif, secim]);

  const topluUygula = () => {
    const ids = topluPtype === "SECTIONS" ? [...topluSections] : [];
    setSecim((prev) => {
      const next = { ...prev };
      for (const key of aktifSeviyeAnahtarlari) {
        next[key] = { ptype: topluPtype, sectionIds: ids };
      }
      return next;
    });
  };

  const items: BulkEntryItem[] = useMemo(
    () =>
      Object.entries(secim).map(([key, kapsam]) => {
        const [level, courseId] = key.split(":").map(Number);
        return {
          course_id: courseId,
          level,
          participant_type: kapsam.ptype,
          // LEVEL kapsamda şube listesi TAŞINMAZ — backend de boş liste yazar.
          section_ids: kapsam.ptype === "SECTIONS" ? kapsam.sectionIds : [],
        };
      }),
    [secim],
  );

  // Şube seçilmemiş SECTIONS satırı sessizce "seviye geneli"ne düşmemeli:
  // kaydetme kapatılır ve eksik ders adı gösterilir.
  const eksikDersAdlari = useMemo(() => {
    const adlar: string[] = [];
    for (const [key, kapsam] of Object.entries(secim)) {
      if (kapsam.ptype !== "SECTIONS" || kapsam.sectionIds.length > 0) continue;
      const [level, courseId] = key.split(":").map(Number);
      const ad = levels
        .find((l) => l.value === level)
        ?.courses.find((c) => c.id === courseId)?.name;
      if (ad) adlar.push(ad);
    }
    return adlar;
  }, [secim, levels]);

  const saveMutation = useMutation({
    mutationFn: () => examCalendarApi.bulkEntries(calendarId, items),
    onSuccess: (result) => {
      const base = `${result.created.length} ders eklendi, ${result.existed.length} zaten vardı.`;
      if (result.skipped.length > 0) {
        // Tek birleşik mesaj (snackbar kuyruklu — iki mesaj sırayla beklerdi);
        // reddedilen ders SESSİZCE DÜŞMEZ.
        snackbar.error(
          `${base} ${result.skipped.length} ders atlandı: ${result.skipped
            .slice(0, 3)
            .join("; ")}${result.skipped.length > 3 ? "…" : ""}`,
        );
      } else {
        snackbar.success(base);
      }
      onSaved();
    },
    onError: (e) =>
      snackbar.error(e instanceof ApiError ? e.message : "Seçmeli dersler eklenemedi."),
  });

  const canSave = items.length > 0 && eksikDersAdlari.length === 0 && !saveMutation.isPending;

  return (
    <Dialog
      open
      wide
      onClose={onClose}
      title="Seçmeli ders seç"
      actions={
        <>
          <Button variant="text" onClick={onClose} disabled={saveMutation.isPending}>
            Vazgeç
          </Button>
          <Button icon="check" onClick={() => saveMutation.mutate()} disabled={!canSave}>
            {saveMutation.isPending ? "Ekleniyor…" : `Havuza ekle (${items.length})`}
          </Button>
        </>
      }
    >
      <div className="flex flex-col gap-3">
        <p className="text-body-medium text-on-surface-variant">
          Seçmeli dersler seviye seviye seçilir. Bir dersi işaretleyince katılımcı kapsamını da
          belirleyebilirsiniz: seviyenin tamamı, bir şube kümesi ya da tek tek şubeler.
        </p>

        {optionsQuery.isPending ? (
          <SkeletonList rows={4} />
        ) : optionsQuery.isError ? (
          <p role="alert" className="text-body-medium text-error">
            Seçmeli ders listesi yüklenemedi:{" "}
            {optionsQuery.error instanceof ApiError
              ? optionsQuery.error.message
              : "beklenmeyen hata."}
          </p>
        ) : levels.length === 0 ? (
          <p className="text-body-medium text-on-surface-variant">
            Seçilebilecek seçmeli ders yok. Ders havuzunda seçmeli derslerin “Sınav” alanı{" "}
            <strong>Yazılı</strong> olmalı ve o seviyede öğrenci bulunmalı.
          </p>
        ) : (
          <>
            <Tabs
              items={levels.map((l) => ({ key: String(l.value), label: l.display_label }))}
              active={activeLevel}
              onChange={(key) => {
                setActiveLevel(key);
                // Toplu panel seviyeye ait — sekme değişince şube seçimi sıfırlanır.
                setTopluSections([]);
              }}
              ariaLabel="Seviyeler"
              idBase="secmeli-seviye"
            />
            <div {...tabPanelProps("secmeli-seviye", activeLevel)} className="flex flex-col gap-3">
              {aktif === null ? null : (
                <>
                  <TopluKapsamPaneli
                    ptype={topluPtype}
                    onPtypeChange={(p) => {
                      setTopluPtype(p);
                      if (p === "LEVEL") setTopluSections([]);
                    }}
                    sectionIds={topluSections}
                    sections={seviyeSubeleri}
                    groups={(sectionGroups.data ?? []).map((g) => ({ id: g.id, name: g.name }))}
                    onToggleSection={(id) =>
                      setTopluSections((prev) =>
                        prev.includes(id) ? prev.filter((v) => v !== id) : [...prev, id],
                      )
                    }
                    onApplyGroup={applyGroupToplu}
                    disabled={
                      aktifSeviyeAnahtarlari.length === 0 ||
                      (topluPtype === "SECTIONS" && topluSections.length === 0)
                    }
                    onApply={topluUygula}
                    seciliSayisi={aktifSeviyeAnahtarlari.length}
                  />

                  <ul className="flex flex-col gap-2">
                    {aktif.courses.map((c) => {
                      const key = secimAnahtari(aktif.value, c.id);
                      const kapsam = secim[key];
                      const checked = c.in_pool || kapsam !== undefined;
                      return (
                        <li
                          key={c.id}
                          className="rounded-shape-md border border-outline-variant p-3"
                        >
                          <label
                            className={`flex min-h-9 items-center gap-2 text-body-medium text-on-surface ${
                              c.in_pool ? "" : "cursor-pointer"
                            }`}
                          >
                            <input
                              type="checkbox"
                              className="h-5 w-5 accent-primary"
                              checked={checked}
                              disabled={c.in_pool}
                              readOnly={c.in_pool}
                              onChange={() => !c.in_pool && toggleCourse(aktif.value, c.id)}
                            />
                            {c.name}
                            {c.in_pool ? (
                              <span className="rounded-full bg-surface-container-high px-2 py-0.5 text-label-small text-on-surface-variant">
                                Havuzda
                              </span>
                            ) : null}
                          </label>
                          {kapsam !== undefined && !c.in_pool ? (
                            <KapsamSatiri
                              courseName={c.name}
                              kapsam={kapsam}
                              sections={seviyeSubeleri}
                              groups={(sectionGroups.data ?? []).map((g) => ({
                                id: g.id,
                                name: g.name,
                              }))}
                              onPtypeChange={(p) =>
                                setKapsam(key, {
                                  ptype: p,
                                  // LEVEL'e dönüşte şube seçimi bırakılmaz.
                                  sectionIds: p === "LEVEL" ? [] : kapsam.sectionIds,
                                })
                              }
                              onToggleSection={(id) => toggleSection(key, id)}
                              onApplyGroup={(gid) => applyGroup(key, gid)}
                            />
                          ) : null}
                        </li>
                      );
                    })}
                  </ul>
                </>
              )}
            </div>
          </>
        )}

        {eksikDersAdlari.length > 0 ? (
          <p role="alert" className="text-body-medium text-error">
            Şube seçilmemiş ders var: {eksikDersAdlari.join(", ")}. En az bir şube seçin ya da
            kapsamı “Seviye geneli” yapın.
          </p>
        ) : null}
      </div>
    </Dialog>
  );
}

/** Aktif seviyedeki işaretli derslere aynı kapsamı basan kısayol. */
function TopluKapsamPaneli({
  ptype,
  onPtypeChange,
  sectionIds,
  sections,
  groups,
  onToggleSection,
  onApplyGroup,
  onApply,
  disabled,
  seciliSayisi,
}: {
  ptype: ParticipantTypeCode;
  onPtypeChange: (p: ParticipantTypeCode) => void;
  sectionIds: number[];
  sections: { id: number; class_label: string }[];
  groups: { id: number; name: string }[];
  onToggleSection: (id: number) => void;
  onApplyGroup: (groupId: number) => void;
  onApply: () => void;
  disabled: boolean;
  seciliSayisi: number;
}) {
  return (
    <fieldset className="rounded-shape-md bg-surface-container p-3">
      <legend className="px-1 text-label-large text-on-surface-variant">
        Seçili derslere topluca kapsam uygula
      </legend>
      <div className="flex flex-wrap items-end gap-3">
        <div className="w-44">
          <Select
            label="Kapsam"
            options={KAPSAM_SECENEKLERI}
            value={ptype}
            onChange={(e) => onPtypeChange(e.target.value as ParticipantTypeCode)}
          />
        </div>
        <Button variant="tonal" icon="done_all" onClick={onApply} disabled={disabled}>
          {`Seçili ${seciliSayisi} derse uygula`}
        </Button>
      </div>
      {ptype === "SECTIONS" ? (
        <SubeSecici
          adPreki="Toplu"
          sectionIds={sectionIds}
          sections={sections}
          groups={groups}
          onToggleSection={onToggleSection}
          onApplyGroup={onApplyGroup}
        />
      ) : null}
    </fieldset>
  );
}

/** Tek dersin kapsam denetimi (işaretlenince açılır). */
function KapsamSatiri({
  courseName,
  kapsam,
  sections,
  groups,
  onPtypeChange,
  onToggleSection,
  onApplyGroup,
}: {
  courseName: string;
  kapsam: Kapsam;
  sections: { id: number; class_label: string }[];
  groups: { id: number; name: string }[];
  onPtypeChange: (p: ParticipantTypeCode) => void;
  onToggleSection: (id: number) => void;
  onApplyGroup: (groupId: number) => void;
}) {
  return (
    <div className="mt-2 flex flex-col gap-2 border-t border-outline-variant/50 pt-2">
      <div className="w-44">
        <Select
          label=""
          aria-label={`${courseName} katılımcı kapsamı`}
          options={KAPSAM_SECENEKLERI}
          value={kapsam.ptype}
          onChange={(e) => onPtypeChange(e.target.value as ParticipantTypeCode)}
        />
      </div>
      {kapsam.ptype === "SECTIONS" ? (
        <SubeSecici
          adPreki={courseName}
          sectionIds={kapsam.sectionIds}
          sections={sections}
          groups={groups}
          onToggleSection={onToggleSection}
          onApplyGroup={onApplyGroup}
        />
      ) : null}
    </div>
  );
}
