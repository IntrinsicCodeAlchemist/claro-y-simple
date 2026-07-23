import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { RiskScore } from "../RiskScore";
import type { Clause } from "@/types/contract";

function makeClause(risk_level: Clause["risk_level"]): Clause {
  return {
    clause_text: "Texto de ejemplo",
    category: "multa",
    risk_level,
    explanation: "Explicación de ejemplo",
    suggested_question: "¿Pregunta?",
  };
}

describe("RiskScore", () => {
  it("shows red and 'Riesgo alto' when any clause is alto", () => {
    const clauses = [makeClause("bajo"), makeClause("alto")];
    render(<RiskScore riskScore={75} clauses={clauses} />);

    expect(screen.getByText("Riesgo alto")).toBeInTheDocument();
    expect(screen.getByText("75/100")).toBeInTheDocument();
    expect(screen.getByText("Puntaje acumulado")).toBeInTheDocument();
    expect(screen.getByText("Basado en la cláusula más grave detectada")).toBeInTheDocument();
  });

  it("shows amber and 'Riesgo medio' when no alto but some medio", () => {
    const clauses = [makeClause("bajo"), makeClause("medio")];
    render(<RiskScore riskScore={40} clauses={clauses} />);

    expect(screen.getByText("Riesgo medio")).toBeInTheDocument();
    expect(screen.getByText("40/100")).toBeInTheDocument();
  });

  it("shows green and 'Riesgo bajo' when all are bajo", () => {
    const clauses = [makeClause("bajo")];
    render(<RiskScore riskScore={10} clauses={clauses} />);

    expect(screen.getByText("Riesgo bajo")).toBeInTheDocument();
    expect(screen.getByText("No se detectaron cláusulas de riesgo")).toBeInTheDocument();
  });

  it("shows green with empty clauses and appropriate subtitle", () => {
    render(<RiskScore riskScore={0} clauses={[]} />);

    expect(screen.getByText("Riesgo bajo")).toBeInTheDocument();
    expect(screen.getByText("No se detectaron cláusulas de riesgo")).toBeInTheDocument();
  });
});
