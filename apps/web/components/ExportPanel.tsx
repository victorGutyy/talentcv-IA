"use client";

import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { useEffect, useState } from "react";
import { ApiError, documentos, exportacion, initToken } from "@/lib/api";
import type { CvDatos, Informe, Plantilla } from "@/lib/types";
import { btnPrimary, cardClass } from "./ui";

const mensaje = (e: unknown) => (e instanceof ApiError ? e.message : "Error inesperado.");
const FUENTES: Record<string, string> = {
  Georgia: "Georgia, 'Times New Roman', serif",
  Calibri: "Calibri, Carlito, 'Segoe UI', Arial, sans-serif",
};

function Titulo({ p, s }: { p: Plantilla; s: string }) {
  const color = p.color ?? "#000000";
  return (
    <h3
      className="mt-3 mb-1 text-[0.95em] font-bold"
      style={{ color, borderBottom: p.linea_bajo_titulos ? `1px solid ${color}` : undefined }}
    >
      {p.titulos[s] ?? s}
    </h3>
  );
}

/** Vista aproximada de la hoja con el estilo de la plantilla (el archivo real lo genera el servidor). */
function HojaPrevia({ cv, p }: { cv: CvDatos; p: Plantilla }) {
  const color = p.color ?? "#000000";
  const contacto = [cv.contacto.email, cv.contacto.telefono, cv.contacto.ubicacion].filter(Boolean).join("  |  ");
  const bloques: Record<string, React.ReactNode> = {
    resumen: cv.resumen && (
      <section key="resumen">
        <Titulo p={p} s="resumen" />
        <p>{cv.resumen}</p>
      </section>
    ),
    experiencia: cv.experiencia.length > 0 && (
      <section key="experiencia">
        <Titulo p={p} s="experiencia" />
        {cv.experiencia.map((e, i) => (
          <div key={i} className="mt-1">
            <p className="flex justify-between gap-3 font-bold">
              <span>{e.empresa ? `${e.cargo} — ${e.empresa}` : e.cargo}</span>
              <span className="shrink-0 font-normal">{e.fechas}</span>
            </p>
            <ul className="list-disc pl-5">
              {e.puntos.map((x, j) => (
                <li key={j}>{x}</li>
              ))}
            </ul>
          </div>
        ))}
      </section>
    ),
    educacion: cv.educacion.length > 0 && (
      <section key="educacion">
        <Titulo p={p} s="educacion" />
        {cv.educacion.map((e, i) => (
          <p key={i} className="flex justify-between gap-3 font-bold">
            <span>{e.institucion ? `${e.titulo} — ${e.institucion}` : e.titulo}</span>
            <span className="shrink-0 font-normal">{e.fecha}</span>
          </p>
        ))}
      </section>
    ),
    habilidades: cv.habilidades.length > 0 && (
      <section key="habilidades">
        <Titulo p={p} s="habilidades" />
        <p>{cv.habilidades.join(", ")}</p>
      </section>
    ),
    certificaciones: cv.certificaciones.length > 0 && (
      <section key="certificaciones">
        <Titulo p={p} s="certificaciones" />
        {cv.certificaciones.map((c, i) => (
          <p key={i} className="flex justify-between gap-3 font-bold">
            <span>{c.emisor ? `${c.nombre} — ${c.emisor}` : c.nombre}</span>
            <span className="shrink-0 font-normal">{c.fecha}</span>
          </p>
        ))}
      </section>
    ),
    idiomas: cv.idiomas.length > 0 && (
      <section key="idiomas">
        <Titulo p={p} s="idiomas" />
        <p>{cv.idiomas.join(", ")}</p>
      </section>
    ),
    logros: cv.logros.length > 0 && (
      <section key="logros">
        <Titulo p={p} s="logros" />
        <ul className="list-disc pl-5">
          {cv.logros.map((l, i) => (
            <li key={i}>{l}</li>
          ))}
        </ul>
      </section>
    ),
  };
  return (
    <div
      className="rounded border border-border bg-white p-6 text-[13px] leading-snug text-black shadow-sm"
      style={{ fontFamily: FUENTES[p.fuente] ?? FUENTES.Calibri }}
      aria-label={`Vista previa con la plantilla ${p.nombre}`}
      role="img"
    >
      <div style={{ textAlign: p.cabecera_centrada ? "center" : "left" }}>
        <p className="text-2xl font-bold" style={{ color }}>
          {cv.nombre}
        </p>
        {cv.titular && <p style={{ color }}>{cv.titular}</p>}
        {contacto && <p>{contacto}</p>}
        {cv.contacto.enlaces.map((e) => (
          <p key={e}>{e}</p>
        ))}
      </div>
      {p.orden.map((s) => bloques[s])}
    </div>
  );
}

type Formato = "docx" | "pdf";
type Papel = "carta" | "a4";

export function ExportPanel() {
  const perfilId = useSearchParams().get("perfil");
  const [nombrePerfil, setNombrePerfil] = useState("");
  const [plantillas, setPlantillas] = useState<Plantilla[]>([]);
  const [informe, setInforme] = useState<Informe | null>(null);
  const [plantilla, setPlantilla] = useState("ats");
  const [formato, setFormato] = useState<Formato>("docx");
  const [papel, setPapel] = useState<Papel>("carta");
  const [error, setError] = useState<string | null>(null);
  const [aviso, setAviso] = useState("");
  const [generando, setGenerando] = useState(false);

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
    exportacion.informe(perfilId).then(setInforme).catch((e) => setError(mensaje(e)));
  }, [perfilId]);

  async function descargar() {
    if (!perfilId) return;
    setError(null);
    setAviso("");
    setGenerando(true);
    try {
      const { blob, nombre } = await exportacion.exportar(perfilId, plantilla, formato, papel);
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = nombre;
      document.body.appendChild(a);
      a.click();
      a.remove();
      setTimeout(() => URL.revokeObjectURL(url), 10_000);
      setAviso(`Se generó «${nombre}». Ábrelo y revísalo antes de enviarlo.`);
    } catch (e) {
      setError(mensaje(e));
    } finally {
      setGenerando(false);
    }
  }

  const actual = plantillas.find((p) => p.id === plantilla);
  const qs = perfilId ? `?perfil=${encodeURIComponent(perfilId)}` : "";

  return (
    <section aria-labelledby="titulo-exp" className="space-y-6">
      <div>
        <Link href="/" className="text-sm underline">
          ← Volver a los perfiles
        </Link>
        <h1 id="titulo-exp" className="mt-2 text-2xl font-semibold">
          Exportar currículum{nombrePerfil ? ` de ${nombrePerfil}` : ""}
        </h1>
        <p className="mt-1 text-muted">
          El archivo se arma <strong>solo con tu información aprobada</strong> y los textos que aprobaste. Nada
          pendiente ni rechazado entra.
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

      {informe && informe.advertencias.length > 0 && (
        <div className={cardClass}>
          <h2 className="text-lg font-medium">Antes de exportar</h2>
          <ul className="mt-2 list-disc space-y-1 pl-5 text-sm">
            {informe.advertencias.map((a) => (
              <li key={a}>{a}</li>
            ))}
          </ul>
          <p className="mt-3 text-sm">
            <Link href={`/revision/${qs}`} className="underline">
              Revisar datos
            </Link>{" "}
            ·{" "}
            <Link href={`/entrevista/${qs}`} className="underline">
              Completar información
            </Link>{" "}
            ·{" "}
            <Link href={`/redaccion/${qs}`} className="underline">
              Redacción
            </Link>
          </p>
        </div>
      )}

      <div className="grid gap-6 lg:grid-cols-[minmax(0,22rem)_1fr]">
        <div className="space-y-5">
          <fieldset className="space-y-2">
            <legend className="mb-1 text-lg font-medium">Plantilla</legend>
            {plantillas.map((p) => (
              <label
                key={p.id}
                className={`${cardClass} block cursor-pointer has-[:checked]:ring-2 has-[:checked]:ring-primary`}
              >
                <span className="flex items-center gap-2">
                  <input
                    type="radio"
                    name="plantilla"
                    value={p.id}
                    checked={plantilla === p.id}
                    onChange={() => setPlantilla(p.id)}
                    className="size-4"
                  />
                  <span className="font-medium">{p.nombre}</span>
                  <span
                    aria-hidden="true"
                    className="ml-auto size-4 rounded-full ring-1 ring-border"
                    style={{ background: p.color ?? "#000000" }}
                  />
                </span>
                <span className="mt-1 block pl-6 text-sm text-muted">{p.descripcion}</span>
              </label>
            ))}
          </fieldset>

          <fieldset>
            <legend className="mb-1 text-lg font-medium">Formato</legend>
            <div className="flex gap-4">
              {(["docx", "pdf"] as Formato[]).map((f) => (
                <label key={f} className="flex min-h-11 items-center gap-2">
                  <input type="radio" name="formato" checked={formato === f} onChange={() => setFormato(f)} className="size-4" />
                  {f === "docx" ? "Word (.docx)" : "PDF"}
                </label>
              ))}
            </div>
          </fieldset>

          <fieldset>
            <legend className="mb-1 text-lg font-medium">Papel</legend>
            <div className="flex gap-4">
              {(["carta", "a4"] as Papel[]).map((x) => (
                <label key={x} className="flex min-h-11 items-center gap-2">
                  <input type="radio" name="papel" checked={papel === x} onChange={() => setPapel(x)} className="size-4" />
                  {x === "carta" ? "Carta" : "A4"}
                </label>
              ))}
            </div>
          </fieldset>

          <button type="button" className={btnPrimary} onClick={descargar} disabled={generando || !informe}>
            {generando ? "Generando…" : `Descargar ${formato === "docx" ? "Word" : "PDF"}`}
          </button>
        </div>

        <div>
          <h2 className="mb-2 text-lg font-medium">Vista previa</h2>
          {informe && actual ? (
            <HojaPrevia cv={informe.cv} p={actual} />
          ) : (
            <p className="text-muted">Cargando vista previa…</p>
          )}
          <p className="mt-2 text-xs text-muted">
            Es una vista aproximada: el archivo final puede variar un poco según el programa que lo abra.
          </p>
        </div>
      </div>
    </section>
  );
}
