// Oturum durum rozeti + tarih biçimi — OYS'de OturumlarPage içindeydi ve detay
// sayfası ORADAN import ediyordu (sayfalar arası import); KS'de yardımcı dosyaya
// çıkarıldı. Etiket sözlüğü api.ts'teki EXAM_SESSION_STATUS_TR'nin takma adıdır
// (backend TextChoices tek kaynak); formatDate lib/format.ts'ten yeniden dışa
// aktarılır — yerel kopya YAZILMAZ (tarih disiplini, CLAUDE.md §2).

import type { ExamSessionStatusCode } from "./api";
import { EXAM_SESSION_STATUS_TR } from "./api";

export { formatDate } from "../../lib/format";

/** Durum → Türkçe etiket (Taslak → Dağıtıldı → Onaylandı → Arşiv). */
export const STATUS_LABELS: Record<ExamSessionStatusCode, string> = EXAM_SESSION_STATUS_TR;

// M3 token'ları — ham renk yok (KS tailwind.config.js'te tanımlı adlar).
const STATUS_BADGE: Record<ExamSessionStatusCode, string> = {
  DRAFT: "bg-surface-container-high text-on-surface-variant",
  DISTRIBUTED: "bg-secondary-container text-on-secondary-container",
  APPROVED: "bg-primary-container text-on-primary-container",
  ARCHIVED: "bg-surface-container text-on-surface-variant",
};

/** Yaşam döngüsü rozeti — liste satırında ve detay başlığında ortak. */
export function StatusBadge({ status }: { status: ExamSessionStatusCode }) {
  return (
    <span className={`rounded-full px-3 py-1 text-label-small ${STATUS_BADGE[status]}`}>
      {STATUS_LABELS[status]}
    </span>
  );
}
