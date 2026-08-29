// OYS `lib/gradeLevels.ts`'ten uyarlandı (F4-D3/D5); yalnız kullanılan yüzey
// taşındı — OYS'nin sınıf çipi renk eşlemesi (`gradeColor`) burada çağıran
// bulamadığı için alınmadı.

// Öğrenim seviyeleri — UI seçicileri (onur kurulu üye seviyesi, md. 183/b).
// `GET /api/v1/grade-levels/` listeyi ÖĞRENCİ SİCİLİNDEN türetir; sicil boşken
// (kurulum öncesi) lise varsayılanını (9-12) döner. Program 9-12 değişmezi
// taşıdığından (import normalize + StudentSerializer kapıları) uç Hazırlık (0)
// ÖNERMEZ ve `prep_enabled` daima false'tur — `gradeLevelLabel`'ın 0 dalı yalnız
// gelecekte iki yazma kapısı da gevşetilirse anlam kazanır.

import { api } from "./api";

export interface GradeLevelOption {
  value: number;
  label: string;
}

export interface GradeLevelsResponse {
  levels: GradeLevelOption[];
  prep_enabled: boolean;
}

export const getGradeLevels = () => api.get<GradeLevelsResponse>("/grade-levels/");

// Üye/kayıt gösterim etiketi: 0 → "Hazırlık", n → "n. sınıf", null/undefined → "—".
export function gradeLevelLabel(level: number | null | undefined): string {
  if (level == null) return "—";
  return level === 0 ? "Hazırlık" : `${level}. sınıf`;
}
