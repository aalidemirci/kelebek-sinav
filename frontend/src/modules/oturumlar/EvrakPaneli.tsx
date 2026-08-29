// Evrak paneli (F4) — OYS RaporlarPaneli'nden UYARLANDI: R1-R5 + R7-R9 tek tek
// indirme + "tümünü ZIP" (arşivden yeniden basım dahil). R6 yalnız gözetmen
// ayarı açıkken listelenir (görevlendirme F7'de gelir — o güne dek backend
// Türkçe hatayla reddeder); salon bazlı raporlar (R1/R2/R3/R7) salon
// filtresiyle daraltılabilir. Durum kapısı backend'dedir; panel yalnız sunar.

import { useState } from "react";
import { useQuery } from "@tanstack/react-query";

import { ApiError } from "../../lib/api";
import { saveBlob } from "../../lib/download";
import Button from "../../ui/Button";
import Select from "../../ui/Select";
import { useSnackbar } from "../../ui/SnackbarProvider";
import type { ExamSession } from "./api";
import { examSessionApi, REPORT_CATALOG } from "./api";

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

  const download = async (code: string, roomScoped: boolean) => {
    setBusy(code);
    try {
      const blob =
        code === "zip"
          ? await examSessionApi.reportsZipBlob(session.id)
          : await examSessionApi.reportBlob(
              session.id,
              code,
              roomScoped && roomId !== "" ? Number(roomId) : undefined,
            );
      const ext = code === "zip" ? "zip" : code === "r5" ? "xlsx" : "pdf";
      saveBlob(blob, `${code === "zip" ? "sinav_evraki" : code}_oturum_${session.id}.${ext}`);
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
          label="Salon filtresi (R1 / R2 / R3 / R7)"
          options={roomOptions}
          placeholder="Tüm salonlar"
          value={roomId}
          onChange={(e) => setRoomId(e.target.value)}
          className="w-64"
        />
        <span className="ml-auto" />
        <Button
          icon="folder_zip"
          onClick={() => void download("zip", false)}
          disabled={busy !== null}
        >
          {busy === "zip" ? "Hazırlanıyor…" : "Tümünü indir (ZIP)"}
        </Button>
      </div>

      <ul className="flex flex-col gap-1">
        {catalog.map((item) => (
          <li
            key={item.code}
            className="flex flex-wrap items-center gap-3 border-b border-outline-variant py-2"
          >
            <span className="w-10 text-label-large uppercase text-on-surface-variant">
              {item.code}
            </span>
            <span className="text-body-medium text-on-surface">{item.title}</span>
            {item.roomScoped && roomId !== "" && (
              <span className="text-body-small text-on-surface-variant">(salon filtreli)</span>
            )}
            <span className="ml-auto" />
            <Button
              variant="text"
              icon="download"
              onClick={() => void download(item.code, item.roomScoped)}
              disabled={busy !== null}
            >
              {busy === item.code ? "İndiriliyor…" : "İndir"}
            </Button>
          </li>
        ))}
      </ul>
      <p className="text-body-small text-on-surface-variant">
        Kişiselleştirilmiş kitapçıklar (R10) &quot;Sorular ve Kitapçıklar&quot; sekmesinden
        üretilir. Arşivli oturumdan tüm evrak yeniden basılabilir.
      </p>
    </div>
  );
}
