"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import { ApiError, api, initToken } from "@/lib/api";
import type { ProfileSummary } from "@/lib/types";
import { ConfirmDialog } from "./ConfirmDialog";
import { btnPrimary, btnSecondary, cardClass } from "./ui";

const fecha = (iso: string) =>
  new Date(iso).toLocaleString("es", { dateStyle: "medium", timeStyle: "short" });

export function ProfileList() {
  const [perfiles, setPerfiles] = useState<ProfileSummary[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [aviso, setAviso] = useState("");
  const [aEliminar, setAEliminar] = useState<ProfileSummary | null>(null);
  const [eliminando, setEliminando] = useState(false);

  const cargar = useCallback(async () => {
    setError(null);
    try {
      setPerfiles(await api.listar());
    } catch (e) {
      setPerfiles(null);
      setError(e instanceof ApiError ? e.message : "Error inesperado.");
    }
  }, []);

  useEffect(() => {
    if (!initToken()) {
      // eslint-disable-next-line react-hooks/set-state-in-effect
      setError("No hay sesión activa. Abre TalentCV AI desde su acceso directo.");
      return;
    }
    void cargar();
  }, [cargar]);

  async function duplicar(p: ProfileSummary) {
    try {
      const copia = await api.duplicar(p.id);
      setAviso(`Se creó «${copia.nombre_completo}».`);
      await cargar();
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Error inesperado.");
    }
  }

  async function confirmarEliminar() {
    if (!aEliminar) return;
    setEliminando(true);
    try {
      await api.eliminar(aEliminar.id);
      setAviso(`Se eliminó «${aEliminar.nombre_completo}».`);
      setAEliminar(null);
      await cargar();
    } catch (e) {
      setAEliminar(null);
      setError(e instanceof ApiError ? e.message : "Error inesperado.");
      await cargar();
    } finally {
      setEliminando(false);
    }
  }

  return (
    <section aria-labelledby="titulo-perfiles">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h1 id="titulo-perfiles" className="text-2xl font-semibold">
          Mis perfiles
        </h1>
        <Link href="/perfil/" className={btnPrimary}>
          Nuevo perfil
        </Link>
      </div>

      <p role="status" aria-live="polite" className={aviso ? "mt-4 rounded-md bg-success-bg p-3 text-success" : "sr-only"}>
        {aviso}
      </p>

      {error && (
        <div role="alert" className="mt-4 rounded-md bg-danger-bg p-3 text-danger">
          {error}
        </div>
      )}

      {perfiles === null && !error && <p className="mt-6 text-muted">Cargando perfiles…</p>}

      {perfiles?.length === 0 && (
        <div className={`${cardClass} mt-6 text-center`}>
          <p className="font-medium">Todavía no tienes perfiles.</p>
          <p className="mt-1 text-muted">Crea el primero para empezar a armar tu currículum.</p>
        </div>
      )}

      {perfiles && perfiles.length > 0 && (
        <ul className="mt-6 space-y-3">
          {perfiles.map((p) => (
            <li key={p.id} className={`${cardClass} flex flex-wrap items-center justify-between gap-3`}>
              <div className="min-w-0">
                <h2 className="truncate text-lg font-medium">{p.nombre_completo}</h2>
                {p.titular && <p className="truncate text-muted">{p.titular}</p>}
                <p className="text-sm text-muted">Actualizado: {fecha(p.actualizado_en)}</p>
              </div>
              <div className="flex flex-wrap gap-2">
                <Link
                  href={`/perfil/?id=${encodeURIComponent(p.id)}`}
                  className={btnSecondary}
                  aria-label={`Editar ${p.nombre_completo}`}
                >
                  Editar
                </Link>
                <Link
                  href={`/documentos/?perfil=${encodeURIComponent(p.id)}`}
                  className={btnSecondary}
                  aria-label={`Documentos de ${p.nombre_completo}`}
                >
                  Documentos
                </Link>
                <Link
                  href={`/revision/?perfil=${encodeURIComponent(p.id)}`}
                  className={btnSecondary}
                  aria-label={`Revisar datos de ${p.nombre_completo}`}
                >
                  Revisar datos
                </Link>
                <Link
                  href={`/entrevista/?perfil=${encodeURIComponent(p.id)}`}
                  className={btnSecondary}
                  aria-label={`Completar información de ${p.nombre_completo}`}
                >
                  Completar
                </Link>
                <Link
                  href={`/redaccion/?perfil=${encodeURIComponent(p.id)}`}
                  className={btnSecondary}
                  aria-label={`Redactar el currículum de ${p.nombre_completo}`}
                >
                  Redactar
                </Link>
                <Link
                  href={`/exportar/?perfil=${encodeURIComponent(p.id)}`}
                  className={btnSecondary}
                  aria-label={`Exportar el currículum de ${p.nombre_completo}`}
                >
                  Exportar
                </Link>
                <Link
                  href={`/versiones/?perfil=${encodeURIComponent(p.id)}`}
                  className={btnSecondary}
                  aria-label={`Versiones del currículum de ${p.nombre_completo}`}
                >
                  Versiones
                </Link>
                <button
                  type="button"
                  className={btnSecondary}
                  onClick={() => duplicar(p)}
                  aria-label={`Duplicar ${p.nombre_completo}`}
                >
                  Duplicar
                </button>
                <button
                  type="button"
                  className={btnSecondary}
                  onClick={() => setAEliminar(p)}
                  aria-label={`Eliminar ${p.nombre_completo}`}
                >
                  Eliminar
                </button>
              </div>
            </li>
          ))}
        </ul>
      )}

      <ConfirmDialog
        open={aEliminar !== null}
        title="¿Eliminar este perfil?"
        description={`Se borrará «${aEliminar?.nombre_completo ?? ""}» de este equipo. Esta acción no se puede deshacer.`}
        confirmLabel="Eliminar"
        busy={eliminando}
        onConfirm={confirmarEliminar}
        onCancel={() => setAEliminar(null)}
      />
    </section>
  );
}
