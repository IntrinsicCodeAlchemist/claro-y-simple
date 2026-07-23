import type { AnalyzeErrorCode, IngestErrorCode } from "@/types/contract";

/** Mensajes amigables para cada error_code de POST /ingest (Req 4.1–4.10) */
export const INGEST_ERROR_MESSAGES: Record<IngestErrorCode, string> = {
  MISSING_FILE: "No se recibió el archivo. Intentá de nuevo.",
  INVALID_FILE_TYPE:
    "El archivo no es un PDF válido. Verificá que sea un documento PDF.",
  FILE_TOO_LARGE: "El archivo es demasiado grande. El máximo es 10 MB.",
  EMPTY_EXTRACTION:
    "No se pudo extraer texto del PDF. Es posible que sea una imagen escaneada sin texto reconocible.",
  TEXTRACT_FAILURE:
    "Hubo un problema al procesar el documento. Intentá de nuevo en unos minutos.",
  S3_OBJECT_NOT_FOUND:
    "Hubo un problema al procesar el documento. Intentá de nuevo en unos minutos.",
  STORAGE_FAILURE:
    "No pudimos guardar tu archivo. Intentá de nuevo en unos minutos.",
  PERSISTENCE_FAILURE:
    "Hubo un error interno. Intentá de nuevo en unos minutos.",
  VALIDATION_FAILURE:
    "Hubo un error interno. Intentá de nuevo en unos minutos.",
  INTERNAL_ERROR: "Ocurrió un error inesperado. Intentá de nuevo más tarde.",
};

/** Mensajes amigables para cada error_code de POST /analyze (Req 5.1–5.10) */
export const ANALYZE_ERROR_MESSAGES: Record<AnalyzeErrorCode, string> = {
  MISSING_DOCUMENT_ID:
    "Hubo un error interno. Intentá subir el contrato de nuevo.",
  INVALID_DOCUMENT_ID:
    "Hubo un error interno. Intentá subir el contrato de nuevo.",
  DOCUMENT_NOT_FOUND:
    "No encontramos el documento. Es posible que haya expirado. Intentá subirlo de nuevo.",
  CONTEXT_TOO_LONG:
    "El contrato es demasiado extenso para analizar. Intentá con un documento más corto.",
  MODEL_RESPONSE_INVALID:
    "El análisis no se pudo completar correctamente. Intentá de nuevo.",
  BEDROCK_TIMEOUT:
    "El análisis está tardando demasiado. Intentá de nuevo en unos minutos.",
  BEDROCK_THROTTLED:
    "Hay muchas solicitudes en este momento. Intentá de nuevo en unos minutos.",
  BEDROCK_SERVICE_ERROR:
    "El servicio de análisis no está disponible. Intentá de nuevo más tarde.",
  PERSISTENCE_FAILURE:
    "Hubo un error al guardar el análisis. Intentá de nuevo en unos minutos.",
  INTERNAL_ERROR: "Ocurrió un error inesperado. Intentá de nuevo más tarde.",
};
