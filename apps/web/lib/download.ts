type RespuestaGuardado = { ok: boolean; ruta?: string; cancelado?: boolean; error?: string };

declare global {
  interface Window {
    // Lo inyecta la ventana de escritorio (pywebview). En el navegador normal no existe.
    pywebview?: {
      api?: {
        guardar_archivo?: (nombre: string, base64: string) => Promise<RespuestaGuardado>;
        seleccionar_carpeta?: () => Promise<{ ok: boolean; ruta?: string; cancelado?: boolean; error?: string }>;
      };
    };
  }
}

/** ¿Estamos en la ventana de escritorio, con selector de carpetas? */
export const puedeElegirCarpeta = () => typeof window !== "undefined" && Boolean(window.pywebview?.api?.seleccionar_carpeta);

/** Abre el selector de carpetas de la ventana de escritorio. `null` si se cancela. */
export async function elegirCarpeta(): Promise<{ ruta: string } | { error: string } | null> {
  const elegir = window.pywebview?.api?.seleccionar_carpeta;
  if (!elegir) return { error: "Esta función solo está disponible en la aplicación de escritorio." };
  const r = await elegir();
  if (r.ok && r.ruta) return { ruta: r.ruta };
  return r.cancelado ? null : { error: r.error ?? "No se pudo abrir la carpeta." };
}

export type ResultadoDescarga =
  | { ok: true; ruta: string | null } // ruta: dónde se guardó (solo en la app de escritorio)
  | { ok: false; cancelado: boolean; error?: string };

async function aBase64(blob: Blob): Promise<string> {
  const bytes = new Uint8Array(await blob.arrayBuffer());
  let binario = "";
  for (let i = 0; i < bytes.length; i += 0x8000) binario += String.fromCharCode(...bytes.subarray(i, i + 0x8000));
  return btoa(binario);
}

/**
 * Entrega un archivo generado en memoria al usuario.
 * - En la app de escritorio: abre el diálogo nativo «Guardar como…».
 * - En el navegador: descarga estándar mediante un enlace temporal.
 */
export async function descargarBlob(blob: Blob, nombre: string): Promise<ResultadoDescarga> {
  const guardar = window.pywebview?.api?.guardar_archivo;
  if (guardar) {
    const r = await guardar(nombre, await aBase64(blob));
    return r.ok ? { ok: true, ruta: r.ruta ?? null } : { ok: false, cancelado: Boolean(r.cancelado), error: r.error };
  }
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = nombre;
  document.body.appendChild(a);
  a.click();
  a.remove();
  setTimeout(() => URL.revokeObjectURL(url), 10_000);
  return { ok: true, ruta: null };
}
