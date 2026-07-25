import { useState } from "react";
import { useNavigate } from "react-router-dom";
import {
  uploadContract,
  analyzeContract,
  ApiIngestError,
  ApiAnalyzeError,
  NetworkError,
} from "../api/client";
import { UploadZone } from "../components/UploadZone";
import {
  INGEST_ERROR_MESSAGES,
  ANALYZE_ERROR_MESSAGES,
} from "../constants/errorMessages";
import type { AnalyzeErrorCode, AnalyzeSuccessResponse } from "../types/contract";

// ---------------------------------------------------------------------------
// Transient analyze error codes — retrying with the same documentId is reasonable
// ---------------------------------------------------------------------------

const TRANSIENT_ANALYZE_ERRORS = new Set<AnalyzeErrorCode>([
  "MODEL_RESPONSE_INVALID",
  "BEDROCK_TIMEOUT",
  "BEDROCK_THROTTLED",
  "BEDROCK_SERVICE_ERROR",
  "PERSISTENCE_FAILURE",
  "INTERNAL_ERROR",
]);

// ---------------------------------------------------------------------------
// State machine types
// ---------------------------------------------------------------------------

interface ErrorDisplay {
  message: string;
  isAnalysisError: boolean;
  documentId?: string;
}

type HomeState =
  | { phase: "idle" }
  | { phase: "uploading" }
  | { phase: "analyzing"; documentId: string }
  | { phase: "error"; errorInfo: ErrorDisplay; retryAction: () => void };

// ---------------------------------------------------------------------------
// Spinner sub-component
// ---------------------------------------------------------------------------

function LoadingSpinner({ label }: { label: string }) {
  return (
    <div className="flex flex-col items-center justify-center gap-4">
      <div className="flex items-center gap-3">
        <div
          className="animate-spin border-2 rounded-full w-6 h-6 border-blue-600 border-t-transparent"
          role="status"
          aria-label="Cargando"
        />
        <p className="text-base text-gray-700">{label}</p>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Home page
// ---------------------------------------------------------------------------

/**
 * Página principal. Orquesta el flujo completo de carga y análisis de contrato.
 *
 * Máquina de estados: idle → uploading → analyzing → (navigate to /results)
 *                                                   ↘ error
 *
 * Requisitos: 1.5, 2.1–2.3, 3.1–3.3, 4.1–4.11, 5.1–5.12
 */
export function Home() {
  const navigate = useNavigate();
  const [state, setState] = useState<HomeState>({ phase: "idle" });

  const isLoading =
    state.phase === "uploading" || state.phase === "analyzing";

  async function handleFileSelected(file: File): Promise<void> {
    // Step 1: transition to uploading
    setState({ phase: "uploading" });

    let documentId: string;

    try {
      const ingestResult = await uploadContract(file);
      documentId = ingestResult.document_id;
    } catch (err) {
      let message: string;
      if (err instanceof ApiIngestError) {
        message = INGEST_ERROR_MESSAGES[err.error_code];
      } else if (err instanceof NetworkError) {
        message = err.message;
      } else {
        message =
          err instanceof Error
            ? err.message
            : "No se pudo subir el archivo. Intentá de nuevo.";
      }
      setState({
        phase: "error",
        errorInfo: { message, isAnalysisError: false },
        retryAction: () => setState({ phase: "idle" }),
      });
      return;
    }

    // Step 2: transition to analyzing
    setState({ phase: "analyzing", documentId });

    await invokeAnalyze(documentId);
  }

  async function invokeAnalyze(documentId: string): Promise<void> {
    let analysis: AnalyzeSuccessResponse;

    try {
      analysis = await analyzeContract(documentId);
    } catch (err) {
      let message: string;
      let retryAction: () => void;

      if (err instanceof ApiAnalyzeError) {
        message = ANALYZE_ERROR_MESSAGES[err.error_code];

        if (TRANSIENT_ANALYZE_ERRORS.has(err.error_code)) {
          // Transient error — retry re-invokes analyze with the same documentId
          retryAction = () => {
            setState({ phase: "analyzing", documentId });
            void invokeAnalyze(documentId);
          };
        } else {
          // Document error — retry goes back to idle so user can re-upload
          retryAction = () => setState({ phase: "idle" });
        }
      } else if (err instanceof NetworkError) {
        // Network errors are transient — retry re-invokes analyze
        message = err.message;
        retryAction = () => {
          setState({ phase: "analyzing", documentId });
          void invokeAnalyze(documentId);
        };
      } else {
        message =
          err instanceof Error
            ? err.message
            : "No se pudo analizar el contrato. Intentá de nuevo.";
        retryAction = () => {
          setState({ phase: "analyzing", documentId });
          void invokeAnalyze(documentId);
        };
      }

      setState({
        phase: "error",
        errorInfo: { message, isAnalysisError: true, documentId },
        retryAction,
      });
      return;
    }

    // Success — navigate to results page passing analysis data
    navigate("/results", { state: { analysis } });
  }

  return (
    <div className="min-h-screen bg-gray-50 font-sans">
      <div className="max-w-xl mx-auto px-4 py-16 flex flex-col gap-8">

        {/* Header */}
        <header className="text-center">
          <h1 className="text-3xl font-bold text-gray-900">Claro y Simple</h1>
          <p className="mt-2 text-base text-gray-500">
            Entendé lo que firmás. Subí tu contrato y te explicamos qué dice en
            lenguaje simple.
          </p>
        </header>

        {/* Upload zone — always rendered; disabled when loading or error */}
        <UploadZone
          onFileSelected={handleFileSelected}
          disabled={isLoading}
        />

        {/* Loading states */}
        {state.phase === "uploading" && (
          <LoadingSpinner label="Subiendo tu contrato..." />
        )}

        {state.phase === "analyzing" && (
          <LoadingSpinner label="Analizando tu contrato... Esto puede tomar unos segundos" />
        )}

        {/* Error state with differentiated retry behavior */}
        {state.phase === "error" && (
          <div
            role="alert"
            className="flex flex-col items-center gap-4 rounded-xl border border-red-200 bg-red-50 px-5 py-6 text-center"
          >
            <p className="text-sm text-red-700">{state.errorInfo.message}</p>
            <button
              type="button"
              onClick={state.retryAction}
              className="
                px-5 py-2 rounded-lg
                bg-blue-600 text-white text-sm font-medium
                hover:bg-blue-700 active:bg-blue-800
                focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-2
                transition-colors duration-150
              "
            >
              Intentar de nuevo
            </button>
          </div>
        )}

      </div>
    </div>
  );
}

export default Home;
