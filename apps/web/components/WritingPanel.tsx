"use client";

import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { useCallback, useEffect, useState } from "react";
import { ApiError, documentos, ia, initToken, redaccion, revision } from "@/lib/api";
import type { Borrador, Comparacion, Hecho, Tarea } from "@/lib/types";
import { btnPrimary, btnSecondary, cardClass, inputClass } from "./ui";

const ACTIVAS = ["en_cola", "ejecutando"];
const MAX_TEXTO = { resumen: 700, logro: 300 } as const;
const mensaje = (e: unknown) => (e instanceof ApiError ? e.message : "Error inesperado.");

const aprobado = (h: Hecho) => h.status === "confirmado" || h.status === "editado";
const etiquetaPuesto = (h: Hecho) =>
  h.data.empresa ? `${String(h.data.cargo)} – ${String(h.data.empresa)}` : String(h.data.cargo);
const norm = (s: string) => s.normalize("NFD").replace(/[̀-ͯ]/g, "").toLowerCase().replace(/[^a-z0-9]+/g, " ").trim();

const ESTADO: Record<Borrador["estado"], string> = { borrador: "Borrador", aprobado: "Aprobado", rechazado: "Rechazado" };

type CardProps = {
  b: Borrador;
  origen?: string; // texto del logro del que sale
  onActuar: (b: Borrador, a: "aprobar" | "rechazar" | "restaurar") => Promise<void>;
  onEditar: (b: Borrador, texto: string) => Promise<void>;
};

function BorradorCard({ b, origen, onActuar, onEditar }: CardProps) {
  const [editando, setEditando] = useState(false);
  const [texto, setTexto] = useState(b.texto);
  const [error, setError] = useState<string | null>(null);
  const [ocupado, setOcupado] = useState(false);
  const bloqueado = b.origen === "ia" && !b.auditoria_ok;
  const max = MAX_TEXTO[b.seccion];

  async function guardar(e: React.FormEvent) {
    e.preventDefault();
    setOcupado(true);
    setError(null);
    try {
      await onEditar(b, texto);
      setEditando(false);
    } catch (err) {
      setError(err instanceof ApiError && err.fields.texto ? err.fields.texto : mensaje(err));
    } finally {
      setOcupado(false);
    }
  }

  return (
    <li className={`${cardClass} ${b.estado === "rechazado" ? "opacity-70" : ""}`}>
      {editando ? (
        <form onSubmit={guardar} noValidate className="space-y-2">
          <label htmlFor={`txt-${b.id}`} className="block text-sm font-medium">
            Edita el texto
          </label>
          <textarea
            id={`txt-${b.id}`}
            className={inputClass}
            rows={b.seccion === "resumen" ? 5 : 3}
            value={texto}
            maxLength={max}
            aria-invalid={Boolean(error)}
            aria-describedby={error ? `txt-${b.id}-err` : undefined}
            onChange={(e) => setTexto(e.target.value)}
          />
          <p className="text-xs text-muted">
            {texto.length} de {max} caracteres. Lo que escribas es tuyo: se revisará con la auditoría, pero solo como aviso.
          </p>
          {error && (
            <p id={`txt-${b.id}-err`} role="alert" className="text-sm text-danger">
              {error}
            </p>
          )}
          <div className="flex gap-2">
            <button type="submit" className={btnPrimary} disabled={ocupado}>
              Guardar texto
            </button>
            <button type="button" className={btnSecondary} onClick={() => { setEditando(false); setTexto(b.texto); setError(null); }}>
              Cancelar
            </button>
          </div>
        </form>
      ) : (
        <>
          <p className="text-base">{b.texto}</p>
          {origen && (
            <p className="mt-2 text-xs text-muted">
              Basado en tu logro: «{origen}»
            </p>
          )}
          <p className="mt-3 flex flex-wrap gap-2 text-xs">
            <span className={`rounded px-2 py-1 ring-1 ring-border ${b.estado === "aprobado" ? "bg-success-bg text-success" : "bg-background"}`}>
              {ESTADO[b.estado]}
            </span>
            <span className="rounded bg-background px-2 py-1 ring-1 ring-border">
              {b.origen === "ia" ? "Redactado por la IA" : "Escrito por ti"}
            </span>
            <span className={`rounded px-2 py-1 ${b.auditoria_ok ? "bg-success-bg text-success" : "bg-danger-bg text-danger"}`}>
              {b.auditoria_ok ? "✔ Auditoría: todo respaldado por tus datos" : "✖ Auditoría: hay contenido sin respaldo"}
            </span>
          </p>
          {!b.auditoria_ok && b.problemas.length > 0 && (
            <ul className="mt-2 list-disc space-y-1 pl-5 text-sm text-danger">
              {b.problemas.map((p, i) => (
                <li key={i}>{p.detalle}</li>
              ))}
            </ul>
          )}
          {b.avisos.length > 0 && (
            <ul className="mt-2 list-disc space-y-1 pl-5 text-xs text-muted">
              {b.avisos.map((a, i) => (
                <li key={i}>{a}</li>
              ))}
            </ul>
          )}
          {bloqueado && (
            <p className="mt-2 text-sm">
              No se puede aprobar tal cual: edítalo para quitar lo que no está en tus datos, o recházalo.
            </p>
          )}
          <div className="mt-3 flex flex-wrap gap-2">
            {b.estado !== "aprobado" && b.estado !== "rechazado" && (
              <button type="button" className={btnPrimary} disabled={bloqueado} onClick={() => onActuar(b, "aprobar")}>
                Aprobar
              </button>
            )}
            <button type="button" className={btnSecondary} onClick={() => { setTexto(b.texto); setEditando(true); }}>
              Editar
            </button>
            {b.estado === "rechazado" ? (
              <button type="button" className={btnSecondary} onClick={() => onActuar(b, "restaurar")}>
                Volver a borrador
              </button>
            ) : (
              <button type="button" className={btnSecondary} onClick={() => onActuar(b, b.estado === "aprobado" ? "restaurar" : "rechazar")}>
                {b.estado === "aprobado" ? "Quitar aprobación" : "Rechazar"}
              </button>
            )}
          </div>
        </>
      )}
    </li>
  );
}

export function WritingPanel() {
  const perfilId = useSearchParams().get("perfil");
  const [nombrePerfil, setNombrePerfil] = useState("");
  const [borradores, setBorradores] = useState<Borrador[] | null>(null);
  const [hechos, setHechos] = useState<Hecho[]>([]);
  const [objetivo, setObjetivo] = useState("");
  const [tarea, setTarea] = useState<Tarea | null>(null);
  const [comparacion, setComparacion] = useState<Comparacion | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [aviso, setAviso] = useState("");

  const recargar = useCallback(async () => {
    if (!perfilId) return;
    try {
      const [b, h] = await Promise.all([redaccion.borradores(perfilId), documentos.hechos(perfilId)]);
      setBorradores(b);
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

  const tareaId = tarea?.id;
  const activa = tarea ? ACTIVAS.includes(tarea.estado) : false;
  useEffect(() => {
    if (!tareaId || !activa) return;
    const t = setInterval(async () => {
      try {
        const nueva = await ia.tarea(tareaId);
        setTarea(nueva);
        if (!ACTIVAS.includes(nueva.estado)) void recargar();
      } catch (e) {
        setError(mensaje(e));
      }
    }, 1500);
    return () => clearInterval(t);
  }, [tareaId, activa, recargar]);

  async function redactar() {
    if (!perfilId) return;
    setError(null);
    setAviso("");
    try {
      setTarea(await redaccion.redactar(perfilId, objetivo.trim() || null));
    } catch (e) {
      setError(mensaje(e));
    }
  }

  async function cancelar() {
    if (!tarea) return;
    try {
      setTarea(await ia.cancelar(tarea.id));
      await recargar();
    } catch (e) {
      setError(mensaje(e));
    }
  }

  async function analizar() {
    if (!perfilId) return;
    setError(null);
    try {
      setComparacion(await redaccion.palabrasClave(perfilId, objetivo));
    } catch (e) {
      setError(e instanceof ApiError && e.fields.oferta ? e.fields.oferta : mensaje(e));
    }
  }

  const reemplazar = (nuevo: Borrador) => setBorradores((bs) => (bs ?? []).map((b) => (b.id === nuevo.id ? nuevo : b)));

  async function actuar(b: Borrador, a: "aprobar" | "rechazar" | "restaurar") {
    setError(null);
    try {
      reemplazar(await redaccion.actuar(b.id, a));
      setAviso({ aprobar: "Texto aprobado.", rechazar: "Texto rechazado.", restaurar: "Texto devuelto a borrador." }[a]);
    } catch (e) {
      setError(mensaje(e));
    }
  }

  async function editar(b: Borrador, texto: string) {
    reemplazar(await redaccion.editar(b.id, texto)); // los errores los muestra la tarjeta
    setAviso("Texto guardado. Revísalo y apruébalo cuando esté bien.");
  }

  async function asignar(h: Hecho, puesto: string) {
    setError(null);
    try {
      await revision.editar(h.id, { texto: String(h.data.texto ?? ""), contexto: puesto });
      setAviso("Logro asignado al puesto.");
      await recargar();
    } catch (e) {
      setError(mensaje(e));
    }
  }

  const aprobados = hechos.filter(aprobado);
  const puestos = aprobados.filter((h) => h.category === "experiencia");
  const logros = aprobados.filter((h) => h.category === "logro");
  const clavesPuestos = new Set(puestos.map((p) => norm(etiquetaPuesto(p))));
  const sinPuesto = logros.filter((l) => !clavesPuestos.has(norm(String(l.data.contexto ?? ""))));
  const resumen = (borradores ?? []).filter((b) => b.seccion === "resumen");
  const puntos = (borradores ?? []).filter((b) => b.seccion === "logro");
  const textoLogro = (id: string | undefined) => (id ? String(hechos.find((h) => h.id === id)?.data.texto ?? "") : "");
  const sinDatos = hechos.length > 0 && aprobados.length === 0;
  const pct = Math.round((tarea?.progreso ?? 0) * 100);
  const nAprobados = (borradores ?? []).filter((b) => b.estado === "aprobado").length;

  return (
    <section aria-labelledby="titulo-red" className="space-y-6">
      <div>
        <Link href="/" className="text-sm underline">
          ← Volver a los perfiles
        </Link>
        <h1 id="titulo-red" className="mt-2 text-2xl font-semibold">
          Redacción{nombrePerfil ? ` de ${nombrePerfil}` : ""}
        </h1>
        <p className="mt-1 text-muted">
          La IA local redacta tu resumen y mejora tus logros usando <strong>solo tu información aprobada</strong>. Cada
          texto pasa por una auditoría que busca cifras, empresas, herramientas o cargos que no estén en tus datos. Nada
          se usa en el currículum hasta que lo apruebes.
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

      {sinDatos && perfilId && (
        <div className={cardClass}>
          <p>
            Aún no hay datos aprobados.{" "}
            <Link href={`/revision/?perfil=${encodeURIComponent(perfilId)}`} className="underline">
              Revisa y aprueba tus datos
            </Link>{" "}
            para poder redactar.
          </p>
        </div>
      )}

      <div className={`${cardClass} space-y-3`}>
        <label htmlFor="objetivo" className="block text-sm font-medium">
          Puesto al que aspiras (opcional)
        </label>
        <textarea
          id="objetivo"
          className={inputClass}
          rows={4}
          maxLength={3000}
          value={objetivo}
          placeholder="Pega aquí la oferta o describe el puesto"
          onChange={(e) => setObjetivo(e.target.value)}
          aria-describedby="objetivo-ayuda"
        />
        <p id="objetivo-ayuda" className="text-xs text-muted">
          Sirve para orientar el tono y ver qué piden que ya tienes. <strong>No es una fuente de datos</strong>: lo que
          pida la oferta y no esté en tu información no se escribirá.
        </p>
        <div className="flex flex-wrap gap-3">
          <button type="button" className={btnPrimary} onClick={redactar} disabled={activa || aprobados.length === 0}>
            {borradores && borradores.length > 0 ? "Volver a redactar" : "Redactar con IA"}
          </button>
          <button type="button" className={btnSecondary} onClick={analizar} disabled={objetivo.trim().length < 3}>
            Analizar palabras clave de la oferta
          </button>
        </div>
        {borradores && borradores.length > 0 && (
          <p className="text-xs text-muted">Al volver a redactar se conservan los textos aprobados y los que tú escribiste.</p>
        )}
      </div>

      {tarea && activa && (
        <div className={cardClass} aria-live="polite">
          <p className="text-sm">{tarea.mensaje}</p>
          <div
            role="progressbar"
            aria-label="Progreso de la redacción"
            aria-valuemin={0}
            aria-valuemax={100}
            aria-valuenow={pct}
            className="mt-2 h-3 w-full overflow-hidden rounded-full bg-border"
          >
            <div className="h-full bg-primary transition-[width]" style={{ width: `${pct}%` }} />
          </div>
          <button type="button" className={`${btnSecondary} mt-3`} onClick={cancelar}>
            Cancelar
          </button>
        </div>
      )}
      {tarea?.estado === "error" && (
        <p role="alert" className="rounded-md bg-danger-bg p-3 text-danger">
          {tarea.error}
        </p>
      )}
      {tarea?.estado === "completado" && tarea.resultado && (
        <p
          className={
            Number(tarea.resultado.con_problemas) > 0
              ? `${cardClass} text-sm`
              : "rounded-md bg-success-bg p-3 text-success"
          }
        >
          Se redactaron {String(tarea.resultado.borradores)} {Number(tarea.resultado.borradores) === 1 ? "texto" : "textos"}
          {Number(tarea.resultado.con_problemas) > 0
            ? `; ${String(tarea.resultado.con_problemas)} ${Number(tarea.resultado.con_problemas) === 1 ? "no pasó" : "no pasaron"} la auditoría (revísalos abajo).`
            : ", todos respaldados por tus datos."}
        </p>
      )}

      {comparacion && (
        <div className={`${cardClass} space-y-3`}>
          <h2 className="text-lg font-medium">Coincidencia con la oferta</h2>
          <div>
            <p className="text-sm font-medium">Aparecen en tu información ({comparacion.coinciden.length})</p>
            <p className="mt-1 flex flex-wrap gap-2 text-sm">
              {comparacion.coinciden.length === 0 && <span className="text-muted">Ninguno.</span>}
              {comparacion.coinciden.map((t) => (
                <span key={t} className="rounded bg-success-bg px-2 py-1 text-success">
                  ✔ {t}
                </span>
              ))}
            </p>
          </div>
          <div>
            <p className="text-sm font-medium">No aparecen en tu información ({comparacion.faltan.length})</p>
            <p className="mt-1 flex flex-wrap gap-2 text-sm">
              {comparacion.faltan.length === 0 && <span className="text-muted">Ninguno.</span>}
              {comparacion.faltan.map((t) => (
                <span key={t} className="rounded bg-background px-2 py-1 ring-1 ring-border">
                  {t}
                </span>
              ))}
            </p>
          </div>
          <p className="text-sm text-muted">
            Si tienes experiencia real en alguno de los que faltan, agrégalo en{" "}
            {perfilId && (
              <Link href={`/entrevista/?perfil=${encodeURIComponent(perfilId)}`} className="underline">
                Completar información
              </Link>
            )}
            . Si no la tienes, no se mencionará: el currículum solo dice lo que es cierto.
          </p>
        </div>
      )}

      {sinPuesto.length > 0 && (
        <div className={`${cardClass} space-y-3`}>
          <h2 className="text-lg font-medium">Logros sin puesto asignado ({sinPuesto.length})</h2>
          <p className="text-sm text-muted">
            Para mejorarlos y ponerlos bajo el puesto correcto, indica a cuál pertenece cada uno.
          </p>
          <ul className="space-y-3">
            {sinPuesto.map((l) => (
              <li key={l.id} className="border-t border-border pt-3">
                <p className="text-sm">«{String(l.data.texto)}»</p>
                {puestos.length === 0 ? (
                  <p className="mt-1 text-xs text-muted">Primero necesitas un puesto aprobado en «Revisar datos».</p>
                ) : (
                  <div className="mt-2 flex flex-wrap items-center gap-2">
                    <label htmlFor={`as-${l.id}`} className="sr-only">
                      Puesto del logro
                    </label>
                    <select
                      id={`as-${l.id}`}
                      className={`${inputClass} max-w-xs`}
                      defaultValue=""
                      onChange={(e) => e.target.value && asignar(l, e.target.value)}
                    >
                      <option value="">Asignar a un puesto…</option>
                      {puestos.map((p) => (
                        <option key={p.id} value={etiquetaPuesto(p)}>
                          {etiquetaPuesto(p)}
                        </option>
                      ))}
                    </select>
                  </div>
                )}
              </li>
            ))}
          </ul>
        </div>
      )}

      {borradores && borradores.length > 0 && (
        <div className="space-y-6">
          <h2 className="text-xl font-semibold">
            Textos redactados ({nAprobados} de {borradores.length} aprobados)
          </h2>
          {resumen.length > 0 && (
            <section aria-labelledby="sec-resumen">
              <h3 id="sec-resumen" className="mb-2 text-lg font-medium">
                Resumen profesional
              </h3>
              <ul className="space-y-3">
                {resumen.map((b) => (
                  <BorradorCard key={b.id} b={b} onActuar={actuar} onEditar={editar} />
                ))}
              </ul>
            </section>
          )}
          {puestos
            .filter((p) => puntos.some((b) => b.puesto_id === p.id))
            .map((p) => (
              <section key={p.id} aria-labelledby={`sec-${p.id}`}>
                <h3 id={`sec-${p.id}`} className="mb-2 text-lg font-medium">
                  {etiquetaPuesto(p)}
                </h3>
                <ul className="space-y-3">
                  {puntos
                    .filter((b) => b.puesto_id === p.id)
                    .map((b) => (
                      <BorradorCard key={b.id} b={b} origen={textoLogro(b.fuentes[0])} onActuar={actuar} onEditar={editar} />
                    ))}
                </ul>
              </section>
            ))}
        </div>
      )}

      {borradores && borradores.length === 0 && !activa && aprobados.length > 0 && (
        <p className="text-muted">Todavía no hay textos redactados. Pulsa «Redactar con IA».</p>
      )}
    </section>
  );
}
