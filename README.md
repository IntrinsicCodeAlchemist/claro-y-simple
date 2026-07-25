# Claro y Simple

> *"Entendé lo que firmás."*

Claro y Simple analiza contratos (alquiler, servicios, suscripciones) usando IA y devuelve un resumen en lenguaje simple, las cláusulas de riesgo identificadas, un score de riesgo general (0-100), y preguntas que el usuario debería hacer antes de firmar.

## Problema

En Argentina y LatAm, millones de personas firman contratos sin entender cláusulas abusivas (renovación automática, multas desproporcionadas, cesión de datos sin límites) porque el lenguaje legal es inaccesible y la asesoría legal es costosa.

## Cómo funciona

1. El usuario sube un PDF de un contrato desde la UI
2. El backend extrae el texto (pdfplumber para PDFs digitales, Amazon Textract para escaneados)
3. Amazon Bedrock (`us.anthropic.claude-haiku-4-5-20251001-v1:0`) analiza las cláusulas y genera el resumen
4. El usuario recibe un reporte con cláusulas de riesgo categorizadas, score 0-100, y preguntas sugeridas

## Stack tecnológico

| Capa | Tecnología |
|------|-----------|
| Backend | Python 3.12, Lambda handlers (API Gateway proxy integration), Pydantic v2 |
| Frontend | React 18 + TypeScript + Vite + Tailwind CSS |
| IA | Amazon Bedrock — `us.anthropic.claude-haiku-4-5-20251001-v1:0` (Claude Haiku 4.5 vía cross-region inference profile) |
| Extracción de texto | pdfplumber + Amazon Textract (fallback para PDFs escaneados) |
| Infraestructura | AWS SAM, Lambda, API Gateway (con API Key + Usage Plan), S3, DynamoDB |
| Testing | pytest + Hypothesis (backend), Vitest + fast-check (frontend) |
| Desarrollo local | LocalStack (S3, DynamoDB emulados vía Docker) |

## Estructura del proyecto

```
claro-y-simple/
├── backend/
│   ├── ingestion/       # Módulo 1: ingesta y extracción de texto
│   ├── analysis/        # Módulo 2: motor de análisis con Bedrock
│   └── shared/          # Código compartido (aws_utils, exceptions)
├── frontend/            # Módulo 3: UI React + TypeScript + Tailwind
├── infra/
│   └── template.yaml    # AWS SAM — Lambda, S3, DynamoDB, API Gateway, Bedrock
├── scripts/
│   ├── setup_localstack.py        # Bootstrap de recursos LocalStack (multiplataforma)
│   ├── setup-localstack.sh        # Equivalente bash (Linux/macOS)
│   ├── gen_sample_pdf.py           # Genera PDFs de prueba para fixtures
│   ├── invoke_deployed_ingestion.py # Prueba manual contra el Lambda de Ingestion ya deployado
│   ├── test_bedrock_real.py        # Prueba manual contra Bedrock real
│   └── test_textract_real.py       # Prueba manual contra Textract real
├── .kiro/
│   ├── steering/        # Documentos de producto, tech, estructura, contratos
│   └── specs/           # Specs de cada módulo (requirements, design, tasks)
└── .github/workflows/   # CI (tests en cada push)
```

## API desplegada

**URL base**: `https://sr07qh0zxl.execute-api.us-east-1.amazonaws.com/development`

Endpoints:
- `POST /ingest` — sube un PDF y extrae texto
- `POST /analyze` — analiza un documento previamente ingestado

Requiere API key (no incluida por seguridad — el repo es público). Para acceso de demo, contactar al equipo, o generar una propia siguiendo la sección de Deploy.

**CORS**: configurado con `AllowOrigin: '*'` para desarrollo. **Binary Media Types**: `multipart/form-data` habilitado para que API Gateway envíe el PDF como base64 al handler.

## Desarrollo local

### Prerrequisitos

- Python 3.12+
- Node.js 18+ y npm
- Docker Desktop (para LocalStack)
- AWS SAM CLI (opcional, para deploy)

### LocalStack — dos opciones

**Opción A** — Imagen actual con token (recomendada para tener la última versión):

```bash
# Crear cuenta gratis en https://app.localstack.cloud (plan Hobby)
# Obtener el auth token desde el dashboard

docker run --rm -d -p 4566:4566 --name localstack \
  -e LOCALSTACK_AUTH_TOKEN=<tu-token> \
  localstack/localstack
```

Desde marzo 2026, LocalStack unificó las imágenes community y pro. La imagen `latest` exige `LOCALSTACK_AUTH_TOKEN` incluso para uso gratuito.

**Opción B** — Tag fijo sin token (anterior al cambio, estable para S3 + DynamoDB):

```bash
docker run --rm -d -p 4566:4566 --name localstack \
  localstack/localstack:4.4.0
```

No requiere token. No recibe actualizaciones, pero es suficiente para lo que usa este proyecto (S3 y DynamoDB).

### Setup backend

```bash
# 1. Crear recursos en LocalStack (S3 bucket, tablas DynamoDB con TTL)
python scripts/setup_localstack.py

# 2. Instalar dependencias de cada módulo
cd backend/ingestion && pip install -r requirements.txt && cd ../..
cd backend/analysis && pip install -r requirements.txt && cd ../..

# 3. Configurar variables de entorno (copiar el ejemplo y ajustar si es necesario)
cp backend/ingestion/.env.localstack.example backend/ingestion/.env
cp backend/analysis/.env.example backend/analysis/.env
```

### Setup frontend

```bash
cd frontend
npm install
cp .env.example .env
# Editar .env con:
#   VITE_API_BASE_URL=https://sr07qh0zxl.execute-api.us-east-1.amazonaws.com/development
#   VITE_API_KEY=<tu-api-key>  (no incluida por seguridad)
npm run dev
# → http://localhost:5173
```

## Tests

### Backend — Ingestion (Módulo 1)

```bash
# Tests unitarios
pytest backend/ingestion/tests/ -v

# Tests de integración (requieren LocalStack activo + setup_localstack.py ejecutado)
$env:ENVIRONMENT="localstack"   # PowerShell
pytest backend/ingestion/tests/test_integration.py -v -m integration
```

### Backend — Analysis (Módulo 2)

```bash
# Tests unitarios + property-based (Hypothesis)
pytest backend/analysis/tests/test_analyzer.py -v

# Tests de integración contra LocalStack (Bedrock mockeado, DynamoDB real)
$env:ENVIRONMENT="localstack"   # PowerShell
pytest backend/analysis/tests/test_integration.py -v -m integration
```

### Frontend (Módulo 3)

```bash
cd frontend
npm run test -- --run
# 57 tests, 9 archivos, incluye property-based con fast-check
```

## Módulos

El proyecto se divide en 3 módulos independientes que se comunican vía contratos de datos definidos en `.kiro/steering/interface-contracts.md`:

1. **Ingestion** (`backend/ingestion/`): Recibe PDF → extrae texto → persiste en DynamoDB (`ContractExtractions`)
2. **Analysis** (`backend/analysis/`): Lee texto → analiza con Bedrock → calcula risk_score determinísticamente → persiste resultado en DynamoDB (`ContractAnalyses`). Cachea resultados (campo `cached: true/false` en la respuesta)
3. **Frontend** (`frontend/`): UI para subir PDFs y visualizar resultados — upload con drag & drop, estados de carga, manejo de errores con retry diferenciado, score visual con paleta rojo/amber/verde

## Contratos de interfaz

Los contratos entre módulos son fuente de verdad y no se modifican sin aprobación de los 3 integrantes:
- **Contrato 1**: Ingestion → Analysis (DynamoDB: `ContractExtractions`)
- **Contrato 2**: Analysis → Frontend (DynamoDB: `ContractAnalyses`)
- **Contrato 3**: Ingestion HTTP response → Frontend (`POST /ingest`)
- **Contrato 4**: Analysis HTTP response → Frontend (`POST /analyze`)

Ver detalle completo en `.kiro/steering/interface-contracts.md`.

## Convención de imports Lambda

Los módulos `ingestion`, `analysis` y `shared` se importan **sin prefijo `backend.`**:

```python
from analysis.analyzer import calculate_risk_score  # ✓ correcto
from shared.aws_utils import get_boto3_client       # ✓ correcto
from backend.analysis.analyzer import ...           # ✗ incorrecto en Lambda
```

Esto es consecuencia de que `CodeUri` en el SAM template apunta a `../backend/`, haciendo que ese directorio sea la raíz del paquete Lambda.

## Deploy

```bash
cd infra
sam build
sam deploy --guided
# Parámetros requeridos:
#   EnvironmentName: development | production
#   BedrockModelId: us.anthropic.claude-haiku-4-5-20251001-v1:0
```

La API Key y el Usage Plan se crean automáticamente como parte del stack (ver `ClaroYSimpleApiKey` en `infra/template.yaml`). Para obtener el valor real de la key después del deploy:

```bash
aws apigateway get-api-keys --include-values --region us-east-1
```

## Contexto

Proyecto desarrollado durante el **Hackathon Kiro AI — Powered by AWS** (20-27 de julio de 2026).

- **Equipo**: 3 integrantes con conocimiento básico de AWS
- **Presupuesto**: ~$100 USD en créditos AWS
- **Objetivo**: demostrar uso de IA generativa (Amazon Bedrock) para resolver un problema real con impacto social

## Licencia

MIT
