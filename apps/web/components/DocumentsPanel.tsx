"use client";

import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { useCallback, useEffect, useRef, useState } from "react";
import { ApiError, documentos, ia, initToken } from "@/lib/api";
import type { Documento, Hecho, Tarea } from "@/lib/types";
import { ConfirmDialog } from "./ConfirmDialog";
import { btnPrimary, btnSecondary, cardClass } from "./ui";

const ACTIVAS = ["en_cola", "ejecutando"];
const TIPOS: Record<string, string> = { pdf: "PDF", docx: "Word (DOCX)", image: "Imagen" };

type Seguida = { docId: string; kind: "lectura" | "extraccion"; tarea: Tarea };

const kb = (n: number) => (n >= 1048576 ? `${(n / 1048576).toFixed(1)} MB` : `${Math.max(1, Math.round(n / 1024))} KB`);

function TextoLeido({ docId }: { docId: string }) {
  const [paginas, setPaginas] = useState<string[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  return (
    <details
      className="mt-3 text-sm"
      onToggle={(e) => {
        if ((e.currentTarget as HTMLDetailsElement).open && paginas === null) {
          documentos
            .texto(docId)
            .then((d) => setPaginas(d.paginas))
            .catch((err) => setError(err instanceof ApiError ? err.message : "Error inesperado."));
        }
      }}
    >
      <summary className="cursor-pointer py-2">Ver el texto leído</summary>
      {error && <p className="text-danger">{error}</p>}
      {paginas?.map((p, i) => (
        <div key={i} className="mt-2">
          <p className="text-xs font-medium text-muted">Página {i + 1}</p>
          <pre className="mt-1 max-h-64 overflow-auto whitespace-pre-wrap rounded bg-background p-3 text-xs ring-1 ring-border">
            {p}
          </pre>
        </div>
      ))}
    </details>
  );
}

export function DocumentsPanel() {
  const perfilId = useSearchParams().get("perfil");
  const [nombrePerfil, setNombrePerfil] = useState("");
  const [docs, setDocs] = useState<Documento[]>([]);
  const [hechos, setHechos] = useState<Hecho[]>([]);
  const [seguidas, setSeguidas] = useState<Record<string, Seguida>>({});
  const [error, setError] = useState<string | null>(null);
  const [aviso, setAviso] = useState("");
  const [subiendo, setSubiendo] = useState(false);
  const [aEliminar, setAEliminar] = useState<Documento | null>(null);
  const [eliminando, setEliminando] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);

  const mensaje = (e: unknown) => (e instanceof ApiError ? e.message : "Error inesperado.");

  const recargar = useCallback(async () => {
    if (!perfilId) return;
    try {
      const [d, h] = await Promise.all([documentos.listar(perfilId), documentos.hechos(perfilId)]);
      setDocs(d);
      setHechos(h);
    } catch (e) {
      setError(mensaje(e));
    }
  }, [perfilId]);

  useEffect(() => {
    if (!initToken()) {
      // eslint-disable-next-line react-hooks/set-state-in-effect
      setError("No hay sesión activa. Abre TalentCV AI desde su acceso directo.");
      return;
    }
    if (!perfilId) {
      setError("Falta indicar el perfil. Vuelve a la lista de perfiles.");
      return;
    }
    documentos.perfil(perfilId).then((p) => setNombrePerfil(p.nombre_completo)).catch((e) => setError(mensaje(e)));
    void recargar();
  }, [perfilId, recargar]);

  // Consulta el avance de las tareas activas cada 1,5 s.
  const hayActivas = Object.values(seguidas).some((s) => ACTIVAS.includes(s.tarea.estado));
  useEffect(() => {
    if (!hayActivas) return;
    const t = setInterval(async () => {
      const actuales = Object.entries(seguidas).filter(([, s]) => ACTIVAS.includes(s.tarea.estado));
      let termino = false;
      const nuevas: Record<string, Seguida> = {};
      await Promise.all(
        actuales.map(async ([id, s]) => {
          try {
            const tarea = await ia.tarea(id);
            nuevas[id] = { ...s, tarea };
            if (!ACTIVAS.includes(tarea.estado)) termino = true;
          } catch (e) {
            setError(mensaje(e));
          }
        }),
      );
      setSeguidas((prev) => ({ ...prev, ...nuevas }));
      if (termino) void recargar();
    }, 1500);
    return () => clearInterval(t);
  }, [hayActivas, seguidas, recargar]);

  async function subir(file: File) {
    if (!perfilId) return;
    setError(null);
    setAviso("");
    setSubiendo(true);
    try {
      const r = await documentos.subir(perfilId, file);
      setSeguidas((s) => ({ ...s, [r.tarea.id]: { docId: r.documento.id, kind: "lectura", tarea: r.tarea } }));
      setAviso(`Se subió «${r.documento.nombre}». Estoy leyendo su texto…`);
      await recargar();
    } catch (e) {
      setError(mensaje(e));
    } finally {
      setSubiendo(false);
      if (inputRef.current) inputRef.current.value = "";
    }
  }

  async function extraer(d: Documento) {
    setError(null);
    try {
      const tarea = await documentos.extraer(d.id);
      setSeguidas((s) => ({ ...s, [tarea.id]: { docId: d.id, kind: "extraccion", tarea } }));
    } catch (e) {
      setError(mensaje(e));
    }
  }

  async function cancelar(tareaId: string) {
    try {
      const tarea = await ia.cancelar(tareaId);
      setSeguidas((s) => ({ ...s, [tareaId]: { ...s[tareaId], tarea } }));
      await recargar();
    } catch (e) {
      setError(mensaje(e));
    }
  }

  async function confirmarEliminar() {
    if (!aEliminar) return;
    setEliminando(true);
    try {
      await documentos.eliminar(aEliminar.id);
      setAviso(`Se eliminó «${aEliminar.nombre}». Los datos que ya habías aprobado se conservan.`);
      setAEliminar(null);
      await recargar();
    } catch (e) {
      setAEliminar(null);
      setError(mensaje(e));
    } finally {
      setEliminando(false);
    }
  }

  const tareaDe = (docId: string, kind: Seguida["kind"]) =>
    Object.values(seguidas).filter((s) => s.docId === docId && s.kind === kind).at(-1)?.tarea;

  return (
    <section aria-labelledby="titulo-docs" className="space-y-6">
      <div>
        <Link href="/" className="text-sm underline">
          ← Volver a los perfiles
        </Link>
        <h1 id="titulo-docs" className="mt-2 text-2xl font-semibold">
          Documentos{nombrePerfil ? ` de ${nombrePerfil}` : ""}
        </h1>
        <p className="mt-1 text-muted">
          Sube tu currículum o tus certificados. Todo se procesa en este equipo. Los datos que se detecten quedan{" "}
          <strong>pendientes de confirmar</strong>: nada se usa hasta que tú lo apruebes.
        </p>
      </div>

      {error && (
        <div role="alert" className="rounded-md bg-danger-bg p-3 text-danger">
          {error}
        </div>
      )}
      <p role="status" aria-live="polite" className={aviso ? "rounded-md bg-success-bg p-3 text-success" : "sr-only"}>
        {aviso}
      </p>

      <div className={cardClass}>
        <label htmlFor="archivo" className="block text-sm font-medium">
          Subir un documento (PDF, DOCX, PNG o JPG; máximo 20 MB)
        </label>
        <input
          ref={inputRef}
          id="archivo"
          type="file"
          accept=".pdf,.docx,.png,.jpg,.jpeg,application/pdf,image/png,image/jpeg"
          disabled={subiendo || !perfilId}
          onChange={(e) => e.target.files?.[0] && subir(e.target.files[0])}
          className="mt-2 block min-h-11 w-full text-sm file:mr-3 file:min-h-11 file:cursor-pointer file:rounded-md file:border-0 file:bg-primary file:px-4 file:py-2 file:text-primary-fg"
        />
        {subiendo && <p className="mt-2 text-sm text-muted">Subiendo…</p>}
      </div>

      {docs.length === 0 && perfilId && !error && <p className="text-muted">Todavía no hay documentos en este perfil.</p>}

      <ul className="space-y-3">
        {docs.map((d) => {
          const lectura = tareaDe(d.id, "lectura");
          const extraccion = tareaDe(d.id, "extraccion");
          const leyendo = d.estado === "subido" && lectura && ACTIVAS.includes(lectura.estado);
          const extrayendo = extraccion && ACTIVAS.includes(extraccion.estado);
          return (
            <li key={d.id} className={cardClass}>
              <div className="flex flex-wrap items-start justify-between gap-3">
                <div className="min-w-0">
                  <h2 className="truncate text-lg font-medium">{d.nombre}</h2>
                  <p className="text-sm text-muted">
                    {TIPOS[d.tipo]} · {kb(d.tamano)}
                    {d.estado === "leido" && ` · ${d.paginas} ${d.paginas === 1 ? "página" : "páginas"}`}
                    {d.paginas_ocr.length > 0 && ` · OCR en ${d.paginas_ocr.length === 1 ? "la página" : "las páginas"} ${d.paginas_ocr.join(", ")}`}
                  </p>
                </div>
                <div className="flex flex-wrap gap-2">
                  {d.estado === "leido" && (
                    <button type="button" className={btnPrimary} onClick={() => extraer(d)} disabled={Boolean(extrayendo)}>
                      Extraer datos
                    </button>
                  )}
                  <button
                    type="button"
                    className={btnSecondary}
                    onClick={() => setAEliminar(d)}
                    aria-label={`Eliminar ${d.nombre}`}
                  >
                    Eliminar
                  </button>
                </div>
              </div>

              {d.estado === "subido" && !leyendo && <p className="mt-2 text-sm text-muted">Pendiente de lectura.</p>}
              {d.estado === "error" && (
                <p role="alert" className="mt-3 rounded-md bg-danger-bg p-3 text-sm text-danger">
                  {d.error ?? "No se pudo leer el documento."}
                </p>
              )}

              {[
                [leyendo ? lectura : undefined, "Leyendo el documento"],
                [extrayendo ? extraccion : undefined, "Extrayendo datos con la IA"],
              ].map(([t, titulo]) => {
                const tarea = t as Tarea | undefined;
                if (!tarea) return null;
                const pct = Math.round(tarea.progreso * 100);
                return (
                  <div key={tarea.id} className="mt-3" aria-live="polite">
                    <p className="text-sm">
                      {titulo as string}: {tarea.mensaje}
                    </p>
                    <div
                      role="progressbar"
                      aria-label={titulo as string}
                      aria-valuemin={0}
                      aria-valuemax={100}
                      aria-valuenow={pct}
                      className="mt-1 h-3 w-full overflow-hidden rounded-full bg-border"
                    >
                      <div className="h-full bg-primary transition-[width]" style={{ width: `${pct}%` }} />
                    </div>
                    <button type="button" className={`${btnSecondary} mt-2`} onClick={() => cancelar(tarea.id)}>
                      Cancelar
                    </button>
                  </div>
                );
              })}

              {extraccion?.estado === "error" && (
                <p role="alert" className="mt-3 rounded-md bg-danger-bg p-3 text-sm text-danger">
                  {extraccion.error}
                </p>
              )}
              {extraccion?.estado === "completado" && extraccion.resultado && (
                <p className="mt-3 rounded-md bg-success-bg p-3 text-sm text-success">
                  Se encontraron {String(extraccion.resultado.hechos)} datos para revisar.
                  {Number(extraccion.resultado.descartados) > 0 &&
                    ` Se descartaron ${String(extraccion.resultado.descartados)} porque no estaban respaldados por el texto del documento.`}
                </p>
              )}

              {d.estado === "leido" && <TextoLeido docId={d.id} />}
            </li>
          );
        })}
      </ul>

      {hechos.length > 0 && perfilId && (
        <div className={cardClass}>
          <h2 className="text-lg font-medium">Datos encontrados</h2>
          <p className="mt-1 text-sm">
            {hechos.length} {hechos.length === 1 ? "dato" : "datos"} en total:{" "}
            <strong>{hechos.filter((h) => h.status === "pendiente").length} por revisar</strong>,{" "}
            {hechos.filter((h) => h.status === "confirmado" || h.status === "editado").length} aprobados,{" "}
            {hechos.filter((h) => h.status === "rechazado").length} rechazados.
          </p>
          <Link href={`/revision/?perfil=${encodeURIComponent(perfilId)}`} className={`${btnPrimary} mt-3`}>
            Revisar y confirmar datos
          </Link>
        </div>
      )}

      <ConfirmDialog
        open={aEliminar !== null}
        title="¿Eliminar este documento?"
        description={`Se borrará «${aEliminar?.nombre ?? ""}» de este equipo y los datos extraídos de él que aún no hayas aprobado. Lo que ya confirmaste se conserva. Esta acción no se puede deshacer.`}
        confirmLabel="Eliminar"
        busy={eliminando}
        onConfirm={confirmarEliminar}
        onCancel={() => setAEliminar(null)}
      />
    </section>
  );
}
