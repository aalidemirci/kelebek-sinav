// Sınav süreç kalemi kataloğu yönetimi Dialog'u (F6) — OYS ADR-0044 FAZ T6'dan
// UYARLA (rol katmanı düştü). GLOBAL katalog (takvimden bağımsız): ekle /
// ad-açıklama düzenle / pasifleştir-etkinleştir. Pasif kalem çizelgede sütun
// olmaz ama kaydı ve işaretleri silinmez. M3 token'ları.
//
// 18.09.2026: eskiden yan yana iki düğme vardı — "Pasifle" ve "Sil (kalem
// gizlenir)". Kullanıcıya ikisi de "kalemi gizle" diye sunuluyordu, ama "Sil"
// (DELETE) kalemi bu listeden de kaldırıyor ve geri getirme yolu bırakmıyordu;
// onay metni ise "işaretler korunur" diyordu. TEK eylem kaldı: Pasifleştir ↔
// Etkinleştir (PATCH is_active) — geri alınabilir ve ne yaptığı bellidir. Silme
// düğmesi kalktı; `examTrackItemApi.remove` ucu istemcide durur, arayüz çağırmaz.

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useCallback, useState } from "react";

import { ApiError } from "../../lib/api";
import Button from "../../ui/Button";
import { useConfirm } from "../../ui/ConfirmProvider";
import Dialog from "../../ui/Dialog";
import EmptyState from "../../ui/EmptyState";
import Icon from "../../ui/Icon";
import { SkeletonList } from "../../ui/Skeleton";
import { useSnackbar } from "../../ui/SnackbarProvider";
import TextField from "../../ui/TextField";
import { examTrackItemApi } from "./api";

export default function KalemYonetimiDialog({
  open,
  onClose,
  onChanged,
}: {
  open: boolean;
  onClose: () => void;
  onChanged: () => void;
}) {
  const snackbar = useSnackbar();
  const confirm = useConfirm();
  const queryClient = useQueryClient();
  const [newName, setNewName] = useState("");
  const [newDesc, setNewDesc] = useState("");
  const [editing, setEditing] = useState<{ id: number; name: string; description: string } | null>(
    null,
  );
  // Tur 644: kapanışta form state sıfırlanır — bayat "editing" satırı kapat-aç
  // sonrası eski adı geri yazabiliyordu. useCallback ŞART: Dialog'un focus-trap
  // effect'i [open, onClose]'a bağlı; kimliği her render'da değişen handler
  // yazma sırasında odağı panele çalıyordu.
  const handleClose = useCallback(() => {
    setEditing(null);
    setNewName("");
    setNewDesc("");
    onClose();
  }, [onClose]);

  const itemsQuery = useQuery({
    queryKey: ["exam-track-items", "all"],
    queryFn: () => examTrackItemApi.list(true),
    enabled: open,
  });

  const refresh = () => {
    void queryClient.invalidateQueries({ queryKey: ["exam-track-items"] });
    onChanged();
  };

  const createMutation = useMutation({
    mutationFn: () =>
      examTrackItemApi.create({ name: newName.trim(), description: newDesc.trim() }),
    onSuccess: () => {
      snackbar.success("Kalem eklendi.");
      setNewName("");
      setNewDesc("");
      refresh();
    },
    onError: (e) => snackbar.error(e instanceof ApiError ? e.message : "Kalem eklenemedi."),
  });

  const updateMutation = useMutation({
    mutationFn: (p: { id: number; name?: string; description?: string; is_active?: boolean }) =>
      examTrackItemApi.update(p.id, {
        name: p.name,
        description: p.description,
        is_active: p.is_active,
      }),
    onSuccess: (_data, p) => {
      // Her durum geçişinin kendi cümlesi (docs/sozluk.md §3).
      snackbar.success(
        p.is_active === undefined
          ? "Kalem güncellendi."
          : p.is_active
            ? "Kalem etkinleştirildi."
            : "Kalem pasifleştirildi.",
      );
      setEditing(null);
      refresh();
    },
    onError: (e) => snackbar.error(e instanceof ApiError ? e.message : "Kalem güncellenemedi."),
  });

  // Pasifleştirme geri alınabilir ama ETKİSİ geniştir: katalog takvimden
  // bağımsızdır, sütun bütün takvimlerin süreç takibinden birden kalkar — onay
  // diyaloğu bunu söyler. Etkinleştirme zararsızdır, onaysız geçer.
  const toggleActive = (item: { id: number; name: string; is_active: boolean }) => {
    if (!item.is_active) {
      updateMutation.mutate({ id: item.id, is_active: true });
      return;
    }
    void confirm({
      title: "Kalem pasifleştirilsin mi?",
      message:
        `“${item.name}” sütunu bütün takvimlerin süreç takibinden kalkar. Kayıt ve ` +
        "işaretler silinmez; kalemi buradan yeniden etkinleştirebilirsiniz.",
      confirmLabel: "Pasifleştir",
    }).then((ok) => ok && updateMutation.mutate({ id: item.id, is_active: false }));
  };

  const items = itemsQuery.data?.results ?? [];

  return (
    <Dialog
      open={open}
      onClose={handleClose}
      title="Süreç kalemi yönetimi"
      wide
      actions={
        <Button variant="text" onClick={handleClose}>
          Kapat
        </Button>
      }
    >
      <div className="flex flex-col gap-4">
        <div className="rounded-shape-sm bg-surface-container-low p-3">
          <p className="mb-2 text-label-large text-on-surface-variant">Yeni kalem</p>
          <div className="flex flex-col gap-2 sm:flex-row sm:items-end">
            <TextField
              label="Ad"
              className="flex-1"
              value={newName}
              onChange={(e) => setNewName(e.target.value)}
            />
            <TextField
              label="Açıklama (isteğe bağlı)"
              className="flex-1"
              value={newDesc}
              onChange={(e) => setNewDesc(e.target.value)}
            />
            <Button
              icon="add"
              disabled={!newName.trim() || createMutation.isPending}
              onClick={() => createMutation.mutate()}
            >
              Ekle
            </Button>
          </div>
        </div>

        {itemsQuery.isPending ? (
          <SkeletonList rows={4} />
        ) : itemsQuery.isError ? (
          <p role="alert" className="text-body-medium text-error">
            Süreç kalemleri yüklenemedi:{" "}
            {itemsQuery.error instanceof ApiError ? itemsQuery.error.message : "beklenmeyen hata."}
          </p>
        ) : items.length === 0 ? (
          <EmptyState compact icon="checklist" title="Henüz süreç kalemi yok." />
        ) : (
          <ul className="divide-y divide-outline-variant">
            {items.map((item) => (
              <li key={item.id} className="py-2">
                {editing?.id === item.id ? (
                  <div className="flex flex-col gap-2 sm:flex-row sm:items-end">
                    <TextField
                      label="Ad"
                      className="flex-1"
                      value={editing.name}
                      onChange={(e) => setEditing((p) => (p ? { ...p, name: e.target.value } : p))}
                    />
                    <TextField
                      label="Açıklama"
                      className="flex-1"
                      value={editing.description}
                      onChange={(e) =>
                        setEditing((p) => (p ? { ...p, description: e.target.value } : p))
                      }
                    />
                    <Button
                      icon="check"
                      disabled={!editing.name.trim() || updateMutation.isPending}
                      onClick={() =>
                        updateMutation.mutate({
                          id: editing.id,
                          name: editing.name.trim(),
                          description: editing.description.trim(),
                        })
                      }
                    >
                      Kaydet
                    </Button>
                    <Button variant="text" onClick={() => setEditing(null)}>
                      Vazgeç
                    </Button>
                  </div>
                ) : (
                  <div className="flex items-center gap-2">
                    <div className="min-w-0 flex-1">
                      <span
                        className={`block truncate text-body-medium ${
                          item.is_active
                            ? "text-on-surface"
                            : "text-on-surface-variant line-through"
                        }`}
                      >
                        {item.name}
                      </span>
                      {item.description ? (
                        <span className="block truncate text-body-small text-on-surface-variant">
                          {item.description}
                        </span>
                      ) : null}
                    </div>
                    {!item.is_active ? (
                      <span className="shrink-0 rounded-full bg-surface-container-high px-2 py-0.5 text-label-small text-on-surface-variant">
                        Pasif
                      </span>
                    ) : null}
                    <button
                      type="button"
                      aria-label={`${item.name} kalemini düzenle`}
                      title="Düzenle"
                      onClick={() =>
                        setEditing({ id: item.id, name: item.name, description: item.description })
                      }
                      className="inline-flex h-8 w-8 items-center justify-center rounded-shape-sm text-on-surface-variant hover:bg-on-surface/5 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary"
                    >
                      <Icon name="edit" />
                    </button>
                    {/* TEK durum eylemi — yazılı etiketle: göz simgesi tek başına
                        "gizle mi, sil mi" sorusunu yanıtlamıyordu. */}
                    <Button
                      variant="text"
                      icon={item.is_active ? "visibility_off" : "visibility"}
                      aria-label={
                        item.is_active
                          ? `${item.name} kalemini pasifleştir`
                          : `${item.name} kalemini etkinleştir`
                      }
                      disabled={updateMutation.isPending}
                      onClick={() => toggleActive(item)}
                    >
                      {item.is_active ? "Pasifleştir" : "Etkinleştir"}
                    </Button>
                  </div>
                )}
              </li>
            ))}
          </ul>
        )}
      </div>
    </Dialog>
  );
}
