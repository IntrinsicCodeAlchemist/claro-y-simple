import type { Clause, RiskLevel } from "@/types/contract";
import { CATEGORY_LABELS } from "@/constants/categories";

interface ClauseCardProps {
  clause: Clause;
}

/** Clases Tailwind exactas por nivel de riesgo — coincide con la paleta de RiskScore.tsx */
const RISK_CLASSES: Record<
  RiskLevel,
  { text: string; bg: string; border: string; label: string }
> = {
  alto: {
    text: "text-red-600",
    bg: "bg-red-50",
    border: "border-red-600",
    label: "Alto",
  },
  medio: {
    text: "text-amber-500",
    bg: "bg-amber-50",
    border: "border-amber-500",
    label: "Medio",
  },
  bajo: {
    text: "text-green-600",
    bg: "bg-green-50",
    border: "border-green-600",
    label: "Bajo",
  },
};

/**
 * Tarjeta individual que muestra una cláusula riesgosa con su texto original,
 * categoría, nivel de riesgo, explicación y pregunta sugerida.
 *
 * Requisitos: 7.2–7.6, 12.2
 */
export function ClauseCard({ clause }: ClauseCardProps) {
  const risk = RISK_CLASSES[clause.risk_level];
  const categoryLabel = CATEGORY_LABELS[clause.category];

  return (
    <article
      className={`
        rounded-xl border-l-4 p-5 bg-white shadow-sm
        ${risk.border}
      `}
      aria-label={`Cláusula de riesgo ${risk.label}: ${categoryLabel}`}
    >
      {/* Encabezado: categoría y nivel de riesgo */}
      <div className="flex flex-wrap items-center gap-2 mb-3">
        {/* Badge de categoría — Req 7.3 */}
        <span className="inline-block px-2 py-0.5 rounded-full text-xs font-medium bg-gray-100 text-gray-700">
          {categoryLabel}
        </span>

        {/* Badge de nivel de riesgo — Req 7.4 */}
        <span
          className={`
            inline-block px-2 py-0.5 rounded-full text-xs font-semibold border
            ${risk.bg} ${risk.text} ${risk.border}
          `}
        >
          Riesgo {risk.label}
        </span>
      </div>

      {/* Texto citado del contrato — Req 7.2 */}
      <blockquote
        className="border-l-2 border-gray-300 pl-3 mb-3 italic text-sm text-gray-600 leading-relaxed"
        aria-label="Texto original del contrato"
      >
        "{clause.clause_text}"
      </blockquote>

      {/* Explicación en lenguaje simple — Req 7.5 */}
      <p className="text-sm text-gray-800 leading-relaxed mb-3">
        {clause.explanation}
      </p>

      {/* Pregunta sugerida — Req 7.6 */}
      {clause.suggested_question && (
        <div className={`rounded-lg p-3 ${risk.bg}`}>
          <p className="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-1">
            Pregunta antes de firmar
          </p>
          <p className={`text-sm font-medium ${risk.text}`}>
            {clause.suggested_question}
          </p>
        </div>
      )}
    </article>
  );
}

export default ClauseCard;
