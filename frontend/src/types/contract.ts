// Types derived from interface-contracts.md — do not modify without team approval

// --- Contrato 2: Analysis data types ---

export type ClauseCategory =
  | "renovacion_automatica"
  | "multa"
  | "jurisdiccion"
  | "cesion_datos"
  | "otro";

export type RiskLevel = "bajo" | "medio" | "alto";

export interface Clause {
  clause_text: string;
  category: ClauseCategory;
  risk_level: RiskLevel;
  explanation: string;
  suggested_question: string;
}

export interface AnalysisResult {
  document_id: string;
  summary_plain: string;
  risk_score: number; // entero 0-100
  clauses: Clause[];
  overall_recommendation: string;
}

// --- Contrato 3: POST /ingest response types ---

export type IngestErrorCode =
  | "MISSING_FILE"
  | "INVALID_FILE_TYPE"
  | "FILE_TOO_LARGE"
  | "EMPTY_EXTRACTION"
  | "TEXTRACT_FAILURE"
  | "S3_OBJECT_NOT_FOUND"
  | "STORAGE_FAILURE"
  | "PERSISTENCE_FAILURE"
  | "VALIDATION_FAILURE"
  | "INTERNAL_ERROR";

export interface IngestSuccessResponse {
  document_id: string;
}

export interface IngestErrorResponse {
  error_code: IngestErrorCode;
  message: string;
  document_id?: string; // solo presente cuando error_code === "EMPTY_EXTRACTION"
}

/** Tipo unión para el resultado de POST /ingest — usar con discriminación por status HTTP */
export type IngestResponse = IngestSuccessResponse | IngestErrorResponse;

// --- Contrato 4: POST /analyze response types ---

export type AnalyzeErrorCode =
  | "MISSING_DOCUMENT_ID"
  | "INVALID_DOCUMENT_ID"
  | "DOCUMENT_NOT_FOUND"
  | "CONTEXT_TOO_LONG"
  | "MODEL_RESPONSE_INVALID"
  | "BEDROCK_TIMEOUT"
  | "BEDROCK_THROTTLED"
  | "BEDROCK_SERVICE_ERROR"
  | "PERSISTENCE_FAILURE"
  | "INTERNAL_ERROR";

export interface AnalyzeSuccessResponse {
  document_id: string;
  summary_plain: string;
  risk_score: number; // entero 0-100
  clauses: Clause[];
  overall_recommendation: string;
  cached: boolean; // false = análisis fresco, true = resultado cacheado
}

export interface AnalyzeErrorResponse {
  error_code: AnalyzeErrorCode;
  message: string;
  document_id?: string;
}

/** Tipo unión para el resultado de POST /analyze — usar con discriminación por status HTTP */
export type AnalyzeResponse = AnalyzeSuccessResponse | AnalyzeErrorResponse;
