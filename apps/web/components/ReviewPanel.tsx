"use client";

import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { useCallback, useEffect, useState } from "react";
import { type AccionDato, ApiError, documentos, initToken, revision } from "@/lib/api";
import type { Categoria, Hecho, HechoDatos } from "@/lib/types";
import { CATEGORIAS, FactForm, HechoCard, resumen } from "./hechos";
import { btnPrimary, btnSecondary, cardClass, inputClass } from "./ui";

type Filtro = "pendiente" | "aprobado" | "rechazado" | "todos";

const FILTROS: [Filtro, string][] = [
  ["pendiente", "Por revisar"],
  ["aprobado", "Aprobados"],
  ["rechazado", "Rechazados"],
  ["todos", "Todos"],
];

const esAprobado = (h: Hecho) => h.status === "confirmado" || h.status === "editado";
const sinAvisos = (h: Hecho) => h.status === "pendiente" && !h.from_ocr && h.dropped_fields.length === 0;

export function ReviewPanel() {
  const perfilId = useSearchParams().get("perfil");
  const [nombrePerfil, setNombrePerfil] = useState("");
  const [hechos, setHechos] = useState<Hecho[] | null>(null);
  const [nombresDoc, setNombresDoc] = useState<Record<string, string>>({});
  const [filtro, setFiltro] = useState<Filtro>("pendiente");
  const [seleccion, setSeleccion] = useState<Set<string>>(new Set());
  const [editando, setEditando] = useState<string | null>(null);
  const [nueva, setNueva] = useState<Categoria>("experiencia");
  const [error, setError] = useState<string | null>(null);
  const [aviso, setAviso] = useState("");

  const mensaje = (e: unknown) => (e instanceof ApiError ? e.message : "Error inesperado.");

  const cargar = useCallback(async () => {
    if (!perfilId) return;
    try {
      const [h, d] = await Promise.all([documentos.hechos(perfilId), documentos.listar(perfilId)]);
      setHechos(h);
      setNombresDoc(Object.fromEntries(d.map((x) => [x.id, x.nombre])));
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
    void cargar();
  }, [perfilId, cargar]);

  const reemplazar = (nuevo: Hecho) =>
    setHechos((hs) => (hs ? hs.map((h) => (h.id === nuevo.id ? nuevo : h)) : hs));

  async function actuar(h: Hecho, accion: AccionDato) {
    setError(null);
    try {
      reemplazar(await revision.actuar(h.id, accion));
      setSeleccion((s) => {
        const n = new Set(s);
        n.delete(h.id);
        return n;
      });
      const texto = { confirmar: "confirmado", rechazar: "rechazado", restaurar: "devuelto a pendientes" }[accion];
      setAviso(`«${resumen(h)}» quedó ${texto}.`);
    } catch (e) {
      setError(mensaje(e));
    }
  }

  async function guardarEdicion(h: Hecho, datos: HechoDatos) {
    reemplazar(await revision.editar(h.id, datos)); // los errores los muestra el formulario
    setEditando(null);
    setAviso(`Se guardaron tus cambios en «${resumen(h)}».`);
  }

  async function agregar(datos: HechoDatos) {
    if (!perfilId) return;
    const nuevoHecho = await revision.agregar(perfilId, nueva, datos);
    setHechos((hs) => [...(hs ?? []), nuevoHecho]);
    setAviso(`Se agregó «${resumen(nuevoHecho)}» a tu información aprobada.`);
    setFiltro("aprobado");
  }

  async function lote(accion: AccionDato) {
    if (!perfilId || seleccion.size === 0) return;
    setError(null);
    try {
      const r = await revision.lote(perfilId, [...seleccion], accion);
      setAviso(`${r.actualizados} datos ${accion === "confirmar" ? "confirmados" : "rechazados"}.`);
      setSeleccion(new Set());
      await cargar();
    } catch (e) {
      setError(mensaje(e));
    }
  }

  const todos = hechos ?? [];
  const cuenta = {
    pendiente: todos.filter((h) => h.status === "pendiente").length,
    aprobado: todos.filter(esAprobado).length,
    rechazado: todos.filter((h) => h.status === "rechazado").length,
    todos: todos.length,
  };
  const visibles = todos.filter((h) =>
    filtro === "todos" ? true : filtro === "aprobado" ? esAprobado(h) : h.status === filtro,
  );
  const grupos = (Object.keys(CATEGORIAS) as Categoria[])
    .map((c) => [c, visibles.filter((h) => h.category === c)] as const)
    .filter(([, hs]) => hs.length > 0);
  const nombreDoc = (h: Hecho) => (h.document_id ? (nombresDoc[h.document_id] ?? "documento") : null);

  return (
    <section aria-labelledby="titulo-rev" className="space-y-6">
      <div>
        <Link href={perfilId ? `/documentos/?perfil=${encodeURIComponent(perfilId)}` : "/"} className="text-sm underline">
          ← Volver a los documentos
        </Link>
        <h1 id="titulo-rev" className="mt-2 text-2xl font-semibold">
          Revisar datos{nombrePerfil ? ` de ${nombrePerfil}` : ""}
        </h1>
        <p className="mt-1 text-muted">
          Solo la información que apruebes aquí se usará en tu currículum. Compara cada dato con su cita del documento,
          corrígelo si hace falta o recházalo.
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

      <div role="group" aria-label="Filtrar datos" className="flex flex-wrap gap-2">
        {FILTROS.map(([f, etiqueta]) => (
          <button
            key={f}
            type="button"
            aria-pressed={filtro === f}
            onClick={() => setFiltro(f)}
            className={`${btnSecondary} ${filtro === f ? "ring-2 ring-primary" : ""}`}
          >
            {etiqueta} ({cuenta[f]})
          </button>
        ))}
      </div>

      {filtro === "pendiente" && cuenta.pendiente > 0 && (
        <div className={`${cardClass} flex flex-wrap items-center gap-2`}>
          <span className="mr-2 text-sm">{seleccion.size} seleccionados</span>
          <button
            type="button"
            className={btnSecondary}
            onClick={() => setSeleccion(new Set(visibles.filter(sinAvisos).map((h) => h.id)))}
          >
            Seleccionar los que no tienen avisos
          </button>
          <button type="button" className={btnSecondary} onClick={() => setSeleccion(new Set())} disabled={seleccion.size === 0}>
            Quitar selección
          </button>
          <button type="button" className={btnPrimary} onClick={() => lote("confirmar")} disabled={seleccion.size === 0}>
            Confirmar seleccionados
          </button>
          <button type="button" className={btnSecondary} onClick={() => lote("rechazar")} disabled={seleccion.size === 0}>
            Rechazar seleccionados
          </button>
        </div>
      )}

      {hechos === null && !error && <p className="text-muted">Cargando datos…</p>}
      {hechos && visibles.length === 0 && (
        <div className={`${cardClass} text-center`}>
          <p className="font-medium">
            {filtro === "pendiente" ? "No tienes datos por revisar." : "No hay datos en esta vista."}
          </p>
          {filtro === "pendiente" && (
            <p className="mt-1 text-muted">
              Sube un documento y extrae sus datos, o agrega uno propio más abajo.
            </p>
          )}
        </div>
      )}

      {grupos.map(([cat, hs]) => (
        <section key={cat} aria-labelledby={`cat-${cat}`}>
          <h2 id={`cat-${cat}`} className="mb-2 text-lg font-medium">
            {CATEGORIAS[cat]} ({hs.length})
          </h2>
          <ul className="space-y-3">
            {hs.map((h) =>
              editando === h.id ? (
                <li key={h.id} className={cardClass}>
                  <h3 className="mb-3 font-medium">Editar: {resumen(h)}</h3>
                  {h.origin === "documento" && (
                    <blockquote className="mb-3 border-l-4 border-border pl-3 text-sm italic text-muted">«{h.quote}»</blockquote>
                  )}
                  <FactForm
                    categoria={h.category}
                    idBase={`ed-${h.id}`}
                    inicial={h.data}
                    etiquetaGuardar="Guardar cambios"
                    onSubmit={(datos) => guardarEdicion(h, datos)}
                    onCancel={() => setEditando(null)}
                  />
                </li>
              ) : (
                <HechoCard
                  key={h.id}
                  h={h}
                  nombreDoc={nombreDoc(h)}
                  seleccion={
                    h.status === "pendiente"
                      ? {
                          marcado: seleccion.has(h.id),
                          onChange: (v) =>
                            setSeleccion((s) => {
                              const n = new Set(s);
                              if (v) n.add(h.id);
                              else n.delete(h.id);
                              return n;
                            }),
                        }
                      : undefined
                  }
                >
                  {h.status === "pendiente" && (
                    <button type="button" className={btnPrimary} onClick={() => actuar(h, "confirmar")} aria-label={`Confirmar: ${resumen(h)}`}>
                      Confirmar
                    </button>
                  )}
                  {h.status !== "rechazado" && (
                    <button type="button" className={btnSecondary} onClick={() => setEditando(h.id)} aria-label={`Editar: ${resumen(h)}`}>
                      Editar
                    </button>
                  )}
                  {h.status !== "rechazado" ? (
                    <button type="button" className={btnSecondary} onClick={() => actuar(h, "rechazar")} aria-label={`Rechazar: ${resumen(h)}`}>
                      Rechazar
                    </button>
                  ) : (
                    <button type="button" className={btnSecondary} onClick={() => actuar(h, "restaurar")} aria-label={`Restaurar: ${resumen(h)}`}>
                      Volver a pendientes
                    </button>
                  )}
                </HechoCard>
              ),
            )}
          </ul>
        </section>
      ))}

      <details className={cardClass}>
        <summary className="cursor-pointer py-1 font-medium">Agregar un dato que no está en mis documentos</summary>
        <div className="mt-4 space-y-3">
          <p className="text-sm text-muted">
            Lo que escribas aquí queda aprobado de inmediato, porque lo afirmas tú. Escribe solo información verdadera.
          </p>
          <div>
            <label htmlFor="nueva-categoria" className="mb-1 block text-sm font-medium">
              ¿Qué tipo de dato es?
            </label>
            <select
              id="nueva-categoria"
              className={inputClass}
              value={nueva}
              onChange={(e) => setNueva(e.target.value as Categoria)}
            >
              {(Object.keys(CATEGORIAS) as Categoria[]).map((c) => (
                <option key={c} value={c}>
                  {CATEGORIAS[c]}
                </option>
              ))}
            </select>
          </div>
          <FactForm key={nueva} categoria={nueva} idBase="nuevo" etiquetaGuardar="Agregar dato" onSubmit={agregar} />
        </div>
      </details>
    </section>
  );
}
