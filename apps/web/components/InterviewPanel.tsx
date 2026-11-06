"use client";

import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { useCallback, useEffect, useRef, useState } from "react";
import { ApiError, documentos, entrevista, initToken } from "@/lib/api";
import type { EstadoEntrevista, Pregunta } from "@/lib/types";
import { btnPrimary, btnSecondary, cardClass, inputClass } from "./ui";

const mensaje = (e: unknown) => (e instanceof ApiError ? e.message : "Error inesperado.");

type FormProps = {
  pregunta: Pregunta;
  onResponder: (valores: Record<string, string>) => Promise<void>;
  onOmitir: () => Promise<void>;
};

/** Formulario generado a partir de los campos que define el servidor para cada pregunta. */
function PreguntaForm({ pregunta, onResponder, onOmitir }: FormProps) {
  const [valores, setValores] = useState<Record<string, string>>({});
  const [errores, setErrores] = useState<Record<string, string>>({});
  const [errorGeneral, setErrorGeneral] = useState<string | null>(null);
  const [ocupado, setOcupado] = useState(false);
  const titulo = useRef<HTMLHeadingElement>(null);

  // Al cambiar de pregunta, el foco va al enunciado para que se anuncie con lector de pantalla.
  useEffect(() => {
    titulo.current?.focus();
  }, [pregunta.id]);

  async function enviar(e: React.FormEvent) {
    e.preventDefault();
    setErrores({});
    setErrorGeneral(null);
    const faltan = pregunta.campos.filter((c) => c.obligatorio && !(valores[c.key] ?? "").trim());
    if (faltan.length) {
      setErrores(Object.fromEntries(faltan.map((c) => [c.key, "Este campo es obligatorio."])));
      document.getElementById(`q-${faltan[0].key}`)?.focus();
      return;
    }
    setOcupado(true);
    try {
      await onResponder(valores);
    } catch (err) {
      if (err instanceof ApiError) {
        const { __: general, ...porCampo } = err.fields;
        setErrores(porCampo);
        setErrorGeneral(general ?? (Object.keys(porCampo).length ? err.message : err.message));
        const primero = Object.keys(porCampo)[0];
        if (primero) document.getElementById(`q-${primero}`)?.focus();
      } else {
        setErrorGeneral("Error inesperado.");
      }
    } finally {
      setOcupado(false);
    }
  }

  async function omitir() {
    setOcupado(true);
    try {
      await onOmitir();
    } catch (err) {
      setErrorGeneral(mensaje(err));
    } finally {
      setOcupado(false);
    }
  }

  return (
    <form onSubmit={enviar} noValidate aria-labelledby="pregunta-titulo" className={`${cardClass} space-y-4`}>
      <div>
        {pregunta.contexto && <p className="text-sm font-medium text-muted">{pregunta.contexto}</p>}
        <h2 id="pregunta-titulo" ref={titulo} tabIndex={-1} className="text-xl font-semibold outline-none">
          {pregunta.texto}
        </h2>
        {pregunta.ayuda && <p className="mt-1 text-sm text-muted">{pregunta.ayuda}</p>}
      </div>

      {errorGeneral && (
        <p role="alert" className="rounded-md bg-danger-bg p-3 text-sm text-danger">
          {errorGeneral}
        </p>
      )}

      {pregunta.campos.map((c) => {
        const id = `q-${c.key}`;
        const err = errores[c.key];
        const descr = [c.ayuda ? `${id}-ayuda` : "", err ? `${id}-error` : ""].filter(Boolean).join(" ") || undefined;
        const comunes = {
          id,
          value: valores[c.key] ?? "",
          "aria-invalid": Boolean(err),
          "aria-describedby": descr,
          className: inputClass,
          onChange: (ev: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement>) =>
            setValores((v) => ({ ...v, [c.key]: ev.target.value })),
        };
        return (
          <div key={c.key}>
            <label htmlFor={id} className="mb-1 block text-sm font-medium">
              {c.label}
              {c.obligatorio && (
                <span aria-hidden="true" className="text-danger">
                  {" "}
                  *
                </span>
              )}
            </label>
            {c.tipo === "area" || c.tipo === "lista" ? (
              <textarea {...comunes} rows={4} maxLength={2000} />
            ) : (
              <input {...comunes} maxLength={300} />
            )}
            {c.ayuda && (
              <p id={`${id}-ayuda`} className="mt-1 text-xs text-muted">
                {c.ayuda}
              </p>
            )}
            {err && (
              <p id={`${id}-error`} className="mt-1 text-sm text-danger">
                {err}
              </p>
            )}
          </div>
        );
      })}

      <div className="flex flex-wrap gap-3">
        <button type="submit" className={btnPrimary} disabled={ocupado}>
          {ocupado ? "Guardando…" : "Guardar respuesta"}
        </button>
        <button type="button" className={btnSecondary} onClick={omitir} disabled={ocupado}>
          {pregunta.opcional ? "No aplica / omitir" : "Omitir por ahora"}
        </button>
      </div>
    </form>
  );
}

export function InterviewPanel() {
  const perfilId = useSearchParams().get("perfil");
  const [nombrePerfil, setNombrePerfil] = useState("");
  const [estado, setEstado] = useState<EstadoEntrevista | null>(null);
  const [total, setTotal] = useState(0);
  const [error, setError] = useState<string | null>(null);
  const [aviso, setAviso] = useState("");

  const aplicar = useCallback((e: EstadoEntrevista) => {
    setEstado(e);
    setTotal((t) => Math.max(t, e.restantes));
  }, []);

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
    entrevista.estado(perfilId).then(aplicar).catch((e) => setError(mensaje(e)));
  }, [perfilId, aplicar]);

  async function responder(valores: Record<string, string>) {
    if (!perfilId || !estado?.siguiente) return;
    const nuevo = await entrevista.responder(perfilId, estado.siguiente.id, valores); // los errores los muestra el formulario
    aplicar(nuevo);
    setAviso("Respuesta guardada.");
  }

  async function omitir() {
    if (!perfilId || !estado?.siguiente) return;
    aplicar(await entrevista.omitir(perfilId, estado.siguiente.id));
    setAviso("Pregunta omitida.");
  }

  async function reiniciar() {
    if (!perfilId) return;
    setError(null);
    try {
      aplicar(await entrevista.reiniciar(perfilId));
      setAviso("Volveré a preguntarte lo que habías omitido.");
    } catch (e) {
      setError(mensaje(e));
    }
  }

  const q = estado?.siguiente ?? null;
  const hechas = total > 0 && estado ? total - estado.restantes : 0;
  const pct = total > 0 ? Math.round((hechas / total) * 100) : 0;

  return (
    <section aria-labelledby="titulo-ent" className="space-y-6">
      <div>
        <Link href="/" className="text-sm underline">
          ← Volver a los perfiles
        </Link>
        <h1 id="titulo-ent" className="mt-2 text-2xl font-semibold">
          Completar información{nombrePerfil ? ` de ${nombrePerfil}` : ""}
        </h1>
        <p className="mt-1 text-muted">
          Te haré preguntas solo sobre lo que falta en tu información aprobada. Lo que respondas es tuyo: no lo inventa
          nadie. Puedes omitir cualquier pregunta.
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

      {estado && estado.pendientes_de_revision > 0 && perfilId && (
        <div className={cardClass}>
          <p className="text-sm">
            Tienes <strong>{estado.pendientes_de_revision} datos sin revisar</strong>. Las preguntas se basan solo en lo
            que ya aprobaste, así que conviene revisarlos primero para no repetir.{" "}
            <Link href={`/revision/?perfil=${encodeURIComponent(perfilId)}`} className="underline">
              Revisar datos
            </Link>
          </p>
        </div>
      )}

      {estado && q && (
        <>
          <div>
            <p className="text-sm">
              {estado.restantes === 1 ? "Queda 1 pregunta" : `Quedan ${estado.restantes} preguntas`}
              {estado.omitidas > 0 && ` · ${estado.omitidas} omitidas`}
            </p>
            <div
              role="progressbar"
              aria-label="Avance del cuestionario"
              aria-valuemin={0}
              aria-valuemax={100}
              aria-valuenow={pct}
              className="mt-1 h-3 w-full overflow-hidden rounded-full bg-border"
            >
              <div className="h-full bg-primary transition-[width]" style={{ width: `${pct}%` }} />
            </div>
          </div>
          <PreguntaForm key={q.id} pregunta={q} onResponder={responder} onOmitir={omitir} />
        </>
      )}

      {estado && !q && (
        <div className={`${cardClass} space-y-3`}>
          <h2 className="text-xl font-semibold">¡Listo! No tengo más preguntas.</h2>
          <p className="text-muted">
            Tu información aprobada está completa
            {estado.omitidas > 0 ? `, salvo ${estado.omitidas} ${estado.omitidas === 1 ? "pregunta" : "preguntas"} que omitiste` : ""}
            .
          </p>
          <div className="flex flex-wrap gap-3">
            {perfilId && (
              <Link href={`/revision/?perfil=${encodeURIComponent(perfilId)}`} className={btnPrimary}>
                Ver mi información aprobada
              </Link>
            )}
            {estado.omitidas > 0 && (
              <button type="button" className={btnSecondary} onClick={reiniciar}>
                Volver a preguntar lo omitido
              </button>
            )}
          </div>
        </div>
      )}

      {estado && q && estado.omitidas > 0 && (
        <button type="button" className={btnSecondary} onClick={reiniciar}>
          Volver a preguntar lo omitido
        </button>
      )}
    </section>
  );
}
