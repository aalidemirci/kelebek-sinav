import { api } from "../../lib/api";

export interface UpdateStatus {
  current_version: string;
  latest_version: string;
  update_available: boolean;
  release_name: string;
  published_at: string;
  release_url: string;
  /**
   * Programın çalıştığı platform. Uygulama içi indirme yalnız Windows kurulum
   * dosyasını bilir; "linux"ta `can_download` hep false'tur ve arayüz paketle
   * güncellemeye yönlendirir. Eski backend alanı göndermez → Windows sayılır.
   */
  platform?: "windows" | "linux";
  can_download: boolean;
  installer_name: string;
  installer_size: number;
}

export const updateApi = {
  check: (force = false) => api.get<UpdateStatus>(`/updates/latest/${force ? "?force=1" : ""}`),
  downloadInstaller: () => api.getBlob("/updates/latest/installer/"),
};
