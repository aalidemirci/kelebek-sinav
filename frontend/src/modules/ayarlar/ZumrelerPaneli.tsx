// Ayarlar → Zümreler (bilgi girişi). Okul zümre başkanları kurulunu oluşturan
// sınıf/alan zümreleri burada tanımlanır; her zümrenin başkanı PERSONEL
// sicilinden seçilir. Sınav takvimi PDF'inin imza bloğu bu katalogdan beslenir
// (B7 revizyonu — "her ders bir zümre" varsayımı kalktı).
//
// Kalıp AyarlarPage'in hâkim kalıbıdır: react-query DEĞİL, useState + load().
// Personel adı backend'de ŞİFRELİ tutulur; liste ada göre DB'de sıralanamaz →
// seçici burada `localeCompare(…, "tr")` ile sıralar.

import { useCallback, useEffect, useState } from "react";

import { ApiError } from "../../lib/api";
import Button from "../../ui/Button";
import Card from "../../ui/Card";
import { useConfirm } from "../../ui/ConfirmProvider";
import EmptyState from "../../ui/EmptyState";
import Icon from "../../ui/Icon";
import Select from "../../ui/Select";
import { SkeletonList } from "../../ui/Skeleton";
import { useSnackbar } from "../../ui/SnackbarProvider";
import TextField from "../../ui/TextField";
import { okulApi } from "../okul/api";
import type { Personnel, SubjectDepartment } from "../okul/api";

/** Personel seçeneği: "Ad SOYAD — Branş" (branş boşsa yalnız ad). */
function personnelLabel(person: Personnel): string {
  return person.branch ? `${person.full_name} — ${person.branch}` : person.full_name;
}

export default function ZumrelerPaneli() {
  const [rows, setRows] = useState<SubjectDepartment[]>([]);
  const [personnel, setPersonnel] = useState<Personnel[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [name, setName] = useState("");
  const [head, setHead] = useState("");
  const [busy, setBusy] = useState(false);
  const snackbar = useSnackbar();
  const confirm = useConfirm();

  useEffect(() => {
    // Yalnız AKTİF personel: ayrılan öğretmen zümre başkanı seçilemez.
    // limit=500 şart — DRF varsayılan sayfası 25'tir.
    okulApi
      .listPersonnel({ onlyActive: true, limit: 500 })
      .then((page) =>
        setPersonnel(
          [...page.results].sort((a, b) => a.full_name.localeCompare(b.full_name, "tr")),
        ),
      )
      .catch(() => setPersonnel([]));
  }, []);

  const load = useCallback(() => {
    setLoading(true);
    okulApi
      .listSubjectDepartments()
      .then((items) => {
        setRows(items);
        setError(null);
      })
      .catch((e: unknown) =>
        setError(e instanceof ApiError ? e.message : "Zümre listesi yüklenemedi."),
      )
      .finally(() => setLoading(false));
  }, []);
  useEffect(load, [load]);

  const ekle = async () => {
    if (!name.trim()) return;
    setBusy(true);
    try {
      await okulApi.createSubjectDepartment({
        name: name.trim(),
        head: head === "" ? null : Number(head),
      });
      snackbar.success("Zümre eklendi.");
      setName("");
      setHead("");
      load();
    } catch (e) {
      snackbar.error(e instanceof ApiError ? e.message : "Zümre eklenemedi.");
    } finally {
      setBusy(false);
    }
  };

  // Seçim anında kaydedilir ("Kaydet" düğmesi yok) — sessiz geçmesin diye her
  // iki satır içi değişiklik de kendi cümlesiyle bildirilir: seçici değişti ama
  // KAYDEDİLDİ Mİ sorusu ekranda yanıtsız kalıyordu.
  const baskanDegistir = async (row: SubjectDepartment, value: string) => {
    try {
      await okulApi.updateSubjectDepartment(row.id, { head: value === "" ? null : Number(value) });
      snackbar.success(
        value === ""
          ? `“${row.name}” zümresinin başkanı kaldırıldı.`
          : `“${row.name}” zümresinin başkanı güncellendi.`,
      );
      load();
    } catch (e) {
      snackbar.error(e instanceof ApiError ? e.message : "Zümre başkanı değiştirilemedi.");
    }
  };

  const kurulDegistir = async (row: SubjectDepartment, value: boolean) => {
    try {
      await okulApi.updateSubjectDepartment(row.id, { is_board_member: value });
      snackbar.success(
        value ? `“${row.name}” kurula eklendi.` : `“${row.name}” kuruldan çıkarıldı.`,
      );
      load();
    } catch (e) {
      snackbar.error(e instanceof ApiError ? e.message : "Kurul üyeliği değiştirilemedi.");
    }
  };

  const sil = async (row: SubjectDepartment) => {
    const ok = await confirm({
      title: "Zümre kaldırılsın mı?",
      message: `“${row.name}” zümresi listeden kalkar ve daha önce seçildiği takvimlerin imza bloğundan da düşer. Öğretmen kayıtları etkilenmez.`,
      confirmLabel: "Kaldır",
    });
    if (!ok) return;
    try {
      await okulApi.deleteSubjectDepartment(row.id);
      snackbar.success(`“${row.name}” kaldırıldı.`);
      load();
    } catch (e) {
      snackbar.error(e instanceof ApiError ? e.message : "Zümre kaldırılamadı.");
    }
  };

  // Boş seçenek tek biçim: "— yok —" (docs/sozluk.md §3).
  const personnelOptions = [
    { value: "", label: "— yok —" },
    ...personnel.map((p) => ({ value: String(p.id), label: personnelLabel(p) })),
  ];

  /**
   * Satırın kendi seçenek listesi: mevcut başkan aday listesinde YOKSA (kayıt
   * pasifleştirilmiş ya da silinmişse) seçenek olarak eklenir. Aksi hâlde
   * `<select>` eşleşmeyen değerde ilk seçeneği gösterir ve kayıtlı başkan
   * "seçilmemiş" gibi okunurdu.
   */
  const optionsForRow = (row: SubjectDepartment) =>
    row.head !== null && !personnel.some((p) => p.id === row.head)
      ? [
          ...personnelOptions,
          { value: String(row.head), label: `${row.head_name || "—"} (listede yok)` },
        ]
      : personnelOptions;

  return (
    <div className="space-y-6">
      {error && (
        <div
          role="alert"
          className="flex items-start gap-2 rounded-shape-sm bg-error-container px-4 py-3 text-body-medium text-on-error-container"
        >
          <Icon name="error" size="lg" />
          <span>{error}</span>
        </div>
      )}

      <Card elevation={1} className="p-6">
        <p className="text-title-medium text-on-surface">Okul zümre başkanları kurulu</p>
        <p className="mt-1 text-body-medium text-on-surface-variant">
          Okulunuzda kurulan sınıf/alan zümrelerini ve başkanlarını buraya girin. Sınav takvimi
          PDF'inin imza bölümünde hangi zümrelerin yer alacağını, takvimin Önizleme sekmesinde bu
          listeden seçersiniz. Zümre başkanı adayları öğretmen sicilindeki aktif kayıtlardır.
        </p>

        {loading ? (
          <SkeletonList rows={3} className="mt-4" />
        ) : rows.length === 0 ? (
          <div className="mt-2">
            <EmptyState
              compact
              icon="groups"
              title="Henüz zümre tanımlanmamış. Aşağıdan ekleyin (örn. “Sosyal Bilimler”, “Matematik”)."
            />
          </div>
        ) : (
          <ul className="mt-4 space-y-2">
            {rows.map((row) => (
              <li
                key={row.id}
                className="grid grid-cols-1 items-center gap-3 rounded-shape-sm bg-surface-container px-4 py-3 sm:grid-cols-[minmax(0,1fr)_18rem_auto_auto]"
              >
                <span className="text-body-large text-on-surface">{row.name}</span>
                <Select
                  label=""
                  aria-label={`${row.name} zümre başkanı`}
                  value={row.head === null ? "" : String(row.head)}
                  onChange={(e) => void baskanDegistir(row, e.target.value)}
                  options={optionsForRow(row)}
                />
                <label className="flex min-h-9 items-center gap-2 text-body-medium text-on-surface">
                  <input
                    type="checkbox"
                    className="h-5 w-5 accent-primary"
                    checked={row.is_board_member}
                    onChange={(e) => void kurulDegistir(row, e.target.checked)}
                  />
                  Kurulda
                </label>
                <Button
                  variant="text"
                  icon="delete"
                  aria-label={`${row.name} zümresini kaldır`}
                  onClick={() => void sil(row)}
                >
                  Kaldır
                </Button>
              </li>
            ))}
          </ul>
        )}

        <div className="mt-5 grid grid-cols-1 items-end gap-3 sm:grid-cols-[minmax(0,1fr)_18rem_auto]">
          <TextField
            label="Zümre adı"
            value={name}
            onChange={(e) => setName(e.target.value)}
            placeholder="Sosyal Bilimler"
          />
          <Select
            label="Zümre başkanı"
            value={head}
            onChange={(e) => setHead(e.target.value)}
            options={personnelOptions}
            helperText={
              personnel.length === 0 ? "Öğretmen sicili boş — Kişiler ekranından ekleyin." : ""
            }
          />
          <Button icon="add" onClick={() => void ekle()} disabled={busy || !name.trim()}>
            Zümre ekle
          </Button>
        </div>
      </Card>
    </div>
  );
}
