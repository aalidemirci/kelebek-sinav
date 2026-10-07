// Oturum Detayı → Yerleştirme Kuralları → "Kalıcı sınav tedbirleri" bölümü (07.10.2026).
//
// Kişiler → BEP ve tedbirler'deki tedbirli öğrencilerden BU OTURUMA girenleri gösterir.
// Yer tedbiri dağıtımda kendiliğinden uygulanır; öğrenciye bu panelden oturum kuralı
// girilirse o geçerli olur (`overridden`). Ek süre ve okuyucu/yazıcı desteği yerleşimi
// değiştirmez — yalnız idare özetine basılır (kullanıcı kararı), özet buradan da indirilir.
//
// Bildirim ve başlıklarda öğrenci adı geçmez; satır zaten gösteriyor.

import { useId } from "react";
import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";

import { ApiError } from "../../lib/api";
import type { SessionAccommodation } from "./api";
import { iepApi } from "./api";
import IdareOzetiDugmesi from "./IdareOzetiDugmesi";

function yerMetni(row: SessionAccommodation): string {
  if (row.seat_no === null) return "henüz dağıtılmadı";
  return `${row.room_name} · koltuk ${row.seat_no}`;
}

export default function OturumTedbirleriBolumu({
  session,
}: {
  session: { id: number; name: string; exam_date: string };
}) {
  const headingId = useId();
  const sorgu = useQuery({
    queryKey: ["session-accommodations", session.id],
    queryFn: () => iepApi.session(session.id),
    // Yer bilgisi yerleşimden okunur: takas/dağıtımdan sonra sekmeye dönülünce tazelensin.
    staleTime: 0,
  });

  if (sorgu.isError && sorgu.data === undefined) {
    return (
      <p role="alert" className="text-body-small text-error">
        {sorgu.error instanceof ApiError
          ? sorgu.error.message
          : "Kalıcı sınav tedbirleri okunamadı."}
      </p>
    );
  }
  const satirlar = sorgu.data?.rows ?? [];
  // Oturuma giren tedbirli öğrenci yoksa (ya da sorgu sürüyorsa) bölüm HİÇ çizilmez.
  if (satirlar.length === 0) return null;

  return (
    <section
      aria-labelledby={headingId}
      className="flex flex-col gap-3 rounded-shape-md border border-outline-variant p-3"
    >
      <h3 id={headingId} className="text-title-small text-on-surface">
        Kalıcı sınav tedbirleri
      </h3>
      <p className="text-body-small text-on-surface-variant">
        Bu sınava giren ve{" "}
        <Link to="/kisiler?tab=bep" className="font-medium underline underline-offset-2">
          Kişiler → BEP ve tedbirler
        </Link>{" "}
        listesinde tedbiri olan öğrenciler. Yer tedbiri dağıtımda kendiliğinden uygulanır; aşağıda
        öğrenciye kural eklerseniz bu oturumda o geçerli olur. Ek süre ile okuyucu ve yazıcı desteği
        salon evrakına basılmaz — gözetmene idare özetiyle siz bildirirsiniz.
      </p>
      <ul className="flex flex-col gap-2">
        {satirlar.map((row) => (
          <li
            key={row.student_id}
            className="flex flex-wrap items-baseline gap-x-3 gap-y-1 rounded-shape-sm bg-surface-container-low px-3 py-2 text-body-medium"
          >
            <span className="text-on-surface-variant">{row.student_number}</span>
            <span className="text-on-surface">{row.full_name}</span>
            <span className="text-body-small text-on-surface-variant">{row.class_label}</span>
            <span className="text-on-surface">{row.measures.join(" · ")}</span>
            <span className="text-body-small text-on-surface-variant">{yerMetni(row)}</span>
            {row.overridden && (
              <span className="rounded-shape-sm bg-secondary-container px-2 py-0.5 text-label-medium text-on-secondary-container">
                bu oturumda kural geçerli
              </span>
            )}
            {row.placement_applied === false && (
              // Tedbir dağıtımdan SONRA girildi (ya da düzen kuralları uygulamıyor):
              // yerleşim tedbiri yansıtmıyor — sessiz kalmasın.
              <span className="rounded-shape-sm bg-error-container px-2 py-0.5 text-label-medium text-on-error-container">
                yer tedbiri bu dağıtımda uygulanmadı — oturumu yeniden dağıtın
              </span>
            )}
          </li>
        ))}
      </ul>
      <IdareOzetiDugmesi session={session} />
    </section>
  );
}
