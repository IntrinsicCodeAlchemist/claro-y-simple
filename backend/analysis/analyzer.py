"""Motor de análisis de contratos — Módulo 2.

Este módulo implementa la lógica de negocio del análisis: validación de request,
operaciones DynamoDB, construcción de prompt, invocación de Bedrock, parsing de
respuesta, y cálculo del risk_score.
"""
from __future__ import annotations

import json
import os
import re
from pathlib import Path

from botocore.config import Config
from botocore.exceptions import ClientError, ReadTimeoutError
from pydantic import ValidationError

from backend.shared.aws_utils import get_boto3_client
from backend.shared.exceptions import (
    AnalysisError,
    AnalysisErrorCode,
    BedrockError,
    BedrockErrorCode,
    StorageError,
    StorageErrorCode,
)
from backend.analysis.models import (
    AnalysisResult,
    Clause,
    ModelResponse,
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
_bedrock_client = get_boto3_client("bedrock-runtime")


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


# ============================================================================
# Prompt builder y validación de contexto
# ============================================================================

_PROMPT_TEMPLATE_PATH = Path(__file__).parent / "prompts" / "clause_analysis.txt"


def validate_context_length(raw_text: str) -> None:
    """Verifica que el texto del contrato no exceda el límite de contexto.

    Args:
        raw_text: Texto completo extraído del contrato.

    Raises:
        AnalysisError: Con CONTEXT_TOO_LONG si el texto excede MAX_CONTEXT_CHARS.
    """
    max_chars = int(os.environ["MAX_CONTEXT_CHARS"])
    if len(raw_text) > max_chars:
        raise AnalysisError(
            error_code=AnalysisErrorCode.CONTEXT_TOO_LONG,
            message=(
                f"El texto del contrato ({len(raw_text)} caracteres) excede el límite "
                f"de contexto ({max_chars} caracteres)."
            ),
        )


def build_prompt(raw_text: str) -> str:
    """Carga el template del prompt e inyecta el texto del contrato.

    Args:
        raw_text: Texto completo extraído del contrato.

    Returns:
        El prompt completo listo para enviar a Bedrock.
    """
    template = _PROMPT_TEMPLATE_PATH.read_text(encoding="utf-8")
    return template.format(raw_text=raw_text)


# ============================================================================
# Invocación de Bedrock
# ============================================================================


def invoke_bedrock(prompt: str) -> str:
    """Invoca Amazon Bedrock con el prompt y retorna la respuesta del modelo.

    Usa el formato de la API de mensajes de Anthropic Claude en Bedrock.

    Args:
        prompt: El prompt completo a enviar al modelo.

    Returns:
        El texto de la respuesta del modelo (string crudo).

    Raises:
        BedrockError: Con BEDROCK_TIMEOUT si no responde a tiempo,
            BEDROCK_THROTTLED si hay throttling,
            BEDROCK_SERVICE_ERROR para otros errores de servicio.
    """
    model_id = os.environ["BEDROCK_MODEL_ID"]
    timeout_seconds = int(os.environ["BEDROCK_TIMEOUT_SECONDS"])

    payload = {
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": 4096,
        "anthropic_version": "bedrock-2023-05-31",
    }

    try:
        response = _bedrock_client.invoke_model(
            body=json.dumps(payload),
            modelId=model_id,
            accept="application/json",
            contentType="application/json",
            config=Config(read_timeout=timeout_seconds),
        )
    except ReadTimeoutError:
        raise BedrockError(
            error_code=BedrockErrorCode.BEDROCK_TIMEOUT,
            message="Bedrock no respondió dentro del timeout configurado.",
        )
    except ClientError as exc:
        error_code = exc.response["Error"]["Code"]
        if error_code == "ThrottlingException":
            raise BedrockError(
                error_code=BedrockErrorCode.BEDROCK_THROTTLED,
                message="Bedrock rechazó la solicitud por throttling.",
            )
        raise BedrockError(
            error_code=BedrockErrorCode.BEDROCK_SERVICE_ERROR,
            message=f"Error de Bedrock: {error_code}",
        )

    response_body = json.loads(response["body"].read())
    return response_body["content"][0]["text"]


# ============================================================================
# Response Parser y Risk Calculator
# ============================================================================

RISK_WEIGHTS: dict[str, int] = {"bajo": 10, "medio": 25, "alto": 45}


def parse_model_response(raw_response: str) -> ModelResponse:
    """Parsea y valida la respuesta JSON del modelo contra el schema esperado.

    Args:
        raw_response: String crudo retornado por Bedrock.

    Returns:
        ModelResponse validado por Pydantic.

    Raises:
        AnalysisError: Con MODEL_RESPONSE_INVALID si el JSON es inválido
            o no cumple el schema.
    """
    try:
        data = json.loads(raw_response)
    except (json.JSONDecodeError, TypeError) as exc:
        raise AnalysisError(
            error_code=AnalysisErrorCode.MODEL_RESPONSE_INVALID,
            message=f"La respuesta del modelo no es JSON válido: {exc}",
        )

    try:
        return ModelResponse(**data)
    except ValidationError as exc:
        raise AnalysisError(
            error_code=AnalysisErrorCode.MODEL_RESPONSE_INVALID,
            message=f"La respuesta del modelo no cumple el schema esperado: {exc}",
        )


def calculate_risk_score(clauses: list[Clause]) -> int:
    """Calcula risk_score determinístico (0-100) a partir de cláusulas.

    Pesos: bajo=10, medio=25, alto=45.
    Fórmula: min(sum(pesos), 100).

    Args:
        clauses: Lista de cláusulas con risk_level válido.

    Returns:
        Entero en [0, 100].
    """
    if not clauses:
        return 0
    raw_score = sum(RISK_WEIGHTS[c.risk_level] for c in clauses)
    return min(raw_score, 100)


# ============================================================================
# Orquestador de análisis
# ============================================================================


def analyze_contract(raw_text: str, document_id: str) -> AnalysisResult:
    """Orquesta el análisis completo: validar contexto, prompt, Bedrock, parse, risk_score.

    Args:
        raw_text: Texto completo del contrato.
        document_id: UUID v4 del documento.

    Returns:
        AnalysisResult completo con todos los campos del Contrato 2.

    Raises:
        AnalysisError: En caso de contexto excedido o respuesta inválida.
        BedrockError: En caso de fallas de comunicación con Bedrock.
    """
    validate_context_length(raw_text)
    prompt = build_prompt(raw_text)
    raw_response = invoke_bedrock(prompt)
    model_response = parse_model_response(raw_response)

    # Convertir ModelClause a Clause para el cálculo de risk_score
    clauses = [
        Clause(
            clause_text=mc.clause_text,
            category=mc.category,
            risk_level=mc.risk_level,
            explanation=mc.explanation,
            suggested_question=mc.suggested_question,
        )
        for mc in model_response.clauses
    ]

    risk_score = calculate_risk_score(clauses)

    return AnalysisResult(
        document_id=document_id,
        summary_plain=model_response.summary_plain,
        risk_score=risk_score,
        clauses=clauses,
        overall_recommendation=model_response.overall_recommendation,
    )


# ============================================================================
# Persistencia
# ============================================================================


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
