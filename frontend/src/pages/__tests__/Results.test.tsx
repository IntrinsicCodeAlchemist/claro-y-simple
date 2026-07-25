import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { MemoryRouter, Routes, Route } from "react-router-dom";
import { Results } from "../Results";
import type { AnalyzeSuccessResponse, Clause } from "@/types/contract";

function makeClause(
  risk_level: Clause["risk_level"],
  category: Clause["category"] = "multa",
  question = "¿Pregunta?"
): Clause {
  return {
    clause_text: `Texto de cláusula ${risk_level}`,
    category,
    risk_level,
    explanation: `Explicación ${risk_level}`,
    suggested_question: question,
  };
}

function renderWithData(analysis: AnalyzeSuccessResponse) {
  return render(
    <MemoryRouter initialEntries={[{ pathname: "/results", state: { analysis } }]}>
      <Routes>
        <Route path="/results" element={<Results />} />
        <Route path="/" element={<div>Home</div>} />
      </Routes>
    </MemoryRouter>
  );
}

describe("Results", () => {
  const baseAnalysis: AnalyzeSuccessResponse = {
    document_id: "test-uuid",
    summary_plain: "Este es un resumen de prueba.",
    risk_score: 65,
    clauses: [
      makeClause("medio", "renovacion_automatica"),
      makeClause("alto", "multa"),
      makeClause("bajo", "jurisdiccion"),
    ],
    overall_recommendation: "Recomendamos revisar con un abogado.",
    cached: false,
  };

  it("renders summary_plain", () => {
    renderWithData(baseAnalysis);
    expect(screen.getByText("Este es un resumen de prueba.")).toBeInTheDocument();
  });

  it("renders risk score", () => {
    renderWithData(baseAnalysis);
    expect(screen.getByText("65/100")).toBeInTheDocument();
  });

  it("renders overall_recommendation", () => {
    renderWithData(baseAnalysis);
    expect(screen.getByText("Recomendamos revisar con un abogado.")).toBeInTheDocument();
  });

  it("renders clauses ordered by risk (alto first)", () => {
    renderWithData(baseAnalysis);
    const clauseTexts = screen.getAllByText(/Texto de cláusula/);
    expect(clauseTexts[0].textContent).toContain("alto");
    expect(clauseTexts[1].textContent).toContain("medio");
    expect(clauseTexts[2].textContent).toContain("bajo");
  });

  it("shows cache note when cached=true", () => {
    renderWithData({ ...baseAnalysis, cached: true });
    expect(
      screen.getByText(
        "Este resultado corresponde a un análisis previo del mismo documento."
      )
    ).toBeInTheDocument();
  });

  it("does not show cache note when cached=false", () => {
    renderWithData({ ...baseAnalysis, cached: false });
    expect(
      screen.queryByText(
        "Este resultado corresponde a un análisis previo del mismo documento."
      )
    ).not.toBeInTheDocument();
  });

  it("shows positive message when clauses is empty", () => {
    renderWithData({ ...baseAnalysis, clauses: [], risk_score: 0 });
    expect(
      screen.getByText("No se encontraron cláusulas de riesgo en tu contrato.")
    ).toBeInTheDocument();
  });

  it("still shows risk_score and summary when clauses is empty", () => {
    renderWithData({ ...baseAnalysis, clauses: [], risk_score: 0 });
    expect(screen.getByText("0/100")).toBeInTheDocument();
    expect(screen.getByText("Este es un resumen de prueba.")).toBeInTheDocument();
  });

  it("does not show SuggestedQuestions section when clauses is empty", () => {
    renderWithData({ ...baseAnalysis, clauses: [] });
    expect(
      screen.queryByText("Preguntas para hacer antes de firmar")
    ).not.toBeInTheDocument();
  });

  it("redirects to / when no state is provided", () => {
    render(
      <MemoryRouter initialEntries={["/results"]}>
        <Routes>
          <Route path="/results" element={<Results />} />
          <Route path="/" element={<div>Home Page</div>} />
        </Routes>
      </MemoryRouter>
    );
    expect(screen.getByText("Home Page")).toBeInTheDocument();
  });
});
