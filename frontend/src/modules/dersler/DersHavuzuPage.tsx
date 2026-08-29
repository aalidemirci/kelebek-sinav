// Ders havuzu — MEB çizelgesinden tohumlanan katalog + elle ekleme + pasifleştirme
// + mükerrer birleştirme (tasarım §7). Liste ilk açılışta backend tembel tohumunu
// tetikler (K5); veri dosyası yoksa havuz boş başlar ve elle ekleme yolu açıktır (TB2).

import { useCallback, useEffect, useState } from "react";

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
import { COURSE_SOURCE_TR, COURSE_TYPE_TR, derslerApi } from "./api";
import type { Course, CourseType, DuplicateCluster } from "./api";

export default function DersHavuzuPage() {
  const [rows, setRows] = useState<Course[]>([]);
  const [levels, setLevels] = useState<GradeLevelOption[]>([]);
  const [level, setLevel] = useState<number | null>(null);
  const [courseType, setCourseType] = useState<CourseType | null>(null);
  const [showInactive, setShowInactive] = useState(false);
  const [query, setQuery] = useState("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [adding, setAdding] = useState(false);
  const [duplicates, setDuplicates] = useState<DuplicateCluster[]>([]);

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
            ekleyebilirsiniz. Ders silinmez — pasifleştirilir.
          </p>
        </div>
        <Button icon="add" onClick={() => setAdding(true)}>
          Ders ekle
        </Button>
      </div>

      {error && <ErrorBanner message={error} />}

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
                <th className="px-4 py-3">Kaynak</th>
                <th className="px-4 py-3">Durum</th>
                <th className="px-4 py-3 text-right">İşlem</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((course) => (
                <CourseRow key={course.id} course={course} onChanged={load} />
              ))}
            </tbody>
          </table>
        </Card>
      )}

      {adding && (
        <CourseDialog
          levels={levels}
          onClose={() => setAdding(false)}
          onSaved={() => {
            setAdding(false);
            load();
          }}
        />
      )}
    </div>
  );
}

function CourseRow({ course, onChanged }: { course: Course; onChanged: () => void }) {
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
      <td className="px-4 py-3 text-on-surface-variant">{COURSE_SOURCE_TR[course.source]}</td>
      <td className="px-4 py-3">
        {course.is_active ? (
          <span className="rounded-shape-sm bg-success-container px-2 py-0.5 text-label-medium text-on-success-container">
            Aktif
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
          icon={course.is_active ? "visibility_off" : "visibility"}
          onClick={toggleActive}
          disabled={busy}
        >
          {course.is_active ? "Pasifleştir" : "Aktifleştir"}
        </Button>
      </td>
    </tr>
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

function CourseDialog({
  levels,
  onClose,
  onSaved,
}: {
  levels: GradeLevelOption[];
  onClose: () => void;
  onSaved: () => void;
}) {
  const [name, setName] = useState("");
  const [selected, setSelected] = useState<number[]>([]);
  const [courseType, setCourseType] = useState<CourseType>("COMMON");
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
    try {
      await derslerApi.createCourse({
        name: name.trim(),
        levels: selected,
        course_type: courseType,
      });
      snackbar.success(`'${name.trim()}' havuza eklendi.`);
      onSaved();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Ders eklenemedi.");
      setBusy(false);
    }
  };

  return (
    <Dialog
      open
      onClose={onClose}
      title="Havuza ders ekle"
      actions={
        <>
          <Button variant="text" onClick={onClose} disabled={busy}>
            Vazgeç
          </Button>
          <Button icon="check" onClick={save} disabled={busy}>
            {busy ? "Ekleniyor…" : "Ekle"}
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
