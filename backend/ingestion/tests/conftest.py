"""Fixtures compartidos para los tests del módulo de ingesta."""
import os

# Configurar entorno ANTES de cualquier import del módulo ingestion
# para que los module-scope checks en handler.py y extractor.py pasen.
os.environ.setdefault("DYNAMODB_TABLE_NAME", "ContractExtractions")
os.environ.setdefault("S3_BUCKET_NAME", "claro-y-simple-contracts")
os.environ.setdefault("AWS_REGION", "us-east-1")
os.environ.setdefault("AWS_DEFAULT_REGION", "us-east-1")
os.environ.setdefault("AWS_ACCESS_KEY_ID", "test")
os.environ.setdefault("AWS_SECRET_ACCESS_KEY", "test")

import pytest


def pytest_configure(config):
    """Registra marks personalizados para evitar warnings."""
    config.addinivalue_line("markers", "integration: tests que requieren LocalStack corriendo")


@pytest.fixture
def lambda_context() -> object:
    """Fixture que retorna un objeto context simulado de Lambda."""

    class FakeContext:
        aws_request_id = "test-request-abc123"

    return FakeContext()


@pytest.fixture
def scanned_pdf_bytes() -> bytes:
    """Fixture que retorna los bytes del PDF escaneado (sin texto extraíble)."""
    fixture_path = os.path.join(
        os.path.dirname(__file__),
        "fixtures",
        "sample_scanned.pdf",
    )
    with open(fixture_path, "rb") as f:
        return f.read()


@pytest.fixture
def empty_pdf_bytes() -> bytes:
    """Fixture que retorna los bytes de un PDF vacío (sin texto extraíble)."""
    fixture_path = os.path.join(
        os.path.dirname(__file__),
        "fixtures",
        "sample_empty.pdf",
    )
    with open(fixture_path, "rb") as f:
        return f.read()


@pytest.fixture
def corrupted_pdf_bytes() -> bytes:
    """Fixture que retorna bytes de un PDF corrupto (no procesable)."""
    fixture_path = os.path.join(
        os.path.dirname(__file__),
        "fixtures",
        "sample_corrupted.pdf",
    )
    with open(fixture_path, "rb") as f:
        return f.read()


@pytest.fixture
def sample_pdf_bytes() -> bytes:
    """Fixture que retorna los bytes del PDF de prueba."""
    fixture_path = os.path.join(
        os.path.dirname(__file__),
        "fixtures",
        "sample_text.pdf",
    )
    with open(fixture_path, "rb") as f:
        return f.read()
