"""Fixtures compartidas para tests del Módulo 2 (Analysis)."""
from __future__ import annotations

import json
import os
import time
from unittest.mock import MagicMock, patch

import pytest


# ============================================================================
# Variables de entorno para tests
# ============================================================================

@pytest.fixture(autouse=True)
def set_env_vars(monkeypatch):
    """Setea todas las variables de entorno requeridas por el módulo."""
    monkeypatch.setenv("ANALYSES_TABLE_NAME", "ContractAnalyses")
    monkeypatch.setenv("EXTRACTIONS_TABLE_NAME", "ContractExtractions")
    monkeypatch.setenv("BEDROCK_MODEL_ID", "anthropic.claude-3-haiku-20240307-v1:0")
    monkeypatch.setenv("MAX_CONTEXT_CHARS", "150000")
    monkeypatch.setenv("BEDROCK_TIMEOUT_SECONDS", "45")
    monkeypatch.setenv("AWS_DEFAULT_REGION", "us-east-1")
    monkeypatch.setenv("LOG_LEVEL", "INFO")


# ============================================================================
# Lambda context mock
# ============================================================================

@pytest.fixture
def lambda_context():
    """Mock del contexto Lambda con aws_request_id."""
    ctx = MagicMock()
    ctx.aws_request_id = "test-request-id"
    return ctx


# ============================================================================
# Helpers para construir eventos y datos de prueba
# ============================================================================

def make_event(document_id: str) -> dict:
    """Construye un evento API Gateway con el document_id dado."""
    return {
        "body": json.dumps({"document_id": document_id}),
    }


def make_extraction_item(document_id: str, raw_text: str) -> dict:
    """Construye un ítem DynamoDB en formato AttributeValue simulando ContractExtractions."""
    return {
        "Item": {
            "document_id": {"S": document_id},
            "raw_text": {"S": raw_text},
            "extraction_method": {"S": "text"},
            "page_count": {"N": "3"},
            "metadata": {
                "M": {
                    "filename": {"S": "contrato.pdf"},
                    "uploaded_at": {"S": "2024-01-15T10:30:00Z"},
                }
            },
        }
    }


def make_cached_analysis_item(document_id: str) -> dict:
    """Construye un ítem DynamoDB en formato AttributeValue simulando ContractAnalyses con cache."""
    ttl_value = int(time.time()) + 604800
    return {
        "Item": {
            "document_id": {"S": document_id},
            "summary_plain": {"S": "Este es un contrato de alquiler estándar."},
            "risk_score": {"N": "35"},
            "clauses": {
                "L": [
                    {
                        "M": {
                            "clause_text": {"S": "El contrato se renueva automáticamente."},
                            "category": {"S": "renovacion_automatica"},
                            "risk_level": {"S": "medio"},
                            "explanation": {"S": "Se renueva sin que hagas nada."},
                            "suggested_question": {"S": "¿Puedo cancelar la renovación?"},
                        }
                    }
                ]
            },
            "overall_recommendation": {"S": "Negociar la cláusula de renovación."},
            "ttl": {"N": str(ttl_value)},
        }
    }


def make_bedrock_response(clauses: list[dict] | None = None) -> dict:
    """Construye una respuesta mock de Bedrock invoke_model.

    Args:
        clauses: Lista de cláusulas para incluir. Si None, usa una cláusula de ejemplo.
    """
    if clauses is None:
        clauses = [
            {
                "clause_text": "El contrato se renueva automáticamente cada 12 meses.",
                "category": "renovacion_automatica",
                "risk_level": "medio",
                "explanation": "El contrato se renueva sin necesidad de acción del inquilino.",
                "suggested_question": "¿Puedo optar por no renovar sin penalización?",
            }
        ]

    model_output = {
        "summary_plain": "Contrato de alquiler con cláusulas estándar.",
        "clauses": clauses,
        "overall_recommendation": "Revisar la cláusula de renovación automática.",
    }

    # Simular la estructura de respuesta de Bedrock/Claude
    response_body = json.dumps({
        "id": "msg_test123",
        "type": "message",
        "role": "assistant",
        "content": [{"type": "text", "text": json.dumps(model_output)}],
        "model": "claude-3-haiku-20240307",
        "stop_reason": "end_turn",
        "usage": {"input_tokens": 500, "output_tokens": 200},
    })

    # Bedrock retorna un StreamingBody mock
    body_mock = MagicMock()
    body_mock.read.return_value = response_body.encode("utf-8")

    return {"body": body_mock}
