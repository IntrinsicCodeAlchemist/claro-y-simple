import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { SuggestedQuestions } from "../SuggestedQuestions";
import type { Clause } from "@/types/contract";

function makeClause(question: string, category: Clause["category"] = "multa"): Clause {
  return {
    clause_text: "Texto de ejemplo",
    category,
    risk_level: "medio",
    explanation: "Explicación",
    suggested_question: question,
  };
}

describe("SuggestedQuestions", () => {
  it("renders nothing when clauses array is empty", () => {
    const { container } = render(<SuggestedQuestions clauses={[]} />);
    expect(container.innerHTML).toBe("");
  });

  it("renders nothing when no clause has a suggested_question", () => {
    const clauses = [makeClause(""), makeClause("   ")];
    const { container } = render(<SuggestedQuestions clauses={clauses} />);
    expect(container.innerHTML).toBe("");
  });

  it("renders questions with section title", () => {
    const clauses = [
      makeClause("¿Puedo cancelar sin multa?"),
      makeClause("¿Quién tiene mis datos?", "cesion_datos"),
    ];
    render(<SuggestedQuestions clauses={clauses} />);

    expect(screen.getByText("Preguntas para hacer antes de firmar")).toBeInTheDocument();
    expect(screen.getByText("¿Puedo cancelar sin multa?")).toBeInTheDocument();
    expect(screen.getByText("¿Quién tiene mis datos?")).toBeInTheDocument();
  });

  it("shows category badge for each question", () => {
    const clauses = [makeClause("¿Pregunta?", "jurisdiccion")];
    render(<SuggestedQuestions clauses={clauses} />);

    expect(screen.getByText("Jurisdicción")).toBeInTheDocument();
  });

  it("only renders questions from clauses with non-empty suggested_question", () => {
    const clauses = [
      makeClause("¿Pregunta visible?"),
      makeClause(""), // empty — should be filtered out
    ];
    render(<SuggestedQuestions clauses={clauses} />);

    const items = screen.getAllByRole("listitem");
    expect(items).toHaveLength(1);
  });
});
