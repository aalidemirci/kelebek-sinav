// Gözetmenler paneli (F7) — OYS GozetmenlerPaneli'nden UYARLA (U2/TB4):
// "Otomatik Öner" ALINMADI — OYS'de havuz ders programı + devamsızlık
// köprülerine dayanıyordu; o kaynaklar KS'de yok, aynı yanlış-seçim sorunu
// geri gelirdi. Birincil (ve tek) akış: salon başına ARANABİLİR seçici
// (Autocomplete); muaf/pencere-çakışan/atanmış adaylar listede GÖRÜNÜR ama
// nedeniyle seçilemez. Görevlendirme yalnız DAĞITILDI durumda düzenlenir;
// tebellüğ onaydan sonra da işlenebilir. KS eki: muafiyet yönetimi bölümü —
// OYS'de admin arayüzünden giriliyordu, KS'de admin arka kapısı yok.

import { useCallback, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { ApiError } from "../../lib/api";
import Autocomplete from "../../ui/Autocomplete";
import Button from "../../ui/Button";
import Icon from "../../ui/Icon";
import Select from "../../ui/Select";
import { useConfirm } from "../../ui/ConfirmProvider";
import { useSnackbar } from "../../ui/SnackbarProvider";
import type {
  ExamSession,
  ExemptionReasonCode,
  ProctorAssignmentRow,
  ProctorCandidate,
  ProctorRoleCode,
} from "./api";
import { EXEMPTION_REASON_TR, examSessionApi, proctorExemptionApi } from "./api";

/** Aday neden seçilemez — Autocomplete getDisabled sözleşmesi. */
function candidateDisabledReason(c: ProctorCandidate): string | undefined {
  if (c.is_assigned) return "bu oturumda zaten görevli";
  if (c.is_exempt) return "muaf";
  if (c.is_busy) return "aynı saatte başka görevde";
  return undefined;
}

function AssignmentChip({
  assignment,
  editable,
  canAcknowledge,
  onRemove,
  onAcknowledge,
}: {
  assignment: ProctorAssignmentRow;
  editable: boolean;
  canAcknowledge: boolean;
  onRemove: (a: ProctorAssignmentRow) => void;
  onAcknowledge: (id: number) => void;
}) {
  return (
    <span className="flex items-center gap-1 rounded-full bg-secondary-container py-1 pl-4 pr-1 text-label-large text-on-secondary-container">
      {assignment.teacher_name}
      {assignment.acknowledged && <Icon name="task_alt" size="base" label="Tebellüğ işlendi" />}
      {!assignment.acknowledged && canAcknowledge && (
        <button
          type="button"
          onClick={() => onAcknowledge(assignment.id)}
          aria-label={`${assignment.teacher_name} tebellüğ işle`}
          title="Tebellüğ işle"
          className="flex min-h-8 min-w-8 items-center justify-center rounded-shape-sm hover:bg-on-secondary-container/5 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary"
        >
          <Icon name="task_alt" size="base" />
        </button>
      )}
      {editable && (
        <button
          type="button"
          onClick={() => onRemove(assignment)}
          aria-label={`${assignment.teacher_name} görevlendirmesini kaldır`}
          title="Görevlendirmeyi kaldır"
          className="flex min-h-8 min-w-8 items-center justify-center rounded-shape-sm hover:bg-on-secondary-container/5 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary"
        >
          <Icon name="close" size="base" />
        </button>
      )}
    </span>
  );
}

export default function GozetmenlerPaneli({ session }: { session: ExamSession }) {
  const snackbar = useSnackbar();
  const confirm = useConfirm();
  const qc = useQueryClient();
  const editable = session.status === "DISTRIBUTED";
  const canAcknowledge = session.status !== "ARCHIVED";
  // Atama sonrası ilgili satırın Autocomplete'ini sıfırlamak için sayaç.
  const [resetTick, setResetTick] = useState(0);

  const proctors = useQuery({
    queryKey: ["exam-proctors", session.id],
    queryFn: () => examSessionApi.proctors(session.id),
  });
  const candidates = useQuery({
    queryKey: ["exam-proctor-candidates", session.id],
    queryFn: () => examSessionApi.proctorCandidates(session.id),
    enabled: editable && session.proctors_enabled,
  });
  const seating = useQuery({
    queryKey: ["exam-seating", session.id],
    queryFn: () => examSessionApi.seating(session.id),
    enabled: session.proctors_enabled,
  });

  const refresh = () => {
    void qc.invalidateQueries({ queryKey: ["exam-proctors", session.id] });
    void qc.invalidateQueries({ queryKey: ["exam-proctor-candidates", session.id] });
  };

  const assign = useMutation({
    mutationFn: (payload: { teacher_id: number; role: ProctorRoleCode; room_id?: number }) =>
      examSessionApi.assignProctor(session.id, payload),
    onSuccess: () => {
      refresh();
      setResetTick((t) => t + 1);
      snackbar.success("Görevlendirme eklendi.");
    },
    onError: (e) => snackbar.error(e instanceof ApiError ? e.message : "Atama yapılamadı."),
  });

  const remove = useMutation({
    mutationFn: (id: number) => examSessionApi.removeProctor(id),
    onSuccess: () => {
      refresh();
      snackbar.success("Görevlendirme kaldırıldı.");
    },
    onError: (e) => snackbar.error(e instanceof ApiError ? e.message : "Kaldırılamadı."),
  });

  const acknowledge = useMutation({
    mutationFn: (id: number) => examSessionApi.acknowledgeProctor(id),
    onSuccess: () => {
      refresh();
      snackbar.success("Tebellüğ işlendi.");
    },
    onError: (e) => snackbar.error(e instanceof ApiError ? e.message : "İşlenemedi."),
  });

  // Aday araması: liste küçük (~50 öğretmen) ve sorgu zaten yüklü — filtre
  // istemci tarafında, Türkçe duyarlı. Uygun olmayan adaylar SONUÇTA KALIR
  // (görünür, seçilemez — neden alt etikette).
  const searchCandidates = useCallback(
    async (q: string) => {
      const needle = q.toLocaleLowerCase("tr");
      const rows = candidates.data?.candidates ?? [];
      const starts = rows.filter((c) => c.teacher_name.toLocaleLowerCase("tr").startsWith(needle));
      const contains = rows.filter(
        (c) =>
          !c.teacher_name.toLocaleLowerCase("tr").startsWith(needle) &&
          c.teacher_name.toLocaleLowerCase("tr").includes(needle),
      );
      return [...starts, ...contains];
    },
    [candidates.data],
  );

  const handleRemove = (a: ProctorAssignmentRow) => {
    void confirm({
      title: "Görevlendirme kaldırılsın mı?",
      message: `${a.teacher_name} — ${a.room_name || "Yedek"} görevlendirmesi kaldırılacak.`,
      confirmLabel: "Kaldır",
    }).then((ok) => ok && remove.mutate(a.id));
  };

  if (!session.proctors_enabled) {
    return (
      <p className="text-body-medium text-on-surface-variant">
        Gözetmen modülü bu oturumda kapalı (K2 — varsayılan). Taslakta oturum ayarlarından
        açılabilir; kapalıyken R9 tutanağında görevli adı elle yazılır ve R6 evrak kataloğunda
        görünmez.
      </p>
    );
  }

  const assignments = proctors.data?.assignments ?? [];
  const byRoom = new Map<number, ProctorAssignmentRow[]>();
  const reserves: ProctorAssignmentRow[] = [];
  for (const a of assignments) {
    if (a.role === "RESERVE" || a.room_id === null) {
      reserves.push(a);
    } else {
      const list = byRoom.get(a.room_id) ?? [];
      list.push(a);
      byRoom.set(a.room_id, list);
    }
  }
  const rooms = seating.data?.rooms ?? [];

  const pickerFor = (label: string, role: ProctorRoleCode, roomId?: number) => (
    <div className="ml-auto w-72">
      <Autocomplete<ProctorCandidate>
        key={`${role}:${roomId ?? "reserve"}:${resetTick}`}
        label=""
        ariaLabel={label}
        placeholder="Gözetmen ekle — ilk harfleri yazın…"
        minChars={1}
        selected={null}
        onClear={() => undefined}
        search={searchCandidates}
        onSelect={(c) => assign.mutate({ teacher_id: c.teacher_id, role, room_id: roomId })}
        getKey={(c) => c.teacher_id}
        getLabel={(c) => c.teacher_name}
        getDisabled={candidateDisabledReason}
      />
    </div>
  );

  return (
    <div className="flex flex-col gap-4">
      {editable ? (
        <p className="max-w-3xl text-body-small text-on-surface-variant">
          Her salon için öğretmeni LİSTEDEN seçin (ilk harfler yazılınca süzülür). Muaf, aynı saatte
          başka oturumda görevli ve zaten atanmış öğretmenler nedeniyle birlikte görünür ama
          seçilemez. Yedek görevli salonsuzdur (öneri: 5 salona 1 yedek).
        </p>
      ) : (
        <p className="text-body-small text-on-surface-variant">
          Oturum {session.status === "APPROVED" ? "onaylı" : "arşivde"} — görevlendirme kilitli;
          {session.status === "APPROVED" ? " tebellüğ işlenebilir." : " kayıtlar salt-okunur."}
        </p>
      )}

      {editable ? (
        <ul className="flex flex-col gap-2">
          {rooms.map((room) => (
            <li
              key={room.room_id}
              className="flex flex-wrap items-center gap-3 rounded-shape-md border border-outline-variant p-3"
            >
              <span className="w-24 shrink-0 text-title-small text-on-surface">
                {room.room_name}
              </span>
              {(byRoom.get(room.room_id) ?? []).map((a) => (
                <AssignmentChip
                  key={a.id}
                  assignment={a}
                  editable={editable}
                  canAcknowledge={canAcknowledge}
                  onRemove={handleRemove}
                  onAcknowledge={(id) => acknowledge.mutate(id)}
                />
              ))}
              {(byRoom.get(room.room_id) ?? []).length === 0 && (
                <span className="text-body-small text-on-surface-variant">Görevli yok</span>
              )}
              {pickerFor(`${room.room_name} için gözetmen ata`, "PROCTOR", room.room_id)}
            </li>
          ))}
          <li className="flex flex-wrap items-center gap-3 rounded-shape-md border border-outline-variant bg-surface-container-low p-3">
            <span className="w-24 shrink-0 text-title-small text-on-surface">Yedekler</span>
            {reserves.map((a) => (
              <AssignmentChip
                key={a.id}
                assignment={a}
                editable={editable}
                canAcknowledge={canAcknowledge}
                onRemove={handleRemove}
                onAcknowledge={(id) => acknowledge.mutate(id)}
              />
            ))}
            {reserves.length === 0 && (
              <span className="text-body-small text-on-surface-variant">
                Yedek yok (öneri: 5 salona 1 yedek)
              </span>
            )}
            {pickerFor("Yedek gözetmen ata", "RESERVE")}
          </li>
        </ul>
      ) : assignments.length === 0 ? (
        <p className="text-body-medium text-on-surface-variant">Görevlendirme yapılmamış.</p>
      ) : (
        <ul className="flex flex-col gap-2">
          {assignments.map((a) => (
            <li
              key={a.id}
              className="flex flex-wrap items-center gap-3 rounded-shape-md border border-outline-variant p-3"
            >
              <span className="text-title-small text-on-surface">{a.teacher_name}</span>
              <span className="rounded-full bg-secondary-container px-3 py-1 text-label-small text-on-secondary-container">
                {a.role === "RESERVE" ? "Yedek" : "Gözetmen"}
              </span>
              <span className="text-body-small text-on-surface-variant">
                {a.room_name || "Salonsuz (yedek)"}
              </span>
              {a.acknowledged && (
                <span className="rounded-full bg-primary-container px-3 py-1 text-label-small text-on-primary-container">
                  Tebellüğ ✓
                </span>
              )}
              <span className="ml-auto" />
              {!a.acknowledged && canAcknowledge && (
                <Button
                  variant="text"
                  icon="task_alt"
                  onClick={() => acknowledge.mutate(a.id)}
                  disabled={acknowledge.isPending}
                >
                  Tebellüğ işle
                </Button>
              )}
            </li>
          ))}
        </ul>
      )}

      {editable ? <MuafiyetBolumu sessionId={session.id} onChanged={refresh} /> : null}
    </div>
  );
}

/** Muafiyet yönetimi — KS eki: OYS'de admin arayüzünden giriliyordu; KS'de
 * admin arka kapısı yok. Gerekçe YALNIZ kategori (KVKK md. 6). */
function MuafiyetBolumu({ sessionId, onChanged }: { sessionId: number; onChanged: () => void }) {
  const snackbar = useSnackbar();
  const confirm = useConfirm();
  const qc = useQueryClient();
  const [reason, setReason] = useState<ExemptionReasonCode>("OTHER");
  const [scope, setScope] = useState<"PERMANENT" | "SESSION">("PERMANENT");
  const [resetTick, setResetTick] = useState(0);

  const exemptions = useQuery({
    queryKey: ["proctor-exemptions", sessionId],
    queryFn: () => proctorExemptionApi.list(sessionId),
  });
  const candidates = useQuery({
    queryKey: ["exam-proctor-candidates", sessionId],
    queryFn: () => examSessionApi.proctorCandidates(sessionId),
  });

  const refresh = () => {
    void qc.invalidateQueries({ queryKey: ["proctor-exemptions", sessionId] });
    onChanged();
  };

  const create = useMutation({
    mutationFn: (teacherId: number) =>
      proctorExemptionApi.create({
        teacher_id: teacherId,
        scope,
        session_id: scope === "SESSION" ? sessionId : null,
        reason_category: reason,
      }),
    onSuccess: () => {
      refresh();
      setResetTick((t) => t + 1);
      snackbar.success("Muafiyet eklendi.");
    },
    onError: (e) => snackbar.error(e instanceof ApiError ? e.message : "Muafiyet eklenemedi."),
  });

  const remove = useMutation({
    mutationFn: (id: number) => proctorExemptionApi.remove(id),
    onSuccess: () => {
      refresh();
      snackbar.success("Muafiyet kaldırıldı.");
    },
    onError: (e) => snackbar.error(e instanceof ApiError ? e.message : "Kaldırılamadı."),
  });

  const search = useCallback(
    async (q: string) => {
      const needle = q.toLocaleLowerCase("tr");
      return (candidates.data?.candidates ?? []).filter((c) =>
        c.teacher_name.toLocaleLowerCase("tr").includes(needle),
      );
    },
    [candidates.data],
  );

  const rows = exemptions.data?.results ?? [];

  return (
    <section className="rounded-shape-md bg-surface-container p-4">
      <h3 className="text-title-small text-on-surface">Muaf personel</h3>
      <p className="mb-3 mt-1 text-body-small text-on-surface-variant">
        Muaf öğretmen elle atamada bile SEÇİLEMEZ. Gerekçe yalnız kategoridir; serbest metin alanı
        bilinçle yoktur (KVKK md. 6). Güncelleme yerine kaldır + yeniden ekle.
      </p>
      <div className="mb-3 flex flex-wrap items-end gap-3">
        <div className="w-72">
          <Autocomplete<ProctorCandidate>
            key={`muafiyet:${resetTick}`}
            label="Öğretmen"
            placeholder="Ad yazın…"
            minChars={1}
            selected={null}
            onClear={() => undefined}
            search={search}
            onSelect={(c) => create.mutate(c.teacher_id)}
            getKey={(c) => c.teacher_id}
            getLabel={(c) => c.teacher_name}
            getDisabled={(c) => (c.is_exempt ? "zaten muaf" : undefined)}
          />
        </div>
        <div className="w-40">
          <Select
            label="Kapsam"
            options={[
              { value: "PERMANENT", label: "Kalıcı" },
              { value: "SESSION", label: "Bu oturum" },
            ]}
            value={scope}
            onChange={(e) => setScope(e.target.value as "PERMANENT" | "SESSION")}
          />
        </div>
        <div className="w-40">
          <Select
            label="Gerekçe"
            options={(Object.keys(EXEMPTION_REASON_TR) as ExemptionReasonCode[]).map((k) => ({
              value: k,
              label: EXEMPTION_REASON_TR[k],
            }))}
            value={reason}
            onChange={(e) => setReason(e.target.value as ExemptionReasonCode)}
          />
        </div>
      </div>
      {rows.length === 0 ? (
        <p className="text-body-small text-on-surface-variant">Muaf personel yok.</p>
      ) : (
        <ul className="flex flex-wrap gap-2">
          {rows.map((row) => (
            <li
              key={row.id}
              className="flex items-center gap-2 rounded-full bg-surface-container-high py-1 pl-4 pr-1 text-label-large text-on-surface"
            >
              {row.teacher_name}
              <span className="text-label-small text-on-surface-variant">
                {row.scope === "PERMANENT" ? "Kalıcı" : "Bu oturum"} ·{" "}
                {EXEMPTION_REASON_TR[row.reason_category]}
              </span>
              <button
                type="button"
                aria-label={`${row.teacher_name} muafiyetini kaldır`}
                title="Muafiyeti kaldır"
                onClick={() =>
                  void confirm({
                    title: "Muafiyet kaldırılsın mı?",
                    message: `${row.teacher_name} muafiyeti kaldırılacak.`,
                    confirmLabel: "Kaldır",
                  }).then((ok) => ok && remove.mutate(row.id))
                }
                className="flex min-h-8 min-w-8 items-center justify-center rounded-shape-sm hover:bg-on-surface/5 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary"
              >
                <Icon name="close" size="base" />
              </button>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}
