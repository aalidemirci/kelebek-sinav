// Bakanlığın ülke geneli ortak yazılı sınavları (19.09.2026) — takvim sayfasında
// bant. Kaynak: ÖDSHGM'nin 10.09.2026 tarihli yazısının eki (Ülke Geneli Ortak
// Yazılı Sınav Takvimi). Takvim sınav GÜNÜNÜ verir, ders saatini vermez:
// "Takvime uygula" sınavı resmî gününe okulun ilk sınav saatiyle SABİTLER,
// saati idareci ızgarada düzeltir (kullanıcı kararı). Yeni takvim oluşturulurken
// uygulama kendiliğinden yapılır; bant eski taslaklar ve eksikler içindir.
// Yalnız okulun öğrencisi olan sınıf düzeyleri gelir (ortaokul satırları düşer).

import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { ApiError } from "../../lib/api";
import { formatDate } from "../../lib/format";
import Button from "../../ui/Button";
import Icon from "../../ui/Icon";
import { useSnackbar } from "../../ui/SnackbarProvider";
import type { NationalExamApplyResult, NationalExamRow } from "./api";
import { examCalendarApi } from "./api";

function durumMetni(sinav: NationalExamRow): string {
  if (sinav.status === "placed") {
    return `takvimde, ${sinav.period_no ?? "?"}. ders saati`;
  }
  if (sinav.status === "missing_course") return "ders havuzunda bu adla ders yok";
  return "takvime uygulanmadı";
}

export default function BakanlikSinavlari({
  calendarId,
  editable,
  onApplied,
}: {
  calendarId: number;
  /** Yalnız taslak takvimde uygulanabilir. */
  editable: boolean;
  onApplied: () => void;
}) {
  const snackbar = useSnackbar();
  const qc = useQueryClient();
  const [sonuc, setSonuc] = useState<NationalExamApplyResult | null>(null);
  const plan = useQuery({
    queryKey: ["exam-calendar-national", calendarId],
    queryFn: () => examCalendarApi.nationalExams(calendarId),
    retry: false,
  });
  const uygula = useMutation({
    mutationFn: () => examCalendarApi.applyNationalExams(calendarId),
    onSuccess: (data) => {
      qc.setQueryData(["exam-calendar-national", calendarId], { exams: data.exams });
      setSonuc(data.result);
      const adet = data.result.placed.length;
      snackbar.success(
        adet ? `${adet} Bakanlık sınavı takvime yerleştirildi.` : "Takvimde değişiklik olmadı.",
      );
      onApplied();
    },
    onError: (e) =>
      snackbar.error(e instanceof ApiError ? e.message : "Bakanlık sınavları uygulanamadı."),
  });

  const sinavlar = plan.data?.exams ?? [];
  if (sinavlar.length === 0) return null;
  const bekleyen = sinavlar.some((s) => s.status === "pending");

  return (
    <section
      aria-label="Bakanlık sınavları"
      className="mb-3 flex flex-col gap-1 rounded-shape-sm bg-secondary-container px-3 py-2 text-body-small text-on-secondary-container"
    >
      <p className="flex items-center gap-2 font-medium">
        <Icon name="account_balance" size="sm" />
        Bakanlığın ülke geneli ortak yazılı sınavları
      </p>
      <ul className="flex flex-col gap-0.5 pl-6">
        {sinavlar.map((s) => (
          <li key={`${s.level}-${s.course_name}`}>
            <strong>
              {s.level_label} {s.course_name}
            </strong>{" "}
            — {formatDate(s.date)} {s.weekday_label} · {durumMetni(s)}
          </li>
        ))}
      </ul>
      <p className="pl-6">
        Dayanak: {sinavlar[0].source}. Takvim sınav gününü verir; ders saati Bakanlığın uygulama
        esaslarıyla kesinleşir — saati Yerleştirme sekmesinde düzeltebilirsiniz.
      </p>
      {sonuc && (sonuc.placed.length > 0 || sonuc.skipped.length > 0) ? (
        <ul className="flex flex-col gap-0.5 pl-6">
          {sonuc.placed.map((m) => (
            <li key={`y-${m}`}>Yerleştirildi: {m}</li>
          ))}
          {sonuc.skipped.map((m) => (
            <li key={`a-${m}`}>Uygulanamadı: {m}</li>
          ))}
        </ul>
      ) : null}
      {editable && bekleyen ? (
        <div className="pl-4">
          <Button
            variant="text"
            icon="event_available"
            onClick={() => uygula.mutate()}
            disabled={uygula.isPending}
          >
            {uygula.isPending ? "Uygulanıyor…" : "Takvime uygula"}
          </Button>
        </div>
      ) : null}
    </section>
  );
}
