from __future__ import annotations

import time
from enum import Enum
from typing import Literal, Optional

from pydantic import BaseModel, Field


# ============================================================================
# Modelos del Contrato 2 — Resultado de Análisis
# ============================================================================

ClauseCategory = Literal[
    "renovacion_automatica",
    "multa",
    "jurisdiccion",
    "cesion_datos",
    "otro",
]

RiskLevel = Literal["bajo", "medio", "alto"]


class Clause(BaseModel):
    """Una cláusula riesgosa identificada en el contrato."""
    clause_text: str = Field(min_length=1)
    category: ClauseCategory
    risk_level: RiskLevel
    explanation: str
    suggested_question: str


class AnalysisResult(BaseModel):
    """
    Resultado completo del análisis. Implementa el Contrato 2.
    Persistido en DynamoDB tabla ContractAnalyses.
    """
    document_id: str
    summary_plain: str
    risk_score: int = Field(ge=0, le=100)
    clauses: list[Clause] = Field(default_factory=list)
    overall_recommendation: str


# ============================================================================
# Modelo parcial — Respuesta cruda del modelo de IA (sin risk_score)
# ============================================================================


class ModelClause(BaseModel):
    """Cláusula tal como la retorna el modelo (misma estructura que Clause)."""
    clause_text: str = Field(min_length=1)
    category: ClauseCategory
    risk_level: RiskLevel
    explanation: str
    suggested_question: str


class ModelResponse(BaseModel):
    """
    Schema esperado de la respuesta del modelo de IA.
    NO incluye risk_score — ese campo se calcula por Risk_Calculator.
    """
    summary_plain: str
    clauses: list[ModelClause] = Field(default_factory=list)
    overall_recommendation: str


# ============================================================================
# Modelos del Contrato 4 — Respuesta HTTP de POST /analyze
# ============================================================================


class AnalyzeErrorCode(str, Enum):
    """Códigos de error para las respuestas HTTP del endpoint POST /analyze."""
    MISSING_DOCUMENT_ID = "MISSING_DOCUMENT_ID"
    INVALID_DOCUMENT_ID = "INVALID_DOCUMENT_ID"
    DOCUMENT_NOT_FOUND = "DOCUMENT_NOT_FOUND"
    CONTEXT_TOO_LONG = "CONTEXT_TOO_LONG"
    MODEL_RESPONSE_INVALID = "MODEL_RESPONSE_INVALID"
    BEDROCK_TIMEOUT = "BEDROCK_TIMEOUT"
    BEDROCK_THROTTLED = "BEDROCK_THROTTLED"
    BEDROCK_SERVICE_ERROR = "BEDROCK_SERVICE_ERROR"
    PERSISTENCE_FAILURE = "PERSISTENCE_FAILURE"
    INTERNAL_ERROR = "INTERNAL_ERROR"


class AnalyzeSuccessResponse(BaseModel):
    """Respuesta exitosa de POST /analyze (HTTP 200). Contrato 2 + campo cached."""
    document_id: str
    summary_plain: str
    risk_score: int = Field(ge=0, le=100)
    clauses: list[Clause] = Field(default_factory=list)
    overall_recommendation: str
    cached: bool = False


class AnalyzeErrorResponse(BaseModel):
    """Respuesta de error de POST /analyze."""
    error_code: AnalyzeErrorCode
    message: str
    document_id: Optional[str] = None


# ============================================================================
# Helpers de serialización DynamoDB
# ============================================================================


def build_analysis_dynamodb_item(result: AnalysisResult) -> dict:
    """
    Serializa un AnalysisResult a formato DynamoDB AttributeValue.
    Incluye atributo TTL (7 días desde ahora).
    """
    ttl_value = int(time.time()) + 604800  # 7 días

    clauses_list = []
    for clause in result.clauses:
        clauses_list.append({
            "M": {
                "clause_text": {"S": clause.clause_text},
                "category": {"S": clause.category},
                "risk_level": {"S": clause.risk_level},
                "explanation": {"S": clause.explanation},
                "suggested_question": {"S": clause.suggested_question},
            }
        })

    return {
        "document_id": {"S": result.document_id},
        "summary_plain": {"S": result.summary_plain},
        "risk_score": {"N": str(result.risk_score)},
        "clauses": {"L": clauses_list},
        "overall_recommendation": {"S": result.overall_recommendation},
        "ttl": {"N": str(ttl_value)},
    }


def deserialize_analysis_item(item: dict) -> dict:
    """
    Convierte un ítem DynamoDB (formato AttributeValue) a un dict plano
    compatible con AnalysisResult.
    """
    clauses = []
    for clause_attr in item.get("clauses", {}).get("L", []):
        m = clause_attr.get("M", {})
        clauses.append({
            "clause_text": m["clause_text"]["S"],
            "category": m["category"]["S"],
            "risk_level": m["risk_level"]["S"],
            "explanation": m["explanation"]["S"],
            "suggested_question": m["suggested_question"]["S"],
        })

    return {
        "document_id": item["document_id"]["S"],
        "summary_plain": item["summary_plain"]["S"],
        "risk_score": int(item["risk_score"]["N"]),
        "clauses": clauses,
        "overall_recommendation": item["overall_recommendation"]["S"],
    }
