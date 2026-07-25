import type { ClauseCategory } from "@/types/contract";

/** Etiquetas en español para cada categoría de cláusula (Req 7.3) */
export const CATEGORY_LABELS: Record<ClauseCategory, string> = {
  renovacion_automatica: "Renovación automática",
  multa: "Multa",
  jurisdiccion: "Jurisdicción",
  cesion_datos: "Cesión de datos",
  otro: "Otro",
};
