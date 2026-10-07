// Seçmeli ders seçimi bekleyen öğrenciler (07.10.2026, kullanıcı isteği).
//
// Şubesi değişen ya da nakil gelen öğrencinin yeni şubesi bir seçmeliyi BÖLÜNEREK
// okutuyorsa (şubede o dersin öğrenci listesi varsa) öğrenci listelerin hiçbirinde
// değildir: kendiliğinden yazılsaydı yanlış derse, yazılmasaydı sessizce hiçbir
// sınava girmezdi. Program öğrenciyi burada "seçim bekliyor" diye gösterir; idareci
// aldığı dersleri işaretler. Eski şubesinde aldığı ders yeni şubede de varsa
// işaretli gelir (öneri). Seçim beklerken o şubenin bölünmüş dersini içeren oturum
// DAĞITILAMAZ (kullanıcı kararı — backend `participants.has_pending_choices`).
//
// Bant iki yerde durur: Ders Havuzu (pencereyi açar) ve Kişiler (Ders Havuzu'na
// götürür). İkisi de aynı sorguyu (`PENDING_CHOICES_KEY`) okur.

import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Link } from "react-router-dom";

import { ApiError } from "../../lib/api";
import { formatNumber } from "../../lib/format";
import Button from "../../ui/Button";
import Dialog from "../../ui/Dialog";
import EmptyState from "../../ui/EmptyState";
import Icon from "../../ui/Icon";
import { SkeletonList } from "../../ui/Skeleton";
import { useSnackbar } from "../../ui/SnackbarProvider";
import type { PendingElectiveChoice } from "./api";
import { PENDING_CHOICES_KEY, derslerApi } from "./api";

/** Pencerenin derin bağlantısı — Kişiler bandı ve sihirbaz buraya götürür. */
export const SECIM_BEKLEYENLER_YOLU = "/dersler?secim=bekleyen";

export function useBekleyenSecimler() {
  return useQuery({
    queryKey: PENDING_CHOICES_KEY,
    queryFn: () => derslerApi.pendingElectiveChoices(),
    // Aktif ders yılı yoksa uç 400 döner; bant gizli kalır, sayfa çalışır.
    retry: false,
  });
}

/** Seçim bekleyen öğrenci varsa bant; `onOpen` yoksa Ders Havuzu'na bağlantı verir. */
export function SecimBekleyenBandi({ onOpen }: { onOpen?: () => void }) {
  const sorgu = useBekleyenSecimler();
  const sayi = sorgu.data?.results.length ?? 0;
  if (sayi === 0) return null;
  return (
    <div
      role="status"
      className="flex flex-wrap items-center gap-3 rounded-shape-sm bg-tertiary-container px-4 py-3 text-body-medium text-on-tertiary-container"
    >
      <Icon name="rule" size="lg" />
      <span className="min-w-60 flex-1">
        <strong>{formatNumber(sayi)} öğrencinin seçmeli ders seçimi bekliyor.</strong> Şubeleri
        değişti ya da okula yeni geldiler ve yeni şubeleri bazı seçmelileri bölünerek okutuyor.
        Seçim yapılana kadar bu şubelerin bölünmüş derslerini içeren sınav oturumları dağıtılamaz.
      </span>
      {onOpen ? (
        <Button variant="tonal" icon="checklist" onClick={onOpen}>
          Seçimleri yap
        </Button>
      ) : (
        <Link
          to={SECIM_BEKLEYENLER_YOLU}
          className="font-medium underline underline-offset-2 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary"
        >
          Ders Havuzu → Seçimleri yap
        </Link>
      )}
    </div>
  );
}

/** Ders kaydına dokunan sorgular — seçim kaydedilince hepsi tazelenir. */
const TAZELENECEK = [
  PENDING_CHOICES_KEY,
  ["course-enrollments"],
  ["course-enrollment-counts"],
  ["course-section-offerings"],
  ["course-sections"],
  ["exam-participants"],
] as const;

export default function SecimBekleyenlerDialog({ onClose }: { onClose: () => void }) {
  const sorgu = useBekleyenSecimler();
  const satirlar = sorgu.data?.results ?? [];

  return (
    <Dialog
      open
      wide
      onClose={onClose}
      title="Seçmeli ders seçimi bekleyen öğrenciler"
      actions={
        <Button variant="text" onClick={onClose}>
          Kapat
        </Button>
      }
    >
      <p className="mb-3 text-body-medium text-on-surface-variant">
        Bu öğrencilerin şubesi değişti ya da okula yeni geldiler; yeni şubeleri aşağıdaki
        seçmelileri bölünerek okutuyor (dersi şubenin yalnız bir kısmı alıyor). Öğrencinin aldığı
        dersleri işaretleyip kaydedin; hiçbirini almıyorsa işaretsiz kaydedin. Eski şubesinde aldığı
        ders işaretli gelir — bu yalnız bir öneridir. e-Okul'dan seçmeli öğrencileri yeniden
        aktarırsanız raporda geçen öğrencilerin seçimi kendiliğinden kapanır.
      </p>
      {sorgu.isPending ? (
        <SkeletonList rows={3} />
      ) : sorgu.error ? (
        <p role="alert" className="text-body-medium text-error">
          {sorgu.error instanceof ApiError ? sorgu.error.message : "Liste yüklenemedi."}
        </p>
      ) : satirlar.length === 0 ? (
        <EmptyState
          compact
          icon="check_circle"
          title="Seçim bekleyen öğrenci yok"
          description="Bütün öğrencilerin seçmeli dersleri belli."
        />
      ) : (
        <ul className="flex flex-col gap-3">
          {satirlar.map((satir) => (
            <SecimSatiri key={satir.student_id} satir={satir} />
          ))}
        </ul>
      )}
    </Dialog>
  );
}

function SecimSatiri({ satir }: { satir: PendingElectiveChoice }) {
  const snackbar = useSnackbar();
  const queryClient = useQueryClient();
  const [secili, setSecili] = useState<Set<number>>(
    () => new Set(satir.courses.filter((c) => c.enrolled || c.suggested).map((c) => c.course_id)),
  );

  const kaydet = useMutation({
    mutationFn: () => derslerApi.resolveElectiveChoice(satir.student_id, [...secili]),
    onSuccess: () => {
      // Bildirimde öğrenci adı geçmez — satır zaten gösteriyordu.
      snackbar.success(
        secili.size === 0
          ? "Kaydedildi: öğrenci bu şubede bölünerek okutulan derslerin hiçbirini almıyor."
          : "Öğrencinin seçmeli dersleri kaydedildi.",
      );
      for (const key of TAZELENECEK) void queryClient.invalidateQueries({ queryKey: [...key] });
    },
    onError: (e) => snackbar.error(e instanceof ApiError ? e.message : "Seçim kaydedilemedi."),
  });

  const toggle = (id: number) =>
    setSecili((prev) => {
      const yeni = new Set(prev);
      if (yeni.has(id)) yeni.delete(id);
      else yeni.add(id);
      return yeni;
    });

  return (
    <li className="rounded-shape-md border border-outline-variant p-3">
      <fieldset>
        <legend className="mb-1 flex flex-wrap items-baseline gap-x-2 text-title-small text-on-surface">
          <span className="text-on-surface-variant">{satir.student_number}</span>
          <span>{satir.full_name}</span>
          <span className="text-body-small text-on-surface-variant">— {satir.class_label}</span>
        </legend>
        <div className="flex flex-wrap items-end gap-x-6 gap-y-1">
          {satir.courses.map((c) => (
            <label
              key={c.course_id}
              className="flex min-h-9 items-center gap-2 text-body-medium text-on-surface"
            >
              <input
                type="checkbox"
                className="h-5 w-5 accent-primary"
                checked={secili.has(c.course_id)}
                onChange={() => toggle(c.course_id)}
              />
              <span>
                {c.course_name}{" "}
                <span className="text-body-small text-on-surface-variant">
                  ({formatNumber(c.listed_count)} öğrenci
                  {c.suggested ? " · eski şubesinde alıyordu" : ""})
                </span>
              </span>
            </label>
          ))}
          <span className="ml-auto" />
          <Button
            variant="tonal"
            icon="check"
            onClick={() => kaydet.mutate()}
            disabled={kaydet.isPending}
          >
            {kaydet.isPending ? "Kaydediliyor…" : "Kaydet"}
          </Button>
        </div>
      </fieldset>
    </li>
  );
}
