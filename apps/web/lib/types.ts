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

export type InfoSistema = { version: string; datos: string; empaquetado: boolean };

export type ResultadoRestauracion = { perfiles: number; documentos: number; copia_previa: string; creada: string };

export type PaqueteActualizacion = {
  ruta: string;
  ok: boolean;
  motivo: "ok" | "sin_paquete" | "formato" | "firma" | "no_es_nueva" | "archivo" | "hash";
  mensaje: string;
  version: string | null;
  notas: string | null;
  fecha: string | null;
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

export type Borrador = {
  id: string;
  perfil_id: string;
  seccion: "resumen" | "logro";
  puesto_id: string | null;
  fuentes: string[];
  texto: string;
  origen: "ia" | "usuario";
  estado: "borrador" | "aprobado" | "rechazado";
  auditoria_ok: boolean;
  problemas: { tipo: string; detalle: string }[];
  avisos: string[];
  actualizado_en: string;
};

export type Plantilla = {
  id: string;
  nombre: string;
  descripcion: string;
  color: string | null;
  fuente: string;
  secciones: string[];
  orden: string[];
  titulos: Record<string, string>;
  cabecera_centrada: boolean;
  linea_bajo_titulos: boolean;
};

export type CvPuesto = { cargo: string; empresa: string | null; fechas: string | null; puntos: string[] };
export type CvDatos = {
  nombre: string;
  titular: string | null;
  contacto: { email: string | null; telefono: string | null; ubicacion: string | null; enlaces: string[] };
  resumen: string | null;
  experiencia: CvPuesto[];
  educacion: { titulo: string; institucion: string | null; fecha: string | null }[];
  habilidades: string[];
  idiomas: string[];
  certificaciones: { nombre: string; emisor: string | null; fecha: string | null }[];
  logros: string[];
};
export type Informe = { cv: CvDatos; advertencias: string[] };

export type Version = {
  id: string;
  perfil_id: string;
  numero: number;
  etiqueta: string | null;
  origen: "exportacion" | "manual";
  creada_en: string;
  exportaciones: { plantilla: string; formato: string; papel: string; fecha: string }[];
  contenido: { puestos: number; puntos: number; habilidades: number; tiene_resumen: boolean };
};
export type VersionDetalle = Version & { cv: CvDatos };
export type CambioVersion = {
  seccion: string;
  tipo: "agregado" | "quitado" | "cambiado";
  antes: string | null;
  despues: string | null;
};
export type ComparacionVersiones = { antes: string; despues: string; iguales: boolean; cambios: CambioVersion[] };

export type Comparacion = { coinciden: string[]; faltan: string[] };

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
