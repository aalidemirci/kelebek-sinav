import { useState } from "react";

import { api } from "../../lib/api";
import { saveBlob } from "../../lib/download";
import Button from "../../ui/Button";
import Card from "../../ui/Card";
import Icon from "../../ui/Icon";
import { useSnackbar } from "../../ui/SnackbarProvider";

function hataMesaji(error: unknown): string {
  return error instanceof Error ? error.message : "Şifreli yedek oluşturulamadı.";
}

function yedekDosyaAdi(): string {
  const timestamp = new Date().toISOString().replace("T", "-").slice(0, 19).replace(/:/g, "");
  return `disiplin-defteri-yedek-${timestamp}.ddbak`;
}

export default function SifreliYedekleme({ parolaKurulu }: { parolaKurulu: boolean }) {
  const snackbar = useSnackbar();
  const [calisiyor, setCalisiyor] = useState(false);

  async function indir() {
    setCalisiyor(true);
    try {
      const yedek = await api.postBlob("/backups/encrypted/");
      saveBlob(yedek, yedekDosyaAdi());
      snackbar.success("Şifreli veritabanı yedeği indirildi.");
    } catch (error) {
      snackbar.error(hataMesaji(error));
    } finally {
      setCalisiyor(false);
    }
  }

  return (
    <Card className="p-6">
      <div className="flex items-start gap-3">
        <Icon name="backup" className="mt-0.5 text-primary" />
        <div className="min-w-0 flex-1">
          <h2 className="text-title-large text-on-surface">Şifreli veritabanı yedeği</h2>
          <p className="mt-2 text-body-medium text-on-surface-variant">
            Veritabanının tutarlı bir görüntüsü cihazda X25519 ve AES-256-GCM ile şifrelenir,
            ardından <span className="font-mono">.ddbak</span> dosyası olarak indirilir. Düz metin
            yedek veya bulut bağlantısı oluşturulmaz.
          </p>
          <p className="mt-2 text-body-small text-on-surface-variant">
            İndirdiğiniz dosyayı USB belleğe, NAS'a veya tercih ettiğiniz bulut klasörüne kendiniz
            kopyalayın. Yedeği açmak için uygulama parolanızı ya da kurtarma anahtarınızı güvenli
            biçimde saklayın.
          </p>
          {!parolaKurulu && (
            <p className="mt-3 rounded-shape-md bg-error-container p-3 text-body-small text-on-error-container">
              Şifreli yedek oluşturabilmek için önce uygulama parolası kurmalısınız.
            </p>
          )}
          <div className="mt-5">
            <Button icon="download" onClick={indir} disabled={calisiyor || !parolaKurulu}>
              {calisiyor ? "Şifreli yedek hazırlanıyor…" : "Şifreli yedeği indir"}
            </Button>
          </div>
        </div>
      </div>
    </Card>
  );
}
