// Ders havuzu — MEB çizelgesinden tohumlanan katalog + elle ekleme + pasifleştirme
// + mükerrer birleştirme (tasarım §7). Liste ilk açılışta backend tembel tohumunu
// tetikler (K5); veri dosyası yoksa havuz boş başlar ve elle ekleme yolu açıktır (TB2).
//
// 03.09.2026: seçmeli derslerde "Şubeler" sütunu — dersi hangi şubelerin aldığı
// BURADA girilir, sınav takvimi havuzu o bilgiden beslenir (takvim başına
// yeniden şube işaretlemek yok). Liste manuel `load()` ile, kapsam haritası
// React Query ile gelir: diyalog kaydedince invalidate ile ikisi de tazelenir.

import { useCallback, useEffect, useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";

import { ApiError } from "../../lib/api";
import Button from "../../ui/Button";
import Card from "../../ui/Card";
import { useConfirm } from "../../ui/ConfirmProvider";
import Dialog from "../../ui/Dialog";
import Icon from "../../ui/Icon";
import Select from "../../ui/Select";
import { SkeletonList } from "../../ui/Skeleton";
import { useSnackbar } from "../../ui/SnackbarProvider";
import TextField from "../../ui/TextField";
import { okulApi } from "../okul/api";
import type { GradeLevelOption } from "../okul/api";
import { COURSE_EXAM_MODE_TR, COURSE_SOURCE_TR, COURSE_TYPE_TR, derslerApi } from "./api";
import type { CatalogStatus, Course, CourseExamMode, CourseType, DuplicateCluster } from "./api";
import DersSubeKapsamiDialog from "./DersSubeKapsamiDialog";

export default function DersHavuzuPage() {
  const [rows, setRows] = useState<Course[]>([]);
  const [status, setStatus] = useState<CatalogStatus | null>(null);
  const [levels, setLevels] = useState<GradeLevelOption[]>([]);
  const [level, setLevel] = useState<number | null>(null);
  const [courseType, setCourseType] = useState<CourseType | null>(null);
  const [showInactive, setShowInactive] = useState(false);
  const [query, setQuery] = useState("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [adding, setAdding] = useState(false);
  // Düzenlenen ders — ekleme ile aynı dialog'u besler (iki bileşen olsaydı
  // seviye çipleri + tür + sınav biçimi iki yerde sürüklenirdi).
  const [editing, setEditing] = useState<Course | null>(null);
  // Şube kapsamı düzenlenen ders (seçmeli) — kapsamın KAYNAĞI bu ekrandır.
  const [sectionsFor, setSectionsFor] = useState<Course | null>(null);
  const [duplicates, setDuplicates] = useState<DuplicateCluster[]>([]);

  const offeringsQuery = useQuery({
    queryKey: ["course-section-offerings"],
    queryFn: () => derslerApi.sectionOfferings(),
    // Aktif ders yılı yoksa uç 400 döner; sütun "—" kalır, sayfa çalışmaya devam eder.
    retry: false,
  });
  const sectionCatalog = useQuery({
    queryKey: ["class-sections"],
    queryFn: () => okulApi.listClassSections(),
    retry: false,
  });

  /** course_id → seviye bazlı şube etiketleri ("9: A, B"). */
  const kapsamOzetleri = useMemo(() => {
    const etiket = new Map((sectionCatalog.data ?? []).map((s) => [s.id, s.class_label] as const));
    const ozet = new Map<number, string[]>();
    for (const row of offeringsQuery.data?.results ?? []) {
      const adlar = row.section_ids
        .map((id) => etiket.get(id))
        .filter((x): x is string => Boolean(x));
      if (adlar.length === 0) continue;
      const parca = `${row.level === 0 ? "Hz" : row.level}: ${adlar
        .map((a) => a.split("/")[1] ?? a)
        .join(", ")}`;
      ozet.set(row.course, [...(ozet.get(row.course) ?? []), parca]);
    }
    return ozet;
  }, [offeringsQuery.data, sectionCatalog.data]);

  useEffect(() => {
    okulApi
      .getGradeLevels()
      .then((data) => setLevels(data.levels))
      .catch(() => setLevels([]));
  }, []);

  const load = useCallback(() => {
    setLoading(true);
    Promise.all([
      derslerApi.listCourses({
        level,
        courseType,
        includeInactive: showInactive,
        q: query,
      }),
      derslerApi.listDuplicates(),
    ])
      .then(([courses, clusters]) => {
        setRows(courses);
        setDuplicates(clusters);
        setError(null);
        // Çizelge paneli liste senkronundan SONRA çekilir (liste ucu tembel tohumu
        // koşturur; önce çekilse "henüz senkronlanmadı" yanlış görünürdü).
        // Gelmezse panel gizli kalır, liste çalışmaya devam eder.
        return derslerApi
          .getCatalogStatus()
          .then(setStatus)
          .catch(() => setStatus(null));
      })
      .catch((err: unknown) =>
        setError(err instanceof ApiError ? err.message : "Ders havuzu yüklenemedi."),
      )
      .finally(() => setLoading(false));
  }, [level, courseType, showInactive, query]);

  useEffect(load, [load]);

  return (
    <div className="space-y-6">
      <div className="ks-page-header">
        <div>
          <h1 className="ks-page-title">Ders havuzu</h1>
          <p className="ks-page-description">
            Sınav oturumları dersleri bu havuzdan seçer. Havuz, MEB haftalık ders çizelgesinden
            (okul türünüze göre) kendiliğinden tohumlanır; listede olmayan dersi elle
            ekleyebilirsiniz. Ders silinmez — pasifleştirilir. <strong>Sınav</strong> sütunu dersin
            yazılı mı, uygulama mı olduğunu (ya da hiç sınavı olmadığını) söyler; takvim havuzuna
            zorunlu dersler eklenirken yalnız <em>Yazılı</em> dersler çekilir.
          </p>
        </div>
        <Button icon="add" onClick={() => setAdding(true)}>
          Ders ekle
        </Button>
      </div>

      {error && <ErrorBanner message={error} />}

      {status && <CizelgePaneli status={status} onResynced={load} />}

      {duplicates.length > 0 && <DuplicatesPanel clusters={duplicates} onMerged={load} />}

      <Card elevation={1} className="p-5">
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-4">
          <TextField
            label="Ara"
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            placeholder="Ders adı…"
          />
          <Select
            label="Seviye"
            value={level === null ? "" : String(level)}
            onChange={(event) =>
              setLevel(event.target.value === "" ? null : Number(event.target.value))
            }
            options={[
              { value: "", label: "Tümü" },
              ...levels.map((item) => ({ value: String(item.value), label: item.label })),
            ]}
          />
          <Select
            label="Tür"
            value={courseType ?? ""}
            onChange={(event) =>
              setCourseType(event.target.value === "" ? null : (event.target.value as CourseType))
            }
            options={[
              { value: "", label: "Tümü" },
              { value: "COMMON", label: COURSE_TYPE_TR.COMMON },
              { value: "ELECTIVE", label: COURSE_TYPE_TR.ELECTIVE },
            ]}
          />
          <Select
            label="Pasif dersler"
            value={showInactive ? "1" : "0"}
            onChange={(event) => setShowInactive(event.target.value === "1")}
            options={[
              { value: "0", label: "Gizle" },
              { value: "1", label: "Göster" },
            ]}
          />
        </div>
      </Card>

      {loading ? (
        <SkeletonList rows={6} />
      ) : rows.length === 0 ? (
        <Card elevation={1} className="p-8 text-center">
          <Icon name="menu_book" size="xl" className="mx-auto text-on-surface-variant" />
          <p className="mt-3 text-title-medium text-on-surface">Havuzda ders yok</p>
          <p className="mt-1 text-body-medium text-on-surface-variant">
            Süzgeçleri genişletin ya da “Ders ekle” ile elle ekleyin. MEB çizelge verisi paketle
            birlikte gelir; okul türünüz için veri yoksa havuz boş başlar.
          </p>
        </Card>
      ) : (
        <Card elevation={1} className="overflow-x-auto">
          <table className="w-full text-left text-body-medium">
            <thead>
              <tr className="border-b border-outline-variant text-label-medium text-on-surface-variant">
                <th className="px-4 py-3">Ders</th>
                <th className="px-4 py-3">Seviyeler</th>
                <th className="px-4 py-3">Tür</th>
                <th className="px-4 py-3">Sınav</th>
                <th className="px-4 py-3">Şubeler</th>
                <th className="px-4 py-3">Kaynak</th>
                <th className="px-4 py-3">Durum</th>
                <th className="px-4 py-3 text-right">İşlem</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((course) => (
                <CourseRow
                  key={course.id}
                  course={course}
                  kapsamOzeti={kapsamOzetleri.get(course.id) ?? []}
                  onEdit={() => setEditing(course)}
                  onEditSections={() => setSectionsFor(course)}
                  onChanged={load}
                />
              ))}
            </tbody>
          </table>
        </Card>
      )}

      {sectionsFor && (
        <DersSubeKapsamiDialog
          course={sectionsFor}
          onClose={() => setSectionsFor(null)}
          onSaved={() => setSectionsFor(null)}
        />
      )}

      {(adding || editing) && (
        <CourseDialog
          levels={levels}
          course={editing}
          onClose={() => {
            setAdding(false);
            setEditing(null);
          }}
          onSaved={() => {
            setAdding(false);
            setEditing(null);
            load();
          }}
        />
      )}
    </div>
  );
}

/** Sınav biçimi rozeti — yazılı olmayan ders takvim havuzuna kendiliğinden girmez. */
function ExamModeBadge({ course }: { course: Course }) {
  // Etiket backend'den gelir (exam_mode_label); sözlük yalnız veri eski/eksik
  // geldiğinde devreye girer — iki kaynak arasında sessiz boşluk kalmasın.
  const label = course.exam_mode_label || COURSE_EXAM_MODE_TR[course.exam_mode];
  if (course.exam_mode === "WRITTEN") {
    return <span className="text-on-surface-variant">{label}</span>;
  }
  return (
    <span className="rounded-shape-sm bg-tertiary-container px-2 py-0.5 text-label-medium text-on-tertiary-container">
      {label}
    </span>
  );
}

/**
 * "Şubeler" hücresi — kapsam YALNIZ seçmeli derste anlamlıdır: zorunlu ders
 * seviyenin tamamında okutulur ve takvim havuzuna seviye geneli girer.
 * Kapsamı girilmemiş YAZILI seçmeli, havuz doldurmada atlanacağı için ayrıca
 * uyarılır (sessiz düşme olmasın).
 */
function SubeKapsamiHucresi({
  course,
  ozet,
  onEdit,
}: {
  course: Course;
  ozet: string[];
  onEdit: () => void;
}) {
  if (course.course_type !== "ELECTIVE") {
    return <span className="text-on-surface-variant">Seviye geneli</span>;
  }
  return (
    <button
      type="button"
      aria-label={`${course.name} dersinin şubelerini düzenle`}
      onClick={onEdit}
      className="rounded-shape-sm px-2 py-1 text-left underline-offset-4 hover:bg-on-surface/5 hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary"
    >
      {ozet.length > 0 ? (
        <span className="text-on-surface">{ozet.join(" · ")}</span>
      ) : (
        <span
          className="text-on-surface-variant"
          title={
            course.exam_mode === "WRITTEN"
              ? "Şubeleri girilmediği için sınav takvimi havuzuna kendiliğinden girmez."
              : "Bu dersin yazılı sınavı yok; kapsam yalnız bilgi amaçlıdır."
          }
        >
          {course.exam_mode === "WRITTEN" ? "Girilmedi ⚠" : "Girilmedi"}
        </span>
      )}
    </button>
  );
}

function CourseRow({
  course,
  kapsamOzeti,
  onEdit,
  onEditSections,
  onChanged,
}: {
  course: Course;
  kapsamOzeti: string[];
  onEdit: () => void;
  onEditSections: () => void;
  onChanged: () => void;
}) {
  const confirm = useConfirm();
  const snackbar = useSnackbar();
  const [busy, setBusy] = useState(false);

  const toggleActive = async () => {
    if (course.is_active) {
      const approved = await confirm({
        title: "Dersi pasifleştir",
        message: `'${course.name}' yeni sınav planlamalarında seçilemeyecek. Geçmiş kayıtlar etkilenmez.`,
        confirmLabel: "Pasifleştir",
      });
      if (!approved) return;
    }
    setBusy(true);
    try {
      await derslerApi.updateCourse(course.id, { is_active: !course.is_active });
      snackbar.success(
        course.is_active
          ? `'${course.name}' pasifleştirildi.`
          : `'${course.name}' aktifleştirildi.`,
      );
      onChanged();
    } catch (err) {
      snackbar.error(err instanceof ApiError ? err.message : "Ders güncellenemedi.");
      setBusy(false);
    }
  };

  return (
    <tr className="border-b border-outline-variant/50 last:border-b-0">
      <td className="px-4 py-3 text-on-surface">{course.name}</td>
      <td className="px-4 py-3 text-on-surface-variant">{course.level_labels.join(", ")}</td>
      <td className="px-4 py-3 text-on-surface-variant">{COURSE_TYPE_TR[course.course_type]}</td>
      <td className="px-4 py-3">
        <ExamModeBadge course={course} />
      </td>
      <td className="px-4 py-3 text-body-small">
        <SubeKapsamiHucresi course={course} ozet={kapsamOzeti} onEdit={onEditSections} />
      </td>
      <td className="px-4 py-3 text-on-surface-variant">{COURSE_SOURCE_TR[course.source]}</td>
      <td className="px-4 py-3">
        {course.is_active ? (
          <span className="rounded-shape-sm bg-success-container px-2 py-0.5 text-label-medium text-on-success-container">
            Aktif
          </span>
        ) : course.catalog_excluded ? (
          // Senkron pasifleştirdi: okulun yürürlükteki çizelgesinde yok. İdari
          // pasiften ayrı gösterilir; çizelgeye geri girerse kendiliğinden açılır.
          <span
            className="rounded-shape-sm bg-surface-container-high px-2 py-0.5 text-label-medium text-on-surface-variant"
            title="Okulun yürürlükteki MEB çizelgesinde yok; çizelgeye geri girerse kendiliğinden açılır."
          >
            Çizelge dışı
          </span>
        ) : (
          <span className="rounded-shape-sm bg-surface-container-high px-2 py-0.5 text-label-medium text-on-surface-variant">
            Pasif
          </span>
        )}
      </td>
      <td className="px-4 py-3 text-right">
        <Button
          variant="text"
          icon="edit"
          aria-label={`${course.name} dersini düzenle`}
          onClick={onEdit}
          disabled={busy}
        >
          Düzenle
        </Button>
        <Button
          variant="text"
          icon={course.is_active ? "visibility_off" : "visibility"}
          aria-label={`${course.name} dersini ${course.is_active ? "pasifleştir" : "aktifleştir"}`}
          onClick={toggleActive}
          disabled={busy}
        >
          {course.is_active ? "Pasifleştir" : "Aktifleştir"}
        </Button>
      </td>
    </tr>
  );
}

/**
 * Yürürlükteki çizelge paneli — hangi TTK çizelgesinin hangi seviyede uygulandığı,
 * dayanağı ve varsa uyarılar (kademeli çizelgede aktarılmamış önceki nesil gibi).
 * "Çizelgeyi yeniden uygula" kataloğu damgadan bağımsız senkronlar.
 */
function CizelgePaneli({ status, onResynced }: { status: CatalogStatus; onResynced: () => void }) {
  const snackbar = useSnackbar();
  const [busy, setBusy] = useState(false);
  const ayniKume = new Set(
    status.levels.map((lv) =>
      lv.programs
        .map((p) => p.key)
        .sort()
        .join("|"),
    ),
  );
  const tek = ayniKume.size === 1 && status.levels.length > 0 ? status.levels[0].programs : null;

  const resync = async () => {
    setBusy(true);
    try {
      const sonuc = await derslerApi.resyncCatalog();
      const r = sonuc.result;
      snackbar.success(
        r
          ? `Çizelge uygulandı: ${r.created} yeni, ${r.updated} güncellenen, ${r.restored} geri açılan, ${r.excluded} çizelge dışı.`
          : "Çizelge verisi yok; havuz değişmedi.",
      );
      onResynced();
    } catch (err) {
      snackbar.error(err instanceof ApiError ? err.message : "Çizelge uygulanamadı.");
    } finally {
      setBusy(false);
    }
  };

  return (
    <Card elevation={1} className="p-5">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0">
          <p className="flex items-center gap-2 text-title-medium text-on-surface">
            <Icon name="fact_check" />
            Yürürlükteki çizelge — {status.school_type_label}
            {status.has_prep_class ? " (hazırlık sınıflı)" : ""}, {status.year_label}
          </p>
          {tek ? (
            <p className="mt-1 text-body-medium text-on-surface-variant">
              Tüm seviyeler:{" "}
              {tek.map((p) => (
                <span key={p.key} className="text-on-surface">
                  {p.name}
                  {p.source ? ` — ${p.source.split(" — ")[0]}` : ""}
                  {"; "}
                </span>
              ))}
            </p>
          ) : (
            <ul className="mt-1 space-y-0.5 text-body-medium text-on-surface-variant">
              {status.levels.map((lv) => (
                <li key={lv.level}>
                  <span className="text-on-surface">{lv.label}:</span>{" "}
                  {lv.programs.map((p) => p.name).join(" + ") || "çizelge atanmamış"}
                </li>
              ))}
            </ul>
          )}
          {!status.synced && (
            <p className="mt-1 text-body-small text-on-surface-variant">
              Havuz bu planla henüz senkronlanmadı; liste açıldığında kendiliğinden uygulanır.
            </p>
          )}
        </div>
        <Button variant="tonal" icon="sync" onClick={resync} disabled={busy}>
          {busy ? "Uygulanıyor…" : "Çizelgeyi yeniden uygula"}
        </Button>
      </div>
      {status.warnings.length > 0 && (
        <ul className="mt-3 space-y-1">
          {status.warnings.map((w) => (
            <li
              key={w}
              className="flex items-start gap-2 rounded-shape-sm bg-tertiary-container px-3 py-2 text-body-small text-on-tertiary-container"
            >
              <Icon name="warning" size="sm" />
              <span>{w}</span>
            </li>
          ))}
        </ul>
      )}
    </Card>
  );
}

function DuplicatesPanel({
  clusters,
  onMerged,
}: {
  clusters: DuplicateCluster[];
  onMerged: () => void;
}) {
  const confirm = useConfirm();
  const snackbar = useSnackbar();
  const [busy, setBusy] = useState(false);

  const merge = async (cluster: DuplicateCluster) => {
    const canonical = cluster.courses.find((c) => c.id === cluster.suggested_canonical_id);
    const duplicate = cluster.courses.find((c) => c.id !== cluster.suggested_canonical_id);
    if (!canonical || !duplicate) return;
    const approved = await confirm({
      title: "Mükerrer dersi birleştir",
      message:
        `'${duplicate.name}' kaydı '${canonical.name}' dersine birleştirilecek; ` +
        "tüm başvurular taşınır, kopya ad takma ad olarak öğrenilir. Bu işlem geri alınamaz.",
      confirmLabel: "Birleştir",
    });
    if (!approved) return;
    setBusy(true);
    try {
      await derslerApi.mergeCourses(duplicate.id, canonical.id);
      snackbar.success(`'${duplicate.name}' → '${canonical.name}' birleştirildi.`);
      onMerged();
    } catch (err) {
      snackbar.error(err instanceof ApiError ? err.message : "Birleştirme yapılamadı.");
    } finally {
      setBusy(false);
    }
  };

  return (
    <Card elevation={1} className="border-l-4 border-l-primary p-5">
      <p className="flex items-center gap-2 text-title-medium text-on-surface">
        <Icon name="call_merge" />
        Olası mükerrer dersler ({clusters.length})
      </p>
      <p className="mt-1 text-body-medium text-on-surface-variant">
        İçe aktarma veya elle giriş aynı dersi iki kez açmış olabilir. Önerilen kanonik kayda
        birleştirebilirsiniz; ikiden fazla kayıt varsa en uygun ikilisi önerilir.
      </p>
      <ul className="mt-3 space-y-2">
        {clusters.map((cluster) => (
          <li
            key={cluster.canon_key}
            className="flex flex-wrap items-center justify-between gap-2 rounded-shape-sm bg-surface-container-low px-3 py-2"
          >
            <span className="text-body-medium text-on-surface">
              {cluster.courses.map((c) => c.name).join(" · ")}
            </span>
            <Button
              variant="tonal"
              icon="call_merge"
              onClick={() => merge(cluster)}
              disabled={busy}
            >
              Birleştir
            </Button>
          </li>
        ))}
      </ul>
    </Card>
  );
}

/**
 * Ders ekleme/düzenleme dialog'u — TEK bileşen. `course` verilirse düzenleme
 * kipidir: alanlar mevcut kayıttan dolar, kaydetme `updateCourse`'a gider.
 * (Sınav biçimi hem MEB tohumunda hem elle girişte değişebilmeli; ayrı bir
 * "yalnız sınav biçimi" dialog'u üçüncü bir seviye/tür kaynağı doğururdu.)
 */
function CourseDialog({
  levels,
  course,
  onClose,
  onSaved,
}: {
  levels: GradeLevelOption[];
  course?: Course | null;
  onClose: () => void;
  onSaved: () => void;
}) {
  const [name, setName] = useState(course?.name ?? "");
  const [selected, setSelected] = useState<number[]>(course?.levels ?? []);
  const [courseType, setCourseType] = useState<CourseType>(course?.course_type ?? "COMMON");
  const [examMode, setExamMode] = useState<CourseExamMode>(course?.exam_mode ?? "WRITTEN");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const snackbar = useSnackbar();

  const toggleLevel = (value: number) => {
    setSelected((current) =>
      current.includes(value)
        ? current.filter((item) => item !== value)
        : [...current, value].sort((a, b) => a - b),
    );
  };

  const save = async () => {
    if (!name.trim()) {
      setError("Ders adı zorunludur.");
      return;
    }
    if (selected.length === 0) {
      setError("En az bir seviye seçin.");
      return;
    }
    setBusy(true);
    setError(null);
    const body = {
      name: name.trim(),
      levels: selected,
      course_type: courseType,
      exam_mode: examMode,
    };
    try {
      if (course) {
        await derslerApi.updateCourse(course.id, body);
        snackbar.success(`'${body.name}' güncellendi.`);
      } else {
        await derslerApi.createCourse(body);
        snackbar.success(`'${body.name}' havuza eklendi.`);
      }
      onSaved();
    } catch (err) {
      setError(
        err instanceof ApiError
          ? err.message
          : course
            ? "Ders güncellenemedi."
            : "Ders eklenemedi.",
      );
      setBusy(false);
    }
  };

  return (
    <Dialog
      open
      onClose={onClose}
      title={course ? `Dersi düzenle: ${course.name}` : "Havuza ders ekle"}
      actions={
        <>
          <Button variant="text" onClick={onClose} disabled={busy}>
            Vazgeç
          </Button>
          <Button icon="check" onClick={save} disabled={busy}>
            {busy ? "Kaydediliyor…" : course ? "Kaydet" : "Ekle"}
          </Button>
        </>
      }
    >
      <div className="space-y-4">
        {error && <ErrorBanner message={error} />}
        <TextField
          label="Ders adı"
          required
          value={name}
          onChange={(event) => setName(event.target.value)}
          placeholder="Örn. Astronomi ve Uzay Bilimleri"
        />
        <div>
          <p className="text-label-medium text-on-surface-variant">Seviyeler</p>
          <div className="mt-2 flex flex-wrap gap-2">
            {levels.map((item) => {
              const active = selected.includes(item.value);
              return (
                <button
                  key={item.value}
                  type="button"
                  aria-pressed={active}
                  onClick={() => toggleLevel(item.value)}
                  className={`rounded-shape-sm border px-3 py-1.5 text-label-large transition focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary ${
                    active
                      ? "border-primary bg-primary text-on-primary"
                      : "border-outline-variant bg-surface-container-low text-on-surface"
                  }`}
                >
                  {item.label}
                </button>
              );
            })}
          </div>
        </div>
        <Select
          label="Tür"
          value={courseType}
          onChange={(event) => setCourseType(event.target.value as CourseType)}
          options={[
            { value: "COMMON", label: COURSE_TYPE_TR.COMMON },
            { value: "ELECTIVE", label: COURSE_TYPE_TR.ELECTIVE },
          ]}
          helperText="Ortak dersler takvim havuzuna topluca eklenir; seçmeliler seviye seviye seçilir."
        />
        <Select
          label="Sınav"
          value={examMode}
          onChange={(event) => setExamMode(event.target.value as CourseExamMode)}
          options={[
            { value: "WRITTEN", label: COURSE_EXAM_MODE_TR.WRITTEN },
            { value: "PRACTICE", label: COURSE_EXAM_MODE_TR.PRACTICE },
            { value: "NONE", label: COURSE_EXAM_MODE_TR.NONE },
          ]}
          helperText="Uygulama ve “sınav yok” dersleri takvim havuzuna kendiliğinden eklenmez; gerekirse havuz panelinden elle eklersiniz."
        />
      </div>
    </Dialog>
  );
}

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
