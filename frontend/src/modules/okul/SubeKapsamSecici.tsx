// Şube kapsamı seçimi — ORTAK parça (okul modülünde, üç ekran kullanır).
// 31.08.2026'da takvim modülünde doğdu (seçmeli ders dialog'u + havuzdaki
// "Kapsamı düzenle"); 03.09.2026'da kapsamın KAYNAĞI ders havuzuna taşınınca
// (Ders Havuzu → "Şubeler") buraya alındı. Üç kopya, çip görünümü ile aria
// etiketlerini sürüklenmeye açardı.
//
// Küme çipi şubeleri seçime EKLER, AYRI DURUM TUTMAZ ("gruptan gelen" ile "elle
// seçilen" için ikinci kaynak-gerçek doğardı; emsal SinavSihirbazi.applyGroup).
// Küme kimliği hiçbir takvim kaydına yazılmaz (CLAUDE.md §3).
//
// Sözcükler docs/sozluk.md'den: alan adı "Katılımcılar", seçenekler "Sınıf
// düzeyinin tamamı" / "Seçili şubeler" — oturum sihirbazı ile takvim AYNI
// sözcükleri kullanır ("Seviye geneli", "Şube seç", tek başına "Kapsam" YOK).
// Takvim ve ders havuzu ekranları bu sabitleri buradan okur; metin ikinci bir
// yere yazılmaz.

/** Katılımcı kapsamı alanının etiketi. */
export const KATILIMCILAR_ETIKETI = "Katılımcılar";

/** `participant_type` = LEVEL: sınıf düzeyindeki bütün şubeler. */
export const SINIF_DUZEYININ_TAMAMI = "Sınıf düzeyinin tamamı";

/** `participant_type` = SECTIONS: yalnız işaretlenen şubeler. */
export const SECILI_SUBELER = "Seçili şubeler";

export const KAPSAM_SECENEKLERI = [
  { value: "LEVEL", label: SINIF_DUZEYININ_TAMAMI },
  { value: "SECTIONS", label: SECILI_SUBELER },
];

/**
 * Bir girdinin katılımcı özeti — tablo hücresi ve rozetler için. Backend'in
 * `participant_label` alanı da aynı sözcükleri taşır (19.09.2026'dan beri); arayüz
 * yine de metni tip + şube sayısından KENDİSİ üretir — tek kaynak bu dosyadır.
 */
export function katilimciOzeti(participantType: string, sectionCount: number): string {
  return participantType === "SECTIONS" ? `${sectionCount} şube` : SINIF_DUZEYININ_TAMAMI;
}

/**
 * Küme çipleri + şube onay kutuları. Çip `aria-pressed` TAŞIMAZ: durum tutmaz,
 * yalnız "ekle" eylemidir (sihirbazdaki görsel sözleşmenin aynısı).
 */
export default function SubeSecici({
  adPreki,
  sectionIds,
  sections,
  groups,
  onToggleSection,
  onApplyGroup,
}: {
  adPreki: string;
  sectionIds: number[];
  sections: { id: number; class_label: string }[];
  groups: { id: number; name: string }[];
  onToggleSection: (id: number) => void;
  onApplyGroup: (groupId: number) => void;
}) {
  return (
    <div>
      {groups.length > 0 ? (
        <div className="mb-2 flex flex-wrap items-center gap-2">
          <span className="text-body-small text-on-surface-variant">Kümeden ekle:</span>
          {groups.map((g) => (
            <button
              key={g.id}
              type="button"
              aria-label={`${adPreki}: ${g.name} kümesini ekle`}
              onClick={() => onApplyGroup(g.id)}
              className="min-h-8 rounded-full bg-secondary-container px-3 text-label-medium text-on-secondary-container hover:bg-secondary-container/80 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary"
            >
              {g.name}
            </button>
          ))}
        </div>
      ) : null}
      {sections.length === 0 ? (
        <p className="text-body-small text-on-surface-variant">
          Bu sınıf düzeyinde tanımlı şube yok — şube kataloğunu Ayarlar’dan doldurun.
        </p>
      ) : (
        // Dar diyalogda üç sütun şube etiketini ("11/AMP") sıkıştırıp satırı
        // kırıyordu; ızgara dar ekranda iki, genişte üç sütundur.
        <div className="grid max-h-48 grid-cols-2 gap-1 overflow-y-auto sm:grid-cols-3">
          {sections.map((s) => (
            <label
              key={s.id}
              className="flex min-h-9 cursor-pointer items-center gap-2 rounded-shape-sm border border-outline px-3 text-body-medium text-on-surface"
            >
              <input
                type="checkbox"
                checked={sectionIds.includes(s.id)}
                onChange={() => onToggleSection(s.id)}
                className="h-5 w-5 accent-primary"
                aria-label={`${adPreki}: ${s.class_label}`}
              />
              {s.class_label}
            </label>
          ))}
        </div>
      )}
    </div>
  );
}
