import type { EstadoIA, Profile, ProfileInput, ProfileSummary, Tarea } from "./types";

// En la app instalada la interfaz y el API comparten origen (""). En desarrollo,
// NEXT_PUBLIC_API_URL apunta al backend local (p. ej. http://127.0.0.1:8000).
const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? "";
const TOKEN_KEY = "tcv-token";

/** Errores de validación por campo, p. ej. { email: "El correo no es válido" }. */
export class ApiError extends Error {
  constructor(
    message: string,
    public status: number,
    public fields: Record<string, string> = {},
  ) {
    super(message);
  }
}

let memoryToken = "";

/**
 * El lanzador abre la ventana en http://127.0.0.1:PUERTO/#TOKEN. El token se guarda
 * en memoria y en sessionStorage (para sobrevivir a recargas) y se borra de la URL.
 */
export function initToken(): boolean {
  if (typeof window === "undefined") return false;
  const fromHash = window.location.hash.slice(1);
  if (fromHash) {
    memoryToken = fromHash;
    try {
      window.sessionStorage.setItem(TOKEN_KEY, fromHash);
    } catch {
      /* sin sessionStorage: solo en memoria */
    }
    window.history.replaceState(null, "", window.location.pathname + window.location.search);
  }
  if (!memoryToken) {
    try {
      memoryToken = window.sessionStorage.getItem(TOKEN_KEY) ?? "";
    } catch {
      /* ignorar */
    }
  }
  if (!memoryToken && process.env.NEXT_PUBLIC_DEV_TOKEN) {
    memoryToken = process.env.NEXT_PUBLIC_DEV_TOKEN; // solo desarrollo
  }
  return memoryToken !== "";
}

const MENSAJES: Record<number, string> = {
  401: "La sesión no es válida. Cierra y vuelve a abrir la aplicación.",
  403: "Acceso no permitido.",
  404: "No se encontró el perfil. Puede que ya se haya eliminado.",
};

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  let res: Response;
  try {
    res = await fetch(API_BASE + path, {
      ...init,
      headers: {
        ...(init.body ? { "Content-Type": "application/json" } : {}),
        "x-tcv-token": memoryToken,
      },
    });
  } catch {
    throw new ApiError("No se pudo conectar con el servicio local. ¿Está en ejecución?", 0);
  }
  if (res.status === 204) return undefined as T;
  if (!res.ok) {
    if (res.status === 422) {
      const body = await res.json().catch(() => null);
      const fields: Record<string, string> = {};
      for (const e of body?.detail ?? []) {
        const campo = String(e.loc?.[1] ?? "");
        const msg = String(e.msg ?? "").replace(/^Value error, /, "");
        if (campo && !fields[campo]) fields[campo] = msg;
      }
      throw new ApiError("Revisa los campos marcados.", 422, fields);
    }
    throw new ApiError(MENSAJES[res.status] ?? `Error inesperado (${res.status}).`, res.status);
  }
  return (await res.json()) as T;
}

export const ia = {
  estado: () => request<EstadoIA>("/api/ia/estado"),
  lanzar: (tipo: string) => request<Tarea>("/api/tareas", { method: "POST", body: JSON.stringify({ tipo }) }),
  tarea: (id: string) => request<Tarea>(`/api/tareas/${encodeURIComponent(id)}`),
  cancelar: (id: string) => request<Tarea>(`/api/tareas/${encodeURIComponent(id)}/cancelar`, { method: "POST" }),
};

export const api = {
  listar: () => request<ProfileSummary[]>("/api/perfiles"),
  obtener: (id: string) => request<Profile>(`/api/perfiles/${encodeURIComponent(id)}`),
  crear: (data: ProfileInput) => request<Profile>("/api/perfiles", { method: "POST", body: JSON.stringify(data) }),
  actualizar: (id: string, data: ProfileInput) =>
    request<Profile>(`/api/perfiles/${encodeURIComponent(id)}`, { method: "PUT", body: JSON.stringify(data) }),
  duplicar: (id: string) => request<Profile>(`/api/perfiles/${encodeURIComponent(id)}/duplicar`, { method: "POST" }),
  eliminar: (id: string) => request<void>(`/api/perfiles/${encodeURIComponent(id)}`, { method: "DELETE" }),
};
