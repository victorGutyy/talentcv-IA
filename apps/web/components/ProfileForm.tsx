"use client";

import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { useEffect, useRef, useState } from "react";
import { ApiError, api, initToken } from "@/lib/api";
import type { Enlace, Profile, ProfileInput } from "@/lib/types";
import { btnPrimary, btnSecondary, inputClass } from "./ui";

type Valores = {
  nombre_completo: string;
  titular: string;
  email: string;
  telefono: string;
  ciudad: string;
  pais: string;
  resumen: string;
};

const VACIO: Valores = { nombre_completo: "", titular: "", email: "", telefono: "", ciudad: "", pais: "", resumen: "" };
const MAX_ENLACES = 10;
const MAX_RESUMEN = 2000;

function desdePerfil(p: Profile): Valores {
  return {
    nombre_completo: p.nombre_completo,
    titular: p.titular ?? "",
    email: p.email ?? "",
    telefono: p.telefono ?? "",
    ciudad: p.ciudad ?? "",
    pais: p.pais ?? "",
    resumen: p.resumen ?? "",
  };
}

const nulo = (s: string) => (s.trim() === "" ? null : s.trim());

type CampoProps = {
  id: string;
  label: string;
  error?: string;
  ayuda?: string;
  obligatorio?: boolean;
  children: (p: { id: string; "aria-invalid": boolean; "aria-describedby": string | undefined }) => React.ReactNode;
};

function Campo({ id, label, error, ayuda, obligatorio, children }: CampoProps) {
  const descr = [ayuda ? `${id}-ayuda` : "", error ? `${id}-error` : ""].filter(Boolean).join(" ") || undefined;
  return (
    <div>
      <label htmlFor={id} className="mb-1 block text-sm font-medium">
        {label}
        {obligatorio && (
          <span aria-hidden="true" className="text-danger">
            {" "}
            *
          </span>
        )}
      </label>
      {children({ id, "aria-invalid": Boolean(error), "aria-describedby": descr })}
      {ayuda && (
        <p id={`${id}-ayuda`} className="mt-1 text-sm text-muted">
          {ayuda}
        </p>
      )}
      {error && (
        <p id={`${id}-error`} className="mt-1 text-sm text-danger">
          {error}
        </p>
      )}
    </div>
  );
}

export function ProfileForm() {
  const router = useRouter();
  const id = useSearchParams().get("id");
  const [valores, setValores] = useState<Valores>(VACIO);
  const [enlaces, setEnlaces] = useState<Enlace[]>([]);
  const [cargando, setCargando] = useState(Boolean(id));
  const [guardando, setGuardando] = useState(false);
  const [errores, setErrores] = useState<Record<string, string>>({});
  const [errorGeneral, setErrorGeneral] = useState<string | null>(null);
  const [guardado, setGuardado] = useState(false);
  const resumenGeneral = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!initToken()) {
      // eslint-disable-next-line react-hooks/set-state-in-effect
      setErrorGeneral("No hay sesión activa. Abre TalentCV AI desde su acceso directo.");
      setCargando(false);
      return;
    }
    if (!id) return;
    let activo = true;
    api
      .obtener(id)
      .then((p) => {
        if (!activo) return;
        setValores(desdePerfil(p));
        setEnlaces(p.enlaces);
      })
      .catch((e) => activo && setErrorGeneral(e instanceof ApiError ? e.message : "Error inesperado."))
      .finally(() => activo && setCargando(false));
    return () => {
      activo = false;
    };
  }, [id]);

  const cambiar = (campo: keyof Valores) => (e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement>) => {
    setValores((v) => ({ ...v, [campo]: e.target.value }));
    setGuardado(false);
  };

  function cambiarEnlace(i: number, campo: keyof Enlace, valor: string) {
    setEnlaces((l) => l.map((e, j) => (j === i ? { ...e, [campo]: valor } : e)));
    setGuardado(false);
  }

  async function enviar(e: React.FormEvent) {
    e.preventDefault();
    setErrores({});
    setErrorGeneral(null);
    setGuardado(false);

    const local: Record<string, string> = {};
    if (!valores.nombre_completo.trim()) local.nombre_completo = "El nombre completo es obligatorio.";
    if (Object.keys(local).length) {
      setErrores(local);
      document.getElementById("nombre_completo")?.focus();
      return;
    }

    const datos: ProfileInput = {
      nombre_completo: valores.nombre_completo.trim(),
      titular: nulo(valores.titular),
      email: nulo(valores.email),
      telefono: nulo(valores.telefono),
      ciudad: nulo(valores.ciudad),
      pais: nulo(valores.pais),
      resumen: nulo(valores.resumen),
      enlaces: enlaces.map((l) => ({ etiqueta: l.etiqueta.trim(), url: l.url.trim() })),
    };

    setGuardando(true);
    try {
      const p = id ? await api.actualizar(id, datos) : await api.crear(datos);
      setValores(desdePerfil(p));
      setEnlaces(p.enlaces);
      setGuardado(true);
      if (!id) router.replace(`/perfil/?id=${encodeURIComponent(p.id)}`);
    } catch (err) {
      if (err instanceof ApiError) {
        setErrores(err.fields);
        setErrorGeneral(err.message);
        const primero = Object.keys(err.fields)[0];
        if (primero && document.getElementById(primero)) document.getElementById(primero)?.focus();
        else resumenGeneral.current?.focus();
      } else {
        setErrorGeneral("Error inesperado.");
      }
    } finally {
      setGuardando(false);
    }
  }

  if (cargando) return <p className="text-muted">Cargando perfil…</p>;

  return (
    <form onSubmit={enviar} noValidate aria-labelledby="titulo-form" className="space-y-6">
      <h1 id="titulo-form" className="text-2xl font-semibold">
        {id ? "Editar perfil" : "Nuevo perfil"}
      </h1>

      <div ref={resumenGeneral} tabIndex={-1} role="alert" className={errorGeneral ? "rounded-md bg-danger-bg p-3 text-danger" : "sr-only"}>
        {errorGeneral}
      </div>
      <p role="status" aria-live="polite" className={guardado ? "rounded-md bg-success-bg p-3 text-success" : "sr-only"}>
        {guardado ? "Perfil guardado." : ""}
      </p>

      <p className="text-sm text-muted">
        Los campos con <span aria-hidden="true">*</span>
        <span className="sr-only">asterisco</span> son obligatorios. Escribe solo datos verdaderos: la aplicación no los
        inventa ni los modifica sin tu aprobación.
      </p>

      <fieldset className="space-y-4">
        <legend className="mb-2 text-lg font-medium">Datos personales</legend>
        <Campo id="nombre_completo" label="Nombre completo" obligatorio error={errores.nombre_completo}>
          {(p) => (
            <input {...p} className={inputClass} value={valores.nombre_completo} onChange={cambiar("nombre_completo")} maxLength={200} autoComplete="name" required aria-required="true" />
          )}
        </Campo>
        <Campo id="titular" label="Titular profesional" ayuda="Por ejemplo: Ingeniera de sistemas" error={errores.titular}>
          {(p) => <input {...p} className={inputClass} value={valores.titular} onChange={cambiar("titular")} maxLength={200} autoComplete="organization-title" />}
        </Campo>
        <div className="grid gap-4 sm:grid-cols-2">
          <Campo id="email" label="Correo electrónico" error={errores.email}>
            {(p) => <input {...p} type="email" className={inputClass} value={valores.email} onChange={cambiar("email")} maxLength={254} autoComplete="email" />}
          </Campo>
          <Campo id="telefono" label="Teléfono" error={errores.telefono}>
            {(p) => <input {...p} type="tel" className={inputClass} value={valores.telefono} onChange={cambiar("telefono")} maxLength={40} autoComplete="tel" />}
          </Campo>
          <Campo id="ciudad" label="Ciudad" error={errores.ciudad}>
            {(p) => <input {...p} className={inputClass} value={valores.ciudad} onChange={cambiar("ciudad")} maxLength={120} autoComplete="address-level2" />}
          </Campo>
          <Campo id="pais" label="País" error={errores.pais}>
            {(p) => <input {...p} className={inputClass} value={valores.pais} onChange={cambiar("pais")} maxLength={120} autoComplete="country-name" />}
          </Campo>
        </div>
        <Campo
          id="resumen"
          label="Resumen"
          ayuda={`${valores.resumen.length} de ${MAX_RESUMEN} caracteres. Es tu texto; la IA lo usará solo si lo apruebas.`}
          error={errores.resumen}
        >
          {(p) => <textarea {...p} className={inputClass} rows={5} value={valores.resumen} onChange={cambiar("resumen")} maxLength={MAX_RESUMEN} />}
        </Campo>
      </fieldset>

      <fieldset className="space-y-4">
        <legend className="mb-2 text-lg font-medium">Enlaces</legend>
        {enlaces.length === 0 && <p className="text-sm text-muted">Aún no agregaste enlaces (LinkedIn, GitHub, sitio web…).</p>}
        {enlaces.map((l, i) => (
          <div key={i} className="grid items-end gap-3 sm:grid-cols-[1fr_2fr_auto]">
            <Campo id={`enlace-etiqueta-${i}`} label={`Etiqueta del enlace ${i + 1}`}>
              {(p) => <input {...p} className={inputClass} value={l.etiqueta} onChange={(e) => cambiarEnlace(i, "etiqueta", e.target.value)} maxLength={60} placeholder="LinkedIn" />}
            </Campo>
            <Campo id={`enlace-url-${i}`} label={`Dirección del enlace ${i + 1}`}>
              {(p) => <input {...p} type="url" className={inputClass} value={l.url} onChange={(e) => cambiarEnlace(i, "url", e.target.value)} maxLength={500} placeholder="https://" />}
            </Campo>
            <button type="button" className={btnSecondary} onClick={() => { setEnlaces((x) => x.filter((_, j) => j !== i)); setGuardado(false); }} aria-label={`Quitar enlace ${i + 1}`}>
              Quitar
            </button>
          </div>
        ))}
        {errores.enlaces && <p className="text-sm text-danger">{errores.enlaces}</p>}
        <button type="button" className={btnSecondary} disabled={enlaces.length >= MAX_ENLACES} onClick={() => { setEnlaces((x) => [...x, { etiqueta: "", url: "" }]); setGuardado(false); }}>
          Agregar enlace
        </button>
      </fieldset>

      <div className="flex flex-wrap gap-3">
        <button type="submit" className={btnPrimary} disabled={guardando}>
          {guardando ? "Guardando…" : "Guardar perfil"}
        </button>
        <Link href="/" className={btnSecondary}>
          Volver a la lista
        </Link>
      </div>
    </form>
  );
}
