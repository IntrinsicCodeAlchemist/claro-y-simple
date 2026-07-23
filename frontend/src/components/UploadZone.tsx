import { useRef, useState } from "react";

interface UploadZoneProps {
  onFileSelected: (file: File) => void;
  disabled: boolean;
}

type UploadZoneState = "idle" | "dragOver";

const MAX_FILE_SIZE_BYTES = 10 * 1024 * 1024; // 10 MB

/**
 * Zona de drag & drop para seleccionar un PDF.
 * Valida extensión (.pdf) y tamaño (≤ 10 MB) antes de invocar onFileSelected.
 * Cuando disabled=true bloquea toda interacción (estado uploading/analyzing).
 *
 * Requisitos: 1.1–1.5, 2.2
 */
export function UploadZone({ onFileSelected, disabled }: UploadZoneProps) {
  const [state, setState] = useState<UploadZoneState>("idle");
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  function validateAndSelect(file: File): void {
    const isPdf =
      file.name.toLowerCase().endsWith(".pdf") ||
      file.type === "application/pdf";

    if (!isPdf) {
      setErrorMessage("Solo se aceptan archivos en formato PDF");
      return;
    }

    if (file.size > MAX_FILE_SIZE_BYTES) {
      setErrorMessage(
        "El archivo supera el tamaño máximo permitido (10 MB)",
      );
      return;
    }

    setErrorMessage(null);
    onFileSelected(file);
  }

  function handleDragOver(e: React.DragEvent<HTMLDivElement>): void {
    if (disabled) return;
    e.preventDefault();
    setState("dragOver");
  }

  function handleDragLeave(e: React.DragEvent<HTMLDivElement>): void {
    if (disabled) return;
    // Only leave dragOver state if leaving the zone entirely (not entering a child)
    if (!e.currentTarget.contains(e.relatedTarget as Node)) {
      setState("idle");
    }
  }

  function handleDrop(e: React.DragEvent<HTMLDivElement>): void {
    if (disabled) return;
    e.preventDefault();
    setState("idle");

    const file = e.dataTransfer.files[0];
    if (file) {
      validateAndSelect(file);
    }
  }

  function handleInputChange(e: React.ChangeEvent<HTMLInputElement>): void {
    const file = e.target.files?.[0];
    if (file) {
      validateAndSelect(file);
    }
    // Reset so the same file can be selected again after an error
    e.target.value = "";
  }

  function handleButtonClick(): void {
    if (disabled) return;
    inputRef.current?.click();
  }

  const isDragOver = state === "dragOver";

  const zoneClasses = [
    "relative flex flex-col items-center justify-center gap-4",
    "rounded-xl border-2 border-dashed p-12",
    "transition-colors duration-150",
    isDragOver
      ? "border-blue-500 bg-blue-50"
      : "border-gray-300 bg-white hover:border-gray-400",
    disabled ? "opacity-50 pointer-events-none" : "cursor-default",
  ].join(" ");

  return (
    <div className="w-full">
      {/* Drop zone */}
      <div
        role="region"
        aria-label="Zona de carga de archivo"
        className={zoneClasses}
        onDragOver={handleDragOver}
        onDragLeave={handleDragLeave}
        onDrop={handleDrop}
      >
        {/* Upload icon */}
        <svg
          xmlns="http://www.w3.org/2000/svg"
          className={`w-12 h-12 transition-colors duration-150 ${isDragOver ? "text-blue-500" : "text-gray-400"}`}
          fill="none"
          viewBox="0 0 24 24"
          stroke="currentColor"
          strokeWidth={1.5}
          aria-hidden="true"
        >
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            d="M3 16.5v2.25A2.25 2.25 0 005.25 21h13.5A2.25 2.25 0 0021 18.75V16.5m-13.5-9L12 3m0 0l4.5 4.5M12 3v13.5"
          />
        </svg>

        {/* Instructions */}
        <div className="text-center">
          <p className="text-base font-medium text-gray-700">
            {isDragOver
              ? "Soltá el archivo aquí"
              : "Arrastrá tu contrato en PDF aquí"}
          </p>
          <p className="mt-1 text-sm text-gray-500">o usá el botón para buscarlo en tu dispositivo</p>
          <p className="mt-1 text-xs text-gray-400">Solo PDF · Máximo 10 MB</p>
        </div>

        {/* Hidden file input */}
        <input
          ref={inputRef}
          type="file"
          accept=".pdf,application/pdf"
          className="sr-only"
          aria-hidden="true"
          tabIndex={-1}
          disabled={disabled}
          onChange={handleInputChange}
        />

        {/* File picker button */}
        <button
          type="button"
          disabled={disabled}
          onClick={handleButtonClick}
          className="
            mt-2 px-6 py-2.5 rounded-lg
            bg-blue-600 text-white text-sm font-medium
            hover:bg-blue-700 active:bg-blue-800
            focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-2
            transition-colors duration-150
            disabled:opacity-50 disabled:cursor-not-allowed
          "
        >
          Seleccionar archivo
        </button>
      </div>

      {/* Inline validation error */}
      {errorMessage && (
        <p
          role="alert"
          className="mt-3 text-sm text-red-600"
        >
          {errorMessage}
        </p>
      )}
    </div>
  );
}

export default UploadZone;
