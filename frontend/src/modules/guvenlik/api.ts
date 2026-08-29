// `guvenlik` modülü API istemcisi — uygulama parolası / kilit uçları.
// Backend `apps/okul/{urls,views}.py` "security/*" bloğuyla BİREBİR.
// Parolalar YALNIZ gövdede taşınır; hiçbir yanıtta geri dönmez. Tek istisna
// `enable` yanıtındaki `recovery_key`: tek seferlik üretilir, bir daha alınamaz.

import { api } from "../../lib/api";

/** `GET /security/status/` — sır içermez, her açılışta okunur. */
export interface GuvenlikDurumu {
  /** Uygulama parolası kurulu mu (veri dizininde guvenlik.json var mı)? */
  password_set: boolean;
  /** Kurulu ve anahtar bellekte değil → veri okunamaz. */
  locked: boolean;
  /** Yarım kalmış şifreleme/çözme geçişi var mı (elektrik kesintisi vb.)? */
  transition_pending: boolean;
  /** "SIFRELENIYOR" | "COZULUYOR" | "" (yalnız yarım geçişte dolu). */
  transition: string;
  /** Korunan alanların Türkçe adları — arayüz metni bunları listeler. */
  protected_fields: string[];
}

/** `POST /security/enable/` yanıtı: durum + TEK SEFERLİK kurtarma anahtarı. */
export interface ParolaKurmaSonucu extends GuvenlikDurumu {
  recovery_key: string;
}

export const guvenlikApi = {
  durum: () => api.get<GuvenlikDurumu>("/security/status/"),
  kur: (password: string) => api.post<ParolaKurmaSonucu>("/security/enable/", { password }),
  ac: (password: string) => api.post<GuvenlikDurumu>("/security/unlock/", { password }),
  kilitle: () => api.post<GuvenlikDurumu>("/security/lock/"),
  kurtar: (recovery_key: string, new_password: string) =>
    api.post<GuvenlikDurumu>("/security/recover/", { recovery_key, new_password }),
  parolaDegistir: (current_password: string, new_password: string) =>
    api.post<GuvenlikDurumu>("/security/change-password/", { current_password, new_password }),
  kaldir: (password: string) => api.post<GuvenlikDurumu>("/security/disable/", { password }),
};
