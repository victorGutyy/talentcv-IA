import type { Metadata } from "next";
import { Suspense } from "react";
import { WritingPanel } from "@/components/WritingPanel";

export const metadata: Metadata = { title: "Redacción · TalentCV AI" };

// El perfil va en la query (?perfil=...): con exportación estática no hay rutas dinámicas sin generar.
export default function RedaccionPage() {
  return (
    <Suspense fallback={<p className="text-muted">Cargando…</p>}>
      <WritingPanel />
    </Suspense>
  );
}
