import type { Metadata, Viewport } from "next";
import Link from "next/link";
import "./globals.css";

export const metadata: Metadata = {
  title: "TalentCV AI",
  description: "Crea currículums profesionales con inteligencia artificial local.",
};

export const viewport: Viewport = { width: "device-width", initialScale: 1 };

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    <html lang="es" className="h-full">
      <body className="min-h-full flex flex-col">
        <a
          href="#contenido"
          className="sr-only focus:not-sr-only focus:absolute focus:left-4 focus:top-4 focus:z-50 focus:rounded focus:bg-primary focus:px-4 focus:py-2 focus:text-primary-fg"
        >
          Saltar al contenido
        </a>
        <header className="border-b border-border bg-surface">
          <div className="mx-auto flex max-w-4xl items-center justify-between px-4 py-3">
            <Link href="/" className="text-lg font-semibold">
              TalentCV AI
            </Link>
            <nav aria-label="Principal" className="flex gap-1">
              <Link href="/" className="rounded px-3 py-2 text-sm hover:underline">
                Perfiles
              </Link>
              <Link href="/ia/" className="rounded px-3 py-2 text-sm hover:underline">
                IA local
              </Link>
              <Link href="/sistema/" className="rounded px-3 py-2 text-sm hover:underline">
                Sistema
              </Link>
            </nav>
          </div>
        </header>
        <main id="contenido" className="mx-auto w-full max-w-4xl flex-1 px-4 py-8">
          {children}
        </main>
        <footer className="border-t border-border px-4 py-4 text-center text-sm text-muted">
          Tus datos se guardan solo en este equipo.
        </footer>
      </body>
    </html>
  );
}
