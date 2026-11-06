import type {
  Borrador,
  Categoria,
  Comparacion,
  Documento,
  EstadoEntrevista,
  EstadoIA,
  Hecho,
  HechoDatos,
  Informe,
  Plantilla,
  Profile,
  ProfileInput,
  ProfileSummary,
  Tarea,
} from "./types";

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
        // JSON salvo que quien llama indique otro tipo (subida de archivos).
        ...(typeof init.body === "string" ? { "Content-Type": "application/json" } : {}),
        "x-tcv-token": memoryToken,
      },
    });
  } catch {
    throw new ApiError("No se pudo conectar con el servicio local. ¿Está en ejecución?", 0);
  }
  if (res.status === 204) return undefined as T;
  if (!res.ok) {
    const body = await res.json().catch(() => null);
    // Mensajes que el propio backend redacta en español (HTTPException con texto).
    if (typeof body?.detail === "string" && res.status !== 401 && res.status !== 403) {
      throw new ApiError(body.detail, res.status);
    }
    if (res.status === 422) {
      const fields: Record<string, string> = {};
      for (const e of Array.isArray(body?.detail) ? body.detail : []) {
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

export const documentos = {
  listar: (perfilId: string) => request<Documento[]>(`/api/perfiles/${encodeURIComponent(perfilId)}/documentos`),
  // El archivo viaja como cuerpo crudo; el nombre va en la URL solo para mostrarlo.
  subir: (perfilId: string, file: File) =>
    request<{ documento: Documento; tarea: Tarea }>(
      `/api/perfiles/${encodeURIComponent(perfilId)}/documentos?nombre=${encodeURIComponent(file.name)}`,
      { method: "POST", body: file },
    ),
  texto: (id: string) => request<{ paginas: string[] }>(`/api/documentos/${encodeURIComponent(id)}/texto`),
  extraer: (id: string) => request<Tarea>(`/api/documentos/${encodeURIComponent(id)}/extraer`, { method: "POST" }),
  eliminar: (id: string) => request<void>(`/api/documentos/${encodeURIComponent(id)}`, { method: "DELETE" }),
  hechos: (perfilId: string) => request<Hecho[]>(`/api/perfiles/${encodeURIComponent(perfilId)}/hechos`),
  perfil: (id: string) => request<Profile>(`/api/perfiles/${encodeURIComponent(id)}`),
};

/** Descarga un archivo del API (lleva el token en la cabecera) y devuelve el contenido y su nombre. */
async function requestFile(path: string, body: unknown): Promise<{ blob: Blob; nombre: string }> {
  let res: Response;
  try {
    res = await fetch(API_BASE + path, {
      method: "POST",
      headers: { "Content-Type": "application/json", "x-tcv-token": memoryToken },
      body: JSON.stringify(body),
    });
  } catch {
    throw new ApiError("No se pudo conectar con el servicio local. ¿Está en ejecución?", 0);
  }
  if (!res.ok) {
    const j = await res.json().catch(() => null);
    throw new ApiError(typeof j?.detail === "string" ? j.detail : `No se pudo generar el archivo (${res.status}).`, res.status);
  }
  const nombre = /filename="([^"]+)"/.exec(res.headers.get("content-disposition") ?? "")?.[1] ?? "curriculum";
  return { blob: await res.blob(), nombre };
}

export const exportacion = {
  plantillas: () => request<Plantilla[]>("/api/plantillas"),
  informe: (perfilId: string) => request<Informe>(`/api/perfiles/${encodeURIComponent(perfilId)}/curriculum`),
  exportar: (perfilId: string, plantilla: string, formato: "docx" | "pdf", papel: "carta" | "a4") =>
    requestFile(`/api/perfiles/${encodeURIComponent(perfilId)}/exportar`, { plantilla, formato, papel }),
};

export const redaccion = {
  redactar: (perfilId: string, puestoObjetivo: string | null) =>
    request<Tarea>(`/api/perfiles/${encodeURIComponent(perfilId)}/redaccion`, {
      method: "POST",
      body: JSON.stringify({ puesto_objetivo: puestoObjetivo }),
    }),
  borradores: (perfilId: string) =>
    request<Borrador[]>(`/api/perfiles/${encodeURIComponent(perfilId)}/borradores`),
  actuar: (id: string, accion: "aprobar" | "rechazar" | "restaurar") =>
    request<Borrador>(`/api/borradores/${encodeURIComponent(id)}`, { method: "PATCH", body: JSON.stringify({ accion }) }),
  editar: (id: string, texto: string) =>
    request<Borrador>(`/api/borradores/${encodeURIComponent(id)}`, {
      method: "PATCH",
      body: JSON.stringify({ accion: "editar", texto }),
    }),
  palabrasClave: (perfilId: string, oferta: string) =>
    request<Comparacion>(`/api/perfiles/${encodeURIComponent(perfilId)}/palabras-clave`, {
      method: "POST",
      body: JSON.stringify({ oferta }),
    }),
};

export const entrevista = {
  estado: (perfilId: string) => request<EstadoEntrevista>(`/api/perfiles/${encodeURIComponent(perfilId)}/entrevista`),
  responder: (perfilId: string, preguntaId: string, valores: Record<string, string>) =>
    request<EstadoEntrevista>(`/api/perfiles/${encodeURIComponent(perfilId)}/entrevista/responder`, {
      method: "POST",
      body: JSON.stringify({ pregunta_id: preguntaId, valores }),
    }),
  omitir: (perfilId: string, preguntaId: string) =>
    request<EstadoEntrevista>(`/api/perfiles/${encodeURIComponent(perfilId)}/entrevista/omitir`, {
      method: "POST",
      body: JSON.stringify({ pregunta_id: preguntaId }),
    }),
  reiniciar: (perfilId: string) =>
    request<EstadoEntrevista>(`/api/perfiles/${encodeURIComponent(perfilId)}/entrevista/reiniciar`, {
      method: "POST",
    }),
};

export type AccionDato ="confirmar" | "rechazar" | "restaurar";

export const revision = {
  actuar: (id: string, accion: AccionDato) =>
    request<Hecho>(`/api/hechos/${encodeURIComponent(id)}`, { method: "PATCH", body: JSON.stringify({ accion }) }),
  editar: (id: string, datos: HechoDatos) =>
    request<Hecho>(`/api/hechos/${encodeURIComponent(id)}`, {
      method: "PATCH",
      body: JSON.stringify({ accion: "editar", datos }),
    }),
  agregar: (perfilId: string, categoria: Categoria, datos: HechoDatos) =>
    request<Hecho>(`/api/perfiles/${encodeURIComponent(perfilId)}/hechos`, {
      method: "POST",
      body: JSON.stringify({ categoria, datos }),
    }),
  lote: (perfilId: string, ids: string[], accion: AccionDato) =>
    request<{ actualizados: number; ignorados: number }>(
      `/api/perfiles/${encodeURIComponent(perfilId)}/hechos/lote`,
      { method: "POST", body: JSON.stringify({ ids, accion }) },
    ),
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
