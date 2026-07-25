import type { Clause } from "@/types/contract";

export interface RiskDisplay {
  /** Tailwind color token: "red" | "amber" | "green" */
  color: "red" | "amber" | "green";
  /** Etiqueta textual del nivel de riesgo */
  label: string;
  /** Subtítulo explicativo */
  subtitle: string;
}

/**
 * Deriva el color, etiqueta y subtítulo de riesgo a partir del array de cláusulas.
 *
 * Reglas (Req 6.2–6.5, Design Property 1):
 * - Si al menos una cláusula tiene risk_level "alto" → rojo, "Riesgo alto"
 * - Si ninguna tiene "alto" pero al menos una tiene "medio" → amber, "Riesgo medio"
 * - Si todas son "bajo" o el array está vacío → verde, "Riesgo bajo"
 *
 * El valor numérico del risk_score NO influye en este cálculo.
 */
export function deriveRiskDisplay(clauses: Clause[]): RiskDisplay {
  if (clauses.some((c) => c.risk_level === "alto")) {
    return {
      color: "red",
      label: "Riesgo alto",
      subtitle: "Basado en la cláusula más grave detectada",
    };
  }

  if (clauses.some((c) => c.risk_level === "medio")) {
    return {
      color: "amber",
      label: "Riesgo medio",
      subtitle: "Basado en la cláusula más grave detectada",
    };
  }

  return {
    color: "green",
    label: "Riesgo bajo",
    subtitle: "No se detectaron cláusulas de riesgo",
  };
}

/** Orden de gravedad para el sort: mayor número = mayor gravedad */
const RISK_ORDER: Record<Clause["risk_level"], number> = {
  alto: 2,
  medio: 1,
  bajo: 0,
};

/**
 * Ordena las cláusulas por nivel de riesgo descendente: alto → medio → bajo.
 * Es un sort estable: cláusulas con el mismo risk_level mantienen su orden relativo original.
 *
 * (Req 7.7, Design Property 4)
 */
export function sortClausesByRisk(clauses: Clause[]): Clause[] {
  return [...clauses].sort(
    (a, b) => RISK_ORDER[b.risk_level] - RISK_ORDER[a.risk_level],
  );
}
