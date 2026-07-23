import { useLocation, Navigate } from "react-router-dom";
import type { AnalyzeSuccessResponse } from "@/types/contract";
import { sortClausesByRisk } from "@/utils/riskDisplay";
import { RiskScore } from "@/components/RiskScore";
import { ClauseCard } from "@/components/ClauseCard";
import { SuggestedQuestions } from "@/components/SuggestedQuestions";

interface ResultsLocationState {
  analysis: AnalyzeSuccessResponse;
}

/**
 * Página de resultados del análisis de contrato.
 * Recibe AnalyzeSuccessResponse via useLocation().state (pasado desde Home.tsx).
 *
 * Secciones en orden (Req 10.1–10.3, 6.1–6.5, 7.7, 8.1–8.3, 12.1–12.3, 9.1–9.3):
 * 1. Nota de caché (condicional — si cached=true)
 * 2. Resumen (summary_plain)
 * 3. RiskScore (risk_score + clauses)
 * 4. Cláusulas ordenadas por gravedad (alto → medio → bajo) o mensaje positivo si vacío
 * 5. SuggestedQuestions (solo si hay cláusulas)
 * 6. Recomendación general (overall_recommendation)
 */
export function Results() {
  const location = useLocation();
  const state = location.state as ResultsLocationState | null;

  // Redirigir a / si no hay datos (navegación directa a /results sin análisis)
  if (!state?.analysis) {
    return <Navigate to="/" replace />;
  }

  const { analysis } = state;
  const {
    summary_plain,
    risk_score,
    clauses,
    overall_recommendation,
    cached,
  } = analysis;

  const hasClauses = clauses.length > 0;
  const sortedClauses = hasClauses ? sortClausesByRisk(clauses) : [];

  return (
    <div className="min-h-screen bg-gray-50 font-sans">
      <div className="max-w-2xl mx-auto px-4 py-8 flex flex-col gap-6">

        {/* Encabezado de página */}
        <header>
          <h1 className="text-2xl font-bold text-gray-900">
            Análisis de tu contrato
          </h1>
        </header>

        {/* 1. Nota de caché — Req 9.1–9.3: solo si cached=true, como info neutra */}
        {cached && (
          <div
            className="flex items-start gap-3 px-4 py-3 rounded-lg bg-blue-50 border border-blue-200"
            role="note"
            aria-label="Información sobre resultado cacheado"
          >
            {/* Ícono info */}
            <svg
              xmlns="http://www.w3.org/2000/svg"
              className="w-5 h-5 text-blue-500 mt-0.5 shrink-0"
              fill="none"
              viewBox="0 0 24 24"
              stroke="currentColor"
              strokeWidth={2}
              aria-hidden="true"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                d="M11.25 11.25l.041-.02a.75.75 0 011.063.852l-.708 2.836a.75.75 0 001.063.853l.041-.021M21 12a9 9 0 11-18 0 9 9 0 0118 0zm-9-3.75h.008v.008H12V8.25z"
              />
            </svg>
            <p className="text-sm text-blue-700">
              Este resultado corresponde a un análisis previo del mismo
              documento.
            </p>
          </div>
        )}

        {/* 2. Resumen — Req 10.1, 10.3: summary_plain antes de cláusulas individuales */}
        <section aria-labelledby="summary-title">
          <h2
            id="summary-title"
            className="text-lg font-semibold text-gray-900 mb-2"
          >
            Resumen
          </h2>
          <p className="text-base text-gray-700 leading-relaxed">
            {summary_plain}
          </p>
        </section>

        {/* 3. RiskScore — Req 6.1–6.5, 8.1–8.3 */}
        <RiskScore riskScore={risk_score} clauses={clauses} />

        {/* 4. Cláusulas — Req 7.7, 8.1–8.3 */}
        {hasClauses ? (
          <section aria-labelledby="clauses-title">
            <h2
              id="clauses-title"
              className="text-lg font-semibold text-gray-900 mb-3"
            >
              Cláusulas de riesgo
            </h2>
            <div className="flex flex-col gap-4">
              {sortedClauses.map((clause, index) => (
                <ClauseCard key={index} clause={clause} />
              ))}
            </div>
          </section>
        ) : (
          /* Caso clauses vacío — Req 8.1–8.3: mensaje positivo con ícono */
          <div
            className="flex items-center gap-3 px-5 py-4 rounded-xl bg-green-50 border border-green-200"
            role="status"
            aria-label="No se encontraron cláusulas de riesgo"
          >
            {/* Ícono checkmark positivo */}
            <span
              className="flex items-center justify-center w-9 h-9 rounded-full bg-green-100 shrink-0"
              aria-hidden="true"
            >
              <svg
                xmlns="http://www.w3.org/2000/svg"
                className="w-5 h-5 text-green-600"
                fill="none"
                viewBox="0 0 24 24"
                stroke="currentColor"
                strokeWidth={2.5}
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  d="M4.5 12.75l6 6 9-13.5"
                />
              </svg>
            </span>
            <p className="text-sm font-medium text-green-800">
              No se encontraron cláusulas de riesgo en tu contrato.
            </p>
          </div>
        )}

        {/* 5. Preguntas sugeridas — Req 12.1–12.3: solo si hay cláusulas */}
        {hasClauses && <SuggestedQuestions clauses={sortedClauses} />}

        {/* 6. Recomendación general — Req 10.2: diferenciada visualmente */}
        <section
          aria-labelledby="recommendation-title"
          className="rounded-xl border border-gray-300 bg-white p-5 shadow-sm"
        >
          <h2
            id="recommendation-title"
            className="text-base font-semibold text-gray-500 uppercase tracking-wide mb-2"
          >
            Recomendación general
          </h2>
          <p className="text-base text-gray-900 leading-relaxed">
            {overall_recommendation}
          </p>
        </section>

      </div>
    </div>
  );
}

export default Results;
