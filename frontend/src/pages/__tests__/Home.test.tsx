import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { Home } from "../Home";

// Mock the API client module
vi.mock("../../api/client", () => ({
  uploadContract: vi.fn(),
  analyzeContract: vi.fn(),
  ApiIngestError: class ApiIngestError extends Error {
    error_code: string;
    constructor(resp: { error_code: string; message: string }) {
      super(resp.message);
      this.name = "ApiIngestError";
      this.error_code = resp.error_code;
    }
  },
  ApiAnalyzeError: class ApiAnalyzeError extends Error {
    error_code: string;
    constructor(resp: { error_code: string; message: string }) {
      super(resp.message);
      this.name = "ApiAnalyzeError";
      this.error_code = resp.error_code;
    }
  },
  NetworkError: class NetworkError extends Error {
    constructor() {
      super("No se pudo conectar con el servidor. Verificá tu conexión a internet.");
      this.name = "NetworkError";
    }
  },
}));

// Mock react-router-dom navigate
const mockNavigate = vi.fn();
vi.mock("react-router-dom", async () => {
  const actual = await vi.importActual("react-router-dom");
  return {
    ...actual,
    useNavigate: () => mockNavigate,
  };
});

import {
  uploadContract,
  analyzeContract,
  ApiIngestError,
  ApiAnalyzeError,
} from "../../api/client";

function renderHome() {
  return render(
    <MemoryRouter>
      <Home />
    </MemoryRouter>
  );
}

function createPdfFile(): File {
  return new File([new Uint8Array(1024)], "test.pdf", { type: "application/pdf" });
}

describe("Home", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("renders the upload zone in idle state", () => {
    renderHome();
    expect(screen.getByText("Claro y Simple")).toBeInTheDocument();
    expect(screen.getByText("Arrastrá tu contrato en PDF aquí")).toBeInTheDocument();
  });

  it("shows uploading state after selecting a file", async () => {
    (uploadContract as ReturnType<typeof vi.fn>).mockReturnValue(new Promise(() => {})); // never resolves
    renderHome();

    const input = document.querySelector('input[type="file"]') as HTMLInputElement;
    const file = createPdfFile();

    const user = userEvent.setup();
    await user.upload(input, file);

    expect(await screen.findByText("Subiendo tu contrato...")).toBeInTheDocument();
  });

  it("shows analyzing state after successful ingest", async () => {
    (uploadContract as ReturnType<typeof vi.fn>).mockResolvedValue({ document_id: "abc-123" });
    (analyzeContract as ReturnType<typeof vi.fn>).mockReturnValue(new Promise(() => {})); // never resolves

    renderHome();

    const input = document.querySelector('input[type="file"]') as HTMLInputElement;
    const file = createPdfFile();

    const user = userEvent.setup();
    await user.upload(input, file);

    expect(
      await screen.findByText("Analizando tu contrato... Esto puede tomar unos segundos")
    ).toBeInTheDocument();
  });

  it("navigates to /results on successful analysis", async () => {
    const analysisResult = {
      document_id: "abc-123",
      summary_plain: "Resumen",
      risk_score: 50,
      clauses: [],
      overall_recommendation: "Ok",
      cached: false,
    };
    (uploadContract as ReturnType<typeof vi.fn>).mockResolvedValue({ document_id: "abc-123" });
    (analyzeContract as ReturnType<typeof vi.fn>).mockResolvedValue(analysisResult);

    renderHome();

    const input = document.querySelector('input[type="file"]') as HTMLInputElement;
    const file = createPdfFile();

    const user = userEvent.setup();
    await user.upload(input, file);

    await waitFor(() => {
      expect(mockNavigate).toHaveBeenCalledWith("/results", { state: { analysis: analysisResult } });
    });
  });

  it("shows error message on ingest error and retry goes back to idle", async () => {
    const error = new (ApiIngestError as unknown as new (r: { error_code: string; message: string }) => Error)({
      error_code: "FILE_TOO_LARGE",
      message: "File too large",
    });
    (uploadContract as ReturnType<typeof vi.fn>).mockRejectedValue(error);

    renderHome();

    const input = document.querySelector('input[type="file"]') as HTMLInputElement;
    const file = createPdfFile();

    const user = userEvent.setup();
    await user.upload(input, file);

    expect(
      await screen.findByText("El archivo es demasiado grande. El máximo es 10 MB.")
    ).toBeInTheDocument();

    // Click retry should go back to idle
    await user.click(screen.getByRole("button", { name: "Intentar de nuevo" }));
    expect(screen.getByText("Arrastrá tu contrato en PDF aquí")).toBeInTheDocument();
  });

  it("shows error on transient analyze error and retry re-invokes analyze", async () => {
    const error = new (ApiAnalyzeError as unknown as new (r: { error_code: string; message: string }) => Error)({
      error_code: "BEDROCK_TIMEOUT",
      message: "Timeout",
    });
    (uploadContract as ReturnType<typeof vi.fn>).mockResolvedValue({ document_id: "abc-123" });
    (analyzeContract as ReturnType<typeof vi.fn>).mockRejectedValueOnce(error);

    renderHome();

    const input = document.querySelector('input[type="file"]') as HTMLInputElement;
    const file = createPdfFile();

    const user = userEvent.setup();
    await user.upload(input, file);

    expect(
      await screen.findByText(
        "El análisis está tardando demasiado. Intentá de nuevo en unos minutos."
      )
    ).toBeInTheDocument();

    // Mock analyze to never resolve on retry (so we can see analyzing state)
    (analyzeContract as ReturnType<typeof vi.fn>).mockReturnValue(new Promise(() => {}));
    await user.click(screen.getByRole("button", { name: "Intentar de nuevo" }));

    expect(
      await screen.findByText("Analizando tu contrato... Esto puede tomar unos segundos")
    ).toBeInTheDocument();
    // Verify analyzeContract was called again with same documentId
    expect(analyzeContract).toHaveBeenCalledWith("abc-123");
  });

  it("shows error on document analyze error and retry goes back to idle", async () => {
    const error = new (ApiAnalyzeError as unknown as new (r: { error_code: string; message: string }) => Error)({
      error_code: "DOCUMENT_NOT_FOUND",
      message: "Not found",
    });
    (uploadContract as ReturnType<typeof vi.fn>).mockResolvedValue({ document_id: "abc-123" });
    (analyzeContract as ReturnType<typeof vi.fn>).mockRejectedValue(error);

    renderHome();

    const input = document.querySelector('input[type="file"]') as HTMLInputElement;
    const file = createPdfFile();

    const user = userEvent.setup();
    await user.upload(input, file);

    expect(
      await screen.findByText(
        "No encontramos el documento. Es posible que haya expirado. Intentá subirlo de nuevo."
      )
    ).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "Intentar de nuevo" }));
    expect(screen.getByText("Arrastrá tu contrato en PDF aquí")).toBeInTheDocument();
  });
});
