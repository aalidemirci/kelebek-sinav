// Kişiler sayfası (DD kalıbından KS'ye) — öğrenci ve öğretmen sicillerinin tek
// ekranı. İki sekme; her sekmede arama/filtre + sayfalama, Dialog içinde elle
// ekleme-düzenleme-silme ve "e-Okul listesinden aktar" paneli (önizle → aktar).
// KVKK (tasarım §5): TCKN, veli ve demografi alanları bu programda HİÇ YOKTUR —
// kelebek dağıtımı ad-soyad + okul no + sınıf/şube üçlüsüyle çalışır.

import { useCallback, useEffect, useId, useRef, useState } from "react";

import { useFormErrors } from "../../hooks/useFormErrors";
import { ApiError } from "../../lib/api";
import { saveBlob } from "../../lib/download";
import { formatNumber } from "../../lib/format";
import type { Paginated } from "../../lib/pagination";
import Button from "../../ui/Button";
import Card from "../../ui/Card";
import { useConfirm } from "../../ui/ConfirmProvider";
import DataTable from "../../ui/DataTable";
import type { Column } from "../../ui/DataTable";
import Dialog from "../../ui/Dialog";
import EmptyState from "../../ui/EmptyState";
import Icon from "../../ui/Icon";
import Select from "../../ui/Select";
import { SkeletonList } from "../../ui/Skeleton";
import { useSnackbar } from "../../ui/SnackbarProvider";
import Tabs, { tabPanelProps } from "../../ui/Tabs";
import type { TabItem } from "../../ui/Tabs";
import TextField from "../../ui/TextField";
import {
  importCounts,
  okulApi,
  PERSONNEL_TEMPLATE_FILENAME,
  STUDENT_STATUS_TR,
  STUDENT_TEMPLATE_FILENAME,
} from "../okul/api";
import type {
  GradeLevelOption,
  ImportInput,
  ImportReport,
  Personnel,
  PersonnelWriteBody,
  Student,
  StudentStatus,
  StudentWriteBody,
} from "../okul/api";

/** Sayfa başına kayıt (CLAUDE.md §7 — liste uçları limit/offset, varsayılan 25). */
const PAGE_SIZE = 25;

const TABS: TabItem[] = [
  { key: "ogrenciler", label: "Öğrenciler", icon: "school" },
  { key: "personel", label: "Öğretmenler", icon: "badge" },
];

function emptyPage<T>(): Paginated<T> {
  return { count: 0, next: null, previous: null, results: [] };
}

/**
 * Boş dönen sayfa için geri düşülecek offset (yoksa null). Son sayfadaki tek kayıt
 * silinince liste boşalır; boş durumda sayfalama çubuğu basılmadığından kullanıcı
 * orada kilitlenirdi — bir önceki sayfaya düşülüp yeniden yüklenir.
 */
function geriDusulecekOffset<T>(result: Paginated<T>, offset: number): number | null {
  if (result.results.length > 0 || offset === 0) return null;
  return Math.max(0, offset - PAGE_SIZE);
}

/** Yazarken her tuşta istek atmamak için gecikmeli değer (300 ms). */
function useDebounced(value: string, delay = 300): string {
  const [debounced, setDebounced] = useState(value);
  useEffect(() => {
    const timer = setTimeout(() => setDebounced(value), delay);
    return () => clearTimeout(timer);
  }, [value, delay]);
  return debounced;
}

export default function KisilerPage() {
  const [active, setActive] = useState("ogrenciler");

  return (
    <div className="space-y-[var(--ks-page-gap)]">
      <div className="ks-page-header">
        <div>
          <h1 className="ks-page-title">Kişiler</h1>
          <p className="ks-page-description">
            Öğrenci ve öğretmen sicili. Kayıtlar e-Okul listesinden toplu aktarılabilir ya da tek
            tek girilebilir. TCKN ve veli bilgisi bu programda tutulmaz.
          </p>
        </div>
      </div>

      <Tabs
        items={TABS}
        active={active}
        onChange={setActive}
        ariaLabel="Kişiler bölümleri"
        idBase="kisiler"
      />

      <div {...tabPanelProps("kisiler", active)}>
        {active === "ogrenciler" ? <OgrencilerSekmesi /> : <PersonelSekmesi />}
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Ortak parçalar
// ---------------------------------------------------------------------------

/** Hata bandı canlı bölgedir: başarısız yükleme/kaydetme/silme ekran okuyucuya duyurulur. */
function ErrorBand({ message }: { message: string }) {
  return (
    <div
      role="alert"
      className="flex items-start gap-2 rounded-shape-sm bg-error-container px-4 py-3 text-body-medium text-on-error-container"
    >
      <Icon name="error" size="lg" />
      <span>{message}</span>
    </div>
  );
}

function PaginationBar({
  count,
  offset,
  onOffset,
}: {
  count: number;
  offset: number;
  onOffset: (next: number) => void;
}) {
  const from = count === 0 ? 0 : offset + 1;
  const to = Math.min(offset + PAGE_SIZE, count);
  return (
    <div className="flex flex-wrap items-center justify-between gap-2">
      <p className="text-body-small text-on-surface-variant">
        {formatNumber(from)}–{formatNumber(to)} / {formatNumber(count)} kayıt
      </p>
      <div className="flex gap-2">
        <Button
          variant="text"
          icon="chevron_left"
          onClick={() => onOffset(Math.max(0, offset - PAGE_SIZE))}
          disabled={offset === 0}
        >
          Önceki
        </Button>
        <Button
          variant="text"
          icon="chevron_right"
          onClick={() => onOffset(offset + PAGE_SIZE)}
          disabled={to >= count}
        >
          Sonraki
        </Button>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Öğrenciler sekmesi
// ---------------------------------------------------------------------------

function OgrencilerSekmesi() {
  const [searchInput, setSearchInput] = useState("");
  const search = useDebounced(searchInput);
  const [level, setLevel] = useState("");
  const [section, setSection] = useState("");
  const [offset, setOffset] = useState(0);
  const [page, setPage] = useState<Paginated<Student>>(emptyPage<Student>());
  const [levels, setLevels] = useState<GradeLevelOption[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [reloadKey, setReloadKey] = useState(0);
  const [editing, setEditing] = useState<Student | null>(null);
  const [creating, setCreating] = useState(false);

  const reload = useCallback(() => setReloadKey((k) => k + 1), []);

  // Sınıf seçicisi sicilden türetilir (kurulum öncesi lise varsayılanı döner).
  useEffect(() => {
    okulApi
      .getGradeLevels()
      .then((r) => setLevels(r.levels))
      .catch(() => setLevels([]));
  }, []);

  useEffect(() => {
    let cancelled = false;
    // Geri düşüşte iskelet ekranda kalır: araya boş-durum kartı girip yanıp sönmesin.
    let geriDusuluyor = false;
    setLoading(true);
    okulApi
      .listStudents({
        search,
        classLevel: level ? Number(level) : null,
        classSection: section,
        limit: PAGE_SIZE,
        offset,
      })
      .then((result) => {
        if (cancelled) return;
        const geri = geriDusulecekOffset(result, offset);
        if (geri !== null) {
          geriDusuluyor = true;
          setOffset(geri);
          return;
        }
        setPage(result);
        setError(null);
      })
      .catch((e: unknown) => {
        if (cancelled) return;
        setError(e instanceof ApiError ? e.message : "Öğrenci listesi yüklenemedi.");
      })
      .finally(() => {
        if (!cancelled && !geriDusuluyor) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [search, level, section, offset, reloadKey]);

  const columns: Column<Student>[] = [
    { header: "Okul no", cell: (s) => s.student_number || "—" },
    { header: "Ad soyad", cell: (s) => s.full_name },
    { header: "Sınıf", cell: (s) => s.class_label || "—" },
    { header: "Durum", cell: (s) => STUDENT_STATUS_TR[s.status] },
  ];

  return (
    <div className="space-y-[var(--ks-page-gap)]">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <p className="text-title-medium text-on-surface">Öğrenci sicili</p>
          {!loading && (
            <p className="text-body-small text-on-surface-variant">
              {formatNumber(page.count)} kayıt
            </p>
          )}
        </div>
        <Button icon="person_add" onClick={() => setCreating(true)}>
          Öğrenci ekle
        </Button>
      </div>

      <Card
        elevation={0}
        className="grid items-end gap-3 p-[var(--ks-panel-padding)] shadow-elevation-1 sm:grid-cols-[minmax(15rem,1fr)_10rem_7rem]"
      >
        <TextField
          className="min-w-60 flex-1"
          label="Ara"
          value={searchInput}
          onChange={(e) => {
            setSearchInput(e.target.value);
            setOffset(0);
          }}
          placeholder="Ad soyad veya okul no…"
        />
        <Select
          className="min-w-40"
          label="Sınıf"
          placeholder="Tümü"
          value={level}
          onChange={(e) => {
            setLevel(e.target.value);
            setOffset(0);
          }}
          options={levels.map((l) => ({ value: String(l.value), label: l.label }))}
        />
        <TextField
          className="w-32"
          label="Şube"
          value={section}
          onChange={(e) => {
            setSection(e.target.value);
            setOffset(0);
          }}
          placeholder="A"
        />
      </Card>

      {error && <ErrorBand message={error} />}

      {loading ? (
        <SkeletonList rows={5} />
      ) : page.results.length === 0 ? (
        <EmptyState
          icon="school"
          title="Gösterilecek öğrenci yok"
          description="Filtreleri değiştirin ya da aşağıdaki Excel şablonundan öğrenci aktarın."
        />
      ) : (
        <>
          <DataTable<Student>
            columns={columns}
            rows={page.results}
            onRowClick={(s) => setEditing(s)}
            rowLabel={(s) => `${s.full_name} kaydını düzenle`}
          />
          <PaginationBar count={page.count} offset={offset} onOffset={setOffset} />
        </>
      )}

      <ImportPanel kind="students" onImported={reload} />

      {(creating || editing !== null) && (
        <OgrenciFormDialog
          student={editing}
          levels={levels}
          onClose={() => {
            setCreating(false);
            setEditing(null);
          }}
          onSaved={() => {
            setCreating(false);
            setEditing(null);
            reload();
          }}
        />
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Öğrenci ekleme/düzenleme formu (Dialog)
// ---------------------------------------------------------------------------

function OgrenciFormDialog({
  student,
  levels,
  onClose,
  onSaved,
}: {
  /** null → yeni kayıt; dolu → düzenleme (silme yalnız bu durumda görünür). */
  student: Student | null;
  levels: GradeLevelOption[];
  onClose: () => void;
  onSaved: () => void;
}) {
  const [firstName, setFirstName] = useState(student?.first_name ?? "");
  const [lastName, setLastName] = useState(student?.last_name ?? "");
  const [studentNumber, setStudentNumber] = useState(student?.student_number ?? "");
  const [level, setLevel] = useState(
    student?.class_level == null ? "" : String(student.class_level),
  );
  const [section, setSection] = useState(student?.class_section ?? "");
  const [status, setStatus] = useState<StudentStatus>(student?.status ?? "ACTIVE");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const { errors, setFieldError, clearErrors, applyApiError } = useFormErrors();
  const snackbar = useSnackbar();
  const confirm = useConfirm();

  const submit = async () => {
    clearErrors();
    setError(null);
    if (!firstName.trim() || !lastName.trim()) {
      if (!firstName.trim()) setFieldError("first_name", "Ad zorunludur.");
      if (!lastName.trim()) setFieldError("last_name", "Soyad zorunludur.");
      return;
    }
    // Boş metin alanları backend'de "" olarak meşru; sayı alanı null olmalı.
    const body: StudentWriteBody = {
      first_name: firstName.trim(),
      last_name: lastName.trim(),
      student_number: studentNumber.trim(),
      class_level: level ? Number(level) : null,
      class_section: section.trim(),
      status,
    };
    setBusy(true);
    try {
      if (student) await okulApi.updateStudent(student.id, body);
      else await okulApi.createStudent(body);
      snackbar.success(student ? "Öğrenci güncellendi." : "Öğrenci eklendi.");
      onSaved();
    } catch (e) {
      applyApiError(e);
      setError(e instanceof ApiError ? e.message : "Öğrenci kaydedilemedi.");
      setBusy(false);
    }
  };

  const remove = async () => {
    if (!student) return;
    const ok = await confirm({
      message: `'${student.full_name}' sicilden silinsin mi? Kayıt geri alınabilir biçimde (soft delete) saklanır.`,
      confirmLabel: "Sil",
    });
    if (!ok) return;
    setBusy(true);
    setError(null);
    try {
      await okulApi.deleteStudent(student.id);
      snackbar.success("Öğrenci silindi.");
      onSaved();
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Öğrenci silinemedi.");
      setBusy(false);
    }
  };

  return (
    <Dialog
      open
      wide
      onClose={onClose}
      title={student ? "Öğrenciyi düzenle" : "Yeni öğrenci"}
      actions={
        <>
          {student && (
            <Button variant="text" icon="delete" onClick={remove} disabled={busy}>
              Sil
            </Button>
          )}
          <Button variant="text" onClick={onClose} disabled={busy}>
            Vazgeç
          </Button>
          <Button icon="check" onClick={submit} disabled={busy}>
            {busy ? "Kaydediliyor…" : "Kaydet"}
          </Button>
        </>
      }
    >
      <div className="space-y-4">
        {error && <ErrorBand message={error} />}

        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
          <TextField
            label="Ad"
            required
            value={firstName}
            onChange={(e) => setFirstName(e.target.value)}
            error={errors.first_name}
          />
          <TextField
            label="Soyad"
            required
            value={lastName}
            onChange={(e) => setLastName(e.target.value)}
            error={errors.last_name}
          />
          <TextField
            label="Okul no"
            value={studentNumber}
            onChange={(e) => setStudentNumber(e.target.value)}
            error={errors.student_number}
            helperText="İçe aktarma bu numarayla eşleştirir; aktif kayıtlar arasında tekildir."
          />
          <Select
            label="Sınıf"
            placeholder="Sınıfsız"
            value={level}
            onChange={(e) => setLevel(e.target.value)}
            options={levels.map((l) => ({ value: String(l.value), label: l.label }))}
            error={errors.class_level}
          />
          <TextField
            label="Şube"
            value={section}
            onChange={(e) => setSection(e.target.value)}
            error={errors.class_section}
            helperText="Türkçe harfler ASCII'ye katlanır (ş → S)."
          />
          <Select
            label="Durum"
            value={status}
            onChange={(e) => setStatus(e.target.value as StudentStatus)}
            options={(Object.entries(STUDENT_STATUS_TR) as [string, string][]).map(
              ([value, label]) => ({ value, label }),
            )}
            error={errors.status}
          />
        </div>
      </div>
    </Dialog>
  );
}

// ---------------------------------------------------------------------------
// Personel sekmesi
// ---------------------------------------------------------------------------

function PersonelSekmesi() {
  const [searchInput, setSearchInput] = useState("");
  const search = useDebounced(searchInput);
  const [offset, setOffset] = useState(0);
  const [page, setPage] = useState<Paginated<Personnel>>(emptyPage<Personnel>());
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [reloadKey, setReloadKey] = useState(0);
  const [editing, setEditing] = useState<Personnel | null>(null);
  const [creating, setCreating] = useState(false);

  const reload = useCallback(() => setReloadKey((k) => k + 1), []);

  useEffect(() => {
    let cancelled = false;
    let geriDusuluyor = false;
    setLoading(true);
    okulApi
      .listPersonnel({ search, limit: PAGE_SIZE, offset })
      .then((result) => {
        if (cancelled) return;
        const geri = geriDusulecekOffset(result, offset);
        if (geri !== null) {
          geriDusuluyor = true;
          setOffset(geri);
          return;
        }
        setPage(result);
        setError(null);
      })
      .catch((e: unknown) => {
        if (cancelled) return;
        setError(e instanceof ApiError ? e.message : "Personel listesi yüklenemedi.");
      })
      .finally(() => {
        if (!cancelled && !geriDusuluyor) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [search, offset, reloadKey]);

  const columns: Column<Personnel>[] = [
    { header: "Ad soyad", cell: (p) => p.full_name },
    { header: "Unvan", cell: (p) => p.title || "—" },
    { header: "Branş", cell: (p) => p.branch || "—" },
    { header: "Durum", cell: (p) => (p.is_active ? "Aktif" : "Pasif") },
  ];

  return (
    <div className="space-y-[var(--ks-page-gap)]">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <p className="text-title-medium text-on-surface">Öğretmen sicili</p>
          {!loading && (
            <p className="text-body-small text-on-surface-variant">
              {formatNumber(page.count)} kayıt
            </p>
          )}
        </div>
        <Button icon="person_add" onClick={() => setCreating(true)}>
          Öğretmen ekle
        </Button>
      </div>

      <Card
        elevation={0}
        className="grid items-end gap-3 bg-surface-container-lowest p-[var(--ks-panel-padding)] sm:grid-cols-2"
      >
        <TextField
          className="min-w-60 flex-1"
          label="Ara"
          value={searchInput}
          onChange={(e) => {
            setSearchInput(e.target.value);
            setOffset(0);
          }}
          placeholder="Ad soyad…"
        />
      </Card>

      {error && <ErrorBand message={error} />}

      {loading ? (
        <SkeletonList rows={5} />
      ) : page.results.length === 0 ? (
        <EmptyState
          icon="badge"
          title="Gösterilecek öğretmen yok"
          description="Aramayı değiştirin ya da öğretmen listesini aşağıdaki panelden içe aktarın."
        />
      ) : (
        <>
          <DataTable<Personnel>
            columns={columns}
            rows={page.results}
            onRowClick={(p) => setEditing(p)}
            rowLabel={(p) => `${p.full_name} kaydını düzenle`}
          />
          <PaginationBar count={page.count} offset={offset} onOffset={setOffset} />
        </>
      )}

      <ImportPanel kind="personnel" onImported={reload} />

      {(creating || editing !== null) && (
        <PersonelFormDialog
          personnel={editing}
          onClose={() => {
            setCreating(false);
            setEditing(null);
          }}
          onSaved={() => {
            setCreating(false);
            setEditing(null);
            reload();
          }}
        />
      )}
    </div>
  );
}

function PersonelFormDialog({
  personnel,
  onClose,
  onSaved,
}: {
  personnel: Personnel | null;
  onClose: () => void;
  onSaved: () => void;
}) {
  const [firstName, setFirstName] = useState(personnel?.first_name ?? "");
  const [lastName, setLastName] = useState(personnel?.last_name ?? "");
  const [title, setTitle] = useState(personnel?.title ?? "");
  const [branch, setBranch] = useState(personnel?.branch ?? "");
  const [aktif, setAktif] = useState(personnel?.is_active ?? true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const { errors, setFieldError, clearErrors, applyApiError } = useFormErrors();
  const snackbar = useSnackbar();
  const confirm = useConfirm();

  const submit = async () => {
    clearErrors();
    setError(null);
    if (!firstName.trim() || !lastName.trim()) {
      if (!firstName.trim()) setFieldError("first_name", "Ad zorunludur.");
      if (!lastName.trim()) setFieldError("last_name", "Soyad zorunludur.");
      return;
    }
    const body: PersonnelWriteBody = {
      first_name: firstName.trim(),
      last_name: lastName.trim(),
      title: title.trim(),
      branch: branch.trim(),
      is_active: aktif,
    };
    setBusy(true);
    try {
      if (personnel) await okulApi.updatePersonnel(personnel.id, body);
      else await okulApi.createPersonnel(body);
      snackbar.success(personnel ? "Personel güncellendi." : "Personel eklendi.");
      onSaved();
    } catch (e) {
      applyApiError(e);
      setError(e instanceof ApiError ? e.message : "Personel kaydedilemedi.");
      setBusy(false);
    }
  };

  const remove = async () => {
    if (!personnel) return;
    const ok = await confirm({
      message: `'${personnel.full_name}' sicilden silinsin mi? Kayıt geri alınabilir biçimde (soft delete) saklanır.`,
      confirmLabel: "Sil",
    });
    if (!ok) return;
    setBusy(true);
    setError(null);
    try {
      await okulApi.deletePersonnel(personnel.id);
      snackbar.success("Personel silindi.");
      onSaved();
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Personel silinemedi.");
      setBusy(false);
    }
  };

  return (
    <Dialog
      open
      onClose={onClose}
      title={personnel ? "Personeli düzenle" : "Yeni personel"}
      actions={
        <>
          {personnel && (
            <Button variant="text" icon="delete" onClick={remove} disabled={busy}>
              Sil
            </Button>
          )}
          <Button variant="text" onClick={onClose} disabled={busy}>
            Vazgeç
          </Button>
          <Button icon="check" onClick={submit} disabled={busy}>
            {busy ? "Kaydediliyor…" : "Kaydet"}
          </Button>
        </>
      }
    >
      <div className="space-y-4">
        {error && <ErrorBand message={error} />}
        <TextField
          label="Ad"
          required
          value={firstName}
          onChange={(e) => setFirstName(e.target.value)}
          error={errors.first_name}
        />
        <TextField
          label="Soyad"
          required
          value={lastName}
          onChange={(e) => setLastName(e.target.value)}
          error={errors.last_name}
        />
        <TextField
          label="Unvan"
          value={title}
          onChange={(e) => setTitle(e.target.value)}
          error={errors.title}
          helperText="Örn. Müdür Yardımcısı, Öğretmen, Memur."
        />
        <TextField
          label="Branş"
          value={branch}
          onChange={(e) => setBranch(e.target.value)}
          error={errors.branch}
        />
        <Select
          label="Durum"
          value={aktif ? "1" : "0"}
          onChange={(e) => setAktif(e.target.value === "1")}
          options={[
            { value: "1", label: "Aktif" },
            { value: "0", label: "Pasif" },
          ]}
          helperText="Pasif öğretmen gözetmen aday havuzuna girmez."
        />
      </div>
    </Dialog>
  );
}

// ---------------------------------------------------------------------------
// İçe aktarma paneli (dosya VEYA pano metni → önizle → aktar)
// ---------------------------------------------------------------------------

type ImportKind = "students" | "personnel";

const IMPORT_LABEL: Record<ImportKind, { title: string; hint: string; template: string }> = {
  students: {
    title: "e-Okul raporundan veya şablondan öğrenci aktar",
    hint: "e-Okul Öğrenci İşlemleri → Raporlar → OOG01001R020 — Sınıf/Şube Öğrenci Listesi raporunu Excel olarak indirip DEĞİŞTİRMEDEN yükleyin: şube blokları, sınıf başlıkları ve sayaç dipnotları otomatik çözülür. Alternatif olarak uygulama şablonu (sınıf, okul numarası, ad, soyad) doldurulabilir ya da tablo doğrudan panoya yapıştırılabilir. Öğrencinin adı-soyadı ve numarası dışındaki sütunlar (cinsiyet, pansiyon) okunmaz.",
    template: STUDENT_TEMPLATE_FILENAME,
  },
  personnel: {
    title: "e-Okul raporundan veya şablondan öğretmen aktar",
    hint: "e-Okul Kurum İşlemleri → Raporlar → OOK01001R1 — Personel Listesi raporunu Excel olarak indirip DEĞİŞTİRMEDEN yükleyin (ad-soyad, görev ve branş okunur; sayaç dipnotu atlanır). Alternatif olarak uygulama şablonu doldurulabilir ya da tablo panoya yapıştırılabilir.",
    template: PERSONNEL_TEMPLATE_FILENAME,
  },
};

function ImportPanel({ kind, onImported }: { kind: ImportKind; onImported: () => void }) {
  const [file, setFile] = useState<File | null>(null);
  const [text, setText] = useState("");
  const [report, setReport] = useState<ImportReport | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const snackbar = useSnackbar();
  const fileId = useId();
  const textId = useId();
  // Seçimi geri almak için gerçek DOM alanına erişim şart: `value` sıfırlanmadan
  // aynı dosya yeniden seçilemez ve tarayıcı "dosya seçilmedi" durumuna dönmez.
  const fileRef = useRef<HTMLInputElement>(null);

  const labels = IMPORT_LABEL[kind];
  // Dosya öncelikli: ikisi birden doluysa backend 400 döner, o yüzden tek girdi seçilir.
  const input: ImportInput | null = file ? { file } : text.trim() ? { text } : null;
  // Aktarma yalnız önizlemeden sonra açılır (dry_run raporu görülmeden yazma yok).
  const canCommit = report !== null && report.dry_run;

  const run = async (mode: "preview" | "commit") => {
    if (!input) {
      setError("Önce bir dosya seçin ya da listeyi yapıştırın.");
      return;
    }
    setBusy(true);
    setError(null);
    try {
      const result =
        mode === "preview"
          ? kind === "students"
            ? await okulApi.previewStudentImport(input)
            : await okulApi.previewPersonnelImport(input)
          : kind === "students"
            ? await okulApi.commitStudentImport(input)
            : await okulApi.commitPersonnelImport(input);
      setReport(result);
      if (mode === "commit") {
        snackbar.success("İçe aktarma tamamlandı.");
        onImported();
      }
    } catch (e) {
      setError(
        e instanceof ApiError
          ? e.message
          : mode === "preview"
            ? "Önizleme yapılamadı."
            : "İçe aktarma yapılamadı.",
      );
    } finally {
      setBusy(false);
    }
  };

  const downloadTemplate = async () => {
    setError(null);
    try {
      const blob =
        kind === "students" ? await okulApi.studentTemplate() : await okulApi.personnelTemplate();
      saveBlob(blob, labels.template);
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Şablon indirilemedi.");
    }
  };

  return (
    <Card elevation={0} className="space-y-4 p-[var(--ks-panel-padding)]">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <p className="text-title-medium text-on-surface">{labels.title}</p>
          <p className="mt-0.5 max-w-3xl text-body-small text-on-surface-variant">{labels.hint}</p>
        </div>
        <Button variant="outlined" icon="download" onClick={downloadTemplate}>
          Şablon indir
        </Button>
      </div>

      <div>
        <label htmlFor={fileId} className="mb-1 block text-label-large text-on-surface-variant">
          Dosya (e-Okul .xls veya şablon .xlsx)
        </label>
        <div className="flex flex-wrap items-center gap-2">
          <input
            id={fileId}
            ref={fileRef}
            type="file"
            /* e-Okul ihraçları BÜYÜK harfli .XLS uzantısıyla iner; tarayıcı
               accept eşleşmesi büyük/küçük harfe duyarsızdır ama MIME tipini
               tanımayan Windows kurulumları için uzantı listesi de verilir. */
            accept=".xls,.xlsx,application/vnd.ms-excel,application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            onChange={(e) => {
              setFile(e.target.files?.[0] ?? null);
              setReport(null);
              setError(null);
            }}
            className="block min-h-[var(--ks-field-height)] flex-1 rounded-shape-sm border border-outline bg-surface-container-lowest px-3 py-2 text-body-medium text-on-surface file:mr-3 file:rounded-shape-sm file:border-0 file:bg-secondary-container file:px-3 file:py-1.5 file:text-label-large file:text-on-secondary-container focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary"
          />
          {file && (
            <Button
              variant="text"
              icon="close"
              onClick={() => {
                if (fileRef.current) fileRef.current.value = "";
                setFile(null);
                setReport(null);
                setError(null);
              }}
            >
              Dosyayı kaldır
            </Button>
          )}
        </div>
      </div>

      <div>
        <label htmlFor={textId} className="mb-1 block text-label-large text-on-surface-variant">
          Ya da tabloyu yapıştırın
        </label>
        <textarea
          id={textId}
          rows={3}
          value={text}
          onChange={(e) => {
            setText(e.target.value);
            setReport(null);
            setError(null);
          }}
          disabled={file !== null}
          placeholder="Excel satırlarını kopyalayıp buraya yapıştırın…"
          className="block w-full rounded-shape-xs border border-outline bg-surface px-4 py-3 text-body-medium text-on-surface outline-none placeholder:text-on-surface-variant/60 focus-visible:ring-2 focus-visible:ring-primary focus:border-primary disabled:opacity-50"
        />
      </div>

      {error && <ErrorBand message={error} />}

      <div className="flex flex-wrap justify-end gap-2">
        <Button variant="tonal" icon="visibility" onClick={() => run("preview")} disabled={busy}>
          {busy ? "Çalışıyor…" : "Önizle"}
        </Button>
        <Button icon="upload" onClick={() => run("commit")} disabled={busy || !canCommit}>
          Aktar
        </Button>
      </div>

      {report && <ImportReportView report={report} />}
    </Card>
  );
}

function ImportReportView({ report }: { report: ImportReport }) {
  const counts = importCounts(report);
  const cells: { label: string; value: number }[] = [
    { label: "Toplam satır", value: report.total_rows },
    { label: "İşlenen", value: report.processed },
    { label: "Yeni", value: counts.created },
    { label: "Güncellenen", value: counts.updated },
    { label: "Değişmeyen", value: counts.unchanged },
  ];

  return (
    <div className="space-y-3 rounded-shape-md bg-surface-container-low p-4">
      <p className="text-title-small text-on-surface">
        {report.dry_run ? "Önizleme — hiçbir kayıt yazılmadı" : "İçe aktarma sonucu"}
      </p>

      {report.already_imported && (
        <div className="flex items-start gap-2 rounded-shape-sm bg-tertiary-container px-4 py-3 text-body-medium text-on-tertiary-container">
          <Icon name="info" size="lg" />
          <span>
            Bu içerik daha önce aktarılmış. Güncelleme amaçlı yeniden aktarma engellenmez.
          </span>
        </div>
      )}

      <dl className="grid grid-cols-2 gap-3 sm:grid-cols-5">
        {cells.map((c) => (
          <div key={c.label} className="rounded-shape-sm bg-surface-container px-3 py-2">
            <dt className="text-label-small text-on-surface-variant">{c.label}</dt>
            <dd className="text-title-medium text-on-surface">{formatNumber(c.value)}</dd>
          </div>
        ))}
      </dl>

      <IssueTable
        title={`Uyarılar (${report.warnings.length})`}
        issues={report.warnings}
        emptyText="Uyarı yok."
      />
      <IssueTable
        title={`Atlanan satırlar (${report.skipped.length})`}
        issues={report.skipped}
        emptyText="Atlanan satır yok."
      />
    </div>
  );
}

function IssueTable({
  title,
  issues,
  emptyText,
}: {
  title: string;
  issues: ImportReport["warnings"];
  emptyText: string;
}) {
  return (
    <div>
      <p className="text-label-large text-on-surface-variant">{title}</p>
      {issues.length === 0 ? (
        <EmptyState compact title={emptyText} icon="check_circle" />
      ) : (
        <div className="mt-2 overflow-x-auto">
          <table className="w-full border-collapse text-body-small">
            <thead>
              <tr className="border-b border-outline-variant text-left text-label-medium text-on-surface-variant">
                <th className="p-2">Satır</th>
                <th className="p-2">Alan</th>
                <th className="p-2">Sorun</th>
                <th className="p-2">Değer</th>
              </tr>
            </thead>
            <tbody>
              {issues.map((issue, i) => (
                <tr
                  key={`${issue.row_number}-${issue.field}-${i}`}
                  className="border-t border-outline-variant/50"
                >
                  <td className="p-2 text-on-surface-variant">{issue.row_number}</td>
                  <td className="p-2 text-on-surface-variant">{issue.field || "—"}</td>
                  <td className="p-2 text-on-surface">{issue.issue}</td>
                  <td className="p-2 text-on-surface-variant">{issue.raw_value || "—"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
