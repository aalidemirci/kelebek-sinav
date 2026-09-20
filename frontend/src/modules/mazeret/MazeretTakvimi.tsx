// Mazeret Sınav Takvimi (20.09.2026, kullanıcı isteği): son sınav bitip yoklamalar girilince,
// mazereti kabul edilen öğrencilerin gireceği sınavlar için AYRI takvim — herkesin girdiği
// sınavlar burada yoktur. Asıl takvim sırası korunur; kaç güne sığacağını ve bir öğrencinin
// günde en çok kaç sınava gireceğini idareci belirler. Onaylanan takvimin oturumları tek
// tıkla üretilir (aynı saatteki sınavlar tek oturumda); ilan nüshası ADSIZDIR.
//
// Kurallar backend'dedir (`makeup_schedule` + `services_makeup_plan`); ekran yalnız sunar.

import { useCallback, useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Link } from "react-router-dom";

import { ApiError } from "../../lib/api";
import { dosyaAdi, saveBlob } from "../../lib/download";
import { formatDate } from "../../lib/format";
import Button from "../../ui/Button";
import Card from "../../ui/Card";
import { useConfirm } from "../../ui/ConfirmProvider";
import Dialog from "../../ui/Dialog";
import EmptyState from "../../ui/EmptyState";
import Icon from "../../ui/Icon";
import Select from "../../ui/Select";
import { SkeletonList } from "../../ui/Skeleton";
import TextField from "../../ui/TextField";
import UyariBandi from "../../ui/UyariBandi";
import { useSnackbar } from "../../ui/SnackbarProvider";
import type { MakeupPlan, MakeupPlanItem, MakeupPlanPdfKind } from "./api";
import { makeupPlanApi } from "./api";
import type { PlanFormValues } from "./MazeretTakvimiDialoglari";
import { MoveItemDialog, PlanFormDialog } from "./MazeretTakvimiDialoglari";

const hata = (e: unknown, varsayilan: string) => (e instanceof ApiError ? e.message : varsayilan);

/** Takvim parametrelerinin tek cümlelik özeti. */
function ozet(plan: MakeupPlan): string {
  const sira = plan.strict_order
    ? "asıl takvim sırası kesin korunur"
    : "sınavlar boş saatlere öne çekilir (öğrencinin kendi sırası korunur)";
  return `${formatDate(plan.start_date)} tarihinden başlayarak ${plan.day_count} gün · bir öğrenci günde en çok ${plan.max_per_day} sınav · ${sira}`;
}

function SinavKarti({
  item,
  editable,
  onEdit,
}: {
  item: MakeupPlanItem;
  editable: boolean;
  onEdit: (item: MakeupPlanItem) => void;
}) {
  return (
    <div className="flex flex-col gap-1 rounded-shape-sm border border-outline-variant bg-surface-container-lowest p-2">
      <div className="flex flex-wrap items-center gap-1">
        <span className="text-label-large text-on-surface">{item.course_label}</span>
        {item.is_pinned && (
          <Icon name="push_pin" size="sm" label="Sabit" className="text-on-surface-variant" />
        )}
        {item.external && (
          <span className="rounded-full bg-tertiary-container px-2 py-0.5 text-label-small text-on-tertiary-container">
            Üst makam
          </span>
        )}
      </div>
      <span className="text-body-small text-on-surface-variant">
        {item.student_count} öğrenci · asıl sınav {formatDate(item.source_date)}
      </span>
      {item.session_id !== null && (
        <Link
          to={`/oturumlar/${item.session_id}`}
          className="text-body-small text-primary underline"
        >
          Oturuma git
        </Link>
      )}
      <details className="text-body-small text-on-surface-variant">
        <summary className="cursor-pointer">Öğrenciler</summary>
        <ul className="mt-1 flex flex-col gap-0.5">
          {item.students.map((s) => (
            <li key={s.record_id}>
              {s.student_number} · {s.full_name} · {s.class_label}
            </li>
          ))}
        </ul>
      </details>
      {editable && item.session_id === null && (
        <Button
          variant="text"
          icon="open_with"
          onClick={() => onEdit(item)}
          aria-label={`${item.course_label} sınavını taşı`}
          className="self-start"
        >
          {item.placed_date ? "Taşı" : "Takvime koy"}
        </Button>
      )}
    </div>
  );
}

export default function MazeretTakvimi({ semesterId }: { semesterId: number | undefined }) {
  const qc = useQueryClient();
  const snackbar = useSnackbar();
  const confirm = useConfirm();
  const [selectedId, setSelectedId] = useState<number | null>(null);
  const [formOpen, setFormOpen] = useState<"new" | "edit" | null>(null);
  const [moving, setMoving] = useState<MakeupPlanItem | null>(null);
  const [approveOpen, setApproveOpen] = useState(false);
  const [approvedBy, setApprovedBy] = useState("");
  const [hideNames, setHideNames] = useState(false);
  const [moveWarnings, setMoveWarnings] = useState<string[]>([]);
  const [pdfBusy, setPdfBusy] = useState<string | null>(null);
  // Dialog odak efekti onClose kimliğine bağlı — sabit referans şart (OturumlarPage emsali).
  const closeForm = useCallback(() => setFormOpen(null), []);
  const closeMove = useCallback(() => setMoving(null), []);
  const closeApprove = useCallback(() => setApproveOpen(false), []);

  const list = useQuery({
    queryKey: ["makeup-plans", semesterId ?? "varsayilan"],
    queryFn: () => makeupPlanApi.list(semesterId),
  });
  const plans = useMemo(() => list.data?.plans ?? [], [list.data]);
  const currentId = selectedId ?? plans[0]?.id ?? null;
  const detail = useQuery({
    queryKey: ["makeup-plan", currentId],
    queryFn: () => makeupPlanApi.get(currentId as number),
    enabled: currentId !== null,
  });
  const plan = currentId !== null ? detail.data : undefined;

  /** İşlem uçları takvimin güncel hâlini döner: önbelleğe yaz, bağlı listeleri tazele. */
  const yerlestir = (guncel: MakeupPlan) => {
    qc.setQueryData(["makeup-plan", guncel.id], guncel);
    void qc.invalidateQueries({ queryKey: ["makeup-plans"] });
    void qc.invalidateQueries({ queryKey: ["makeup-absences"] });
  };

  const create = useMutation({
    mutationFn: (values: PlanFormValues) =>
      makeupPlanApi.create({ ...values, semester_id: list.data?.semester_id ?? 0 }),
    onSuccess: (yeni) => {
      yerlestir(yeni);
      setSelectedId(yeni.id);
      setFormOpen(null);
      snackbar.success("Mazeret takvimi oluşturuldu ve sınavlar yerleştirildi.");
    },
    onError: (e) => snackbar.error(hata(e, "Mazeret takvimi oluşturulamadı.")),
  });
  const update = useMutation({
    mutationFn: (values: PlanFormValues) => makeupPlanApi.update(currentId as number, values),
    onSuccess: (guncel) => {
      yerlestir(guncel);
      setFormOpen(null);
      snackbar.success("Parametreler kaydedildi; sınavlar yeniden yerleştirildi.");
    },
    onError: (e) => snackbar.error(hata(e, "Parametreler kaydedilemedi.")),
  });
  const replace = useMutation({
    mutationFn: () => makeupPlanApi.replace(currentId as number),
    onSuccess: (guncel) => {
      yerlestir(guncel);
      snackbar.success("Sınavlar yeniden yerleştirildi; sabitlediklerinize dokunulmadı.");
    },
    onError: (e) => snackbar.error(hata(e, "Yeniden yerleştirilemedi.")),
  });
  const sync = useMutation({
    mutationFn: () => makeupPlanApi.sync(currentId as number),
    onSuccess: (guncel) => {
      yerlestir(guncel);
      snackbar.success(`${guncel.result.added} kayıt takvime eklendi.`);
    },
    onError: (e) => snackbar.error(hata(e, "Kayıtlar güncellenemedi.")),
  });
  const approve = useMutation({
    mutationFn: () => makeupPlanApi.approve(currentId as number, approvedBy.trim()),
    onSuccess: (guncel) => {
      yerlestir(guncel);
      setApproveOpen(false);
      setApprovedBy("");
      snackbar.success("Mazeret takvimi onaylandı.");
    },
    onError: (e) => snackbar.error(hata(e, "Mazeret takvimi onaylanamadı.")),
  });
  const reopen = useMutation({
    mutationFn: () => makeupPlanApi.reopen(currentId as number),
    onSuccess: (guncel) => {
      yerlestir(guncel);
      snackbar.success("Mazeret takvimi taslağa alındı.");
    },
    onError: (e) => snackbar.error(hata(e, "Takvim yeniden açılamadı.")),
  });
  const sessions = useMutation({
    mutationFn: () => makeupPlanApi.createSessions(currentId as number),
    onSuccess: (guncel) => {
      yerlestir(guncel);
      void qc.invalidateQueries({ queryKey: ["exam-sessions"] });
      const adet = guncel.result.created.length;
      snackbar.success(
        adet > 0
          ? `${adet} mazeret oturumu oluşturuldu; salon ve dağıtımı oturum sayfasından tamamlayın.`
          : "Oluşturulacak yeni oturum yok; bütün sınavların oturumu zaten var.",
      );
    },
    onError: (e) => snackbar.error(hata(e, "Oturumlar oluşturulamadı.")),
  });
  const removePlan = useMutation({
    mutationFn: () => makeupPlanApi.remove(currentId as number),
    onSuccess: () => {
      setSelectedId(null);
      void qc.invalidateQueries({ queryKey: ["makeup-plans"] });
      void qc.invalidateQueries({ queryKey: ["makeup-absences"] });
      snackbar.success("Mazeret takvimi silindi; kayıtlar yeniden mazeret sınavı bekliyor.");
    },
    onError: (e) => snackbar.error(hata(e, "Takvim silinemedi.")),
  });
  const moveItem = useMutation({
    mutationFn: ({
      itemId,
      payload,
    }: {
      itemId: number;
      payload: { placed_date: string | null; period_no: number | null; is_pinned?: boolean };
    }) => makeupPlanApi.moveItem(itemId, payload),
    onSuccess: (guncel) => {
      yerlestir(guncel);
      setMoving(null);
      setMoveWarnings(guncel.result.warnings);
      snackbar.success("Sınavın yeri güncellendi.");
    },
    onError: (e) => snackbar.error(hata(e, "Sınav taşınamadı.")),
  });
  const removeItem = useMutation({
    mutationFn: (itemId: number) => makeupPlanApi.removeItem(itemId),
    onSuccess: (guncel) => {
      yerlestir(guncel);
      setMoving(null);
      snackbar.success("Sınav takvimden çıkarıldı; öğrencileri yeniden mazeret sınavı bekliyor.");
    },
    onError: (e) => snackbar.error(hata(e, "Sınav takvimden çıkarılamadı.")),
  });

  const indir = async (kind: MakeupPlanPdfKind) => {
    if (!plan) return;
    const names = kind === "liste" && !hideNames;
    setPdfBusy(kind);
    try {
      const blob = await makeupPlanApi.pdfBlob(plan.id, kind, names);
      const ek =
        kind === "ilan" ? null : names ? "Öğrenci Listesi" : "Öğrenci Listesi (okul numarasıyla)";
      saveBlob(blob, dosyaAdi([plan.name, ek], "pdf"));
    } catch (e) {
      snackbar.error(hata(e, "Belge üretilemedi."));
    } finally {
      setPdfBusy(null);
    }
  };

  if (list.isPending) return <SkeletonList rows={3} />;
  if (list.isError) {
    return (
      <p role="alert" className="text-body-medium text-error">
        Mazeret takvimleri yüklenemedi: {hata(list.error, "beklenmeyen hata.")}
      </p>
    );
  }

  const bekleyen = list.data.eligible_count;
  const taslak = plan?.status === "DRAFT";
  const mesgul =
    replace.isPending ||
    sync.isPending ||
    approve.isPending ||
    reopen.isPending ||
    sessions.isPending;
  const yerlesik = (plan?.items ?? []).filter((i) => i.placed_date !== null);
  const konmamis = (plan?.items ?? []).filter((i) => i.placed_date === null);
  const oturumsuz = yerlesik.filter((i) => i.session_id === null && i.student_count > 0);

  return (
    <div className="flex flex-col gap-4">
      <p className="text-body-medium text-on-surface-variant">
        Son sınav yapılıp yoklamalar girildikten sonra, mazereti kabul edilen öğrencilerin gireceği
        sınavlar için ayrı bir takvim kurun. Bu takvimde yalnız mazeret sınavları yer alır; sıra
        asıl sınav takvimini izler. Aynı saate düşen sınavlar tek mazeret oturumunda toplanır.
      </p>

      <div className="flex flex-wrap items-end gap-3">
        {plans.length > 0 && (
          <Select
            label="Mazeret takvimi"
            options={plans.map((p) => ({
              value: String(p.id),
              label: `${p.name} (${p.status_label})`,
            }))}
            value={currentId === null ? "" : String(currentId)}
            onChange={(e) => {
              setSelectedId(Number(e.target.value));
              setMoveWarnings([]);
            }}
            className="w-[28rem] max-w-full"
          />
        )}
        <span className="text-body-small text-on-surface-variant">
          {bekleyen > 0
            ? `Takvime alınmayı bekleyen ${bekleyen} mazeretli kayıt var.`
            : "Takvime alınmayı bekleyen mazeretli kayıt yok."}
        </span>
        <span className="ml-auto" />
        <Button icon="add" onClick={() => setFormOpen("new")} disabled={bekleyen === 0}>
          Yeni mazeret takvimi
        </Button>
      </div>

      {plans.length === 0 && (
        <EmptyState
          icon="event_note"
          title="Henüz mazeret takvimi yok"
          description="Önce Kayıtlar sekmesinde mazeret kararlarını tamamlayın; “Mazeretli” öğrenciler takvime kendiliğinden alınır."
        />
      )}

      {currentId !== null && detail.isPending && <SkeletonList rows={4} />}
      {detail.isError && (
        <p role="alert" className="text-body-medium text-error">
          Mazeret takvimi yüklenemedi: {hata(detail.error, "beklenmeyen hata.")}
        </p>
      )}

      {plan && (
        <>
          <Card elevation={1} className="flex flex-col gap-3 p-4">
            <div className="flex flex-wrap items-center gap-2">
              <h2 className="text-title-large text-on-surface">{plan.name}</h2>
              <span
                className={`rounded-full px-3 py-1 text-label-small ${
                  taslak
                    ? "bg-surface-container-high text-on-surface-variant"
                    : "bg-primary-container text-on-primary-container"
                }`}
              >
                {plan.status_label}
              </span>
            </div>
            <p className="text-body-medium text-on-surface-variant">{ozet(plan)}</p>
            <div className="flex flex-wrap items-center gap-2">
              {taslak ? (
                <>
                  <Button variant="tonal" icon="tune" onClick={() => setFormOpen("edit")}>
                    Parametreler
                  </Button>
                  <Button
                    variant="tonal"
                    icon="shuffle"
                    onClick={() => replace.mutate()}
                    disabled={mesgul}
                  >
                    Yeniden yerleştir
                  </Button>
                  {plan.unsynced_count > 0 && (
                    <Button
                      variant="tonal"
                      icon="sync"
                      onClick={() => sync.mutate()}
                      disabled={mesgul}
                    >
                      Kayıtları güncelle ({plan.unsynced_count})
                    </Button>
                  )}
                  <Button
                    icon="verified"
                    onClick={() => setApproveOpen(true)}
                    disabled={mesgul || plan.errors.length > 0 || yerlesik.length === 0}
                  >
                    Onayla
                  </Button>
                </>
              ) : (
                <>
                  <Button
                    icon="event_available"
                    onClick={() => sessions.mutate()}
                    disabled={mesgul || oturumsuz.length === 0}
                  >
                    Oturumları oluştur
                  </Button>
                  <Button
                    variant="tonal"
                    icon="lock_open"
                    onClick={() => reopen.mutate()}
                    disabled={mesgul}
                  >
                    Yeniden aç
                  </Button>
                </>
              )}
              <span className="ml-auto" />
              <Button
                variant="text"
                icon="picture_as_pdf"
                onClick={() => void indir("ilan")}
                disabled={pdfBusy !== null}
              >
                {pdfBusy === "ilan" ? "Hazırlanıyor…" : "Takvim (PDF)"}
              </Button>
              <Button
                variant="text"
                icon="groups"
                onClick={() => void indir("liste")}
                disabled={pdfBusy !== null}
              >
                {pdfBusy === "liste" ? "Hazırlanıyor…" : "Öğrenci listesi (PDF)"}
              </Button>
              {taslak && (
                <Button
                  variant="text"
                  icon="delete"
                  onClick={() => {
                    void confirm({
                      title: "Mazeret takvimi silinsin mi?",
                      message:
                        "Takvim ve yerleştirme silinir; öğrenci kayıtları yeniden mazeret sınavı bekleyen olur.",
                      confirmLabel: "Sil",
                    }).then((ok) => ok && removePlan.mutate());
                  }}
                >
                  Takvimi sil
                </Button>
              )}
            </div>
            <label className="flex min-h-9 cursor-pointer items-center gap-2 text-body-small text-on-surface-variant">
              <input
                type="checkbox"
                className="h-4 w-4 accent-primary"
                checked={hideNames}
                onChange={(e) => setHideNames(e.target.checked)}
              />
              Öğrenci listesinde adları gizle (yalnız okul numarası) — “Takvim (PDF)” zaten
              adsızdır, ilan için onu kullanın.
            </label>
          </Card>

          {plan.errors.length > 0 && (
            <ul role="alert" className="flex flex-col gap-1 text-body-medium text-error">
              {plan.errors.map((e) => (
                <li key={e}>{e}</li>
              ))}
            </ul>
          )}
          {plan.min_days !== null && (
            <p className="rounded-shape-sm bg-tertiary-container p-3 text-body-medium text-on-tertiary-container">
              Bütün sınavlar {plan.day_count} güne sığmadı. Bu kurallarla en az{" "}
              <strong>{plan.min_days} gün</strong> gerekir — “Parametreler”den gün sayısını artırın,
              günlük sınırı yükseltin ya da sıra kuralını gevşetin.
            </p>
          )}
          <UyariBandi
            title="Bu taşımanın doğurduğu uyarılar"
            messages={moveWarnings}
            onClose={() => setMoveWarnings([])}
          />
          {plan.warnings.length > 0 && (
            <div className="rounded-shape-sm bg-surface-container p-3">
              <h3 className="text-title-small text-on-surface">Uyarılar</h3>
              <ul className="mt-1 list-disc space-y-0.5 pl-5 text-body-small text-on-surface-variant">
                {plan.warnings.map((w) => (
                  <li key={w}>{w}</li>
                ))}
              </ul>
            </div>
          )}

          <Card elevation={1} className="overflow-x-auto p-0">
            <table className="w-full min-w-table border-collapse text-body-small">
              <caption className="sr-only">Mazeret sınavları yerleştirme çizelgesi</caption>
              <thead className="bg-surface-container-low text-left text-label-medium text-on-surface-variant">
                <tr>
                  <th scope="col" className="px-3 py-2">
                    Gün
                  </th>
                  {plan.periods.map((p) => (
                    <th key={p.no} scope="col" className="px-3 py-2">
                      {p.name}
                      {p.start && <span className="ml-1 font-normal">{p.start}</span>}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {plan.days.map((d) => (
                  <tr key={d.date} className="border-t border-outline-variant/50 align-top">
                    <th
                      scope="row"
                      className="whitespace-nowrap px-3 py-2 text-left text-on-surface"
                    >
                      {formatDate(d.date)}
                      <span className="block text-body-small font-normal text-on-surface-variant">
                        {d.weekday_label}
                      </span>
                    </th>
                    {plan.periods.map((p) => (
                      <td key={p.no} className="px-2 py-2">
                        <div className="flex flex-col gap-2">
                          {yerlesik
                            .filter((i) => i.placed_date === d.date && i.period_no === p.no)
                            .map((i) => (
                              <SinavKarti
                                key={i.id}
                                item={i}
                                editable={taslak}
                                onEdit={setMoving}
                              />
                            ))}
                        </div>
                      </td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          </Card>

          {konmamis.length > 0 && (
            <Card elevation={1} className="flex flex-col gap-2 p-4">
              <h3 className="text-title-medium text-on-surface">
                Takvime konmamış sınavlar ({konmamis.length})
              </h3>
              <ul className="flex flex-col gap-2">
                {konmamis.map((i) => (
                  <li key={i.id} className="grid gap-2 md:grid-cols-[18rem_1fr]">
                    <SinavKarti item={i} editable={taslak} onEdit={setMoving} />
                    <p className="text-body-small text-on-surface-variant">{i.note}</p>
                  </li>
                ))}
              </ul>
            </Card>
          )}
        </>
      )}

      {formOpen !== null && (
        <PlanFormDialog
          open
          onClose={closeForm}
          plan={formOpen === "edit" ? (plan ?? null) : null}
          allPeriods={list.data.all_periods}
          defaultPeriodNos={list.data.default_period_nos}
          maxDayCount={list.data.max_day_count}
          busy={create.isPending || update.isPending}
          onSubmit={(values) =>
            formOpen === "edit" ? update.mutate(values) : create.mutate(values)
          }
        />
      )}
      {plan && moving && (
        <MoveItemDialog
          open
          onClose={closeMove}
          plan={plan}
          item={moving}
          busy={moveItem.isPending || removeItem.isPending}
          onMove={(payload) => moveItem.mutate({ itemId: moving.id, payload })}
          onUnplace={() =>
            moveItem.mutate({ itemId: moving.id, payload: { placed_date: null, period_no: null } })
          }
          onRemove={() => {
            void confirm({
              title: "Sınav takvimden çıkarılsın mı?",
              message:
                "Bu sınavın öğrencileri yeniden mazeret sınavı bekleyen olur; başka bir takvime ya da elle açacağınız mazeret sınavına alınabilirler.",
              confirmLabel: "Çıkar",
            }).then((ok) => ok && removeItem.mutate(moving.id));
          }}
        />
      )}
      <Dialog
        open={approveOpen}
        onClose={closeApprove}
        title="Mazeret takvimi onaylansın mı?"
        actions={
          <>
            <Button variant="text" onClick={closeApprove}>
              Vazgeç
            </Button>
            <Button icon="verified" onClick={() => approve.mutate()} disabled={approve.isPending}>
              {approve.isPending ? "Onaylanıyor…" : "Onayla"}
            </Button>
          </>
        }
      >
        <div className="flex flex-col gap-3">
          <p className="text-body-medium text-on-surface">
            Onay takvimi kilitler ve belgelerdeki “TASLAK” yazısını kaldırır; ardından mazeret
            oturumlarını tek tıkla oluşturabilirsiniz.
          </p>
          <TextField
            label="Onaylayan"
            value={approvedBy}
            onChange={(e) => setApprovedBy(e.target.value)}
            helperText="Boş bırakılırsa okul müdürünün adı yazılır."
          />
        </div>
      </Dialog>
    </div>
  );
}
