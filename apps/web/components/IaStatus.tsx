"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { ApiError, ia, initToken } from "@/lib/api";
import type { EstadoIA, Tarea } from "@/lib/types";
import { btnPrimary, btnSecondary, cardClass } from "./ui";

const ACTIVAS = ["en_cola", "ejecutando"];

const ETIQUETAS: Record<string, string> = {
  extrae_el_nombre: "Extrae el nombre del documento",
  extrae_el_anio: "Extrae el año de inicio",
  no_inventa_la_fecha_de_graduacion: "No inventa un dato que no aparece (fecha de graduación)",
};

const ESTADOS: Record<string, string> = {
  en_cola: "En cola",
  ejecutando: "En curso",
  completado: "Completada",
  error: "Con error",
  cancelado: "Cancelada",
  interrumpido: "Interrumpida",
};

export function IaStatus() {
  const [estado, setEstado] = useState<EstadoIA | null>(null);
  const [tarea, setTarea] = useState<Tarea | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [lanzando, setLanzando] = useState(false);
  const timer = useRef<ReturnType<typeof setInterval> | null>(null);

  const cargarEstado = useCallback(async () => {
    try {
      setEstado(await ia.estado());
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Error inesperado.");
    }
  }, []);

  useEffect(() => {
    if (!initToken()) {
      // eslint-disable-next-line react-hooks/set-state-in-effect
      setError("No hay sesión activa. Abre TalentCV AI desde su acceso directo.");
      return;
    }
    void cargarEstado();
  }, [cargarEstado]);

  // Consulta el progreso cada segundo mientras la tarea siga activa.
  const id = tarea?.id;
  const activa = tarea ? ACTIVAS.includes(tarea.estado) : false;
  useEffect(() => {
    if (!id || !activa) return;
    timer.current = setInterval(async () => {
      try {
        setTarea(await ia.tarea(id));
      } catch (e) {
        setError(e instanceof ApiError ? e.message : "Error inesperado.");
      }
    }, 1000);
    return () => {
      if (timer.current) clearInterval(timer.current);
    };
  }, [id, activa]);

  async function probar() {
    setError(null);
    setLanzando(true);
    try {
      setTarea(await ia.lanzar("diagnostico_ia"));
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Error inesperado.");
    } finally {
      setLanzando(false);
    }
  }

  async function cancelar() {
    if (!tarea) return;
    try {
      setTarea(await ia.cancelar(tarea.id));
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Error inesperado.");
    }
  }

  const pct = Math.round((tarea?.progreso ?? 0) * 100);
  const listo = estado?.disponible && estado.modelo_instalado;

  return (
    <section aria-labelledby="titulo-ia" className="space-y-6">
      <h1 id="titulo-ia" className="text-2xl font-semibold">
        IA local
      </h1>
      <p className="text-muted">
        TalentCV AI usa un modelo que se ejecuta en este equipo. Tus documentos no se envían a ningún servicio externo.
      </p>

      {error && (
        <div role="alert" className="rounded-md bg-danger-bg p-3 text-danger">
          {error}
        </div>
      )}

      <div className={cardClass}>
        <h2 className="text-lg font-medium">Estado del motor</h2>
        {!estado && !error && <p className="mt-2 text-muted">Comprobando…</p>}
        {estado && (
          <dl className="mt-3 grid gap-x-6 gap-y-1 text-sm sm:grid-cols-[auto_1fr]">
            <dt className="text-muted">Estado</dt>
            <dd className={listo ? "font-medium text-success" : "font-medium text-danger"}>
              {listo ? "Listo para usar" : estado.disponible ? "Falta el modelo" : "No disponible"}
            </dd>
            <dt className="text-muted">Motor</dt>
            <dd>
              {estado.proveedor} {estado.version ?? ""}
            </dd>
            <dt className="text-muted">Modelo</dt>
            <dd>
              {estado.modelo} {estado.modelo_instalado ? "(instalado)" : "(no instalado)"}
            </dd>
            <dt className="text-muted">Dirección</dt>
            <dd>{estado.url}</dd>
          </dl>
        )}
        {estado?.error && <p className="mt-3 text-sm text-danger">{estado.error}</p>}
        <div className="mt-4 flex flex-wrap gap-3">
          <button type="button" className={btnPrimary} onClick={probar} disabled={!listo || lanzando || activa}>
            Probar la IA local
          </button>
          <button type="button" className={btnSecondary} onClick={cargarEstado}>
            Volver a comprobar
          </button>
        </div>
        <p className="mt-3 text-sm text-muted">
          La prueba analiza un documento ficticio y verifica que el modelo no invente datos. Puede tardar unos segundos.
        </p>
      </div>

      {tarea && (
        <div className={cardClass} aria-live="polite">
          <h2 className="text-lg font-medium">Prueba de la IA</h2>
          <p className="mt-1 text-sm text-muted">
            {ESTADOS[tarea.estado] ?? tarea.estado}: {tarea.mensaje}
          </p>

          {activa && (
            <>
              <div
                role="progressbar"
                aria-label="Progreso de la prueba"
                aria-valuemin={0}
                aria-valuemax={100}
                aria-valuenow={pct}
                className="mt-3 h-3 w-full overflow-hidden rounded-full bg-border"
              >
                <div className="h-full bg-primary transition-[width]" style={{ width: `${pct}%` }} />
              </div>
              <p className="mt-1 text-sm">{pct} %</p>
              <button type="button" className={`${btnSecondary} mt-3`} onClick={cancelar}>
                Cancelar
              </button>
            </>
          )}

          {tarea.estado === "error" && (
            <p role="alert" className="mt-3 rounded-md bg-danger-bg p-3 text-danger">
              {tarea.error}
            </p>
          )}

          {tarea.estado === "completado" && tarea.resultado && (
            <div className="mt-3 space-y-3">
              <p
                className={
                  tarea.resultado.ok
                    ? "rounded-md bg-success-bg p-3 font-medium text-success"
                    : "rounded-md bg-danger-bg p-3 font-medium text-danger"
                }
              >
                {tarea.resultado.ok
                  ? "✔ La IA local funciona correctamente."
                  : "✖ La IA respondió, pero no pasó todas las verificaciones."}
              </p>
              <ul className="space-y-1 text-sm">
                {Object.entries(tarea.resultado.verificaciones).map(([k, v]) => (
                  <li key={k}>
                    <span aria-hidden="true">{v ? "✔" : "✖"}</span>
                    <span className="sr-only">{v ? "Correcto:" : "Falló:"}</span> {ETIQUETAS[k] ?? k}
                  </li>
                ))}
              </ul>
              <p className="text-sm text-muted">
                Modelo {tarea.resultado.modelo} · {tarea.resultado.tokens_por_segundo} tokens/s ·{" "}
                {tarea.resultado.segundos} s · {tarea.resultado.tokens_entrada} tokens leídos,{" "}
                {tarea.resultado.tokens_salida} generados
              </p>
            </div>
          )}
        </div>
      )}
    </section>
  );
}
