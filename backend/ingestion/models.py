from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Literal, Optional

from pydantic import BaseModel, Field, field_validator


# ============================================================================
# Modelos del Contrato 1 — Extracción de texto (design.md sección 3)
# ============================================================================


class ExtractionMetadata(BaseModel):
    """Metadata del documento recibido. Forma parte del Contrato 1."""
    filename: str
    uploaded_at: datetime  # siempre UTC; se serializa a ISO 8601 con sufijo Z


class ExtractionResult(BaseModel):
    """
    Resultado de la extracción. Implementa el Contrato 1 definido en
    interface-contracts.md. Este objeto se persiste íntegramente en
    DynamoDB tabla ContractExtractions.

    El campo `ttl` NO forma parte del Contrato 1 pero es requerido por
    DynamoDB para el TTL de 24 horas. Se incluye en el ítem pero no se
    expone en la respuesta HTTP.
    """
    document_id: str = Field(
        pattern=r'^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$'
    )
    raw_text: str = Field(min_length=1)
    extraction_method: Literal["text", "ocr"]
    page_count: int = Field(gt=0)
    metadata: ExtractionMetadata
    ttl: int  # Unix timestamp: now() + 86400 — campo extra para DynamoDB TTL

    @field_validator("raw_text")
    @classmethod
    def raw_text_not_whitespace_only(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("raw_text no puede ser vacío ni contener únicamente espacios en blanco")
        return v


# ============================================================================
# Modelos del Contrato 3 — Respuesta HTTP de POST /ingest
# (interface-contracts.md, Contrato 3)
# ============================================================================


class IngestErrorCode(str, Enum):
    """Códigos de error para las respuestas HTTP del endpoint POST /ingest."""
    MISSING_FILE = "MISSING_FILE"
    INVALID_FILE_TYPE = "INVALID_FILE_TYPE"
    FILE_TOO_LARGE = "FILE_TOO_LARGE"
    EMPTY_EXTRACTION = "EMPTY_EXTRACTION"
    TEXTRACT_FAILURE = "TEXTRACT_FAILURE"
    S3_OBJECT_NOT_FOUND = "S3_OBJECT_NOT_FOUND"
    STORAGE_FAILURE = "STORAGE_FAILURE"
    PERSISTENCE_FAILURE = "PERSISTENCE_FAILURE"
    VALIDATION_FAILURE = "VALIDATION_FAILURE"
    INTERNAL_ERROR = "INTERNAL_ERROR"


class IngestSuccessResponse(BaseModel):
    """Respuesta exitosa de POST /ingest (HTTP 200)."""
    document_id: str


class IngestErrorResponse(BaseModel):
    """Respuesta de error de POST /ingest (HTTP 4xx / 5xx)."""
    error_code: IngestErrorCode
    message: str
    document_id: Optional[str] = None  # solo presente cuando error_code es EMPTY_EXTRACTION


# ============================================================================
# Helper de serialización para DynamoDB
# ============================================================================


def build_dynamodb_item(result: ExtractionResult) -> dict:
    """
    Serializa un ExtractionResult a un ítem DynamoDB (formato AttributeValue).

    Convierte:
    - `metadata.uploaded_at` (datetime) → string ISO 8601 con sufijo Z
    - `ttl` → número entero (N)
    - Todos los strings → tipo S
    - Todos los enteros → tipo N
    """
    uploaded_at_str: str
    if isinstance(result.metadata.uploaded_at, datetime):
        dt = result.metadata.uploaded_at
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        uploaded_at_str = dt.strftime("%Y-%m-%dT%H:%M:%SZ")
    else:
        uploaded_at_str = str(result.metadata.uploaded_at)

    return {
        "document_id":        {"S": result.document_id},
        "raw_text":           {"S": result.raw_text},
        "extraction_method":  {"S": result.extraction_method},
        "page_count":         {"N": str(result.page_count)},
        "metadata": {
            "M": {
                "filename":    {"S": result.metadata.filename},
                "uploaded_at": {"S": uploaded_at_str},
            }
        },
        "ttl": {"N": str(result.ttl)},
    }


def deserialize_dynamodb_item(item: dict) -> dict:
    """
    Convierte un ítem de DynamoDB (formato AttributeValue) a un dict plano
    con las mismas claves que el Contrato 1.

    Realiza la operación inversa de build_dynamodb_item:
    - {"S": value} → value (string)
    - {"N": "123"} → 123 (int)
    - {"M": {...}} → {...} (dict recursivo)

    Returns:
        Dict con campos: document_id, raw_text, extraction_method,
        page_count, metadata.filename, metadata.uploaded_at, ttl.
    """
    result = {}
    for key, value in item.items():
        if isinstance(value, dict):
            if "S" in value:
                result[key] = value["S"]
            elif "N" in value:
                result[key] = int(value["N"])
            elif "M" in value:
                result[key] = deserialize_dynamodb_item(value["M"])
            else:
                result[key] = value
        else:
            result[key] = value
    return result
