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
