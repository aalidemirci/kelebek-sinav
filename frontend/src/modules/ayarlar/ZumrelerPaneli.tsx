// Ayarlar → Zümreler (bilgi girişi). Okul zümre başkanları kurulunu oluşturan
// sınıf/alan zümreleri burada tanımlanır; her zümrenin başkanı PERSONEL
// sicilinden seçilir. Sınav takvimi PDF'inin imza bloğu bu katalogdan beslenir
// (B7 revizyonu — "her ders bir zümre" varsayımı kalktı).
//
// 20.09.2026 (kullanıcı isteği): zümreler e-Okul öğretmen listesindeki BRANŞ
// bilgisinden üretilir ("Branşlardan zümre üret" — adaylar görülerek, seçilerek);
// elle ekleme/kaldırma serbest kalır. Her zümre branşlarını taşır ve başkan
// seçicisi YALNIZ o branşların öğretmenlerini listeler. Branşı tanımsız zümrede
// (ve "tüm öğretmenleri göster" açıkken) aday bütün aktif öğretmenlerdir. Branş
// eşleşmesi ANAHTAR üzerindendir (`Personnel.branch_key` ↔ `branch_keys`):
// harf büyüklüğü/şapka katlaması backend'dedir, burada yalnız eşitlik sorulur.
//
// Kalıp AyarlarPage'in hâkim kalıbıdır: react-query DEĞİL, useState + load().
// Personel adı backend'de ŞİFRELİ tutulur; liste ada göre DB'de sıralanamaz →
// seçici burada `localeCompare(…, "tr")` ile sıralar.

import { useCallback, useEffect, useMemo, useState } from "react";

import { ApiError } from "../../lib/api";
import Button from "../../ui/Button";
import Card from "../../ui/Card";
import { useConfirm } from "../../ui/ConfirmProvider";
import Dialog from "../../ui/Dialog";
import EmptyState from "../../ui/EmptyState";
import Icon from "../../ui/Icon";
import Select from "../../ui/Select";
import { SkeletonList } from "../../ui/Skeleton";
import { useSnackbar } from "../../ui/SnackbarProvider";
import TextField from "../../ui/TextField";
import { okulApi } from "../okul/api";
import type { BranchCandidate, Personnel, SubjectDepartment } from "../okul/api";

/** Personel seçeneği: "Ad SOYAD — Branş" (branş boşsa yalnız ad). */
function personnelLabel(person: Personnel): string {
  return person.branch ? `${person.full_name} — ${person.branch}` : person.full_name;
}

const CHECKBOX = "h-5 w-5 accent-primary";

/** Üretim sonucunun tek cümlelik özeti (snackbar). */
function uretimOzeti(created: number, linked: number): string {
  const parcalar: string[] = [];
  if (created > 0) parcalar.push(`${created} zümre oluşturuldu`);
  if (linked > 0) parcalar.push(`${linked} zümreye branşı bağlandı`);
  return parcalar.length > 0 ? `${parcalar.join(", ")}.` : "Üretilecek yeni zümre yok.";
}

export default function ZumrelerPaneli() {
  const [rows, setRows] = useState<SubjectDepartment[]>([]);
  const [personnel, setPersonnel] = useState<Personnel[]>([]);
  const [candidates, setCandidates] = useState<BranchCandidate[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [name, setName] = useState("");
  const [branchKey, setBranchKey] = useState("");
  const [head, setHead] = useState("");
  const [busy, setBusy] = useState(false);
  const [showAll, setShowAll] = useState(false);
  const [generateOpen, setGenerateOpen] = useState(false);
  const [editing, setEditing] = useState<SubjectDepartment | null>(null);
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
    // Branş adayları zümrelere göre değişir (NEW ↔ COVERED) — birlikte tazelenir.
    // Okunamazsa üretim düğmesi ve branş seçicisi boş kalır; zümre listesi çalışır.
    okulApi
      .listBranchCandidates()
      .then(setCandidates)
      .catch(() => setCandidates([]));
  }, []);
  useEffect(load, [load]);

  const yeniAdaySayisi = candidates.filter((c) => c.status !== "COVERED").length;

  /** Verilen branş anahtarlarının öğretmenleri; anahtar yoksa (ya da "tümü" açıksa) herkes. */
  const adaylar = useCallback(
    (keys: string[]): Personnel[] =>
      showAll || keys.length === 0
        ? personnel
        : personnel.filter((p) => p.branch_key !== "" && keys.includes(p.branch_key)),
    [personnel, showAll],
  );

  const ekle = async () => {
    if (!name.trim()) return;
    setBusy(true);
    try {
      const brans = candidates.find((c) => c.key === branchKey);
      await okulApi.createSubjectDepartment({
        name: name.trim(),
        head: head === "" ? null : Number(head),
        ...(brans ? { branches: [brans.name] } : {}),
      });
      snackbar.success("Zümre eklendi.");
      setName("");
      setHead("");
      setBranchKey("");
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
  const bosSecenek = { value: "", label: "— yok —" };

  /**
   * Satırın kendi seçenek listesi: zümrenin branşlarındaki öğretmenler. Kayıtlı
   * başkan bu listede YOKSA seçenek olarak eklenir — aksi hâlde `<select>`
   * eşleşmeyen değerde ilk seçeneği gösterir ve kayıtlı başkan "seçilmemiş" gibi
   * okunurdu. İki ayrı neden ayrı etiketlenir: başka branştan (aktif) öğretmen ya
   * da sicilde artık olmayan (pasif/silinmiş) kayıt.
   */
  const optionsForRow = (row: SubjectDepartment) => {
    const liste = adaylar(row.branch_keys ?? []);
    const secenekler = [
      bosSecenek,
      ...liste.map((p) => ({ value: String(p.id), label: personnelLabel(p) })),
    ];
    if (row.head === null || liste.some((p) => p.id === row.head)) return secenekler;
    const baskan = personnel.find((p) => p.id === row.head);
    return [
      ...secenekler,
      baskan
        ? { value: String(baskan.id), label: `${personnelLabel(baskan)} (başka branş)` }
        : { value: String(row.head), label: `${row.head_name || "—"} (listede yok)` },
    ];
  };

  // Ekleme formu: branş seçilirse başkan adayları o branşın öğretmenleridir.
  const eklemeAdaylari = adaylar(branchKey === "" ? [] : [branchKey]);
  const bransSecenekleri = [
    bosSecenek,
    ...candidates
      .filter((c) => c.status !== "COVERED")
      .map((c) => ({ value: c.key, label: c.name })),
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
        <div className="flex flex-wrap items-start justify-between gap-3">
          <p className="text-title-medium text-on-surface">Okul zümre başkanları kurulu</p>
          <Button
            variant="tonal"
            icon="auto_awesome"
            onClick={() => setGenerateOpen(true)}
            disabled={candidates.length === 0}
          >
            {yeniAdaySayisi > 0
              ? `Branşlardan zümre üret (${yeniAdaySayisi} yeni)`
              : "Branşlardan zümre üret"}
          </Button>
        </div>
        <p className="mt-1 text-body-medium text-on-surface-variant">
          Zümreler, öğretmen listesindeki <strong>branş</strong> bilgisinden üretilebilir; sonradan
          zümre ekleyebilir, kaldırabilir, bir zümrenin branşlarını değiştirebilirsiniz (örn. Tarih,
          Coğrafya ve Felsefe tek “Sosyal Bilimler” zümresinde). Zümre başkanı adayları zümrenin
          branşlarındaki aktif öğretmenlerdir. Sınav takvimi PDF'inin imza bölümünde hangi
          zümrelerin yer alacağını, takvimin Önizleme sekmesinde bu listeden seçersiniz.
        </p>
        {candidates.length === 0 && !loading && (
          <p className="mt-2 text-body-small text-on-surface-variant">
            Öğretmen listesinde branş bilgisi yok — branşlardan üretim için öğretmenleri Kişiler
            ekranından branşlarıyla aktarın.
          </p>
        )}

        <label className="mt-4 flex min-h-9 items-center gap-2 text-body-medium text-on-surface">
          <input
            type="checkbox"
            className={CHECKBOX}
            checked={showAll}
            onChange={(e) => setShowAll(e.target.checked)}
          />
          Başkan adaylarında tüm öğretmenleri göster
        </label>

        {loading ? (
          <SkeletonList rows={3} className="mt-4" />
        ) : rows.length === 0 ? (
          <div className="mt-2">
            <EmptyState
              compact
              icon="groups"
              title="Henüz zümre tanımlanmamış. Branşlardan üretin ya da aşağıdan ekleyin (örn. “Sosyal Bilimler”, “Matematik”)."
            />
          </div>
        ) : (
          <ul className="mt-2 space-y-2">
            {rows.map((row) => {
              const branslar = row.branches ?? [];
              return (
                <li
                  key={row.id}
                  className="grid grid-cols-1 items-center gap-3 rounded-shape-sm bg-surface-container px-4 py-3 sm:grid-cols-[minmax(0,1fr)_18rem_auto_auto]"
                >
                  <div className="min-w-0">
                    <span className="text-body-large text-on-surface">{row.name}</span>
                    <p className="flex flex-wrap items-center gap-x-2 text-body-small text-on-surface-variant">
                      <span>
                        {branslar.length > 0
                          ? `Branş: ${branslar.join(", ")}`
                          : "Branş tanımlı değil — başkan adayı tüm öğretmenler"}
                      </span>
                      <button
                        type="button"
                        className="font-medium text-primary underline-offset-2 hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary"
                        aria-label={`${row.name} zümresinin branşlarını düzenle`}
                        onClick={() => setEditing(row)}
                      >
                        Branşları düzenle
                      </button>
                    </p>
                  </div>
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
                      className={CHECKBOX}
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
              );
            })}
          </ul>
        )}

        <div className="mt-5 grid grid-cols-1 items-end gap-3 sm:grid-cols-[minmax(0,1fr)_14rem_18rem_auto]">
          <TextField
            label="Zümre adı"
            value={name}
            onChange={(e) => setName(e.target.value)}
            placeholder="Sosyal Bilimler"
          />
          <Select
            label="Branş"
            value={branchKey}
            onChange={(e) => {
              setBranchKey(e.target.value);
              setHead(""); // aday listesi değişir — eski seçim yeni listede olmayabilir
            }}
            options={bransSecenekleri}
          />
          <Select
            label="Zümre başkanı"
            value={head}
            onChange={(e) => setHead(e.target.value)}
            options={[
              bosSecenek,
              ...eklemeAdaylari.map((p) => ({ value: String(p.id), label: personnelLabel(p) })),
            ]}
            helperText={
              personnel.length === 0 ? "Öğretmen sicili boş — Kişiler ekranından ekleyin." : ""
            }
          />
          <Button icon="add" onClick={() => void ekle()} disabled={busy || !name.trim()}>
            Zümre ekle
          </Button>
        </div>
      </Card>

      {generateOpen && (
        <BranstanUretDialog
          candidates={candidates}
          onClose={() => setGenerateOpen(false)}
          onDone={(created, linked) => {
            setGenerateOpen(false);
            snackbar.success(uretimOzeti(created, linked));
            load();
          }}
        />
      )}

      {editing && (
        <BransDuzenleDialog
          department={editing}
          candidates={candidates}
          onClose={() => setEditing(null)}
          onSaved={() => {
            setEditing(null);
            snackbar.success(`“${editing.name}” zümresinin branşları güncellendi.`);
            load();
          }}
        />
      )}
    </div>
  );
}

/** Aday satırının durum notu — hangi zümreye bağlı olduğu söylenir (iç kod yok). */
function adayNotu(candidate: BranchCandidate): string {
  if (candidate.status === "COVERED") return `“${candidate.department_name}” zümresinde`;
  if (candidate.status === "LINKABLE")
    return `“${candidate.department_name}” zümresi var — branşı ona bağlanır`;
  return "yeni zümre";
}

/**
 * "Branşlardan zümre üret" penceresi: öğretmen sicilindeki branşlar durumlarıyla
 * listelenir; zümresi olmayanlar İŞARETLİ gelir, idareci istemediğini (örn.
 * sınav yapmayan bir branş) kaldırıp üretir. Branşı zaten bir zümrede olan satır
 * bilgi içindir, seçilemez.
 */
function BranstanUretDialog({
  candidates,
  onClose,
  onDone,
}: {
  candidates: BranchCandidate[];
  onClose: () => void;
  onDone: (created: number, linked: number) => void;
}) {
  const snackbar = useSnackbar();
  const secilebilir = useMemo(() => candidates.filter((c) => c.status !== "COVERED"), [candidates]);
  const [selected, setSelected] = useState<Set<string>>(
    () => new Set(candidates.filter((c) => c.status !== "COVERED").map((c) => c.key)),
  );
  const [busy, setBusy] = useState(false);

  const toggle = (key: string) =>
    setSelected((prev) => {
      const next = new Set(prev);
      if (next.has(key)) next.delete(key);
      else next.add(key);
      return next;
    });

  const uret = async () => {
    setBusy(true);
    try {
      const sonuc = await okulApi.generateDepartments([...selected]);
      onDone(sonuc.created.length, sonuc.linked.length);
    } catch (e) {
      snackbar.error(e instanceof ApiError ? e.message : "Zümreler üretilemedi.");
    } finally {
      setBusy(false);
    }
  };

  return (
    <Dialog
      open
      onClose={onClose}
      title="Branşlardan zümre üret"
      actions={
        <>
          <Button variant="text" onClick={onClose}>
            Vazgeç
          </Button>
          <Button onClick={() => void uret()} disabled={busy || selected.size === 0}>
            {busy ? "Üretiliyor…" : `Seçilenleri üret (${selected.size})`}
          </Button>
        </>
      }
    >
      <div className="flex flex-col gap-3">
        <p className="text-body-medium text-on-surface-variant">
          Aktif öğretmenlerin branşları aşağıdadır. İşaretli her branş için aynı adla bir zümre
          açılır ve branş o zümreye bağlanır. İstemediğiniz branşın işaretini kaldırın; zümreleri
          sonradan birleştirebilir, adını ya da branşlarını değiştirebilirsiniz.
        </p>
        {secilebilir.length === 0 && (
          <p className="text-body-medium text-on-surface">
            Bütün branşların zümresi var; üretilecek yeni zümre yok.
          </p>
        )}
        <ul className="flex max-h-[50vh] flex-col gap-1 overflow-y-auto">
          {candidates.map((candidate) => {
            const kapali = candidate.status === "COVERED";
            return (
              <li key={candidate.key}>
                <label
                  className={`flex min-h-9 items-center gap-3 rounded-shape-sm px-2 py-1 text-body-medium ${
                    kapali ? "text-on-surface-variant" : "text-on-surface"
                  }`}
                >
                  <input
                    type="checkbox"
                    className={CHECKBOX}
                    checked={!kapali && selected.has(candidate.key)}
                    disabled={kapali}
                    onChange={() => toggle(candidate.key)}
                  />
                  <span className="min-w-0 flex-1">{candidate.name}</span>
                  <span className="text-body-small text-on-surface-variant">
                    {candidate.teacher_count} öğretmen · {adayNotu(candidate)}
                  </span>
                </label>
              </li>
            );
          })}
        </ul>
      </div>
    </Dialog>
  );
}

/**
 * Bir zümrenin branşlarını düzenleme penceresi. Seçenekler öğretmen sicilindeki
 * branşlardır; başka bir zümreye bağlı branş seçilemez (bir branş en çok bir
 * zümrededir). Zümrenin sicilde artık karşılığı olmayan branşı listede kalır ki
 * kaydederken sessizce düşmesin.
 */
function BransDuzenleDialog({
  department,
  candidates,
  onClose,
  onSaved,
}: {
  department: SubjectDepartment;
  candidates: BranchCandidate[];
  onClose: () => void;
  onSaved: () => void;
}) {
  const snackbar = useSnackbar();
  // Seçenek = sicildeki branşlar + zümrenin sicilde olmayan kendi branşları.
  const secenekler = useMemo(() => {
    const mevcut = department.branches ?? [];
    const mevcutAnahtarlar = department.branch_keys ?? [];
    const sicilde = new Set(candidates.map((c) => c.key));
    const yetimler = mevcut
      .map((name, index) => ({ name, key: mevcutAnahtarlar[index] ?? name }))
      .filter((b) => !sicilde.has(b.key));
    return [
      ...candidates.map((c) => ({
        key: c.key,
        name: c.name,
        note: `${c.teacher_count} öğretmen`,
        // Başka zümredeki branş kilitlidir; bu zümrenin kendi branşı serbesttir.
        lockedBy:
          c.status === "COVERED" && c.department_id !== department.id ? c.department_name : "",
      })),
      ...yetimler.map((b) => ({ ...b, note: "öğretmen listesinde yok", lockedBy: "" })),
    ];
  }, [candidates, department]);

  const [selected, setSelected] = useState<Set<string>>(
    () => new Set(department.branch_keys ?? []),
  );
  const [busy, setBusy] = useState(false);

  const toggle = (key: string) =>
    setSelected((prev) => {
      const next = new Set(prev);
      if (next.has(key)) next.delete(key);
      else next.add(key);
      return next;
    });

  const kaydet = async () => {
    setBusy(true);
    try {
      await okulApi.updateSubjectDepartment(department.id, {
        branches: secenekler.filter((s) => selected.has(s.key)).map((s) => s.name),
      });
      onSaved();
    } catch (e) {
      snackbar.error(e instanceof ApiError ? e.message : "Branşlar kaydedilemedi.");
    } finally {
      setBusy(false);
    }
  };

  return (
    <Dialog
      open
      onClose={onClose}
      title={`Branşlar — ${department.name}`}
      actions={
        <>
          <Button variant="text" onClick={onClose}>
            Vazgeç
          </Button>
          <Button onClick={() => void kaydet()} disabled={busy}>
            {busy ? "Kaydediliyor…" : "Kaydet"}
          </Button>
        </>
      }
    >
      <div className="flex flex-col gap-3">
        <p className="text-body-medium text-on-surface-variant">
          Zümre başkanı adayları işaretlediğiniz branşların öğretmenlerinden listelenir. Hiç branş
          işaretlemezseniz aday bütün aktif öğretmenlerdir. Bir branş yalnız bir zümrede olabilir.
        </p>
        {secenekler.length === 0 && (
          <p className="text-body-medium text-on-surface">Öğretmen listesinde branş bilgisi yok.</p>
        )}
        <ul className="flex max-h-[50vh] flex-col gap-1 overflow-y-auto">
          {secenekler.map((secenek) => {
            const kilitli = secenek.lockedBy !== "";
            return (
              <li key={secenek.key}>
                <label
                  className={`flex min-h-9 items-center gap-3 rounded-shape-sm px-2 py-1 text-body-medium ${
                    kilitli ? "text-on-surface-variant" : "text-on-surface"
                  }`}
                >
                  <input
                    type="checkbox"
                    className={CHECKBOX}
                    checked={!kilitli && selected.has(secenek.key)}
                    disabled={kilitli}
                    onChange={() => toggle(secenek.key)}
                  />
                  <span className="min-w-0 flex-1">{secenek.name}</span>
                  <span className="text-body-small text-on-surface-variant">
                    {kilitli ? `“${secenek.lockedBy}” zümresinde` : secenek.note}
                  </span>
                </label>
              </li>
            );
          })}
        </ul>
      </div>
    </Dialog>
  );
}
