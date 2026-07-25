import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { ClauseCard } from "../ClauseCard";
import type { Clause } from "@/types/contract";

describe("ClauseCard", () => {
  const clause: Clause = {
    clause_text: "El contrato se renueva automáticamente cada 12 meses.",
    category: "renovacion_automatica",
    risk_level: "alto",
    explanation: "Esto significa que no podés cancelar fácilmente.",
    suggested_question: "¿Puedo cancelar antes de la renovación?",
  };

  it("renders clause_text as a quote", () => {
    render(<ClauseCard clause={clause} />);
    expect(
      screen.getByText(`"${clause.clause_text}"`)
    ).toBeInTheDocument();
  });

  it("renders category label in Spanish", () => {
    render(<ClauseCard clause={clause} />);
    expect(screen.getByText("Renovación automática")).toBeInTheDocument();
  });

  it("renders risk_level badge with correct label", () => {
    render(<ClauseCard clause={clause} />);
    expect(screen.getByText("Riesgo Alto")).toBeInTheDocument();
  });

  it("renders the explanation", () => {
    render(<ClauseCard clause={clause} />);
    expect(screen.getByText(clause.explanation)).toBeInTheDocument();
  });

  it("renders the suggested question", () => {
    render(<ClauseCard clause={clause} />);
    expect(screen.getByText(clause.suggested_question)).toBeInTheDocument();
  });

  it("renders medio risk with amber styling label", () => {
    const medioClause: Clause = {
      ...clause,
      risk_level: "medio",
    };
    render(<ClauseCard clause={medioClause} />);
    expect(screen.getByText("Riesgo Medio")).toBeInTheDocument();
  });

  it("renders bajo risk with green styling label", () => {
    const bajoClause: Clause = {
      ...clause,
      risk_level: "bajo",
    };
    render(<ClauseCard clause={bajoClause} />);
    expect(screen.getByText("Riesgo Bajo")).toBeInTheDocument();
  });

  it("renders all category labels correctly", () => {
    const categories = [
      { category: "multa" as const, label: "Multa" },
      { category: "jurisdiccion" as const, label: "Jurisdicción" },
      { category: "cesion_datos" as const, label: "Cesión de datos" },
      { category: "otro" as const, label: "Otro" },
    ];

    for (const { category, label } of categories) {
      const { unmount } = render(
        <ClauseCard clause={{ ...clause, category }} />
      );
      expect(screen.getByText(label)).toBeInTheDocument();
      unmount();
    }
  });
});
