import type { Clause } from "@/types/contract";
import { CATEGORY_LABELS } from "@/constants/categories";

interface SuggestedQuestionsProps {
  clauses: Clause[];
}

/**
 * Sección consolidada de preguntas sugeridas derivadas de las cláusulas con riesgo.
 * Muestra solo las cláusulas que tienen suggested_question no vacío.
 * Retorna null si el array de cláusulas está vacío.
 *
 * Requisitos: 12.1–12.3
 */
export function SuggestedQuestions({ clauses }: SuggestedQuestionsProps) {
  // Req 12.3: no renderizar si clauses está vacío
  if (clauses.length === 0) {
    return null;
  }

  // Req 12.1, 12.2: filtrar cláusulas con pregunta sugerida no vacía
  const clausesWithQuestions = clauses.filter(
    (c) => c.suggested_question.trim() !== ""
  );

  if (clausesWithQuestions.length === 0) {
    return null;
  }

  return (
    <section aria-labelledby="suggested-questions-title">
      {/* Req 12.1: título de sección */}
      <h2
        id="suggested-questions-title"
        className="text-lg font-semibold text-gray-900 mb-4"
      >
        Preguntas para hacer antes de firmar
      </h2>

      <ol className="flex flex-col gap-3">
        {clausesWithQuestions.map((clause, index) => (
          <li
            key={index}
            className="flex flex-col gap-1 p-4 rounded-lg bg-gray-50 border border-gray-200"
          >
            {/* Badge de categoría — Req 12.2 */}
            <span className="inline-block self-start px-2 py-0.5 rounded-full text-xs font-medium bg-gray-200 text-gray-600 mb-1">
              {CATEGORY_LABELS[clause.category]}
            </span>

            {/* Pregunta sugerida */}
            <p className="text-sm text-gray-800 leading-relaxed">
              {clause.suggested_question}
            </p>
          </li>
        ))}
      </ol>
    </section>
  );
}

export default SuggestedQuestions;
