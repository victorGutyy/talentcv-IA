"use client";

import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { useCallback, useEffect, useState } from "react";
import { ApiError, documentos, exportacion, initToken, versiones } from "@/lib/api";
import { descargarBlob } from "@/lib/download";
import type { ComparacionVersiones, Plantilla, Version, VersionDetalle } from "@/lib/types";
import { ConfirmDialog } from "./ConfirmDialog";
import { HojaCv } from "./HojaCv";
import { btnPrimary, btnSecondary, cardClass, inputClass } from "./ui";

const mensaje = (e: unknown) => (e instanceof ApiError ? e.message : "Error inesperado.");
const fecha = (iso: string) => new Date(iso).toLocaleString("es", { dateStyle: "medium", timeStyle: "short" });
const FORMATO = { docx: "Word", pdf: "PDF" } as Record<string, string>;

const TIPO_CAMBIO = {
  agregado: { simbolo: "＋", texto: "Agregado", clase: "text-success" },
  quitado: { simbolo: "−", texto: "Quitado", clase: "text-danger" },
  cambiado: { simbolo: "↻", texto: "Cambiado", clase: "text-foreground" },
} as const;

function Comparacion({ c }: { c: ComparacionVersiones }) {
  const secciones = [...new Set(c.cambios.map((x) => x.seccion))];
  return (
    <div className={`${cardClass} space-y-3`} aria-live="polite">
      <h2 className="text-lg font-medium">
        Cambios de «{c.antes}» a «{c.despues}»
      </h2>
      {c.iguales && <p className="text-muted">No hay diferencias: el contenido es idéntico.</p>}
      {secciones.map((s) => (
        <section key={s} aria-label={s}>
          <h3 className="text-sm font-semibold">{s}</h3>
          <ul className="mt-1 space-y-1 text-sm">
            {c.cambios
              .filter((x) => x.seccion === s)
              .map((x, i) => {
                const t = TIPO_CAMBIO[x.tipo];
                return (
                  <li key={i} className={t.clase}>
                    <span aria-hidden="true">{t.simbolo} </span>
                    <span className="sr-only">{t.texto}: </span>
                    {x.tipo === "cambiado" ? (
                      <>
                        <del className="opacity-70">{x.antes}</del> → <ins className="no-underline">{x.despues}</ins>
                      </>
                    ) : (
                      (x.antes ?? x.despues)
                    )}
                  </li>
                );
              })}
          </ul>
        </section>
      ))}
    </div>
  );
}

export function VersionsPanel() {
  const perfilId = useSearchParams().get("perfil");
  const [nombrePerfil, setNombrePerfil] = useState("");
  const [lista, setLista] = useState<Version[] | null>(null);
  const [plantillas, setPlantillas] = useState<Plantilla[]>([]);
  const [abierta, setAbierta] = useState<VersionDetalle | null>(null);
  const [comparacion, setComparacion] = useState<ComparacionVersiones | null>(null);
  const [etiqueta, setEtiqueta] = useState("");
  const [editando, setEditando] = useState<string | null>(null);
  const [etiquetaEdit, setEtiquetaEdit] = useState("");
  const [descargando, setDescargando] = useState<string | null>(null);
  const [opc, setOpc] = useState({ plantilla: "ats", formato: "docx" as "docx" | "pdf", papel: "carta" as "carta" | "a4" });
  const [aEliminar, setAEliminar] = useState<Version | null>(null);
  const [eliminando, setEliminando] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [aviso, setAviso] = useState("");

  const recargar = useCallback(async () => {
    if (!perfilId) return;
    try {
      setLista(await versiones.listar(perfilId));
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
    exportacion.plantillas().then(setPlantillas).catch((e) => setError(mensaje(e)));
    void recargar();
  }, [perfilId, recargar]);

  async function guardar(e: React.FormEvent) {
    e.preventDefault();
    if (!perfilId) return;
    setError(null);
    try {
      const r = await versiones.guardar(perfilId, etiqueta.trim() || null);
      setAviso(
        r.creada
          ? `Se guardó la versión ${r.version.numero}.`
          : `Tu información no ha cambiado desde la versión ${r.version.numero}; no se creó una nueva.`,
      );
      setEtiqueta("");
      await recargar();
    } catch (err) {
      setError(err instanceof ApiError && err.fields.etiqueta ? err.fields.etiqueta : mensaje(err));
    }
  }

  async function ver(v: Version) {
    setError(null);
    if (abierta?.id === v.id) {
      setAbierta(null);
      return;
    }
    try {
      setAbierta(await versiones.ver(v.id));
    } catch (e) {
      setError(mensaje(e));
    }
  }

  async function comparar(antes: Version, con: string) {
    setError(null);
    try {
      setComparacion(await versiones.comparar(antes.id, con));
    } catch (e) {
      setError(mensaje(e));
    }
  }

  async function guardarEtiqueta(v: Version) {
    try {
      await versiones.renombrar(v.id, etiquetaEdit.trim() || null);
      setEditando(null);
      setAviso(`Etiqueta de la versión ${v.numero} actualizada.`);
      await recargar();
    } catch (e) {
      setError(mensaje(e));
    }
  }

  async function descargar(v: Version) {
    setError(null);
    try {
      const { blob, nombre } = await versiones.exportar(v.id, opc.plantilla, opc.formato, opc.papel);
      descargarBlob(blob, nombre);
      setAviso(`Se generó «${nombre}» con el contenido exacto de la versión ${v.numero}.`);
      setDescargando(null);
      await recargar();
    } catch (e) {
      setError(mensaje(e));
    }
  }

  async function confirmarEliminar() {
    if (!aEliminar) return;
    setEliminando(true);
    try {
      await versiones.eliminar(aEliminar.id);
      setAviso(`Se eliminó la versión ${aEliminar.numero}.`);
      if (abierta?.id === aEliminar.id) setAbierta(null);
      setComparacion(null);
      setAEliminar(null);
      await recargar();
    } catch (e) {
      setAEliminar(null);
      setError(mensaje(e));
    } finally {
      setEliminando(false);
    }
  }

  const plantillaVista = plantillas.find((p) => p.id === "ats");

  return (
    <section aria-labelledby="titulo-ver" className="space-y-6">
      <div>
        <Link href="/" className="text-sm underline">
          ← Volver a los perfiles
        </Link>
        <h1 id="titulo-ver" className="mt-2 text-2xl font-semibold">
          Historial de versiones{nombrePerfil ? ` de ${nombrePerfil}` : ""}
        </h1>
        <p className="mt-1 text-muted">
          Cada vez que descargas tu currículum se guarda una copia exacta de su contenido, solo en este equipo. Puedes
          ver cualquier versión, compararla y volver a descargarla tal como era, aunque tus datos hayan cambiado.
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

      <form onSubmit={guardar} className={`${cardClass} space-y-2`}>
        <label htmlFor="etiqueta-nueva" className="block text-sm font-medium">
          Guardar una versión ahora (opcional: ponle un nombre)
        </label>
        <div className="flex flex-wrap gap-3">
          <input
            id="etiqueta-nueva"
            className={`${inputClass} max-w-md flex-1`}
            value={etiqueta}
            maxLength={80}
            placeholder="Por ejemplo: Para la entrevista de Tecnosur"
            onChange={(e) => setEtiqueta(e.target.value)}
          />
          <button type="submit" className={btnPrimary}>
            Guardar versión
          </button>
        </div>
      </form>

      {comparacion && <Comparacion c={comparacion} />}

      {lista === null && !error && <p className="text-muted">Cargando versiones…</p>}
      {lista?.length === 0 && (
        <div className={`${cardClass} text-center`}>
          <p className="font-medium">Todavía no hay versiones.</p>
          <p className="mt-1 text-muted">Descarga tu currículum o guarda una versión para empezar el historial.</p>
        </div>
      )}

      <ul className="space-y-3">
        {lista?.map((v, i) => {
          const anterior = lista[i + 1];
          const formatos = [...new Set(v.exportaciones.map((e) => `${plantillas.find((p) => p.id === e.plantilla)?.nombre ?? e.plantilla} · ${FORMATO[e.formato] ?? e.formato}`))];
          return (
            <li key={v.id} className={cardClass}>
              <div className="flex flex-wrap items-start justify-between gap-2">
                <div className="min-w-0">
                  <h2 className="text-lg font-medium">
                    Versión {v.numero}
                    {i === 0 && <span className="ml-2 rounded bg-background px-2 py-0.5 text-xs ring-1 ring-border">La más reciente</span>}
                  </h2>
                  {editando === v.id ? (
                    <form
                      className="mt-1 flex flex-wrap gap-2"
                      onSubmit={(e) => {
                        e.preventDefault();
                        void guardarEtiqueta(v);
                      }}
                    >
                      <label htmlFor={`et-${v.id}`} className="sr-only">
                        Etiqueta de la versión {v.numero}
                      </label>
                      <input id={`et-${v.id}`} className={`${inputClass} max-w-sm`} value={etiquetaEdit} maxLength={80} onChange={(e) => setEtiquetaEdit(e.target.value)} />
                      <button type="submit" className={btnPrimary}>
                        Guardar
                      </button>
                      <button type="button" className={btnSecondary} onClick={() => setEditando(null)}>
                        Cancelar
                      </button>
                    </form>
                  ) : (
                    v.etiqueta && <p className="font-medium">{v.etiqueta}</p>
                  )}
                  <p className="text-sm text-muted">
                    {fecha(v.creada_en)} · {v.origen === "manual" ? "Guardada a mano" : "Creada al descargar"} ·{" "}
                    {v.contenido.puestos} {v.contenido.puestos === 1 ? "puesto" : "puestos"}, {v.contenido.puntos}{" "}
                    {v.contenido.puntos === 1 ? "punto" : "puntos"}, {v.contenido.habilidades} habilidades
                    {v.contenido.tiene_resumen ? ", con resumen" : ", sin resumen"}
                  </p>
                  {formatos.length > 0 && <p className="text-xs text-muted">Descargada como: {formatos.join(", ")}</p>}
                </div>
              </div>

              <div className="mt-3 flex flex-wrap gap-2">
                <button type="button" className={btnSecondary} aria-expanded={abierta?.id === v.id} onClick={() => ver(v)} aria-label={`${abierta?.id === v.id ? "Ocultar" : "Ver"} el contenido de la versión ${v.numero}`}>
                  {abierta?.id === v.id ? "Ocultar contenido" : "Ver contenido"}
                </button>
                <button type="button" className={btnSecondary} onClick={() => comparar(v, "actual")} aria-label={`Comparar la versión ${v.numero} con el estado actual`}>
                  Comparar con lo actual
                </button>
                {anterior && (
                  <button type="button" className={btnSecondary} onClick={() => comparar(anterior, v.id)} aria-label={`Ver qué cambió en la versión ${v.numero} respecto a la ${anterior.numero}`}>
                    Qué cambió
                  </button>
                )}
                <button type="button" className={btnSecondary} aria-expanded={descargando === v.id} onClick={() => setDescargando(descargando === v.id ? null : v.id)} aria-label={`Descargar la versión ${v.numero}`}>
                  Descargar…
                </button>
                <button type="button" className={btnSecondary} onClick={() => { setEditando(v.id); setEtiquetaEdit(v.etiqueta ?? ""); }} aria-label={`Poner nombre a la versión ${v.numero}`}>
                  Nombre
                </button>
                <button type="button" className={btnSecondary} onClick={() => setAEliminar(v)} aria-label={`Eliminar la versión ${v.numero}`}>
                  Eliminar
                </button>
              </div>

              {descargando === v.id && (
                <div className="mt-3 flex flex-wrap items-end gap-3 border-t border-border pt-3">
                  <div>
                    <label htmlFor={`pl-${v.id}`} className="block text-xs font-medium">
                      Plantilla
                    </label>
                    <select id={`pl-${v.id}`} className={inputClass} value={opc.plantilla} onChange={(e) => setOpc({ ...opc, plantilla: e.target.value })}>
                      {plantillas.map((p) => (
                        <option key={p.id} value={p.id}>
                          {p.nombre}
                        </option>
                      ))}
                    </select>
                  </div>
                  <div>
                    <label htmlFor={`fo-${v.id}`} className="block text-xs font-medium">
                      Formato
                    </label>
                    <select id={`fo-${v.id}`} className={inputClass} value={opc.formato} onChange={(e) => setOpc({ ...opc, formato: e.target.value as "docx" | "pdf" })}>
                      <option value="docx">Word (.docx)</option>
                      <option value="pdf">PDF</option>
                    </select>
                  </div>
                  <div>
                    <label htmlFor={`pa-${v.id}`} className="block text-xs font-medium">
                      Papel
                    </label>
                    <select id={`pa-${v.id}`} className={inputClass} value={opc.papel} onChange={(e) => setOpc({ ...opc, papel: e.target.value as "carta" | "a4" })}>
                      <option value="carta">Carta</option>
                      <option value="a4">A4</option>
                    </select>
                  </div>
                  <button type="button" className={btnPrimary} onClick={() => descargar(v)}>
                    Descargar versión {v.numero}
                  </button>
                </div>
              )}

              {abierta?.id === v.id && plantillaVista && (
                <div className="mt-3 border-t border-border pt-3">
                  <HojaCv cv={abierta.cv} p={plantillaVista} />
                </div>
              )}
            </li>
          );
        })}
      </ul>

      <ConfirmDialog
        open={aEliminar !== null}
        title="¿Eliminar esta versión?"
        description={`Se borrará la versión ${aEliminar?.numero ?? ""} de tu historial en este equipo. Los archivos que ya descargaste no se tocan.`}
        confirmLabel="Eliminar"
        busy={eliminando}
        onConfirm={confirmarEliminar}
        onCancel={() => setAEliminar(null)}
      />
    </section>
  );
}
