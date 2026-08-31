// Sınav Salonları sayfası (OYS T10'dan KS'ye): salon listesi + 2D yerleşim
// editörü + şube↔derslik eşlemesi. Liste/editör tek sayfada durum geçişlidir.
// Şube seçici F1 şube kataloğundan (okul.ClassSection) beslenir.
// M3 token'ları — ham renk/px yok.

import { useCallback, useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { ApiError } from "../../lib/api";
import Button from "../../ui/Button";
import Card from "../../ui/Card";
import Dialog from "../../ui/Dialog";
import Icon from "../../ui/Icon";
import { SkeletonList } from "../../ui/Skeleton";
import TextField from "../../ui/TextField";
import { useConfirm } from "../../ui/ConfirmProvider";
import { useSnackbar } from "../../ui/SnackbarProvider";
import { okulApi } from "../okul/api";
import type { ExamRoom } from "./api";
import { examRoomApi } from "./api";
import DerslikKumeleriDialog from "./DerslikKumeleriDialog";
import RoomEditor from "./RoomEditor";
import { emptyPlan } from "./planEdit";

export default function SalonlarPage() {
  const qc = useQueryClient();
  const snackbar = useSnackbar();
  const confirm = useConfirm();
  const [selectedId, setSelectedId] = useState<number | null>(null);
  const [createOpen, setCreateOpen] = useState(false);
  const [newName, setNewName] = useState("");
  const [newBlock, setNewBlock] = useState("");
  const [groupsOpen, setGroupsOpen] = useState(false);
  const closeGroups = useCallback(() => setGroupsOpen(false), []);
  // Dialog odak efekti onClose kimliğine bağlı — inline arrow her render'da
  // yenilenir ve yazarken odağı panele geri çalar; sabit referans şart.
  const closeCreate = useCallback(() => setCreateOpen(false), []);

  const rooms = useQuery({
    queryKey: ["exam-rooms"],
    queryFn: () => examRoomApi.list(true),
  });
  // Bağlı şube seçici: F1 şube kataloğu (aktif ders yılı).
  const sections = useQuery({
    queryKey: ["class-sections"],
    queryFn: () => okulApi.listClassSections(),
  });

  const sectionOptions = useMemo(
    () =>
      (sections.data ?? []).map((s) => ({
        value: String(s.id),
        label: s.class_label,
      })),
    [sections.data],
  );

  const create = useMutation({
    mutationFn: () =>
      examRoomApi.create({
        name: newName.trim(),
        block: newBlock.trim(),
        layout_plan: emptyPlan(),
      }),
    onSuccess: (room) => {
      snackbar.success("Salon oluşturuldu — planı düzenleyebilirsiniz.");
      setCreateOpen(false);
      setNewName("");
      setNewBlock("");
      void qc.invalidateQueries({ queryKey: ["exam-rooms"] });
      setSelectedId(room.id);
    },
    onError: (e) => snackbar.error(e instanceof ApiError ? e.message : "Salon oluşturulamadı."),
  });

  const generateSectionRooms = useMutation({
    mutationFn: () => examRoomApi.generateSectionRooms(),
    onSuccess: (result) => {
      void qc.invalidateQueries({ queryKey: ["exam-rooms"] });
      snackbar.success(
        `${result.created.length} salon oluşturuldu, ${result.skipped.length} zaten vardı.`,
      );
      if (result.orphan_rooms.length > 0) {
        snackbar.error(
          `Kapatılmış şubeye bağlı ${result.orphan_rooms.length} salon var — pasifleştirmeyi değerlendirin.`,
        );
      }
    },
    onError: (e) => snackbar.error(e instanceof ApiError ? e.message : "Salonlar üretilemedi."),
  });

  const handleGenerateSectionRooms = () => {
    void confirm({
      title: "Şube dersliklerini oluştur",
      message:
        "Her aktif şube için 40 koltuklu ikili-sıra derslik planı üretilecek (kapı sol-ön, öğretmen masası sağ-ön). Zaten tanımlı salonlar atlanır.",
      confirmLabel: "Oluştur",
    }).then((ok) => {
      if (ok) generateSectionRooms.mutate();
    });
  };

  const list = rooms.data?.results ?? [];
  const selected = list.find((r) => r.id === selectedId) ?? null;

  const handleSaved = (room: ExamRoom) => {
    void qc.invalidateQueries({ queryKey: ["exam-rooms"] });
    void qc.setQueryData<typeof rooms.data>(["exam-rooms"], (prev) =>
      prev ? { ...prev, results: prev.results.map((r) => (r.id === room.id ? room : r)) } : prev,
    );
  };

  return (
    <div>
      {selected ? (
        <RoomEditor
          key={selected.id}
          room={selected}
          sectionOptions={sectionOptions}
          onSaved={handleSaved}
          onBack={() => setSelectedId(null)}
        />
      ) : (
        <>
          <div className="mb-4 flex flex-wrap items-center gap-3">
            <h1 className="text-headline-medium text-on-surface">Sınav Salonları</h1>
            <span className="ml-auto" />
            <Button variant="text" icon="category" onClick={() => setGroupsOpen(true)}>
              Kümeler
            </Button>
            <Button
              variant="tonal"
              icon="domain_add"
              disabled={generateSectionRooms.isPending}
              onClick={handleGenerateSectionRooms}
            >
              Şube dersliklerini oluştur
            </Button>
            <Button icon="add" onClick={() => setCreateOpen(true)}>
              Yeni salon
            </Button>
          </div>
          <p className="mb-4 text-body-medium text-on-surface-variant">
            Salon planları kroki (R1) ve kelebek dağıtımının temelidir. Bir salonu şubeye bağlamak
            klasik (kendi dersliğinde) düzeni mümkün kılar. Salon sayısı kalabalıksa (ikili eğitim)
            "Kümeler" ile Sabah/Öğle gibi kümeler tanımlayın — sihirbazda tek tıkla seçilirler.
          </p>

          {rooms.isPending && <SkeletonList rows={4} />}
          {rooms.isError && (
            <Card elevation={1} className="p-6">
              <p role="alert" className="text-body-medium text-error">
                Salonlar yüklenemedi:{" "}
                {rooms.error instanceof ApiError ? rooms.error.message : "beklenmeyen hata."}
              </p>
            </Card>
          )}
          {rooms.isSuccess && list.length === 0 && (
            <Card elevation={1} className="p-6">
              <p className="text-body-medium text-on-surface-variant">
                Henüz salon tanımlı değil. &quot;Yeni salon&quot; ile başlayın.
              </p>
            </Card>
          )}

          <ul className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
            {list.map((room) => (
              <li key={room.id}>
                <button
                  type="button"
                  onClick={() => setSelectedId(room.id)}
                  className="group relative block w-full overflow-hidden rounded-shape-lg text-left focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary focus-visible:ring-offset-2 focus-visible:ring-offset-surface"
                >
                  <Card elevation={1} className="h-full p-5">
                    <span aria-hidden="true" className="state-layer" />
                    <div className="relative">
                      <div className="flex items-center gap-2">
                        <Icon
                          name="meeting_room"
                          aria-hidden="true"
                          className="text-on-surface-variant"
                        />
                        <span className="text-title-medium text-on-surface">{room.name}</span>
                        {!room.is_active && (
                          <span className="ml-auto rounded-full bg-surface-container-high px-3 py-1 text-label-small text-on-surface-variant">
                            Pasif
                          </span>
                        )}
                      </div>
                      <dl className="mt-2 space-y-1 text-body-small text-on-surface-variant">
                        <div className="flex justify-between">
                          <dt>Kapasite</dt>
                          <dd className="text-on-surface">{room.capacity} koltuk</dd>
                        </div>
                        <div className="flex justify-between">
                          <dt>Blok</dt>
                          <dd>{room.block || "—"}</dd>
                        </div>
                        <div className="flex justify-between">
                          <dt>Bağlı şube</dt>
                          <dd>{room.linked_section_label || "—"}</dd>
                        </div>
                      </dl>
                    </div>
                  </Card>
                </button>
              </li>
            ))}
          </ul>

          <Dialog
            open={createOpen}
            onClose={closeCreate}
            title="Yeni salon"
            actions={
              <>
                <Button variant="text" onClick={closeCreate}>
                  Vazgeç
                </Button>
                <Button
                  onClick={() => create.mutate()}
                  disabled={create.isPending || newName.trim() === ""}
                >
                  Oluştur
                </Button>
              </>
            }
          >
            <div className="flex flex-col gap-3">
              <TextField
                label="Salon adı"
                value={newName}
                onChange={(e) => setNewName(e.target.value)}
                placeholder="Örn. D-204"
                required
              />
              <TextField
                label="Blok / kat"
                value={newBlock}
                onChange={(e) => setNewBlock(e.target.value)}
                placeholder="Örn. A Blok 2. Kat"
              />
              <p className="text-body-small text-on-surface-variant">
                Plan boş başlar; oluşturduktan sonra editörde sıraları yerleştirin.
              </p>
            </div>
          </Dialog>

          {groupsOpen ? <DerslikKumeleriDialog rooms={list} onClose={closeGroups} /> : null}
        </>
      )}
    </div>
  );
}
