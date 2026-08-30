import { api } from "../../lib/api";

export interface UpdateStatus {
  current_version: string;
  latest_version: string;
  update_available: boolean;
  release_name: string;
  published_at: string;
  release_url: string;
  can_download: boolean;
  installer_name: string;
  installer_size: number;
}

export const updateApi = {
  check: (force = false) => api.get<UpdateStatus>(`/updates/latest/${force ? "?force=1" : ""}`),
  downloadInstaller: () => api.getBlob("/updates/latest/installer/"),
};
