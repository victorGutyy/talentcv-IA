import type { CvDatos, Plantilla } from "@/lib/types";

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
export function HojaCv({ cv, p }: { cv: CvDatos; p: Plantilla }) {
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
      role="group"
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
