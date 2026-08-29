// Backend API istemcisi — OYS `lib/api.ts`'ten UYARLANMIŞTIR (Görev 3).
// Kelebek Sınav authsuz/tek-kullanıcılı çalışır (README "Mimari"): JWT/Bearer,
// token yenileme, `personnel_inactive`/`password_change_required` oturum kapıları
// ve impersonation TAMAMEN çıkarıldı. Kalan: temel `fetch` sarmalayıcı, `ApiError`,
// backend `{code, message, fields}` hata sözleşmesi (CLAUDE.md §7 mirası) ve
// snake_case gövde. Blob yardımcıları (`getBlob`/`postBlob`) evrak/PDF üretimi
// (sınav evrak seti: kroki, yoklama, tutanaklar, kitapçıklar) için korunur.

// Boş/tanımsız → göreli "/api/v1": geliştirmede Vite proxy'si (vite.config.ts
// server.proxy) backend'e yönlendirir. Mutlak URL yalnız özel senaryoda gerekir.
const API_BASE = import.meta.env.VITE_API_BASE_URL || "/api/v1";

export class ApiError extends Error {
  status: number;
  code: string;
  fields: Record<string, unknown>;

  constructor(status: number, code: string, message: string, fields: Record<string, unknown> = {}) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.code = code;
    this.fields = fields;
  }
}

interface RequestOptions {
  method?: string;
  body?: unknown;
}

async function request<T>(path: string, options: RequestOptions = {}): Promise<T> {
  const { method = "GET", body } = options;
  const isForm = body instanceof FormData;
  const headers: Record<string, string> = {};
  // FormData'da Content-Type'ı tarayıcı (boundary ile) kendisi koyar.
  if (body !== undefined && !isForm) headers["Content-Type"] = "application/json";

  const resp = await fetch(`${API_BASE}${path}`, {
    method,
    headers,
    body: body === undefined ? undefined : isForm ? (body as FormData) : JSON.stringify(body),
  });

  if (resp.status === 204) return undefined as T;

  let data: unknown = null;
  try {
    data = await resp.json();
  } catch {
    /* boş gövde */
  }

  if (!resp.ok) {
    const d = (data ?? {}) as { code?: string; message?: string; fields?: Record<string, unknown> };
    throw new ApiError(
      resp.status,
      d.code ?? String(resp.status),
      d.message ?? "Beklenmeyen bir hata oluştu.",
      d.fields ?? {},
    );
  }
  return data as T;
}

/** İkili (dosya) indirme — evrak/PDF üretimi (sınav evrak seti) için. */
async function requestBlob(
  path: string,
  options: { method?: string; body?: unknown } = {},
): Promise<Blob> {
  const { method = "GET", body } = options;
  const headers: Record<string, string> = {};
  if (body !== undefined) headers["Content-Type"] = "application/json";
  const resp = await fetch(`${API_BASE}${path}`, {
    method,
    headers,
    body: body === undefined ? undefined : JSON.stringify(body),
  });
  if (!resp.ok) {
    // Hatalı yanıt genelde JSON; gövdeyi okuyup ApiError'a aktar.
    let code = String(resp.status);
    let message = "Dosya indirilemedi.";
    let fields: Record<string, unknown> = {};
    try {
      const d = (await resp.json()) as {
        code?: string;
        message?: string;
        fields?: Record<string, unknown>;
      };
      code = d.code ?? code;
      message = d.message ?? message;
      fields = d.fields ?? {};
    } catch {
      /* boş gövde */
    }
    throw new ApiError(resp.status, code, message, fields);
  }
  return resp.blob();
}

export const api = {
  get: <T>(path: string) => request<T>(path, { method: "GET" }),
  post: <T>(path: string, body?: unknown) => request<T>(path, { method: "POST", body }),
  patch: <T>(path: string, body?: unknown) => request<T>(path, { method: "PATCH", body }),
  put: <T>(path: string, body?: unknown) => request<T>(path, { method: "PUT", body }),
  /** Çok parçalı (dosya) gönderim — Content-Type tarayıcıya bırakılır. */
  postForm: <T>(path: string, form: FormData) => request<T>(path, { method: "POST", body: form }),
  putForm: <T>(path: string, form: FormData) => request<T>(path, { method: "PUT", body: form }),
  del: <T>(path: string) => request<T>(path, { method: "DELETE" }),
  /** Dosya indirme (evrak/PDF). */
  getBlob: (path: string) => requestBlob(path),
  /** JSON body ile POST + dosya yanıtı. */
  postBlob: (path: string, body?: unknown) => requestBlob(path, { method: "POST", body }),
};

export { API_BASE };
