// "Yeniden dağıt" — DAĞITILDI oturumda yerleşimi beğenmeyen (ya da dağıtımdan
// sonra yerleştirme kuralı ekleyen) idarecinin yolu. Backend `distribute` ucu
// TASLAK ve DAĞITILDI durumda çalışır: önceki yerleşim ve gözetmen
// görevlendirmeleri silinir, yenisi yazılır (`services.distribute_session`).
//
// 18.09.2026 değerlendirmesi: kılavuz "Yeniden Dağıt" düğmesine yolluyor ama
// düğme yoktu — tek yol "Taslağa al" + sihirbazın sonuna kadar yürümekti.
//
// Sonuç ve backend UYARILARI diyalogda kalır (snackbar'da akıp gitmez; emsal
// OturumKopyalaDialog "Kopyalama sonucu"): gözetmenlerin sıfırlandığı, salon
// doluluk farkı, uygulanamayan kural gibi bilgiler okunmadan kaybolmasın.

import { useState } from "react";
import { useMutation } from "@tanstack/react-query";

import { ApiError } from "../../lib/api";
import Button from "../../ui/Button";
import Dialog from "../../ui/Dialog";
import Icon from "../../ui/Icon";
import { useSnackbar } from "../../ui/SnackbarProvider";
import type { DistributeResult, LayoutModeCode } from "./api";
import { examSessionApi, usesDistributionNumber } from "./api";
import DagitimSecenekleri, {
  BOS_DAGITIM_SECENEKLERI,
  DagitimSonucu,
  dagitimCumlesi,
  dagitimGovdesi,
} from "./DagitimSecenekleri";

export default function YenidenDagitDialog({
  sessionId,
  layoutMode,
  onClose,
  onDistributed,
}: {
  sessionId: number;
  layoutMode: LayoutModeCode;
  onClose: () => void;
  /** Dağıtım yazıldı — oturum, yerleşim ve gözetmen sorguları tazelenmeli. */
  onDistributed: () => void;
}) {
  const snackbar = useSnackbar();
  // "Kendi dersliğinde" düzeninde karıştırma yoktur: numara ve katı dağıtım sonucu
  // değiştirmez (sihirbazın Dağıt adımıyla aynı kural) — seçenekler gösterilmez.
  const numarali = usesDistributionNumber(layoutMode);
  const [options, setOptions] = useState(BOS_DAGITIM_SECENEKLERI);
  const [result, setResult] = useState<DistributeResult | null>(null);

  const distribute = useMutation({
    mutationFn: () => examSessionApi.distribute(sessionId, dagitimGovdesi(options)),
    onSuccess: (sonuc) => {
      setResult(sonuc);
      snackbar.success(dagitimCumlesi("Yeniden dağıtıldı", sonuc, numarali));
      onDistributed();
    },
    onError: (e) => snackbar.error(e instanceof ApiError ? e.message : "Yeniden dağıtılamadı."),
  });

  return (
    <Dialog
      open
      onClose={onClose}
      title={result ? "Yeniden dağıtım sonucu" : "Yeniden dağıtılsın mı?"}
      actions={
        result ? (
          <Button variant="text" onClick={onClose}>
            Kapat
          </Button>
        ) : (
          <>
            <Button variant="text" onClick={onClose}>
              Vazgeç
            </Button>
            <Button
              icon="shuffle"
              onClick={() => distribute.mutate()}
              disabled={distribute.isPending}
            >
              {distribute.isPending ? "Dağıtılıyor…" : "Yeniden dağıt"}
            </Button>
          </>
        )
      }
    >
      {result ? (
        <DagitimSonucu result={result} numarali={numarali} />
      ) : (
        <div className="flex flex-col gap-4">
          <p className="flex items-start gap-2 rounded-shape-sm bg-error-container px-3 py-2 text-on-error-container">
            <Icon name="warning" size="lg" className="shrink-0" />
            <span>
              Elle yapılan koltuk takasları ve gözetmen görevlendirmeleri sıfırlanır. Daha önce
              basılmış evrak ve üretilmiş kitapçıklar eski yerleşime göre kalır; yeniden üretmeniz
              gerekir.
            </span>
          </p>
          <p>Ders, şube ve salon seçimi, yerleştirme kuralları ve soru dosyaları korunur.</p>
          {!numarali ? (
            <p>
              Bu oturum “Kendi dersliğinde” düzenindedir: her şube kendi şube dersliğine okul
              numarası sırasıyla yeniden yerleştirilir. Öğrenci listesi ya da şube derslikleri
              değiştiyse yerleşim ona göre güncellenir.
            </p>
          ) : (
            <DagitimSecenekleri
              deger={options}
              onChange={setOptions}
              seedLabel="Dağıtım numarası (boş bırakılırsa yeni rastgele)"
              className="flex flex-col gap-3"
            />
          )}
        </div>
      )}
    </Dialog>
  );
}
