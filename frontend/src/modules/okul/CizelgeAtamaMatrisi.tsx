// Çizelge ataması — okul türü + hazırlık seçimine göre yürürlükteki MEB çizelgesini
// gösterir ve seviye bazında özelleştirmeye (kademeli dönüşüm, çok programlı okul,
// bölümlü GSL) izin verir. Kurulum sihirbazı ve Ayarlar → Okul bilgileri AYNI
// bileşeni kullanır; plan backend'den önizlemeyle gelir (`GET /courses/catalog-status/`
// + kaydedilmemiş seçim), yürürlük/kademeli kuralı istemcide TEKRARLANMAZ.
//
// Değer sözleşmesi (`SchoolConfig.level_programs`): boş nesne = varsayılan;
// yazılan seviye için yalnız listedeki program anahtarları uygulanır.

import { useEffect, useMemo, useState } from "react";

import { ApiError } from "../../lib/api";
import Button from "../../ui/Button";
import Card from "../../ui/Card";
import Icon from "../../ui/Icon";
import { SkeletonList } from "../../ui/Skeleton";
import { derslerApi } from "../dersler/api";
import type { CatalogProgram, CatalogStatus } from "../dersler/api";
import type { LevelPrograms, SchoolType } from "./api";

interface Props {
  schoolType: SchoolType;
  hasPrepClass: boolean;
  value: LevelPrograms;
  onChange: (next: LevelPrograms) => void;
}

/** Seviye satırlarının hepsi aynı program kümesini mi kullanıyor? */
function tekTip(status: CatalogStatus): string[] | null {
  const kumeler = new Set(
    status.levels.map((lv) =>
      lv.programs
        .map((p) => p.key)
        .sort()
        .join("|"),
    ),
  );
  return kumeler.size === 1 && status.levels.length > 0
    ? status.levels[0].programs.map((p) => p.name)
    : null;
}

export default function CizelgeAtamaMatrisi({ schoolType, hasPrepClass, value, onChange }: Props) {
  const [status, setStatus] = useState<CatalogStatus | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [tumProgramlar, setTumProgramlar] = useState(false);
  const valueKey = JSON.stringify(value);
  const custom = Object.keys(value).length > 0;

  useEffect(() => {
    let iptal = false;
    setLoading(true);
    derslerApi
      .getCatalogStatus({
        schoolType,
        hasPrepClass,
        levelPrograms: JSON.parse(valueKey) as LevelPrograms,
      })
      .then((s) => {
        if (iptal) return;
        setStatus(s);
        setError(null);
      })
      .catch((e: unknown) => {
        if (!iptal) setError(e instanceof ApiError ? e.message : "Çizelge planı yüklenemedi.");
      })
      .finally(() => {
        if (!iptal) setLoading(false);
      });
    return () => {
      iptal = true;
    };
  }, [schoolType, hasPrepClass, valueKey]);

  // Matriste gösterilen programlar: okul türüne ait olanlar; istenirse hepsi
  // (kademeli tür dönüşümünde başka türün çizelgesi seçilir).
  const programlar = useMemo(() => {
    if (!status) return [] as CatalogProgram[];
    const turun = new Set(
      status.school_types.find((t) => t.value === schoolType)?.program_keys ?? [],
    );
    const secili = new Set(Object.values(value).flat());
    return status.programs.filter((p) => tumProgramlar || turun.has(p.key) || secili.has(p.key));
  }, [status, schoolType, value, tumProgramlar]);

  const seviyeListesi = (level: number): string[] => {
    const acik = value[String(level)];
    if (acik) return acik;
    return status?.levels.find((lv) => lv.level === level)?.default_program_keys ?? [];
  };

  const degistir = (level: number, key: string, checked: boolean) => {
    const mevcut = seviyeListesi(level);
    const sonraki = checked ? [...mevcut, key] : mevcut.filter((k) => k !== key);
    onChange({ ...value, [String(level)]: Array.from(new Set(sonraki)) });
  };

  const ozellestir = () => {
    if (!status) return;
    // Her seviye varsayılanının açık kopyasıyla başlar; idareci buradan oynar.
    const acik: LevelPrograms = {};
    for (const lv of status.levels) acik[String(lv.level)] = [...lv.default_program_keys];
    onChange(acik);
  };

  if (loading && !status) return <SkeletonList rows={2} />;
  if (error) {
    return (
      <div
        role="alert"
        className="flex items-start gap-2 rounded-shape-sm bg-error-container px-4 py-3 text-body-medium text-on-error-container"
      >
        <Icon name="error" size="lg" />
        <span>{error}</span>
      </div>
    );
  }
  if (!status) return null;

  const ortak = !custom ? tekTip(status) : null;

  return (
    <Card elevation={0} className="border border-outline-variant p-4">
      <p className="flex items-center gap-2 text-title-small text-on-surface">
        <Icon name="fact_check" />
        Yürürlükteki ders çizelgesi — {status.year_label}
      </p>

      {!status.data_available && (
        <p className="mt-2 rounded-shape-sm bg-tertiary-container px-3 py-2 text-body-small text-on-tertiary-container">
          Bu okul türü için çizelge verisi bu sürümde yok: ders havuzu boş başlar, dersler
          &quot;Ders havuzu&quot; ekranından elle eklenir. Aşağıdaki listeden başka bir türün
          çizelgesini de uygulayabilirsiniz.
        </p>
      )}

      {ortak ? (
        <p className="mt-2 text-body-medium text-on-surface-variant">
          Tüm seviyeler: <span className="text-on-surface">{ortak.join(" + ")}</span>
        </p>
      ) : (
        <ul className="mt-2 space-y-1 text-body-medium text-on-surface-variant">
          {status.levels.map((lv) => (
            <li key={lv.level}>
              <span className="text-on-surface">{lv.label}:</span>{" "}
              {lv.programs.length > 0
                ? lv.programs.map((p) => p.name).join(" + ")
                : "çizelge atanmamış"}
              {lv.explicit && (
                <span className="ml-2 rounded-shape-xl bg-secondary-container px-2 py-0.5 text-label-small text-on-secondary-container">
                  özel
                </span>
              )}
            </li>
          ))}
        </ul>
      )}

      {status.warnings.length > 0 && (
        <ul className="mt-2 space-y-1">
          {status.warnings.map((w) => (
            <li
              key={w}
              className="flex items-start gap-2 rounded-shape-sm bg-tertiary-container px-3 py-2 text-body-small text-on-tertiary-container"
            >
              <Icon name="warning" size="sm" />
              <span>{w}</span>
            </li>
          ))}
        </ul>
      )}

      <div className="mt-3 flex flex-wrap items-center gap-2">
        {custom ? (
          <Button variant="text" icon="restart_alt" onClick={() => onChange({})}>
            Varsayılana dön
          </Button>
        ) : (
          <Button variant="tonal" icon="tune" onClick={ozellestir}>
            Seviye bazında özelleştir
          </Button>
        )}
        <span className="text-body-small text-on-surface-variant">
          Kademeli dönüşümde (ör. Anadolu Lisesi → Fen Lisesi) yeni tür 9. sınıftan başlar, üst
          sınıflar eski çizelgede kalır; çok programlı okulda aynı seviyeye birden çok çizelge
          işaretlenir.
        </span>
      </div>

      {custom && (
        <div className="mt-3 overflow-x-auto">
          <label className="mb-2 flex items-center gap-2 text-body-small text-on-surface-variant">
            <input
              type="checkbox"
              checked={tumProgramlar}
              onChange={(e) => setTumProgramlar(e.target.checked)}
            />
            Diğer okul türlerinin çizelgelerini de göster
          </label>
          <table className="w-full text-left text-body-small">
            <thead>
              <tr className="border-b border-outline-variant text-label-medium text-on-surface-variant">
                <th className="py-2 pr-3">Çizelge programı</th>
                {status.levels.map((lv) => (
                  <th key={lv.level} className="px-2 py-2 text-center">
                    {lv.label}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {programlar.map((p) => (
                <tr key={p.key} className="border-b border-outline-variant/50 last:border-b-0">
                  <td className="py-2 pr-3">
                    <span className="text-on-surface">{p.name}</span>
                    <span className="block text-label-small text-on-surface-variant">
                      {p.school_type_label}
                      {p.department ? ` · ${p.department}` : ""}
                      {p.has_prep ? " · hazırlıklı" : ""}
                      {p.source ? ` · ${p.source.split(" — ")[0]}` : ""}
                    </span>
                  </td>
                  {status.levels.map((lv) => (
                    <td key={lv.level} className="px-2 py-2 text-center">
                      <input
                        type="checkbox"
                        aria-label={`${p.name} — ${lv.label}`}
                        checked={seviyeListesi(lv.level).includes(p.key)}
                        onChange={(e) => degistir(lv.level, p.key, e.target.checked)}
                      />
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </Card>
  );
}
