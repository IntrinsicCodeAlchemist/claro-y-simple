"""Motor de análisis de contratos — Módulo 2.

Este módulo implementa la lógica de negocio del análisis: validación de request,
operaciones DynamoDB, construcción de prompt, invocación de Bedrock, parsing de
respuesta, y cálculo del risk_score.
"""
from __future__ import annotations

import os
import re

from backend.shared.aws_utils import get_boto3_client
from backend.shared.exceptions import (
    AnalysisError,
    AnalysisErrorCode,
    StorageError,
    StorageErrorCode,
)
from backend.analysis.models import (
    AnalysisResult,
    build_analysis_dynamodb_item,
    deserialize_analysis_item,
)


# ============================================================================
# Configuración y clientes (module-level)
# ============================================================================

_UUID_V4_REGEX = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$"
)

_dynamodb_client = get_boto3_client("dynamodb")


# ============================================================================
# Validación de request
# ============================================================================


def validate_document_id(body: dict) -> str:
    """Valida presencia y formato UUID v4 del document_id en el body del request.

    Args:
        body: Dict parseado del body JSON del request.

    Returns:
        El document_id validado como string.

    Raises:
        AnalysisError: Con MISSING_DOCUMENT_ID si ausente/vacío,
            INVALID_DOCUMENT_ID si formato inválido.
    """
    document_id = body.get("document_id")

    if not document_id or (isinstance(document_id, str) and document_id.strip() == ""):
        raise AnalysisError(
            error_code=AnalysisErrorCode.MISSING_DOCUMENT_ID,
            message="El campo 'document_id' es obligatorio.",
        )

    if not isinstance(document_id, str) or not _UUID_V4_REGEX.match(document_id):
        raise AnalysisError(
            error_code=AnalysisErrorCode.INVALID_DOCUMENT_ID,
            message=f"El document_id '{document_id}' no tiene formato UUID v4 válido.",
        )

    return document_id


# ============================================================================
# Operaciones DynamoDB
# ============================================================================


def get_cached_analysis(document_id: str) -> dict | None:
    """Consulta ContractAnalyses por resultado previo.

    Args:
        document_id: UUID v4 del documento.

    Returns:
        Dict plano compatible con AnalysisResult si existe, None si no hay cache.
    """
    table_name = os.environ["ANALYSES_TABLE_NAME"]

    response = _dynamodb_client.get_item(
        TableName=table_name,
        Key={"document_id": {"S": document_id}},
    )

    item = response.get("Item")
    if not item:
        return None

    return deserialize_analysis_item(item)


def get_extraction(document_id: str) -> dict:
    """Consulta ContractExtractions por el texto extraído.

    Args:
        document_id: UUID v4 del documento.

    Returns:
        Dict con al menos el campo 'raw_text'.

    Raises:
        AnalysisError: Con DOCUMENT_NOT_FOUND si el documento no existe.
    """
    table_name = os.environ["EXTRACTIONS_TABLE_NAME"]

    response = _dynamodb_client.get_item(
        TableName=table_name,
        Key={"document_id": {"S": document_id}},
    )

    item = response.get("Item")
    if not item:
        raise AnalysisError(
            error_code=AnalysisErrorCode.DOCUMENT_NOT_FOUND,
            message=f"El documento '{document_id}' no existe en ContractExtractions.",
        )

    return {
        "raw_text": item["raw_text"]["S"],
        "document_id": item["document_id"]["S"],
    }


def persist_analysis(result: AnalysisResult) -> None:
    """Escribe AnalysisResult en ContractAnalyses con TTL de 7 días.

    Args:
        result: El AnalysisResult completo a persistir.

    Raises:
        StorageError: Con PERSISTENCE_FAILURE si la operación put_item falla.
    """
    table_name = os.environ["ANALYSES_TABLE_NAME"]
    item = build_analysis_dynamodb_item(result)

    try:
        _dynamodb_client.put_item(
            TableName=table_name,
            Item=item,
        )
    except Exception as exc:
        raise StorageError(
            error_code=StorageErrorCode.PERSISTENCE_FAILURE,
            message=f"Error al persistir análisis en DynamoDB: {exc}",
        ) from exc
