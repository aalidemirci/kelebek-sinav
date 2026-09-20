// Ayarlar → Ders Saatleri. Zil çizelgesi buraya kadar hiçbir ekrandan
// düzenlenemiyordu: alan vardı ama serileştiricide yoktu, okul varsayılan
// çizelgeye (08:30'dan 50'şer dakika) mahkûmdu.
//
// İki katman: (1) DERS AKIŞI hesaplayıcısı — ilk ders, süre, teneffüs, uzun ara
// ve blok düzeninden saatleri backend hesaplar; (2) hesaplanan listeyi idareci
// satır satır ELLE düzeltebilir. Akış parametreleri ayrıca saklanır, çünkü elle
// düzeltme akıştan türetilemez ve hesaplayıcı bir daha açıldığında son
// girilenlerle dolmalıdır.
//
// Hesap ÖN YÜZDE DEĞİL: `previewBellSchedule` ucu çağrılır (salon editöründeki
// koltuk önizlemesiyle aynı desen — iş kuralı backend'de kalır).
//
// İkili eğitim: aynı ders saati sabah ve öğle grubunda farklı zamanda başlar,
// bu yüzden iki ayrı çizelge tutulur ve şubeler oturumlarına işaretlenir.
// Kalıp AyarlarPage'in hâkim kalıbıdır: react-query DEĞİL, useState + load().

import { useCallback, useEffect, useState } from "react";

import { ApiError } from "../../lib/api";
import Button from "../../ui/Button";
import Card from "../../ui/Card";
import Icon from "../../ui/Icon";
import Select from "../../ui/Select";
import { SkeletonList } from "../../ui/Skeleton";
import { useSnackbar } from "../../ui/SnackbarProvider";
import TextField from "../../ui/TextField";
import { SHIFT_LABELS, okulApi } from "../okul/api";
import type { BellPeriod, ClassSection, EducationModel, LessonFlowBody, Shift } from "../okul/api";

/** "2+2+2+2" → [2,2,2,2]; boş/bozuk giriş boş dizi (her ders tek blok). */
function blokCoz(metin: string): number[] {
  return metin
    .split(/[+,\s]+/)
    .map((p) => Number(p.trim()))
    .filter((n) => Number.isInteger(n) && n > 0);
}

function blokYaz(bloklar: number[] | undefined): string {
  return (bloklar ?? []).join("+");
}

type OturumKey = "morning" | "afternoon";

interface OturumDurumu {
  flow: LessonFlowBody;
  blokMetni: string;
  periods: BellPeriod[];
  bitis: string;
  oneri: string;
}

const BOS_OTURUM: OturumDurumu = {
  flow: {
    first_lesson: "08:30",
    lesson_count: 8,
    lesson_minutes: 40,
    break_minutes: 10,
    long_break_after: 0,
    long_break_minutes: 0,
  },
  blokMetni: "",
  periods: [],
  bitis: "",
  oneri: "",
};

export default function DersSaatleriPaneli() {
  const [egitimModeli, setEgitimModeli] = useState<EducationModel>("FULL_DAY");
  const [oturumlar, setOturumlar] = useState<Record<OturumKey, OturumDurumu>>({
    morning: BOS_OTURUM,
    afternoon: { ...BOS_OTURUM, flow: { ...BOS_OTURUM.flow, first_lesson: "13:00" } },
  });
  const [aktif, setAktif] = useState<OturumKey>("morning");
  const [subeler, setSubeler] = useState<ClassSection[]>([]);
  const [secili, setSecili] = useState<number[]>([]);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const snackbar = useSnackbar();

  const load = useCallback(() => {
    setLoading(true);
    Promise.all([okulApi.getSchoolConfig(), okulApi.listClassSections()])
      .then(([c, s]) => {
        setEgitimModeli(c.education_model ?? "FULL_DAY");
        setOturumlar({
          morning: {
            ...BOS_OTURUM,
            flow: { ...BOS_OTURUM.flow, ...(c.bell_flow ?? {}) },
            blokMetni: blokYaz(c.bell_flow?.block_sizes),
            periods: c.bell_schedule ?? [],
          },
          afternoon: {
            ...BOS_OTURUM,
            flow: {
              ...BOS_OTURUM.flow,
              first_lesson: "13:00",
              ...(c.afternoon_bell_flow ?? {}),
            },
            blokMetni: blokYaz(c.afternoon_bell_flow?.block_sizes),
            periods: c.afternoon_bell_schedule ?? [],
          },
        });
        setSubeler(s);
        setError(null);
      })
      .catch((e: unknown) =>
        setError(e instanceof ApiError ? e.message : "Ders saatleri yüklenemedi."),
      )
      .finally(() => setLoading(false));
  }, []);
  useEffect(load, [load]);

  const durum = oturumlar[aktif];
  const guncelle = (yama: Partial<OturumDurumu>) =>
    setOturumlar((prev) => ({ ...prev, [aktif]: { ...prev[aktif], ...yama } }));
  const akisAyarla = (yama: Partial<LessonFlowBody>) =>
    guncelle({ flow: { ...durum.flow, ...yama } });

  const hesapla = async () => {
    setBusy(true);
    try {
      const sonuc = await okulApi.previewBellSchedule({
        ...durum.flow,
        block_sizes: blokCoz(durum.blokMetni),
      });
      guncelle({ periods: sonuc.periods, bitis: sonuc.end_time, oneri: sonuc.next_start });
      snackbar.success(`Saatler hesaplandı; son ders ${sonuc.end_time}'te biter.`);
    } catch (e) {
      snackbar.error(e instanceof ApiError ? e.message : "Saatler hesaplanamadı.");
    } finally {
      setBusy(false);
    }
  };

  const sabahaGoreHesapla = async () => {
    setBusy(true);
    try {
      const sabah = await okulApi.previewBellSchedule({
        ...oturumlar.morning.flow,
        block_sizes: blokCoz(oturumlar.morning.blokMetni),
      });
      const ogle = await okulApi.previewBellSchedule({
        ...oturumlar.afternoon.flow,
        first_lesson: sabah.next_start,
        block_sizes: blokCoz(oturumlar.afternoon.blokMetni),
      });
      setOturumlar((prev) => ({
        ...prev,
        afternoon: {
          ...prev.afternoon,
          flow: { ...prev.afternoon.flow, first_lesson: sabah.next_start },
          periods: ogle.periods,
          bitis: ogle.end_time,
          oneri: "",
        },
      }));
      snackbar.success(`Öğleden sonra oturumu ${sabah.next_start}'te başlayacak şekilde kuruldu.`);
    } catch (e) {
      snackbar.error(e instanceof ApiError ? e.message : "Öğle oturumu hesaplanamadı.");
    } finally {
      setBusy(false);
    }
  };

  const saatDegistir = (no: number, saat: string) =>
    guncelle({
      periods: durum.periods.map((p) => (p.no === no ? { ...p, start: saat } : p)),
    });

  const kaydet = async () => {
    setBusy(true);
    try {
      await okulApi.updateSchoolConfig({
        education_model: egitimModeli,
        bell_schedule: oturumlar.morning.periods,
        bell_flow: {
          ...oturumlar.morning.flow,
          block_sizes: blokCoz(oturumlar.morning.blokMetni),
        },
        afternoon_bell_schedule: egitimModeli === "DUAL" ? oturumlar.afternoon.periods : [],
        afternoon_bell_flow: {
          ...oturumlar.afternoon.flow,
          block_sizes: blokCoz(oturumlar.afternoon.blokMetni),
        },
      });
      snackbar.success("Ders saatleri kaydedildi.");
      load();
    } catch (e) {
      snackbar.error(e instanceof ApiError ? e.message : "Ders saatleri kaydedilemedi.");
    } finally {
      setBusy(false);
    }
  };

  const vardiyaAta = async (shift: Shift) => {
    if (secili.length === 0) return;
    setBusy(true);
    try {
      const { updated } = await okulApi.assignClassSectionShift({ section_ids: secili, shift });
      snackbar.success(`${updated} şube güncellendi.`);
      setSecili([]);
      load();
    } catch (e) {
      snackbar.error(e instanceof ApiError ? e.message : "Şubeler güncellenemedi.");
    } finally {
      setBusy(false);
    }
  };

  if (loading) return <SkeletonList rows={5} />;

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
        <p className="text-title-medium text-on-surface">Ders saatleri</p>
        <p className="mt-1 text-body-medium text-on-surface-variant">
          Sınav takvimi ve slottan üretilen oturumlar saatlerini buradan alır. Önce ders akışını
          girip hesaplatın, gerekirse tek tek düzeltin. Saat alanını boş bırakırsanız o ders saati
          için evrakta yalnız adı basılır.
        </p>

        <div className="mt-4 max-w-xs">
          <Select
            label="Eğitim modeli"
            value={egitimModeli}
            onChange={(e) => setEgitimModeli(e.target.value as EducationModel)}
            options={[
              { value: "FULL_DAY", label: "Tam gün" },
              { value: "DUAL", label: "İkili eğitim" },
            ]}
          />
        </div>
        {egitimModeli === "DUAL" && (
          <p className="mt-2 text-body-small text-on-surface-variant">
            İkili eğitimde aynı ders saati iki farklı zamana denk gelir; evrakta saat, sınava giren
            şubenin oturumuna göre basılır. Şubeleri aşağıdan işaretleyin.
          </p>
        )}

        {egitimModeli === "DUAL" && (
          <div className="mt-4 flex gap-2">
            {(["morning", "afternoon"] as const).map((key) => (
              <Button
                key={key}
                variant={aktif === key ? "filled" : "outlined"}
                onClick={() => setAktif(key)}
              >
                {key === "morning" ? "Sabah" : "Öğleden sonra"}
              </Button>
            ))}
          </div>
        )}

        <div className="mt-4 grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
          <TextField
            label="İlk ders saati"
            value={durum.flow.first_lesson ?? ""}
            onChange={(e) => akisAyarla({ first_lesson: e.target.value })}
            placeholder="08:30"
          />
          <TextField
            label="Ders sayısı"
            type="number"
            value={String(durum.flow.lesson_count ?? 8)}
            onChange={(e) => akisAyarla({ lesson_count: Number(e.target.value) })}
          />
          <TextField
            label="Ders süresi (dakika)"
            type="number"
            value={String(durum.flow.lesson_minutes ?? 40)}
            onChange={(e) => akisAyarla({ lesson_minutes: Number(e.target.value) })}
          />
          <TextField
            label="Teneffüs (dakika)"
            type="number"
            value={String(durum.flow.break_minutes ?? 10)}
            onChange={(e) => akisAyarla({ break_minutes: Number(e.target.value) })}
          />
          <TextField
            label="Uzun ara kaçıncı dersten sonra (0 = yok)"
            type="number"
            value={String(durum.flow.long_break_after ?? 0)}
            onChange={(e) => akisAyarla({ long_break_after: Number(e.target.value) })}
          />
          <TextField
            label="Uzun ara (dakika)"
            type="number"
            value={String(durum.flow.long_break_minutes ?? 0)}
            onChange={(e) => akisAyarla({ long_break_minutes: Number(e.target.value) })}
          />
          <TextField
            label="Blok düzeni (örn. 2+2+2+2)"
            value={durum.blokMetni}
            onChange={(e) => guncelle({ blokMetni: e.target.value })}
            placeholder="boş = her ders ayrı"
          />
        </div>

        <div className="mt-4 flex flex-wrap items-center gap-3">
          <Button onClick={hesapla} disabled={busy} icon="calculate">
            Saatleri hesapla
          </Button>
          {egitimModeli === "DUAL" && aktif === "afternoon" && (
            <Button variant="outlined" onClick={sabahaGoreHesapla} disabled={busy}>
              Sabaha göre hesapla
            </Button>
          )}
          {durum.bitis && (
            <span className="text-body-small text-on-surface-variant">
              Son ders {durum.bitis}&apos;te biter.
              {egitimModeli === "DUAL" && aktif === "morning" && durum.oneri
                ? ` Öğleden sonra için önerilen başlangıç: ${durum.oneri}.`
                : ""}
            </span>
          )}
        </div>

        {durum.periods.length > 0 && (
          <div className="mt-5">
            <p className="text-title-small text-on-surface">
              {egitimModeli === "DUAL"
                ? aktif === "morning"
                  ? "Sabah çizelgesi"
                  : "Öğleden sonra çizelgesi"
                : "Ders saati listesi"}
            </p>
            <div className="mt-2 grid gap-2 sm:grid-cols-2 lg:grid-cols-4">
              {durum.periods.map((p) => (
                <TextField
                  key={p.no}
                  label={p.name}
                  value={p.start}
                  onChange={(e) => saatDegistir(p.no, e.target.value)}
                  placeholder="SS:DD"
                />
              ))}
            </div>
          </div>
        )}

        <div className="mt-5">
          <Button onClick={kaydet} disabled={busy} icon="save">
            Kaydet
          </Button>
        </div>
      </Card>

      {egitimModeli === "DUAL" && (
        <Card elevation={1} className="p-6">
          <p className="text-title-medium text-on-surface">Şube oturumları</p>
          <p className="mt-1 text-body-medium text-on-surface-variant">
            Hangi şubenin sabah, hangisinin öğleden sonra okuduğunu işaretleyin. Sınav takvimi
            evrakında saat bu işarete göre basılır; işaretlenmeyen şube sabah sayılır.
          </p>
          <div className="mt-4 flex flex-wrap gap-2">
            {subeler.map((s) => (
              <label
                key={s.id}
                className="flex cursor-pointer items-center gap-2 rounded-shape-sm border border-outline-variant px-3 py-2 text-body-medium"
              >
                <input
                  type="checkbox"
                  checked={secili.includes(s.id)}
                  onChange={() =>
                    setSecili((prev) =>
                      prev.includes(s.id) ? prev.filter((x) => x !== s.id) : [...prev, s.id],
                    )
                  }
                />
                <span>{s.class_label}</span>
                <span className="text-body-small text-on-surface-variant">
                  {s.shift ? SHIFT_LABELS[s.shift] : "—"}
                </span>
              </label>
            ))}
          </div>
          <div className="mt-4 flex flex-wrap gap-2">
            <Button onClick={() => vardiyaAta("MORNING")} disabled={busy || secili.length === 0}>
              Sabah yap
            </Button>
            <Button onClick={() => vardiyaAta("AFTERNOON")} disabled={busy || secili.length === 0}>
              Öğleden sonra yap
            </Button>
            <Button
              variant="outlined"
              onClick={() => vardiyaAta("")}
              disabled={busy || secili.length === 0}
            >
              İşareti kaldır
            </Button>
          </div>
        </Card>
      )}
    </div>
  );
}
