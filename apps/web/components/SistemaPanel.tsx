"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { ApiError, initToken, sistema } from "@/lib/api";
import { elegirCarpeta, descargarBlob, puedeElegirCarpeta } from "@/lib/download";
import type { InfoSistema, PaqueteActualizacion, ResultadoRestauracion } from "@/lib/types";
import { ConfirmDialog } from "./ConfirmDialog";
import { btnPrimary, btnSecondary, cardClass, inputClass } from "./ui";

const mensaje = (e: unknown) => (e instanceof ApiError ? e.message : "Error inesperado.");
const MIN_CONTRASENA = 8;

export function SistemaPanel() {
  const [info, setInfo] = useState<InfoSistema | null>(null);
  const [error, setError] = useState<string | null>(null);

  // --- copia de seguridad
  const [clave, setClave] = useState("");
  const [clave2, setClave2] = useState("");
  const [creando, setCreando] = useState(false);
  const [avisoCopia, setAvisoCopia] = useState("");
  const [errorCopia, setErrorCopia] = useState("");

  // --- restaurar
  const [archivo, setArchivo] = useState<File | null>(null);
  const [claveRestaurar, setClaveRestaurar] = useState("");
  const [confirmaRestaurar, setConfirmaRestaurar] = useState(false);
  const [restaurando, setRestaurando] = useState(false);
  const [restaurada, setRestaurada] = useState<ResultadoRestauracion | null>(null);
  const [errorRestaurar, setErrorRestaurar] = useState("");

  // --- actualizaciones
  const [ruta, setRuta] = useState("");
  const [paquetes, setPaquetes] = useState<PaqueteActualizacion[] | null>(null);
  const [buscando, setBuscando] = useState(false);
  const [aInstalar, setAInstalar] = useState<PaqueteActualizacion | null>(null);
  const [instalando, setInstalando] = useState(false);
  const [instalada, setInstalada] = useState("");
  const [errorAct, setErrorAct] = useState("");

  // pywebview se inyecta después de cargar la página: se vuelve a comprobar cuando avisa de que está listo.
  const [escritorio, setEscritorio] = useState(false);
  useEffect(() => {
    const comprobar = () => setEscritorio(puedeElegirCarpeta());
    comprobar();
    window.addEventListener("pywebviewready", comprobar);
    return () => window.removeEventListener("pywebviewready", comprobar);
  }, []);

  useEffect(() => {
    if (!initToken()) {
      // eslint-disable-next-line react-hooks/set-state-in-effect
      setError("No hay sesión activa. Abre TalentCV AI desde su acceso directo.");
      return;
    }
    sistema.version().then(setInfo).catch((e) => setError(mensaje(e)));
  }, []);

  // ------------------------------------------------------------ copia
  async function crearCopia() {
    setErrorCopia("");
    setAvisoCopia("");
    if (clave && clave.length < MIN_CONTRASENA) return setErrorCopia(`La contraseña debe tener al menos ${MIN_CONTRASENA} caracteres.`);
    if (clave !== clave2) return setErrorCopia("Las dos contraseñas no coinciden.");
    setCreando(true);
    try {
      const { blob, nombre } = await sistema.copia(clave || null);
      const r = await descargarBlob(blob, nombre);
      if (!r.ok && r.cancelado) setAvisoCopia("No se guardó la copia (cancelaste).");
      else if (!r.ok) setErrorCopia(r.error ?? "No se pudo guardar la copia.");
      else
        setAvisoCopia(
          (r.ruta ? `Copia guardada en «${r.ruta}».` : `Se generó «${nombre}».`) +
            (clave ? " Está protegida con tu contraseña." : " No tiene contraseña: guárdala en un lugar seguro."),
        );
    } catch (e) {
      setErrorCopia(mensaje(e));
    } finally {
      setCreando(false);
    }
  }

  // ------------------------------------------------------------ restaurar
  async function restaurar() {
    if (!archivo) return;
    setErrorRestaurar("");
    setRestaurando(true);
    try {
      setRestaurada(await sistema.restaurar(archivo, claveRestaurar));
      setConfirmaRestaurar(false);
      setArchivo(null);
      setClaveRestaurar("");
    } catch (e) {
      setConfirmaRestaurar(false);
      setErrorRestaurar(mensaje(e));
    } finally {
      setRestaurando(false);
    }
  }

  // ------------------------------------------------------------ actualizaciones
  async function buscar() {
    setErrorAct("");
    setBuscando(true);
    try {
      setPaquetes(await sistema.buscarActualizaciones());
    } catch (e) {
      setErrorAct(mensaje(e));
    } finally {
      setBuscando(false);
    }
  }

  async function comprobarRuta(r: string) {
    setErrorAct("");
    setBuscando(true);
    try {
      setPaquetes([await sistema.verificarActualizacion(r)]);
    } catch (e) {
      setErrorAct(mensaje(e));
    } finally {
      setBuscando(false);
    }
  }

  async function elegir() {
    const r = await elegirCarpeta();
    if (!r) return;
    if ("error" in r) return setErrorAct(r.error);
    setRuta(r.ruta);
    await comprobarRuta(r.ruta);
  }

  async function instalar() {
    if (!aInstalar) return;
    setInstalando(true);
    try {
      const r = await sistema.instalarActualizacion(aInstalar.ruta);
      setAInstalar(null);
      setInstalada(`Instalando la versión ${r.version ?? ""}. La aplicación se cerrará y volverá a abrirse sola.`);
    } catch (e) {
      setAInstalar(null);
      setErrorAct(mensaje(e));
    } finally {
      setInstalando(false);
    }
  }

  return (
    <section aria-labelledby="titulo-sis" className="space-y-6">
      <h1 id="titulo-sis" className="text-2xl font-semibold">
        Sistema
      </h1>

      {error && (
        <div role="alert" className="rounded-md bg-danger-bg p-3 text-danger">
          {error}
        </div>
      )}

      <div className={cardClass}>
        <h2 className="text-lg font-medium">Esta instalación</h2>
        {!info && !error && <p className="mt-2 text-muted">Comprobando…</p>}
        {info && (
          <dl className="mt-3 grid gap-x-6 gap-y-1 text-sm sm:grid-cols-[auto_1fr]">
            <dt className="text-muted">Versión</dt>
            <dd>{info.version}</dd>
            <dt className="text-muted">Tus datos están en</dt>
            <dd className="break-all">{info.datos}</dd>
          </dl>
        )}
        <p className="mt-3 text-sm text-muted">
          Todo se guarda solo en este equipo. Para revisar el motor de IA, ve a <Link href="/ia/" className="underline">IA local</Link>.
        </p>
      </div>

      {/* ------------------------------------------------------------ copia */}
      <div className={cardClass}>
        <h2 className="text-lg font-medium">Copia de seguridad</h2>
        <p className="mt-1 text-sm text-muted">
          Guarda un archivo con todos tus perfiles, documentos y versiones. Sirve para pasar tus datos a otro equipo o recuperarlos si algo falla.
        </p>
        <div className="mt-4 grid gap-4 sm:grid-cols-2">
          <div>
            <label htmlFor="copia-clave" className="block text-sm font-medium">
              Contraseña (opcional)
            </label>
            <input
              id="copia-clave"
              type="password"
              autoComplete="new-password"
              className={`${inputClass} mt-1`}
              value={clave}
              onChange={(e) => setClave(e.target.value)}
              aria-describedby="copia-ayuda"
            />
          </div>
          <div>
            <label htmlFor="copia-clave2" className="block text-sm font-medium">
              Repite la contraseña
            </label>
            <input
              id="copia-clave2"
              type="password"
              autoComplete="new-password"
              className={`${inputClass} mt-1`}
              value={clave2}
              onChange={(e) => setClave2(e.target.value)}
              disabled={clave === ""}
            />
          </div>
        </div>
        <p id="copia-ayuda" className="mt-2 text-sm text-muted">
          Con contraseña, la copia queda cifrada (mínimo {MIN_CONTRASENA} caracteres). <strong>Si la olvidas, no hay forma de recuperarla.</strong>
        </p>
        <button type="button" className={`${btnPrimary} mt-4`} onClick={crearCopia} disabled={creando}>
          {creando ? "Creando la copia…" : "Crear copia de seguridad"}
        </button>
        {errorCopia && (
          <p role="alert" className="mt-3 rounded-md bg-danger-bg p-3 text-danger">
            {errorCopia}
          </p>
        )}
        <p role="status" className="mt-3 text-sm">
          {avisoCopia}
        </p>
      </div>

      {/* ------------------------------------------------------------ restaurar */}
      <div className={cardClass}>
        <h2 className="text-lg font-medium">Restaurar una copia</h2>
        <p className="mt-1 text-sm text-muted">
          Reemplaza lo que hay ahora en la aplicación por el contenido de la copia. Antes de hacerlo se guarda automáticamente una copia del estado actual.
        </p>
        <div className="mt-4 grid gap-4 sm:grid-cols-2">
          <div>
            <label htmlFor="rest-archivo" className="block text-sm font-medium">
              Archivo de la copia (.tcvbackup)
            </label>
            <input
              id="rest-archivo"
              type="file"
              accept=".tcvbackup"
              className={`${inputClass} mt-1`}
              onChange={(e) => {
                setArchivo(e.target.files?.[0] ?? null);
                setRestaurada(null);
                setErrorRestaurar("");
              }}
            />
          </div>
          <div>
            <label htmlFor="rest-clave" className="block text-sm font-medium">
              Contraseña (solo si la protegiste)
            </label>
            <input
              id="rest-clave"
              type="password"
              autoComplete="off"
              className={`${inputClass} mt-1`}
              value={claveRestaurar}
              onChange={(e) => setClaveRestaurar(e.target.value)}
            />
          </div>
        </div>
        <button
          type="button"
          className={`${btnSecondary} mt-4`}
          disabled={!archivo || restaurando}
          onClick={() => setConfirmaRestaurar(true)}
        >
          Restaurar esta copia…
        </button>
        {errorRestaurar && (
          <p role="alert" className="mt-3 rounded-md bg-danger-bg p-3 text-danger">
            {errorRestaurar}
          </p>
        )}
        {restaurada && (
          <div role="status" className="mt-3 space-y-1 rounded-md bg-success-bg p-3 text-success">
            <p className="font-medium">
              Copia restaurada: {restaurada.perfiles} {restaurada.perfiles === 1 ? "perfil" : "perfiles"} y {restaurada.documentos}{" "}
              {restaurada.documentos === 1 ? "documento" : "documentos"}.
            </p>
            <p className="text-sm break-all">Tus datos anteriores quedaron guardados en: {restaurada.copia_previa}</p>
            <p className="text-sm">
              <Link href="/" className="underline">
                Ir a mis perfiles
              </Link>
            </p>
          </div>
        )}
      </div>

      {/* ------------------------------------------------------------ actualizaciones */}
      <div className={cardClass}>
        <h2 className="text-lg font-medium">Actualizar la aplicación</h2>
        <p className="mt-1 text-sm text-muted">
          Conecta la memoria USB con la actualización y pulsa «Buscar en las unidades». Solo se instalan paquetes con la firma de TalentCV AI;
          nada se descarga de internet.
        </p>
        <div className="mt-4 flex flex-wrap gap-3">
          <button type="button" className={btnPrimary} onClick={buscar} disabled={buscando}>
            {buscando ? "Buscando…" : "Buscar en las unidades"}
          </button>
          {escritorio && (
            <button type="button" className={btnSecondary} onClick={elegir} disabled={buscando}>
              Elegir una carpeta…
            </button>
          )}
        </div>
        {!escritorio && (
          <div className="mt-4">
            <label htmlFor="act-ruta" className="block text-sm font-medium">
              O escribe la carpeta del paquete
            </label>
            <div className="mt-1 flex flex-wrap gap-3">
              <input
                id="act-ruta"
                type="text"
                className={`${inputClass} max-w-md`}
                value={ruta}
                placeholder="E:\TalentCV-Actualizacion"
                onChange={(e) => setRuta(e.target.value)}
              />
              <button type="button" className={btnSecondary} onClick={() => comprobarRuta(ruta)} disabled={!ruta.trim() || buscando}>
                Comprobar
              </button>
            </div>
          </div>
        )}

        {errorAct && (
          <p role="alert" className="mt-3 rounded-md bg-danger-bg p-3 text-danger">
            {errorAct}
          </p>
        )}
        {instalada && (
          <p role="status" className="mt-3 rounded-md bg-success-bg p-3 font-medium text-success">
            {instalada}
          </p>
        )}

        <div aria-live="polite">
          {paquetes && paquetes.length === 0 && (
            <p className="mt-3 text-sm text-muted">No se encontró ninguna actualización en las unidades conectadas.</p>
          )}
          {paquetes && paquetes.length > 0 && (
            <ul className="mt-4 space-y-3">
              {paquetes.map((p) => (
                <li key={p.ruta} className="rounded-md border border-border p-3">
                  <p className="text-sm break-all text-muted">{p.ruta}</p>
                  {p.ok ? (
                    <>
                      <p className="mt-1 font-medium text-success">
                        <span aria-hidden="true">✔ </span>
                        Versión {p.version} lista para instalar
                      </p>
                      {p.notas && <p className="mt-1 text-sm whitespace-pre-line">{p.notas}</p>}
                      <button type="button" className={`${btnPrimary} mt-3`} onClick={() => setAInstalar(p)} disabled={instalando}>
                        Instalar la versión {p.version}…
                      </button>
                    </>
                  ) : (
                    <p className="mt-1 text-danger">
                      <span aria-hidden="true">✖ </span>
                      {p.mensaje}
                    </p>
                  )}
                </li>
              ))}
            </ul>
          )}
        </div>
      </div>

      <ConfirmDialog
        idBase="dlg-restaurar"
        open={confirmaRestaurar}
        title="¿Restaurar esta copia?"
        description="Se reemplazarán tus perfiles, documentos y versiones actuales por los de la copia. Lo que tienes ahora se guarda antes en una copia automática."
        confirmLabel="Sí, restaurar"
        busy={restaurando}
        busyLabel="Restaurando…"
        onConfirm={restaurar}
        onCancel={() => setConfirmaRestaurar(false)}
      />
      <ConfirmDialog
        idBase="dlg-actualizar"
        neutral
        open={aInstalar !== null}
        title={`¿Instalar la versión ${aInstalar?.version ?? ""}?`}
        description="La aplicación se cerrará, se actualizará y volverá a abrirse sola. Tus datos no se tocan. Termina lo que estés haciendo antes de continuar."
        confirmLabel="Sí, instalar"
        busy={instalando}
        busyLabel="Preparando…"
        onConfirm={instalar}
        onCancel={() => setAInstalar(null)}
      />
    </section>
  );
}
