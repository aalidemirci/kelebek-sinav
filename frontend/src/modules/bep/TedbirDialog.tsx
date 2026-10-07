// Kişiler → BEP ve tedbirler: öğrenci ekleme ve tedbir düzenleme penceresi (07.10.2026).
//
// Kullanıcı isteği: "okul numaralarını girerek hangi tedbirlerin uygulanacağını
// seçebilsek". Ekleme iki yoldan yapılır: ad/okul no ile tek öğrenci, ya da okul
// numaralarını yazıp (yapıştırıp) toplu — toplu eklemede hepsine AYNI tedbirler yazılır,
// farklılık sonra satırdan düzenlenir.
//
// Tedbirler üç ayaktır: YER (her oturumda yerleştirme kuralı olarak uygulanır; oturumda
// kural girilirse o geçerlidir), SÜRE ve DESTEK (yerleşimi değiştirmez; YALNIZ idare
// özetine basılır — kullanıcı kararı). Okuyucu/yazıcı görevlisini program atamaz.
//
// KVKK md. 6: gerekçe YALNIZ kategoridir; tanı, rapor, açıklama ya da serbest metin
// alanı BİLİNÇLE YOKTUR — bu pencereye öyle bir alan EKLEMEYİN. Bildirimlerde öğrenci
// adı geçmez.

import { useState } from "react";
import { useMutation, useQuery } from "@tanstack/react-query";

import { ApiError } from "../../lib/api";
import Autocomplete from "../../ui/Autocomplete";
import Button from "../../ui/Button";
import Dialog from "../../ui/Dialog";
import Select from "../../ui/Select";
import TextField from "../../ui/TextField";
import { useSnackbar } from "../../ui/SnackbarProvider";
import type { Student } from "../okul/api";
import { okulApi } from "../okul/api";
import type { RuleReason, SeatPreference } from "../oturumlar/api";
import { RULE_REASON_TR, SEAT_PREFERENCE_TR } from "../oturumlar/api";
import { examRoomApi } from "../salonlar/api";
import type { AccommodationBody, AccommodationPlacement, IepStudent } from "./api";
import { MAX_EXTRA_MINUTES, PLACEMENT_TR, iepApi } from "./api";

type Kip = "tek" | "toplu";

/** Gerekçe seçenekleri — BEP başta: liste en çok BEP kapsamındaki öğrenciler içindir. */
const GEREKCE_SIRASI: RuleReason[] = ["IEP", "DISABILITY", "HEALTH", "OTHER"];

function bos(): AccommodationBody {
  return {
    reason_category: "IEP",
    placement: "NONE",
    target_room_id: null,
    seat_preference: "NONE",
    solo_desk: false,
    extra_minutes: 0,
    reader: false,
    scribe: false,
  };
}

function satirdan(row: IepStudent): AccommodationBody {
  return {
    reason_category: row.reason_category,
    placement: row.placement,
    target_room_id: row.target_room_id,
    seat_preference: row.seat_preference,
    solo_desk: row.solo_desk,
    extra_minutes: row.extra_minutes,
    reader: row.reader,
    scribe: row.scribe,
  };
}

/** Yer değişince geçersizleşen alanları temizler (backend'in kuralının aynısı). */
function yerDegisti(body: AccommodationBody, placement: AccommodationPlacement): AccommodationBody {
  const salonIci = placement === "HOME_CLASSROOM" || placement === "SEPARATE_ROOM";
  return {
    ...body,
    placement,
    target_room_id: placement === "SEPARATE_ROOM" ? body.target_room_id : null,
    seat_preference: salonIci ? body.seat_preference : "NONE",
    solo_desk: placement === "NONE" ? false : body.solo_desk,
  };
}

/** Kaydetmeden önceki denetim — metin backend'inkiyle aynı anlamdadır. */
function eksik(body: AccommodationBody): string | null {
  if (body.placement === "SEPARATE_ROOM" && body.target_room_id === null) {
    return "“Ayrı salon” için salon seçin.";
  }
  if (
    !Number.isInteger(body.extra_minutes) ||
    body.extra_minutes < 0 ||
    body.extra_minutes > MAX_EXTRA_MINUTES
  ) {
    return `Ek süre 0 ile ${MAX_EXTRA_MINUTES} dakika arasında olmalı.`;
  }
  const tedbirVar =
    body.placement !== "NONE" || body.extra_minutes > 0 || body.reader || body.scribe;
  if (body.reason_category !== "IEP" && !tedbirVar) {
    return "BEP dışındaki gerekçede en az bir tedbir seçin (yer, ek süre ya da destek).";
  }
  return null;
}

export default function TedbirDialog({
  row,
  listedStudentIds = new Set<number>(),
  onClose,
  onSaved,
}: {
  /** null → ekleme; dolu → o satırın tedbirlerini düzenleme. */
  row: IepStudent | null;
  /** Listede zaten olan öğrenciler aramada görünür ama seçilemez (öğrenci başına tek satır). */
  listedStudentIds?: Set<number>;
  onClose: () => void;
  onSaved: () => void;
}) {
  const snackbar = useSnackbar();
  const [kip, setKip] = useState<Kip>("tek");
  const [ogrenci, setOgrenci] = useState<Student | null>(null);
  const [numaralar, setNumaralar] = useState("");
  const [body, setBody] = useState<AccommodationBody>(() => (row ? satirdan(row) : bos()));
  const [dakika, setDakika] = useState(() => String(row?.extra_minutes ?? 0));

  const salonlar = useQuery({
    queryKey: ["exam-rooms"],
    queryFn: () => examRoomApi.list(false),
  });

  const govde: AccommodationBody = {
    ...body,
    extra_minutes: dakika.trim() === "" ? 0 : Number(dakika),
  };
  const sorun = eksik(govde);

  const kaydet = useMutation({
    mutationFn: async (): Promise<string> => {
      if (row) {
        await iepApi.update(row.id, govde);
        return "Tedbirler kaydedildi.";
      }
      if (kip === "tek") {
        if (ogrenci === null) throw new Error("Öğrenci seçilmedi.");
        await iepApi.add(ogrenci.id, govde);
        return "Öğrenci listeye eklendi.";
      }
      const sonuc = await iepApi.addByNumbers(numaralar, govde);
      const parcalar = [`${sonuc.added} öğrenci eklendi`];
      if (sonuc.already) parcalar.push(`${sonuc.already} öğrenci zaten listedeydi`);
      if (sonuc.not_found.length) {
        parcalar.push(`bu numaralarla aktif öğrenci yok: ${sonuc.not_found.join(", ")}`);
      }
      return `${parcalar.join("; ")}.`;
    },
    onSuccess: (mesaj) => {
      snackbar.success(mesaj);
      onSaved();
    },
    onError: (e) => snackbar.error(e instanceof ApiError ? e.message : "Kaydedilemedi."),
  });

  const searchStudents = (q: string): Promise<Student[]> =>
    okulApi.listStudents({ search: q, onlyActive: true, limit: 20 }).then((p) => p.results);

  const secimEksik = row === null && (kip === "tek" ? ogrenci === null : numaralar.trim() === "");
  const destekli = govde.reader || govde.scribe;
  const salonIci = govde.placement === "HOME_CLASSROOM" || govde.placement === "SEPARATE_ROOM";

  return (
    <Dialog
      open
      wide
      onClose={onClose}
      title={row ? "Tedbirleri düzenle" : "Öğrenci ekle"}
      actions={
        <>
          <Button variant="text" onClick={onClose} disabled={kaydet.isPending}>
            Vazgeç
          </Button>
          <Button
            icon="check"
            onClick={() => kaydet.mutate()}
            disabled={kaydet.isPending || secimEksik || sorun !== null}
          >
            {kaydet.isPending ? "Kaydediliyor…" : "Kaydet"}
          </Button>
        </>
      }
    >
      <div className="flex flex-col gap-4">
        {row ? (
          <p className="text-body-medium text-on-surface">
            <span className="text-on-surface-variant">{row.student_number}</span> {row.full_name}{" "}
            <span className="text-body-small text-on-surface-variant">— {row.class_label}</span>
          </p>
        ) : (
          <>
            <fieldset className="flex flex-wrap gap-x-6 gap-y-1">
              <legend className="sr-only">Öğrenci nasıl seçilsin?</legend>
              <label className="flex min-h-9 items-center gap-2 text-body-medium text-on-surface">
                <input
                  type="radio"
                  name="kip"
                  className="h-5 w-5 accent-primary"
                  checked={kip === "tek"}
                  onChange={() => setKip("tek")}
                />
                Tek öğrenci
              </label>
              <label className="flex min-h-9 items-center gap-2 text-body-medium text-on-surface">
                <input
                  type="radio"
                  name="kip"
                  className="h-5 w-5 accent-primary"
                  checked={kip === "toplu"}
                  onChange={() => setKip("toplu")}
                />
                Okul numaralarıyla toplu
              </label>
            </fieldset>
            {kip === "tek" ? (
              <Autocomplete<Student>
                label="Öğrenci"
                placeholder="Ad veya okul no…"
                selected={ogrenci}
                search={searchStudents}
                onSelect={setOgrenci}
                onClear={() => setOgrenci(null)}
                getLabel={(s) => `${s.full_name} (${s.student_number})`}
                getSublabel={(s) => s.class_label}
                getKey={(s) => s.id}
                getDisabled={(s) => (listedStudentIds.has(s.id) ? "zaten listede" : undefined)}
                required
              />
            ) : (
              <label className="flex flex-col gap-1 text-label-large text-on-surface-variant">
                Okul numaraları
                <textarea
                  aria-label="Okul numaraları"
                  rows={3}
                  value={numaralar}
                  onChange={(e) => setNumaralar(e.target.value)}
                  placeholder="Örnek: 101 102 215 — boşluk, virgül ya da satırla ayırın"
                  className="block w-full rounded-shape-xs border border-outline bg-surface px-4 py-3 text-body-medium text-on-surface outline-none placeholder:text-on-surface-variant/60 focus-visible:ring-2 focus-visible:ring-primary"
                />
                <span className="text-body-small">
                  Hepsine aşağıdaki gerekçe ve tedbirler yazılır; farklı olanı sonra satırından
                  düzenleyin.
                </span>
              </label>
            )}
          </>
        )}

        <Select
          label="Gerekçe"
          value={govde.reason_category}
          onChange={(e) => setBody({ ...body, reason_category: e.target.value as RuleReason })}
          options={GEREKCE_SIRASI.map((value) => ({ value, label: RULE_REASON_TR[value] }))}
          helperText="Yalnız kategori tutulur; tanı, rapor ya da açıklama HİÇ kaydedilmez. Bireysel soru dosyası yalnız BEP gerekçesinde uygulanır."
        />

        <fieldset className="flex flex-col gap-3 rounded-shape-md border border-outline-variant p-3">
          <legend className="px-1 text-label-large text-on-surface-variant">Yer</legend>
          <Select
            label="Sınava nerede girsin?"
            value={govde.placement}
            onChange={(e) => setBody(yerDegisti(body, e.target.value as AccommodationPlacement))}
            options={(Object.keys(PLACEMENT_TR) as AccommodationPlacement[]).map((value) => ({
              value,
              label: PLACEMENT_TR[value],
            }))}
            helperText="Her sınav oturumunda kendiliğinden uygulanır; oturumda öğrenciye kural girerseniz o geçerli olur."
          />
          {govde.placement === "SEPARATE_ROOM" && (
            <Select
              label="Salon"
              placeholder="Seçin"
              value={govde.target_room_id === null ? "" : String(govde.target_room_id)}
              onChange={(e) =>
                setBody({
                  ...body,
                  target_room_id: e.target.value === "" ? null : Number(e.target.value),
                })
              }
              options={(salonlar.data?.results ?? []).map((r) => ({
                value: String(r.id),
                label: r.group_name ? `${r.name} · ${r.group_name}` : r.name,
              }))}
            />
          )}
          {salonIci && (
            <Select
              label="Salon içinde"
              value={govde.seat_preference}
              onChange={(e) =>
                setBody({ ...body, seat_preference: e.target.value as SeatPreference })
              }
              options={(Object.keys(SEAT_PREFERENCE_TR) as SeatPreference[]).map((value) => ({
                value,
                label: SEAT_PREFERENCE_TR[value],
              }))}
            />
          )}
          {govde.placement !== "NONE" && (
            <label className="flex min-h-9 items-center gap-2 text-body-medium text-on-surface">
              <input
                type="checkbox"
                className="h-5 w-5 accent-primary"
                checked={govde.solo_desk}
                onChange={(e) => setBody({ ...body, solo_desk: e.target.checked })}
              />
              Sırada tek başına otursun
            </label>
          )}
        </fieldset>

        <fieldset className="flex flex-col gap-3 rounded-shape-md border border-outline-variant p-3">
          <legend className="px-1 text-label-large text-on-surface-variant">Süre ve destek</legend>
          <TextField
            label="Ek süre (dakika)"
            type="number"
            inputMode="numeric"
            min={0}
            max={MAX_EXTRA_MINUTES}
            step={5}
            value={dakika}
            onChange={(e) => setDakika(e.target.value)}
            helperText="0 = ek süre yok. Salon evrakına basılmaz; idare özetinde görünür, gözetmene siz bildirirsiniz."
          />
          <div className="flex flex-wrap gap-x-6">
            <label className="flex min-h-9 items-center gap-2 text-body-medium text-on-surface">
              <input
                type="checkbox"
                className="h-5 w-5 accent-primary"
                checked={govde.reader}
                onChange={(e) => setBody({ ...body, reader: e.target.checked })}
              />
              Okuyucu desteği
            </label>
            <label className="flex min-h-9 items-center gap-2 text-body-medium text-on-surface">
              <input
                type="checkbox"
                className="h-5 w-5 accent-primary"
                checked={govde.scribe}
                onChange={(e) => setBody({ ...body, scribe: e.target.checked })}
              />
              Yazıcı desteği
            </label>
          </div>
          {destekli && govde.placement !== "SEPARATE_ROOM" && (
            <p className="flex flex-wrap items-center gap-2 rounded-shape-sm bg-tertiary-container px-3 py-2 text-body-small text-on-tertiary-container">
              <span>
                Sesli okuma ve yazdırma salondaki öbür öğrencileri etkiler; “Ayrı salon” önerilir.
              </span>
              <Button variant="text" onClick={() => setBody(yerDegisti(body, "SEPARATE_ROOM"))}>
                Ayrı salon seç
              </Button>
            </p>
          )}
          <p className="text-body-small text-on-surface-variant">
            Görevli öğretmeni program atamaz; ihtiyaç idare özetinde öğrencinin salonuyla birlikte
            görünür.
          </p>
        </fieldset>

        {sorun && <p className="text-body-small text-error">{sorun}</p>}
      </div>
    </Dialog>
  );
}
