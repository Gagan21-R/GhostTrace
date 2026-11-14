// Thin fetch wrapper: attaches the JWT, normalises the backend's error envelope, supports uploads and blobs.
const TOKEN_KEY = "evx_token";

export function getToken(): string | null {
  try { return localStorage.getItem(TOKEN_KEY); } catch { return null; }
}
export function setToken(t: string | null) {
  try { t ? localStorage.setItem(TOKEN_KEY, t) : localStorage.removeItem(TOKEN_KEY); } catch { /* storage unavailable */ }
}

export class ApiError extends Error {
  status: number; details: unknown;
  constructor(status: number, message: string, details?: unknown) { super(message); this.status = status; this.details = details; }
}

async function request<T>(method: string, path: string, body?: unknown, isForm = false): Promise<T> {
  const headers: Record<string, string> = {};
  const tok = getToken();
  if (tok) headers.Authorization = `Bearer ${tok}`;
  if (body !== undefined && !isForm) headers["Content-Type"] = "application/json";
  const res = await fetch(path, { method, headers, body: body === undefined ? undefined : isForm ? (body as FormData) : JSON.stringify(body) });
  if (res.status === 401 && path !== "/api/auth/login") {
    setToken(null);
    if (!location.pathname.startsWith("/login")) location.assign("/login");
  }
  const text = await res.text();
  const data = text ? (() => { try { return JSON.parse(text); } catch { return text; } })() : null;
  if (!res.ok) {
    const err = (data && (data as any).error) || {};
    const details = err.details;
    let msg = err.message || res.statusText;
    if (Array.isArray(details) && details[0]?.message) msg = `${msg}: ${details.map((d: any) => `${d.field} ${d.message}`).join("; ")}`;
    throw new ApiError(res.status, msg, details);
  }
  return data as T;
}

export const api = {
  get: <T,>(p: string) => request<T>("GET", p),
  post: <T,>(p: string, b?: unknown) => request<T>("POST", p, b ?? {}),
  patch: <T,>(p: string, b: unknown) => request<T>("PATCH", p, b),
  del: <T,>(p: string) => request<T>("DELETE", p),
  upload: <T,>(p: string, form: FormData) => request<T>("POST", p, form, true),
  /** Upload with byte-level progress (XHR), for the evidence vault. */
  uploadWithProgress<T>(p: string, form: FormData, onProgress: (fraction: number) => void): Promise<T> {
    return new Promise((resolve, reject) => {
      const xhr = new XMLHttpRequest();
      xhr.open("POST", p);
      const tok = getToken();
      if (tok) xhr.setRequestHeader("Authorization", `Bearer ${tok}`);
      xhr.upload.onprogress = (e) => { if (e.lengthComputable) onProgress(e.loaded / e.total); };
      xhr.onload = () => {
        let data: any = null;
        try { data = JSON.parse(xhr.responseText); } catch { /* not JSON */ }
        if (xhr.status >= 200 && xhr.status < 300) resolve(data as T);
        else reject(new ApiError(xhr.status, data?.error?.message || xhr.statusText, data?.error?.details));
      };
      xhr.onerror = () => reject(new ApiError(0, "Network error during upload"));
      xhr.send(form);
    });
  },
  async blobUrl(p: string): Promise<{ url: string; type: string }> {
    const res = await fetch(p, { headers: getToken() ? { Authorization: `Bearer ${getToken()}` } : {} });
    if (!res.ok) throw new ApiError(res.status, "Could not load file");
    const b = await res.blob();
    return { url: URL.createObjectURL(b), type: b.type };
  },
  async download(p: string, filename: string) {
    const { url } = await api.blobUrl(p);
    const a = document.createElement("a");
    a.href = url; a.download = filename; a.click();
    setTimeout(() => URL.revokeObjectURL(url), 4000);
  },
};
