// Önerilen sınav haftalarının dayanağı (19.09.2026) — yeni takvim ve tarih
// düzenleme pencerelerinde, tarih alanlarının altında. Bakanlığın o yıl ilan
// ettiği haftalar (ör. 10.09.2026 tarihli yazı), ilan yoksa Yönetmelik kuralı.
// Bilgi amaçlıdır: tarihler idarecinin kararıdır, hiçbir yerleştirme buna göre
// reddedilmez (kullanıcı kararı — "katı bir kısıtlama olmasın").

import { formatDate } from "../../lib/format";
import Button from "../../ui/Button";
import type { DefaultWindow } from "./api";

export default function PencereOnerisi({
  pencere,
  onApply,
}: {
  pencere: DefaultWindow;
  /** Verilirse "Bu tarihleri kullan" düğmesi çizilir. */
  onApply?: () => void;
}) {
  return (
    <div className="flex flex-wrap items-center gap-2 text-body-small text-on-surface-variant">
      <p>
        {pencere.official ? "Bakanlığın ilan ettiği sınav haftaları" : "Yönetmeliğe göre önerilen"}:{" "}
        <strong className="text-on-surface">
          {formatDate(pencere.start_date)} – {formatDate(pencere.end_date)}
        </strong>{" "}
        ({pencere.source}). Tarihleri okulunuzun planına göre değiştirebilirsiniz.
      </p>
      {onApply ? (
        <Button variant="text" icon="event_available" onClick={onApply}>
          Bu tarihleri kullan
        </Button>
      ) : null}
    </div>
  );
}
