// Güvenlik sekmesi: öğrenci fotoğraflarının nerede durduğu + toplu silme
// (19.09.2026, kullanıcı kararı: "Ayarlar'da 'tüm fotoğrafları sil' düğmesi
// olur"). Aktarım Kişiler ekranındadır; burada yalnız KVKK yüzü durur — sayım,
// saklama bilgisi ve silme. Silme davranışı `FotograflariSilDugmesi`nden gelir.

import { useQuery } from "@tanstack/react-query";

import { formatNumber } from "../../lib/format";
import Card from "../../ui/Card";
import Icon from "../../ui/Icon";
import FotograflariSilDugmesi from "../kisiler/FotograflariSilDugmesi";
import { okulApi } from "../okul/api";

export default function OgrenciFotograflari() {
  const stats = useQuery({
    queryKey: ["student-photo-stats"],
    queryFn: () => okulApi.photoStats(),
    retry: false,
  });
  const adet = stats.data?.with_photo ?? 0;

  return (
    <Card className="p-6">
      <div className="flex items-start gap-3">
        <Icon name="photo_camera" className="mt-0.5 text-primary" />
        <div className="min-w-0 flex-1">
          <h2 className="text-title-large text-on-surface">Öğrenci fotoğrafları</h2>
          <p className="mt-2 text-body-medium text-on-surface-variant">
            e-Okul'dan aktarılan fotoğraflar yalnız bu bilgisayardaki veritabanında durur ve yedeğe
            girer; uygulama parolası kuruluysa şifrelidir. Okuldan ayrılan ya da silinen öğrencinin
            fotoğrafı kendiliğinden silinir. Aktarım Kişiler ekranındadır.
          </p>
          {stats.data && (
            <p className="mt-2 text-body-small text-on-surface-variant">
              {adet > 0
                ? `${formatNumber(adet)} öğrencinin fotoğrafı kayıtlı.`
                : "Kayıtlı fotoğraf yok."}
            </p>
          )}
          <div className="mt-4">
            <FotograflariSilDugmesi disabled={adet === 0} />
          </div>
        </div>
      </div>
    </Card>
  );
}
