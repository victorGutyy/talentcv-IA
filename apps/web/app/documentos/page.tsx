import type { Metadata } from "next";
import { Suspense } from "react";
import { DocumentsPanel } from "@/components/DocumentsPanel";

export const metadata: Metadata = { title: "Documentos · TalentCV AI" };

// El perfil va en la query (?perfil=...): con exportación estática no hay rutas dinámicas sin generar.
export default function DocumentosPage() {
  return (
    <Suspense fallback={<p className="text-muted">Cargando…</p>}>
      <DocumentsPanel />
    </Suspense>
  );
}
