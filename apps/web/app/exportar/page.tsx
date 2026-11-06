import type { Metadata } from "next";
import { Suspense } from "react";
import { ExportPanel } from "@/components/ExportPanel";

export const metadata: Metadata = { title: "Exportar · TalentCV AI" };

// El perfil va en la query (?perfil=...): con exportación estática no hay rutas dinámicas sin generar.
export default function ExportarPage() {
  return (
    <Suspense fallback={<p className="text-muted">Cargando…</p>}>
      <ExportPanel />
    </Suspense>
  );
}
