import type { Metadata } from "next";
import { Suspense } from "react";
import { InterviewPanel } from "@/components/InterviewPanel";

export const metadata: Metadata = { title: "Completar información · TalentCV AI" };

// El perfil va en la query (?perfil=...): con exportación estática no hay rutas dinámicas sin generar.
export default function EntrevistaPage() {
  return (
    <Suspense fallback={<p className="text-muted">Cargando…</p>}>
      <InterviewPanel />
    </Suspense>
  );
}
