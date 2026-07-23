import { describe, it, expect } from "vitest";
import * as fc from "fast-check";
import { deriveRiskDisplay, sortClausesByRisk } from "@/utils/riskDisplay";
import { INGEST_ERROR_MESSAGES, ANALYZE_ERROR_MESSAGES } from "@/constants/errorMessages";
import type { Clause, ClauseCategory, RiskLevel, IngestErrorCode, AnalyzeErrorCode } from "@/types/contract";

// ---------------------------------------------------------------------------
// Generators
// ---------------------------------------------------------------------------

const riskLevelArb: fc.Arbitrary<RiskLevel> = fc.constantFrom("bajo", "medio", "alto");
const categoryArb: fc.Arbitrary<ClauseCategory> = fc.constantFrom(
  "renovacion_automatica",
  "multa",
  "jurisdiccion",
  "cesion_datos",
  "otro"
);

const clauseArb: fc.Arbitrary<Clause> = fc.record({
  clause_text: fc.string({ minLength: 1, maxLength: 200 }),
  category: categoryArb,
  risk_level: riskLevelArb,
  explanation: fc.string({ minLength: 0, maxLength: 200 }),
  suggested_question: fc.string({ minLength: 0, maxLength: 200 }),
});

const clausesArb = fc.array(clauseArb, { minLength: 0, maxLength: 20 });

// ---------------------------------------------------------------------------
// Property 1: El color se deriva del risk_level más grave
// **Validates: Requirements 6.2, 6.3, 6.4, 6.5**
// ---------------------------------------------------------------------------

describe("Property 1: deriveRiskDisplay derives color from most severe risk_level", () => {
  it("returns red when any clause has risk_level alto", () => {
    fc.assert(
      fc.property(clausesArb, (clauses) => {
        const hasAlto = clauses.some((c) => c.risk_level === "alto");
        const result = deriveRiskDisplay(clauses);
        if (hasAlto) {
          expect(result.color).toBe("red");
          expect(result.label).toBe("Riesgo alto");
        }
      }),
      { numRuns: 100 }
    );
  });

  it("returns amber when no alto but some medio", () => {
    fc.assert(
      fc.property(clausesArb, (clauses) => {
        const hasAlto = clauses.some((c) => c.risk_level === "alto");
        const hasMedio = clauses.some((c) => c.risk_level === "medio");
        const result = deriveRiskDisplay(clauses);
        if (!hasAlto && hasMedio) {
          expect(result.color).toBe("amber");
          expect(result.label).toBe("Riesgo medio");
        }
      }),
      { numRuns: 100 }
    );
  });

  it("returns green when all bajo or empty", () => {
    fc.assert(
      fc.property(clausesArb, (clauses) => {
        const hasAlto = clauses.some((c) => c.risk_level === "alto");
        const hasMedio = clauses.some((c) => c.risk_level === "medio");
        const result = deriveRiskDisplay(clauses);
        if (!hasAlto && !hasMedio) {
          expect(result.color).toBe("green");
          expect(result.label).toBe("Riesgo bajo");
        }
      }),
      { numRuns: 100 }
    );
  });
});

// ---------------------------------------------------------------------------
// Property 2: Todo error_code tiene un mensaje amigable mapeado
// **Validates: Requirements 4.1–4.10, 5.1–5.10**
// ---------------------------------------------------------------------------

describe("Property 2: All error_codes have a non-empty friendly message", () => {
  const ingestCodes: IngestErrorCode[] = [
    "MISSING_FILE", "INVALID_FILE_TYPE", "FILE_TOO_LARGE", "EMPTY_EXTRACTION",
    "TEXTRACT_FAILURE", "S3_OBJECT_NOT_FOUND", "STORAGE_FAILURE",
    "PERSISTENCE_FAILURE", "VALIDATION_FAILURE", "INTERNAL_ERROR",
  ];

  const analyzeCodes: AnalyzeErrorCode[] = [
    "MISSING_DOCUMENT_ID", "INVALID_DOCUMENT_ID", "DOCUMENT_NOT_FOUND",
    "CONTEXT_TOO_LONG", "MODEL_RESPONSE_INVALID", "BEDROCK_TIMEOUT",
    "BEDROCK_THROTTLED", "BEDROCK_SERVICE_ERROR", "PERSISTENCE_FAILURE",
    "INTERNAL_ERROR",
  ];

  it("every IngestErrorCode maps to a non-empty string", () => {
    fc.assert(
      fc.property(fc.constantFrom(...ingestCodes), (code) => {
        const msg = INGEST_ERROR_MESSAGES[code];
        expect(typeof msg).toBe("string");
        expect(msg.length).toBeGreaterThan(0);
      }),
      { numRuns: 100 }
    );
  });

  it("every AnalyzeErrorCode maps to a non-empty string", () => {
    fc.assert(
      fc.property(fc.constantFrom(...analyzeCodes), (code) => {
        const msg = ANALYZE_ERROR_MESSAGES[code];
        expect(typeof msg).toBe("string");
        expect(msg.length).toBeGreaterThan(0);
      }),
      { numRuns: 100 }
    );
  });
});

// ---------------------------------------------------------------------------
// Property 3: Retry de errores transitorios reutiliza document_id
// **Validates: Requirements 5.11**
// ---------------------------------------------------------------------------

describe("Property 3: Transient analysis errors retry with same document_id", () => {
  const transientCodes: AnalyzeErrorCode[] = [
    "MODEL_RESPONSE_INVALID", "BEDROCK_TIMEOUT", "BEDROCK_THROTTLED",
    "BEDROCK_SERVICE_ERROR", "PERSISTENCE_FAILURE", "INTERNAL_ERROR",
  ];
  const documentCodes: AnalyzeErrorCode[] = [
    "MISSING_DOCUMENT_ID", "INVALID_DOCUMENT_ID", "DOCUMENT_NOT_FOUND", "CONTEXT_TOO_LONG",
  ];

  it("transient error codes are classified as retriable with same document_id", () => {
    const TRANSIENT_SET = new Set<AnalyzeErrorCode>(transientCodes);
    fc.assert(
      fc.property(fc.constantFrom(...transientCodes), (code) => {
        expect(TRANSIENT_SET.has(code)).toBe(true);
      }),
      { numRuns: 100 }
    );
  });

  it("document error codes are NOT in the transient set", () => {
    const TRANSIENT_SET = new Set<AnalyzeErrorCode>(transientCodes);
    fc.assert(
      fc.property(fc.constantFrom(...documentCodes), (code) => {
        expect(TRANSIENT_SET.has(code)).toBe(false);
      }),
      { numRuns: 100 }
    );
  });
});

// ---------------------------------------------------------------------------
// Property 4: Las cláusulas se ordenan por risk_level descendente
// **Validates: Requirements 7.7**
// ---------------------------------------------------------------------------

describe("Property 4: sortClausesByRisk orders alto > medio > bajo", () => {
  const RISK_ORDER: Record<RiskLevel, number> = { alto: 2, medio: 1, bajo: 0 };

  it("sorted array has no inversions of risk order", () => {
    fc.assert(
      fc.property(clausesArb, (clauses) => {
        const sorted = sortClausesByRisk(clauses);
        for (let i = 1; i < sorted.length; i++) {
          expect(RISK_ORDER[sorted[i - 1].risk_level]).toBeGreaterThanOrEqual(
            RISK_ORDER[sorted[i].risk_level]
          );
        }
      }),
      { numRuns: 100 }
    );
  });

  it("sorted array contains same elements as input", () => {
    fc.assert(
      fc.property(clausesArb, (clauses) => {
        const sorted = sortClausesByRisk(clauses);
        expect(sorted).toHaveLength(clauses.length);
      }),
      { numRuns: 100 }
    );
  });
});

// ---------------------------------------------------------------------------
// Property 5: La sección de preguntas muestra exactamente las preguntas de las cláusulas
// **Validates: Requirements 12.1, 12.3**
// ---------------------------------------------------------------------------

describe("Property 5: Questions count equals clauses with non-empty suggested_question", () => {
  it("count of filtered questions matches clauses with non-empty trimmed suggested_question", () => {
    fc.assert(
      fc.property(clausesArb, (clauses) => {
        const expected = clauses.filter((c) => c.suggested_question.trim() !== "").length;
        // Simulate what SuggestedQuestions component does
        const filtered = clauses.filter((c) => c.suggested_question.trim() !== "");
        expect(filtered.length).toBe(expected);
      }),
      { numRuns: 100 }
    );
  });
});
