// Bakanlık takvimleri bandı — takvim sayfasında iki bölüm:
// 1) Ülke geneli ortak yazılı sınavlar (19.09.2026): ÖDSHGM'nin 10.09.2026 tarihli
//    yazısının eki. Takvim sınav GÜNÜNÜ verir, ders saatini vermez: "Takvime uygula"
//    sınavı resmî gününe okulun ilk sınav saatiyle SABİTLER, saati idareci ızgarada
//    düzeltir (kullanıcı kararı).
// 2) OYSS uygulama takvimi (22.10.2026): Bakanlık okul geneli ortak yazılı sınavın
//    GÜNÜNÜ ve ders saatini verir (günde tek sınav 2., iki sınav 2. ve 4. ders
//    saati). Sınav okul sınavı kalır; "Takvime uygula" onu resmî gün + saate
//    sabitler. Kural ve açıklama metni sunucudan gelir (`oyss_info.notes`) — ön yüz
//    kopya kural yazmaz.
// Yeni takvim oluşturulurken ikisi de kendiliğinden uygulanır; bant eski taslaklar
// ve eksikler içindir. Yalnız okulun öğrencisi olan sınıf düzeyleri gelir.

import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { ApiError } from "../../lib/api";
import { formatDate } from "../../lib/format";
import Button from "../../ui/Button";
import Icon from "../../ui/Icon";
import { useSnackbar } from "../../ui/SnackbarProvider";
import type { MinistryExamsPlan, NationalExamRow, OyssExamRow } from "./api";
import { examCalendarApi } from "./api";

function durumMetni(sinav: NationalExamRow): string {
  if (sinav.status === "placed") {
    return `takvimde, ${sinav.period_no ?? "?"}. ders saati`;
  }
  if (sinav.status === "missing_course") return "ders havuzunda bu adla ders yok";
  return "takvime uygulanmadı";
}

/** Aynı gün, ders, saat ve durumdaki OYSS satırları tek satırda (düzeyler birleşir). */
interface OyssGrubu {
  key: string;
  ilk: OyssExamRow;
  levels: number[];
}

function oyssGruplari(satirlar: OyssExamRow[]): OyssGrubu[] {
  const gruplar = new Map<string, OyssGrubu>();
  for (const s of satirlar) {
    if (s.status === "missing_course") continue;
    const key = [
      s.date,
      s.course_name,
      s.pool_course_name,
      s.period_no,
      s.status,
      s.entry_date,
      s.entry_period_no,
    ].join("|");
    const grup = gruplar.get(key);
    if (grup) grup.levels.push(s.level);
    else gruplar.set(key, { key, ilk: s, levels: [s.level] });
  }
  return [...gruplar.values()];
}

/** [9, 10, 11] → "9., 10. ve 11. Sınıf"; [10] → "10. Sınıf". */
function duzeyler(levels: number[]): string {
  const parcalar = levels.map((lv) => `${lv}.`);
  const birlesik =
    parcalar.length > 1
      ? `${parcalar.slice(0, -1).join(", ")} ve ${parcalar[parcalar.length - 1]}`
      : (parcalar[0] ?? "");
  return `${birlesik} Sınıf`;
}

function oyssDurumu(s: OyssExamRow): string {
  if (s.status === "placed") {
    return s.entry_period_no !== null && s.entry_period_no !== s.period_no
      ? `takvimde, ${s.entry_period_no}. ders saati`
      : "takvimde";
  }
  if (s.status === "needs_pool") {
    return "seçmeli ders takvim havuzunda yok — Ders Havuzu'nda şubelerini girin";
  }
  if (s.entry_date && s.entry_date !== s.date) {
    return `takvimde başka günde (${formatDate(s.entry_date)})`;
  }
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
  const [sonuc, setSonuc] = useState<{ placed: string[]; skipped: string[] } | null>(null);
  const plan = useQuery({
    queryKey: ["exam-calendar-national", calendarId],
    queryFn: () => examCalendarApi.nationalExams(calendarId),
    retry: false,
  });
  const uygula = useMutation({
    mutationFn: () => examCalendarApi.applyNationalExams(calendarId),
    onSuccess: (data) => {
      const yeni: MinistryExamsPlan = {
        exams: data.exams,
        oyss: data.oyss,
        oyss_info: data.oyss_info,
      };
      qc.setQueryData(["exam-calendar-national", calendarId], yeni);
      const placed = [...data.result.placed, ...(data.oyss_result?.placed ?? [])];
      const skipped = [...data.result.skipped, ...(data.oyss_result?.skipped ?? [])];
      setSonuc({ placed, skipped });
      snackbar.success(
        placed.length
          ? `${placed.length} sınav Bakanlık takvimine göre yerleştirildi.`
          : "Takvimde değişiklik olmadı.",
      );
      onApplied();
    },
    onError: (e) =>
      snackbar.error(e instanceof ApiError ? e.message : "Bakanlık takvimi uygulanamadı."),
  });

  const sinavlar = plan.data?.exams ?? [];
  const oyss = plan.data?.oyss ?? [];
  const oyssInfo = plan.data?.oyss_info ?? null;
  const oyssVar = oyssInfo !== null && oyss.length > 0;
  if (sinavlar.length === 0 && !oyssVar) return null;
  const bekleyen =
    sinavlar.some((s) => s.status === "pending") || oyss.some((s) => s.status === "pending");
  const karsiliksiz = oyss.filter((s) => s.status === "missing_course");

  return (
    <section
      aria-label="Bakanlık sınavları"
      className="mb-3 flex flex-col gap-1 rounded-shape-sm bg-secondary-container px-3 py-2 text-body-small text-on-secondary-container"
    >
      {sinavlar.length > 0 && (
        <>
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
        </>
      )}
      {oyssVar && oyssInfo && (
        <>
          <p className="flex items-center gap-2 font-medium">
            <Icon name="event_note" size="sm" />
            Ortak Yazılı Sınav Sistemi (OYSS) uygulama takvimi
          </p>
          <ul className="flex flex-col gap-0.5 pl-6">
            {oyssGruplari(oyss).map(({ key, ilk, levels }) => (
              <li key={key}>
                <strong>
                  {ilk.course_name} — {duzeyler(levels)}
                </strong>
                {ilk.pool_course_name && ilk.pool_course_name !== ilk.course_name
                  ? ` (havuzdaki ders: ${ilk.pool_course_name})`
                  : ""}{" "}
                — {formatDate(ilk.date)} {ilk.weekday_label}
                {ilk.period_no !== null ? ` · ${ilk.period_no}. ders saati` : ""} ·{" "}
                {oyssDurumu(ilk)}
              </li>
            ))}
          </ul>
          {karsiliksiz.length > 0 && (
            <p className="pl-6">
              Ders havuzunda karşılığı olmayanlar:{" "}
              {karsiliksiz.map((s) => `${s.level_label} ${s.course_name}`).join(", ")} — ders o
              sınıf düzeyinde okutulmuyorsa işlem gerekmez.
            </p>
          )}
          <p className="pl-6">Dayanak: {oyssInfo.source}.</p>
          {oyssInfo.notes.map((not) => (
            <p key={not} className="pl-6">
              {not}
            </p>
          ))}
        </>
      )}
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
