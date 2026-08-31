// Ayarlar → Şube Kümeleri. "Sayısal", "Eşit Ağırlık", "Dil" gibi kümeler
// tanımlanır ve şubeler bu kümelere TOPLUCA atanır; sınav sihirbazında küme
// çipiyle tek tıkla seçilirler.
//
// Sözleşme: küme YALNIZ seçim aracıdır. Küme kimliği hiçbir oturum kaydına
// yazılmaz — sihirbaz kümeyi yazma anında somut şube pk'lerine açar. Aksi
// hâlde küme sonradan değişince ONAYLANMIŞ oturumun katılımcısı geriye dönük
// kayardı (SNAPSHOT deseni + "aynı seed → aynı dağıtım").
//
// Bir şube EN ÇOK BİR kümededir (kullanıcı kararı 31.08.2026).
// Kalıp AyarlarPage'in hâkim kalıbıdır: react-query DEĞİL, useState + load().

import { useCallback, useEffect, useState } from "react";

import { ApiError } from "../../lib/api";
import Button from "../../ui/Button";
import Card from "../../ui/Card";
import { useConfirm } from "../../ui/ConfirmProvider";
import Icon from "../../ui/Icon";
import Select from "../../ui/Select";
import { SkeletonList } from "../../ui/Skeleton";
import { useSnackbar } from "../../ui/SnackbarProvider";
import TextField from "../../ui/TextField";
import { okulApi } from "../okul/api";
import type { ClassSection, ClassSectionGroup } from "../okul/api";

export default function SubeKumeleriPaneli() {
  const [gruplar, setGruplar] = useState<ClassSectionGroup[]>([]);
  const [subeler, setSubeler] = useState<ClassSection[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [name, setName] = useState("");
  const [busy, setBusy] = useState(false);
  const [secili, setSecili] = useState<number[]>([]);
  const [hedefGrup, setHedefGrup] = useState("");
  const snackbar = useSnackbar();
  const confirm = useConfirm();

  const load = useCallback(() => {
    setLoading(true);
    Promise.all([okulApi.listClassSectionGroups(), okulApi.listClassSections()])
      .then(([g, s]) => {
        setGruplar(g);
        setSubeler(s);
        setError(null);
      })
      .catch((e: unknown) =>
        setError(e instanceof ApiError ? e.message : "Şube kümeleri yüklenemedi."),
      )
      .finally(() => setLoading(false));
  }, []);
  useEffect(load, [load]);

  const ekle = async () => {
    if (!name.trim()) return;
    setBusy(true);
    try {
      await okulApi.createClassSectionGroup({ name: name.trim() });
      snackbar.success("Küme eklendi.");
      setName("");
      load();
    } catch (e) {
      snackbar.error(e instanceof ApiError ? e.message : "Küme eklenemedi.");
    } finally {
      setBusy(false);
    }
  };

  const sil = async (grup: ClassSectionGroup) => {
    const ok = await confirm({
      title: "Kümeyi kaldır",
      message: `'${grup.name}' kümesi kaldırılsın mı? Şubeler silinmez, yalnız kümesiz kalır.`,
      confirmLabel: "Kaldır",
    });
    if (!ok) return;
    try {
      await okulApi.deleteClassSectionGroup(grup.id);
      snackbar.success(`'${grup.name}' kaldırıldı.`);
      load();
    } catch (e) {
      snackbar.error(e instanceof ApiError ? e.message : "Küme kaldırılamadı.");
    }
  };

  const topluAta = async () => {
    if (secili.length === 0) return;
    setBusy(true);
    try {
      const { updated } = await okulApi.assignClassSectionGroup({
        section_ids: secili,
        group: hedefGrup === "" ? null : Number(hedefGrup),
      });
      snackbar.success(`${updated} şube güncellendi.`);
      setSecili([]);
      load();
    } catch (e) {
      snackbar.error(e instanceof ApiError ? e.message : "Şubeler güncellenemedi.");
    } finally {
      setBusy(false);
    }
  };

  const toggle = (id: number) =>
    setSecili((prev) => (prev.includes(id) ? prev.filter((x) => x !== id) : [...prev, id]));

  const grupSecenekleri = [
    { value: "", label: "— kümesiz —" },
    ...gruplar.map((g) => ({ value: String(g.id), label: g.name })),
  ];

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
        <p className="text-title-medium text-on-surface">Şube kümeleri</p>
        <p className="mt-1 text-body-medium text-on-surface-variant">
          Şubeleri "Sayısal", "Eşit Ağırlık", "Dil" gibi kümelere ayırın; sınav sihirbazında
          katılacak şubeleri tek tek işaretlemek yerine küme çipiyle topluca seçersiniz. Bir şube en
          çok bir kümede olur. Küme yalnız seçim kolaylığıdır — oturum kaydına küme değil, seçilen
          şubeler yazılır.
        </p>

        {loading ? (
          <SkeletonList rows={3} className="mt-4" />
        ) : gruplar.length === 0 ? (
          <p className="mt-4 text-body-medium text-on-surface-variant">
            Henüz küme tanımlanmamış. Aşağıdan ekleyin.
          </p>
        ) : (
          <ul className="mt-4 flex flex-wrap gap-2">
            {gruplar.map((g) => (
              <li
                key={g.id}
                className="flex items-center gap-1 rounded-shape-sm bg-surface-container px-3 py-1.5 text-body-medium text-on-surface"
              >
                {g.name}
                <span className="text-on-surface-variant"> ({g.section_count})</span>
                <button
                  type="button"
                  aria-label={`${g.name} kümesini kaldır`}
                  onClick={() => void sil(g)}
                  className="ml-1 flex h-6 w-6 items-center justify-center rounded-shape-xs text-on-surface-variant transition hover:bg-surface-container-high hover:text-error focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary"
                >
                  <Icon name="close" size="sm" />
                </button>
              </li>
            ))}
          </ul>
        )}

        <div className="mt-5 grid grid-cols-1 items-end gap-3 sm:grid-cols-[minmax(0,1fr)_auto]">
          <TextField
            label="Küme adı"
            value={name}
            onChange={(e) => setName(e.target.value)}
            placeholder="Sayısal"
          />
          <Button icon="add" onClick={() => void ekle()} disabled={busy || !name.trim()}>
            Küme ekle
          </Button>
        </div>
      </Card>

      <Card elevation={1} className="p-6">
        <p className="text-title-medium text-on-surface">Şubeleri kümeye ata</p>
        <p className="mt-1 text-body-medium text-on-surface-variant">
          Şubeleri işaretleyip aşağıdan kümeyi seçin. Tek tek düzenlemek yerine topluca atanır; "—
          kümesiz —" seçerek kümeden çıkarabilirsiniz.
        </p>

        {loading ? (
          <SkeletonList rows={4} className="mt-4" />
        ) : subeler.length === 0 ? (
          <p className="mt-4 text-body-medium text-on-surface-variant">
            Aktif ders yılında şube yok. Öğrenci listesi aktarınca şubeler kendiliğinden gelir.
          </p>
        ) : (
          <div className="mt-4 flex flex-wrap gap-x-5 gap-y-1">
            {subeler.map((s) => (
              <label
                key={s.id}
                className="flex min-h-9 items-center gap-2 text-body-medium text-on-surface"
              >
                <input
                  type="checkbox"
                  className="h-5 w-5 accent-primary"
                  checked={secili.includes(s.id)}
                  onChange={() => toggle(s.id)}
                />
                <span>
                  {s.class_label}
                  {s.group_name ? (
                    <span className="text-on-surface-variant"> · {s.group_name}</span>
                  ) : null}
                </span>
              </label>
            ))}
          </div>
        )}

        <div className="mt-5 grid grid-cols-1 items-end gap-3 sm:grid-cols-[18rem_auto_auto]">
          <Select
            label="Küme"
            value={hedefGrup}
            onChange={(e) => setHedefGrup(e.target.value)}
            options={grupSecenekleri}
          />
          <Button
            icon="playlist_add_check"
            onClick={() => void topluAta()}
            disabled={busy || secili.length === 0}
          >
            Seçilenleri ata ({secili.length})
          </Button>
          {secili.length > 0 ? (
            <Button variant="text" onClick={() => setSecili([])}>
              Seçimi temizle
            </Button>
          ) : null}
        </div>
      </Card>
    </div>
  );
}
