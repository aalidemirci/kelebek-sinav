// Kurulum sihirbazı (DD kalıbından KS'ye) — programın İLK AÇILIŞ ekranı. Üç
// adımda kurumu çalışır hale getirir: okul kimliği (evrak anteti + okul türü,
// U4: ders havuzu ve seviye kümesi türe bağlıdır) → ders yılı + dönemler (şube
// kataloğu ve sınav takvimi buna bağlanır) → kişi sicili yönlendirmesi.
// DD'deki tatil adımı YOK: kelebek iş günü hesabı yapmaz (tasarım §11 ALMA).
//
// Durum tek kaynaktan (`GET /setup/status/`) beslenir: sihirbaz yeniden
// açıldığında tamamlanmış adımlar işaretli gelir ve ilk EKSİK adımdan başlar.
// Adımlar arası geri/ileri serbesttir; yalnız "aktif ders yılı" kapısı zorunludur.

import { useCallback, useEffect, useMemo, useState } from "react";
import type { ReactNode } from "react";
import { useLocation, useNavigate } from "react-router-dom";

import type { KapiYonlendirmesi } from "../../KurulumKapisi";
import { useFormErrors } from "../../hooks/useFormErrors";
import { ApiError } from "../../lib/api";
import { formatDate, formatNumber } from "../../lib/format";
import Button from "../../ui/Button";
import Card from "../../ui/Card";
import Icon from "../../ui/Icon";
import Select from "../../ui/Select";
import { SkeletonList } from "../../ui/Skeleton";
import { useSnackbar } from "../../ui/SnackbarProvider";
import Stepper from "../../ui/Stepper";
import type { StepperItem } from "../../ui/Stepper";
import TextField from "../../ui/TextField";
import CizelgeAtamaMatrisi from "../okul/CizelgeAtamaMatrisi";
import {
  MAKS_GUNLUK_DERS_SAATI,
  MESLEKI_TURLER,
  VARSAYILAN_GUNLUK_DERS_SAATI,
  okulApi,
  okulTuruSecenekleri,
} from "../okul/api";
import type {
  LevelPrograms,
  SchoolType,
  SchoolTypeOption,
  SchoolYear,
  SetupStatus,
} from "../okul/api";

const ADIMLAR = [
  { key: "okul", label: "Okul bilgileri", icon: "school" },
  { key: "yil", label: "Ders yılı", icon: "calendar_month" },
  { key: "kisiler", label: "Kişiler", icon: "group" },
] as const;

const SON_ADIM = ADIMLAR.length - 1;

/** Hata mesajını Türkçeleştirir: ApiError gövdesi varsa onu, yoksa yedek metni verir. */
function hataMesaji(err: unknown, yedek: string): string {
  return err instanceof ApiError ? err.message : yedek;
}

/** Kalıcı hata bandı (snackbar geçici bildirim içindir — kalıcı durum inline gösterilir). */
function HataBandi({ mesaj }: { mesaj: string }) {
  return (
    <div
      role="alert"
      className="flex items-start gap-2 rounded-shape-sm bg-error-container px-4 py-3 text-body-medium text-on-error-container"
    >
      <Icon name="error" size="lg" />
      <span>{mesaj}</span>
    </div>
  );
}

/** Bilgilendirme bandı (uyarı/ipucu) — tonal yüzey, ham renk yok. */
function BilgiBandi({ ikon, children }: { ikon: string; children: ReactNode }) {
  return (
    <div className="flex items-start gap-2 rounded-shape-sm bg-tertiary-container px-4 py-3 text-body-medium text-on-tertiary-container">
      <Icon name={ikon} size="lg" />
      <span>{children}</span>
    </div>
  );
}

/** Sihirbaz yeniden açıldığında ilk EKSİK adıma konumlanır (hepsi tamsa başa döner). */
function ilkEksikAdim(s: SetupStatus): number {
  if (!s.school_name.trim()) return 0;
  if (!s.has_active_school_year) return 1;
  return SON_ADIM;
}

export default function KurulumPage() {
  const navigate = useNavigate();
  const snackbar = useSnackbar();
  // Kapı yönlendirmesiyle mi gelindi? (KurulumKapisi gezinme durumunda taşır.)
  const kapidanGelenYol =
    (useLocation().state as KapiYonlendirmesi | null)?.kapiYonlendirdi ?? null;

  const [status, setStatus] = useState<SetupStatus | null>(null);
  const [adim, setAdim] = useState(0);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState<string | null>(null);

  // 1. adımın form değerleri sihirbaz kabuğunda tutulur: "Kaydet ve devam"
  // düğmesi gezinme satırında olduğundan değerlere burada erişilmesi gerekir.
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

  const [busy, setBusy] = useState(false);
  const [adimHatasi, setAdimHatasi] = useState<string | null>(null);
  const { errors, applyApiError, clearErrors, setFieldError } = useFormErrors<string>();

  /** Durum özetini tazeler (adım rozetleri + sayımlar bundan okur). */
  const durumTazele = useCallback(async () => {
    try {
      setStatus(await okulApi.getSetupStatus());
    } catch {
      /* durum tazelemesi başarısız olsa da asıl işlem tamamlanmıştır */
    }
  }, []);

  useEffect(() => {
    let iptal = false;
    Promise.all([okulApi.getSetupStatus(), okulApi.getSchoolConfig()])
      .then(([s, c]) => {
        if (iptal) return;
        setStatus(s);
        setOkulAdi(c.school_name);
        setIl(c.province);
        setIlce(c.district);
        setMudur(c.principal_name);
        setOkulTuru(c.school_type);
        setHazirlikVar(c.has_prep_class);
        setLevelPrograms(c.level_programs ?? {});
        setGunlukDersSaati(c.daily_period_count || VARSAYILAN_GUNLUK_DERS_SAATI);
        setSinavSaatleri(c.exam_period_nos ?? []);
        setAdim(ilkEksikAdim(s));
        setLoadError(null);
      })
      .catch((e: unknown) => {
        if (!iptal) setLoadError(hataMesaji(e, "Kurulum durumu yüklenemedi."));
      })
      .finally(() => {
        if (!iptal) setLoading(false);
      });
    // Okul türü listesi ayrı yüklenir: gelmezse sabit sözlükten düşülür.
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

  // Adım rozetleri: her adımın "tamam" ölçütü backend durumundan türetilir.
  const tamam = useMemo(
    () => [
      (status?.school_name ?? "").trim().length > 0,
      status?.has_active_school_year ?? false,
      status?.setup_completed ?? false,
    ],
    [status],
  );

  const stepperItems: StepperItem[] = ADIMLAR.map((a, i) => ({
    key: a.key,
    label: a.label,
    icon: a.icon,
    status: i === adim ? "current" : tamam[i] ? "done" : "upcoming",
  }));

  const aktifYilVar = status?.has_active_school_year ?? false;
  // Tek zorunlu kapı: aktif ders yılı olmadan şube kataloğu ve sınav takvimi çalışmaz.
  const ileriKapisiKapali = adim === 1 && !aktifYilVar;

  const okulBilgileriniKaydet = async () => {
    if (!okulAdi.trim()) {
      setFieldError("school_name", "Okul adı zorunludur.");
      return;
    }
    setBusy(true);
    setAdimHatasi(null);
    clearErrors();
    try {
      await okulApi.updateSchoolConfig({
        school_name: okulAdi.trim(),
        province: il.trim(),
        district: ilce.trim(),
        principal_name: mudur.trim(),
        school_type: okulTuru,
        daily_period_count: gunlukDersSaati,
        // Gün kısaldıysa taşan saat gönderilmez (backend açık listeyi kırpmaz, reddeder).
        exam_period_nos: sinavSaatleri.filter((no) => no <= gunlukDersSaati),
        has_prep_class: hazirlikVar,
        level_programs: levelPrograms,
      });
      snackbar.success("Okul bilgileri kaydedildi.");
      await durumTazele();
      setAdim(1);
    } catch (e) {
      applyApiError(e);
      setAdimHatasi(hataMesaji(e, "Okul bilgileri kaydedilemedi."));
    } finally {
      setBusy(false);
    }
  };

  const ileri = () => {
    setAdimHatasi(null);
    if (adim === 0) {
      void okulBilgileriniKaydet();
      return;
    }
    setAdim((s) => Math.min(s + 1, SON_ADIM));
  };

  const geri = () => {
    setAdimHatasi(null);
    setAdim((s) => Math.max(s - 1, 0));
  };

  const kurulumuTamamla = async () => {
    setBusy(true);
    setAdimHatasi(null);
    try {
      await okulApi.completeSetup();
      snackbar.success("Kurulum tamamlandı.");
      navigate("/");
    } catch (e) {
      setAdimHatasi(hataMesaji(e, "Kurulum tamamlanamadı."));
      setBusy(false);
    }
  };

  return (
    <div className="mx-auto max-w-4xl space-y-6">
      <div className="ks-page-header">
        <div>
          <h1 className="ks-page-title">Kurulum sihirbazı</h1>
          <p className="ks-page-description">
            Programı kullanmaya başlamadan önce üç adımı tamamlayın. Girdiğiniz her bilgiyi daha
            sonra Ayarlar ekranından değiştirebilirsiniz.
          </p>
        </div>
      </div>

      {kapidanGelenYol !== null && (
        <BilgiBandi ikon="lock">
          Kurulum tamamlanmadan diğer ekranlar açılmaz; bu yüzden buraya getirildiniz. Aşağıdaki
          adımları bitirip &quot;Kurulumu tamamla&quot; dediğinizde menüdeki tüm bölümler açılır.
        </BilgiBandi>
      )}

      {status?.setup_completed && (
        <div className="flex items-start gap-2 rounded-shape-sm bg-secondary-container px-4 py-3 text-body-medium text-on-secondary-container">
          <Icon name="check_circle" size="lg" />
          <span>
            Kurulum daha önce tamamlanmıştı. Bilgileri buradan gözden geçirip güncelleyebilirsiniz.
          </span>
        </div>
      )}

      <Stepper items={stepperItems} ariaLabel="Kurulum adımları" />

      {loadError && <HataBandi mesaj={loadError} />}

      {loading ? (
        <SkeletonList rows={5} />
      ) : (
        !loadError && (
          <>
            {adim === 0 && (
              <OkulBilgileriAdimi
                okulAdi={okulAdi}
                il={il}
                ilce={ilce}
                mudur={mudur}
                okulTuru={okulTuru}
                hazirlikVar={hazirlikVar}
                levelPrograms={levelPrograms}
                okulTurleri={okulTurleri}
                errors={errors}
                onOkulAdi={setOkulAdi}
                onIl={setIl}
                onIlce={setIlce}
                onMudur={setMudur}
                onOkulTuru={setOkulTuru}
                onHazirlikVar={setHazirlikVar}
                onLevelPrograms={setLevelPrograms}
                gunlukDersSaati={gunlukDersSaati}
                sinavSaatleri={sinavSaatleri}
                onGunlukDersSaati={setGunlukDersSaati}
                onSinavSaatleri={setSinavSaatleri}
              />
            )}
            {adim === 1 && <DersYiliAdimi onChanged={durumTazele} />}
            {adim === 2 && <KisilerAdimi status={status} />}

            {adimHatasi && <HataBandi mesaj={adimHatasi} />}

            <div className="flex flex-wrap items-center justify-between gap-3">
              <Button variant="text" icon="arrow_back" onClick={geri} disabled={adim === 0 || busy}>
                Geri
              </Button>
              <div className="flex flex-wrap items-center justify-end gap-3">
                {ileriKapisiKapali && (
                  <p className="text-body-small text-on-surface-variant">
                    Devam etmek için bir ders yılını aktifleştirin.
                  </p>
                )}
                {adim < SON_ADIM ? (
                  <Button
                    icon="arrow_forward"
                    onClick={ileri}
                    disabled={busy || ileriKapisiKapali || (adim === 0 && !okulAdi.trim())}
                  >
                    {adim === 0 ? (busy ? "Kaydediliyor…" : "Kaydet ve devam") : "İleri"}
                  </Button>
                ) : (
                  <Button icon="check_circle" onClick={kurulumuTamamla} disabled={busy}>
                    {busy ? "Tamamlanıyor…" : "Kurulumu tamamla"}
                  </Button>
                )}
              </div>
            </div>
          </>
        )
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// 1. adım — Okul bilgileri (evrak anteti + okul türü)
// ---------------------------------------------------------------------------

interface OkulBilgileriProps {
  okulAdi: string;
  il: string;
  ilce: string;
  mudur: string;
  okulTuru: SchoolType;
  hazirlikVar: boolean;
  levelPrograms: LevelPrograms;
  gunlukDersSaati: number;
  sinavSaatleri: number[];
  okulTurleri: SchoolTypeOption[];
  errors: Partial<Record<string, string>>;
  onOkulAdi: (v: string) => void;
  onIl: (v: string) => void;
  onIlce: (v: string) => void;
  onMudur: (v: string) => void;
  onOkulTuru: (v: SchoolType) => void;
  onHazirlikVar: (v: boolean) => void;
  onLevelPrograms: (v: LevelPrograms) => void;
  onGunlukDersSaati: (v: number) => void;
  onSinavSaatleri: (v: number[]) => void;
}

function OkulBilgileriAdimi({
  okulAdi,
  il,
  ilce,
  mudur,
  okulTuru,
  hazirlikVar,
  levelPrograms,
  okulTurleri,
  errors,
  onOkulAdi,
  onIl,
  onIlce,
  onMudur,
  onOkulTuru,
  onHazirlikVar,
  onLevelPrograms,
  gunlukDersSaati,
  sinavSaatleri,
  onGunlukDersSaati,
  onSinavSaatleri,
}: OkulBilgileriProps) {
  return (
    <Card elevation={1} className="p-6">
      <p className="text-title-medium text-on-surface">1. Okul bilgileri</p>
      <p className="mt-1 text-body-medium text-on-surface-variant">
        Bu bilgiler salon evrakının antetinde kullanılır. Okul türü ve hazırlık sınıfı, ders
        havuzunun hangi MEB çizelgesinden türetileceğini ve geçerli sınıf seviyelerini belirler.
      </p>
      <div className="mt-4 grid grid-cols-1 gap-4 sm:grid-cols-2">
        <TextField
          className="sm:col-span-2"
          label="Okul adı"
          required
          value={okulAdi}
          onChange={(e) => onOkulAdi(e.target.value)}
          error={errors.school_name}
          placeholder="Örn. Örnek Anadolu Lisesi"
          helperText="Evrak antedinin ilk satırı."
        />
        <TextField
          label="İl"
          value={il}
          onChange={(e) => onIl(e.target.value)}
          error={errors.province}
        />
        <TextField
          label="İlçe"
          value={ilce}
          onChange={(e) => onIlce(e.target.value)}
          error={errors.district}
        />
        <TextField
          className="sm:col-span-2"
          label="Okul müdürü"
          value={mudur}
          onChange={(e) => onMudur(e.target.value)}
          error={errors.principal_name}
          helperText="Evrak imza bloğunda görünür; boş bırakılırsa şablon yer tutucu basar."
        />
        <Select
          label="Okul türü"
          value={okulTuru}
          onChange={(e) => onOkulTuru(e.target.value as SchoolType)}
          options={okulTuruSecenekleri(okulTurleri)}
          helperText="Ders havuzu bu türün TTK haftalık ders çizelgesinden türetilir."
        />
        <Select
          label="Hazırlık sınıfı"
          value={hazirlikVar ? "1" : "0"}
          onChange={(e) => onHazirlikVar(e.target.value === "1")}
          options={[
            { value: "0", label: "Yok" },
            { value: "1", label: "Var" },
          ]}
          helperText="Varsa 'Hazırlık Sınıfı Bulunan …' çizelgesi uygulanır ve seviyelere Hazırlık eklenir."
        />
        <Select
          label="Günlük ders saati sayısı"
          value={String(gunlukDersSaati)}
          onChange={(e) => onGunlukDersSaati(Number(e.target.value))}
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
              Sınav takvimini otomatik kurarken program yalnız işaretli saatleri kullanır. Boş
              bırakılırsa tüm saatler sınava açıktır; sonradan Ayarlar → Okul Bilgileri'nden
              değiştirilebilir.
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
                      onSinavSaatleri(
                        sinavSaatleri.includes(no)
                          ? sinavSaatleri.filter((x) => x !== no)
                          : [...sinavSaatleri, no].sort((a, b) => a - b),
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
            onChange={onLevelPrograms}
          />
        </div>
      </div>
    </Card>
  );
}

// ---------------------------------------------------------------------------
// 2. adım — Ders yılı + dönemler (şube kataloğu ve sınav takvimi buna bağlı)
// ---------------------------------------------------------------------------

/** Bugüne göre makul ders yılı önerisi: eylül ve sonrası yeni yılı başlatır. */
function varsayilanDersYili(): {
  ad: string;
  baslangic: string;
  bitis: string;
  birinciDonemBitis: string;
  ikinciDonemBaslangic: string;
} {
  const bugun = new Date();
  const yil = bugun.getMonth() >= 8 ? bugun.getFullYear() : bugun.getFullYear() - 1;
  return {
    ad: `${yil}-${yil + 1}`,
    baslangic: `${yil}-09-01`,
    bitis: `${yil + 1}-06-30`,
    birinciDonemBitis: `${yil + 1}-01-16`,
    ikinciDonemBaslangic: `${yil + 1}-02-02`,
  };
}

function DersYiliAdimi({ onChanged }: { onChanged: () => Promise<void> }) {
  const varsayilan = useMemo(varsayilanDersYili, []);
  const [yillar, setYillar] = useState<SchoolYear[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [ad, setAd] = useState(varsayilan.ad);
  const [baslangic, setBaslangic] = useState(varsayilan.baslangic);
  const [bitis, setBitis] = useState(varsayilan.bitis);
  const [birinciDonemBitis, setBirinciDonemBitis] = useState(varsayilan.birinciDonemBitis);
  const [ikinciDonemBaslangic, setIkinciDonemBaslangic] = useState(varsayilan.ikinciDonemBaslangic);
  const { errors, applyApiError, clearErrors } = useFormErrors<string>();
  const snackbar = useSnackbar();

  const yukle = useCallback(() => {
    setLoading(true);
    okulApi
      .listSchoolYears()
      .then((r) => {
        setYillar(r);
        setError(null);
      })
      .catch((e: unknown) => setError(hataMesaji(e, "Ders yılları yüklenemedi.")))
      .finally(() => setLoading(false));
  }, []);
  useEffect(yukle, [yukle]);

  const olustur = async () => {
    setBusy(true);
    setError(null);
    clearErrors();
    try {
      // Sihirbazda oluşturulan yıl doğrudan aktifleştirilir (kurulum kapısı budur).
      const olusan = await okulApi.createSchoolYear({
        name: ad.trim(),
        start_date: baslangic,
        end_date: bitis,
      });
      await okulApi.configureSchoolTerms(olusan.id, {
        first_term_end: birinciDonemBitis,
        second_term_start: ikinciDonemBaslangic,
      });
      await okulApi.activateSchoolYear(olusan.id);
      snackbar.success("Ders yılı oluşturuldu ve aktifleştirildi.");
      yukle();
      await onChanged();
    } catch (e) {
      applyApiError(e);
      setError(hataMesaji(e, "Ders yılı oluşturulamadı."));
    } finally {
      setBusy(false);
    }
  };

  const aktiflestir = async (yil: SchoolYear) => {
    setBusy(true);
    setError(null);
    try {
      await okulApi.activateSchoolYear(yil.id);
      snackbar.success(`${yil.name} ders yılı aktifleştirildi.`);
      yukle();
      await onChanged();
    } catch (e) {
      setError(hataMesaji(e, "Ders yılı aktifleştirilemedi."));
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="space-y-4">
      <Card elevation={1} className="p-6">
        <p className="text-title-medium text-on-surface">2. Ders yılı</p>
        <p className="mt-1 text-body-medium text-on-surface-variant">
          Şube kataloğu, sınav oturumları ve sınav takvimi AKTİF ders yılına bağlanır. Aynı anda
          yalnız bir yıl aktif olabilir.
        </p>

        {loading ? (
          <SkeletonList rows={3} className="mt-4" />
        ) : yillar.length === 0 ? (
          <p className="mt-4 text-body-medium text-on-surface-variant">
            Henüz ders yılı tanımlanmamış. Aşağıdaki formla ilk yılı oluşturun.
          </p>
        ) : (
          <ul className="mt-4 divide-y divide-outline-variant/50">
            {yillar.map((y) => (
              <li key={y.id} className="flex flex-wrap items-center justify-between gap-3 py-3">
                <div className="min-w-0">
                  <p className="flex items-center gap-2 text-body-medium text-on-surface">
                    {y.name}
                    {y.is_active && (
                      <span className="inline-flex items-center rounded-shape-xl bg-primary-container px-2 py-0.5 text-label-small text-on-primary-container">
                        Aktif
                      </span>
                    )}
                  </p>
                  <p className="text-label-small text-on-surface-variant">
                    {formatDate(y.start_date)} – {formatDate(y.end_date)}
                  </p>
                </div>
                {!y.is_active && (
                  <Button
                    variant="text"
                    icon="check"
                    onClick={() => void aktiflestir(y)}
                    disabled={busy}
                  >
                    Aktifleştir
                  </Button>
                )}
              </li>
            ))}
          </ul>
        )}
      </Card>

      <Card elevation={1} className="p-6">
        <p className="text-title-medium text-on-surface">Yeni ders yılı</p>
        <div className="mt-4 grid grid-cols-1 gap-4 sm:grid-cols-3">
          <TextField
            label="Ad"
            required
            value={ad}
            onChange={(e) => setAd(e.target.value)}
            error={errors.name}
            helperText="Örn. 2026-2027"
          />
          <TextField
            label="Başlangıç"
            type="date"
            required
            value={baslangic}
            onChange={(e) => {
              const value = e.target.value;
              setBaslangic(value);
              const year = Number(value.slice(0, 4));
              if (Number.isFinite(year)) {
                setBirinciDonemBitis(`${year + 1}-01-16`);
                setIkinciDonemBaslangic(`${year + 1}-02-02`);
              }
            }}
            error={errors.start_date}
          />
          <TextField
            label="Bitiş"
            type="date"
            required
            value={bitis}
            onChange={(e) => setBitis(e.target.value)}
            error={errors.end_date}
          />
        </div>
        <div className="mt-4 grid grid-cols-1 gap-4 sm:grid-cols-2">
          <TextField
            label="1. dönem bitişi"
            type="date"
            required
            value={birinciDonemBitis}
            onChange={(e) => setBirinciDonemBitis(e.target.value)}
            error={errors.first_term_end}
          />
          <TextField
            label="2. dönem başlangıcı"
            type="date"
            required
            value={ikinciDonemBaslangic}
            onChange={(e) => setIkinciDonemBaslangic(e.target.value)}
            error={errors.second_term_start}
          />
        </div>
        <p className="mt-2 text-label-small text-on-surface-variant">
          Yarıyıl tatili iki tarih arasında kalır. Sınav takviminin mevzuat pencereleri (F6) dönem
          sınırlarına göre hesaplanır.
        </p>
        {error && (
          <div className="mt-4">
            <HataBandi mesaj={error} />
          </div>
        )}
        <div className="mt-4 flex justify-end">
          <Button
            icon="calendar_add_on"
            onClick={() => void olustur()}
            disabled={
              busy ||
              !ad.trim() ||
              !baslangic ||
              !bitis ||
              !birinciDonemBitis ||
              !ikinciDonemBaslangic
            }
          >
            {busy ? "Kaydediliyor…" : "Ders yılını kaydet ve aktifleştir"}
          </Button>
        </div>
      </Card>
    </div>
  );
}

// ---------------------------------------------------------------------------
// 3. adım — Kişiler (öğrenci/öğretmen sicili Kişiler ekranından aktarılır)
// ---------------------------------------------------------------------------

function SayimKutusu({ ikon, etiket, deger }: { ikon: string; etiket: string; deger: number }) {
  return (
    <div className="flex items-center gap-3 rounded-shape-md bg-surface-container px-4 py-3">
      <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-shape-md bg-primary-container text-on-primary-container">
        <Icon name={ikon} />
      </span>
      <div>
        <p className="text-label-medium text-on-surface-variant">{etiket}</p>
        <p className="text-title-medium text-on-surface">{formatNumber(deger)}</p>
      </div>
    </div>
  );
}

function KisilerAdimi({ status }: { status: SetupStatus | null }) {
  return (
    <Card elevation={1} className="p-6">
      <p className="text-title-medium text-on-surface">3. Kişiler</p>
      <p className="mt-1 text-body-medium text-on-surface-variant">
        Öğrenci ve öğretmen listeleri, kurulum tamamlandıktan sonra{" "}
        <span className="text-on-surface">Kişiler</span> ekranından aktarılır: e-Okul listesinin
        Excel dosyasını seçin ya da tabloyu panodan yapıştırın. Önce ÖNİZLEME alınır — bu adım
        hiçbir kayıt yazmaz, yalnız uyarıları listeler; sonuç uygunsa AKTAR ile kaydedilir. Aktarım
        sonrası görülen şubeler kataloğa kendiliğinden eklenir.
      </p>

      <div className="mt-4 grid grid-cols-1 gap-3 sm:grid-cols-3">
        <SayimKutusu ikon="school" etiket="Öğrenci" deger={status?.student_count ?? 0} />
        <SayimKutusu ikon="badge" etiket="Öğretmen" deger={status?.personnel_count ?? 0} />
        <SayimKutusu ikon="meeting_room" etiket="Şube" deger={status?.class_section_count ?? 0} />
      </div>

      <p className="mt-4 text-body-medium text-on-surface-variant">
        Sicil boş olsa da kuruluma son verebilirsiniz; kişileri istediğiniz zaman aktarabilirsiniz.
        &quot;Kurulumu tamamla&quot; dedikten sonra program panelle açılır.
      </p>
    </Card>
  );
}
