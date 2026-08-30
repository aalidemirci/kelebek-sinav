import { api } from "../../lib/api";

export interface ArsivAdayi {
  id: number;
  name: string;
  exam_date: string; // ISO (yyyy-mm-dd)
}

export interface ArsivAdayListesi {
  retention_days: number;
  candidates: ArsivAdayi[];
}

export const bakimApi = {
  arsivAdaylari: () => api.get<ArsivAdayListesi>("/exam-sessions/archive-anonymization/"),
  anonimlestir: (sessionIds: number[]) =>
    api.post<{ anonymized: number[] }>("/exam-sessions/archive-anonymization/", {
      session_ids: sessionIds,
    }),
};
