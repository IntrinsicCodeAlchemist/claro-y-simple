from __future__ import annotations

from enum import Enum


# ---------------------------------------------------------------------------
# ExtractionError
# ---------------------------------------------------------------------------


class ExtractionErrorCode(str, Enum):
    """Códigos de error para fallos de extracción de texto."""
    EMPTY_EXTRACTION = "EMPTY_EXTRACTION"          # ambos métodos no produjeron texto
    TEXTRACT_FAILURE = "TEXTRACT_FAILURE"           # Textract lanzó excepción de servicio
    S3_OBJECT_NOT_FOUND = "S3_OBJECT_NOT_FOUND"     # objeto S3 no accesible para Textract


class ExtractionError(Exception):
    """Raised by Extractor when text extraction fails."""

    def __init__(self, error_code: ExtractionErrorCode, message: str) -> None:
        self.error_code = error_code
        self.message = message
        super().__init__(message)


# ---------------------------------------------------------------------------
# StorageError
# ---------------------------------------------------------------------------


class StorageErrorCode(str, Enum):
    """Códigos de error para fallos de almacenamiento (S3 / DynamoDB)."""
    STORAGE_FAILURE = "STORAGE_FAILURE"            # falla al subir el PDF a S3
    PERSISTENCE_FAILURE = "PERSISTENCE_FAILURE"     # falla al escribir en DynamoDB


class StorageError(Exception):
    """Raised by handler when S3 or DynamoDB operations fail."""

    def __init__(self, error_code: StorageErrorCode, message: str) -> None:
        self.error_code = error_code
        self.message = message
        super().__init__(message)


# ---------------------------------------------------------------------------
# ValidationError
# ---------------------------------------------------------------------------


class ValidationErrorCode(str, Enum):
    """Códigos de error para validación del archivo subido."""
    MISSING_FILE = "MISSING_FILE"
    INVALID_FILE_TYPE = "INVALID_FILE_TYPE"
    FILE_TOO_LARGE = "FILE_TOO_LARGE"


class ValidationError(Exception):
    """Raised by PDF_Validator when the uploaded file is invalid."""

    def __init__(self, error_code: ValidationErrorCode, message: str) -> None:
        self.error_code = error_code
        self.message = message
        super().__init__(message)


# ---------------------------------------------------------------------------
# ConfigurationError
# ---------------------------------------------------------------------------


class ConfigurationError(Exception):
    """Raised during module initialization when a required env var is missing."""

    def __init__(self, message: str) -> None:
        self.message = message
        super().__init__(message)
