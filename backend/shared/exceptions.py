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


# ---------------------------------------------------------------------------
# BedrockError — Módulo 2: errores de comunicación con Amazon Bedrock
# ---------------------------------------------------------------------------


class BedrockErrorCode(str, Enum):
    """Códigos de error para fallos de comunicación con Bedrock."""
    BEDROCK_TIMEOUT = "BEDROCK_TIMEOUT"
    BEDROCK_THROTTLED = "BEDROCK_THROTTLED"
    BEDROCK_SERVICE_ERROR = "BEDROCK_SERVICE_ERROR"


class BedrockError(Exception):
    """Raised when Bedrock invocation fails."""

    def __init__(self, error_code: BedrockErrorCode, message: str) -> None:
        self.error_code = error_code
        self.message = message
        super().__init__(message)


# ---------------------------------------------------------------------------
# AnalysisError — Módulo 2: errores de lógica de análisis
# ---------------------------------------------------------------------------


class AnalysisErrorCode(str, Enum):
    """Códigos de error para fallos en el flujo de análisis."""
    MISSING_DOCUMENT_ID = "MISSING_DOCUMENT_ID"
    INVALID_DOCUMENT_ID = "INVALID_DOCUMENT_ID"
    DOCUMENT_NOT_FOUND = "DOCUMENT_NOT_FOUND"
    CONTEXT_TOO_LONG = "CONTEXT_TOO_LONG"
    MODEL_RESPONSE_INVALID = "MODEL_RESPONSE_INVALID"


class AnalysisError(Exception):
    """Raised by analyzer when analysis logic fails."""

    def __init__(self, error_code: AnalysisErrorCode, message: str) -> None:
        self.error_code = error_code
        self.message = message
        super().__init__(message)
