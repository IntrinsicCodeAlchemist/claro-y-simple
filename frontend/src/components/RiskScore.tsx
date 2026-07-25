import type { Clause } from "@/types/contract";
import { deriveRiskDisplay } from "@/utils/riskDisplay";

interface RiskScoreProps {
  riskScore: number; // 0-100
  clauses: Clause[];
}

/** Mapeo de color semántico a clases Tailwind exactas de la paleta de riesgo */
const COLOR_CLASSES: Record<
  "red" | "amber" | "green",
  { text: string; bg: string; border: string }
> = {
  red: {
    text: "text-red-600",
    bg: "bg-red-50",
    border: "border-red-600",
  },
  amber: {
    text: "text-amber-500",
    bg: "bg-amber-50",
    border: "border-amber-500",
  },
  green: {
    text: "text-green-600",
    bg: "bg-green-50",
    border: "border-green-600",
  },
};

/**
 * Muestra el risk_score numérico y la etiqueta de riesgo derivada del nivel
 * más grave detectado en las cláusulas.
 *
 * Requisitos: 6.1–6.5, 8.1–8.3
 */
export function RiskScore({ riskScore, clauses }: RiskScoreProps) {
  const { color, label, subtitle } = deriveRiskDisplay(clauses);
  const classes = COLOR_CLASSES[color];

  return (
    <div
      className={`
        flex flex-col items-center gap-4 p-6 rounded-xl border
        font-sans bg-white
        ${classes.border}
      `}
    >
      {/* Valor numérico prominente — Req 6.1, 8.2 */}
      <div className="flex flex-col items-center gap-1">
        <span
          className={`text-3xl font-bold leading-none ${classes.text}`}
          aria-label={`Puntaje de riesgo: ${riskScore} sobre 100`}
        >
          {riskScore}/100
        </span>
        <span className="text-sm text-gray-500">Puntaje acumulado</span>
      </div>

      {/* Ícono visual según nivel — Req 8.3 */}
      <div
        className={`
          flex items-center justify-center w-12 h-12 rounded-full
          ${classes.bg}
        `}
        aria-hidden="true"
      >
        {color === "green" ? (
          /* Checkmark para riesgo bajo / clauses vacío */
          <svg
            xmlns="http://www.w3.org/2000/svg"
            className={`w-6 h-6 ${classes.text}`}
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
        ) : color === "amber" ? (
          /* Signo de advertencia para riesgo medio */
          <svg
            xmlns="http://www.w3.org/2000/svg"
            className={`w-6 h-6 ${classes.text}`}
            fill="none"
            viewBox="0 0 24 24"
            stroke="currentColor"
            strokeWidth={2.5}
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              d="M12 9v3.75m-9.303 3.376c-.866 1.5.217 3.374 1.948 3.374h14.71c1.73 0 2.813-1.874 1.948-3.374L13.949 3.378c-.866-1.5-3.032-1.5-3.898 0L2.697 16.126zM12 15.75h.007v.008H12v-.008z"
            />
          </svg>
        ) : (
          /* Exclamación para riesgo alto */
          <svg
            xmlns="http://www.w3.org/2000/svg"
            className={`w-6 h-6 ${classes.text}`}
            fill="none"
            viewBox="0 0 24 24"
            stroke="currentColor"
            strokeWidth={2.5}
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              d="M12 9v3.75m9-.75a9 9 0 11-18 0 9 9 0 0118 0zm-9 3.75h.008v.008H12v-.008z"
            />
          </svg>
        )}
      </div>

      {/* Etiqueta y subtítulo — Req 6.2–6.5, 8.1 */}
      <div className="flex flex-col items-center gap-1 text-center">
        <span className={`text-base font-semibold ${classes.text}`}>
          {label}
        </span>
        <span className="text-sm text-gray-500">{subtitle}</span>
      </div>
    </div>
  );
}

export default RiskScore;
