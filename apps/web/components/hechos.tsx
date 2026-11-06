"use client";

import { useState } from "react";
import { ApiError } from "@/lib/api";
import type { Categoria, Hecho, HechoDatos } from "@/lib/types";
import { btnPrimary, btnSecondary, cardClass, inputClass } from "./ui";

export const CATEGORIAS: Record<Categoria, string> = {
  contacto: "Datos de contacto",
  experiencia: "Experiencia laboral",
  educacion: "Educación",
  certificacion: "Certificaciones",
  idioma: "Idiomas",
  habilidad: "Habilidades",
  logro: "Logros y responsabilidades",
};

export const TIPO_CONTACTO: Record<string, string> = {
  nombre: "Nombre",
  email: "Correo",
  telefono: "Teléfono",
  ciudad: "Ciudad",
  pais: "País",
  enlace: "Enlace",
};

type CampoDef = { key: string; label: string; tipo?: "area" | "lista" | "tipoContacto"; obligatorio?: boolean; ayuda?: string };

export const FORMULARIOS: Record<Categoria, CampoDef[]> = {
  contacto: [
    { key: "tipo", label: "Tipo de dato", tipo: "tipoContacto", obligatorio: true },
    { key: "valor", label: "Valor", obligatorio: true },
  ],
  experiencia: [
    { key: "cargo", label: "Cargo", obligatorio: true },
    { key: "empresa", label: "Empresa" },
    { key: "inicio", label: "Inicio", ayuda: "Tal como lo quieres mostrar, p. ej. marzo 2020" },
    { key: "fin", label: "Fin", ayuda: "O «actualidad»" },
  ],
  educacion: [
    { key: "titulo", label: "Título", obligatorio: true },
    { key: "institucion", label: "Institución" },
    { key: "fecha_graduacion", label: "Fecha de graduación" },
  ],
  certificacion: [
    { key: "nombre", label: "Nombre", obligatorio: true },
    { key: "emisor", label: "Entidad emisora" },
    { key: "fecha", label: "Fecha" },
  ],
  idioma: [
    { key: "idioma", label: "Idioma", obligatorio: true },
    { key: "nivel", label: "Nivel" },
  ],
  habilidad: [{ key: "nombres", label: "Habilidades", tipo: "lista", obligatorio: true, ayuda: "Sepáralas con comas" }],
  logro: [{ key: "texto", label: "Texto", tipo: "area", obligatorio: true }],
};

export const ESTADOS: Record<Hecho["status"], string> = {
  pendiente: "Pendiente de confirmar",
  confirmado: "Confirmado",
  editado: "Editado por ti",
  rechazado: "Rechazado",
};

/** Texto corto para identificar un dato en botones y avisos. */
export function resumen(h: Hecho): string {
  const d = h.data;
  const pick = (...k: string[]) => k.map((x) => d[x]).find((v) => v && (!Array.isArray(v) || v.length)) ?? "";
  const v = pick("cargo", "titulo", "nombre", "idioma", "valor", "nombres", "texto");
  const texto = Array.isArray(v) ? v.join(", ") : String(v);
  return texto.length > 60 ? `${texto.slice(0, 57)}…` : texto || "dato";
}

export function Valor({ v }: { v: string | string[] | null | undefined }) {
  const texto = Array.isArray(v) ? v.join(", ") : v;
  return texto ? <>{texto}</> : <em className="text-muted">No aparece en el documento</em>;
}

type CardProps = {
  h: Hecho;
  nombreDoc: string | null;
  seleccion?: { marcado: boolean; onChange: (v: boolean) => void };
  children?: React.ReactNode; // acciones
};

export function HechoCard({ h, nombreDoc, seleccion, children }: CardProps) {
  const campos = FORMULARIOS[h.category].filter((c) => c.key !== "tipo");
  const pendiente = h.status === "pendiente";
  return (
    <li className={`${cardClass} ${h.status === "rechazado" ? "opacity-70" : ""}`}>
      <div className="flex items-start gap-3">
        {seleccion && (
          <input
            type="checkbox"
            className="mt-1 size-5 shrink-0"
            checked={seleccion.marcado}
            onChange={(e) => seleccion.onChange(e.target.checked)}
            aria-label={`Seleccionar: ${resumen(h)}`}
          />
        )}
        <div className="min-w-0 flex-1">
          {h.category === "contacto" && (
            <p className="text-sm font-medium text-muted">{TIPO_CONTACTO[String(h.data.tipo)] ?? "Contacto"}</p>
          )}
          <dl className="grid gap-x-4 gap-y-1 text-sm sm:grid-cols-[auto_1fr]">
            {campos.map((c) => (
              <div key={c.key} className="contents">
                <dt className="text-muted">{c.label}</dt>
                <dd className="font-medium">
                  {h.origin === "manual" && !h.data[c.key] ? <em className="text-muted">Sin indicar</em> : <Valor v={h.data[c.key]} />}
                </dd>
              </div>
            ))}
          </dl>

          {h.original_data && (
            <p className="mt-2 text-xs text-muted">
              Valor original extraído:{" "}
              {FORMULARIOS[h.category]
                .filter((c) => c.key !== "tipo")
                .map((c) => (Array.isArray(h.original_data?.[c.key]) ? (h.original_data?.[c.key] as string[]).join(", ") : h.original_data?.[c.key]))
                .filter(Boolean)
                .join(" · ")}
            </p>
          )}

          {h.origin === "manual" ? (
            <p className="mt-3 text-xs text-muted">Escrito por ti: no proviene de ningún documento.</p>
          ) : (
            <figure className="mt-3 border-l-4 border-border pl-3">
              <blockquote className="text-sm italic">«{h.quote}»</blockquote>
              <figcaption className="mt-1 text-xs text-muted">
                Fuente: {nombreDoc ?? "documento eliminado"}
                {h.page ? `, página ${h.page}` : ""}
              </figcaption>
            </figure>
          )}

          <p className="mt-3 flex flex-wrap gap-2 text-xs">
            <span
              className={`rounded px-2 py-1 ring-1 ring-border ${
                h.status === "confirmado" || h.status === "editado" ? "bg-success-bg text-success" : "bg-background"
              }`}
            >
              {h.origin === "manual" ? "Escrito por ti" : ESTADOS[h.status]}
            </span>
            {pendiente && h.from_ocr && (
              <span className="rounded bg-danger-bg px-2 py-1 text-danger">Leído por OCR: revisa que esté bien escrito</span>
            )}
            {pendiente && h.dropped_fields.length > 0 && (
              <span className="rounded bg-danger-bg px-2 py-1 text-danger">
                No verificado en el documento: {h.dropped_fields.join(", ")}
              </span>
            )}
          </p>
          {children && <div className="mt-3 flex flex-wrap gap-2">{children}</div>}
        </div>
      </div>
    </li>
  );
}

type FormProps = {
  categoria: Categoria;
  idBase: string;
  inicial?: HechoDatos;
  etiquetaGuardar: string;
  onSubmit: (datos: HechoDatos) => Promise<void>;
  onCancel?: () => void;
};

const aTexto = (v: string | string[] | null | undefined) => (Array.isArray(v) ? v.join(", ") : (v ?? ""));

/** Formulario de edición/alta. Los errores del servidor se asocian a su campo. */
export function FactForm({ categoria, idBase, inicial, etiquetaGuardar, onSubmit, onCancel }: FormProps) {
  const defs = FORMULARIOS[categoria];
  const [valores, setValores] = useState<Record<string, string>>(() =>
    Object.fromEntries(defs.map((d) => [d.key, aTexto(inicial?.[d.key]) || (d.tipo === "tipoContacto" ? "email" : "")])),
  );
  const [errores, setErrores] = useState<Record<string, string>>({});
  const [errorGeneral, setErrorGeneral] = useState<string | null>(null);
  const [guardando, setGuardando] = useState(false);

  async function enviar(e: React.FormEvent) {
    e.preventDefault();
    const datos: HechoDatos = {};
    for (const d of defs) {
      const v = valores[d.key] ?? "";
      datos[d.key] = d.tipo === "lista" ? v.split(/[,\n]/).map((x) => x.trim()).filter(Boolean) : v.trim() || null;
    }
    const locales: Record<string, string> = {};
    for (const d of defs) {
      const vacio = Array.isArray(datos[d.key]) ? (datos[d.key] as string[]).length === 0 : !datos[d.key];
      if (d.obligatorio && vacio) locales[d.key] = "Este campo es obligatorio.";
    }
    setErrores(locales);
    setErrorGeneral(null);
    if (Object.keys(locales).length) {
      document.getElementById(`${idBase}-${Object.keys(locales)[0]}`)?.focus();
      return;
    }
    setGuardando(true);
    try {
      await onSubmit(datos);
    } catch (err) {
      if (err instanceof ApiError) {
        setErrores(err.fields);
        setErrorGeneral(err.message);
        const primero = Object.keys(err.fields)[0];
        if (primero) document.getElementById(`${idBase}-${primero}`)?.focus();
      } else {
        setErrorGeneral("Error inesperado.");
      }
    } finally {
      setGuardando(false);
    }
  }

  return (
    <form onSubmit={enviar} noValidate className="space-y-3">
      {errorGeneral && (
        <p role="alert" className="rounded-md bg-danger-bg p-2 text-sm text-danger">
          {errorGeneral}
        </p>
      )}
      {defs.map((d) => {
        const id = `${idBase}-${d.key}`;
        const err = errores[d.key];
        const descr = [d.ayuda ? `${id}-ayuda` : "", err ? `${id}-error` : ""].filter(Boolean).join(" ") || undefined;
        const comunes = {
          id,
          value: valores[d.key] ?? "",
          "aria-invalid": Boolean(err),
          "aria-describedby": descr,
          className: inputClass,
          onChange: (e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement | HTMLSelectElement>) =>
            setValores((v) => ({ ...v, [d.key]: e.target.value })),
        };
        return (
          <div key={d.key}>
            <label htmlFor={id} className="mb-1 block text-sm font-medium">
              {d.label}
              {d.obligatorio && (
                <span aria-hidden="true" className="text-danger">
                  {" "}
                  *
                </span>
              )}
            </label>
            {d.tipo === "tipoContacto" ? (
              <select {...comunes}>
                {Object.entries(TIPO_CONTACTO).map(([v, l]) => (
                  <option key={v} value={v}>
                    {l}
                  </option>
                ))}
              </select>
            ) : d.tipo === "area" || d.tipo === "lista" ? (
              <textarea {...comunes} rows={3} maxLength={d.tipo === "area" ? 600 : 2000} />
            ) : (
              <input {...comunes} maxLength={300} />
            )}
            {d.ayuda && (
              <p id={`${id}-ayuda`} className="mt-1 text-xs text-muted">
                {d.ayuda}
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
      <div className="flex flex-wrap gap-2">
        <button type="submit" className={btnPrimary} disabled={guardando}>
          {guardando ? "Guardando…" : etiquetaGuardar}
        </button>
        {onCancel && (
          <button type="button" className={btnSecondary} onClick={onCancel}>
            Cancelar
          </button>
        )}
      </div>
    </form>
  );
}
