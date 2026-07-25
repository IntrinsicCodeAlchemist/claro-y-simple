"""
Tests de integración contra LocalStack.

PRECONDICIÓN:
  1. LocalStack debe estar corriendo:
       podman run --rm -d -p 4566:4566 localstack/localstack
  2. Los recursos AWS deben estar creados:
       python scripts/setup_localstack.py
  3. Variables de entorno:
       ENVIRONMENT=localstack
       AWS_ENDPOINT_URL=http://localhost:4566
       AWS_DEFAULT_REGION=us-east-1
       AWS_ACCESS_KEY_ID=test
       AWS_SECRET_ACCESS_KEY=test
       DYNAMODB_TABLE_NAME=ContractExtractions
       S3_BUCKET_NAME=claro-y-simple-contracts

  Se puede ejecutar con:
    $env:ENVIRONMENT='localstack'; ... pytest -v -m integration
"""
import base64
import json
import os
import re
import sys

import pytest

# Los tests de integración requieren LocalStack.
# Si las variables de entorno no están configuradas, se saltean todos los tests.
pytestmark = pytest.mark.skipif(
    os.environ.get("ENVIRONMENT") != "localstack",
    reason="Requiere ENVIRONMENT=localstack y LocalStack corriendo",
)

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from datetime import datetime, timezone  # noqa: E402
from unittest.mock import patch  # noqa: E402

from ingestion.handler import lambda_handler  # noqa: E402
from ingestion.models import ExtractionResult, ExtractionMetadata  # noqa: E402
from shared.aws_utils import get_boto3_client  # noqa: E402

BOUNDARY = "----IntegrationTestBoundary"
S3_BUCKET = os.environ.get("S3_BUCKET_NAME", "claro-y-simple-contracts")
DYNAMODB_TABLE = os.environ.get("DYNAMODB_TABLE_NAME", "ContractExtractions")

FIXTURES_DIR = os.path.join(os.path.dirname(__file__), "fixtures")


def _build_event(pdf_bytes: bytes, filename: str = "sample_text.pdf") -> dict:
    """Construye un evento API Gateway para lambda_handler."""
    header = (
        f"--{BOUNDARY}\r\n"
        f'Content-Disposition: form-data; name="file"; filename="{filename}"\r\n'
        f"Content-Type: application/pdf\r\n\r\n"
    ).encode("utf-8")
    footer = f"\r\n--{BOUNDARY}--\r\n".encode("utf-8")
    body = header + pdf_bytes + footer
    return {
        "body": base64.b64encode(body).decode("ascii"),
        "isBase64Encoded": True,
        "headers": {"Content-Type": f"multipart/form-data; boundary={BOUNDARY}"},
    }


class FakeContext:
    aws_request_id = "integ-test-request-001"


@pytest.fixture(scope="session")
def s3_client():
    return get_boto3_client("s3")


@pytest.fixture(scope="session")
def dynamo_client():
    return get_boto3_client("dynamodb")


# =============================================================================
# Test 1: Flujo completo — extracción con texto embebido
# =============================================================================


@pytest.mark.integration
def test_integration_full_flow_text_extraction(s3_client, dynamo_client):
    """Flujo completo: sube PDF, extrae texto, persiste en DynamoDB."""
    pdf_path = os.path.join(FIXTURES_DIR, "sample_text.pdf")
    with open(pdf_path, "rb") as f:
        pdf_bytes = f.read()

    event = _build_event(pdf_bytes)
    ctx = FakeContext()

    with patch("ingestion.extractor._textract_client"):
        # Textract no debería ser llamado — pdfplumber extrae el texto
        response = lambda_handler(event, ctx)

    assert response["statusCode"] == 200
    body = json.loads(response["body"])
    document_id = body["document_id"]
    assert re.match(
        r'^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$',
        document_id,
    ), f"document_id no es un UUID v4 válido: {document_id}"

    # Verificar objeto en S3
    s3_obj = s3_client.head_object(Bucket=S3_BUCKET, Key=f"contracts/{document_id}.pdf")
    assert s3_obj["ResponseMetadata"]["HTTPStatusCode"] == 200

    # Verificar ítem en DynamoDB (Contrato 1)
    item = dynamo_client.get_item(
        TableName=DYNAMODB_TABLE,
        Key={"document_id": {"S": document_id}},
    )["Item"]
    assert item["extraction_method"]["S"] == "text"
    assert len(item["raw_text"]["S"].strip()) > 0
    assert int(item["page_count"]["N"]) > 0
    assert "ttl" in item
    assert item["metadata"]["M"]["filename"]["S"] == "sample_text.pdf"
    uploaded_at = item["metadata"]["M"]["uploaded_at"]["S"]
    assert re.match(
        r'^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$',
        uploaded_at,
    ), f"uploaded_at no cumple ISO 8601 UTC: {uploaded_at}"

    # Limpiar
    s3_client.delete_object(Bucket=S3_BUCKET, Key=f"contracts/{document_id}.pdf")
    dynamo_client.delete_item(
        TableName=DYNAMODB_TABLE,
        Key={"document_id": {"S": document_id}},
    )


# =============================================================================
# Test 2: Round-trip — serialización/deserialización del Contrato 1
# =============================================================================


@pytest.mark.integration
def test_integration_contract1_roundtrip(s3_client, dynamo_client):
    """Persiste y lee un ExtractionResult; todos los campos se preservan."""
    now = datetime.now(timezone.utc)
    original = ExtractionResult(
        document_id="a1b2c3d4-e5f6-4789-abc0-def123456789",
        raw_text="Cláusula de penalización por rescisión anticipada.\nSe aplicará multa del 10%.",
        extraction_method="text",
        page_count=2,
        metadata=ExtractionMetadata(
            filename="contrato.pdf",
            uploaded_at=now,
        ),
        ttl=int(now.timestamp()) + 86400,
    )

    from ingestion.models import build_dynamodb_item

    item = build_dynamodb_item(original)

    # Escribir en DynamoDB real
    dynamo_client.put_item(TableName=DYNAMODB_TABLE, Item=item)

    # Leer de vuelta
    stored = dynamo_client.get_item(
        TableName=DYNAMODB_TABLE,
        Key={"document_id": {"S": original.document_id}},
    )["Item"]

    # Verificar campos del Contrato 1
    assert stored["document_id"]["S"] == original.document_id
    assert stored["raw_text"]["S"] == original.raw_text
    assert stored["extraction_method"]["S"] == original.extraction_method
    assert int(stored["page_count"]["N"]) == original.page_count
    assert stored["metadata"]["M"]["filename"]["S"] == original.metadata.filename

    uploaded_at_str = stored["metadata"]["M"]["uploaded_at"]["S"]
    assert uploaded_at_str.endswith("Z")

    # Step 2: round-trip con deserialize_dynamodb_item — cumple Property 4 (Req 8.6)
    from ingestion.models import deserialize_dynamodb_item

    deserialized = deserialize_dynamodb_item(stored)

    assert deserialized["document_id"] == original.document_id
    assert deserialized["raw_text"] == original.raw_text
    assert deserialized["extraction_method"] == original.extraction_method
    assert deserialized["page_count"] == original.page_count
    assert deserialized["metadata"]["filename"] == original.metadata.filename
    assert deserialized["metadata"]["uploaded_at"] == uploaded_at_str
    assert deserialized["ttl"] == original.ttl

    # Limpiar
    dynamo_client.delete_item(
        TableName=DYNAMODB_TABLE,
        Key={"document_id": {"S": original.document_id}},
    )


# =============================================================================
# Test 3: EMPTY_EXTRACTION no escribe en DynamoDB
# =============================================================================


@pytest.mark.integration
def test_integration_empty_extraction_no_dynamodb_write(s3_client, dynamo_client):
    """PDF sin texto → 422, no se persiste nada en DynamoDB."""
    pdf_path = os.path.join(FIXTURES_DIR, "sample_empty.pdf")
    with open(pdf_path, "rb") as f:
        pdf_bytes = f.read()

    event = _build_event(pdf_bytes)
    ctx = FakeContext()

    with patch("ingestion.extractor._textract_client") as mock_textract:
        mock_textract.detect_document_text.return_value = {"Blocks": []}
        response = lambda_handler(event, ctx)

    assert response["statusCode"] == 422
    body = json.loads(response["body"])
    assert body["error_code"] == "EMPTY_EXTRACTION"
    document_id = body.get("document_id")

    # Verificar que NO haya registro en DynamoDB
    if document_id:
        result = dynamo_client.get_item(
            TableName=DYNAMODB_TABLE,
            Key={"document_id": {"S": document_id}},
        )
        assert "Item" not in result, "No debería haber registro en DynamoDB"
