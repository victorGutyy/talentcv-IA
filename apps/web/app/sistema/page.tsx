import type { Metadata } from "next";
import { SistemaPanel } from "@/components/SistemaPanel";

export const metadata: Metadata = { title: "Sistema · TalentCV AI" };

export default function SistemaPage() {
  return <SistemaPanel />;
}
