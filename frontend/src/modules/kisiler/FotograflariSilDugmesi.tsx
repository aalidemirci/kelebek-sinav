// "Tüm fotoğrafları sil" (19.09.2026, kullanıcı kararı — KVKK). İki yerde
// durur ve davranışı TEK yerden gelir: Kişiler → Öğrenci fotoğrafları kartı ve
// Ayarlar → Güvenlik. Silme KATIDIR (geri alınamaz), bu yüzden onaydan geçer;
// sonrasında sayım ve yoklama planının fotoğraf sorguları tazelenir.

import { useMutation, useQueryClient } from "@tanstack/react-query";

import { ApiError } from "../../lib/api";
import { formatNumber } from "../../lib/format";
import Button from "../../ui/Button";
import { useConfirm } from "../../ui/ConfirmProvider";
import { useSnackbar } from "../../ui/SnackbarProvider";
import { okulApi } from "../okul/api";

export default function FotograflariSilDugmesi({
  disabled = false,
  onDeleted,
}: {
  /** Silinecek fotoğraf yoksa kapalı tutulur. */
  disabled?: boolean;
  onDeleted?: () => void;
}) {
  const snackbar = useSnackbar();
  const confirm = useConfirm();
  const qc = useQueryClient();

  const silme = useMutation({
    mutationFn: () => okulApi.deleteAllPhotos(),
    onSuccess: (r) => {
      snackbar.success(`${formatNumber(r.deleted)} fotoğraf kalıcı olarak silindi.`);
      onDeleted?.();
      void qc.invalidateQueries({ queryKey: ["student-photo-stats"] });
      void qc.invalidateQueries({ queryKey: ["exam-seating-photos"] });
    },
    onError: (e) => snackbar.error(e instanceof ApiError ? e.message : "Fotoğraflar silinemedi."),
  });

  return (
    <Button
      variant="text"
      icon="delete_forever"
      disabled={disabled || silme.isPending}
      onClick={() =>
        void confirm({
          title: "Bütün öğrenci fotoğrafları silinsin mi?",
          message:
            "Fotoğraflar kalıcı olarak silinir; salon evrakı ve yoklama planı fotoğrafsız " +
            "basılır. Gerekirse e-Okul'dan yeniden aktarabilirsiniz.",
          confirmLabel: "Sil",
        }).then((ok) => ok && silme.mutate())
      }
    >
      Tüm fotoğrafları sil
    </Button>
  );
}
