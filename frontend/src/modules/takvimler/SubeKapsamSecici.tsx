// Takvim girdisi katılımcı kapsamı — ORTAK seçim parçaları.
// Buraya taşındı (31.08.2026 denetimi): kapsam artık iki yerde seçiliyor —
// "Seçmeli ders seç" dialog'unda (henüz eklenmemiş ders) ve havuz tablosundaki
// "Kapsamı düzenle" dialog'unda (eklenmiş girdi). İki kopya, çip görünümü ile
// aria etiketlerini sürüklenmeye açardı.
//
// Küme çipi şubeleri seçime EKLER, AYRI DURUM TUTMAZ ("gruptan gelen" ile "elle
// seçilen" için ikinci kaynak-gerçek doğardı; emsal SinavSihirbazi.applyGroup).
// Küme kimliği hiçbir takvim kaydına yazılmaz (CLAUDE.md §3).

export const KAPSAM_SECENEKLERI = [
  { value: "LEVEL", label: "Seviye geneli" },
  { value: "SECTIONS", label: "Şube seç" },
];

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
          Bu seviyede tanımlı şube yok — şube kataloğunu Ayarlar’dan doldurun.
        </p>
      ) : (
        <div className="grid max-h-48 grid-cols-3 gap-1 overflow-y-auto">
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
