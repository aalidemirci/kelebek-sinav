// Okul çekirdeği API istemcisi (F0 iskeleti).
// F1'de okul künyesi, ders yılı, kişiler ve içe aktarma uçları buraya gelir
// (DD `modules/okul/api.ts` kalıbı); F0'da yalnız kurulum kapısının ihtiyacı var.

import { api } from "../../lib/api";

/** `GET /setup/status/` yanıtı — backend `apps/okul/views.py` ile birebir. */
export interface SetupStatus {
  setup_completed: boolean;
  school_name: string;
  has_active_school_year: boolean;
  student_count: number;
  personnel_count: number;
}

export const okulApi = {
  getSetupStatus: () => api.get<SetupStatus>("/setup/status/"),
};
