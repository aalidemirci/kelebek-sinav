// "Başka oturumdan kopyala" — ders + katılacak şubeler ve/veya salon planını
// var olan TASLAK oturuma taşır; kopyadan sonra sihirbazda değiştirilebilir.
//
// "Katılacak sınıf" verisi fiziksel olarak `ExamSessionCourse.section_ids`
// içindedir; bu yüzden "dersler" seçeneği şubeleri de getirir — ayrı
// kopyalanamaz. Seed, yerleşim, yoklama, gözetmen ve onay damgaları TAŞINMAZ.

import { useState } from "react";
import { useMutation, useQuery } from "@tanstack/react-query";

import { ApiError } from "../../lib/api";
import Button from "../../ui/Button";
import Dialog from "../../ui/Dialog";
import Select from "../../ui/Select";
import { SkeletonList } from "../../ui/Skeleton";
import { useSnackbar } from "../../ui/SnackbarProvider";
import type { CopyPlanReport } from "./api";
import { examSessionApi } from "./api";
import { formatDate } from "./oturumEtiket";

export default function OturumKopyalaDialog({
  sessionId,
  onClose,
  onCopied,
}: {
  sessionId: number;
  onClose: () => void;
  onCopied: () => void;
}) {
  const snackbar = useSnackbar();
  const [kaynak, setKaynak] = useState("");
  const [dersler, setDersler] = useState(true);
  const [salonlar, setSalonlar] = useState(true);
  const [rapor, setRapor] = useState<CopyPlanReport | null>(null);

  const oturumlar = useQuery({
    queryKey: ["exam-sessions", "kopya-kaynagi"],
    queryFn: () => examSessionApi.list(),
  });

  const kopyala = useMutation({
    mutationFn: () =>
      examSessionApi.copyPlan(sessionId, {
        source_id: Number(kaynak),
        courses: dersler,
        rooms: salonlar,
      }),
    onSuccess: ({ report }) => {
      setRapor(report);
      const eklenen = report.courses_created.length + report.rooms_created.length;
      snackbar.success(`${eklenen} kalem kopyalandı.`);
      onCopied();
    },
    onError: (e) => snackbar.error(e instanceof ApiError ? e.message : "Kopyalanamadı."),
  });

  const secenekler = (oturumlar.data?.results ?? [])
    .filter((o) => o.id !== sessionId)
    .map((o) => ({
      value: String(o.id),
      label: `${o.name} — ${formatDate(o.exam_date)}`,
    }));

  return (
    <Dialog
      open
      onClose={onClose}
      title="Başka oturumdan kopyala"
      actions={
        <>
          <Button variant="text" onClick={onClose}>
            Kapat
          </Button>
          <Button
            icon="content_copy"
            disabled={kaynak === "" || kopyala.isPending || (!dersler && !salonlar)}
            onClick={() => kopyala.mutate()}
          >
            Kopyala
          </Button>
        </>
      }
    >
      <div className="flex flex-col gap-4">
        <p className="text-body-medium text-on-surface-variant">
          Seçtiğiniz oturumun planı bu taslağa eklenir; sonra üzerinde değişiklik yapabilirsiniz.
          Zaten ekli ders ve salonlar atlanır. Sınav tarihi, saati, dağıtım (seed), yoklama,
          gözetmen görevlendirmesi ve onay damgaları KOPYALANMAZ.
        </p>

        {oturumlar.isPending ? (
          <SkeletonList rows={2} />
        ) : secenekler.length === 0 ? (
          <p className="text-body-medium text-on-surface-variant">Kopyalanacak başka oturum yok.</p>
        ) : (
          <Select
            label="Kaynak oturum"
            placeholder="— seçin —"
            value={kaynak}
            onChange={(e) => setKaynak(e.target.value)}
            options={secenekler}
          />
        )}

        <label className="flex min-h-9 items-center gap-2 text-body-medium text-on-surface">
          <input
            type="checkbox"
            className="h-5 w-5 accent-primary"
            checked={dersler}
            onChange={(e) => setDersler(e.target.checked)}
          />
          Dersler ve katılacak şubeler
        </label>
        <label className="flex min-h-9 items-center gap-2 text-body-medium text-on-surface">
          <input
            type="checkbox"
            className="h-5 w-5 accent-primary"
            checked={salonlar}
            onChange={(e) => setSalonlar(e.target.checked)}
          />
          Kullanılacak derslikler
        </label>

        {rapor ? (
          <div className="rounded-shape-sm bg-surface-container p-3 text-body-small text-on-surface">
            <p className="font-medium">Kopyalama sonucu</p>
            <ul className="mt-1 space-y-0.5">
              {rapor.courses_created.map((x) => (
                <li key={`dc-${x}`}>+ {x}</li>
              ))}
              {rapor.rooms_created.map((x) => (
                <li key={`rc-${x}`}>+ {x}</li>
              ))}
              {[...rapor.courses_skipped, ...rapor.rooms_skipped].map((x) => (
                <li key={`sk-${x}`} className="text-on-surface-variant">
                  atlandı: {x}
                </li>
              ))}
              {rapor.warnings.map((x) => (
                <li key={`w-${x}`} className="text-error">
                  {x}
                </li>
              ))}
            </ul>
          </div>
        ) : null}
      </div>
    </Dialog>
  );
}
