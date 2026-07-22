# Claro y Simple

> *"Entendé lo que firmás."*

Claro y Simple analiza contratos (alquiler, servicios, suscripciones) usando IA y devuelve un resumen en lenguaje simple, las cláusulas de riesgo identificadas, un score de riesgo general (0-100), y preguntas que el usuario debería hacer antes de firmar.

## Problema

En Argentina y LatAm, millones de personas firman contratos sin entender cláusulas abusivas (renovación automática, multas desproporcionadas, cesión de datos sin límites) porque el lenguaje legal es inaccesible y la asesoría legal es costosa.

## Cómo funciona

1. El usuario sube un PDF de un contrato
2. El sistema extrae el texto (pdfplumber para PDFs digitales, Amazon Textract para escaneados)
3. Amazon Bedrock analiza las cláusulas y genera el resumen
4. El usuario recibe un reporte claro con cláusulas de riesgo, score y preguntas sugeridas

## Stack tecnológico

| Capa | Tecnología |
|------|-----------|
| Backend | Python 3.12, FastAPI, Pydantic v2 |
| Frontend | React + TypeScript + Vite |
| IA | Amazon Bedrock |
| Extracción de texto | pdfplumber + Amazon Textract (fallback) |
| Infraestructura | AWS SAM, Lambda, API Gateway, S3, DynamoDB |
| Testing | pytest, moto, Hypothesis |
| Desarrollo local | LocalStack (S3, DynamoDB emulados) |

## Estructura del proyecto

```
claro-y-simple/
├── backend/
│   ├── ingestion/       # Módulo 1: ingesta y extracción de texto
│   ├── analysis/        # Módulo 2: motor de análisis con Bedrock
│   └── shared/          # Código compartido (aws_utils, exceptions)
├── frontend/            # Módulo 3: UI React + TypeScript
├── infra/
│   └── template.yaml    # AWS SAM — recursos Lambda, S3, DynamoDB, API Gateway
├── scripts/
│   └── setup-localstack.sh  # Bootstrap de LocalStack para desarrollo local
├── .kiro/
│   ├── steering/        # Documentos de producto, tech, estructura, contratos
│   └── specs/           # Specs de cada módulo (requirements, design, tasks)
└── docs/
```

## Desarrollo local

### Prerrequisitos

- Python 3.12+
- Docker (para LocalStack)
- AWS CLI
- AWS SAM CLI

### Setup

```bash
# 1. Levantar LocalStack (Docker o Podman — usá el que tengas instalado)
docker run --rm -d --name localstack-main -p 4566:4566 -p 4510-4559:4510-4559 -e SERVICES=s3,dynamodb -e LOCALSTACK_AUTH_TOKEN=<tu-token> localstack/localstack

# Si usás Podman en vez de Docker, el comando es idéntico, solo cambiá "docker" por "podman"
```

> **Nota**: `LOCALSTACK_AUTH_TOKEN` es obligatorio incluso para uso gratuito (Community). Se obtiene registrándose gratis en https://app.localstack.cloud.

```bash
# 2. Crear recursos (S3, DynamoDB)
./scripts/setup-localstack.sh

# 3. Instalar dependencias del módulo de ingesta
cd backend/ingestion
pip install -r requirements.txt

# 4. Copiar y configurar variables de entorno
cp .env.localstack.example .env

# 5. Correr tests
pytest tests/ -v
```

### Tests de integración (requieren LocalStack)

```bash
ENVIRONMENT=localstack pytest tests/test_integration.py -v -m integration
```

## Módulos

El proyecto se divide en 3 módulos independientes que se comunican vía contratos de datos definidos en `.kiro/steering/interface-contracts.md`:

1. **Ingestion** (`backend/ingestion/`): Recibe PDF → extrae texto → persiste en DynamoDB
2. **Analysis** (`backend/analysis/`): Lee texto → analiza con Bedrock → genera resumen y score. Cachea resultados para evitar re-invocaciones a Bedrock (campo `cached: true/false` en la respuesta)
3. **Frontend** (`frontend/`): UI para subir PDFs y visualizar resultados

## Contratos de interfaz

Los contratos entre módulos son fuente de verdad y no se modifican sin aprobación de los 3 integrantes:
- **Contrato 1**: Ingestion → Analysis (DynamoDB: `ContractExtractions`)
- **Contrato 2**: Analysis → Frontend (DynamoDB: `ContractAnalyses`)
- **Contrato 3**: Ingestion HTTP response → Frontend (POST /ingest)
- **Contrato 4**: Analysis HTTP response → Frontend (POST /analyze)

## Contexto

Proyecto desarrollado durante el **Hackathon Kiro AI — Powered by AWS**.

## Licencia

MIT
