// Varsayılan şablonu TOPLUCA uygulama diyaloğu (02.09.2026 kullanıcı isteği).
//
// GEREKÇE: varsayılan salon şablonu 02.09.2026'da değişti (öğretmen masası
// sağ-öndeyken sol-öne geçti, kapı düştü, numaralandırma masanın önünden
// başlar). Daha önce kurulmuş okullarda onlarca derslik eski düzende kaldı;
// salon başına editörden düzeltmek yüzlerce tıklamaydı.
//
// Kalıp DerslikKumeleriDialog'dan: react-query + onaylı toplu uç. Seçim
// kutuları eski düzendeki salonlarla İŞARETLİ açılır (ön seçim sezgisi
// `planEdit.matchesDefaultTemplate` — yetki backend'de).

import { useMemo, useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";

import { ApiError } from "../../lib/api";
import Button from "../../ui/Button";
import { useConfirm } from "../../ui/ConfirmProvider";
import Dialog from "../../ui/Dialog";
import { useSnackbar } from "../../ui/SnackbarProvider";
import type { ExamRoom } from "./api";
import { examRoomApi } from "./api";
import { matchesDefaultTemplate } from "./planEdit";

export default function SablonUygulaDialog({
  rooms,
  onClose,
}: {
  rooms: ExamRoom[];
  onClose: () => void;
}) {
  const qc = useQueryClient();
  const snackbar = useSnackbar();
  const confirm = useConfirm();

  const eskiDuzen = useMemo(
    () => rooms.filter((r) => !matchesDefaultTemplate(r.layout_plan)).map((r) => r.id),
    [rooms],
  );
  const [secili, setSecili] = useState<number[]>(eskiDuzen);

  const uygula = useMutation({
    mutationFn: () => examRoomApi.applyDefaultPlan(secili),
    onSuccess: (sonuc) => {
      void qc.invalidateQueries({ queryKey: ["exam-rooms"] });
      snackbar.success(
        `${sonuc.updated.length} salon güncellendi, ${sonuc.unchanged.length} zaten uygundu.`,
      );
      // Atlananlar SESSİZ geçmez: kullanıcı hangi salonun elde kaldığını bilmeli.
      if (sonuc.skipped_in_use.length > 0) {
        snackbar.error(
          `Yerleşimi yapılmış ${sonuc.skipped_in_use.length} salon atlandı ` +
            `(${sonuc.skipped_in_use.join(", ")}) — editörden tek tek değiştirebilirsiniz.`,
        );
      }
      onClose();
    },
    onError: (e) => snackbar.error(e instanceof ApiError ? e.message : "Şablon uygulanamadı."),
  });

  const toggle = (id: number) =>
    setSecili((prev) => (prev.includes(id) ? prev.filter((x) => x !== id) : [...prev, id]));

  const onayla = () => {
    void confirm({
      title: "Varsayılan şablonu uygula",
      message:
        `${secili.length} salonun planı varsayılan şablonla DEĞİŞTİRİLECEK; ` +
        "o salonlarda elle yapılmış düzenlemeler kaybolur. Her salon kendi satır/sütun " +
        "ölçüsünde kalır, kapasite değişmez. Devam edilsin mi?",
      confirmLabel: "Uygula",
    }).then((ok) => ok && uygula.mutate());
  };

  return (
    <Dialog
      open
      wide
      onClose={onClose}
      title="Varsayılan şablonu topluca uygula"
      actions={
        <>
          <Button variant="text" onClick={onClose}>
            Vazgeç
          </Button>
          <Button
            icon="grid_view"
            onClick={onayla}
            disabled={uygula.isPending || secili.length === 0}
          >
            Uygula ({secili.length})
          </Button>
        </>
      }
    >
      <div className="space-y-4">
        <p className="text-body-medium text-on-surface-variant">
          Seçili salonların planı <strong>varsayılan şablona</strong> çekilir: öğretmen masası
          ön-sol, kapı yok, tüm hücreler ikili sıra — numaralar masanın önünden başlar. Her salon{" "}
          <strong>kendi satır/sütun ölçüsünde</strong> kalır, kapasite değişmez.
          <br />
          <strong>Yerleşimi yapılmış salonlar atlanır:</strong> basılmış evraktaki koltuk numarası
          planla çelişmesin diye. Onları editörden tek tek değiştirebilirsiniz.
        </p>

        <div className="flex flex-wrap gap-2">
          <Button variant="text" onClick={() => setSecili(eskiDuzen)}>
            Eski düzendekileri seç ({eskiDuzen.length})
          </Button>
          <Button variant="text" onClick={() => setSecili(rooms.map((r) => r.id))}>
            Tümünü seç
          </Button>
          <Button variant="text" onClick={() => setSecili([])}>
            Seçimi temizle
          </Button>
        </div>

        <div className="max-h-72 overflow-y-auto rounded-shape-sm border border-outline-variant p-3">
          {rooms.length === 0 ? (
            <p className="text-body-medium text-on-surface-variant">Henüz salon tanımlı değil.</p>
          ) : (
            <div className="flex flex-wrap gap-x-5 gap-y-1">
              {rooms.map((r) => {
                const uygun = matchesDefaultTemplate(r.layout_plan);
                return (
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
                      <span className="text-on-surface-variant">
                        {" · "}
                        {uygun ? "şablona uygun" : "eski düzen"}
                      </span>
                    </span>
                  </label>
                );
              })}
            </div>
          )}
        </div>
      </div>
    </Dialog>
  );
}
