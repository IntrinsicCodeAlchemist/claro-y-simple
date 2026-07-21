---
inclusion: always
---

# Contratos de Interfaz entre Módulos — Fuente de Verdad

> ⚠️ **ADVERTENCIA: ESTOS CONTRATOS NO PUEDEN CAMBIAR SIN APROBACIÓN DE LOS 3 INTEGRANTES DEL EQUIPO.**
> Cualquier cambio debe ser commiteado en `main` y comunicado explícitamente a todos los integrantes antes de continuar el desarrollo. Si hay discrepancia entre el código y este documento, **este documento gana**.

---

## Contrato 1: Salida del Módulo 1 (Ingesta) → Entrada del Módulo 2 (Análisis)

**Almacén**: DynamoDB tabla `ContractExtractions`
**Clave de partición**: `document_id`

```json
{
  "document_id": "string (uuid v4)",
  "raw_text": "string (texto completo extraído del PDF)",
  "extraction_method": "text | ocr",
  "page_count": "number",
  "metadata": {
    "filename": "string",
    "uploaded_at": "string (ISO8601 timestamp, ej: 2024-01-15T10:30:00Z)"
  }
}
```

### Reglas de Validación — Contrato 1

- `document_id` es generado por el Módulo 1 (UUID v4); nunca es provisto por el cliente
- `raw_text` no puede ser string vacío (`""`); si la extracción no produce texto, el flujo debe fallar con error explícito
- `extraction_method` solo acepta exactamente los valores `"text"` (pdfplumber) o `"ocr"` (Textract)
- `uploaded_at` siempre en UTC, formato ISO 8601 con sufijo `Z`
- `page_count` es un entero positivo mayor a 0

### Modelo Pydantic de Referencia (Módulo 1)

Implementar en `backend/ingestion/models.py`:

```python
from pydantic import BaseModel, Field
from typing import Literal
from datetime import datetime

class ExtractionMetadata(BaseModel):
    filename: str
    uploaded_at: datetime  # siempre UTC

class ExtractionResult(BaseModel):
    document_id: str = Field(pattern=r'^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$')
    raw_text: str = Field(min_length=1)
    extraction_method: Literal["text", "ocr"]
    page_count: int = Field(gt=0)
    metadata: ExtractionMetadata
```

---

## Contrato 2: Salida del Módulo 2 (Análisis) → Entrada del Módulo 3 (Frontend/API)

**Almacén**: DynamoDB tabla `ContractAnalyses`
**Clave de partición**: `document_id`

```json
{
  "document_id": "string (uuid v4, mismo que en Contrato 1)",
  "summary_plain": "string (resumen en lenguaje simple, máx 500 palabras)",
  "risk_score": "number (entero de 0 a 100)",
  "clauses": [
    {
      "clause_text": "string (texto original de la cláusula)",
      "category": "renovacion_automatica | multa | jurisdiccion | cesion_datos | otro",
      "risk_level": "bajo | medio | alto",
      "explanation": "string (explicación en lenguaje simple de por qué es riesgosa)",
      "suggested_question": "string (pregunta que el usuario debería hacer antes de firmar)"
    }
  ],
  "overall_recommendation": "string (recomendación general en lenguaje simple)"
}
```

### Reglas de Validación — Contrato 2

- `document_id` debe existir en `ContractExtractions` antes de escribir en `ContractAnalyses`
- `risk_score` es un entero (`int`), nunca float; rango válido: 0 a 100 inclusive
- `clauses` puede ser un array vacío (`[]`) si no se detectan cláusulas riesgosas en el contrato
- `risk_level` solo acepta exactamente `"bajo"`, `"medio"`, o `"alto"` (minúsculas, sin tildes)
- `category` solo acepta exactamente los valores: `"renovacion_automatica"`, `"multa"`, `"jurisdiccion"`, `"cesion_datos"`, `"otro"`
- `summary_plain` tiene un máximo de 500 palabras
- `clause_text` no puede ser string vacío

### Modelo Pydantic de Referencia (Módulo 2)

Implementar en `backend/analysis/models.py`:

```python
from pydantic import BaseModel, Field
from typing import Literal

ClauseCategory = Literal[
    "renovacion_automatica",
    "multa",
    "jurisdiccion",
    "cesion_datos",
    "otro"
]

RiskLevel = Literal["bajo", "medio", "alto"]

class Clause(BaseModel):
    clause_text: str = Field(min_length=1)
    category: ClauseCategory
    risk_level: RiskLevel
    explanation: str
    suggested_question: str

class AnalysisResult(BaseModel):
    document_id: str
    summary_plain: str
    risk_score: int = Field(ge=0, le=100)
    clauses: list[Clause] = Field(default_factory=list)
    overall_recommendation: str
```

### Tipos TypeScript de Referencia (Módulo 3)

Implementar en `frontend/src/types/contract.ts`:

```typescript
export type ClauseCategory =
  | "renovacion_automatica"
  | "multa"
  | "jurisdiccion"
  | "cesion_datos"
  | "otro";

export type RiskLevel = "bajo" | "medio" | "alto";

export interface Clause {
  clause_text: string;
  category: ClauseCategory;
  risk_level: RiskLevel;
  explanation: string;
  suggested_question: string;
}

export interface AnalysisResult {
  document_id: string;
  summary_plain: string;
  risk_score: number; // entero 0-100
  clauses: Clause[];
  overall_recommendation: string;
}
```

---

## Contrato 3: Respuesta HTTP de POST /ingest (Módulo 1) → consumido por Módulo 3 (Frontend)

**Transporte**: HTTP response de API Gateway
**Endpoint**: `POST /ingest`

### Respuesta de éxito (HTTP 200)

```json
{
  "document_id": "string (uuid v4)"
}
```

### Respuesta de error (HTTP 400 / 413 / 422 / 500 / 502 según el caso)

```json
{
  "error_code": "string (uno de los valores del enum IngestErrorCode)",
  "message": "string",
  "document_id": "string (uuid v4, opcional)"
}
```

### Reglas de Validación — Contrato 3

- `error_code` es siempre uno de los 10 valores exactos listados en la tabla siguiente — nunca un string libre
- `document_id` solo aparece en la respuesta de error cuando `error_code` es `"EMPTY_EXTRACTION"` y el `document_id` ya había sido generado al momento del fallo; en todos los demás casos de error el campo está ausente
- Todas las respuestas (éxito y error) tienen `Content-Type: application/json`
- `message` es siempre un string no vacío; su contenido es informativo para el frontend pero no debe ser parseado como dato estructurado

### Tabla de error_codes

| `error_code` | HTTP Status | Significado |
|---|---|---|
| `MISSING_FILE` | 400 | No se recibió archivo en el campo `file` |
| `INVALID_FILE_TYPE` | 400 | El archivo no es un PDF válido |
| `FILE_TOO_LARGE` | 413 | El archivo supera el límite de 10 MB |
| `EMPTY_EXTRACTION` | 422 | Ningún método de extracción produjo texto (lleva `document_id` en la respuesta) |
| `TEXTRACT_FAILURE` | 422 | Textract lanzó una excepción de servicio |
| `S3_OBJECT_NOT_FOUND` | 422 | El objeto S3 no era accesible para Textract |
| `STORAGE_FAILURE` | 502 | Falla al subir el PDF a S3 |
| `PERSISTENCE_FAILURE` | 502 | Falla de infraestructura en `put_item` de DynamoDB (red, permisos, throttling) |
| `VALIDATION_FAILURE` | 500 | El `ExtractionResult` construido internamente falló la validación de Pydantic |
| `INTERNAL_ERROR` | 500 | Excepción no esperada — no expone detalles internos |

### Modelo Pydantic de Referencia (Módulo 1 — backend)

Implementar en `backend/ingestion/models.py`:

```python
from __future__ import annotations
from enum import Enum
from pydantic import BaseModel
from typing import Optional


class IngestErrorCode(str, Enum):
    MISSING_FILE = "MISSING_FILE"
    INVALID_FILE_TYPE = "INVALID_FILE_TYPE"
    FILE_TOO_LARGE = "FILE_TOO_LARGE"
    EMPTY_EXTRACTION = "EMPTY_EXTRACTION"
    TEXTRACT_FAILURE = "TEXTRACT_FAILURE"
    S3_OBJECT_NOT_FOUND = "S3_OBJECT_NOT_FOUND"
    STORAGE_FAILURE = "STORAGE_FAILURE"
    PERSISTENCE_FAILURE = "PERSISTENCE_FAILURE"
    VALIDATION_FAILURE = "VALIDATION_FAILURE"
    INTERNAL_ERROR = "INTERNAL_ERROR"


class IngestSuccessResponse(BaseModel):
    document_id: str


class IngestErrorResponse(BaseModel):
    error_code: IngestErrorCode
    message: str
    document_id: Optional[str] = None  # solo presente cuando error_code es EMPTY_EXTRACTION
```

### Tipos TypeScript de Referencia (Módulo 3 — frontend)

Implementar en `frontend/src/types/contract.ts`:

```typescript
export type IngestErrorCode =
  | "MISSING_FILE"
  | "INVALID_FILE_TYPE"
  | "FILE_TOO_LARGE"
  | "EMPTY_EXTRACTION"
  | "TEXTRACT_FAILURE"
  | "S3_OBJECT_NOT_FOUND"
  | "STORAGE_FAILURE"
  | "PERSISTENCE_FAILURE"
  | "VALIDATION_FAILURE"
  | "INTERNAL_ERROR";

export interface IngestSuccessResponse {
  document_id: string;
}

export interface IngestErrorResponse {
  error_code: IngestErrorCode;
  message: string;
  document_id?: string; // solo presente cuando error_code === "EMPTY_EXTRACTION"
}

/** Tipo unión para el resultado de POST /ingest — usar con discriminación por status HTTP */
export type IngestResponse = IngestSuccessResponse | IngestErrorResponse;
```

---

## Contrato 4: Respuesta HTTP del endpoint de análisis (Módulo 2) → consumido por Módulo 3 (Frontend)

**Transporte**: HTTP response de API Gateway
**Endpoint**: `POST /analyze`

### Request body

```json
{
  "document_id": "string (uuid v4, obligatorio)"
}
```

### Respuesta de éxito (HTTP 200)

```json
{
  "document_id": "string (uuid v4)",
  "summary_plain": "string (resumen en lenguaje simple, máx 500 palabras)",
  "risk_score": "number (entero de 0 a 100)",
  "clauses": [
    {
      "clause_text": "string (texto original de la cláusula)",
      "category": "renovacion_automatica | multa | jurisdiccion | cesion_datos | otro",
      "risk_level": "bajo | medio | alto",
      "explanation": "string (explicación en lenguaje simple)",
      "suggested_question": "string (pregunta que el usuario debería hacer antes de firmar)"
    }
  ],
  "overall_recommendation": "string (recomendación general en lenguaje simple)",
  "cached": "boolean (false = análisis fresco, true = resultado cacheado de análisis previo)"
}
```

La respuesta de éxito es el `AnalysisResult` del Contrato 2 más un campo `cached` que indica si el resultado es un análisis recién ejecutado (`false`) o un resultado previamente persistido que se retorna directamente (`true`). Cuando `cached` es `true`, el endpoint no invocó Bedrock — simplemente leyó el resultado existente de `ContractAnalyses`.

### Respuesta de error (HTTP 400 / 404 / 422 / 500 / 502 / 503 según el caso)

```json
{
  "error_code": "string (uno de los valores del enum AnalyzeErrorCode)",
  "message": "string",
  "document_id": "string (uuid v4, opcional — presente cuando el document_id fue recibido correctamente)"
}
```

### Reglas de Validación — Contrato 4

- `error_code` es siempre uno de los 10 valores exactos listados en la tabla siguiente — nunca un string libre
- `document_id` se incluye en la respuesta de error siempre que el request contenía un `document_id` válido (UUID v4 bien formado); se omite si el request no lo incluía o tenía formato inválido
- Todas las respuestas (éxito y error) tienen `Content-Type: application/json`
- `message` es siempre un string no vacío; su contenido es informativo para el frontend pero no debe ser parseado como dato estructurado
- `cached` es siempre `true` o `false` en la respuesta de éxito; nunca está ausente en un HTTP 200

### Tabla de error_codes

| `error_code` | HTTP Status | Significado |
|---|---|---|
| `MISSING_DOCUMENT_ID` | 400 | El request no incluye `document_id` o está vacío |
| `INVALID_DOCUMENT_ID` | 400 | El `document_id` no tiene formato UUID v4 válido |
| `DOCUMENT_NOT_FOUND` | 404 | El `document_id` no existe en `ContractExtractions` (nunca fue ingresado o es un typo) |
| `CONTEXT_TOO_LONG` | 422 | El `raw_text` excede el límite de contexto del modelo de Bedrock seleccionado |
| `MODEL_RESPONSE_INVALID` | 422 | Bedrock retornó una respuesta que no es JSON válido o no cumple la estructura esperada |
| `BEDROCK_TIMEOUT` | 503 | Bedrock no respondió dentro del timeout configurado |
| `BEDROCK_THROTTLED` | 503 | Bedrock rechazó la solicitud por throttling (demasiadas requests concurrentes) |
| `BEDROCK_SERVICE_ERROR` | 502 | Bedrock retornó un error de servicio no recuperable |
| `PERSISTENCE_FAILURE` | 502 | Falla de infraestructura al escribir en DynamoDB `ContractAnalyses` |
| `INTERNAL_ERROR` | 500 | Excepción no esperada — no expone detalles internos |

### Modelo Pydantic de Referencia (Módulo 2 — backend)

Implementar en `backend/analysis/models.py`:

```python
from __future__ import annotations
from enum import Enum
from typing import Optional
from pydantic import BaseModel, Field


class AnalyzeErrorCode(str, Enum):
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
    """
    Respuesta exitosa de POST /analyze (HTTP 200).
    Extiende AnalysisResult del Contrato 2 con el campo `cached`.
    """
    document_id: str
    summary_plain: str
    risk_score: int = Field(ge=0, le=100)
    clauses: list[Clause] = Field(default_factory=list)
    overall_recommendation: str
    cached: bool = False  # True si se retornó un resultado previamente persistido


class AnalyzeErrorResponse(BaseModel):
    """Respuesta de error de POST /analyze."""
    error_code: AnalyzeErrorCode
    message: str
    document_id: Optional[str] = None
```

### Tipos TypeScript de Referencia (Módulo 3 — frontend)

Implementar en `frontend/src/types/contract.ts`:

```typescript
export type AnalyzeErrorCode =
  | "MISSING_DOCUMENT_ID"
  | "INVALID_DOCUMENT_ID"
  | "DOCUMENT_NOT_FOUND"
  | "CONTEXT_TOO_LONG"
  | "MODEL_RESPONSE_INVALID"
  | "BEDROCK_TIMEOUT"
  | "BEDROCK_THROTTLED"
  | "BEDROCK_SERVICE_ERROR"
  | "PERSISTENCE_FAILURE"
  | "INTERNAL_ERROR";

export interface AnalyzeSuccessResponse {
  document_id: string;
  summary_plain: string;
  risk_score: number; // entero 0-100
  clauses: Clause[];
  overall_recommendation: string;
  cached: boolean; // false = análisis fresco, true = resultado cacheado
}

export interface AnalyzeErrorResponse {
  error_code: AnalyzeErrorCode;
  message: string;
  document_id?: string;
}

/** Tipo unión para el resultado de POST /analyze — usar con discriminación por status HTTP */
export type AnalyzeResponse = AnalyzeSuccessResponse | AnalyzeErrorResponse;
```

---

## Flujo de Datos End-to-End

```
1. Usuario sube PDF desde el frontend
         ↓
2. Frontend → API Gateway → Lambda Ingestion
         ↓
3. Lambda Ingestion extrae texto (pdfplumber o Textract)
   y genera document_id (UUID v4)
         ↓
4. Lambda Ingestion escribe en DynamoDB: ContractExtractions
   [Contrato 1]
         ↓
5. Lambda Ingestion retorna respuesta HTTP al frontend
   [Contrato 3 — éxito: { document_id } / error: { error_code, message, document_id? }]
         ↓
6. Frontend → API Gateway → Lambda Analysis (con document_id)
         ↓
7. Lambda Analysis lee raw_text desde ContractExtractions
   y llama a Amazon Bedrock para el análisis
         ↓
8. Lambda Analysis escribe en DynamoDB: ContractAnalyses
   [Contrato 2]
         ↓
9. Lambda Analysis retorna respuesta HTTP al frontend
   [Contrato 4 — éxito: AnalysisResult completo / error: { error_code, message, document_id? }]
         ↓
10. Frontend (Results page) renderiza score, cláusulas y preguntas
```

---

## Notas para Implementadores

- Los modelos Pydantic en `backend/ingestion/models.py` y `backend/analysis/models.py` deben reflejar **exactamente** los contratos definidos en este documento.
- Los tipos TypeScript en `frontend/src/types/contract.ts` deben reflejar **exactamente** el Contrato 2 (datos de análisis), el Contrato 3 (respuestas de ingesta) y el Contrato 4 (respuestas de análisis).
- Si necesitás agregar un campo nuevo a cualquier contrato: abrí una discusión con el equipo, actualizá este archivo, commitealo en `main`, y notificá a todos antes de cambiar el código.
- Los nombres de las tablas DynamoDB (`ContractExtractions`, `ContractAnalyses`) son los canónicos y deben usarse en `infra/template.yaml` y en el código.
