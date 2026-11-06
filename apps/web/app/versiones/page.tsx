import type { Metadata } from "next";
import { Suspense } from "react";
import { VersionsPanel } from "@/components/VersionsPanel";

export const metadata: Metadata = { title: "Versiones · TalentCV AI" };

// El perfil va en la query (?perfil=...): con exportación estática no hay rutas dinámicas sin generar.
export default function VersionesPage() {
  return (
    <Suspense fallback={<p className="text-muted">Cargando…</p>}>
      <VersionsPanel />
    </Suspense>
  );
}
