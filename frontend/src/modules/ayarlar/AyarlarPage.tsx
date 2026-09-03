// Ayarlar sayfası (DD kalıbından KS'ye) — yedi sekme: ders yılları (dönemlerle),
// şube kataloğu (salon-şube eşlemesi ve R2k bu katalogdan okur), şube kümeleri
// (SAY/EA/DİL — sihirbazda toplu şube seçimi), zümreler (okul
// zümre başkanları kurulu — sınav takvimi imza bloğunun kaynağı), okul bilgileri
// (evrak antedi + okul türü, U4), güvenlik (uygulama parolası) ve güncelleme
// (F8 — GitHub sürüm denetimi). DD'deki tatil sekmesi YOK (iş günü hesabı alınmadı).

import { useCallback, useEffect, useState } from "react";
import type { FormEvent } from "react";

import { useTabParam } from "../../hooks/useTabParam";
import { ApiError } from "../../lib/api";
import { formatDate } from "../../lib/format";
import { parseApiFieldErrors } from "../../lib/formErrors";
import Button from "../../ui/Button";
import Card from "../../ui/Card";
import { useConfirm } from "../../ui/ConfirmProvider";
import HubFeatureCard from "../../ui/HubFeatureCard";
import Icon from "../../ui/Icon";
import Select from "../../ui/Select";
import { SkeletonList } from "../../ui/Skeleton";
import { useSnackbar } from "../../ui/SnackbarProvider";
import Tabs, { tabPanelProps } from "../../ui/Tabs";
import type { TabItem } from "../../ui/Tabs";
import TextField from "../../ui/TextField";
import UpdatePanel from "../guncelleme/UpdatePanel";
import SubeKumeleriPaneli from "./SubeKumeleriPaneli";
import ZumrelerPaneli from "./ZumrelerPaneli";
import GuvenlikAyarlari from "../guvenlik/GuvenlikAyarlari";
import CizelgeAtamaMatrisi from "../okul/CizelgeAtamaMatrisi";
import {
  MAKS_GUNLUK_DERS_SAATI,
  MESLEKI_TURLER,
  VARSAYILAN_GUNLUK_DERS_SAATI,
  okulApi,
  okulTuruSecenekleri,
} from "../okul/api";
import type {
  ClassSection,
  GradeLevelOption,
  LevelPrograms,
  SchoolTerm,
  SchoolType,
  SchoolTypeOption,
  SchoolYear,
} from "../okul/api";

// TABS[0] varsayılan sekmedir (useTabParam fallback) — başa yeni anahtar EKLEME.
const TABS = [
  "ders-yillari",
  "subeler",
  "sube-kumeleri",
  "zumreler",
  "okul",
  "guvenlik",
  "guncelleme",
] as const;
type TabKey = (typeof TABS)[number];

const TAB_ITEMS: TabItem[] = [
  { key: "ders-yillari", label: "Ders Yılları", icon: "calendar_month" },
  { key: "subeler", label: "Şubeler", icon: "meeting_room" },
  { key: "sube-kumeleri", label: "Şube Kümeleri", icon: "category" },
  { key: "zumreler", label: "Zümreler", icon: "groups" },
  { key: "okul", label: "Okul Bilgileri", icon: "apartment" },
  { key: "guvenlik", label: "Güvenlik", icon: "lock" },
  { key: "guncelleme", label: "Güncelleme", icon: "system_update" },
];

/** Backend hatasını alan-bazlı haritaya VEYA genel hata bandına dağıtır. */
function splitApiError(
  err: unknown,
  fallback: string,
): { fields: Record<string, string>; message: string | null } {
  const fields = parseApiFieldErrors(err) ?? {};
  if (Object.keys(fields).length > 0) return { fields, message: null };
  return { fields: {}, message: err instanceof ApiError ? err.message : fallback };
}

/**
 * Sayfa genelinde tekrar eden M3 hata bandı. `role="alert"`: bant yükleme/kaydetme
 * başarısız olunca sonradan DOM'a girer, canlı bölge olmadan ekran okuyucu susardı.
 */
function ErrorBanner({ message }: { message: string }) {
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

export default function AyarlarPage() {
  const [tab, setTab] = useTabParam<TabKey>("tab", TABS, "ders-yillari");

  // Ders yılları SAYFA düzeyinde tutulur: hem "Ders Yılları" hem "Şubeler"
  // sekmesi aynı listeden beslenir; aktivasyon sonrası ikisi birden tazelenir.
  const [years, setYears] = useState<SchoolYear[]>([]);
  const [yearsLoading, setYearsLoading] = useState(true);
  const [yearsError, setYearsError] = useState<string | null>(null);

  const loadYears = useCallback(() => {
    setYearsLoading(true);
    okulApi
      .listSchoolYears()
      .then((rows) => {
        setYears(rows);
        setYearsError(null);
      })
      .catch((e: unknown) =>
        setYearsError(e instanceof ApiError ? e.message : "Ders yılları yüklenemedi."),
      )
      .finally(() => setYearsLoading(false));
  }, []);
  useEffect(loadYears, [loadYears]);

  // Okul adı yalnız Güvenlik sekmesi için: kurtarma anahtarı çıktısında hangi
  // okula ait olduğu yazar. Okunamazsa boş geçilir (çıktı yine üretilir).
  const [okulAdi, setOkulAdi] = useState("");
  useEffect(() => {
    let iptal = false;
    okulApi
      .getSchoolConfig()
      .then((c) => {
        if (!iptal) setOkulAdi(c.school_name);
      })
      .catch(() => undefined);
    return () => {
      iptal = true;
    };
  }, []);

  return (
    <div className="space-y-6">
      <div className="ks-page-header">
        <div>
          <h1 className="ks-page-title">Ayarlar</h1>
          <p className="ks-page-description">
            Ders yılı, şube kataloğu, şube kümeleri, zümreler, okul künyesi ve uygulama parolası
            burada yönetilir. Okul künyesi salon evrakının antedinde kullanılır; şube kataloğu
            salon-şube eşlemesini, şube kümeleri sihirbazdaki toplu şube seçimini, zümre listesi de
            sınav takviminin imza bloğunu besler. Derslik kümeleri (Sabah/Öğle) Salonlar
            ekranındadır.
          </p>
        </div>
      </div>

      <Tabs
        items={TAB_ITEMS}
        active={tab}
        onChange={(key) => setTab(key as TabKey)}
        ariaLabel="Ayarlar bölümleri"
        idBase="ayarlar"
      />

      <div {...tabPanelProps("ayarlar", tab)} className="space-y-6">
        {tab === "ders-yillari" && (
          <DersYillariPanel
            years={years}
            loading={yearsLoading}
            error={yearsError}
            onReload={loadYears}
          />
        )}
        {tab === "subeler" && <SubelerPanel years={years} yearsLoading={yearsLoading} />}
        {tab === "sube-kumeleri" && <SubeKumeleriPaneli />}
        {tab === "zumreler" && <ZumrelerPaneli />}
        {tab === "okul" && <OkulBilgileriPanel />}
        {tab === "guvenlik" && <GuvenlikAyarlari okulAdi={okulAdi} />}
        {tab === "guncelleme" && <UpdatePanel />}
      </div>

      <section className="space-y-3">
        <h2 className="text-title-medium text-on-surface">Diğer ayarlar</h2>
        <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
          <HubFeatureCard
            to="/dersler"
            icon="menu_book"
            title="Ders havuzu"
            description="MEB çizelgesinden tohumlanan katalog: elle ders ekleyin, pasifleştirin, mükerrerleri birleştirin."
          />
          {/* Kurulum tamamlandıktan sonra sihirbaza gezinilebilir tek yol burasıdır
              (menüde yer almaz); adımları gözden geçirmek isteyen kullanıcı sıkışmasın. */}
          <HubFeatureCard
            to="/kurulum"
            icon="checklist"
            title="Kurulum sihirbazı"
            description="Okul bilgileri, ders yılı ve kişi aktarma adımlarını yeniden gözden geçirin."
          />
        </div>
      </section>
    </div>
  );
}

// ---------------------------------------------------------------------------
// 1. Ders yılları
// ---------------------------------------------------------------------------

function DersYillariPanel({
  years,
  loading,
  error,
  onReload,
}: {
  years: SchoolYear[];
  loading: boolean;
  error: string | null;
  onReload: () => void;
}) {
  return (
    <div className="space-y-6">
      {error && <ErrorBanner message={error} />}

      <Card elevation={1} className="p-6">
        <p className="text-title-medium text-on-surface">Ders yılları</p>
        <p className="mt-1 text-body-medium text-on-surface-variant">
          Aynı anda yalnız BİR ders yılı aktif olabilir. Kurul, tutanak ve disiplin kayıtları aktif
          yıla bağlanır.
        </p>

        {loading ? (
          <SkeletonList rows={3} className="mt-4" />
        ) : years.length === 0 ? (
          <p className="mt-4 text-body-medium text-on-surface-variant">
            Henüz ders yılı tanımlanmadı. Aşağıdaki formdan ilk yılı oluşturun.
          </p>
        ) : (
          <ul className="mt-4 divide-y divide-outline-variant/50">
            {years.map((y) => (
              <SchoolYearRow key={y.id} year={y} onChanged={onReload} />
            ))}
          </ul>
        )}
      </Card>

      <SchoolYearCreateCard onCreated={onReload} />
    </div>
  );
}

function SchoolYearRow({ year, onChanged }: { year: SchoolYear; onChanged: () => void }) {
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const [editingTerms, setEditingTerms] = useState(false);
  const snackbar = useSnackbar();
  const confirm = useConfirm();

  const activate = async () => {
    const ok = await confirm({
      title: "Ders yılını aktifleştir",
      message: `'${year.name}' aktif ders yılı yapılsın mı? Aynı anda yalnız bir yıl aktif olabilir; diğer yıllar pasife çekilir.`,
      confirmLabel: "Aktifleştir",
    });
    if (!ok) return;
    setBusy(true);
    setErr(null);
    try {
      await okulApi.activateSchoolYear(year.id);
      snackbar.success(`'${year.name}' aktif ders yılı oldu.`);
      onChanged();
    } catch (e) {
      setErr(e instanceof ApiError ? e.message : "Ders yılı aktifleştirilemedi.");
      setBusy(false);
    }
  };

  return (
    <li className="space-y-3 py-3">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="min-w-0">
          <p className="flex flex-wrap items-center gap-2 text-body-large text-on-surface">
            {year.name}
            {year.is_active && (
              <span className="inline-flex items-center gap-1 rounded-shape-xl bg-primary-container px-2 py-0.5 text-label-small text-on-primary-container">
                <Icon name="check_circle" size="sm" />
                Aktif
              </span>
            )}
          </p>
          <p className="text-label-small text-on-surface-variant">
            {formatDate(year.start_date)} – {formatDate(year.end_date)}
          </p>
          {err && (
            <p role="alert" className="text-label-small text-error">
              {err}
            </p>
          )}
        </div>
        <div className="flex gap-2">
          <Button
            variant="text"
            icon="date_range"
            onClick={() => setEditingTerms((value) => !value)}
          >
            Dönemler
          </Button>
          {!year.is_active && (
            <Button variant="text" icon="play_circle" onClick={activate} disabled={busy}>
              Aktifleştir
            </Button>
          )}
        </div>
      </div>
      {editingTerms && <SchoolTermEditor year={year} />}
    </li>
  );
}

function SchoolTermEditor({ year }: { year: SchoolYear }) {
  const snackbar = useSnackbar();
  const [terms, setTerms] = useState<SchoolTerm[]>([]);
  const [firstEnd, setFirstEnd] = useState("");
  const [secondStart, setSecondStart] = useState("");
  const [busy, setBusy] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    okulApi
      .listSchoolTerms(year.id)
      .then((rows) => {
        setTerms(rows);
        setFirstEnd(rows.find((term) => term.sequence === 1)?.end_date ?? "");
        setSecondStart(rows.find((term) => term.sequence === 2)?.start_date ?? "");
      })
      .catch((err: unknown) =>
        setError(err instanceof ApiError ? err.message : "Dönemler yüklenemedi."),
      )
      .finally(() => setBusy(false));
  }, [year.id]);

  const save = async () => {
    if (!firstEnd || !secondStart) {
      setError("Her iki dönem sınır tarihi de seçilmelidir.");
      return;
    }
    setBusy(true);
    setError(null);
    try {
      const rows = await okulApi.configureSchoolTerms(year.id, {
        first_term_end: firstEnd,
        second_term_start: secondStart,
      });
      setTerms(rows);
      snackbar.success(`${year.name} dönem takvimi kaydedildi.`);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Dönemler kaydedilemedi.");
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="rounded-shape-sm bg-surface-container-low p-4">
      <p className="text-body-small text-on-surface-variant">
        1. dönem ders yılı başlangıcında, 2. dönem ders yılı bitişinde sonlanır. Aradaki boşluk
        yarıyıl tatilidir.
      </p>
      <div className="mt-3 grid grid-cols-1 gap-3 sm:grid-cols-2">
        <TextField
          label="1. dönem bitişi"
          type="date"
          value={firstEnd}
          onChange={(event) => setFirstEnd(event.target.value)}
        />
        <TextField
          label="2. dönem başlangıcı"
          type="date"
          value={secondStart}
          onChange={(event) => setSecondStart(event.target.value)}
        />
      </div>
      {terms.length === 2 && (
        <p className="mt-2 text-label-small text-on-surface-variant">
          {formatDate(terms[0].start_date)} – {formatDate(terms[0].end_date)} ·{" "}
          {formatDate(terms[1].start_date)} – {formatDate(terms[1].end_date)}
        </p>
      )}
      {error && <p className="mt-2 text-label-small text-error">{error}</p>}
      <div className="mt-3 flex justify-end">
        <Button variant="tonal" onClick={() => void save()} disabled={busy}>
          {busy ? "Kaydediliyor…" : "Dönemleri kaydet"}
        </Button>
      </div>
    </div>
  );
}

function SchoolYearCreateCard({ onCreated }: { onCreated: () => void }) {
  const [name, setName] = useState("");
  const [startDate, setStartDate] = useState("");
  const [endDate, setEndDate] = useState("");
  const [firstTermEnd, setFirstTermEnd] = useState("");
  const [secondTermStart, setSecondTermStart] = useState("");
  const [fieldErrors, setFieldErrors] = useState<Record<string, string>>({});
  const [formError, setFormError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const snackbar = useSnackbar();

  const submit = async (e: FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    setFormError(null);
    // İstemci tarafı yalnız BOŞ alanları yakalar; tarih sırası doğrulaması
    // backend'in tek doğruluk kaynağıdır (400 → alan altında gösterilir).
    const missing: Record<string, string> = {};
    if (!name.trim()) missing.name = "Ders yılı adı yazılmalıdır.";
    if (!startDate) missing.start_date = "Başlangıç tarihi seçilmelidir.";
    if (!endDate) missing.end_date = "Bitiş tarihi seçilmelidir.";
    if (!firstTermEnd) missing.first_term_end = "1. dönem bitişi seçilmelidir.";
    if (!secondTermStart) missing.second_term_start = "2. dönem başlangıcı seçilmelidir.";
    if (Object.keys(missing).length > 0) {
      setFieldErrors(missing);
      return;
    }
    setFieldErrors({});
    setBusy(true);
    try {
      const created = await okulApi.createSchoolYear({
        name: name.trim(),
        start_date: startDate,
        end_date: endDate,
      });
      await okulApi.configureSchoolTerms(created.id, {
        first_term_end: firstTermEnd,
        second_term_start: secondTermStart,
      });
      snackbar.success("Ders yılı oluşturuldu.");
      setName("");
      setStartDate("");
      setEndDate("");
      setFirstTermEnd("");
      setSecondTermStart("");
      onCreated();
    } catch (err) {
      const split = splitApiError(err, "Ders yılı oluşturulamadı.");
      setFieldErrors(split.fields);
      setFormError(split.message);
    } finally {
      setBusy(false);
    }
  };

  return (
    <Card elevation={1} className="p-6">
      <p className="text-title-medium text-on-surface">Yeni ders yılı</p>
      <p className="mt-1 text-body-medium text-on-surface-variant">
        Yeni yıl PASİF doğar; hazır olduğunuzda listeden aktifleştirirsiniz.
      </p>
      <form className="mt-4 space-y-4" onSubmit={submit} noValidate>
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
          <TextField
            label="Ders yılı adı"
            required
            value={name}
            onChange={(e) => setName(e.target.value)}
            placeholder="2026-2027"
            error={fieldErrors.name}
          />
          <TextField
            label="Başlangıç"
            required
            type="date"
            value={startDate}
            onChange={(e) => setStartDate(e.target.value)}
            error={fieldErrors.start_date}
          />
          <TextField
            label="Bitiş"
            required
            type="date"
            value={endDate}
            onChange={(e) => setEndDate(e.target.value)}
            error={fieldErrors.end_date}
          />
        </div>
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
          <TextField
            label="1. dönem bitişi"
            required
            type="date"
            value={firstTermEnd}
            onChange={(event) => setFirstTermEnd(event.target.value)}
            error={fieldErrors.first_term_end}
          />
          <TextField
            label="2. dönem başlangıcı"
            required
            type="date"
            value={secondTermStart}
            onChange={(event) => setSecondTermStart(event.target.value)}
            error={fieldErrors.second_term_start}
          />
        </div>
        {formError && <ErrorBanner message={formError} />}
        <div className="flex justify-end">
          <Button type="submit" icon="add" disabled={busy}>
            {busy ? "Oluşturuluyor…" : "Ders yılı oluştur"}
          </Button>
        </div>
      </form>
    </Card>
  );
}

// ---------------------------------------------------------------------------
// 2. Şubeler (şube kataloğu — salon-şube eşlemesi ve R2k bu katalogdan okur)
// ---------------------------------------------------------------------------

function SubelerPanel({ years, yearsLoading }: { years: SchoolYear[]; yearsLoading: boolean }) {
  const [yearId, setYearId] = useState<number | null>(null);
  const [rows, setRows] = useState<ClassSection[]>([]);
  const [levels, setLevels] = useState<GradeLevelOption[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [level, setLevel] = useState("");
  const [section, setSection] = useState("");
  const [busy, setBusy] = useState(false);
  const snackbar = useSnackbar();
  const confirm = useConfirm();

  useEffect(() => {
    if (yearId === null && years.length > 0) {
      setYearId((years.find((y) => y.is_active) ?? years[0]).id);
    }
  }, [years, yearId]);

  useEffect(() => {
    okulApi
      .getGradeLevels()
      .then((r) => {
        setLevels(r.levels);
        if (r.levels.length > 0) setLevel(String(r.levels[0].value));
      })
      .catch(() => setLevels([]));
  }, []);

  const load = useCallback(() => {
    if (yearId === null) {
      setRows([]);
      setLoading(false);
      return;
    }
    setLoading(true);
    okulApi
      .listClassSections(yearId)
      .then((items) => {
        setRows(items);
        setError(null);
      })
      .catch((e: unknown) =>
        setError(e instanceof ApiError ? e.message : "Şube kataloğu yüklenemedi."),
      )
      .finally(() => setLoading(false));
  }, [yearId]);
  useEffect(load, [load]);

  const ekle = async () => {
    if (yearId === null || !section.trim() || !level) return;
    setBusy(true);
    try {
      await okulApi.createClassSection({
        school_year: yearId,
        class_level: Number(level),
        class_section: section.trim(),
      });
      snackbar.success("Şube eklendi.");
      setSection("");
      load();
    } catch (e) {
      snackbar.error(e instanceof ApiError ? e.message : "Şube eklenemedi.");
    } finally {
      setBusy(false);
    }
  };

  const sil = async (row: ClassSection) => {
    const ok = await confirm({
      title: "Şubeyi kaldır",
      message: `${row.class_label} şubesi katalogdan kaldırılsın mı? Öğrenci kayıtları etkilenmez; içe aktarma yeniden görürse şube tekrar eklenir.`,
      confirmLabel: "Kaldır",
    });
    if (!ok) return;
    try {
      await okulApi.deleteClassSection(row.id);
      snackbar.success(`${row.class_label} kaldırıldı.`);
      load();
    } catch (e) {
      snackbar.error(e instanceof ApiError ? e.message : "Şube kaldırılamadı.");
    }
  };

  return (
    <div className="space-y-6">
      {error && <ErrorBanner message={error} />}

      <Card elevation={1} className="p-6">
        <p className="text-title-medium text-on-surface">Şube kataloğu</p>
        <p className="mt-1 text-body-medium text-on-surface-variant">
          Öğrenci aktarımında görülen şubeler buraya kendiliğinden eklenir. Salon-şube eşlemesi
          (klasik düzen) ve şube yoklama listeleri bu katalogdan beslenir.
        </p>

        <div className="mt-4 max-w-sm">
          <Select
            label="Ders yılı"
            value={yearId === null ? "" : String(yearId)}
            onChange={(e) => setYearId(Number(e.target.value))}
            options={years.map((y) => ({
              value: String(y.id),
              label: `${y.name}${y.is_active ? " (aktif)" : ""}`,
            }))}
          />
        </div>

        {yearsLoading || loading ? (
          <SkeletonList rows={3} className="mt-4" />
        ) : rows.length === 0 ? (
          <p className="mt-4 text-body-medium text-on-surface-variant">
            Bu ders yılında kayıtlı şube yok. Öğrenci listesi aktarınca şubeler otomatik gelir;
            aşağıdan elle de ekleyebilirsiniz.
          </p>
        ) : (
          <ul className="mt-4 flex flex-wrap gap-2">
            {rows.map((row) => (
              <li
                key={row.id}
                className="flex items-center gap-1 rounded-shape-sm bg-surface-container px-3 py-1.5 text-body-medium text-on-surface"
              >
                {row.class_label}
                <button
                  type="button"
                  aria-label={`${row.class_label} şubesini kaldır`}
                  onClick={() => void sil(row)}
                  className="ml-1 flex h-6 w-6 items-center justify-center rounded-shape-xs text-on-surface-variant transition hover:bg-surface-container-high hover:text-error focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary"
                >
                  <Icon name="close" size="sm" />
                </button>
              </li>
            ))}
          </ul>
        )}

        <div className="mt-5 grid grid-cols-1 items-end gap-3 sm:grid-cols-[10rem_8rem_auto]">
          <Select
            label="Sınıf"
            value={level}
            onChange={(e) => setLevel(e.target.value)}
            options={levels.map((l) => ({ value: String(l.value), label: l.label }))}
          />
          <TextField
            label="Şube"
            value={section}
            onChange={(e) => setSection(e.target.value)}
            placeholder="A"
          />
          <Button
            icon="add"
            onClick={() => void ekle()}
            disabled={busy || yearId === null || !section.trim() || !level}
          >
            Şube ekle
          </Button>
        </div>
      </Card>
    </div>
  );
}

// ---------------------------------------------------------------------------
// 3. Okul bilgileri (kurum künyesi + okul türü)
// ---------------------------------------------------------------------------

function OkulBilgileriPanel() {
  const [okulAdi, setOkulAdi] = useState("");
  const [il, setIl] = useState("");
  const [ilce, setIlce] = useState("");
  const [mudur, setMudur] = useState("");
  const [okulTuru, setOkulTuru] = useState<SchoolType>("ANADOLU_LISESI");
  const [hazirlikVar, setHazirlikVar] = useState(false);
  const [levelPrograms, setLevelPrograms] = useState<LevelPrograms>({});
  const [gunlukDersSaati, setGunlukDersSaati] = useState(VARSAYILAN_GUNLUK_DERS_SAATI);
  const [sinavSaatleri, setSinavSaatleri] = useState<number[]>([]);
  const [okulTurleri, setOkulTurleri] = useState<SchoolTypeOption[]>([]);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [fieldErrors, setFieldErrors] = useState<Record<string, string>>({});
  const snackbar = useSnackbar();

  useEffect(() => {
    let iptal = false;
    okulApi
      .getSchoolConfig()
      .then((c) => {
        if (iptal) return;
        setOkulAdi(c.school_name);
        setIl(c.province);
        setIlce(c.district);
        setMudur(c.principal_name);
        setOkulTuru(c.school_type);
        setHazirlikVar(c.has_prep_class);
        setLevelPrograms(c.level_programs ?? {});
        setGunlukDersSaati(c.daily_period_count || VARSAYILAN_GUNLUK_DERS_SAATI);
        setSinavSaatleri(c.exam_period_nos ?? []);
        setError(null);
      })
      .catch((e: unknown) =>
        setError(e instanceof ApiError ? e.message : "Okul bilgileri yüklenemedi."),
      )
      .finally(() => {
        if (!iptal) setLoading(false);
      });
    okulApi
      .listSchoolTypes()
      .then((r) => {
        if (!iptal) setOkulTurleri(r);
      })
      .catch(() => {
        if (!iptal) setOkulTurleri([]);
      });
    return () => {
      iptal = true;
    };
  }, []);

  const submit = async (e: FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    setBusy(true);
    setError(null);
    setFieldErrors({});
    try {
      await okulApi.updateSchoolConfig({
        school_name: okulAdi.trim(),
        province: il.trim(),
        district: ilce.trim(),
        principal_name: mudur.trim(),
        school_type: okulTuru,
        has_prep_class: hazirlikVar,
        level_programs: levelPrograms,
        daily_period_count: gunlukDersSaati,
        // Gün kısaldıysa taşan saatler gönderilmez: backend'in "açıkça
        // gönderilen liste sessizce kırpılmaz" kuralı hata döndürürdü.
        exam_period_nos: sinavSaatleri.filter((no) => no <= gunlukDersSaati),
      });
      snackbar.success("Okul bilgileri kaydedildi. Ders havuzu çizelgeye göre güncellendi.");
    } catch (err) {
      const split = splitApiError(err, "Okul bilgileri kaydedilemedi.");
      setFieldErrors(split.fields);
      setError(split.message);
    } finally {
      setBusy(false);
    }
  };

  if (loading) return <SkeletonList rows={4} />;

  return (
    <Card elevation={1} className="p-6">
      <p className="text-title-medium text-on-surface">Okul bilgileri</p>
      <p className="mt-1 text-body-medium text-on-surface-variant">
        Salon evrakının antedi bu bilgilerden üretilir. Okul türü, hazırlık sınıfı ve seviye bazlı
        çizelge ataması, ders havuzunun hangi MEB çizelgesinden türetileceğini ve geçerli sınıf
        seviyelerini belirler; kaydedince ders havuzu çizelgeye göre yeniden senkronlanır.
      </p>
      {error && (
        <div className="mt-4">
          <ErrorBanner message={error} />
        </div>
      )}
      <form className="mt-4 grid grid-cols-1 gap-4 sm:grid-cols-2" onSubmit={submit} noValidate>
        <TextField
          className="sm:col-span-2"
          label="Okul adı"
          required
          value={okulAdi}
          onChange={(e) => setOkulAdi(e.target.value)}
          error={fieldErrors.school_name}
        />
        <TextField
          label="İl"
          value={il}
          onChange={(e) => setIl(e.target.value)}
          error={fieldErrors.province}
        />
        <TextField
          label="İlçe"
          value={ilce}
          onChange={(e) => setIlce(e.target.value)}
          error={fieldErrors.district}
        />
        <TextField
          className="sm:col-span-2"
          label="Okul müdürü"
          value={mudur}
          onChange={(e) => setMudur(e.target.value)}
          error={fieldErrors.principal_name}
        />
        <Select
          label="Okul türü"
          value={okulTuru}
          onChange={(e) => setOkulTuru(e.target.value as SchoolType)}
          options={okulTuruSecenekleri(okulTurleri)}
        />
        <Select
          label="Hazırlık sınıfı"
          value={hazirlikVar ? "1" : "0"}
          onChange={(e) => setHazirlikVar(e.target.value === "1")}
          options={[
            { value: "0", label: "Yok" },
            { value: "1", label: "Var" },
          ]}
        />
        <Select
          label="Günlük ders saati sayısı"
          value={String(gunlukDersSaati)}
          onChange={(e) => setGunlukDersSaati(Number(e.target.value))}
          options={Array.from({ length: MAKS_GUNLUK_DERS_SAATI }, (_, i) => ({
            value: String(i + 1),
            label: `${i + 1} ders saati`,
          }))}
          helperText={
            MESLEKI_TURLER.includes(okulTuru)
              ? "Atölye ve işletmede beceri eğitimi günleriyle değişebilir — okulunuzun gününü girin."
              : "Genel liselerde gün 8 ders saatidir."
          }
        />
        <div className="sm:col-span-2">
          <fieldset>
            <legend className="text-label-large text-on-surface">
              Sınav yapılabilecek ders saatleri
            </legend>
            <p className="mb-2 text-body-small text-on-surface-variant">
              Otomatik yerleştirme sınavları YALNIZ işaretli saatlere koyar. Hiçbiri işaretli
              değilse tüm saatler sınava açıktır. Elle yerleştirmede bu seçim bağlayıcı değildir —
              sınav saatini okul müdürlüğü belirler (Yazılı ve Uygulamalı Sınavlar Yönergesi md. 5).
            </p>
            <div className="grid grid-cols-3 gap-1 sm:grid-cols-4">
              {Array.from({ length: gunlukDersSaati }, (_, i) => i + 1).map((no) => (
                <label
                  key={no}
                  className="flex min-h-9 cursor-pointer items-center gap-2 rounded-shape-sm border border-outline px-3 text-body-medium text-on-surface"
                >
                  <input
                    type="checkbox"
                    className="h-5 w-5 accent-primary"
                    checked={sinavSaatleri.includes(no)}
                    aria-label={`${no}. ders saati sınava açık`}
                    onChange={() =>
                      setSinavSaatleri((prev) =>
                        prev.includes(no)
                          ? prev.filter((x) => x !== no)
                          : [...prev, no].sort((a, b) => a - b),
                      )
                    }
                  />
                  {no}. ders
                </label>
              ))}
            </div>
          </fieldset>
        </div>
        <div className="sm:col-span-2">
          <CizelgeAtamaMatrisi
            schoolType={okulTuru}
            hasPrepClass={hazirlikVar}
            value={levelPrograms}
            onChange={setLevelPrograms}
          />
        </div>
        <div className="flex justify-end sm:col-span-2">
          <Button type="submit" icon="check" disabled={busy}>
            {busy ? "Kaydediliyor…" : "Kaydet"}
          </Button>
        </div>
      </form>
    </Card>
  );
}
