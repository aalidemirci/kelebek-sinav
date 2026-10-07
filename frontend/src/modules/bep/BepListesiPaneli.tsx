// Kişiler → "BEP ve tedbirler" sekmesi (20.09.2026 BEP listesi; tedbirler 07.10.2026).
//
// İdareci listeyi BİR KEZ kurar. Satır iki işe yarar:
// - Gerekçesi BEP ise her sınav oturumunda program öğrenciyi Sorular ve Kitapçıklar
//   sekmesinde hatırlatır ve istenirse bireysel soru dosyası uygulanır
//   (`BireyselSorularBolumu`).
// - Kalıcı sınav tedbiri varsa (kullanıcı isteği 07.10.2026 — ayrı salon, ek süre,
//   kendi sınıfında, okuyucu, yazıcı…) YER tedbiri her oturumda yerleştirme kuralı
//   olarak uygulanır; ek süre ve destek yalnız idare özetine basılır. Gerekçeyle
//   herkes girebilir (BEP / engel durumu / sağlık / diğer — kullanıcı kararı).
//
// KVKK md. 6 (özel nitelikli veriye işaret): gerekçe YALNIZ kategoridir; tanı, rapor,
// açıklama ya da serbest metin alanı BİLİNÇLE YOKTUR — bu ekrana öyle bir alan
// EKLEMEYİN. Onay ve bildirim metinlerinde öğrenci adı ve okul numarası geçmez
// ("Bu öğrenci…"): satır zaten gösteriyor.

import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { ApiError } from "../../lib/api";
import { formatNumber } from "../../lib/format";
import Button from "../../ui/Button";
import { useConfirm } from "../../ui/ConfirmProvider";
import DataTable from "../../ui/DataTable";
import type { Column } from "../../ui/DataTable";
import EmptyState from "../../ui/EmptyState";
import Icon from "../../ui/Icon";
import { SkeletonList } from "../../ui/Skeleton";
import { useSnackbar } from "../../ui/SnackbarProvider";
import type { IepStudent } from "./api";
import { iepApi } from "./api";
import BepParolaUyarisi from "./BepParolaUyarisi";
import TedbirDialog from "./TedbirDialog";

export default function BepListesiPaneli() {
  const snackbar = useSnackbar();
  const confirm = useConfirm();
  const qc = useQueryClient();
  // null → kapalı; "yeni" → ekleme; satır → o satırın tedbirleri.
  const [pencere, setPencere] = useState<IepStudent | "yeni" | null>(null);

  const liste = useQuery({ queryKey: ["iep-students"], queryFn: () => iepApi.list() });
  const satirlar = liste.data?.results ?? [];

  const tazele = () => {
    void qc.invalidateQueries({ queryKey: ["iep-students"] });
    // Listeden çıkarma/silme oturumlardaki bireysel soru dosyalarını da siler;
    // o oturumların kitapçık üretimi "güncel değil"e döner. Tedbir değişikliği
    // oturum panellerini de değiştirir.
    void qc.invalidateQueries({ queryKey: ["individual-questions"] });
    void qc.invalidateQueries({ queryKey: ["booklet-runs"] });
    void qc.invalidateQueries({ queryKey: ["session-accommodations"] });
  };

  const cikar = useMutation({
    mutationFn: (id: number) => iepApi.remove(id),
    onSuccess: () => {
      snackbar.success("Öğrenci listeden çıkarıldı.");
      tazele();
    },
    onError: (e) => snackbar.error(e instanceof ApiError ? e.message : "Öğrenci çıkarılamadı."),
  });

  const tumunuSil = useMutation({
    mutationFn: () => iepApi.deleteAll(),
    onSuccess: () => {
      snackbar.success("BEP ve tedbir kayıtları silindi.");
      tazele();
    },
    onError: (e) => snackbar.error(e instanceof ApiError ? e.message : "Kayıtlar silinemedi."),
  });

  const columns: Column<IepStudent>[] = [
    { header: "Okul no", cell: (s) => s.student_number || "—" },
    { header: "Ad soyad", cell: (s) => s.full_name },
    { header: "Şube", cell: (s) => s.class_label || "—" },
    { header: "Gerekçe", cell: (s) => s.reason_label },
    {
      header: "Tedbirler",
      cell: (s) =>
        s.measures.length > 0 ? (
          <span className="text-on-surface">{s.measures.join(" · ")}</span>
        ) : (
          <span className="text-on-surface-variant">Tedbir yok</span>
        ),
    },
    {
      header: "",
      align: "right",
      cell: (s) => (
        <span className="inline-flex gap-1">
          <Button variant="text" icon="edit" onClick={() => setPencere(s)}>
            Düzenle
          </Button>
          <Button
            variant="text"
            icon="person_remove"
            disabled={cikar.isPending}
            onClick={() =>
              void confirm({
                // Başlık soru, gövde sonuç (docs/sozluk.md §3). Gövdede öğrenci adı
                // ve okul numarası GEÇMEZ — satır zaten gösteriyor.
                title: "Öğrenci listeden çıkarılsın mı?",
                message:
                  "Bu öğrencinin tedbirleri silinir ve öğrenci BEP kapsamındaki öğrenciler " +
                  "listesinden çıkar; onaylanmamış oturumlardaki bireysel soru dosyaları da silinir.",
                confirmLabel: "Çıkar",
              }).then((ok) => ok && cikar.mutate(s.id))
            }
          >
            Çıkar
          </Button>
        </span>
      ),
    },
  ];

  return (
    <div className="space-y-[var(--ks-page-gap)]">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <p className="text-title-medium text-on-surface">BEP ve sınav tedbirleri</p>
          {liste.data && (
            <p className="text-body-small text-on-surface-variant">
              {formatNumber(satirlar.length)} öğrenci
            </p>
          )}
        </div>
        <div className="flex flex-wrap gap-2">
          {/* KVKK düğmesi HER ZAMAN açıktır: liste boşken de onaylı/arşiv oturumlarda
              listeden çıkarılmış öğrencinin bireysel soru dosyası kalmış olabilir. */}
          <Button
            variant="text"
            icon="delete_forever"
            disabled={tumunuSil.isPending}
            onClick={() =>
              void confirm({
                title: "Tüm BEP ve tedbir kayıtları silinsin mi?",
                message:
                  "Listedeki bütün öğrenciler, tedbirleri ve bütün oturumlardaki bireysel soru " +
                  "dosyaları kalıcı olarak silinir. Bu işlem geri alınamaz.",
                confirmLabel: "Sil",
              }).then((ok) => ok && tumunuSil.mutate())
            }
          >
            Tüm kayıtları sil
          </Button>
          <Button icon="person_add" onClick={() => setPencere("yeni")}>
            Öğrenci ekle
          </Button>
        </div>
      </div>

      <p className="max-w-4xl text-body-medium text-on-surface-variant">
        Bu liste BEP (bireyselleştirilmiş eğitim programı) kapsamındaki öğrencileri ve sınavlarda
        tedbir uygulanacak öğrencileri tutar;{" "}
        <strong>tanı, rapor ya da açıklama kaydedilmez</strong>, gerekçe yalnız kategoridir. Yer
        tedbiri (kendi sınıfında, ayrı salon, ön sırada) her sınav oturumunda kendiliğinden
        uygulanır. Ek süre ile okuyucu ve yazıcı desteği yerleşimi değiştirmez; yalnız oturumun{" "}
        <strong>idare özetine</strong> basılır, gözetmene siz bildirirsiniz. Salon evrakında ve
        kitapçıklarda öğrenciyi ayıran hiçbir işaret basılmaz. Okuldan ayrılan ya da sicilden
        silinen öğrencinin kaydı kendiliğinden silinir.
      </p>

      <BepParolaUyarisi />

      {liste.isError && (
        <div
          role="alert"
          className="flex items-start gap-2 rounded-shape-sm bg-error-container px-4 py-3 text-body-medium text-on-error-container"
        >
          <Icon name="error" size="lg" />
          <span>
            {liste.error instanceof ApiError ? liste.error.message : "Liste yüklenemedi."}
          </span>
        </div>
      )}

      {liste.isPending ? (
        <SkeletonList rows={3} />
      ) : liste.data === undefined ? null : satirlar.length === 0 ? (
        <EmptyState
          icon="assignment_ind"
          title="Listede öğrenci yok"
          description="“Öğrenci ekle” ile BEP kapsamındaki ya da sınavda tedbir uygulanacak öğrencileri ekleyin; okul numaralarını yazarak toplu da ekleyebilirsiniz."
        />
      ) : (
        <DataTable<IepStudent> columns={columns} rows={satirlar} />
      )}

      {pencere !== null && (
        <TedbirDialog
          row={pencere === "yeni" ? null : pencere}
          listedStudentIds={new Set(satirlar.map((s) => s.student_id))}
          onClose={() => setPencere(null)}
          onSaved={() => {
            setPencere(null);
            tazele();
          }}
        />
      )}
    </div>
  );
}
