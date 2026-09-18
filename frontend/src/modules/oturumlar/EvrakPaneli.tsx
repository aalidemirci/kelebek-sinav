// Evrak paneli (F4) — tek tek indirme + "tümünü ZIP" (arşivden yeniden basım
// dahil). 30.08.2026 sadeleştirmesinden sonra katalog altı satırdır: salon
// evrakı (birleşik), şube duyurusu, ihlal tutanağı, gözetmen görevlendirme,
// doğrulama raporu, Excel çizelge. Her satır ne işe yaradığını kendi altında
// söyler. R6 yalnız gözetmen ayarı açıkken listelenir; salon bazlı evrak
// (salon evrakı ve tutanak) salon filtresiyle daraltılabilir. Durum kapısı
// backend'dedir; panel yalnız sunar.
//
// İndirilen dosyanın adı belge adı + oturum adı + tarih taşır
// (docs/sozluk.md §3): "Salon-Sınav-Evrakı_1-Ortak-Sınav_16.11.2026.pdf". Eski
// `r7_oturum_3.pdf` masaüstünde hangi sınavın hangi belgesi olduğunu söylemiyordu.

import { useState } from "react";
import { useQuery } from "@tanstack/react-query";

import { ApiError } from "../../lib/api";
import { dosyaAdi, saveBlob } from "../../lib/download";
import { formatDate } from "../../lib/format";
import Button from "../../ui/Button";
import Select from "../../ui/Select";
import { useSnackbar } from "../../ui/SnackbarProvider";
import type { ExamSession, ReportCatalogItem } from "./api";
import { examSessionApi, REPORT_CATALOG, REPORTS_ZIP_FILE_TITLE } from "./api";

export default function EvrakPaneli({ session }: { session: ExamSession }) {
  const snackbar = useSnackbar();
  const [roomId, setRoomId] = useState("");
  const [busy, setBusy] = useState<string | null>(null);

  const seating = useQuery({
    queryKey: ["exam-seating", session.id],
    queryFn: () => examSessionApi.seating(session.id),
  });
  const roomOptions = (seating.data?.rooms ?? []).map((r) => ({
    value: String(r.room_id),
    label: r.room_name,
  }));

  const catalog = REPORT_CATALOG.filter((item) => item.code !== "r6" || session.proctors_enabled);
  const selectedRoom = roomOptions.find((r) => r.value === roomId);

  /** Belge adı + (salon filtreliyse salon adı) + oturum adı + tarih. */
  const fileName = (belge: string, ext: string, salon?: string) =>
    dosyaAdi([belge, salon, session.name, formatDate(session.exam_date)], ext);

  // `item` verilmezse "tümünü indir" ZIP'idir.
  const download = async (item?: ReportCatalogItem) => {
    setBusy(item?.code ?? "zip");
    try {
      if (item === undefined) {
        const blob = await examSessionApi.reportsZipBlob(session.id);
        saveBlob(blob, fileName(REPORTS_ZIP_FILE_TITLE, "zip"));
        return;
      }
      const filtered = item.roomScoped && roomId !== "";
      const blob = await examSessionApi.reportBlob(
        session.id,
        item.code,
        filtered ? Number(roomId) : undefined,
      );
      // Salon filtreli indirme ayrı dosyadır; tüm salonlarınkinin üstüne yazmasın.
      saveBlob(
        blob,
        fileName(item.fileTitle, item.ext, filtered ? selectedRoom?.label : undefined),
      );
    } catch (e) {
      snackbar.error(e instanceof ApiError ? e.message : "Evrak üretilemedi.");
    } finally {
      setBusy(null);
    }
  };

  return (
    <div className="flex flex-col gap-4">
      <div className="flex flex-wrap items-end gap-3">
        <Select
          label="Salon filtresi (salon evrakı ve tutanak)"
          options={roomOptions}
          placeholder="Tüm salonlar"
          value={roomId}
          onChange={(e) => setRoomId(e.target.value)}
          className="w-64"
        />
        <span className="ml-auto" />
        <Button icon="folder_zip" onClick={() => void download()} disabled={busy !== null}>
          {busy === "zip" ? "Hazırlanıyor…" : "Tümünü indir (ZIP)"}
        </Button>
      </div>

      <ul className="flex flex-col gap-1">
        {catalog.map((item) => (
          <li
            key={item.code}
            className="flex flex-wrap items-center gap-3 border-b border-outline-variant py-2"
          >
            <div className="min-w-0 flex-1">
              <div className="flex flex-wrap items-center gap-2">
                <span className="text-body-medium text-on-surface">{item.title}</span>
                {item.roomScoped && roomId !== "" && (
                  <span className="text-body-small text-on-surface-variant">(salon filtreli)</span>
                )}
              </div>
              <div className="text-body-small text-on-surface-variant">{item.note}</div>
            </div>
            <Button
              variant="text"
              icon="download"
              onClick={() => void download(item)}
              disabled={busy !== null}
            >
              {busy === item.code ? "İndiriliyor…" : "İndir"}
            </Button>
          </li>
        ))}
      </ul>
      <p className="text-body-small text-on-surface-variant">
        Kişiselleştirilmiş kitapçıklar “Sorular ve Kitapçıklar” sekmesinden üretilir. Arşivlenmiş
        oturumun evrakı da yeniden basılabilir.
      </p>
    </div>
  );
}
