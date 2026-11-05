import type { NextConfig } from "next";

// La interfaz se exporta como sitio estático (carpeta "out") y la sirve el backend
// local. No hay servidor Node en la aplicación instalada.
const nextConfig: NextConfig = {
  output: "export",
  trailingSlash: true, // /perfil/ -> perfil/index.html
  images: { unoptimized: true },
  turbopack: {
    rules: {
      "*.css": {
        loaders: ["@tailwindcss/turbopack"],
        as: "*.css",
      },
    },
  },
};

export default nextConfig;
