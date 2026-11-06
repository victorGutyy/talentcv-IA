"use client";

import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { useEffect, useState } from "react";
import { ApiError, documentos, exportacion, initToken } from "@/lib/api";
import type { Informe, Plantilla } from "@/lib/types";
import { descargarBlob } from "@/lib/download";
import { HojaCv } from "./HojaCv";
import { btnPrimary, cardClass } from "./ui";

const mensaje = (e: unknown) => (e instanceof ApiError ? e.message : "Error inesperado.");

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
      const { blob, nombre, version } = await exportacion.exportar(perfilId, plantilla, formato, papel);
      const r = await descargarBlob(blob, nombre);
      const enHistorial = version ? ` Quedó guardado en tu historial como versión ${version}.` : "";
      if (!r.ok && r.cancelado) {
        setAviso(`No se guardó el archivo (cancelaste).${enHistorial}`);
      } else if (!r.ok) {
        setError(r.error ?? "No se pudo guardar el archivo.");
      } else {
        setAviso(
          (r.ruta ? `Se guardó «${r.ruta}».` : `Se generó «${nombre}».`) + enHistorial + " Ábrelo y revísalo antes de enviarlo.",
        );
      }
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
          <p className="text-sm text-muted">
            Cada descarga guarda una versión en tu historial.{" "}
            <Link href={`/versiones/${qs}`} className="underline">
              Ver historial de versiones
            </Link>
          </p>
        </div>

        <div>
          <h2 className="mb-2 text-lg font-medium">Vista previa</h2>
          {informe && actual ? (
            <HojaCv cv={informe.cv} p={actual} />
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
