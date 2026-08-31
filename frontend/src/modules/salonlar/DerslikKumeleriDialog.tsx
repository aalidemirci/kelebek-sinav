// Derslik kümeleri diyaloğu — "Sabah", "Öğle", "Zemin Kat" gibi kümeler
// tanımlanır ve salonlar bu kümelere TOPLUCA atanır.
//
// GEREKÇE (kullanıcı, 31.08.2026): ikili eğitim yapan okullarda "şube
// dersliklerini oluştur" onlarca derslik üretir; sınav sihirbazında tek tek
// işaretlemek zorlaşır. Küme çipiyle "Sabah"ın tamamı tek tıkla seçilir.
//
// Küme `ExamRoom.block` ile KARIŞTIRILMAZ: blok/kat resmî salon evrakının
// başlığına basılır, küme adı evraka girmez — yalnız seçim aracıdır.
// Kalıp SalonlarPage'in hâkim kalıbıdır: react-query.

import { useCallback, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { ApiError } from "../../lib/api";
import Button from "../../ui/Button";
import { useConfirm } from "../../ui/ConfirmProvider";
import Dialog from "../../ui/Dialog";
import Icon from "../../ui/Icon";
import Select from "../../ui/Select";
import { SkeletonList } from "../../ui/Skeleton";
import { useSnackbar } from "../../ui/SnackbarProvider";
import TextField from "../../ui/TextField";
import type { ExamRoom, ExamRoomGroup } from "./api";
import { examRoomGroupApi } from "./api";

export default function DerslikKumeleriDialog({
  rooms,
  onClose,
}: {
  rooms: ExamRoom[];
  onClose: () => void;
}) {
  const qc = useQueryClient();
  const snackbar = useSnackbar();
  const confirm = useConfirm();
  const [name, setName] = useState("");
  const [secili, setSecili] = useState<number[]>([]);
  const [hedef, setHedef] = useState("");

  const gruplar = useQuery({
    queryKey: ["exam-room-groups"],
    queryFn: () => examRoomGroupApi.list(),
  });

  const tazele = useCallback(() => {
    void qc.invalidateQueries({ queryKey: ["exam-room-groups"] });
    void qc.invalidateQueries({ queryKey: ["exam-rooms"] });
  }, [qc]);

  const ekle = useMutation({
    mutationFn: () => examRoomGroupApi.create({ name: name.trim() }),
    onSuccess: () => {
      snackbar.success("Küme eklendi.");
      setName("");
      tazele();
    },
    onError: (e) => snackbar.error(e instanceof ApiError ? e.message : "Küme eklenemedi."),
  });

  const sil = useMutation({
    mutationFn: (id: number) => examRoomGroupApi.remove(id),
    onSuccess: () => {
      snackbar.success("Küme kaldırıldı.");
      tazele();
    },
    onError: (e) => snackbar.error(e instanceof ApiError ? e.message : "Küme kaldırılamadı."),
  });

  const ata = useMutation({
    mutationFn: () =>
      examRoomGroupApi.assign({
        room_ids: secili,
        group: hedef === "" ? null : Number(hedef),
      }),
    onSuccess: (sonuc) => {
      snackbar.success(`${sonuc.updated} salon güncellendi.`);
      setSecili([]);
      tazele();
    },
    onError: (e) => snackbar.error(e instanceof ApiError ? e.message : "Salonlar güncellenemedi."),
  });

  const kaldir = (grup: ExamRoomGroup) => {
    void confirm({
      title: "Kümeyi kaldır",
      message: `'${grup.name}' kümesi kaldırılsın mı? Salonlar silinmez, yalnız kümesiz kalır.`,
      confirmLabel: "Kaldır",
    }).then((ok) => ok && sil.mutate(grup.id));
  };

  const toggle = (id: number) =>
    setSecili((prev) => (prev.includes(id) ? prev.filter((x) => x !== id) : [...prev, id]));

  const liste = gruplar.data?.results ?? [];
  const secenekler = [
    { value: "", label: "— kümesiz —" },
    ...liste.map((g) => ({ value: String(g.id), label: g.name })),
  ];

  return (
    <Dialog
      open
      wide
      onClose={onClose}
      title="Derslik kümeleri (Sabah / Öğle)"
      actions={
        <Button variant="text" onClick={onClose}>
          Kapat
        </Button>
      }
    >
      <div className="space-y-5">
        <p className="text-body-medium text-on-surface-variant">
          Salonları "Sabah", "Öğle" gibi kümelere ayırın; sınav sihirbazında tek tek işaretlemek
          yerine küme düğmesiyle topluca seçersiniz. Küme yalnız seçim kolaylığıdır — salon evrakına
          basılan bilgi "blok/kat" alanıdır, küme değil.
          <br />
          <strong>Bunlar DERSLİK kümeleridir.</strong> Şubeleri (Sayısal, Eşit Ağırlık, Dil…)
          kümelemek ayrı bir listedir: Ayarlar → Şube Kümeleri.
        </p>

        {gruplar.isPending ? (
          <SkeletonList rows={2} />
        ) : liste.length === 0 ? (
          <p className="text-body-medium text-on-surface-variant">Henüz küme tanımlanmamış.</p>
        ) : (
          <ul className="flex flex-wrap gap-2">
            {liste.map((g) => (
              <li
                key={g.id}
                className="flex items-center gap-1 rounded-shape-sm bg-surface-container px-3 py-1.5 text-body-medium text-on-surface"
              >
                {g.name}
                <span className="text-on-surface-variant"> ({g.room_count})</span>
                <button
                  type="button"
                  aria-label={`${g.name} kümesini kaldır`}
                  onClick={() => kaldir(g)}
                  className="ml-1 flex h-6 w-6 items-center justify-center rounded-shape-xs text-on-surface-variant transition hover:bg-surface-container-high hover:text-error focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary"
                >
                  <Icon name="close" size="sm" />
                </button>
              </li>
            ))}
          </ul>
        )}

        <div className="flex flex-wrap items-end gap-3">
          <TextField
            className="min-w-48 grow"
            label="Küme adı"
            value={name}
            onChange={(e) => setName(e.target.value)}
            placeholder="Sabah"
          />
          <Button
            icon="add"
            onClick={() => ekle.mutate()}
            disabled={ekle.isPending || !name.trim()}
          >
            Küme ekle
          </Button>
        </div>

        <div>
          <p className="text-title-small text-on-surface">Salonları kümeye ata</p>
          <div className="mt-2 max-h-60 overflow-y-auto rounded-shape-sm border border-outline-variant p-3">
            <div className="flex flex-wrap gap-x-5 gap-y-1">
              {rooms.map((r) => (
                <label
                  key={r.id}
                  className="flex min-h-9 items-center gap-2 text-body-medium text-on-surface"
                >
                  <input
                    type="checkbox"
                    className="h-5 w-5 accent-primary"
                    checked={secili.includes(r.id)}
                    onChange={() => toggle(r.id)}
                  />
                  <span>
                    {r.name}
                    {r.group_name ? (
                      <span className="text-on-surface-variant"> · {r.group_name}</span>
                    ) : null}
                  </span>
                </label>
              ))}
            </div>
          </div>
          {/* Dar ekranda alt alta akar; düğme metinleri kırpılmasın diye
              sabit sütun genişliği YOK (saha bulgusu 31.08.2026). */}
          <div className="mt-3 flex flex-wrap items-end gap-3">
            <Select
              className="min-w-48 grow"
              label="Küme"
              value={hedef}
              onChange={(e) => setHedef(e.target.value)}
              options={secenekler}
            />
            <Button
              icon="playlist_add_check"
              onClick={() => ata.mutate()}
              disabled={ata.isPending || secili.length === 0}
            >
              Ata ({secili.length})
            </Button>
            {secili.length > 0 ? (
              <Button variant="text" onClick={() => setSecili([])}>
                Temizle
              </Button>
            ) : null}
          </div>
        </div>
      </div>
    </Dialog>
  );
}
