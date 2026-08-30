import { useEffect, useState } from "react";

import { saveBlob } from "../../lib/download";
import Button from "../../ui/Button";
import Icon from "../../ui/Icon";
import { useSnackbar } from "../../ui/SnackbarProvider";
import { updateApi } from "./api";
import type { UpdateStatus } from "./api";

const DISMISSED_KEY = "kelebek-sinav-dismissed-update";

export default function UpdateBanner() {
  const [update, setUpdate] = useState<UpdateStatus | null>(null);
  const [busy, setBusy] = useState(false);
  const snackbar = useSnackbar();

  useEffect(() => {
    let cancelled = false;
    updateApi
      .check()
      .then((status) => {
        if (
          !cancelled &&
          status.update_available &&
          window.localStorage.getItem(DISMISSED_KEY) !== status.latest_version
        ) {
          setUpdate(status);
        }
      })
      .catch(() => undefined); // çevrimdışı açılışta sessiz; Ayarlar'da elle denetlenebilir
    return () => {
      cancelled = true;
    };
  }, []);

  if (!update) return null;

  const download = async () => {
    setBusy(true);
    try {
      const blob = await updateApi.downloadInstaller();
      saveBlob(blob, update.installer_name || `kelebek-sinav-${update.latest_version}.exe`);
      snackbar.success("Güncelleme indirildi. Programı kapatıp kurulum dosyasını çalıştırın.");
    } catch {
      snackbar.error("Güncelleme indirilemedi. Ayarlar → Güncelleme bölümünden yeniden deneyin.");
    } finally {
      setBusy(false);
    }
  };

  const dismiss = () => {
    window.localStorage.setItem(DISMISSED_KEY, update.latest_version);
    setUpdate(null);
  };

  return (
    <div
      role="status"
      className="mb-4 flex flex-wrap items-center gap-3 rounded-shape-md border border-primary/30 bg-primary-container px-4 py-3 text-on-primary-container"
    >
      <Icon name="system_update" className="shrink-0" />
      <p className="min-w-48 flex-1 text-body-medium">
        <span className="font-medium">Kelebek Sınav {update.latest_version} hazır.</span> Çalışan
        sürüm: {update.current_version}.
      </p>
      <div className="flex flex-wrap gap-1">
        {update.can_download && (
          <Button variant="tonal" icon="download" disabled={busy} onClick={() => void download()}>
            {busy ? "İndiriliyor…" : "Güncellemeyi indir"}
          </Button>
        )}
        <Button variant="text" onClick={dismiss}>
          Daha sonra
        </Button>
      </div>
    </div>
  );
}
