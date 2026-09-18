// Oturum Detayı → Yerleştirme Kuralları. Engelli ya da özel durumu olan
// öğrencilerin yerini sabitler.
//
// VARSAYILAN (kullanıcı isteği 31.08.2026): yer seçilmezse öğrenci KENDİ
// DERSLİĞİNDE, ARKA SIRADA ve TEK BAŞINA oturur. "Tek başına" sıradaki diğer
// koltukları kimseye vermez — salon kapasitesi o kadar azalır (ikili sırada 2).
// İstenirse salon ve koltuk birebir seçilir (BELIRLI_KOLTUK).
//
// KVKK md. 6: gerekçe YALNIZ kategoridir; serbest metin alanı BİLİNÇLE YOKTUR.
// Koltuk koordinatı (satır, sütun, pozisyon) tutulur — `seat_no` DEĞİL:
// numaralandırma düzeni değişince seat_no kayar, koordinat kaymaz.
//
// Koordinat kullanıcıya 1 tabanlı ve SÖZLE gösterilir (docs/sozluk.md §3):
// "3. sıra, 1. sütun, sol koltuk (koltuk no 5)" — eskiden "sıra 2-0, koltuk 0"
// (0 tabanlı, ön cephe bandı da sayılmış) basılıyordu. Koltuk no ve sıra tipi
// salonun GÜNCEL numaralandırmasından (`/exam-rooms/{id}/seats/`) okunur; o uç
// gelmezse konum yine yazılır, yalnız koltuk no düşer (kayıt koordinattır).

import { useState } from "react";
import { useMutation, useQueries, useQuery, useQueryClient } from "@tanstack/react-query";

import { ApiError } from "../../lib/api";
import Autocomplete from "../../ui/Autocomplete";
import Button from "../../ui/Button";
import { useConfirm } from "../../ui/ConfirmProvider";
import DataTable from "../../ui/DataTable";
import Dialog from "../../ui/Dialog";
import EmptyState from "../../ui/EmptyState";
import Icon from "../../ui/Icon";
import Select from "../../ui/Select";
import { SkeletonList } from "../../ui/Skeleton";
import { useSnackbar } from "../../ui/SnackbarProvider";
import type { Student } from "../okul/api";
import { okulApi } from "../okul/api";
import type { SeatPreview } from "../salonlar/api";
import { examRoomApi } from "../salonlar/api";
import { seatPositionLabel } from "../salonlar/planEdit";
import type { PlacementRule, RuleReason, SeatPreference } from "./api";
import { RULE_REASON_TR, RULE_TYPE_TR, SEAT_PREFERENCE_TR, placementRuleApi } from "./api";

/** Salon koltuk ucunun sorgu anahtarı — liste ve koltuk seçici AYNI önbelleği paylaşır. */
const roomSeatsKey = (roomId: number) => ["exam-room-seats", roomId] as const;

/** Koltuk ucundaki satırdan sözlü konum ("3. sıra, 1. sütun, sol koltuk (koltuk no 5)"). */
function seatLabel(seat: SeatPreview): string {
  return seatPositionLabel({
    deskRow: seat.desk_row,
    deskCol: seat.desk_col,
    slot: seat.slot,
    deskType: seat.desk_type,
    seatNo: seat.seat_no,
  });
}

export default function KurallarPaneli({ sessionId }: { sessionId: number }) {
  const qc = useQueryClient();
  const snackbar = useSnackbar();
  const confirm = useConfirm();
  const [addOpen, setAddOpen] = useState(false);

  const kurallar = useQuery({
    queryKey: ["placement-rules", sessionId],
    queryFn: () => placementRuleApi.list({ session: sessionId }),
  });

  const sil = useMutation({
    mutationFn: (id: number) => placementRuleApi.remove(id),
    onSuccess: () => {
      snackbar.success("Kural kaldırıldı.");
      void qc.invalidateQueries({ queryKey: ["placement-rules", sessionId] });
    },
    onError: (e) => snackbar.error(e instanceof ApiError ? e.message : "Kural kaldırılamadı."),
  });

  const satirlar = kurallar.data?.results ?? [];

  // "Belirli koltuk" kurallarının salonları: koltuk no + sıra tipi oradan okunur.
  // Böyle kural bir oturumda bir elin parmağını geçmez — salon başına tek istek.
  const koltukluSalonlar = [
    ...new Set(
      satirlar
        .filter((r) => r.rule_type === "FIXED_SEAT" && r.target_room_id !== null)
        .map((r) => r.target_room_id as number),
    ),
  ];
  const salonKoltuklari = useQueries({
    queries: koltukluSalonlar.map((roomId) => ({
      queryKey: roomSeatsKey(roomId),
      queryFn: () => examRoomApi.seats(roomId),
    })),
  });

  const koltukKonumu = (r: PlacementRule): string => {
    const deskRow = r.target_desk_row ?? 0;
    const deskCol = r.target_desk_col ?? 0;
    const slot = r.target_slot ?? 0;
    const index = r.target_room_id === null ? -1 : koltukluSalonlar.indexOf(r.target_room_id);
    const seat = (index >= 0 ? salonKoltuklari[index]?.data?.seats : undefined)?.find(
      (s) => s.desk_row === deskRow && s.desk_col === deskCol && s.slot === slot,
    );
    // Koltuk ucu yoksa (yükleniyor / koltuk plandan kalkmış) konum yine sözle yazılır.
    return seat ? seatLabel(seat) : seatPositionLabel({ deskRow, deskCol, slot });
  };

  const kuralOzeti = (r: PlacementRule): string => {
    const parcalar = [RULE_TYPE_TR[r.rule_type]];
    if (r.target_room_name) parcalar.push(r.target_room_name);
    if (r.rule_type === "FIXED_SEAT") {
      parcalar.push(koltukKonumu(r));
    } else if (r.seat_preference !== "NONE") {
      parcalar.push(SEAT_PREFERENCE_TR[r.seat_preference]);
    }
    if (r.solo_desk) parcalar.push("tek başına");
    return parcalar.join(" · ");
  };

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center gap-3">
        <p className="text-body-medium text-on-surface-variant">
          Engelli ya da özel durumu olan öğrencilerin yeri burada sabitlenir. Yer seçilmezse öğrenci
          kendi dersliğinde, arka sırada ve tek başına oturur. Kuralı olan öğrencinin yeri dağıtımda
          değiştirilmez; dağıtımdan sonra eklenen kural için “Yeniden dağıt” gerekir.
        </p>
        <span className="ml-auto" />
        <Button variant="tonal" icon="accessible" onClick={() => setAddOpen(true)}>
          Kural ekle
        </Button>
      </div>

      {kurallar.isPending ? (
        <SkeletonList rows={3} />
      ) : satirlar.length === 0 ? (
        <EmptyState
          icon="accessible"
          title="Kural yok"
          description="Özel durumu olan öğrenci varsa yerini buradan sabitleyebilirsiniz."
        />
      ) : (
        <DataTable
          rows={satirlar}
          columns={[
            { header: "Öğrenci", cell: (r: PlacementRule) => r.student_name },
            { header: "Kural", cell: (r: PlacementRule) => kuralOzeti(r) },
            {
              header: "Gerekçe",
              cell: (r: PlacementRule) => RULE_REASON_TR[r.reason_category],
            },
            {
              header: "",
              align: "right" as const,
              cell: (r: PlacementRule) => (
                <Button
                  variant="text"
                  icon="delete"
                  aria-label={`${r.student_name} kuralını kaldır`}
                  disabled={sil.isPending}
                  onClick={() =>
                    void confirm({
                      // Başlık soru, gövde sonuç (docs/sozluk.md §3). Gövdede öğrenci
                      // adı geçmez (CLAUDE.md §1.6) — satır zaten adı gösteriyor.
                      title: "Kural kaldırılsın mı?",
                      message:
                        "Bu öğrencinin yerleştirme kuralı silinir; sonraki dağıtımda yeri diğer öğrenciler gibi belirlenir.",
                      confirmLabel: "Kaldır",
                    }).then((ok) => ok && sil.mutate(r.id))
                  }
                >
                  Kaldır
                </Button>
              ),
            },
          ]}
        />
      )}

      {addOpen ? (
        <KuralEkleDialog
          sessionId={sessionId}
          onClose={() => setAddOpen(false)}
          onSaved={() => {
            setAddOpen(false);
            void qc.invalidateQueries({ queryKey: ["placement-rules", sessionId] });
          }}
        />
      ) : null}
    </div>
  );
}

function KuralEkleDialog({
  sessionId,
  onClose,
  onSaved,
}: {
  sessionId: number;
  onClose: () => void;
  onSaved: () => void;
}) {
  const snackbar = useSnackbar();
  const [ogrenci, setOgrenci] = useState<Student | null>(null);
  const [gerekce, setGerekce] = useState<RuleReason>("DISABILITY");
  const [yeriBenSecerim, setYeriBenSecerim] = useState(false);
  const [salonId, setSalonId] = useState("");
  const [koltuk, setKoltuk] = useState<string>("");
  const [tercih, setTercih] = useState<SeatPreference>("BACK");
  const [solo, setSolo] = useState(true);

  const salonlar = useQuery({
    queryKey: ["exam-rooms"],
    queryFn: () => examRoomApi.list(false),
  });
  const koltuklar = useQuery({
    queryKey: roomSeatsKey(Number(salonId)),
    queryFn: () => examRoomApi.seats(Number(salonId)),
    enabled: yeriBenSecerim && salonId !== "",
  });

  const kaydet = useMutation({
    mutationFn: () => {
      if (ogrenci === null) throw new Error("Öğrenci seçilmedi.");
      if (!yeriBenSecerim) {
        // Varsayılan: kendi dersliğinde, arka sırada, tek başına.
        return placementRuleApi.create({
          student_id: ogrenci.id,
          rule_type: "HOME_CLASSROOM",
          scope: "SESSION",
          session_id: sessionId,
          seat_preference: "BACK",
          solo_desk: true,
          reason_category: gerekce,
        });
      }
      const [row, col, slot] = koltuk.split("-").map(Number);
      return placementRuleApi.create({
        student_id: ogrenci.id,
        rule_type: koltuk === "" ? "FIXED_ROOM" : "FIXED_SEAT",
        scope: "SESSION",
        session_id: sessionId,
        target_room_id: Number(salonId),
        target_desk_row: koltuk === "" ? undefined : row,
        target_desk_col: koltuk === "" ? undefined : col,
        target_slot: koltuk === "" ? undefined : slot,
        seat_preference: koltuk === "" ? tercih : undefined,
        solo_desk: solo,
        reason_category: gerekce,
      });
    },
    onSuccess: () => {
      snackbar.success("Kural eklendi.");
      onSaved();
    },
    onError: (e) => snackbar.error(e instanceof ApiError ? e.message : "Kural eklenemedi."),
  });

  const searchStudents = (q: string): Promise<Student[]> =>
    okulApi.listStudents({ search: q, onlyActive: true, limit: 20 }).then((p) => p.results);

  return (
    <Dialog
      open
      wide
      onClose={onClose}
      title="Yerleştirme kuralı ekle"
      actions={
        <>
          <Button variant="text" onClick={onClose}>
            Vazgeç
          </Button>
          <Button
            disabled={ogrenci === null || kaydet.isPending || (yeriBenSecerim && salonId === "")}
            onClick={() => kaydet.mutate()}
          >
            Kaydet
          </Button>
        </>
      }
    >
      <div className="flex flex-col gap-4">
        <Autocomplete<Student>
          label="Öğrenci"
          placeholder="Ad veya okul no…"
          selected={ogrenci}
          search={searchStudents}
          onSelect={setOgrenci}
          onClear={() => setOgrenci(null)}
          getLabel={(s) => `${s.full_name} (${s.student_number})`}
          getSublabel={(s) => s.class_label}
          getKey={(s) => s.id}
          required
        />

        <Select
          label="Gerekçe"
          value={gerekce}
          onChange={(e) => setGerekce(e.target.value as RuleReason)}
          options={Object.entries(RULE_REASON_TR).map(([value, label]) => ({ value, label }))}
          helperText="Yalnız kategori tutulur; tanı veya rapor bilgisi HİÇ kaydedilmez."
        />

        <label className="flex min-h-9 items-center gap-2 text-body-medium text-on-surface">
          <input
            type="checkbox"
            className="h-5 w-5 accent-primary"
            checked={yeriBenSecerim}
            onChange={(e) => setYeriBenSecerim(e.target.checked)}
          />
          Yerini ben seçeyim
        </label>

        {!yeriBenSecerim ? (
          <p className="rounded-shape-sm bg-tertiary-container px-3 py-2 text-body-small text-on-tertiary-container">
            Öğrenci <strong>kendi dersliğinde, arka sırada ve tek başına</strong> oturacak. Kendi
            dersliği, Sınav Salonları ekranında “Bağlı şube” alanı öğrencinin şubesi olan salondur.
          </p>
        ) : (
          <>
            <Select
              label="Salon"
              placeholder="Seçin"
              value={salonId}
              onChange={(e) => {
                setSalonId(e.target.value);
                setKoltuk("");
              }}
              options={(salonlar.data?.results ?? []).map((r) => ({
                value: String(r.id),
                label: r.group_name ? `${r.name} · ${r.group_name}` : r.name,
              }))}
            />
            <Select
              label="Koltuk"
              value={koltuk}
              onChange={(e) => setKoltuk(e.target.value)}
              options={[
                { value: "", label: "— salon içinde serbest —" },
                // Değer koordinattır (kayıt öyle tutulur); etiket sözledir.
                ...(koltuklar.data?.seats ?? []).map((s) => ({
                  value: `${s.desk_row}-${s.desk_col}-${s.slot}`,
                  label: seatLabel(s),
                })),
              ]}
              disabled={salonId === "" || koltuklar.isPending}
              helperText={
                salonId === ""
                  ? "Önce salon seçin."
                  : "Koltuk seçmezseniz aşağıdaki tercih geçerli."
              }
            />
            {koltuk === "" ? (
              <Select
                label="Salon içinde tercih"
                value={tercih}
                onChange={(e) => setTercih(e.target.value as SeatPreference)}
                options={Object.entries(SEAT_PREFERENCE_TR).map(([value, label]) => ({
                  value,
                  label,
                }))}
              />
            ) : null}
          </>
        )}

        <label className="flex min-h-9 items-center gap-2 text-body-medium text-on-surface">
          <input
            type="checkbox"
            className="h-5 w-5 accent-primary"
            checked={yeriBenSecerim ? solo : true}
            disabled={!yeriBenSecerim}
            onChange={(e) => setSolo(e.target.checked)}
          />
          <span className="inline-flex items-center gap-1">
            Tek başına otursun
            <Icon name="info" size="sm" />
          </span>
        </label>
        <p className="-mt-2 text-body-small text-on-surface-variant">
          Sıradaki diğer koltuklar kimseye verilmez; salon kapasitesi o kadar azalır (ikili sırada
          iki koltuk).
        </p>
      </div>
    </Dialog>
  );
}
