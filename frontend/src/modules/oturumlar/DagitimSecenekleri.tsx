// Dağıtım seçenekleri — sihirbazın "Dağıt" adımı ile DAĞITILDI oturumdaki
// "Yeniden dağıt" diyaloğu AYNI iki alanı gösterir: dağıtım numarası + katı
// dağıtım. Metinler docs/sozluk.md'ye bağlıdır ("seed" → "dağıtım numarası";
// "katı mod (1. halka…)" → "Katı dağıtım: yan, ön ve arka komşuluk da kesinlikle
// yasak"); tek yerde durur ki iki ekran zamanla ayrışmasın. Dağıtımın SONUCU da
// (`DagitimSonucu`) aynı iki ekranda gösterilir: backend uyarıları — uygulanamayan
// yerleştirme kuralı, sıfırlanan gözetmenler, salon doluluk farkı — okunmadan
// kaybolmasın diye snackbar'a değil kalıcı bir bloğa yazılır.

import Icon from "../../ui/Icon";
import TextField from "../../ui/TextField";
import type { DistributeResult } from "./api";

export interface DagitimSecenekleriDegeri {
  /** Metin alanının değeri — boş = rastgele numara. */
  seed: string;
  strict: boolean;
}

export const BOS_DAGITIM_SECENEKLERI: DagitimSecenekleriDegeri = { seed: "", strict: false };

/** Form değerini `distribute` ucunun gövdesine çevirir (boş numara gönderilmez). */
export function dagitimGovdesi(deger: DagitimSecenekleriDegeri): {
  seed?: number;
  strict: boolean;
} {
  return { seed: deger.seed === "" ? undefined : Number(deger.seed), strict: deger.strict };
}

/**
 * Snackbar cümlesi: "<başlangıç>: 30 öğrenci yerleşti (dağıtım numarası 42)."
 * `numarali` = `usesDistributionNumber(layout_mode)` — "Kendi dersliğinde"
 * düzeninde numara yazılmaz.
 */
export function dagitimCumlesi(
  baslangic: string,
  result: DistributeResult,
  numarali: boolean,
): string {
  const numara = numarali ? ` (dağıtım numarası ${result.seed})` : "";
  return `${baslangic}: ${result.placed} öğrenci yerleşti${numara}.`;
}

/** Dağıtım sonucu: yerleşen sayısı + dağıtım numarası + kural denetimi + uyarılar. */
export function DagitimSonucu({
  result,
  numarali = true,
}: {
  result: DistributeResult;
  numarali?: boolean;
}) {
  return (
    <div className="flex flex-col gap-3 text-body-medium text-on-surface">
      <p>
        {result.placed} öğrenci yerleşti.
        {numarali && (
          <>
            {" "}
            Dağıtım numarası: <span className="font-medium">{result.seed}</span>
          </>
        )}
      </p>
      {result.report.is_valid ? (
        <p className="flex items-center gap-2">
          <Icon name="check_circle" size="lg" className="text-primary" />
          Kural ihlali yok — oturum onaylanabilir.
        </p>
      ) : (
        <p role="alert" className="flex items-center gap-2 text-error">
          <Icon name="error" size="lg" />
          {result.report.hard_violations.length} kural ihlali var — onaylanamaz.
          {numarali && " Farklı bir dağıtım numarasıyla yeniden dağıtın."}
        </p>
      )}
      {result.warnings.length > 0 && (
        <div className="rounded-shape-sm bg-surface-container p-3">
          <p className="text-title-small text-on-surface">Uyarılar</p>
          <ul className="mt-1 flex flex-col gap-1 text-body-small">
            {result.warnings.map((w) => (
              <li key={w} className="flex items-start gap-1">
                <Icon name="warning" size="sm" className="mt-0.5 shrink-0 text-error" />
                <span>{w}</span>
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}

export default function DagitimSecenekleri({
  deger,
  onChange,
  seedLabel,
  className = "grid gap-3 sm:grid-cols-2",
}: {
  deger: DagitimSecenekleriDegeri;
  onChange: (deger: DagitimSecenekleriDegeri) => void;
  /** Numara alanının etiketi — boş bırakmanın sonucu ekrana göre değişir. */
  seedLabel: string;
  className?: string;
}) {
  return (
    <div className={className}>
      <TextField
        label={seedLabel}
        type="number"
        min={1}
        max={999999}
        value={deger.seed}
        onChange={(e) => onChange({ ...deger, seed: e.target.value })}
        // Sözlük: "seed" yalnız ilk geçtiği yardım metninde, parantez içinde bir kez.
        helperText="Dağıtım numarası (seed), karıştırmanın başlangıç değeridir: aynı numara her zaman aynı yerleşimi üretir. Kullanılan numara Yerleşim sekmesinde gösterilir; bir yerleşimi yeniden üretmek için o numarayı girin."
      />
      <label className="flex min-h-9 cursor-pointer items-start gap-3 text-body-medium text-on-surface">
        <input
          type="checkbox"
          checked={deger.strict}
          onChange={(e) => onChange({ ...deger, strict: e.target.checked })}
          className="mt-0.5 h-5 w-5 shrink-0 accent-primary"
        />
        <span>Katı dağıtım: yan, ön ve arka komşuluk da kesinlikle yasak</span>
      </label>
    </div>
  );
}
