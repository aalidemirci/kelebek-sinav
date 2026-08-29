// Sınav Sihirbazı — OYS `sinav-islemleri/SinavSihirbazi.tsx`'ten UYARLANDI (F3).
// TASLAK oturumun 5 adımı:
//   0 Veri Ön Kontrolü (B10 — beyan esaslı: sayılar + son aktarım tazeliği;
//     OYS'deki e-Okul nakil hareket sorgusu KS'de YOK)
//   1 Oturum bilgileri (düzen seçimi; gözetmen anahtarı (proctors_enabled) F7 ile Adım 1'e geldi)
//   2 Ders ve katılımcılar (LEVEL | SECTIONS — GROUPS kaldırıldı, TB7;
//     canlı sayılar + çakışma uyarıları)
//   3 Salon seçimi (klasikte adım atlanır) + kapasite yeterlilik çubuğu
//   4 Dağıt & Önizle (seed/katı mod; sonuç bağımsız doğrulayıcıdan)
// Tüm iş kuralları backend'de; sihirbaz yalnız uçları sırayla sürer.

import { useCallback, useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { ApiError } from "../../lib/api";
import { formatDateTime } from "../../lib/format";
import { gradeLevelLabel } from "../../lib/gradeLevels";
import Autocomplete from "../../ui/Autocomplete";
import Button from "../../ui/Button";
import Card from "../../ui/Card";
import Dialog from "../../ui/Dialog";
import Select from "../../ui/Select";
import Stepper from "../../ui/Stepper";
import type { StepperItem, StepperStatus } from "../../ui/Stepper";
import TextField from "../../ui/TextField";
import { useSnackbar } from "../../ui/SnackbarProvider";
import type { Course } from "../dersler/api";
import { derslerApi } from "../dersler/api";
import { okulApi } from "../okul/api";
import { examRoomApi } from "../salonlar/api";
import type { ExamSession, LayoutModeCode, ParticipantTypeCode } from "./api";
import { examSessionApi } from "./api";

const STEPS = [
  { key: "precheck", label: "Veri Ön Kontrolü", icon: "fact_check" },
  { key: "info", label: "Oturum Bilgileri", icon: "event" },
  { key: "courses", label: "Ders ve Katılımcılar", icon: "menu_book" },
  { key: "rooms", label: "Salonlar", icon: "meeting_room" },
  { key: "distribute", label: "Dağıt & Önizle", icon: "shuffle" },
];

interface SihirbazProps {
  session: ExamSession;
  onChanged: () => void; // oturum verisi değişti — detay sorgusunu tazele
}

export default function SinavSihirbazi({ session, onChanged }: SihirbazProps) {
  // Ön kontrol onayı verilmişse Adım 0 atlanır (onay oturuma yazılıdır).
  const [step, setStep] = useState(session.transfer_check_confirmed_at ? 1 : 0);
  const isClassic = session.layout_mode === "HOME_CLASSROOM";

  const items: StepperItem[] = STEPS.map((s, i) => {
    let status: StepperStatus = i < step ? "done" : i === step ? "current" : "upcoming";
    if (s.key === "rooms" && isClassic) status = i === step ? "current" : "skipped";
    return { ...s, status };
  });

  // Klasik düzende salon adımı yoktur: 2↔4 arası ±2 sıçranır.
  const goNext = () => setStep((s) => Math.min(s + (s === 2 && isClassic ? 2 : 1), 4));
  const goBack = () => setStep((s) => Math.max(s - (s === 4 && isClassic ? 2 : 1), 0));

  return (
    <div className="flex flex-col gap-4">
      <Stepper items={items} ariaLabel="Sınav sihirbazı adımları" />
      {step === 0 && <PreCheckStep session={session} onChanged={onChanged} onNext={goNext} />}
      {step === 1 && (
        <InfoStep session={session} onChanged={onChanged} onNext={goNext} onBack={goBack} />
      )}
      {step === 2 && (
        <CoursesStep session={session} onChanged={onChanged} onNext={goNext} onBack={goBack} />
      )}
      {step === 3 && !isClassic && (
        <RoomsStep session={session} onChanged={onChanged} onNext={goNext} onBack={goBack} />
      )}
      {step === 4 && <DistributeStep session={session} onChanged={onChanged} onBack={goBack} />}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Adım 0 — Veri Ön Kontrolü (B10: beyan esaslı)
// ---------------------------------------------------------------------------
function PreCheckStep({ session, onChanged, onNext }: SihirbazProps & { onNext: () => void }) {
  const snackbar = useSnackbar();
  const summary = useQuery({ queryKey: ["exam-pre-check"], queryFn: examSessionApi.preCheck });
  const [checked, setChecked] = useState(false);
  const confirmed = session.transfer_check_confirmed_at !== null;

  const confirm = useMutation({
    mutationFn: () => examSessionApi.confirmTransferCheck(session.id),
    onSuccess: () => {
      snackbar.success("Ön kontrol onayı kaydedildi.");
      onChanged();
      onNext();
    },
    onError: (e) => snackbar.error(e instanceof ApiError ? e.message : "Onay kaydedilemedi."),
  });

  const levels = summary.data?.active_students_by_level ?? {};
  const lastImport = summary.data?.last_student_import;

  return (
    <Card elevation={1} className="flex flex-col gap-4 p-5">
      <h3 className="text-title-medium text-on-surface">Veri Ön Kontrolü</h3>
      <p className="text-body-medium text-on-surface-variant">
        Dağıtım öğrenci sicilinden beslenir. Nakil gelen/giden güncellemelerinin işlendiğini
        onaylamadan devam edilemez; onay kim/ne zaman bilgisiyle oturuma yazılır.
      </p>
      <div className="grid gap-3 sm:grid-cols-2">
        <div>
          <h4 className="mb-1 text-title-small text-on-surface">Aktif öğrenci sayıları</h4>
          <ul className="text-body-medium text-on-surface">
            {Object.entries(levels)
              .sort((a, b) => Number(a[0]) - Number(b[0]))
              .map(([level, count]) => (
                <li
                  key={level}
                  className="flex justify-between border-b border-outline-variant py-1"
                >
                  <span>{gradeLevelLabel(Number(level))}</span>
                  <span>{count}</span>
                </li>
              ))}
          </ul>
        </div>
        <div>
          <h4 className="mb-1 text-title-small text-on-surface">Son öğrenci aktarımı</h4>
          {summary.isSuccess && lastImport === null && (
            <p role="alert" className="text-body-medium text-error">
              Henüz öğrenci aktarımı yapılmamış — önce Okul modülünden e-Okul listesini aktarın.
            </p>
          )}
          {lastImport && (
            <ul className="text-body-medium text-on-surface">
              <li className="flex justify-between gap-3 border-b border-outline-variant py-1">
                <span className="text-on-surface-variant">Dosya</span>
                <span className="truncate">{lastImport.file_name}</span>
              </li>
              <li className="flex justify-between gap-3 border-b border-outline-variant py-1">
                <span className="text-on-surface-variant">Tarih</span>
                <span>{formatDateTime(lastImport.finished_at)}</span>
              </li>
            </ul>
          )}
        </div>
      </div>
      {confirmed ? (
        <p className="text-body-medium text-on-surface-variant">
          ✓ Onaylandı: {session.transfer_check_confirmed_by_name || "—"} —{" "}
          {formatDateTime(session.transfer_check_confirmed_at)}
        </p>
      ) : (
        <label className="flex min-h-9 cursor-pointer items-center gap-3 text-body-medium text-on-surface">
          <input
            type="checkbox"
            checked={checked}
            onChange={(e) => setChecked(e.target.checked)}
            className="h-5 w-5 accent-primary"
          />
          Nakil gelen/giden öğrenci güncellemeleri yapıldı; liste günceldir.
        </label>
      )}
      <div className="flex justify-end gap-2">
        {confirmed ? (
          <Button onClick={onNext}>Devam</Button>
        ) : (
          <Button onClick={() => confirm.mutate()} disabled={!checked || confirm.isPending}>
            Onayla ve devam et
          </Button>
        )}
      </div>
    </Card>
  );
}

// ---------------------------------------------------------------------------
// Adım 1 — Oturum bilgileri
// ---------------------------------------------------------------------------
function InfoStep({
  session,
  onChanged,
  onNext,
  onBack,
}: SihirbazProps & { onNext: () => void; onBack: () => void }) {
  const snackbar = useSnackbar();
  const [form, setForm] = useState({
    name: session.name,
    exam_date: session.exam_date,
    start_time: session.start_time.slice(0, 5),
    duration_minutes: String(session.duration_minutes),
    layout_mode: session.layout_mode as LayoutModeCode,
    proctors_enabled: session.proctors_enabled,
  });

  const save = useMutation({
    mutationFn: () =>
      examSessionApi.update(session.id, {
        name: form.name.trim(),
        exam_date: form.exam_date,
        start_time: form.start_time,
        duration_minutes: Number(form.duration_minutes),
        layout_mode: form.layout_mode,
        proctors_enabled: form.proctors_enabled,
      }),
    onSuccess: () => {
      onChanged();
      onNext();
    },
    onError: (e) => snackbar.error(e instanceof ApiError ? e.message : "Kaydedilemedi."),
  });

  return (
    <Card elevation={1} className="flex flex-col gap-3 p-5">
      <h3 className="text-title-medium text-on-surface">Oturum Bilgileri</h3>
      <TextField
        label="Oturum adı"
        value={form.name}
        onChange={(e) => setForm((f) => ({ ...f, name: e.target.value }))}
        required
      />
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-3">
        <TextField
          label="Sınav tarihi"
          type="date"
          value={form.exam_date}
          onChange={(e) => setForm((f) => ({ ...f, exam_date: e.target.value }))}
        />
        <TextField
          label="Başlangıç"
          type="time"
          value={form.start_time}
          onChange={(e) => setForm((f) => ({ ...f, start_time: e.target.value }))}
        />
        <TextField
          label="Süre (dk)"
          type="number"
          min={10}
          max={240}
          value={form.duration_minutes}
          onChange={(e) => setForm((f) => ({ ...f, duration_minutes: e.target.value }))}
        />
      </div>
      <Select
        label="Düzen"
        options={[
          { value: "BUTTERFLY", label: "Kelebek (karışık dağıtım)" },
          { value: "HOME_CLASSROOM", label: "Kendi dersliğinde (klasik)" },
        ]}
        value={form.layout_mode}
        onChange={(e) => setForm((f) => ({ ...f, layout_mode: e.target.value as LayoutModeCode }))}
        helperText="Klasikte salon seçimi yoktur — öğrenciler bağlı dersliklerine yerleşir."
      />
      <label className="flex min-h-9 items-center gap-2 text-body-medium text-on-surface">
        <input
          type="checkbox"
          className="h-5 w-5 accent-primary"
          checked={form.proctors_enabled}
          onChange={(e) => setForm((f) => ({ ...f, proctors_enabled: e.target.checked }))}
        />
        Gözetmen modülü açık (görevlendirme + R6 belgesi)
      </label>
      <p className="text-body-small text-on-surface-variant">Dönem: {session.term_label}</p>
      <div className="flex justify-between">
        <Button variant="text" onClick={onBack}>
          Geri
        </Button>
        <Button onClick={() => save.mutate()} disabled={save.isPending || !form.name.trim()}>
          Kaydet ve devam et
        </Button>
      </div>
    </Card>
  );
}

// ---------------------------------------------------------------------------
// Adım 2 — Ders ve katılımcılar (LEVEL | SECTIONS — TB7)
// ---------------------------------------------------------------------------
function CoursesStep({
  session,
  onChanged,
  onNext,
  onBack,
}: SihirbazProps & { onNext: () => void; onBack: () => void }) {
  const snackbar = useSnackbar();
  const qc = useQueryClient();
  const [addOpen, setAddOpen] = useState(false);
  // Dialog odak efekti onClose kimliğine bağlı — sabit referans şart.
  const closeAdd = useCallback(() => setAddOpen(false), []);
  const [course, setCourse] = useState<Course | null>(null);
  const [level, setLevel] = useState("");
  const [ptype, setPtype] = useState<ParticipantTypeCode>("LEVEL");
  const [sectionIds, setSectionIds] = useState<number[]>([]);
  const [sharedBooklet, setSharedBooklet] = useState(false);

  const courses = useQuery({ queryKey: ["courses"], queryFn: () => derslerApi.listCourses() });
  // Typeahead: havuz küçük ve zaten yüklü — ilk harf filtresi istemci tarafında,
  // Türkçe küçük-büyük duyarlı (İ/ı) karşılaştırmayla.
  const searchCourses = useCallback(
    async (q: string) => {
      const needle = q.toLocaleLowerCase("tr");
      const rows = courses.data ?? [];
      const starts = rows.filter((c) => c.name.toLocaleLowerCase("tr").startsWith(needle));
      const contains = rows.filter(
        (c) =>
          !c.name.toLocaleLowerCase("tr").startsWith(needle) &&
          c.name.toLocaleLowerCase("tr").includes(needle),
      );
      return [...starts, ...contains];
    },
    [courses.data],
  );
  // Şube seçimi okul modülünün şube kataloğundan (F1).
  const sections = useQuery({
    queryKey: ["class-sections"],
    queryFn: () => okulApi.listClassSections(),
  });
  // Katılımcı önizlemesi: ders eklendikçe canlı sayılar + çakışma uyarıları.
  const participants = useQuery({
    queryKey: ["exam-participants", session.id, session.courses.length],
    queryFn: () => examSessionApi.participants(session.id),
    enabled: session.courses.length > 0,
  });

  const resetForm = () => {
    setCourse(null);
    setLevel("");
    setPtype("LEVEL");
    setSectionIds([]);
    setSharedBooklet(false);
  };

  const addCourse = useMutation({
    mutationFn: () =>
      examSessionApi.addCourse(session.id, {
        course_id: course?.id ?? 0,
        participant_type: ptype,
        level: ptype === "LEVEL" ? Number(level) : undefined,
        section_ids: ptype === "SECTIONS" ? sectionIds : undefined,
        shared_booklet: sharedBooklet,
      }),
    onSuccess: () => {
      setAddOpen(false);
      resetForm();
      onChanged();
      void qc.invalidateQueries({ queryKey: ["exam-participants", session.id] });
    },
    onError: (e) => snackbar.error(e instanceof ApiError ? e.message : "Ders eklenemedi."),
  });

  const removeCourse = useMutation({
    mutationFn: (sessionCourseId: number) => examSessionApi.removeCourse(sessionCourseId),
    onSuccess: () => {
      onChanged();
      void qc.invalidateQueries({ queryKey: ["exam-participants", session.id] });
    },
    onError: (e) => snackbar.error(e instanceof ApiError ? e.message : "Ders çıkarılamadı."),
  });

  const canAdd =
    course !== null &&
    ((ptype === "LEVEL" && level !== "") || (ptype === "SECTIONS" && sectionIds.length > 0));

  const countByCourse = useMemo(() => {
    const map = new Map<number, { count: number; warnings: string[] }>();
    for (const c of participants.data?.courses ?? []) {
      map.set(c.session_course_id, { count: c.count, warnings: c.warnings });
    }
    return map;
  }, [participants.data]);

  const blocking = participants.data?.has_blocking_conflicts ?? false;

  const toggleSection = (id: number) =>
    setSectionIds((prev) => (prev.includes(id) ? prev.filter((v) => v !== id) : [...prev, id]));

  return (
    <Card elevation={1} className="flex flex-col gap-4 p-5">
      <div className="flex flex-wrap items-center gap-3">
        <h3 className="text-title-medium text-on-surface">Ders ve Katılımcılar</h3>
        <span className="ml-auto" />
        {participants.data && (
          <span className="rounded-full bg-primary-container px-4 py-2 text-label-large text-on-primary-container">
            Toplam katılımcı: {participants.data.total_count}
          </span>
        )}
        <Button variant="tonal" icon="add" onClick={() => setAddOpen(true)}>
          Ders ekle
        </Button>
      </div>

      {session.courses.length === 0 && (
        <p className="text-body-medium text-on-surface-variant">
          Henüz ders eklenmedi. Her ders için katılımcılar seviye geneli veya şube şube atanır (aynı
          seviye + aynı ders = aynı kitapçık → çakışma grubu).
        </p>
      )}

      <ul className="flex flex-col gap-2">
        {session.courses.map((row) => {
          const info = countByCourse.get(row.id);
          return (
            <li
              key={row.id}
              className="flex flex-wrap items-center gap-3 rounded-shape-md border border-outline-variant p-3"
            >
              <span className="text-title-small text-on-surface">{row.display_label}</span>
              <span className="text-body-small text-on-surface-variant">
                {row.participant_type === "LEVEL" && "Seviye geneli"}
                {row.participant_type === "SECTIONS" && `${row.section_ids.length} şube`}
              </span>
              {info && (
                <span className="text-body-small text-on-surface-variant">
                  {info.count} öğrenci
                </span>
              )}
              <span className="ml-auto" />
              <Button
                variant="text"
                icon="delete"
                onClick={() => removeCourse.mutate(row.id)}
                disabled={removeCourse.isPending}
              >
                Çıkar
              </Button>
              {info && info.warnings.length > 0 && (
                <ul className="w-full text-body-small text-error">
                  {info.warnings.map((w) => (
                    <li key={w}>⚠ {w}</li>
                  ))}
                </ul>
              )}
            </li>
          );
        })}
      </ul>

      {participants.data && participants.data.warnings.length > 0 && (
        <ul role="alert" className="text-body-small text-error">
          {participants.data.warnings.map((w) => (
            <li key={w}>⚠ {w}</li>
          ))}
        </ul>
      )}
      {blocking && (
        <p role="alert" className="text-body-medium text-error">
          Bir öğrenci aynı oturumda birden çok derse düşüyor — dağıtım engellenecek; ders
          katılımcılarını düzeltin.
        </p>
      )}

      <div className="flex justify-between">
        <Button variant="text" onClick={onBack}>
          Geri
        </Button>
        <Button onClick={onNext} disabled={session.courses.length === 0 || blocking}>
          Devam
        </Button>
      </div>

      <Dialog
        open={addOpen}
        onClose={closeAdd}
        title="Ders ekle"
        actions={
          <>
            <Button variant="text" onClick={closeAdd}>
              Vazgeç
            </Button>
            <Button onClick={() => addCourse.mutate()} disabled={addCourse.isPending || !canAdd}>
              Ekle
            </Button>
          </>
        }
      >
        <div className="flex flex-col gap-3">
          <Autocomplete<Course>
            label="Ders (havuzdan)"
            placeholder="İlk harfleri yazın…"
            required
            minChars={1}
            selected={course}
            onSelect={(c) => {
              setCourse(c);
              // Tek seviyeli ders: seviye otomatik dolar; çok seviyelide seçim istenir.
              setLevel(c.levels.length === 1 ? String(c.levels[0]) : "");
              setSectionIds([]);
            }}
            onClear={() => {
              setCourse(null);
              setLevel("");
              setSectionIds([]);
            }}
            search={searchCourses}
            getKey={(c) => c.id}
            getLabel={(c) => c.name}
            getSublabel={(c) => `Seviyeler: ${c.level_labels.join(", ")}`}
          />
          {course && (
            <Select
              label="Seviye"
              options={course.levels.map((lv) => ({
                value: String(lv),
                label: gradeLevelLabel(lv),
              }))}
              placeholder="Seçin"
              value={level}
              onChange={(e) => {
                setLevel(e.target.value);
                setSectionIds([]);
              }}
              required
              helperText="Aynı ders adı olsa da her seviye ayrı içerik/soru demektir; satır seviye başına eklenir."
            />
          )}
          <Select
            label="Katılımcı tipi"
            options={[
              { value: "LEVEL", label: "Seviye geneli" },
              { value: "SECTIONS", label: "Şube şube" },
            ]}
            value={ptype}
            onChange={(e) => setPtype(e.target.value as ParticipantTypeCode)}
          />
          {ptype === "SECTIONS" && (
            <fieldset>
              <legend className="mb-1 text-label-large text-on-surface-variant">
                Şubeler{level !== "" && ` (${gradeLevelLabel(Number(level))})`}
              </legend>
              <div className="grid max-h-48 grid-cols-3 gap-1 overflow-y-auto">
                {(sections.data ?? [])
                  .filter((s) => level === "" || s.class_level === Number(level))
                  .map((s) => (
                    <label
                      key={s.id}
                      className="flex min-h-9 cursor-pointer items-center gap-2 rounded-shape-sm border border-outline px-3 text-body-medium text-on-surface"
                    >
                      <input
                        type="checkbox"
                        checked={sectionIds.includes(s.id)}
                        onChange={() => toggleSection(s.id)}
                        className="h-5 w-5 accent-primary"
                      />
                      {s.class_label}
                    </label>
                  ))}
              </div>
            </fieldset>
          )}
          <label className="flex min-h-9 cursor-pointer items-center gap-3 text-body-medium text-on-surface">
            <input
              type="checkbox"
              checked={sharedBooklet}
              onChange={(e) => setSharedBooklet(e.target.checked)}
              className="h-5 w-5 accent-primary"
            />
            Ortak kitapçık (bu dersin tüm seviyeleri tek kitapçık/tek çakışma grubu)
          </label>
        </div>
      </Dialog>
    </Card>
  );
}

// ---------------------------------------------------------------------------
// Adım 3 — Salonlar (yalnız kelebek düzeninde)
// ---------------------------------------------------------------------------
function RoomsStep({
  session,
  onChanged,
  onNext,
  onBack,
}: SihirbazProps & { onNext: () => void; onBack: () => void }) {
  const snackbar = useSnackbar();
  const rooms = useQuery({ queryKey: ["exam-rooms"], queryFn: () => examRoomApi.list(false) });
  const participants = useQuery({
    queryKey: ["exam-participants", session.id, session.courses.length],
    queryFn: () => examSessionApi.participants(session.id),
    enabled: session.courses.length > 0,
  });
  const [selected, setSelected] = useState<number[]>(session.rooms.map((r) => r.room_id));

  const save = useMutation({
    mutationFn: () =>
      examSessionApi.setRooms(
        session.id,
        selected.map((room_id) => ({ room_id })),
      ),
    onSuccess: () => {
      onChanged();
      onNext();
    },
    onError: (e) => snackbar.error(e instanceof ApiError ? e.message : "Salonlar kaydedilemedi."),
  });

  const roomList = rooms.data?.results ?? [];
  const capacity = roomList
    .filter((r) => selected.includes(r.id))
    .reduce((sum, r) => sum + r.capacity, 0);
  const needed = participants.data?.total_count ?? 0;
  const enough = capacity >= needed;
  const ratio = needed > 0 ? Math.min(capacity / needed, 1) : selected.length > 0 ? 1 : 0;

  return (
    <Card elevation={1} className="flex flex-col gap-4 p-5">
      <h3 className="text-title-medium text-on-surface">Salon Seçimi</h3>
      <div>
        <div className="mb-1 flex justify-between text-body-medium text-on-surface">
          <span>Kapasite: {capacity}</span>
          <span>Gereken: {needed}</span>
        </div>
        {/* Kapasite yeterlilik çubuğu. */}
        <div
          role="progressbar"
          aria-label="Kapasite yeterliliği"
          aria-valuenow={Math.round(ratio * 100)}
          aria-valuemin={0}
          aria-valuemax={100}
          className="h-3 overflow-hidden rounded-full bg-surface-container-high"
        >
          <div
            className={`h-full rounded-full transition-all ${enough ? "bg-primary" : "bg-error"}`}
            style={{ width: `${Math.round(ratio * 100)}%` }}
          />
        </div>
        {!enough && needed > 0 && (
          <p role="alert" className="mt-1 text-body-small text-error">
            Kapasite yetersiz — {needed - capacity} koltuk daha gerekli.
          </p>
        )}
      </div>
      <div className="flex gap-2">
        <Button
          variant="text"
          icon="select_all"
          onClick={() => setSelected(roomList.map((r) => r.id))}
          disabled={roomList.length === 0}
        >
          Tümünü seç
        </Button>
        <Button
          variant="text"
          icon="deselect"
          onClick={() => setSelected([])}
          disabled={selected.length === 0}
        >
          Temizle
        </Button>
      </div>
      <div className="grid gap-2 sm:grid-cols-2 lg:grid-cols-3">
        {roomList.map((room) => (
          <label
            key={room.id}
            className="flex min-h-9 cursor-pointer items-center gap-3 rounded-shape-md border border-outline-variant px-3 py-2 text-body-medium text-on-surface"
          >
            <input
              type="checkbox"
              checked={selected.includes(room.id)}
              onChange={() =>
                setSelected((prev) =>
                  prev.includes(room.id) ? prev.filter((id) => id !== room.id) : [...prev, room.id],
                )
              }
              className="h-5 w-5 accent-primary"
            />
            <span className="flex-1">{room.name}</span>
            <span className="text-body-small text-on-surface-variant">{room.capacity} koltuk</span>
          </label>
        ))}
      </div>
      <div className="flex justify-between">
        <Button variant="text" onClick={onBack}>
          Geri
        </Button>
        <Button onClick={() => save.mutate()} disabled={save.isPending || selected.length === 0}>
          Kaydet ve devam et
        </Button>
      </div>
    </Card>
  );
}

// ---------------------------------------------------------------------------
// Adım 4 — Dağıt & Önizle
// ---------------------------------------------------------------------------
function DistributeStep({ session, onChanged, onBack }: SihirbazProps & { onBack: () => void }) {
  const snackbar = useSnackbar();
  const [seed, setSeed] = useState("");
  const [strict, setStrict] = useState(false);

  const distribute = useMutation({
    mutationFn: () =>
      examSessionApi.distribute(session.id, {
        seed: seed === "" ? undefined : Number(seed),
        strict,
      }),
    onSuccess: (result) => {
      snackbar.success(`Dağıtım tamam: ${result.placed} öğrenci yerleşti (seed ${result.seed}).`);
      onChanged(); // durum DISTRIBUTED → detay sekmeli görünüme geçer
    },
    onError: (e) => snackbar.error(e instanceof ApiError ? e.message : "Dağıtım başarısız."),
  });

  return (
    <Card elevation={1} className="flex flex-col gap-4 p-5">
      <h3 className="text-title-medium text-on-surface">Dağıt &amp; Önizle</h3>
      <p className="text-body-medium text-on-surface-variant">
        Kelebek motoru aynı kitapçığı cevaplayanları bitiştirmez ve salon geometrisinde
        olabildiğince uzak tutar; sonuç bağımsız doğrulayıcıdan geçer. Aynı seed aynı yerleşimi
        üretir.
      </p>
      <div className="grid grid-cols-2 gap-3">
        <TextField
          label="Seed (boş = rastgele)"
          type="number"
          min={1}
          max={999999}
          value={seed}
          onChange={(e) => setSeed(e.target.value)}
          helperText="Seed, rastgele karıştırmanın başlangıç değeridir: aynı seed her zaman AYNI yerleşimi üretir. Boş bırakılırsa her dağıtımda yeni rastgele seed seçilir; kullanılan değer dağıtım sonrası gösterilir — bir yerleşimi yeniden üretmek için onu girin."
        />
        <label className="flex min-h-9 cursor-pointer items-center gap-3 text-body-medium text-on-surface">
          <input
            type="checkbox"
            checked={strict}
            onChange={(e) => setStrict(e.target.checked)}
            className="h-5 w-5 accent-primary"
          />
          Katı mod (1. halka — yan/ön/arka — da sert kısıt)
        </label>
      </div>
      <div className="flex justify-between">
        <Button variant="text" onClick={onBack}>
          Geri
        </Button>
        <Button icon="shuffle" onClick={() => distribute.mutate()} disabled={distribute.isPending}>
          {distribute.isPending ? "Dağıtılıyor…" : "Dağıt"}
        </Button>
      </div>
    </Card>
  );
}
