"""Lambda handler para el Motor de Análisis — Módulo 2.

Punto de entrada AWS Lambda. Parsea el evento de API Gateway,
orquesta el flujo de análisis, y retorna respuestas HTTP conformes
al Contrato 4 (interface-contracts.md).
"""
from __future__ import annotations

import json
import os

from aws_lambda_powertools import Logger

from backend.shared.exceptions import (
    AnalysisError,
    AnalysisErrorCode,
    BedrockError,
    BedrockErrorCode,
    ConfigurationError,
    StorageError,
)
from backend.analysis.analyzer import (
    analyze_contract,
    get_cached_analysis,
    get_extraction,
    persist_analysis,
    validate_document_id,
)


# ============================================================================
# Inicialización module-scope
# ============================================================================

# Validar que las variables de entorno requeridas existan al cargar el módulo
_REQUIRED_ENV_VARS = [
    "EXTRACTIONS_TABLE_NAME",
    "ANALYSES_TABLE_NAME",
    "BEDROCK_MODEL_ID",
    "MAX_CONTEXT_CHARS",
    "BEDROCK_TIMEOUT_SECONDS",
]

for var in _REQUIRED_ENV_VARS:
    if not os.environ.get(var):
        raise ConfigurationError(
            f"Variable de entorno requerida '{var}' no está definida."
        )

logger = Logger()

# Mapeo de AnalysisErrorCode a HTTP status
_ANALYSIS_ERROR_STATUS: dict[AnalysisErrorCode, int] = {
    AnalysisErrorCode.MISSING_DOCUMENT_ID: 400,
    AnalysisErrorCode.INVALID_DOCUMENT_ID: 400,
    AnalysisErrorCode.DOCUMENT_NOT_FOUND: 404,
    AnalysisErrorCode.CONTEXT_TOO_LONG: 422,
    AnalysisErrorCode.MODEL_RESPONSE_INVALID: 422,
}

# Mapeo de BedrockErrorCode a HTTP status
_BEDROCK_ERROR_STATUS: dict[BedrockErrorCode, int] = {
    BedrockErrorCode.BEDROCK_TIMEOUT: 503,
    BedrockErrorCode.BEDROCK_THROTTLED: 503,
    BedrockErrorCode.BEDROCK_SERVICE_ERROR: 502,
}


# ============================================================================
# Helpers
# ============================================================================


def http_response(status_code: int, body: dict) -> dict:
    """Construye una respuesta HTTP compatible con API Gateway.

    Args:
        status_code: Código HTTP de la respuesta.
        body: Dict a serializar como JSON en el body.

    Returns:
        Dict con statusCode, headers, y body serializados.
    """
    return {
        "statusCode": status_code,
        "headers": {"Content-Type": "application/json"},
        "body": json.dumps(body, ensure_ascii=False),
    }


# ============================================================================
# Lambda Handler
# ============================================================================


def lambda_handler(event: dict, context: object) -> dict:
    """Punto de entrada Lambda para POST /analyze.

    Orquesta el flujo de 10 pasos del análisis de contratos:
    1. Parsear y validar request
    2. Buscar cache en ContractAnalyses
    3. Buscar extracción en ContractExtractions
    4-7. Ejecutar análisis (contexto, prompt, Bedrock, parse)
    8. Calcular risk_score
    9. Persistir resultado
    10. Retornar respuesta

    Args:
        event: Evento de API Gateway.
        context: Contexto Lambda (contiene aws_request_id).

    Returns:
        Respuesta HTTP como dict (statusCode, headers, body).
    """
    request_id = getattr(context, "aws_request_id", "unknown")
    logger.append_keys(request_id=request_id)
    document_id: str | None = None

    try:
        # 1. Parsear y validar request
        body = json.loads(event.get("body") or "{}")
        document_id = validate_document_id(body)
        logger.append_keys(document_id=document_id)

        # 2. Buscar cache en ContractAnalyses
        cached_result = get_cached_analysis(document_id)
        if cached_result:
            logger.info("Cache hit — retornando resultado previo.")
            return http_response(200, {**cached_result, "cached": True})

        # 3. Buscar extracción en ContractExtractions
        extraction = get_extraction(document_id)

        # 4-8. Ejecutar análisis completo (validar contexto, prompt, Bedrock, parse, risk_score)
        analysis_result = analyze_contract(extraction["raw_text"], document_id)

        # 9. Persistir resultado
        persist_analysis(analysis_result)

        # 10. Retornar respuesta
        logger.info("Análisis completado exitosamente.")
        return http_response(200, {**analysis_result.model_dump(), "cached": False})

    except AnalysisError as exc:
        status_code = _ANALYSIS_ERROR_STATUS.get(exc.error_code, 500)
        logger.warning(
            "Error de análisis",
            error_code=exc.error_code.value,
            error_message=exc.message,
        )
        error_body: dict = {
            "error_code": exc.error_code.value,
            "message": exc.message,
        }
        if document_id:
            error_body["document_id"] = document_id
        return http_response(status_code, error_body)

    except BedrockError as exc:
        status_code = _BEDROCK_ERROR_STATUS.get(exc.error_code, 502)
        logger.error(
            "Error de Bedrock",
            error_code=exc.error_code.value,
            error_message=exc.message,
        )
        error_body = {
            "error_code": exc.error_code.value,
            "message": exc.message,
        }
        if document_id:
            error_body["document_id"] = document_id
        return http_response(status_code, error_body)

    except StorageError as exc:
        logger.error(
            "Error de persistencia",
            error_code=exc.error_code.value,
            error_message=exc.message,
        )
        error_body = {
            "error_code": exc.error_code.value,
            "message": exc.message,
        }
        if document_id:
            error_body["document_id"] = document_id
        return http_response(502, error_body)

    except Exception:
        logger.exception("Error inesperado en el flujo de análisis.")
        error_body = {
            "error_code": "INTERNAL_ERROR",
            "message": "Error interno del servidor.",
        }
        if document_id:
            error_body["document_id"] = document_id
        return http_response(500, error_body)
