import type { Metadata } from "next";
import { Suspense } from "react";
import { ReviewPanel } from "@/components/ReviewPanel";

export const metadata: Metadata = { title: "Revisar datos · TalentCV AI" };

// El perfil va en la query (?perfil=...): con exportación estática no hay rutas dinámicas sin generar.
export default function RevisionPage() {
  return (
    <Suspense fallback={<p className="text-muted">Cargando…</p>}>
      <ReviewPanel />
    </Suspense>
  );
}
