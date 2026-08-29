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

import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useNavigate, useParams } from "react-router-dom";

import { ApiError } from "../../lib/api";
import Button from "../../ui/Button";
import { useConfirm } from "../../ui/ConfirmProvider";
import ModuleHeader from "../../ui/ModuleHeader";
import Tabs, { tabPanelProps } from "../../ui/Tabs";
import { useSnackbar } from "../../ui/SnackbarProvider";
import { examSessionApi } from "./api";
import EvrakPaneli from "./EvrakPaneli";
import GozetmenlerPaneli from "./GozetmenlerPaneli";
import { formatDate, StatusBadge } from "./oturumEtiket";
import SinavSihirbazi from "./SinavSihirbazi";
import SorularPaneli from "./SorularPaneli";
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

  const session = useQuery({
    queryKey: ["exam-session", sessionId],
    queryFn: () => examSessionApi.get(sessionId),
    enabled: Number.isFinite(sessionId),
  });

  const refresh = () => {
    void qc.invalidateQueries({ queryKey: ["exam-session", sessionId] });
    void qc.invalidateQueries({ queryKey: ["exam-sessions"] });
  };

  const transition = useMutation({
    mutationFn: (action: "approve" | "reopen" | "archive") =>
      action === "approve"
        ? examSessionApi.approve(sessionId)
        : action === "reopen"
          ? examSessionApi.reopen(sessionId)
          : examSessionApi.archive(sessionId),
    onSuccess: (updated) => {
      refresh();
      snackbar.success(
        updated.status === "APPROVED"
          ? "Oturum onaylandı — yerleşim kilitlendi."
          : updated.status === "ARCHIVED"
            ? "Oturum arşivlendi (salt-okunur; yeniden basım açık)."
            : "Onay geri alındı — oturum yeniden düzenlenebilir.",
      );
    },
    onError: (e) => snackbar.error(e instanceof ApiError ? e.message : "İşlem yapılamadı."),
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
    return <p className="text-body-medium text-on-surface-variant">Oturum yükleniyor…</p>;
  }
  if (session.isError || !session.data) {
    return (
      <p role="alert" className="text-body-medium text-error">
        Oturum yüklenemedi:{" "}
        {session.error instanceof ApiError ? session.error.message : "beklenmeyen hata."}
      </p>
    );
  }
  const data = session.data;
  const isDraft = data.status === "DRAFT";

  // Yoklama yalnız ONAYLI/ARŞİV oturumda (yerleşim kesin olmalı).
  const attendanceOpen = data.status === "APPROVED" || data.status === "ARCHIVED";
  // Evrak DRAFT dışı her durumda (dağıtımdan itibaren; arşivden yeniden basım).
  const tabs = [
    { key: "yerlesim", label: "Yerleşim", icon: "grid_on" },
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
              <Button
                icon="verified"
                onClick={() => transition.mutate("approve")}
                disabled={transition.isPending}
              >
                Onayla
              </Button>
            )}
            {data.status === "APPROVED" && (
              <>
                <Button
                  variant="tonal"
                  icon="lock_open"
                  onClick={() => transition.mutate("reopen")}
                  disabled={transition.isPending}
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
                  disabled={transition.isPending}
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
      </div>

      {isDraft ? (
        <SinavSihirbazi session={data} onChanged={refresh} />
      ) : (
        <div className="flex flex-col gap-4">
          <Tabs items={tabs} active={tab} onChange={setTab} idBase="oturum-detay" />
          <div {...tabPanelProps("oturum-detay", tab)}>
            {tab === "yerlesim" && <YerlesimPaneli session={data} />}
            {tab === "gozetmenler" && <GozetmenlerPaneli session={data} />}
            {tab === "sorular" && <SorularPaneli session={data} />}
            {tab === "evrak" && <EvrakPaneli session={data} />}
            {tab === "yoklama" && attendanceOpen && <YoklamaPaneli session={data} />}
          </div>
        </div>
      )}
    </div>
  );
}
