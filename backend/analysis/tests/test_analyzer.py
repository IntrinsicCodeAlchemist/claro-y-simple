"""Tests unitarios del Módulo 2 — Motor de Análisis.

Fase 2: Tests del camino feliz (Camino B: análisis nuevo + Camino A: cache hit).
"""
from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest

from backend.analysis.tests.conftest import (
    make_bedrock_response,
    make_cached_analysis_item,
    make_event,
    make_extraction_item,
)


VALID_UUID = "550e8400-e29b-41d4-a716-446655440000"
SAMPLE_RAW_TEXT = "Este es un contrato de alquiler entre las partes..."


# ============================================================================
# Fase 2 — Camino feliz
# ============================================================================


@patch("backend.analysis.analyzer._bedrock_client")
@patch("backend.analysis.analyzer._dynamodb_client")
def test_successful_analysis_flow(mock_dynamodb, mock_bedrock, lambda_context):
    """Camino B: análisis nuevo exitoso con cláusulas."""
    # Mock DynamoDB: no cache, sí extracción
    def get_item_side_effect(**kwargs):
        table = kwargs["TableName"]
        if table == "ContractAnalyses":
            return {}  # No cache
        elif table == "ContractExtractions":
            return make_extraction_item(VALID_UUID, SAMPLE_RAW_TEXT)
        return {}

    mock_dynamodb.get_item.side_effect = get_item_side_effect
    mock_dynamodb.put_item.return_value = {}

    # Mock Bedrock: respuesta válida con 1 cláusula
    mock_bedrock.invoke_model.return_value = make_bedrock_response()

    from backend.analysis.handler import lambda_handler

    response = lambda_handler(make_event(VALID_UUID), lambda_context)

    assert response["statusCode"] == 200
    body = json.loads(response["body"])
    assert body["cached"] is False
    assert body["document_id"] == VALID_UUID
    assert body["summary_plain"] != ""
    assert body["risk_score"] >= 0
    assert body["risk_score"] <= 100
    assert len(body["clauses"]) == 1
    assert body["clauses"][0]["category"] == "renovacion_automatica"
    assert body["overall_recommendation"] != ""

    # put_item debe haberse llamado exactamente una vez (persistir resultado)
    mock_dynamodb.put_item.assert_called_once()


@patch("backend.analysis.analyzer._bedrock_client")
@patch("backend.analysis.analyzer._dynamodb_client")
def test_zero_clauses(mock_dynamodb, mock_bedrock, lambda_context):
    """Camino B: Bedrock retorna cero cláusulas -> risk_score=0, clauses=[]."""
    def get_item_side_effect(**kwargs):
        table = kwargs["TableName"]
        if table == "ContractAnalyses":
            return {}
        elif table == "ContractExtractions":
            return make_extraction_item(VALID_UUID, SAMPLE_RAW_TEXT)
        return {}

    mock_dynamodb.get_item.side_effect = get_item_side_effect
    mock_dynamodb.put_item.return_value = {}

    # Bedrock retorna sin cláusulas
    mock_bedrock.invoke_model.return_value = make_bedrock_response(clauses=[])

    from backend.analysis.handler import lambda_handler

    response = lambda_handler(make_event(VALID_UUID), lambda_context)

    assert response["statusCode"] == 200
    body = json.loads(response["body"])
    assert body["cached"] is False
    assert body["risk_score"] == 0
    assert body["clauses"] == []


@patch("backend.analysis.analyzer._bedrock_client")
@patch("backend.analysis.analyzer._dynamodb_client")
def test_cache_hit_returns_cached_true(mock_dynamodb, mock_bedrock, lambda_context):
    """Camino A: cache hit retorna resultado previo con cached=true."""
    # Mock DynamoDB: cache hit
    mock_dynamodb.get_item.return_value = make_cached_analysis_item(VALID_UUID)

    from backend.analysis.handler import lambda_handler

    response = lambda_handler(make_event(VALID_UUID), lambda_context)

    assert response["statusCode"] == 200
    body = json.loads(response["body"])
    assert body["cached"] is True
    assert body["document_id"] == VALID_UUID
    assert body["summary_plain"] != ""
    assert body["risk_score"] == 35
    assert len(body["clauses"]) == 1
    assert body["overall_recommendation"] != ""


@patch("backend.analysis.analyzer._bedrock_client")
@patch("backend.analysis.analyzer._dynamodb_client")
def test_cache_hit_no_bedrock_call(mock_dynamodb, mock_bedrock, lambda_context):
    """Camino A: cache hit NO invoca Bedrock."""
    mock_dynamodb.get_item.return_value = make_cached_analysis_item(VALID_UUID)

    from backend.analysis.handler import lambda_handler

    lambda_handler(make_event(VALID_UUID), lambda_context)

    # Bedrock nunca fue llamado
    mock_bedrock.invoke_model.assert_not_called()



# ============================================================================
# Fase 3 — Tests de validación de request (Task 10)
# ============================================================================


@patch("backend.analysis.analyzer._bedrock_client")
@patch("backend.analysis.analyzer._dynamodb_client")
def test_missing_document_id(mock_dynamodb, mock_bedrock, lambda_context):
    """Body sin campo document_id -> HTTP 400, MISSING_DOCUMENT_ID, sin document_id en respuesta."""
    from backend.analysis.handler import lambda_handler

    event = {"body": "{}"}
    response = lambda_handler(event, lambda_context)

    assert response["statusCode"] == 400
    body = json.loads(response["body"])
    assert body["error_code"] == "MISSING_DOCUMENT_ID"
    assert "document_id" not in body
    assert response["headers"]["Content-Type"] == "application/json"

    # DynamoDB no debe haber sido consultado
    mock_dynamodb.get_item.assert_not_called()


@patch("backend.analysis.analyzer._bedrock_client")
@patch("backend.analysis.analyzer._dynamodb_client")
def test_empty_document_id(mock_dynamodb, mock_bedrock, lambda_context):
    """Body con document_id vacío -> HTTP 400, MISSING_DOCUMENT_ID."""
    from backend.analysis.handler import lambda_handler

    event = {"body": json.dumps({"document_id": ""})}
    response = lambda_handler(event, lambda_context)

    assert response["statusCode"] == 400
    body = json.loads(response["body"])
    assert body["error_code"] == "MISSING_DOCUMENT_ID"
    assert "document_id" not in body
    assert response["headers"]["Content-Type"] == "application/json"

    mock_dynamodb.get_item.assert_not_called()


@patch("backend.analysis.analyzer._bedrock_client")
@patch("backend.analysis.analyzer._dynamodb_client")
def test_invalid_document_id_format(mock_dynamodb, mock_bedrock, lambda_context):
    """UUID malformado -> HTTP 400, INVALID_DOCUMENT_ID."""
    from backend.analysis.handler import lambda_handler

    event = {"body": json.dumps({"document_id": "no-es-uuid-valido"})}
    response = lambda_handler(event, lambda_context)

    assert response["statusCode"] == 400
    body = json.loads(response["body"])
    assert body["error_code"] == "INVALID_DOCUMENT_ID"
    assert response["headers"]["Content-Type"] == "application/json"

    mock_dynamodb.get_item.assert_not_called()


@patch("backend.analysis.analyzer._bedrock_client")
@patch("backend.analysis.analyzer._dynamodb_client")
def test_invalid_document_id_v1(mock_dynamodb, mock_bedrock, lambda_context):
    """UUID v1 (no v4) -> HTTP 400, INVALID_DOCUMENT_ID."""
    from backend.analysis.handler import lambda_handler

    # UUID v1: el tercer grupo empieza con 1, no con 4
    uuid_v1 = "550e8400-e29b-11d4-a716-446655440000"
    event = {"body": json.dumps({"document_id": uuid_v1})}
    response = lambda_handler(event, lambda_context)

    assert response["statusCode"] == 400
    body = json.loads(response["body"])
    assert body["error_code"] == "INVALID_DOCUMENT_ID"
    assert response["headers"]["Content-Type"] == "application/json"

    mock_dynamodb.get_item.assert_not_called()



# ============================================================================
# Fase 3 — Tests de DOCUMENT_NOT_FOUND y CONTEXT_TOO_LONG (Task 11)
# ============================================================================


@patch("backend.analysis.analyzer._bedrock_client")
@patch("backend.analysis.analyzer._dynamodb_client")
def test_document_not_found(mock_dynamodb, mock_bedrock, lambda_context):
    """document_id no existe en ContractExtractions -> HTTP 404, DOCUMENT_NOT_FOUND."""
    # Ambas tablas retornan vacío
    mock_dynamodb.get_item.return_value = {}

    from backend.analysis.handler import lambda_handler

    response = lambda_handler(make_event(VALID_UUID), lambda_context)

    assert response["statusCode"] == 404
    body = json.loads(response["body"])
    assert body["error_code"] == "DOCUMENT_NOT_FOUND"
    # document_id presente porque el UUID era válido
    assert body["document_id"] == VALID_UUID


@patch("backend.analysis.analyzer._bedrock_client")
@patch("backend.analysis.analyzer._dynamodb_client")
def test_context_too_long(mock_dynamodb, mock_bedrock, lambda_context, monkeypatch):
    """raw_text excede MAX_CONTEXT_CHARS -> HTTP 422, CONTEXT_TOO_LONG, Bedrock no invocado."""
    # Reducir MAX_CONTEXT_CHARS para el test
    monkeypatch.setenv("MAX_CONTEXT_CHARS", "100")

    # No cache, sí extracción con texto largo
    def get_item_side_effect(**kwargs):
        table = kwargs["TableName"]
        if table == "ContractAnalyses":
            return {}
        elif table == "ContractExtractions":
            return make_extraction_item(VALID_UUID, "a" * 101)
        return {}

    mock_dynamodb.get_item.side_effect = get_item_side_effect

    from backend.analysis.handler import lambda_handler

    response = lambda_handler(make_event(VALID_UUID), lambda_context)

    assert response["statusCode"] == 422
    body = json.loads(response["body"])
    assert body["error_code"] == "CONTEXT_TOO_LONG"
    assert body["document_id"] == VALID_UUID

    # Bedrock no debe haber sido invocado
    mock_bedrock.invoke_model.assert_not_called()



# ============================================================================
# Fase 3 — Tests de DOCUMENT_NOT_FOUND y CONTEXT_TOO_LONG (Task 11)
# ============================================================================


@patch("backend.analysis.analyzer._bedrock_client")
@patch("backend.analysis.analyzer._dynamodb_client")
def test_document_not_found(mock_dynamodb, mock_bedrock, lambda_context):
    """document_id inexistente en ambas tablas -> HTTP 404, DOCUMENT_NOT_FOUND, document_id presente."""
    from backend.analysis.handler import lambda_handler

    # Ambas tablas retornan vacío
    mock_dynamodb.get_item.return_value = {}

    response = lambda_handler(make_event(VALID_UUID), lambda_context)

    assert response["statusCode"] == 404
    body = json.loads(response["body"])
    assert body["error_code"] == "DOCUMENT_NOT_FOUND"
    assert body["document_id"] == VALID_UUID


@patch("backend.analysis.analyzer._bedrock_client")
@patch("backend.analysis.analyzer._dynamodb_client")
def test_context_too_long(mock_dynamodb, mock_bedrock, lambda_context, monkeypatch):
    """raw_text excede MAX_CONTEXT_CHARS -> HTTP 422, CONTEXT_TOO_LONG, Bedrock no invocado."""
    from backend.analysis.handler import lambda_handler

    # Setear un límite bajo para forzar el error
    monkeypatch.setenv("MAX_CONTEXT_CHARS", "50")

    # No cache, sí extracción con texto largo
    long_text = "a" * 51

    def get_item_side_effect(**kwargs):
        table = kwargs["TableName"]
        if table == "ContractAnalyses":
            return {}
        elif table == "ContractExtractions":
            return make_extraction_item(VALID_UUID, long_text)
        return {}

    mock_dynamodb.get_item.side_effect = get_item_side_effect

    response = lambda_handler(make_event(VALID_UUID), lambda_context)

    assert response["statusCode"] == 422
    body = json.loads(response["body"])
    assert body["error_code"] == "CONTEXT_TOO_LONG"
    assert body["document_id"] == VALID_UUID

    # Bedrock no fue invocado
    mock_bedrock.invoke_model.assert_not_called()



# ============================================================================
# Fase 3 — Tests de errores de Bedrock (Task 12)
# ============================================================================

from botocore.exceptions import ClientError, ReadTimeoutError


@patch("backend.analysis.analyzer._bedrock_client")
@patch("backend.analysis.analyzer._dynamodb_client")
def test_bedrock_timeout(mock_dynamodb, mock_bedrock, lambda_context):
    """Bedrock no responde a tiempo -> HTTP 503, BEDROCK_TIMEOUT, put_item no llamado."""
    from backend.analysis.handler import lambda_handler

    def get_item_side_effect(**kwargs):
        table = kwargs["TableName"]
        if table == "ContractAnalyses":
            return {}
        elif table == "ContractExtractions":
            return make_extraction_item(VALID_UUID, SAMPLE_RAW_TEXT)
        return {}

    mock_dynamodb.get_item.side_effect = get_item_side_effect
    mock_bedrock.invoke_model.side_effect = ReadTimeoutError(
        endpoint_url="https://bedrock.us-east-1.amazonaws.com"
    )

    response = lambda_handler(make_event(VALID_UUID), lambda_context)

    assert response["statusCode"] == 503
    body = json.loads(response["body"])
    assert body["error_code"] == "BEDROCK_TIMEOUT"
    assert body["document_id"] == VALID_UUID
    mock_dynamodb.put_item.assert_not_called()


@patch("backend.analysis.analyzer._bedrock_client")
@patch("backend.analysis.analyzer._dynamodb_client")
def test_bedrock_throttled(mock_dynamodb, mock_bedrock, lambda_context):
    """Bedrock rechaza por throttling -> HTTP 503, BEDROCK_THROTTLED, put_item no llamado."""
    from backend.analysis.handler import lambda_handler

    def get_item_side_effect(**kwargs):
        table = kwargs["TableName"]
        if table == "ContractAnalyses":
            return {}
        elif table == "ContractExtractions":
            return make_extraction_item(VALID_UUID, SAMPLE_RAW_TEXT)
        return {}

    mock_dynamodb.get_item.side_effect = get_item_side_effect
    mock_bedrock.invoke_model.side_effect = ClientError(
        {"Error": {"Code": "ThrottlingException", "Message": "Rate exceeded"}},
        "InvokeModel",
    )

    response = lambda_handler(make_event(VALID_UUID), lambda_context)

    assert response["statusCode"] == 503
    body = json.loads(response["body"])
    assert body["error_code"] == "BEDROCK_THROTTLED"
    assert body["document_id"] == VALID_UUID
    mock_dynamodb.put_item.assert_not_called()


@patch("backend.analysis.analyzer._bedrock_client")
@patch("backend.analysis.analyzer._dynamodb_client")
def test_bedrock_service_error(mock_dynamodb, mock_bedrock, lambda_context):
    """Bedrock error genérico -> HTTP 502, BEDROCK_SERVICE_ERROR, put_item no llamado."""
    from backend.analysis.handler import lambda_handler

    def get_item_side_effect(**kwargs):
        table = kwargs["TableName"]
        if table == "ContractAnalyses":
            return {}
        elif table == "ContractExtractions":
            return make_extraction_item(VALID_UUID, SAMPLE_RAW_TEXT)
        return {}

    mock_dynamodb.get_item.side_effect = get_item_side_effect
    mock_bedrock.invoke_model.side_effect = ClientError(
        {"Error": {"Code": "InternalServerError", "Message": "Something broke"}},
        "InvokeModel",
    )

    response = lambda_handler(make_event(VALID_UUID), lambda_context)

    assert response["statusCode"] == 502
    body = json.loads(response["body"])
    assert body["error_code"] == "BEDROCK_SERVICE_ERROR"
    assert body["document_id"] == VALID_UUID
    mock_dynamodb.put_item.assert_not_called()



# ============================================================================
# Fase 3 — Tests de MODEL_RESPONSE_INVALID y PERSISTENCE_FAILURE (Task 13)
# ============================================================================


def _make_bedrock_raw_response(text_content: str) -> dict:
    """Helper: construye una respuesta Bedrock mock con un text_content arbitrario."""
    response_body = json.dumps({
        "id": "msg_test",
        "type": "message",
        "role": "assistant",
        "content": [{"type": "text", "text": text_content}],
        "model": "claude-3-haiku-20240307",
        "stop_reason": "end_turn",
        "usage": {"input_tokens": 100, "output_tokens": 50},
    })
    body_mock = MagicMock()
    body_mock.read.return_value = response_body.encode("utf-8")
    return {"body": body_mock}


@patch("backend.analysis.analyzer._bedrock_client")
@patch("backend.analysis.analyzer._dynamodb_client")
def test_model_response_invalid_json(mock_dynamodb, mock_bedrock, lambda_context):
    """Bedrock retorna string no-JSON -> HTTP 422, MODEL_RESPONSE_INVALID."""
    from backend.analysis.handler import lambda_handler

    def get_item_side_effect(**kwargs):
        table = kwargs["TableName"]
        if table == "ContractAnalyses":
            return {}
        elif table == "ContractExtractions":
            return make_extraction_item(VALID_UUID, SAMPLE_RAW_TEXT)
        return {}

    mock_dynamodb.get_item.side_effect = get_item_side_effect
    mock_bedrock.invoke_model.return_value = _make_bedrock_raw_response("esto no es json")

    response = lambda_handler(make_event(VALID_UUID), lambda_context)

    assert response["statusCode"] == 422
    body = json.loads(response["body"])
    assert body["error_code"] == "MODEL_RESPONSE_INVALID"


@patch("backend.analysis.analyzer._bedrock_client")
@patch("backend.analysis.analyzer._dynamodb_client")
def test_model_response_missing_fields(mock_dynamodb, mock_bedrock, lambda_context):
    """Bedrock retorna JSON sin campos requeridos -> HTTP 422, MODEL_RESPONSE_INVALID."""
    from backend.analysis.handler import lambda_handler

    def get_item_side_effect(**kwargs):
        table = kwargs["TableName"]
        if table == "ContractAnalyses":
            return {}
        elif table == "ContractExtractions":
            return make_extraction_item(VALID_UUID, SAMPLE_RAW_TEXT)
        return {}

    mock_dynamodb.get_item.side_effect = get_item_side_effect
    # JSON válido pero sin summary_plain ni overall_recommendation
    incomplete_json = json.dumps({"clauses": []})
    mock_bedrock.invoke_model.return_value = _make_bedrock_raw_response(incomplete_json)

    response = lambda_handler(make_event(VALID_UUID), lambda_context)

    assert response["statusCode"] == 422
    body = json.loads(response["body"])
    assert body["error_code"] == "MODEL_RESPONSE_INVALID"


@patch("backend.analysis.analyzer._bedrock_client")
@patch("backend.analysis.analyzer._dynamodb_client")
def test_model_response_invalid_enum(mock_dynamodb, mock_bedrock, lambda_context):
    """Bedrock retorna JSON con risk_level inválido -> HTTP 422, MODEL_RESPONSE_INVALID."""
    from backend.analysis.handler import lambda_handler

    def get_item_side_effect(**kwargs):
        table = kwargs["TableName"]
        if table == "ContractAnalyses":
            return {}
        elif table == "ContractExtractions":
            return make_extraction_item(VALID_UUID, SAMPLE_RAW_TEXT)
        return {}

    mock_dynamodb.get_item.side_effect = get_item_side_effect
    # JSON con enum inválido
    invalid_enum_json = json.dumps({
        "summary_plain": "Resumen",
        "clauses": [{
            "clause_text": "Cláusula ejemplo",
            "category": "multa",
            "risk_level": "muy_alto",  # valor inválido
            "explanation": "Explicación",
            "suggested_question": "Pregunta",
        }],
        "overall_recommendation": "Recomendación",
    })
    mock_bedrock.invoke_model.return_value = _make_bedrock_raw_response(invalid_enum_json)

    response = lambda_handler(make_event(VALID_UUID), lambda_context)

    assert response["statusCode"] == 422
    body = json.loads(response["body"])
    assert body["error_code"] == "MODEL_RESPONSE_INVALID"


@patch("backend.analysis.analyzer._bedrock_client")
@patch("backend.analysis.analyzer._dynamodb_client")
def test_persistence_failure(mock_dynamodb, mock_bedrock, lambda_context):
    """put_item falla -> HTTP 502, PERSISTENCE_FAILURE, document_id presente."""
    from backend.analysis.handler import lambda_handler

    def get_item_side_effect(**kwargs):
        table = kwargs["TableName"]
        if table == "ContractAnalyses":
            return {}
        elif table == "ContractExtractions":
            return make_extraction_item(VALID_UUID, SAMPLE_RAW_TEXT)
        return {}

    mock_dynamodb.get_item.side_effect = get_item_side_effect
    # Bedrock responde bien
    mock_bedrock.invoke_model.return_value = make_bedrock_response()
    # Pero put_item falla
    mock_dynamodb.put_item.side_effect = ClientError(
        {"Error": {"Code": "InternalServerError", "Message": "DynamoDB down"}},
        "PutItem",
    )

    response = lambda_handler(make_event(VALID_UUID), lambda_context)

    assert response["statusCode"] == 502
    body = json.loads(response["body"])
    assert body["error_code"] == "PERSISTENCE_FAILURE"
    assert body["document_id"] == VALID_UUID



# ============================================================================
# Fase 3 — Tests de INTERNAL_ERROR (Task 14)
# ============================================================================


@patch("backend.analysis.handler.logger")
@patch("backend.analysis.analyzer._bedrock_client")
@patch("backend.analysis.analyzer._dynamodb_client")
def test_internal_error_no_leak(mock_dynamodb, mock_bedrock, mock_logger, lambda_context):
    """Excepción inesperada -> HTTP 500, INTERNAL_ERROR, sin detalles internos en respuesta."""
    from backend.analysis.handler import lambda_handler

    # Forzar una excepción inesperada en get_cached_analysis
    mock_dynamodb.get_item.side_effect = RuntimeError("detalle interno secreto")

    response = lambda_handler(make_event(VALID_UUID), lambda_context)

    assert response["statusCode"] == 500
    body = json.loads(response["body"])
    assert body["error_code"] == "INTERNAL_ERROR"

    # El body NO debe contener detalles internos
    assert "detalle interno secreto" not in body["message"]
    assert "Traceback" not in body["message"]
    assert "RuntimeError" not in body["message"]

    # El message debe ser un string no vacío
    assert len(body["message"]) > 0

    # El logger debe haber capturado el traceback internamente
    mock_logger.exception.assert_called_once()



# ============================================================================
# Fase 6 — Property-based tests con Hypothesis (Task 17)
# ============================================================================

from hypothesis import given, settings, assume
from hypothesis import strategies as st

from backend.analysis.analyzer import calculate_risk_score, validate_document_id
from backend.analysis.models import (
    AnalysisResult,
    Clause,
    build_analysis_dynamodb_item,
    deserialize_analysis_item,
)
from backend.shared.exceptions import AnalysisError


# Strategies reutilizables
_risk_levels = st.sampled_from(["bajo", "medio", "alto"])
_categories = st.sampled_from([
    "renovacion_automatica", "multa", "jurisdiccion", "cesion_datos", "otro"
])

_clause_strategy = st.builds(
    Clause,
    clause_text=st.text(min_size=1, max_size=100),
    category=_categories,
    risk_level=_risk_levels,
    explanation=st.text(min_size=0, max_size=200),
    suggested_question=st.text(min_size=0, max_size=200),
)


@settings(max_examples=100)
@given(clauses=st.lists(_clause_strategy, min_size=0, max_size=20))
def test_property_risk_score_bounded(clauses):
    """Feature: analysis, Property 1: Risk score bounded invariant.

    Para cualquier lista de cláusulas con risk_levels válidos,
    calculate_risk_score produce un entero en [0, 100].
    """
    score = calculate_risk_score(clauses)
    assert isinstance(score, int)
    assert 0 <= score <= 100


@settings(max_examples=100)
@given(
    clauses=st.lists(_clause_strategy, min_size=0, max_size=15),
    extra_clause=_clause_strategy,
)
def test_property_risk_score_monotonic(clauses, extra_clause):
    """Feature: analysis, Property 2: Risk score monotonicity.

    Para cualquier lista L y cláusula adicional c,
    risk_score(L + [c]) >= risk_score(L).
    """
    score_base = calculate_risk_score(clauses)
    score_extended = calculate_risk_score(clauses + [extra_clause])
    assert score_extended >= score_base


def test_property_risk_score_zero_empty():
    """Feature: analysis, Property 3: Risk score zero for empty clauses.

    calculate_risk_score([]) == 0.
    """
    assert calculate_risk_score([]) == 0


@settings(max_examples=100)
@given(
    document_id=st.from_regex(
        r"^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$"
    ),
    summary_plain=st.text(min_size=1, max_size=200),
    risk_score=st.integers(min_value=0, max_value=100),
    clauses=st.lists(_clause_strategy, min_size=0, max_size=5),
    overall_recommendation=st.text(min_size=1, max_size=200),
)
def test_property_serialization_round_trip(
    document_id, summary_plain, risk_score, clauses, overall_recommendation
):
    """Feature: analysis, Property 4: Cache round-trip fidelity.

    Para cualquier AnalysisResult válido, serializar y deserializar
    produce campos equivalentes al original.
    """
    result = AnalysisResult(
        document_id=document_id,
        summary_plain=summary_plain,
        risk_score=risk_score,
        clauses=clauses,
        overall_recommendation=overall_recommendation,
    )

    dynamo_item = build_analysis_dynamodb_item(result)
    deserialized = deserialize_analysis_item(dynamo_item)

    assert deserialized["document_id"] == result.document_id
    assert deserialized["summary_plain"] == result.summary_plain
    assert deserialized["risk_score"] == result.risk_score
    assert deserialized["overall_recommendation"] == result.overall_recommendation
    assert len(deserialized["clauses"]) == len(result.clauses)

    for orig, deser in zip(result.clauses, deserialized["clauses"]):
        assert deser["clause_text"] == orig.clause_text
        assert deser["category"] == orig.category
        assert deser["risk_level"] == orig.risk_level
        assert deser["explanation"] == orig.explanation
        assert deser["suggested_question"] == orig.suggested_question


@settings(max_examples=100)
@given(
    s=st.text(min_size=1, max_size=50).filter(
        lambda x: not __import__("re").match(
            r"^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$", x
        )
    )
)
def test_property_invalid_uuid_rejected(s):
    """Feature: analysis, Property 7: Invalid UUID rejection.

    Para cualquier string que no sea UUID v4 válido,
    validate_document_id lanza AnalysisError.
    """
    try:
        validate_document_id({"document_id": s})
        # Si no lanza, es un bug
        assert False, f"Should have raised AnalysisError for '{s}'"
    except AnalysisError as e:
        assert e.error_code.value in ("MISSING_DOCUMENT_ID", "INVALID_DOCUMENT_ID")
