import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import {
  uploadContract,
  analyzeContract,
  ApiIngestError,
  ApiAnalyzeError,
  NetworkError,
} from "../client";

describe("API Client", () => {
  const originalFetch = globalThis.fetch;

  beforeEach(() => {
    globalThis.fetch = vi.fn();
  });

  afterEach(() => {
    globalThis.fetch = originalFetch;
  });

  describe("uploadContract", () => {
    it("returns IngestSuccessResponse on HTTP 200", async () => {
      const mockResponse = { document_id: "abc-123" };
      (globalThis.fetch as ReturnType<typeof vi.fn>).mockResolvedValue({
        ok: true,
        json: () => Promise.resolve(mockResponse),
      });

      const result = await uploadContract(
        new File(["content"], "test.pdf", { type: "application/pdf" })
      );
      expect(result).toEqual({ document_id: "abc-123" });

      // Verify fetch was called with the right method and form data
      const callArgs = (globalThis.fetch as ReturnType<typeof vi.fn>).mock.calls[0];
      expect(callArgs[0]).toContain("/ingest");
      expect(callArgs[1].method).toBe("POST");
      // x-api-key header should be set (value depends on env)
      expect(callArgs[1].headers).toHaveProperty("x-api-key");
    });

    it("throws ApiIngestError on HTTP error", async () => {
      const errorBody = {
        error_code: "INVALID_FILE_TYPE",
        message: "Not a PDF",
      };
      (globalThis.fetch as ReturnType<typeof vi.fn>).mockResolvedValue({
        ok: false,
        json: () => Promise.resolve(errorBody),
      });

      try {
        await uploadContract(new File(["x"], "test.pdf", { type: "application/pdf" }));
        expect.fail("Should have thrown");
      } catch (err) {
        expect(err).toBeInstanceOf(ApiIngestError);
        expect((err as ApiIngestError).error_code).toBe("INVALID_FILE_TYPE");
      }
    });

    it("throws NetworkError when fetch fails", async () => {
      (globalThis.fetch as ReturnType<typeof vi.fn>).mockRejectedValue(new TypeError("Failed to fetch"));

      try {
        await uploadContract(new File(["x"], "test.pdf", { type: "application/pdf" }));
        expect.fail("Should have thrown");
      } catch (err) {
        expect(err).toBeInstanceOf(NetworkError);
        expect((err as Error).message).toBe(
          "No se pudo conectar con el servidor. Verificá tu conexión a internet."
        );
      }
    });
  });

  describe("analyzeContract", () => {
    it("returns AnalyzeSuccessResponse on HTTP 200", async () => {
      const mockResponse = {
        document_id: "abc-123",
        summary_plain: "Resumen",
        risk_score: 50,
        clauses: [],
        overall_recommendation: "Ok",
        cached: false,
      };
      (globalThis.fetch as ReturnType<typeof vi.fn>).mockResolvedValue({
        ok: true,
        json: () => Promise.resolve(mockResponse),
      });

      const result = await analyzeContract("abc-123");
      expect(result).toEqual(mockResponse);

      const callArgs = (globalThis.fetch as ReturnType<typeof vi.fn>).mock.calls[0];
      expect(callArgs[0]).toContain("/analyze");
      expect(callArgs[1].method).toBe("POST");
      expect(callArgs[1].headers["Content-Type"]).toBe("application/json");
      expect(callArgs[1].headers).toHaveProperty("x-api-key");
      expect(JSON.parse(callArgs[1].body)).toEqual({ document_id: "abc-123" });
    });

    it("throws ApiAnalyzeError on HTTP error", async () => {
      const errorBody = {
        error_code: "DOCUMENT_NOT_FOUND",
        message: "Document not found",
      };
      (globalThis.fetch as ReturnType<typeof vi.fn>).mockResolvedValue({
        ok: false,
        json: () => Promise.resolve(errorBody),
      });

      try {
        await analyzeContract("abc-123");
        expect.fail("Should have thrown");
      } catch (err) {
        expect(err).toBeInstanceOf(ApiAnalyzeError);
        expect((err as ApiAnalyzeError).error_code).toBe("DOCUMENT_NOT_FOUND");
      }
    });

    it("throws NetworkError when fetch fails", async () => {
      (globalThis.fetch as ReturnType<typeof vi.fn>).mockRejectedValue(new TypeError("Failed to fetch"));

      try {
        await analyzeContract("abc-123");
        expect.fail("Should have thrown");
      } catch (err) {
        expect(err).toBeInstanceOf(NetworkError);
        expect((err as Error).message).toBe(
          "No se pudo conectar con el servidor. Verificá tu conexión a internet."
        );
      }
    });
  });
});
