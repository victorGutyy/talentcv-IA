import type { Metadata } from "next";
import { IaStatus } from "@/components/IaStatus";

export const metadata: Metadata = { title: "IA local · TalentCV AI" };

export default function IaPage() {
  return <IaStatus />;
}
