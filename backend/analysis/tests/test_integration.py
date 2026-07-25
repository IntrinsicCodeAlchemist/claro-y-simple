"""
Tests de integración contra LocalStack — Módulo 2 (Analysis).

PRECONDICIÓN:
  1. LocalStack debe estar corriendo:
       docker run --rm -d -p 4566:4566 localstack/localstack
  2. Los recursos AWS deben estar creados:
       python scripts/setup_localstack.py
  3. Variables de entorno requeridas:
       ENVIRONMENT=localstack
       AWS_ENDPOINT_URL=http://localhost:4566
       AWS_DEFAULT_REGION=us-east-1
       AWS_ACCESS_KEY_ID=test
       AWS_SECRET_ACCESS_KEY=test
       EXTRACTIONS_TABLE_NAME=ContractExtractions
       ANALYSES_TABLE_NAME=ContractAnalyses
       BEDROCK_MODEL_ID=us.anthropic.claude-haiku-4-5-20251001-v1:0
       MAX_CONTEXT_CHARS=150000
       BEDROCK_TIMEOUT_SECONDS=45
       LOG_LEVEL=INFO

  Se puede ejecutar con:
    $env:ENVIRONMENT='localstack'; pytest backend/analysis/tests/test_integration.py -v -m integration

NOTA: Amazon Bedrock NO tiene emulación en LocalStack. En todos estos tests,
Bedrock se mockea con unittest.mock. DynamoDB es REAL (LocalStack container).
"""
from __future__ import annotations

import json
import os
import sys
import time
import uuid

import pytest

# Los tests de integración requieren LocalStack activo.
pytestmark = pytest.mark.skipif(
    os.environ.get("ENVIRONMENT") != "localstack",
    reason="Requiere ENVIRONMENT=localstack y LocalStack corriendo",
)

# Asegurar que backend/ está en sys.path para imports sin prefijo "backend."
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from unittest.mock import MagicMock, patch

from shared.aws_utils import get_boto3_client

from analysis.models import (
    AnalysisResult,
    Clause,
    build_analysis_dynamodb_item,
    deserialize_analysis_item,
)

# ---------------------------------------------------------------------------
# Configuración
# ---------------------------------------------------------------------------

EXTRACTIONS_TABLE = os.environ.get("EXTRACTIONS_TABLE_NAME", "ContractExtractions")
ANALYSES_TABLE = os.environ.get("ANALYSES_TABLE_NAME", "ContractAnalyses")


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="session")
def dynamo_client():
    return get_boto3_client("dynamodb")


class FakeContext:
    aws_request_id = "integ-analysis-test-001"


def _make_extraction_item(document_id: str, raw_text: str) -> dict:
    """Construye un ítem DynamoDB en formato AttributeValue para ContractExtractions."""
    ttl_value = int(time.time()) + 86400
    return {
        "document_id": {"S": document_id},
        "raw_text": {"S": raw_text},
        "extraction_method": {"S": "text"},
        "page_count": {"N": "5"},
        "metadata": {
            "M": {
                "filename": {"S": "contrato_test.pdf"},
                "uploaded_at": {"S": "2024-06-15T10:00:00Z"},
            }
        },
        "ttl": {"N": str(ttl_value)},
    }


def _make_bedrock_response_mock(clauses: list[dict] | None = None) -> MagicMock:
    """Construye un mock que simula la respuesta de bedrock_client.invoke_model."""
    if clauses is None:
        clauses = [
            {
                "clause_text": "El contrato se renueva automáticamente cada 12 meses sin necesidad de notificación.",
                "category": "renovacion_automatica",
                "risk_level": "medio",
                "explanation": "El contrato se renueva sin que tengas que hacer nada.",
                "suggested_question": "¿Puedo optar por no renovar sin penalización?",
            },
            {
                "clause_text": "En caso de rescisión anticipada se aplicará una multa equivalente a 3 meses de alquiler.",
                "category": "multa",
                "risk_level": "alto",
                "explanation": "Si te vas antes, pagás 3 meses extra.",
                "suggested_question": "¿Es posible reducir la multa por rescisión?",
            },
        ]

    model_output = {
        "summary_plain": "Contrato de alquiler con cláusulas de renovación automática y multa por rescisión anticipada.",
        "clauses": clauses,
        "overall_recommendation": "Negociar la cláusula de multa y revisar las condiciones de renovación.",
    }

    response_body = json.dumps({
        "id": "msg_integration_test",
        "type": "message",
        "role": "assistant",
        "content": [{"type": "text", "text": json.dumps(model_output)}],
        "model": "claude-3-haiku-20240307",
        "stop_reason": "end_turn",
        "usage": {"input_tokens": 800, "output_tokens": 300},
    })

    body_mock = MagicMock()
    body_mock.read.return_value = response_body.encode("utf-8")
    return {"body": body_mock}


def _make_event(document_id: str) -> dict:
    """Construye un evento API Gateway para lambda_handler de analysis."""
    return {"body": json.dumps({"document_id": document_id})}


# =============================================================================
# Test 1: Flujo completo con cache miss — DynamoDB real, Bedrock mockeado
# =============================================================================


@pytest.mark.integration
def test_integration_full_flow(dynamo_client):
    """
    Persiste extracción falsa en ContractExtractions (real),
    ejecuta lambda_handler con Bedrock mockeado,
    confirma que el resultado se persiste en ContractAnalyses (real).
    """
    document_id = str(uuid.uuid4())
    raw_text = (
        "CONTRATO DE LOCACIÓN. Entre las partes se acuerda lo siguiente: "
        "CLÁUSULA PRIMERA: El plazo del contrato es de 24 meses. "
        "CLÁUSULA SEGUNDA: El contrato se renueva automáticamente cada 12 meses "
        "sin necesidad de notificación previa. "
        "CLÁUSULA TERCERA: En caso de rescisión anticipada se aplicará una multa "
        "equivalente a 3 meses de alquiler."
    )

    # Paso 1: Escribir extracción falsa en ContractExtractions (LocalStack real)
    extraction_item = _make_extraction_item(document_id, raw_text)
    dynamo_client.put_item(TableName=EXTRACTIONS_TABLE, Item=extraction_item)

    # Paso 2: Ejecutar handler con Bedrock mockeado
    with patch("analysis.analyzer._bedrock_client") as mock_bedrock:
        mock_bedrock.invoke_model.return_value = _make_bedrock_response_mock()

        from analysis.handler import lambda_handler
        response = lambda_handler(_make_event(document_id), FakeContext())

    # Paso 3: Verificar respuesta HTTP
    assert response["statusCode"] == 200, f"Expected 200, got {response['statusCode']}: {response['body']}"
    body = json.loads(response["body"])
    assert body["cached"] is False
    assert body["document_id"] == document_id
    assert body["summary_plain"] != ""
    assert 0 <= body["risk_score"] <= 100
    assert len(body["clauses"]) == 2
    assert body["overall_recommendation"] != ""

    # Paso 4: Verificar que se persistió en ContractAnalyses (LocalStack real)
    stored = dynamo_client.get_item(
        TableName=ANALYSES_TABLE,
        Key={"document_id": {"S": document_id}},
    )
    assert "Item" in stored, "El resultado no se persistió en ContractAnalyses"
    item = stored["Item"]
    assert item["document_id"]["S"] == document_id
    assert item["summary_plain"]["S"] == body["summary_plain"]
    assert int(item["risk_score"]["N"]) == body["risk_score"]
    assert item["overall_recommendation"]["S"] == body["overall_recommendation"]

    # Verificar TTL está en el futuro
    ttl_value = int(item["ttl"]["N"])
    assert ttl_value > int(time.time()), "TTL debería estar en el futuro"

    # Verificar cláusulas en DynamoDB
    clauses_in_db = item["clauses"]["L"]
    assert len(clauses_in_db) == 2
    first_clause = clauses_in_db[0]["M"]
    assert first_clause["category"]["S"] == "renovacion_automatica"
    assert first_clause["risk_level"]["S"] == "medio"

    # Limpiar
    dynamo_client.delete_item(TableName=EXTRACTIONS_TABLE, Key={"document_id": {"S": document_id}})
    dynamo_client.delete_item(TableName=ANALYSES_TABLE, Key={"document_id": {"S": document_id}})


# =============================================================================
# Test 2: Cache hit — Bedrock NO se invoca en segunda llamada
# =============================================================================


@pytest.mark.integration
def test_integration_cache_hit(dynamo_client):
    """
    Primera llamada: persiste resultado (Bedrock mockeado).
    Segunda llamada: retorna cached=True, Bedrock no invocado.
    """
    document_id = str(uuid.uuid4())
    raw_text = "Contrato simple de prueba para verificar cache hit en LocalStack."

    # Setup: escribir extracción en ContractExtractions
    extraction_item = _make_extraction_item(document_id, raw_text)
    dynamo_client.put_item(TableName=EXTRACTIONS_TABLE, Item=extraction_item)

    with patch("analysis.analyzer._bedrock_client") as mock_bedrock:
        mock_bedrock.invoke_model.return_value = _make_bedrock_response_mock(clauses=[])

        from analysis.handler import lambda_handler

        # Primera llamada — análisis fresco
        response1 = lambda_handler(_make_event(document_id), FakeContext())
        assert response1["statusCode"] == 200
        body1 = json.loads(response1["body"])
        assert body1["cached"] is False

        # Verificar que Bedrock fue llamado exactamente 1 vez
        assert mock_bedrock.invoke_model.call_count == 1

        # Segunda llamada — debería ser cache hit
        response2 = lambda_handler(_make_event(document_id), FakeContext())
        assert response2["statusCode"] == 200
        body2 = json.loads(response2["body"])
        assert body2["cached"] is True

        # Bedrock sigue con 1 sola llamada (no se invocó de nuevo)
        assert mock_bedrock.invoke_model.call_count == 1

    # Verificar que ambas respuestas tienen los mismos datos de análisis
    assert body1["risk_score"] == body2["risk_score"]
    assert body1["summary_plain"] == body2["summary_plain"]

    # Limpiar
    dynamo_client.delete_item(TableName=EXTRACTIONS_TABLE, Key={"document_id": {"S": document_id}})
    dynamo_client.delete_item(TableName=ANALYSES_TABLE, Key={"document_id": {"S": document_id}})


# =============================================================================
# Test 3: Document not found — UUID válido pero no existe en ContractExtractions
# =============================================================================


@pytest.mark.integration
def test_integration_document_not_found(dynamo_client):
    """
    UUID válido que no existe en ContractExtractions → HTTP 404, DOCUMENT_NOT_FOUND.
    """
    document_id = str(uuid.uuid4())  # UUID que nunca se escribió

    with patch("analysis.analyzer._bedrock_client") as mock_bedrock:
        from analysis.handler import lambda_handler
        response = lambda_handler(_make_event(document_id), FakeContext())

    assert response["statusCode"] == 404
    body = json.loads(response["body"])
    assert body["error_code"] == "DOCUMENT_NOT_FOUND"
    assert body["document_id"] == document_id

    # Bedrock no debería haber sido invocado
    mock_bedrock.invoke_model.assert_not_called()


# =============================================================================
# Test 4: Round-trip de serialización del Contrato 2 contra DynamoDB real
# =============================================================================


@pytest.mark.integration
def test_integration_contract2_roundtrip(dynamo_client):
    """
    Serializa un AnalysisResult con build_analysis_dynamodb_item,
    lo persiste con put_item real, lo lee con get_item real,
    lo deserializa, y confirma que todos los valores sobreviven.
    """
    document_id = str(uuid.uuid4())

    original = AnalysisResult(
        document_id=document_id,
        summary_plain="Contrato de servicios de internet con cláusula de permanencia mínima.",
        risk_score=70,
        clauses=[
            Clause(
                clause_text="El cliente se compromete a una permanencia mínima de 18 meses.",
                category="multa",
                risk_level="alto",
                explanation="Si cancelás antes de 18 meses, te cobran la totalidad del período restante.",
                suggested_question="¿Cuál es el monto exacto de la penalización por cancelación anticipada?",
            ),
            Clause(
                clause_text="Los datos personales podrán ser cedidos a empresas del grupo.",
                category="cesion_datos",
                risk_level="bajo",
                explanation="Pueden compartir tus datos con otras empresas del mismo grupo.",
                suggested_question="¿A qué empresas específicas se cederán mis datos?",
            ),
        ],
        overall_recommendation="Negociar la cláusula de permanencia y revisar la política de datos.",
    )

    # Serializar y persistir en DynamoDB real
    dynamo_item = build_analysis_dynamodb_item(original)
    dynamo_client.put_item(TableName=ANALYSES_TABLE, Item=dynamo_item)

    # Leer de vuelta desde DynamoDB real
    stored = dynamo_client.get_item(
        TableName=ANALYSES_TABLE,
        Key={"document_id": {"S": document_id}},
    )
    assert "Item" in stored, "El ítem no se encontró en ContractAnalyses"

    # Deserializar
    deserialized = deserialize_analysis_item(stored["Item"])

    # Verificar round-trip completo
    assert deserialized["document_id"] == original.document_id
    assert deserialized["summary_plain"] == original.summary_plain
    assert deserialized["risk_score"] == original.risk_score
    assert deserialized["overall_recommendation"] == original.overall_recommendation
    assert len(deserialized["clauses"]) == len(original.clauses)

    for i, (orig_clause, deser_clause) in enumerate(zip(original.clauses, deserialized["clauses"])):
        assert deser_clause["clause_text"] == orig_clause.clause_text, f"clause[{i}].clause_text mismatch"
        assert deser_clause["category"] == orig_clause.category, f"clause[{i}].category mismatch"
        assert deser_clause["risk_level"] == orig_clause.risk_level, f"clause[{i}].risk_level mismatch"
        assert deser_clause["explanation"] == orig_clause.explanation, f"clause[{i}].explanation mismatch"
        assert deser_clause["suggested_question"] == orig_clause.suggested_question, f"clause[{i}].suggested_question mismatch"

    # Verificar que TTL está presente y en el futuro
    ttl_value = int(stored["Item"]["ttl"]["N"])
    assert ttl_value > int(time.time()), "TTL debería estar en el futuro"

    # Limpiar
    dynamo_client.delete_item(TableName=ANALYSES_TABLE, Key={"document_id": {"S": document_id}})
