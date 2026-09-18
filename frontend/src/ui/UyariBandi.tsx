// Kalıcı, kapatılabilir UYARI bandı. Snackbar GEÇİCİ bildirimdir (4-6 sn,
// kuyruklu, tek satır): işlemi ENGELLEMEYEN ama okunması gereken uyarılar orada
// akıp kayboluyordu (değerlendirme §3.2 — takvim yerleştirme uyarıları kırmızı
// hata kuyruğunda görünüyor, idareci okuyamadan siliniyordu). Bu bant uyarıları
// ekranda TUTAR; kullanıcı "Kapat" diyene dek kalır.
//
// - `role="status"` (kibar canlı bölge): uyarı işlemi durdurmaz, ekran
//   okuyucuyu da bölmez. Sert ret/hata için `role="alert"` bandı ya da
//   `snackbar.error` kullanılır — bu bileşen hata kanalı DEĞİLDİR.
// - Ton `tertiary-container`: projede uyarının tonudur (hata `error-container`,
//   bilgi `secondary-container`); ham renk yok.
// - Boş listede hiçbir şey çizmez — çağıran koşul yazmak zorunda kalmaz.

import Button from "./Button";
import Icon from "./Icon";

interface UyariBandiProps {
  /** Bant başlığı; aynı zamanda canlı bölgenin erişilebilir adıdır. */
  title: string;
  /** Uyarı cümleleri (boşsa bant çizilmez). */
  messages: string[];
  /** "Kapat" — çağıran listeyi boşaltır. */
  onClose: () => void;
  /** Kapatma düğmesi etiketi (varsayılan "Kapat"). */
  closeLabel?: string;
  /** Dış sarmalayıcıya ek yerleşim sınıfı (örn. "mb-3"). */
  className?: string;
}

export default function UyariBandi({
  title,
  messages,
  onClose,
  closeLabel = "Kapat",
  className = "",
}: UyariBandiProps) {
  if (messages.length === 0) return null;
  return (
    <div
      role="status"
      aria-label={title}
      className={`flex items-start gap-3 rounded-shape-sm bg-tertiary-container px-4 py-3 text-on-tertiary-container ${className}`.trim()}
    >
      <Icon name="warning" size="lg" className="mt-0.5 shrink-0" />
      <div className="min-w-0 flex-1">
        <p className="text-label-large">{title}</p>
        {messages.length === 1 ? (
          <p className="mt-1 text-body-small">{messages[0]}</p>
        ) : (
          <ul className="mt-1 list-disc space-y-0.5 pl-4 text-body-small">
            {messages.map((message, i) => (
              <li key={`${i}-${message}`}>{message}</li>
            ))}
          </ul>
        )}
      </div>
      <Button variant="text" className="shrink-0" onClick={onClose}>
        {closeLabel}
      </Button>
    </div>
  );
}
