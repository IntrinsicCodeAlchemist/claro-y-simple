/**
 * API client para comunicarse con el backend de Claro y Simple.
 * Maneja los endpoints POST /ingest y POST /analyze de API Gateway.
 */

import type {
  AnalyzeErrorCode,
  AnalyzeErrorResponse,
  AnalyzeSuccessResponse,
  IngestErrorCode,
  IngestErrorResponse,
  IngestSuccessResponse,
} from "../types/contract";

const BASE_URL = import.meta.env.VITE_API_BASE_URL as string;
const API_KEY = import.meta.env.VITE_API_KEY as string;

const NETWORK_ERROR_MESSAGE =
  "No se pudo conectar con el servidor. Verificá tu conexión a internet.";

// ---------------------------------------------------------------------------
// Error types
// ---------------------------------------------------------------------------

/** Error lanzado cuando POST /ingest responde con HTTP 4xx/5xx. */
export class ApiIngestError extends Error {
  readonly error_code: IngestErrorCode;
  readonly document_id?: string;

  constructor(response: IngestErrorResponse) {
    super(response.message);
    this.name = "ApiIngestError";
    this.error_code = response.error_code;
    this.document_id = response.document_id;
  }
}

/** Error lanzado cuando POST /analyze responde con HTTP 4xx/5xx. */
export class ApiAnalyzeError extends Error {
  readonly error_code: AnalyzeErrorCode;
  readonly document_id?: string;

  constructor(response: AnalyzeErrorResponse) {
    super(response.message);
    this.name = "ApiAnalyzeError";
    this.error_code = response.error_code;
    this.document_id = response.document_id;
  }
}

/** Error lanzado cuando fetch falla a nivel de red (sin respuesta del servidor). */
export class NetworkError extends Error {
  constructor() {
    super(NETWORK_ERROR_MESSAGE);
    this.name = "NetworkError";
  }
}

// ---------------------------------------------------------------------------
// API functions
// ---------------------------------------------------------------------------

/**
 * Sube un contrato PDF al backend para su extracción de texto.
 *
 * @param file - El archivo PDF a subir.
 * @returns La respuesta de éxito con el `document_id` generado.
 * @throws {ApiIngestError} Si el servidor responde con HTTP 4xx/5xx.
 * @throws {NetworkError} Si no se puede establecer conexión con el servidor.
 */
export async function uploadContract(
  file: File
): Promise<IngestSuccessResponse> {
  const formData = new FormData();
  formData.append("file", file);

  let response: Response;
  try {
    response = await fetch(`${BASE_URL}/ingest`, {
      method: "POST",
      headers: {
        "x-api-key": API_KEY,
      },
      body: formData,
    });
  } catch {
    throw new NetworkError();
  }

  if (!response.ok) {
    const errorBody = (await response.json()) as IngestErrorResponse;
    throw new ApiIngestError(errorBody);
  }

  return (await response.json()) as IngestSuccessResponse;
}

/**
 * Solicita el análisis de un contrato previamente ingestado.
 *
 * @param documentId - El UUID v4 del documento retornado por `uploadContract`.
 * @returns La respuesta de éxito con el análisis completo del contrato.
 * @throws {ApiAnalyzeError} Si el servidor responde con HTTP 4xx/5xx.
 * @throws {NetworkError} Si no se puede establecer conexión con el servidor.
 */
export async function analyzeContract(
  documentId: string
): Promise<AnalyzeSuccessResponse> {
  let response: Response;
  try {
    response = await fetch(`${BASE_URL}/analyze`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "x-api-key": API_KEY,
      },
      body: JSON.stringify({ document_id: documentId }),
    });
  } catch {
    throw new NetworkError();
  }

  if (!response.ok) {
    const errorBody = (await response.json()) as AnalyzeErrorResponse;
    throw new ApiAnalyzeError(errorBody);
  }

  return (await response.json()) as AnalyzeSuccessResponse;
}
