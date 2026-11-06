// Clases compartidas. Objetivos táctiles de al menos 44 px (min-h-11).
const base =
  "inline-flex min-h-11 items-center justify-center rounded-md px-4 py-2 text-sm font-medium disabled:cursor-not-allowed disabled:opacity-60";

export const btnPrimary = `${base} bg-primary text-primary-fg hover:bg-primary-hover`;
export const btnSecondary = `${base} border border-border bg-surface hover:bg-background`;
export const btnDanger = `${base} border border-danger text-danger hover:bg-danger-bg`;

export const inputClass =
  "block min-h-11 w-full rounded-md border border-border bg-surface px-3 py-2 text-base placeholder:text-muted aria-[invalid=true]:border-danger";

export const cardClass = "rounded-lg border border-border bg-surface p-4";
