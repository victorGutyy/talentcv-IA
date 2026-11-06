"use client";

import { useEffect, useRef } from "react";
import { btnDanger, btnSecondary } from "./ui";

type Props = {
  open: boolean;
  title: string;
  description: string;
  confirmLabel: string;
  busy?: boolean;
  onConfirm: () => void;
  onCancel: () => void;
};

/** Diálogo modal nativo: atrapa el foco, se cierra con Esc y se anuncia a lectores de pantalla. */
export function ConfirmDialog({ open, title, description, confirmLabel, busy, onConfirm, onCancel }: Props) {
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
      aria-labelledby="dlg-titulo"
      aria-describedby="dlg-desc"
      className="m-auto w-[min(28rem,calc(100vw-2rem))] rounded-lg border border-border bg-surface p-6 text-foreground backdrop:bg-black/50"
    >
      <h2 id="dlg-titulo" className="text-lg font-semibold">
        {title}
      </h2>
      <p id="dlg-desc" className="mt-2 text-muted">
        {description}
      </p>
      <div className="mt-6 flex justify-end gap-3">
        <button type="button" className={btnSecondary} onClick={onCancel} autoFocus>
          Cancelar
        </button>
        <button type="button" className={btnDanger} onClick={onConfirm} disabled={busy}>
          {busy ? "Eliminando…" : confirmLabel}
        </button>
      </div>
    </dialog>
  );
}
