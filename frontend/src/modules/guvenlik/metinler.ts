// Güvenlik arayüzünün DÜRÜST metinleri — tek kaynak (tasarım §6/§10.2).
// Kural: bu program "veritabanını şifreliyorum" DEMEZ. Şifrelenen şey belirli
// kişisel veri alanlarıdır; anahtar da aynı bilgisayarda durur. Kullanıcıya
// olduğundan güçlü bir koruma vadetmek, gerçek önlemi (tam disk şifreleme)
// almasını engellerdi.

/** Ayarlar ve kilit ekranında gösterilen kapsam açıklaması. */
export const KAPSAM_METNI =
  "Bu koruma, kayıtlardaki kişisel veri alanlarını (öğrenci ve öğretmen " +
  "ad-soyadları, öğrenci fotoğrafları) parolanızdan türetilen bir anahtarla şifreler. TAM DİSK " +
  "ŞİFRELEME DEĞİLDİR: bilgisayarın tamamını korumak için Windows'ta " +
  "BitLocker, Pardus/Linux'ta LUKS kullanın.";

/** Şifrelenmeyen alanlar açıkça söylenir — sürpriz olmasın. */
export const KAPSAM_DISI_METNI =
  "Okul numarası, sınıf/şube ve oturma düzeni bilgisi şifrelenmez (dağıtım, " +
  "sıralama ve süzgeçler bunlara dayanır). Soru belgesi PDF'leri de şifrelenmez.";

/** Kurtarma anahtarı diyaloğunun uyarısı. */
export const KURTARMA_UYARISI =
  "Bu anahtar bir daha gösterilmez. Parolanızı unutursanız kayıtlara ERİŞMENİN " +
  "TEK YOLU budur. Yazdırın veya elle yazıp okul kasasında saklayın; " +
  "bilgisayarın kendisinde saklamayın.";

/** Parola kurma onayı. */
export const KURMA_UYARISI =
  "Parola konulduğunda mevcut kayıtlar şifrelenir. İşlem öncesi otomatik yedek " +
  "alınır ve birkaç saniye sürer; bu sırada programı kapatmayın.";

/** Parola kaldırma onayı. */
export const KALDIRMA_UYARISI =
  "Parola kaldırılınca kişisel veri alanları düz metne döner ve programı açan " +
  "herkes okuyabilir. İşlem öncesi otomatik yedek alınır.";

/** Yarım kalan geçiş uyarısı (elektrik kesintisi vb.). */
export const YARIM_GECIS_METNI =
  "Önceki güvenlik işlemi yarıda kalmış. Parolanızla açtığınızda kaldığı yerden " +
  "otomatik olarak tamamlanacaktır.";

// ---------------------------------------------------------------------------
// Kurtarma anahtarını yenileme (görev devri)
// ---------------------------------------------------------------------------

/** Yenileme kartının açıklaması. */
export const YENILEME_METNI =
  "Kurtarma anahtarını elinde tutan kişi görevden ayrıldıysa ya da kâğıt kaybolduysa " +
  "yeni bir anahtar üretin. Parolanız değişmez, kayıtlar yeniden şifrelenmez. Parolayı " +
  "değiştirmek eski kurtarma anahtarını geçersiz kılmaz; bunun için bu işlem gerekir.";

/** Yenileme onay diyaloğu: sonuç (başlık soru, gövde sonuç — docs/sozluk.md §3). */
export const YENILEME_SONUCU_METNI =
  "Yeni bir kurtarma anahtarı üretilir ve bir kez gösterilir. Eski anahtar bu " +
  "bilgisayardaki kayıtların kilidini artık açmaz.";

/**
 * Eski yedekler: her yedek alındığı günün güvenlik dosyasını içinde taşır (backend
 * `backup_restore`). Testle kanıtlı: `apps/okul/tests/test_kurtarma_yenileme.py::TestYedekler`.
 */
export const ESKI_YEDEK_METNI =
  "Bugünden önce alınmış yedekler (USB bellektekiler dahil) eski anahtarla açılmaya " +
  "devam eder: her yedek, alındığı günün güvenlik dosyasını içinde taşır. Bu bilgisayarda " +
  "o yedekler yeni anahtarla da açılır. Eski yedekler duruyorsa eski kâğıdı atmayın; " +
  "“Eski anahtar — bugünden önceki yedekler için” diye işaretleyip ayrı saklayın.";

/** Dürüst sınır: kayıtların anahtarı değişmez, yenileme tam bir iptal değildir. */
export const ELE_GECMIS_ANAHTAR_METNI =
  "Yenileme, başkasının eline geçmiş bir anahtara karşı tam koruma değildir: kayıtların " +
  "anahtarı değişmez. Eski anahtarı bilen biri, eski bir yedeği ya da veri klasöründe " +
  "“guvenlik-arsiv” adıyla saklanan önceki güvenlik dosyasını ele geçirirse kayıtlara " +
  "ulaşabilir. Eski yedekleri ve veri klasörünü bu gözle koruyun.";

// ---------------------------------------------------------------------------
// Güvenlik dosyası kayıp ekranı
// ---------------------------------------------------------------------------

export const DOSYA_KAYIP_BASLIGI = "Güvenlik dosyası bulunamadı ya da okunamıyor";

/** Ne oldu? */
export const DOSYA_KAYIP_METNI =
  "Bu bilgisayarda uygulama parolası kurulmuş, ancak kayıtların anahtarını saklayan " +
  "güvenlik dosyası (guvenlik.json) veri klasöründe bulunamadı ya da okunamıyor (boş " +
  "ya da bozuk). Dosya olmadan kayıtlar açılamaz. Yeni parola da kurulamaz; kurulsaydı " +
  "eski kayıtlar hiç okunamaz hâle gelirdi.";

/** Birinci çıkış yolu. */
export const DOSYA_KAYIP_GERI_KOY =
  "Dosyanın sağlam bir kopyası varsa (ör. bilgisayar taşınırken alınan veri klasörü ya " +
  "da USB bellekteki kopya) guvenlik.json dosyasını veri klasörüne geri koyun (bozuk " +
  "dosya varsa onun yerine), ardından “Yeniden denetle” düğmesine basın.";

/** İkinci çıkış yolu. */
export const DOSYA_KAYIP_YEDEKTEN =
  "Kopya yoksa aşağıdan bir yedeği geri yükleyin: her şifreli yedek güvenlik dosyasını " +
  "da içinde taşır ve geri yükleme dosyayı yeniden oluşturur. Yedeğin alındığı dönemdeki " +
  "uygulama parolası ya da kurtarma anahtarı gerekir; o yedekten sonra girilen kayıtlar " +
  "ekrandan kalkar.";

/** Üçüncü çıkış yolu — yalnız korunan satır yokken (backend `reset_available`). */
export const DOSYA_KAYIP_SIFIRLA_METNI =
  "Okunamayan dosya bu veritabanındaki hiçbir kaydı korumuyor: kayıtların anahtarı " +
  "veritabanına hiç işlenmemiş ya da parola kaldırılmış. Dosyayı kenara alıp parolasız " +
  "çalışmaya dönebilirsiniz. Dosya silinmez, veri klasöründe “guvenlik-arsiv” adıyla " +
  "kalır; isterseniz Ayarlar → Güvenlik’ten yeniden parola koyarsınız.";
