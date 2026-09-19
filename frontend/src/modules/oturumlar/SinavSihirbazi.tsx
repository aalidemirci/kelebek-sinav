// Sınav Sihirbazı — OYS `sinav-islemleri/SinavSihirbazi.tsx`'ten UYARLANDI (F3).
// TASLAK oturumun 5 adımı:
//   0 Veri Ön Kontrolü (B10 — beyan esaslı: sayılar + son aktarım tazeliği;
//     OYS'deki e-Okul nakil hareket sorgusu KS'de YOK)
//   1 Oturum bilgileri (düzen seçimi; gözetmen anahtarı (proctors_enabled) F7 ile Adım 1'e geldi)
//   2 Ders ve katılımcılar (LEVEL | SECTIONS — GROUPS kaldırıldı, TB7;
//     canlı sayılar + çakışma uyarıları)
//   3 Salon seçimi (klasikte adım atlanır) + kapasite yeterlilik çubuğu
//   4 Dağıt (dağıtım numarası/katı dağıtım; sonuç bağımsız doğrulayıcıdan)
// Tüm iş kuralları backend'de; sihirbaz yalnız uçları sırayla sürer.

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Link } from "react-router-dom";

import { ApiError } from "../../lib/api";
import { formatDateTime } from "../../lib/format";
import { gradeLevelLabel } from "../../lib/gradeLevels";
import Autocomplete from "../../ui/Autocomplete";
import Button from "../../ui/Button";
import Card from "../../ui/Card";
import Dialog from "../../ui/Dialog";
import Icon from "../../ui/Icon";
import Select from "../../ui/Select";
import Stepper from "../../ui/Stepper";
import type { StepperItem, StepperStatus } from "../../ui/Stepper";
import TextField from "../../ui/TextField";
import { useSnackbar } from "../../ui/SnackbarProvider";
import type { Course } from "../dersler/api";
import { derslerApi } from "../dersler/api";
import { okulApi } from "../okul/api";
import { examRoomApi, examRoomGroupApi } from "../salonlar/api";
import DagitimSecenekleri, {
  BOS_DAGITIM_SECENEKLERI,
  DagitimSonucu,
  dagitimCumlesi,
  dagitimGovdesi,
} from "./DagitimSecenekleri";
import OturumKopyalaDialog from "./OturumKopyalaDialog";
import type {
  DistributeResult,
  ExamSession,
  ExamSessionCourseRow,
  LayoutModeCode,
  ParticipantTypeCode,
} from "./api";
import {
  examSessionApi,
  LAYOUT_MODE_OPTIONS,
  PARTICIPANT_TYPE_TR,
  PROCTORS_ENABLED_LABEL,
  usesDistributionNumber,
} from "./api";

const STEPS = [
  { key: "precheck", label: "Veri Ön Kontrolü", icon: "fact_check" },
  { key: "info", label: "Oturum Bilgileri", icon: "event" },
  { key: "courses", label: "Ders ve Katılımcılar", icon: "menu_book" },
  { key: "rooms", label: "Salonlar", icon: "meeting_room" },
  { key: "distribute", label: "Dağıt", icon: "shuffle" },
];

interface SihirbazProps {
  session: ExamSession;
  onChanged: () => void; // oturum verisi değişti — detay sorgusunu tazele
}

/**
 * Sihirbazın açıldığı adım — kullanıcının KALDIĞI yer (18.09.2026 değerlendirmesi:
 * sihirbaz her açılışta başa dönüyordu). Ön kontrol onayı yoksa 0; onaylı ve ders
 * yoksa 1; ders varsa 2 — "Taslağa al"dan dönen kullanıcı düzeltmeye tanımların
 * olduğu adımdan başlar, önceki adımlara Stepper'dan tek tıkla döner.
 */
export function initialStep(session: ExamSession): number {
  if (session.transfer_check_confirmed_at === null) return 0;
  return session.courses.length > 0 ? 2 : 1;
}

/** Hata/uyarı satırı — metne ham "⚠" yazılmaz (docs/sozluk.md §3). */
function WarningItem({ text }: { text: string }) {
  return (
    <li className="flex items-start gap-1">
      <Icon name="warning" size="sm" className="mt-0.5 shrink-0" />
      <span>{text}</span>
    </li>
  );
}

export default function SinavSihirbazi({ session, onChanged }: SihirbazProps) {
  const [step, setStep] = useState(() => initialStep(session));
  // Dağıtım yazıldı ama kullanıcı henüz uyarıları okuyor (bkz. DistributeStep):
  // oturum backend'de artık TASLAK değildir, önceki adımlara dönüş kapatılır.
  const [distributed, setDistributed] = useState(false);
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
      {/* Tamamlanmış adımlar tıklanır; "atlandı" (klasikte Salonlar) tıklanamaz —
          Stepper yalnız "done" adımı düğme yapar. */}
      <Stepper
        items={items}
        ariaLabel="Sınav sihirbazı adımları"
        onSelect={distributed ? undefined : (_key, index) => setStep(index)}
      />
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
      {step === 4 && (
        <DistributeStep
          session={session}
          onChanged={onChanged}
          onBack={goBack}
          onDistributed={() => setDistributed(true)}
        />
      )}
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
  // Onaylayan adı: boş bırakılırsa backend kurulumdaki okul müdürünün adını
  // damgalar (`services.confirm_transfer_check`). Eskiden ad hiç sorulmuyor,
  // ekran ise "kim/ne zaman yazılır" diyordu (değerlendirme §3.2).
  const [confirmedBy, setConfirmedBy] = useState("");
  const confirmed = session.transfer_check_confirmed_at !== null;

  const confirm = useMutation({
    mutationFn: () =>
      examSessionApi.confirmTransferCheck(session.id, { confirmed_by_name: confirmedBy.trim() }),
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
        Dağıtım, Kişiler ekranındaki öğrenci listesinden beslenir. Nakil gelen ve giden öğrencilerin
        listeye işlendiğini onaylamadan devam edilemez; onaylayanın adı ve onay zamanı oturuma
        kaydedilir.
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
              Henüz öğrenci aktarımı yapılmamış — önce{" "}
              <Link
                to="/kisiler"
                className="font-medium underline underline-offset-2 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary"
              >
                Kişiler ekranından
              </Link>{" "}
              e-Okul listesini aktarın.
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
        <p className="flex items-center gap-2 text-body-medium text-on-surface-variant">
          <Icon name="check_circle" size="lg" className="text-primary" />
          <span>
            Onaylandı: {session.transfer_check_confirmed_by_name || "—"} —{" "}
            {formatDateTime(session.transfer_check_confirmed_at)}
          </span>
        </p>
      ) : (
        <>
          <label className="flex min-h-9 cursor-pointer items-center gap-3 text-body-medium text-on-surface">
            <input
              type="checkbox"
              checked={checked}
              onChange={(e) => setChecked(e.target.checked)}
              className="h-5 w-5 accent-primary"
            />
            Nakil gelen/giden öğrenci güncellemeleri yapıldı; liste günceldir.
          </label>
          <TextField
            label="Onaylayan (boş bırakılırsa okul müdürü)"
            value={confirmedBy}
            onChange={(e) => setConfirmedBy(e.target.value)}
            maxLength={128}
            className="max-w-md"
          />
        </>
      )}
      <div className="flex justify-end gap-2">
        {confirmed ? (
          <Button onClick={onNext}>Devam</Button>
        ) : (
          <Button onClick={() => confirm.mutate()} disabled={!checked || confirm.isPending}>
            Kaydet ve devam et
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
        options={LAYOUT_MODE_OPTIONS}
        value={form.layout_mode}
        onChange={(e) => setForm((f) => ({ ...f, layout_mode: e.target.value as LayoutModeCode }))}
        helperText="“Kendi dersliğinde” düzeninde salon seçilmez; her şube kendi şube dersliğine yerleşir."
      />
      <label className="flex min-h-9 items-center gap-2 text-body-medium text-on-surface">
        <input
          type="checkbox"
          className="h-5 w-5 accent-primary"
          checked={form.proctors_enabled}
          onChange={(e) => setForm((f) => ({ ...f, proctors_enabled: e.target.checked }))}
        />
        {PROCTORS_ENABLED_LABEL}
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
  const [copyOpen, setCopyOpen] = useState(false);
  const closeCopy = useCallback(() => setCopyOpen(false), []);

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
  // Şube kümeleri (SAY/EA/DİL) — çip yalnız `sectionIds`'i besler, AYRI durum
  // TUTMAZ: "gruptan gelen" ile "elle seçilen" için ikinci kaynak-gerçek doğardı.
  const sectionGroups = useQuery({
    queryKey: ["class-section-groups"],
    queryFn: () => okulApi.listClassSectionGroups(),
  });
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
  };

  // "Aynı kitapçık" bayrağı (shared_booklet) ekleme formunda SORULMAZ: bayrak
  // satırın değil dersin oturum içi niteliğidir ve yalnız aynı ders birden çok
  // seviyede eklenince anlam kazanır; listenin altındaki ders-başı kutudan
  // ayarlanır (backend değeri kardeş satırlara yayar). Eski "Ortak kitapçık"
  // kutusu MEB'in "ortak sınav" terimiyle karışıp her sınavda işaretleniyordu
  // (18.09.2026 TDE 9/10 vakası).
  const addCourse = useMutation({
    mutationFn: () =>
      examSessionApi.addCourse(session.id, {
        course_id: course?.id ?? 0,
        participant_type: ptype,
        level: ptype === "LEVEL" ? Number(level) : undefined,
        section_ids: ptype === "SECTIONS" ? sectionIds : undefined,
      }),
    onSuccess: () => {
      setAddOpen(false);
      resetForm();
      onChanged();
      void qc.invalidateQueries({ queryKey: ["exam-participants", session.id] });
    },
    onError: (e) => snackbar.error(e instanceof ApiError ? e.message : "Ders eklenemedi."),
  });

  const setSharedBooklet = useMutation({
    mutationFn: ({ rowId, value }: { rowId: number; value: boolean }) =>
      examSessionApi.updateCourse(rowId, { shared_booklet: value }),
    onSuccess: () => {
      onChanged();
      void qc.invalidateQueries({ queryKey: ["exam-participants", session.id] });
    },
    onError: (e) =>
      snackbar.error(e instanceof ApiError ? e.message : "Kitapçık ayarı kaydedilemedi."),
  });

  // Aynı ders birden çok seviyede → ders başına "aynı kitapçık" kutusu.
  const multiLevelCourses = useMemo(() => {
    const byCourse = new Map<number, ExamSessionCourseRow[]>();
    for (const row of session.courses) {
      byCourse.set(row.course_id, [...(byCourse.get(row.course_id) ?? []), row]);
    }
    return [...byCourse.values()].filter((rows) => rows.length > 1);
  }, [session.courses]);
  const courseAlreadyInSession =
    course !== null && session.courses.some((row) => row.course_id === course.id);

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
    const map = new Map<number, { count: number; warnings: string[]; listed: string[] }>();
    for (const c of participants.data?.courses ?? []) {
      map.set(c.session_course_id, {
        count: c.count,
        warnings: c.warnings,
        listed: c.listed_sections ?? [],
      });
    }
    return map;
  }, [participants.data]);

  const blocking = participants.data?.has_blocking_conflicts ?? false;

  const toggleSection = (id: number) =>
    setSectionIds((prev) => (prev.includes(id) ? prev.filter((v) => v !== id) : [...prev, id]));

  /**
   * Küme çipi: kümedeki şubeleri seçime EKLER. Seçili seviyeyle KESİŞTİRİLİR —
   * "Eşit Ağırlık" 10-11-12'yi kapsayabilir ama bir oturum dersi TEK seviyeye
   * bağlıdır (backend karışık seviyeyi 400 ile reddeder).
   */
  const applyGroup = (groupId: number) => {
    const lv = level === "" ? null : Number(level);
    const ids = (sections.data ?? [])
      .filter((sec) => sec.group === groupId && (lv === null || sec.class_level === lv))
      .map((sec) => sec.id);
    setSectionIds((prev) => [...new Set([...prev, ...ids])]);
  };

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
        <Button variant="text" icon="content_copy" onClick={() => setCopyOpen(true)}>
          Başka oturumdan kopyala
        </Button>
        <Button variant="tonal" icon="add" onClick={() => setAddOpen(true)}>
          Ders ekle
        </Button>
      </div>

      {session.courses.length === 0 && (
        <p className="text-body-medium text-on-surface-variant">
          Henüz ders eklenmedi. Her ders için sınava kimlerin gireceğini belirleyin: sınıf düzeyinin
          tamamı ya da seçili şubeler. Aynı sınıf düzeyinde aynı dersin sınavına girenler aynı
          kitapçığı çözer; dağıtımda bu öğrenciler yan yana oturtulmaz.
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
                {row.participant_type === "LEVEL" && PARTICIPANT_TYPE_TR.LEVEL}
                {row.participant_type === "SECTIONS" && `${row.section_ids.length} şube`}
              </span>
              {info && (
                <span className="text-body-small text-on-surface-variant">
                  {info.count} öğrenci
                </span>
              )}
              {info && info.listed.length > 0 && (
                // Seçmeli dersi şubenin yalnız bir kısmı alıyor: katılımcılar Ders
                // Havuzu'ndaki öğrenci listesinden gelir (e-Okul aktarımı ya da elle).
                <span className="rounded-shape-sm bg-secondary-container px-2 py-0.5 text-label-medium text-on-secondary-container">
                  öğrenci listesiyle: {info.listed.join(", ")}
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
                <ul className="flex w-full flex-col gap-0.5 text-body-small text-error">
                  {info.warnings.map((w) => (
                    <WarningItem key={w} text={w} />
                  ))}
                </ul>
              )}
            </li>
          );
        })}
      </ul>

      {multiLevelCourses.length > 0 && (
        <div className="flex flex-col gap-2 rounded-shape-md bg-surface-container p-3">
          <h4 className="text-title-small text-on-surface">Aynı ders birden çok sınıf düzeyinde</h4>
          <p className="text-body-small text-on-surface-variant">
            Olağan durumda her sınıf düzeyi kendi sorularını çözer: her düzey için ayrı soru dosyası
            yüklenir ve farklı düzeylerin öğrencileri yan yana oturabilir. Bir dersin tüm sınıf
            düzeyleri <strong>aynı</strong> soru kitapçığını çözecekse aşağıda işaretleyin; o zaman
            tek dosya yüklenir ve bu öğrenciler birbirinin yanına oturtulmaz.
          </p>
          {multiLevelCourses.map((rows) => (
            <label
              key={rows[0].course_id}
              className="flex min-h-9 cursor-pointer items-center gap-3 text-body-medium text-on-surface"
            >
              <input
                type="checkbox"
                checked={rows[0].shared_booklet}
                onChange={(e) =>
                  setSharedBooklet.mutate({ rowId: rows[0].id, value: e.target.checked })
                }
                disabled={setSharedBooklet.isPending}
                className="h-5 w-5 accent-primary"
              />
              {rows[0].course_name}: {rows.map((r) => gradeLevelLabel(r.level)).join(", ")} aynı
              soru kitapçığını çözecek
            </label>
          ))}
        </div>
      )}

      {participants.data && participants.data.warnings.length > 0 && (
        <ul role="alert" className="flex flex-col gap-0.5 text-body-small text-error">
          {participants.data.warnings.map((w) => (
            <WarningItem key={w} text={w} />
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
            getSublabel={(c) => `Sınıf düzeyleri: ${c.level_labels.join(", ")}`}
          />
          {course && (
            <Select
              label="Sınıf düzeyi"
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
              helperText="Ders adı aynı olsa da her sınıf düzeyinin soruları ayrıdır; her düzey ayrı satır olarak eklenir."
            />
          )}
          {courseAlreadyInSession && (
            <p className="text-body-small text-on-surface-variant">
              Bu ders oturumda başka bir sınıf düzeyinde zaten var. Her düzey ayrı soru dosyası
              alır; hepsi aynı kitapçığı çözecekse ekledikten sonra listenin altındaki kutuyu
              işaretleyin.
            </p>
          )}
          <Select
            label="Katılımcılar"
            options={(Object.keys(PARTICIPANT_TYPE_TR) as ParticipantTypeCode[]).map((value) => ({
              value,
              label: PARTICIPANT_TYPE_TR[value],
            }))}
            value={ptype}
            onChange={(e) => setPtype(e.target.value as ParticipantTypeCode)}
          />
          {ptype === "SECTIONS" && (
            <fieldset>
              <legend className="mb-1 text-label-large text-on-surface-variant">
                Şubeler{level !== "" && ` (${gradeLevelLabel(Number(level))})`}
              </legend>
              {(sectionGroups.data ?? []).length > 0 && (
                <div className="mb-2 flex flex-wrap items-center gap-2">
                  <span className="text-body-small text-on-surface-variant">
                    Şube kümesinden ekle:
                  </span>
                  {(sectionGroups.data ?? []).map((g) => (
                    <button
                      key={g.id}
                      type="button"
                      onClick={() => applyGroup(g.id)}
                      className="min-h-8 rounded-full bg-secondary-container px-3 text-label-medium text-on-secondary-container hover:bg-secondary-container/80 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary"
                    >
                      {g.name}
                    </button>
                  ))}
                </div>
              )}
              {/* Dar pencerede üç sütun şube etiketini sıkıştırıyordu → 2, sm'den itibaren 3. */}
              <div className="grid max-h-48 grid-cols-2 gap-1 overflow-y-auto sm:grid-cols-3">
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
        </div>
      </Dialog>

      {copyOpen ? (
        <OturumKopyalaDialog
          sessionId={session.id}
          onClose={closeCopy}
          onCopied={() => {
            onChanged();
            void qc.invalidateQueries({ queryKey: ["exam-participants", session.id] });
          }}
        />
      ) : null}
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
  // Salon kümeleri (Sabah/Öğle) — ikili eğitimde salon listesi kalabalıklaşır.
  const roomGroups = useQuery({
    queryKey: ["exam-room-groups"],
    queryFn: () => examRoomGroupApi.list(),
  });
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
      {(roomGroups.data?.results ?? []).length > 0 && (
        <div className="flex flex-wrap items-center gap-2">
          <span className="text-body-small text-on-surface-variant">Salon kümesinden ekle:</span>
          {(roomGroups.data?.results ?? []).map((g) => (
            <button
              key={g.id}
              type="button"
              onClick={() =>
                // Pasif salon `set_session_rooms`'ta 400 verir → aktif listeyle kesiştir.
                setSelected((prev) => [
                  ...new Set([
                    ...prev,
                    ...roomList.filter((r) => r.group_id === g.id).map((r) => r.id),
                  ]),
                ])
              }
              className="min-h-8 rounded-full bg-secondary-container px-3 text-label-medium text-on-secondary-container hover:bg-secondary-container/80 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary"
            >
              {g.name} ({roomList.filter((r) => r.group_id === g.id).length})
            </button>
          ))}
        </div>
      )}
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
// Adım 4 — Dağıt
// ---------------------------------------------------------------------------
function DistributeStep({
  session,
  onChanged,
  onBack,
  onDistributed,
}: SihirbazProps & { onBack: () => void; onDistributed: () => void }) {
  const snackbar = useSnackbar();
  const [options, setOptions] = useState(BOS_DAGITIM_SECENEKLERI);
  // Uyarılı sonuç: sekmeli görünüme geçmeden ÖNCE gösterilir. Eskiden `warnings`
  // hiç okunmuyordu — uygulanamayan bir yerleştirme kuralı sessizce geçiyordu.
  const [warned, setWarned] = useState<DistributeResult | null>(null);

  // Uyarılar okunurken oturum sorgusu BİLEREK tazelenmez (tazelenirse durum
  // DAĞITILDI'ya döner ve sihirbaz, uyarılarıyla birlikte ekrandan kalkar).
  // Kullanıcı düğmeye basmadan sayfadan ayrılırsa tazeleme sökülürken yapılır —
  // aksi hâlde liste 30 sn boyunca oturumu hâlâ "Taslak" gösterirdi.
  const refreshPending = useRef(false);
  const onChangedRef = useRef(onChanged);
  useEffect(() => {
    onChangedRef.current = onChanged;
  });
  useEffect(
    () => () => {
      if (refreshPending.current) onChangedRef.current();
    },
    [],
  );

  // "Kendi dersliğinde" düzeninde karıştırma YOKTUR (engine.distribute_home_classroom:
  // şube kendi dersliğine, okul no sırasıyla) — dağıtım numarası ve katı dağıtım
  // sonucu değiştirmez; o düzende sorulmaz/gösterilmez, açıklama da ona göre yazılır.
  const numarali = usesDistributionNumber(session.layout_mode);

  const distribute = useMutation({
    mutationFn: () => examSessionApi.distribute(session.id, dagitimGovdesi(options)),
    onSuccess: (result) => {
      snackbar.success(dagitimCumlesi("Dağıtım tamamlandı", result, numarali));
      if (result.warnings.length > 0) {
        refreshPending.current = true;
        setWarned(result);
        onDistributed();
        return;
      }
      onChanged(); // durum DISTRIBUTED → detay sekmeli görünüme geçer
    },
    onError: (e) => snackbar.error(e instanceof ApiError ? e.message : "Dağıtım başarısız."),
  });

  if (warned) {
    return (
      <Card elevation={1} className="flex flex-col gap-4 p-5">
        <h3 className="text-title-medium text-on-surface">Dağıtım tamamlandı</h3>
        <DagitimSonucu result={warned} numarali={numarali} />
        <div className="flex justify-end">
          <Button
            icon="grid_on"
            onClick={() => {
              refreshPending.current = false;
              onChanged();
            }}
          >
            Yerleşimi görüntüle
          </Button>
        </div>
      </Card>
    );
  }

  return (
    <Card elevation={1} className="flex flex-col gap-4 p-5">
      <h3 className="text-title-medium text-on-surface">Dağıt</h3>
      {!numarali ? (
        <p className="text-body-medium text-on-surface-variant">
          Her şube kendi şube dersliğine, okul numarası sırasıyla yerleştirilir. Bu düzende
          öğrenciler karıştırılmaz; yerleştirme kuralları da uygulanmaz. Yerleşimi dağıtımdan sonra
          Yerleşim sekmesinde incelersiniz.
        </p>
      ) : (
        <>
          <p className="text-body-medium text-on-surface-variant">
            Aynı kitapçığı çözen öğrenciler yan yana oturtulmaz ve salonda birbirinden olabildiğince
            uzağa yerleştirilir; sonuç ayrıca kural denetiminden geçer. Yerleşimi dağıtımdan sonra
            Yerleşim sekmesinde inceler, gerekirse yeniden dağıtırsınız.
          </p>
          <DagitimSecenekleri
            deger={options}
            onChange={setOptions}
            seedLabel="Dağıtım numarası (boş bırakılırsa rastgele)"
          />
        </>
      )}
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
