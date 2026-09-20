// Oturum detayı (F3-F5): TASLAK'ta sihirbaz; sonrasında sekmeli paneller
// (Yerleşim + Gözetmenler + Sorular ve Kitapçıklar + Evrak + koşullu Yoklama) + yaşam
// döngüsü eylemleri (onayla → kilit; yeniden aç; arşivle → salt-okunur,
// evrak yeniden basılabilir). Onay İHLAL=0 şartına bağlıdır (backend approve
// guard'ı). OYS T11 OturumDetayPage'den UYARLANDI:
// - Rapor Merkezi'nin karşılığı Evrak (F4), Soru Yükleme'nin karşılığı
//   Sorular ve Kitapçıklar (F5); Gözetmenler sekmesi F7 ile geldi (kapalı
//   ayarda panel bilgi mesajı basar — sekme OYS gibi koşulsuz);
// - dönem etiketi `term_label` (OYS `semester_label` değil);
// - rota kökü `/oturumlar`. Yoklama yalnız ONAYLI/ARŞİV oturumda
//   (yerleşim kesinleşmeden yoklama açılmaz — OYS Tur 245 kuralı korunur).
//
// 18.09.2026 değerlendirmesi: "Onayla" artık onaylayan adını soran bir diyalogdan
// geçer (damga düşüren işlem — docs/sozluk.md §3) ve DAĞITILDI durumunda
// "Yeniden dağıt" vardır (kılavuzun yolladığı düğme eksikti).

import { useCallback, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useNavigate, useParams } from "react-router-dom";

import { ApiError } from "../../lib/api";
import Button from "../../ui/Button";
import Card from "../../ui/Card";
import { useConfirm } from "../../ui/ConfirmProvider";
import Dialog from "../../ui/Dialog";
import Icon from "../../ui/Icon";
import ModuleHeader from "../../ui/ModuleHeader";
import { SkeletonList } from "../../ui/Skeleton";
import Tabs, { tabPanelProps } from "../../ui/Tabs";
import TextField from "../../ui/TextField";
import { useSnackbar } from "../../ui/SnackbarProvider";
import type { ExamSession } from "./api";
import { examSessionApi } from "./api";
import EvrakPaneli from "./EvrakPaneli";
import GozetmenlerPaneli from "./GozetmenlerPaneli";
import { formatDate, MakeupBadge, StatusBadge } from "./oturumEtiket";
import SinavSihirbazi from "./SinavSihirbazi";
import SorularPaneli from "./SorularPaneli";
import KurallarPaneli from "./KurallarPaneli";
import YenidenDagitDialog from "./YenidenDagitDialog";
import YerlesimPaneli from "./YerlesimPaneli";
import YoklamaPaneli from "./YoklamaPaneli";

export default function OturumDetayPage() {
  const { id } = useParams();
  const sessionId = Number(id);
  const navigate = useNavigate();
  const qc = useQueryClient();
  const snackbar = useSnackbar();
  const confirm = useConfirm();
  const [tab, setTab] = useState("yerlesim");
  const [approveOpen, setApproveOpen] = useState(false);
  const [approvedBy, setApprovedBy] = useState("");
  const [redistributeOpen, setRedistributeOpen] = useState(false);
  // Dialog odak efekti onClose kimliğine bağlı — sabit referans şart.
  const closeApprove = useCallback(() => setApproveOpen(false), []);
  const closeRedistribute = useCallback(() => setRedistributeOpen(false), []);

  const session = useQuery({
    queryKey: ["exam-session", sessionId],
    queryFn: () => examSessionApi.get(sessionId),
    enabled: Number.isFinite(sessionId),
  });

  // Oturum değişince ona BAĞLI sorgular da bayatlar: dağıtım/taslağa alma
  // yerleşimi ve gözetmen görevlendirmelerini siler. Önbellek 30 sn taze
  // sayıldığından (lib/queryClient) tazelenmezse panel eski yerleşimi gösterir.
  const refresh = () => {
    void qc.invalidateQueries({ queryKey: ["exam-session", sessionId] });
    void qc.invalidateQueries({ queryKey: ["exam-sessions"] });
    void qc.invalidateQueries({ queryKey: ["exam-seating", sessionId] });
    void qc.invalidateQueries({ queryKey: ["exam-proctors", sessionId] });
    void qc.invalidateQueries({ queryKey: ["exam-proctor-candidates", sessionId] });
    void qc.invalidateQueries({ queryKey: ["exam-participants", sessionId] });
    // Sorular ve Kitapçıklar sekmesi açıkken yeniden dağıtılırsa: bireysel soru
    // dosyası satırları salon/koltuk taşır, üretilmiş kitapçıklar "güncel değil"e döner.
    void qc.invalidateQueries({ queryKey: ["individual-questions", sessionId] });
    void qc.invalidateQueries({ queryKey: ["booklet-runs", sessionId] });
  };

  const TRANSITIONS = {
    reopen: examSessionApi.reopen,
    archive: examSessionApi.archive,
    revert: examSessionApi.revertToDraft,
  } as const;
  const TRANSITION_MESSAGES: Record<ExamSession["status"], string> = {
    DRAFT: "Oturum taslağa alındı — yerleşim silindi; sihirbazdan düzeltip yeniden dağıtın.",
    DISTRIBUTED: "Onay geri alındı — oturum yeniden düzenlenebilir.",
    APPROVED: "Oturum onaylandı — yerleşim kilitlendi.",
    ARCHIVED: "Oturum arşivlendi — salt okunur; evrak yeniden basılabilir.",
  };
  const transition = useMutation({
    mutationFn: (action: keyof typeof TRANSITIONS) => TRANSITIONS[action](sessionId),
    onSuccess: (updated) => {
      refresh();
      snackbar.success(TRANSITION_MESSAGES[updated.status]);
    },
    onError: (e) => snackbar.error(e instanceof ApiError ? e.message : "İşlem yapılamadı."),
  });

  // Onay ayrı mutasyondur: onaylayan adını taşır. Ad boşsa backend kurulumdaki
  // okul müdürünün adını damgalar (`services.approve_session`). Ret hâlinde
  // (kural ihlali) diyalog açık kalır — kullanıcı gerekçeyi snackbar'da okur.
  const approve = useMutation({
    mutationFn: () => examSessionApi.approve(sessionId, { approved_by_name: approvedBy.trim() }),
    onSuccess: (updated) => {
      setApproveOpen(false);
      setApprovedBy("");
      refresh();
      snackbar.success(TRANSITION_MESSAGES[updated.status]);
    },
    onError: (e) => snackbar.error(e instanceof ApiError ? e.message : "Oturum onaylanamadı."),
  });

  const removeDraft = useMutation({
    mutationFn: () => examSessionApi.remove(sessionId),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ["exam-sessions"] });
      snackbar.success("Taslak oturum silindi.");
      navigate("/oturumlar");
    },
    onError: (e) => snackbar.error(e instanceof ApiError ? e.message : "Silinemedi."),
  });

  if (session.isPending) {
    return <SkeletonList rows={4} />;
  }
  if (session.isError || !session.data) {
    return (
      <Card elevation={1} className="flex flex-col items-start gap-3 p-6">
        <p role="alert" className="text-body-medium text-error">
          Oturum yüklenemedi:{" "}
          {session.error instanceof ApiError ? session.error.message : "beklenmeyen hata."}
        </p>
        <Button variant="text" icon="arrow_back" onClick={() => navigate("/oturumlar")}>
          Oturum listesine dön
        </Button>
      </Card>
    );
  }
  const data = session.data;
  const isDraft = data.status === "DRAFT";
  const busy = transition.isPending || approve.isPending;

  // Yoklama yalnız ONAYLI/ARŞİV oturumda (yerleşim kesin olmalı).
  const attendanceOpen = data.status === "APPROVED" || data.status === "ARCHIVED";
  // Evrak DRAFT dışı her durumda (dağıtımdan itibaren; arşivden yeniden basım).
  const tabs = [
    { key: "yerlesim", label: "Yerleşim", icon: "grid_on" },
    { key: "kurallar", label: "Yerleştirme Kuralları", icon: "accessible" },
    { key: "gozetmenler", label: "Gözetmenler", icon: "supervisor_account" },
    { key: "sorular", label: "Sorular ve Kitapçıklar", icon: "description" },
    { key: "evrak", label: "Evrak", icon: "print" },
    ...(attendanceOpen ? [{ key: "yoklama", label: "Yoklama", icon: "person_off" }] : []),
  ];

  return (
    <div>
      <ModuleHeader
        backTo="/oturumlar"
        moduleLabel="Oturumlar"
        title={data.name}
        actions={
          <>
            {isDraft && (
              <Button
                variant="text"
                icon="delete"
                onClick={() => {
                  void confirm({
                    title: "Taslak silinsin mi?",
                    message: "Taslak oturum ve ders/salon tanımları kaldırılır (geri alınamaz).",
                    confirmLabel: "Sil",
                  }).then((ok) => ok && removeDraft.mutate());
                }}
              >
                Taslağı sil
              </Button>
            )}
            {data.status === "DISTRIBUTED" && (
              <>
                {/* Dağıtımdan sonra fark edilen tanım hatası (yanlış seviye/şube,
                    yanlışlıkla işaretlenmiş "aynı kitapçık") için sihirbaza dönüş yolu. */}
                <Button
                  variant="tonal"
                  icon="undo"
                  onClick={() => {
                    void confirm({
                      title: "Taslağa alınsın mı?",
                      message:
                        "Yerleşim ve gözetmen görevlendirmeleri silinir. Ders, şube ve salon seçimi, yerleştirme kuralları ve soru dosyaları korunur; sihirbazdan düzeltip yeniden dağıtırsınız.",
                      confirmLabel: "Taslağa al",
                    }).then((ok) => ok && transition.mutate("revert"));
                  }}
                  disabled={busy}
                >
                  Taslağa al
                </Button>
                {/* Tanımlar doğru, yalnız yerleşim beğenilmedi (ya da sonradan kural
                    eklendi): taslağa dönmeden yeni dağıtım. */}
                <Button
                  variant="tonal"
                  icon="shuffle"
                  onClick={() => setRedistributeOpen(true)}
                  disabled={busy}
                >
                  Yeniden dağıt
                </Button>
                <Button icon="verified" onClick={() => setApproveOpen(true)} disabled={busy}>
                  Onayla
                </Button>
              </>
            )}
            {data.status === "APPROVED" && (
              <>
                <Button
                  variant="tonal"
                  icon="lock_open"
                  onClick={() => transition.mutate("reopen")}
                  disabled={busy}
                >
                  Yeniden aç
                </Button>
                <Button
                  icon="archive"
                  onClick={() => {
                    void confirm({
                      title: "Arşivlensin mi?",
                      message:
                        "Arşiv geri dönüşsüzdür: oturum salt-okunur olur, evrak yeniden basılabilir.",
                      confirmLabel: "Arşivle",
                    }).then((ok) => ok && transition.mutate("archive"));
                  }}
                  disabled={busy}
                >
                  Arşivle
                </Button>
              </>
            )}
          </>
        }
      />
      <div className="mb-4 flex flex-wrap items-center gap-3">
        <span className="text-body-medium text-on-surface-variant">
          {formatDate(data.exam_date)} · {data.start_time.slice(0, 5)} · {data.term_label}
        </span>
        <StatusBadge status={data.status} />
        {data.is_makeup && <MakeupBadge />}
      </div>

      {(data.status === "DISTRIBUTED" || data.status === "APPROVED") && (
        <YerlesimSapmaBandi sessionId={data.id} />
      )}

      {isDraft ? (
        <SinavSihirbazi session={data} onChanged={refresh} />
      ) : (
        <div className="flex flex-col gap-4">
          <Tabs items={tabs} active={tab} onChange={setTab} idBase="oturum-detay" />
          <div {...tabPanelProps("oturum-detay", tab)}>
            {tab === "yerlesim" && <YerlesimPaneli session={data} />}
            {tab === "kurallar" && <KurallarPaneli sessionId={data.id} />}
            {tab === "gozetmenler" && <GozetmenlerPaneli session={data} />}
            {tab === "sorular" && <SorularPaneli session={data} />}
            {tab === "evrak" && <EvrakPaneli session={data} />}
            {tab === "yoklama" && attendanceOpen && <YoklamaPaneli session={data} />}
          </div>
        </div>
      )}

      {/* Onay damga düşürür ve yerleşimi kilitler → başlık soru, gövde sonuç. */}
      <Dialog
        open={approveOpen}
        onClose={closeApprove}
        title="Oturum onaylansın mı?"
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
          <p>Onay yerleşimi kilitler; yerleşimde kural ihlali varsa reddedilir.</p>
          <TextField
            label="Onaylayan (boş bırakılırsa okul müdürü)"
            value={approvedBy}
            onChange={(e) => setApprovedBy(e.target.value)}
            maxLength={128}
          />
        </div>
      </Dialog>

      {redistributeOpen ? (
        <YenidenDagitDialog
          sessionId={data.id}
          layoutMode={data.layout_mode}
          onClose={closeRedistribute}
          onDistributed={refresh}
        />
      ) : null}
    </div>
  );
}

/**
 * Dağıtımdan sonra katılımcılar değiştiyse uyarı bandı (19.09.2026).
 *
 * Seçmeli ders öğrenci listesi (e-Okul yeniden aktarıldı ya da elle düzeltildi),
 * öğrenci aktarımı veya nakil yerleşimden SONRA olursa yerleşim ve kitapçıklar
 * eski listeye göre kalır; backend yerleşim snapshot'ını güncel çözümle
 * karşılaştırıp `placement_outdated` döner. Sorgu yalnız dağıtılmış/onaylı
 * oturumda çalışır; bilgi yoksa bant çizilmez (sessiz başarı).
 */
function YerlesimSapmaBandi({ sessionId }: { sessionId: number }) {
  const katilimci = useQuery({
    queryKey: ["exam-participants", sessionId, "sapma"],
    queryFn: () => examSessionApi.participants(sessionId),
  });
  if (!katilimci.data?.placement_outdated) return null;
  return (
    <p
      role="status"
      className="mb-4 flex items-start gap-2 rounded-shape-sm bg-tertiary-container px-3 py-2 text-body-medium text-on-tertiary-container"
    >
      <Icon name="warning" size="lg" />
      <span>{katilimci.data.warnings[0]}</span>
    </p>
  );
}
