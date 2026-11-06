import type { Metadata } from "next";
import { Suspense } from "react";
import { ProfileForm } from "@/components/ProfileForm";

export const metadata: Metadata = { title: "Perfil · TalentCV AI" };

// El id va en la query (?id=...): con exportación estática no hay rutas dinámicas sin generar.
export default function PerfilPage() {
  return (
    <Suspense fallback={<p className="text-muted">Cargando…</p>}>
      <ProfileForm />
    </Suspense>
  );
}
