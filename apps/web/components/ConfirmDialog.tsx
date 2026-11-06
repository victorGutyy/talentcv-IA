"use client";

import { useEffect, useRef } from "react";
import { btnDanger, btnPrimary, btnSecondary } from "./ui";

type Props = {
  open: boolean;
  title: string;
  description: string;
  confirmLabel: string;
  busy?: boolean;
  busyLabel?: string;
  /** Acción que no borra nada (p. ej. instalar una actualización): el botón no se pinta como peligro. */
  neutral?: boolean;
  /** Prefijo de los ids: debe ser distinto si hay varios diálogos en la misma página. */
  idBase?: string;
  onConfirm: () => void;
  onCancel: () => void;
};

/** Diálogo modal nativo: atrapa el foco, se cierra con Esc y se anuncia a lectores de pantalla. */
export function ConfirmDialog({
  open,
  title,
  description,
  confirmLabel,
  busy,
  busyLabel = "Eliminando…",
  neutral,
  idBase = "dlg",
  onConfirm,
  onCancel,
}: Props) {
  const ref = useRef<HTMLDialogElement>(null);

  useEffect(() => {
    const dlg = ref.current;
    if (!dlg) return;
    if (open && !dlg.open) dlg.showModal();
    if (!open && dlg.open) dlg.close();
  }, [open]);

  return (
    <dialog
      ref={ref}
      onCancel={(e) => {
        e.preventDefault();
        onCancel();
      }}
      aria-labelledby={`${idBase}-titulo`}
      aria-describedby={`${idBase}-desc`}
      className="m-auto w-[min(28rem,calc(100vw-2rem))] rounded-lg border border-border bg-surface p-6 text-foreground backdrop:bg-black/50"
    >
      <h2 id={`${idBase}-titulo`} className="text-lg font-semibold">
        {title}
      </h2>
      <p id={`${idBase}-desc`} className="mt-2 text-muted">
        {description}
      </p>
      <div className="mt-6 flex justify-end gap-3">
        <button type="button" className={btnSecondary} onClick={onCancel} autoFocus>
          Cancelar
        </button>
        <button type="button" className={neutral ? btnPrimary : btnDanger} onClick={onConfirm} disabled={busy}>
          {busy ? busyLabel : confirmLabel}
        </button>
      </div>
    </dialog>
  );
}
