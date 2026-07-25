"""Tests unitarios del extractor (pdfplumber y Textract)."""
import uuid
from datetime import datetime, timezone
from unittest.mock import patch

import pytest
from hypothesis import given, strategies as st
from pydantic import ValidationError as PydanticValidationError

from botocore.exceptions import ClientError

from ingestion.extractor import extract_text
from ingestion.models import (
    ExtractionResult,
    ExtractionMetadata,
    build_dynamodb_item,
    deserialize_dynamodb_item,
)
from shared.exceptions import ExtractionError, ExtractionErrorCode


class TestExtractTextPdfplumberSuccess:
    """Camino feliz: pdfplumber extrae texto correctamente."""

    def test_extraction_method_is_text(self, sample_pdf_bytes):
        """Verifica que extraction_method sea 'text' cuando pdfplumber tiene éxito."""
        result = extract_text(
            pdf_bytes=sample_pdf_bytes,
            document_id="test-uuid-0001",
            s3_key="contracts/test-uuid-0001.pdf",
            s3_bucket="test-bucket",
        )
        assert result.extraction_method == "text"

    def test_raw_text_is_not_empty(self, sample_pdf_bytes):
        """Verifica que raw_text contenga al menos un carácter no-whitespace."""
        result = extract_text(
            pdf_bytes=sample_pdf_bytes,
            document_id="test-uuid-0002",
            s3_key="contracts/test-uuid-0002.pdf",
            s3_bucket="test-bucket",
        )
        assert len(result.raw_text.strip()) > 0

    def test_page_count_is_positive(self, sample_pdf_bytes):
        """Verifica que page_count sea mayor a 0."""
        result = extract_text(
            pdf_bytes=sample_pdf_bytes,
            document_id="test-uuid-0003",
            s3_key="contracts/test-uuid-0003.pdf",
            s3_bucket="test-bucket",
        )
        assert result.page_count > 0


class TestExtractTextTextractFallback:
    """Fallback a Textract cuando pdfplumber no produce texto."""

    MOCK_LINE_BLOCKS = [
        {"BlockType": "LINE", "Text": "Términos del contrato", "Page": 1},
        {"BlockType": "LINE", "Text": "Cláusula de confidencialidad", "Page": 1},
        {"BlockType": "LINE", "Text": "Firma del usuario", "Page": 2},
        {"BlockType": "TABLE", "Text": "ignored", "Page": 1},
    ]

    def _mock_textract_response(self, *args, **kwargs):
        return {"Blocks": self.MOCK_LINE_BLOCKS}

    def test_extract_text_textract_fallback(self, scanned_pdf_bytes):
        """pdfplumber sin texto → Textract retorna texto → extraction_method='ocr'."""
        with patch("ingestion.extractor._textract_client") as mock_textract:
            mock_textract.detect_document_text.side_effect = self._mock_textract_response

            result = extract_text(
                pdf_bytes=scanned_pdf_bytes,
                document_id="test-uuid-textract-1",
                s3_key="contracts/test-uuid-textract-1.pdf",
                s3_bucket="test-bucket",
            )

        assert result.extraction_method == "ocr"
        assert len(result.raw_text.strip()) > 0
        assert "confidencialidad" in result.raw_text
        assert result.page_count > 0

    def test_extract_text_pdfplumber_empty_triggers_fallback(self, scanned_pdf_bytes):
        """pdfplumber produce texto vacío → Textract es invocado exactamente una vez."""
        with patch("ingestion.extractor._textract_client") as mock_textract:
            mock_textract.detect_document_text.side_effect = self._mock_textract_response

            extract_text(
                pdf_bytes=scanned_pdf_bytes,
                document_id="test-uuid-textract-2",
                s3_key="contracts/test-uuid-textract-2.pdf",
                s3_bucket="test-bucket",
            )

        assert mock_textract.detect_document_text.call_count == 1

    def test_extract_text_pdfplumber_exception_triggers_fallback(self, scanned_pdf_bytes):
        """pdfplumber lanza excepción → Textract es invocado y la excepción no se re-lanza."""
        with patch("ingestion.extractor._textract_client") as mock_textract:
            mock_textract.detect_document_text.side_effect = self._mock_textract_response

            # Forzar que pdfplumber falle — bytes inválidos para pdfplumber
            result = extract_text(
                pdf_bytes=b"",
                document_id="test-uuid-textract-3",
                s3_key="contracts/test-uuid-textract-3.pdf",
                s3_bucket="test-bucket",
            )

        # Textract fue invocado (pdfplumber falló pero no re-lanzó)
        assert mock_textract.detect_document_text.call_count == 1
        assert result.extraction_method == "ocr"


class TestExtractTextEmptyExtraction:
    """Ambos métodos fallan → EMPTY_EXTRACTION."""

    def test_extract_text_empty_extraction(self, empty_pdf_bytes):
        """pdfplumber sin texto + Textract sin LINE Blocks → ExtractionError(EMPTY_EXTRACTION)."""
        with patch("ingestion.extractor._textract_client") as mock_textract:
            mock_textract.detect_document_text.return_value = {"Blocks": []}

            with pytest.raises(ExtractionError) as exc_info:
                extract_text(
                    pdf_bytes=empty_pdf_bytes,
                    document_id="test-uuid-empty",
                    s3_key="contracts/test-uuid-empty.pdf",
                    s3_bucket="test-bucket",
                )

        assert exc_info.value.error_code == ExtractionErrorCode.EMPTY_EXTRACTION


class TestExtractTextTextractErrors:
    """Errores del servicio Textract."""

    def _setup_textract_mock(self, mock_textract):
        """Configura InvalidS3ObjectException como excepción real para que el
        bloque except en _extract_with_textract no falle al evaluar la clase."""
        mock_textract.exceptions.InvalidS3ObjectException = type(
            "InvalidS3ObjectException", (ClientError,), {}
        )

    def test_extract_text_textract_failure(self, scanned_pdf_bytes):
        """Textract lanza Exception genérica → ExtractionError(TEXTRACT_FAILURE)."""
        with patch("ingestion.extractor._textract_client") as mock_textract:
            self._setup_textract_mock(mock_textract)
            mock_textract.detect_document_text.side_effect = Exception("Textract service error")

            with pytest.raises(ExtractionError) as exc_info:
                extract_text(
                    pdf_bytes=scanned_pdf_bytes,
                    document_id="test-uuid-tf",
                    s3_key="contracts/test-uuid-tf.pdf",
                    s3_bucket="test-bucket",
                )

        assert exc_info.value.error_code == ExtractionErrorCode.TEXTRACT_FAILURE

    def test_extract_text_s3_object_not_found(self, scanned_pdf_bytes):
        """Textract lanza InvalidS3ObjectException → ExtractionError(S3_OBJECT_NOT_FOUND)."""
        with patch("ingestion.extractor._textract_client") as mock_textract:
            self._setup_textract_mock(mock_textract)
            mock_textract.detect_document_text.side_effect = (
                mock_textract.exceptions.InvalidS3ObjectException(
                    {"Error": {"Code": "InvalidS3ObjectException", "Message": "not found"}},
                    "DetectDocumentText",
                )
            )

            with pytest.raises(ExtractionError) as exc_info:
                extract_text(
                    pdf_bytes=scanned_pdf_bytes,
                    document_id="test-uuid-s3nf",
                    s3_key="contracts/test-uuid-s3nf.pdf",
                    s3_bucket="test-bucket",
                )

        assert exc_info.value.error_code == ExtractionErrorCode.S3_OBJECT_NOT_FOUND

    def test_extract_text_corrupted_pdf(self, corrupted_pdf_bytes):
        """PDF corrupto → pdfplumber falla → Textract es invocado."""
        with patch("ingestion.extractor._textract_client") as mock_textract:
            mock_textract.detect_document_text.return_value = {
                "Blocks": [
                    {"BlockType": "LINE", "Text": "text from Textract", "Page": 1},
                ]
            }

            result = extract_text(
                pdf_bytes=corrupted_pdf_bytes,
                document_id="test-uuid-corr",
                s3_key="contracts/test-uuid-corr.pdf",
                s3_bucket="test-bucket",
            )

        assert mock_textract.detect_document_text.call_count == 1
        assert result.extraction_method == "ocr"


class TestExtractionResultProperties:
    """Property-based testing con Hypothesis (Task 21)."""

    @given(
        raw_text=st.text(min_size=1).filter(lambda t: t.strip()),
        page_count=st.integers(min_value=1, max_value=500),
        extraction_method=st.sampled_from(["text", "ocr"]),
    )
    def test_property_extraction_result_roundtrip(
        self, raw_text: str, page_count: int, extraction_method: str,
    ):
        """Construir ExtractionResult → build_dynamodb_item → deserialize → campos preservados."""
        now = datetime.now(timezone.utc)
        result = ExtractionResult(
            document_id=str(uuid.uuid4()),
            raw_text=raw_text,
            extraction_method=extraction_method,
            page_count=page_count,
            metadata=ExtractionMetadata(
                filename="property_test.pdf",
                uploaded_at=now,
            ),
            ttl=int(now.timestamp()) + 86400,
        )

        item = build_dynamodb_item(result)
        deserialized = deserialize_dynamodb_item(item)

        assert deserialized["document_id"] == result.document_id
        assert deserialized["raw_text"] == result.raw_text
        assert deserialized["extraction_method"] == result.extraction_method
        assert deserialized["page_count"] == result.page_count
        assert deserialized["metadata"]["filename"] == result.metadata.filename
        assert deserialized["metadata"]["uploaded_at"].endswith("Z")
        assert deserialized["ttl"] == result.ttl

    @given(raw_text=st.just("") | st.just("   ") | st.just("\n") | st.just("\t"))
    def test_property_empty_raw_text_rejected(self, raw_text: str):
        """Strings vacíos o solo whitespace → PydanticValidationError."""
        with pytest.raises(PydanticValidationError):
            ExtractionResult(
                document_id=str(uuid.uuid4()),
                raw_text=raw_text,
                extraction_method="text",
                page_count=1,
                metadata=ExtractionMetadata(
                    filename="empty.pdf",
                    uploaded_at=datetime.now(timezone.utc),
                ),
                ttl=9999999999,
            )
