// Seçmeli dersin bir şubedeki öğrenci listesi (19.09.2026) — "şubenin bir kısmı".
//
// Kural ŞUBE BAZINDADIR (backend `dersler.CourseEnrollment`): listesiz şubeyi dersi
// TAMAMEN alır; öğrenci işaretlenirse yalnız onlar alır. Tipik durum: 9/A'nın bir
// grubu Kur'an-ı Kerim, kalanı Peygamberimizin Hayatı — "Kalanlar" seçimi ikinci
// dersin listesini aynı adımda yazar. Liste sınav oturumunun katılımcılarını ve
// takvimde iki seçmelinin aynı saate konup konamayacağını belirler.
//
// e-Okul'dan toplu aktarım (OOK10002R010) Ders Havuzu başlığındadır; bu diyalog
// tek şubede elle düzeltme içindir.

import { useEffect, useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { ApiError } from "../../lib/api";
import Button from "../../ui/Button";
import Dialog from "../../ui/Dialog";
import Select from "../../ui/Select";
import { SkeletonList } from "../../ui/Skeleton";
import { useSnackbar } from "../../ui/SnackbarProvider";
import { okulApi } from "../okul/api";
import type { Course } from "./api";
import { derslerApi } from "./api";

export interface SubeBilgisi {
  id: number;
  class_level: number;
  class_section: string;
  class_label: string;
}

type Kip = "tamami" | "secili";

/** Okul numarasını sayı gibi sıralar ("9" < "10"); sayısal değilse metin sırası. */
function noSirasi(a: string, b: string): number {
  const na = Number(a);
  const nb = Number(b);
  if (Number.isFinite(na) && Number.isFinite(nb)) return na - nb;
  return a.localeCompare(b, "tr");
}

export default function DersOgrenciListesiDialog({
  course,
  section,
  listedIds,
  onClose,
  onSaved,
}: {
  course: Course;
  section: SubeBilgisi;
  /** Şubenin kayıtlı listesi; `null` = listesiz (şubenin tamamı). */
  listedIds: number[] | null;
  onClose: () => void;
  onSaved: () => void;
}) {
  const snackbar = useSnackbar();
  const queryClient = useQueryClient();
  const [kip, setKip] = useState<Kip>(listedIds ? "secili" : "tamami");
  const [secili, setSecili] = useState<Set<number>>(() => new Set(listedIds ?? []));
  const [kalanDers, setKalanDers] = useState<string>("");

  const ogrenciler = useQuery({
    queryKey: ["students", "section", section.class_level, section.class_section],
    queryFn: () =>
      okulApi.listStudents({
        classLevel: section.class_level,
        classSection: section.class_section,
        onlyActive: true,
        limit: 500,
      }),
  });
  // "Kalanlar" için aynı sınıf düzeyinde okutulan öbür seçmeliler.
  const secmeliler = useQuery({
    queryKey: ["courses", "elective", section.class_level],
    queryFn: () => derslerApi.listCourses({ level: section.class_level, courseType: "ELECTIVE" }),
  });

  const liste = useMemo(
    () =>
      [...(ogrenciler.data?.results ?? [])].sort((a, b) =>
        noSirasi(a.student_number, b.student_number),
      ),
    [ogrenciler.data],
  );
  // Şubeden ayrılmış öğrenci listede kalmışsa sayılmaz (kaydetme yalnız şubedekileri yazar).
  useEffect(() => {
    if (!ogrenciler.data) return;
    const mevcut = new Set(ogrenciler.data.results.map((s) => s.id));
    setSecili((prev) => new Set([...prev].filter((id) => mevcut.has(id))));
  }, [ogrenciler.data]);

  const kalanSayisi = liste.length - secili.size;
  const obur = (secmeliler.data ?? []).filter((c) => c.id !== course.id && c.is_active);

  const kaydet = useMutation({
    mutationFn: () =>
      derslerApi.setSectionEnrollment(course.id, {
        section_id: section.id,
        student_ids: kip === "tamami" ? [] : [...secili],
        ...(kip === "secili" && kalanDers ? { complement_course_id: Number(kalanDers) } : {}),
      }),
    onSuccess: () => {
      snackbar.success(`${section.class_label} şubesinin “${course.name}” listesi kaydedildi.`);
      for (const key of [
        ["course-enrollments"],
        ["course-enrollment-counts"],
        ["course-section-offerings"],
        ["course-sections"],
      ]) {
        void queryClient.invalidateQueries({ queryKey: key });
      }
      onSaved();
    },
    onError: (e) => snackbar.error(e instanceof ApiError ? e.message : "Liste kaydedilemedi."),
  });

  const secimEksik = kip === "secili" && secili.size === 0;
  const toggle = (id: number) =>
    setSecili((prev) => {
      const yeni = new Set(prev);
      if (yeni.has(id)) yeni.delete(id);
      else yeni.add(id);
      return yeni;
    });

  return (
    <Dialog
      open
      wide
      onClose={onClose}
      title={`${course.name} — ${section.class_label} öğrencileri`}
      actions={
        <>
          <Button variant="text" onClick={onClose} disabled={kaydet.isPending}>
            Vazgeç
          </Button>
          <Button
            icon="check"
            onClick={() => kaydet.mutate()}
            disabled={kaydet.isPending || ogrenciler.isPending || secimEksik}
          >
            {kaydet.isPending ? "Kaydediliyor…" : "Kaydet"}
          </Button>
        </>
      }
    >
      <fieldset className="mb-3 flex flex-col gap-1">
        <legend className="sr-only">Bu şubede dersi kimler alıyor?</legend>
        <label className="flex min-h-9 items-center gap-2 text-body-medium text-on-surface">
          <input
            type="radio"
            name="kip"
            className="h-5 w-5 accent-primary"
            checked={kip === "tamami"}
            onChange={() => setKip("tamami")}
          />
          Şubenin tamamı bu dersi alıyor
        </label>
        <label className="flex min-h-9 items-center gap-2 text-body-medium text-on-surface">
          <input
            type="radio"
            name="kip"
            className="h-5 w-5 accent-primary"
            checked={kip === "secili"}
            onChange={() => setKip("secili")}
          />
          Yalnız işaretlenen öğrenciler alıyor
        </label>
      </fieldset>

      {kip === "secili" && (
        <>
          <p className="mb-2 text-body-small text-on-surface-variant">
            Sınav oturumunda bu şubeden yalnız işaretlenen öğrenciler bu derse girer ve bu dersin
            kitapçığını alır. e-Okul'dan toplu aktarım için Ders Havuzu'ndaki “e-Okul'dan seçmeli
            öğrencileri aktar” düğmesini kullanın.
          </p>
          {ogrenciler.isPending ? (
            <SkeletonList rows={4} />
          ) : ogrenciler.error ? (
            <p role="alert" className="text-body-medium text-error">
              Öğrenciler yüklenemedi:{" "}
              {ogrenciler.error instanceof ApiError
                ? ogrenciler.error.message
                : "beklenmeyen hata."}
            </p>
          ) : liste.length === 0 ? (
            <p className="text-body-medium text-on-surface-variant">
              Bu şubede kayıtlı aktif öğrenci yok.
            </p>
          ) : (
            <>
              <div className="mb-2 flex flex-wrap items-center gap-2">
                <Button
                  variant="text"
                  icon="done_all"
                  onClick={() => setSecili(new Set(liste.map((s) => s.id)))}
                >
                  Tümünü işaretle
                </Button>
                <Button variant="text" icon="remove_done" onClick={() => setSecili(new Set())}>
                  İşaretleri kaldır
                </Button>
                <span className="text-body-small text-on-surface-variant">
                  {secili.size} / {liste.length} öğrenci işaretli
                </span>
              </div>
              <ul className="grid max-h-80 grid-cols-1 gap-x-4 overflow-y-auto sm:grid-cols-2">
                {liste.map((s) => (
                  <li key={s.id}>
                    <label className="flex min-h-9 items-center gap-2 text-body-medium text-on-surface">
                      <input
                        type="checkbox"
                        className="h-5 w-5 accent-primary"
                        checked={secili.has(s.id)}
                        onChange={() => toggle(s.id)}
                        aria-label={`${s.student_number} ${s.full_name}`}
                      />
                      <span className="w-14 shrink-0 text-on-surface-variant">
                        {s.student_number}
                      </span>
                      <span>{s.full_name}</span>
                    </label>
                  </li>
                ))}
              </ul>
              <div className="mt-3">
                <Select
                  label="İşaretlenmeyen öğrenciler"
                  value={kalanDers}
                  onChange={(e) => setKalanDers(e.target.value)}
                  options={[
                    { value: "", label: "Dokunma (öbür derslerin listesi değişmez)" },
                    ...obur.map((c) => ({ value: String(c.id), label: `${c.name} dersine yaz` })),
                  ]}
                  helperText={
                    kalanDers
                      ? `${kalanSayisi} öğrenci seçilen dersin bu şubedeki listesi olur (eski listesi değişir).`
                      : "Örnek: bir grup Kur'an-ı Kerim alıyorsa kalanlar Peygamberimizin Hayatı'na yazılabilir."
                  }
                />
              </div>
            </>
          )}
          {secimEksik && liste.length > 0 && (
            <p className="mt-2 text-body-small text-error">
              En az bir öğrenci işaretleyin ya da “Şubenin tamamı”nı seçin.
            </p>
          )}
        </>
      )}
    </Dialog>
  );
}
