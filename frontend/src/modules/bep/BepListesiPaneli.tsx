// Kişiler → BEP sekmesi: BEP kapsamındaki öğrenciler listesi (20.09.2026).
//
// İdareci bu listeyi BİR KEZ kurar; her sınav oturumunda program o oturuma giren
// BEP kapsamındaki öğrencileri Sorular ve Kitapçıklar sekmesinde hatırlatır ve
// isterse öğrenciye bireysel soru dosyası uygulanır (`BireyselSorularBolumu`).
//
// KVKK md. 6 (özel nitelikli veriye işaret): liste YALNIZ üyelik tutar. Tanı,
// rapor, açıklama ya da serbest metin alanı BİLİNÇLE YOKTUR — bu ekrana öyle bir
// alan EKLEMEYİN. Onay ve bildirim metinlerinde öğrenci adı ve okul numarası
// geçmez ("Bu öğrenci…"): satır zaten gösteriyor.

import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { ApiError } from "../../lib/api";
import { formatNumber } from "../../lib/format";
import Autocomplete from "../../ui/Autocomplete";
import Button from "../../ui/Button";
import Card from "../../ui/Card";
import { useConfirm } from "../../ui/ConfirmProvider";
import DataTable from "../../ui/DataTable";
import type { Column } from "../../ui/DataTable";
import EmptyState from "../../ui/EmptyState";
import Icon from "../../ui/Icon";
import { SkeletonList } from "../../ui/Skeleton";
import { useSnackbar } from "../../ui/SnackbarProvider";
import type { Student } from "../okul/api";
import { okulApi } from "../okul/api";
import type { IepStudent } from "./api";
import { iepApi } from "./api";
import BepParolaUyarisi from "./BepParolaUyarisi";

export default function BepListesiPaneli() {
  const snackbar = useSnackbar();
  const confirm = useConfirm();
  const qc = useQueryClient();
  const [secilen, setSecilen] = useState<Student | null>(null);
  // Ekleme sonrası arama kutusu YENİDEN kurulur: Autocomplete seçilen öğrencinin
  // etiketini kendi sorgu metninde tutar; seçim dışarıdan boşaltılınca aynı
  // öğrenciyi yeniden arayıp listeyi açardı.
  const [aramaAnahtari, setAramaAnahtari] = useState(0);

  const liste = useQuery({ queryKey: ["iep-students"], queryFn: () => iepApi.list() });
  const satirlar = liste.data?.results ?? [];
  const listedekiler = new Set(satirlar.map((s) => s.student_id));

  const tazele = () => {
    void qc.invalidateQueries({ queryKey: ["iep-students"] });
    // Listeden çıkarma/silme oturumlardaki bireysel soru dosyalarını da siler;
    // o oturumların kitapçık üretimi "güncel değil"e döner.
    void qc.invalidateQueries({ queryKey: ["individual-questions"] });
    void qc.invalidateQueries({ queryKey: ["booklet-runs"] });
  };

  const ekle = useMutation({
    mutationFn: (studentId: number) => iepApi.add(studentId),
    onSuccess: () => {
      setSecilen(null);
      setAramaAnahtari((k) => k + 1);
      snackbar.success("Öğrenci listeye eklendi.");
      tazele();
    },
    onError: (e) => snackbar.error(e instanceof ApiError ? e.message : "Öğrenci eklenemedi."),
  });

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
      snackbar.success("BEP kayıtları silindi.");
      tazele();
    },
    onError: (e) => snackbar.error(e instanceof ApiError ? e.message : "BEP kayıtları silinemedi."),
  });

  const searchStudents = (q: string): Promise<Student[]> =>
    okulApi.listStudents({ search: q, onlyActive: true, limit: 20 }).then((p) => p.results);

  const columns: Column<IepStudent>[] = [
    { header: "Okul no", cell: (s) => s.student_number || "—" },
    { header: "Ad soyad", cell: (s) => s.full_name },
    { header: "Şube", cell: (s) => s.class_label || "—" },
    {
      header: "",
      align: "right",
      cell: (s) => (
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
                "Bu öğrenci BEP kapsamındaki öğrenciler listesinden çıkarılır; onaylanmamış " +
                "oturumlardaki bireysel soru dosyaları da silinir.",
              confirmLabel: "Çıkar",
            }).then((ok) => ok && cikar.mutate(s.id))
          }
        >
          Çıkar
        </Button>
      ),
    },
  ];

  return (
    <div className="space-y-[var(--ks-page-gap)]">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <p className="text-title-medium text-on-surface">BEP kapsamındaki öğrenciler</p>
          {liste.data && (
            <p className="text-body-small text-on-surface-variant">
              {formatNumber(satirlar.length)} öğrenci
            </p>
          )}
        </div>
        {/* KVKK düğmesi HER ZAMAN açıktır: liste boşken de onaylı/arşiv oturumlarda
            listeden çıkarılmış öğrencinin bireysel soru dosyası kalmış olabilir. */}
        <Button
          variant="text"
          icon="delete_forever"
          disabled={tumunuSil.isPending}
          onClick={() =>
            void confirm({
              title: "Tüm BEP kayıtları silinsin mi?",
              message:
                "Listedeki bütün öğrenciler ve bütün oturumlardaki bireysel soru dosyaları " +
                "kalıcı olarak silinir. Bu işlem geri alınamaz.",
              confirmLabel: "Sil",
            }).then((ok) => ok && tumunuSil.mutate())
          }
        >
          Tüm BEP kayıtlarını sil
        </Button>
      </div>

      <p className="max-w-4xl text-body-medium text-on-surface-variant">
        Bu liste yalnız hangi öğrencilerin BEP (bireyselleştirilmiş eğitim programı) kapsamında
        olduğunu tutar; <strong>tanı, rapor ya da açıklama kaydedilmez</strong>. Liste, sınav
        oturumlarında bu öğrencileri size hatırlatmak ve gerektiğinde bireysel soru dosyası
        uygulamak için kullanılır. Salon evrakında ve kitapçıklarda öğrenciyi ayıran hiçbir işaret
        basılmaz. Okuldan ayrılan ya da sicilden silinen öğrencinin kaydı kendiliğinden silinir.
      </p>

      <BepParolaUyarisi />

      <Card
        elevation={0}
        className="flex flex-wrap items-end gap-3 p-[var(--ks-panel-padding)] shadow-elevation-1"
      >
        <div className="min-w-60 flex-1">
          <Autocomplete<Student>
            key={aramaAnahtari}
            label="Öğrenci ekle"
            placeholder="Ad veya okul no…"
            selected={secilen}
            search={searchStudents}
            onSelect={setSecilen}
            onClear={() => setSecilen(null)}
            getLabel={(s) => `${s.full_name} (${s.student_number})`}
            getSublabel={(s) => s.class_label}
            getKey={(s) => s.id}
            getDisabled={(s) => (listedekiler.has(s.id) ? "zaten listede" : undefined)}
          />
        </div>
        <Button
          icon="person_add"
          disabled={secilen === null || ekle.isPending}
          onClick={() => secilen !== null && ekle.mutate(secilen.id)}
        >
          {ekle.isPending ? "Ekleniyor…" : "Listeye ekle"}
        </Button>
      </Card>

      {liste.isError && (
        <div
          role="alert"
          className="flex items-start gap-2 rounded-shape-sm bg-error-container px-4 py-3 text-body-medium text-on-error-container"
        >
          <Icon name="error" size="lg" />
          <span>
            {liste.error instanceof ApiError ? liste.error.message : "BEP listesi yüklenemedi."}
          </span>
        </div>
      )}

      {liste.isPending ? (
        <SkeletonList rows={3} />
      ) : liste.data === undefined ? null : satirlar.length === 0 ? (
        <EmptyState
          icon="assignment_ind"
          title="Listede öğrenci yok"
          description="BEP kapsamındaki öğrencileri yukarıdaki arama kutusundan ekleyin; sınav oturumlarında program bu öğrencileri size hatırlatır."
        />
      ) : (
        <DataTable<IepStudent> columns={columns} rows={satirlar} />
      )}
    </div>
  );
}
