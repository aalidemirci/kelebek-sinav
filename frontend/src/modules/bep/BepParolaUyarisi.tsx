// BEP parola uyarısı (20.09.2026). BEP bilgisi özel nitelikli veriye işaret eder
// (KVKK md. 6). Uygulama parolası ZORUNLU DEĞİLDİR (kullanıcı kararı) ama
// kapalıyken kayıt bu bilgisayarda ve yedeklerde şifresiz durur — arayüz bunu
// BEP verisinin göründüğü iki yerde de söyler: Kişiler → BEP sekmesi ve oturumun
// bireysel soru dosyaları bölümü. Metin TEK yerde durur.
//
// Parola açıksa, durum henüz okunmadıysa ya da OKUNAMADIYSA hiçbir şey çizilmez:
// uyarı bir öneridir, okunamayan durum için hata bandı basmak ekranı kirletir.

import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";

import Icon from "../../ui/Icon";
import { guvenlikApi } from "../guvenlik/api";

export default function BepParolaUyarisi({ className = "" }: { className?: string }) {
  const durum = useQuery({
    queryKey: ["security-status"],
    queryFn: () => guvenlikApi.durum(),
    retry: false,
    // Parola Ayarlar'da az önce kurulmuş olabilir ve o ekran bu önbelleği
    // tazelemez: bant her açılışta durumu YENİDEN sorar, eski yanıtı göstermez
    // (önbellekten çizilseydi parola kurulduktan sonra bir an yanıp sönerdi).
    staleTime: 0,
    gcTime: 0,
  });

  if (durum.data?.password_set !== false) return null;

  return (
    <div
      role="status"
      aria-label="Uygulama parolası kapalı"
      className={`flex items-start gap-3 rounded-shape-sm bg-tertiary-container px-4 py-3 text-body-small text-on-tertiary-container ${className}`.trim()}
    >
      <Icon name="lock_open" size="lg" className="mt-0.5 shrink-0" />
      <p>
        <strong>Uygulama parolası kapalı:</strong> BEP bilgisi bu bilgisayarda ve yedeklerde
        şifresiz saklanıyor. Bu bilgi özel nitelikli kişisel veridir (KVKK md. 6);{" "}
        <Link
          to="/ayarlar?tab=guvenlik"
          className="font-medium underline underline-offset-2 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary"
        >
          Ayarlar → Güvenlik
        </Link>{" "}
        bölümünden parola koymanız önerilir.
      </p>
    </div>
  );
}
