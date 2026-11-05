export type Enlace = { etiqueta: string; url: string };

export type ProfileInput = {
  nombre_completo: string;
  titular: string | null;
  email: string | null;
  telefono: string | null;
  ciudad: string | null;
  pais: string | null;
  enlaces: Enlace[];
  resumen: string | null;
};

export type Profile = ProfileInput & {
  id: string;
  creado_en: string;
  actualizado_en: string;
};

export type ProfileSummary = {
  id: string;
  nombre_completo: string;
  titular: string | null;
  actualizado_en: string;
};
