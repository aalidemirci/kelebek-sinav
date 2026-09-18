// Ayarlar → Güncelleme. Metin kullanıcı dilindedir (docs/sozluk.md §1): sürüm
// kaynağı "yayımlanan son sürüm", paket "kurulum dosyası"dır — "GitHub sürümü",
// "Release", "kurucu" ve özet algoritmasının adı yüzeye çıkmaz.

import { useCallback, useEffect, useState } from "react";

import { ApiError } from "../../lib/api";
import { saveBlob } from "../../lib/download";
import { formatNumber } from "../../lib/format";
import Button from "../../ui/Button";
import Card from "../../ui/Card";
import Icon from "../../ui/Icon";
import { SkeletonList } from "../../ui/Skeleton";
import { useSnackbar } from "../../ui/SnackbarProvider";
import { updateApi } from "./api";
import type { UpdateStatus } from "./api";

/** Dosya boyutu — Türkçe sayı biçimiyle (ondalık virgül): "41,5 MB". */
function formatBytes(bytes: number): string {
  if (bytes <= 0) return "";
  return `${formatNumber(Math.round((bytes / (1024 * 1024)) * 10) / 10)} MB`;
}

export default function UpdatePanel() {
  const [status, setStatus] = useState<UpdateStatus | null>(null);
  const [checking, setChecking] = useState(true);
  const [downloading, setDownloading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const snackbar = useSnackbar();

  const check = useCallback(async (force = false) => {
    setChecking(true);
    setError(null);
    try {
      setStatus(await updateApi.check(force));
    } catch (e) {
      setError(
        e instanceof ApiError
          ? e.message
          : "Güncelleme denetlenemedi. İnternet bağlantısını kontrol edin.",
      );
    } finally {
      setChecking(false);
    }
  }, []);

  useEffect(() => {
    void check();
  }, [check]);

  const download = async () => {
    if (!status) return;
    setDownloading(true);
    setError(null);
    try {
      const blob = await updateApi.downloadInstaller();
      saveBlob(blob, status.installer_name || `kelebek-sinav-${status.latest_version}.exe`);
      snackbar.success("Kurulum dosyası doğrulanarak indirildi.");
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Güncelleme dosyası indirilemedi.");
    } finally {
      setDownloading(false);
    }
  };

  return (
    <div className="space-y-4">
      <Card elevation={1} className="p-6">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div>
            <p className="text-title-medium text-on-surface">Uygulama güncellemesi</p>
            <p className="mt-1 text-body-medium text-on-surface-variant">
              Yayımlanan son sürüm denetlenir; programın internete çıkan tek isteği budur ve kişisel
              veri taşımaz. Kurulum dosyası, bütünlüğü doğrulanmadan indirmeye sunulmaz.
            </p>
          </div>
          <Button
            variant="outlined"
            icon="refresh"
            disabled={checking || downloading}
            onClick={() => void check(true)}
          >
            {checking ? "Denetleniyor…" : "Şimdi denetle"}
          </Button>
        </div>

        {error && (
          <div
            role="alert"
            className="mt-4 flex items-start gap-2 rounded-shape-sm bg-error-container px-4 py-3 text-body-medium text-on-error-container"
          >
            <Icon name="error" />
            <span>{error}</span>
          </div>
        )}

        {/* İlk denetim sürerken kart boş kalmasın (diğer panellerle aynı kalıp). */}
        {checking && !status && !error && <SkeletonList rows={2} className="mt-5" />}

        {status && (
          <div className="mt-5 grid gap-3 sm:grid-cols-2">
            <div className="rounded-shape-md bg-surface-container p-4">
              <p className="text-label-medium text-on-surface-variant">Kurulu sürüm</p>
              <p className="mt-1 text-title-large text-on-surface">{status.current_version}</p>
            </div>
            <div className="rounded-shape-md bg-surface-container p-4">
              <p className="text-label-medium text-on-surface-variant">Yayımlanan son sürüm</p>
              <p className="mt-1 text-title-large text-on-surface">{status.latest_version}</p>
            </div>
          </div>
        )}

        {status && !status.update_available && (
          <p className="mt-4 flex items-center gap-2 text-body-medium text-primary">
            <Icon name="check_circle" />
            Uygulama güncel.
          </p>
        )}

        {status?.update_available && (
          <div className="mt-4 rounded-shape-md border border-primary/30 bg-primary-container p-4 text-on-primary-container">
            <p className="text-title-small">Yeni sürüm hazır: {status.latest_version}</p>
            {status.installer_size > 0 && (
              <p className="mt-1 text-body-small">
                Windows kurulum dosyası: {formatBytes(status.installer_size)}
              </p>
            )}
            <p className="mt-2 text-body-small">
              İndirme tamamlanınca programı kapatın ve indirilen kurulum dosyasını çalıştırın.
              Verileriniz kurulum klasörünün dışında tutulduğu için korunur.
            </p>
            <div className="mt-3 flex flex-wrap gap-2">
              <Button
                icon="download"
                disabled={!status.can_download || downloading}
                onClick={() => void download()}
              >
                {downloading ? "İndiriliyor…" : "Doğrula ve indir"}
              </Button>
              {!status.can_download && (
                <span className="self-center text-label-small">
                  Bu sürümde Windows kurulum dosyası bulunmuyor.
                </span>
              )}
            </div>
          </div>
        )}
      </Card>
    </div>
  );
}
