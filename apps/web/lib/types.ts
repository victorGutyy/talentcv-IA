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
  resultado: ResultadoDiagnostico | null;
  error: string | null;
};

export type ProfileSummary = {
  id: string;
  nombre_completo: string;
  titular: string | null;
  actualizado_en: string;
};
