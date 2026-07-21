---
inclusion: always
---

# Claro y Simple — Estructura del Repositorio

## Layout del Monorepo

```
claro-y-simple/
├── .kiro/
│   ├── steering/
│   │   ├── product.md              # Visión del producto, usuarios objetivo, criterios del hackathon
│   │   ├── tech.md                 # Stack tecnológico, principios técnicos, convenciones
│   │   ├── structure.md            # Este archivo — estructura de carpetas y roles de módulos
│   │   └── interface-contracts.md  # CRÍTICO: contratos de datos entre módulos (fuente de verdad)
│   ├── specs/
│   │   ├── ingestion/              # Spec del Módulo 1: ingesta y extracción
│   │   ├── analysis/               # Spec del Módulo 2: motor de análisis
│   │   └── frontend/               # Spec del Módulo 3: UI
│   └── hooks/
├── backend/
│   ├── ingestion/                  # Módulo 1: Ingesta y extracción de texto
│   │   ├── handler.py              # Lambda handler — punto de entrada AWS Lambda
│   │   ├── extractor.py            # Lógica de extracción: pdfplumber + Textract fallback
│   │   ├── models.py               # Pydantic models — ExtractionResult (Contrato 1), IngestErrorResponse (Contrato 3), serialización DynamoDB
│   │   ├── tests/
│   │   │   ├── test_extractor.py
│   │   │   ├── test_handler.py
│   │   │   ├── test_integration.py
│   │   │   └── fixtures/           # PDFs de prueba (texto embebido, escaneados, edge cases)
│   │   └── requirements.txt
│   ├── analysis/                   # Módulo 2: Motor de análisis con IA
│   │   ├── handler.py              # Lambda handler — punto de entrada AWS Lambda
│   │   ├── analyzer.py             # Lógica de análisis: llama a Bedrock, procesa respuesta
│   │   ├── models.py               # Pydantic models — AnalysisResult, Clause (Contrato 2)
│   │   ├── prompts/
│   │   │   └── clause_analysis.txt # Prompt template para el análisis de cláusulas
│   │   ├── tests/
│   │   │   └── test_analyzer.py
│   │   └── requirements.txt
│   └── shared/                     # Código compartido entre módulos backend
│       ├── aws_utils.py            # Helper get_boto3_client (respeta AWS_ENDPOINT_URL)
│       └── exceptions.py           # Excepciones personalizadas del dominio
├── frontend/                       # Módulo 3: Interfaz de usuario
│   ├── src/
│   │   ├── components/
│   │   │   ├── UploadZone.tsx      # Zona de drag & drop para subir el PDF
│   │   │   ├── RiskScore.tsx       # Visualización del score 0-100
│   │   │   ├── ClauseCard.tsx      # Tarjeta individual de cláusula riesgosa
│   │   │   └── SuggestedQuestions.tsx  # Lista de preguntas sugeridas
│   │   ├── pages/
│   │   │   ├── Home.tsx            # Página principal con upload
│   │   │   └── Results.tsx         # Página de resultados del análisis
│   │   ├── api/
│   │   │   └── client.ts           # Cliente HTTP para API Gateway
│   │   └── types/
│   │       └── contract.ts         # Tipos TypeScript que reflejan el Contrato 2
│   ├── public/
│   ├── package.json
│   └── vite.config.ts
├── infra/
│   ├── template.yaml               # AWS SAM template — define todos los recursos AWS
│   ├── samconfig.toml              # Configuración de deployment (stack name, región, S3 bucket)
│   └── layers/
│       └── python-deps/            # Lambda layer con dependencias Python comunes
├── docs/
│   ├── architecture.md             # Diagrama y descripción de la arquitectura
│   └── demo-guide.md               # Guía para la demo del hackathon
├── .github/
│   └── workflows/
│       ├── ci.yml                  # Ejecuta tests en cada push a cualquier rama
│       └── deploy.yml              # Deploy a AWS en merge a main
├── README.md
├── .gitignore
└── Makefile                        # Comandos útiles del proyecto
```

---

## Rol de Cada Módulo

### Módulo 1: Ingestion (`backend/ingestion/`)

Responsabilidad: recibir el PDF del usuario y extraer su texto.

- Expuesto como Lambda triggered por S3 (cuando se sube un archivo) o directamente por API Gateway
- Intenta extracción con `pdfplumber`; si falla o el resultado está vacío, invoca Amazon Textract
- Genera un `document_id` único (UUID v4) para el documento
- Persiste el resultado en DynamoDB tabla `ContractExtractions` siguiendo el **Contrato 1**
- **No llama al Módulo 2 directamente** — el análisis se dispara por separado o en el mismo flujo vía API Gateway

### Módulo 2: Analysis (`backend/analysis/`)

Responsabilidad: analizar el texto extraído e identificar cláusulas riesgosas.

- Lee el texto desde DynamoDB usando el `document_id` recibido (Contrato 1)
- Construye el prompt y llama a Amazon Bedrock para el análisis
- Parsea la respuesta del modelo y calcula el `risk_score`
- Persiste el resultado en DynamoDB tabla `ContractAnalyses` siguiendo el **Contrato 2**
- Expone un endpoint via API Gateway para que el frontend consulte el estado/resultado

### Módulo 3: Frontend (`frontend/`)

Responsabilidad: interfaz de usuario para subir contratos y visualizar resultados.

- Permite al usuario subir un PDF (drag & drop o file picker)
- Llama a API Gateway para iniciar el análisis y obtener resultados
- Muestra el score de riesgo, las cláusulas detectadas con su categoría y nivel, y las preguntas sugeridas
- Usa los tipos definidos en `types/contract.ts` que reflejan exactamente el **Contrato 2**

---

## Flujo de Datos y Conexión entre Módulos

```
Usuario sube PDF
      ↓
API Gateway → Lambda Ingestion
      ↓
pdfplumber (o Textract fallback)
      ↓
DynamoDB: ContractExtractions  ← Contrato 1
      ↓
Lambda Analysis (lee document_id)
      ↓
Amazon Bedrock (análisis de cláusulas)
      ↓
DynamoDB: ContractAnalyses  ← Contrato 2
      ↓
API Gateway → Frontend (Results page)
```

El `document_id` es el identificador compartido que conecta todos los módulos. Es generado por el Módulo 1 y usado por los módulos 2 y 3 para leer y escribir datos.

---

## Comandos del Makefile

```makefile
make deploy     # Deploy completo a AWS con SAM
make test       # Ejecuta todos los tests (pytest + vitest)
make lint       # Lint de Python (ruff) y TypeScript (eslint)
make local      # Levanta el entorno local con SAM CLI y frontend dev server
```
