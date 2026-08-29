import Card from "../../ui/Card";
import Icon from "../../ui/Icon";

export default function HakkindaPage() {
  return (
    <div className="mx-auto max-w-4xl space-y-5">
      <header>
        <p className="text-label-medium font-semibold tracking-wide text-primary">Kelebek Sınav</p>
        <h1 className="mt-1 text-headline-medium font-semibold tracking-tight text-on-surface">
          Hakkında ve Lisans
        </h1>
        <p className="mt-2 text-body-medium text-on-surface-variant">
          Programın geliştirici, iletişim ve kullanım koşulları.
        </p>
      </header>

      <Card className="p-5 sm:p-6">
        <div className="flex items-start gap-4">
          <span className="flex h-11 w-11 shrink-0 items-center justify-center rounded-shape-md bg-primary-container text-on-primary-container">
            <Icon name="person" size="xl" />
          </span>
          <div>
            <h2 className="text-title-large font-semibold text-on-surface">Geliştirici</h2>
            <p className="mt-2 text-body-large text-on-surface">Ahmet Ali DEMİRCİ</p>
            <a
              href="mailto:aalidemirci@gmail.com"
              className="mt-1 inline-flex items-center gap-1.5 text-body-medium font-medium text-primary underline-offset-4 hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary"
            >
              <Icon name="mail" size="base" />
              aalidemirci@gmail.com
            </a>
            <p className="mt-3 text-body-medium text-on-surface-variant">
              Programla ilgili talep, öneri, hata bildirimi ve şikâyetlerinizi bu e-posta adresine
              iletebilirsiniz.
            </p>
          </div>
        </div>
      </Card>

      <Card className="p-5 sm:p-6">
        <div className="flex items-start gap-4">
          <span className="flex h-11 w-11 shrink-0 items-center justify-center rounded-shape-md bg-secondary-container text-on-secondary-container">
            <Icon name="license" size="xl" />
          </span>
          <div>
            <h2 className="text-title-large font-semibold text-on-surface">
              Ücretsiz ve ticari olmayan kullanım
            </h2>
            <p className="mt-2 text-body-medium text-on-surface-variant">
              Bu sürüm <strong>PolyForm Noncommercial License 1.0.0</strong> ile sunulur. Eğitim
              kurumları, kamu kurumları, kâr amacı gütmeyen kuruluşlar ve bireyler programı ticari
              olmayan amaçlarla ücretsiz kullanabilir.
            </p>
            <div className="mt-4 rounded-shape-md bg-tertiary-container px-4 py-3 text-body-medium text-on-tertiary-container">
              Program ücretle dağıtılamaz; ücretli teknik destek paketinin, ticari ürünün,
              barındırılan veya yönetilen bir hizmetin parçası olarak sunulamaz. Böyle bir kullanım
              için geliştiriciden ayrıca yazılı ticari lisans alınmalıdır.
            </div>
            <p className="mt-4 text-body-small text-on-surface-variant">
              Gelecekte yayımlanacak sürümlerin lisans veya fiyatlandırma koşulları değişebilir.
              Ücretsiz yayımlanmış bir sürüm ise kendi lisans koşullarıyla ücretsiz ve ticari
              olmayan kullanıma açık kalır. Tam ve bağlayıcı koşullar programla birlikte gelen
              LICENSE dosyasındadır.
            </p>
            <a
              href="https://polyformproject.org/licenses/noncommercial/1.0.0"
              target="_blank"
              rel="noreferrer"
              className="mt-3 inline-flex items-center gap-1.5 text-label-large font-medium text-primary underline-offset-4 hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary"
            >
              Lisansın resmî metni
              <Icon name="open_in_new" size="sm" />
            </a>
          </div>
        </div>
      </Card>
    </div>
  );
}
