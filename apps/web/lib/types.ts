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

export type EstadoIA = {
  disponible: boolean;
  proveedor: string;
  url: string;
  modelo: string;
  modelo_instalado: boolean;
  version: string | null;
  modelos: string[];
  error: string | null;
};

export type TareaEstado = "en_cola" | "ejecutando" | "completado" | "error" | "cancelado" | "interrumpido";

export type ResultadoDiagnostico = {
  modelo: string;
  ok: boolean;
  verificaciones: Record<string, boolean>;
  tokens_entrada: number;
  tokens_salida: number;
  tokens_por_segundo: number;
  segundos: number;
};

export type Tarea = {
  id: string;
  tipo: string;
  estado: TareaEstado;
  progreso: number;
  mensaje: string;
  // Depende del tipo de tarea (p. ej. ResultadoDiagnostico para «diagnostico_ia»).
  resultado: Record<string, unknown> | null;
  error: string | null;
};

export type Documento = {
  id: string;
  perfil_id: string;
  nombre: string;
  tipo: "pdf" | "docx" | "image";
  tamano: number;
  estado: "subido" | "leido" | "error";
  paginas: number;
  paginas_ocr: number[];
  error: string | null;
  creado_en: string;
};

export type Categoria = "contacto" | "experiencia" | "educacion" | "certificacion" | "idioma" | "habilidad" | "logro";
export type HechoDatos = Record<string, string | string[] | null>;

export type Hecho = {
  id: string;
  profile_id: string;
  document_id: string | null;
  origin: "documento" | "manual";
  category: Categoria;
  data: HechoDatos;
  original_data: HechoDatos | null;
  quote: string;
  page: number | null;
  dropped_fields: string[];
  from_ocr: boolean;
  status: "pendiente" | "confirmado" | "editado" | "rechazado";
  created_at: string;
  updated_at: string;
};

export type CampoPregunta = {
  key: string;
  label: string;
  tipo: "texto" | "area" | "lista" | "select";
  obligatorio: boolean;
  ayuda: string | null;
};

export type Pregunta = {
  id: string;
  tipo: "perfil" | "campos" | "nuevo" | "logro";
  categoria: string | null;
  texto: string;
  ayuda: string | null;
  contexto: string | null;
  opcional: boolean;
  campos: CampoPregunta[];
};

export type EstadoEntrevista = {
  siguiente: Pregunta | null;
  restantes: number;
  omitidas: number;
  pendientes_de_revision: number;
};

export type ProfileSummary = {
  id: string;
  nombre_completo: string;
  titular: string | null;
  actualizado_en: string;
};
