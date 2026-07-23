import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { UploadZone } from "../UploadZone";

function createFile(name: string, sizeInBytes: number, type = "application/pdf"): File {
  const content = new Uint8Array(sizeInBytes);
  return new File([content], name, { type });
}

describe("UploadZone", () => {
  it("renders the upload zone with instructions and button", () => {
    render(<UploadZone onFileSelected={vi.fn()} disabled={false} />);
    expect(screen.getByText("Arrastrá tu contrato en PDF aquí")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Seleccionar archivo" })).toBeInTheDocument();
  });

  it("rejects non-pdf files and shows error message", async () => {
    const onFileSelected = vi.fn();
    render(<UploadZone onFileSelected={onFileSelected} disabled={false} />);

    const input = document.querySelector('input[type="file"]') as HTMLInputElement;
    const file = createFile("doc.txt", 100, "text/plain");

    fireEvent.change(input, { target: { files: [file] } });

    expect(await screen.findByText("Solo se aceptan archivos en formato PDF")).toBeInTheDocument();
    expect(onFileSelected).not.toHaveBeenCalled();
  });

  it("rejects files larger than 10 MB and shows error message", async () => {
    const onFileSelected = vi.fn();
    render(<UploadZone onFileSelected={onFileSelected} disabled={false} />);

    const input = document.querySelector('input[type="file"]') as HTMLInputElement;
    const file = createFile("large.pdf", 11 * 1024 * 1024);

    fireEvent.change(input, { target: { files: [file] } });

    expect(await screen.findByText("El archivo supera el tamaño máximo permitido (10 MB)")).toBeInTheDocument();
    expect(onFileSelected).not.toHaveBeenCalled();
  });

  it("calls onFileSelected with a valid PDF ≤ 10 MB", async () => {
    const onFileSelected = vi.fn();
    render(<UploadZone onFileSelected={onFileSelected} disabled={false} />);

    const input = document.querySelector('input[type="file"]') as HTMLInputElement;
    const file = createFile("contract.pdf", 5 * 1024 * 1024);

    fireEvent.change(input, { target: { files: [file] } });

    expect(onFileSelected).toHaveBeenCalledWith(file);
  });

  it("shows dragOver visual feedback when file is dragged over", () => {
    render(<UploadZone onFileSelected={vi.fn()} disabled={false} />);
    const zone = screen.getByRole("region");

    fireEvent.dragOver(zone, { dataTransfer: { files: [] } });

    expect(screen.getByText("Soltá el archivo aquí")).toBeInTheDocument();
  });

  it("disables interaction when disabled=true", () => {
    render(<UploadZone onFileSelected={vi.fn()} disabled={true} />);
    const button = screen.getByRole("button", { name: "Seleccionar archivo" });
    expect(button).toBeDisabled();
  });
});
