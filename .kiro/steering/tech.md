---
inclusion: always
---

# Claro y Simple — Tech Steering

## Stack Tecnológico

### Backend
- **Lenguaje**: Python 3.12
- **Framework**: FastAPI
- **Validación de modelos**: Pydantic v2

### Frontend
- **Framework**: React + TypeScript
- **Bundler**: Vite
- **Testing**: Vitest

### Inteligencia Artificial
- **Servicio**: Amazon Bedrock
- **Modelo**: A definir al momento de implementar. Revisar el catálogo actualizado de modelos disponibles en Amazon Bedrock para la región de deployment — los modelos disponibles y sus precios cambian con frecuencia. Evaluar modelos de la familia Claude y Amazon Nova según disponibilidad regional, soporte para español, y relación costo/tokens al momento de la implementación.

### Extracción de Texto desde PDFs
- **Principal**: `pdfplumber` — para PDFs con texto embebido (la mayoría de contratos digitales)
- **Fallback**: Amazon Textract — para PDFs escaneados o con texto como imagen

### Infraestructura como Código (IaC)
- **Herramienta**: AWS SAM (Serverless Application Model)
- **Archivo principal**: `infra/template.yaml`

### Servicios AWS Utilizados
- **S3**: almacenamiento de PDFs subidos por los usuarios
- **Lambda**: ejecución de los módulos de ingesta y análisis
- **API Gateway**: exposición de los endpoints REST al frontend
- **DynamoDB**: almacén compartido de resultados entre módulos (contratos de interfaz)
- **Bedrock**: motor de IA para análisis de cláusulas y generación de resúmenes

---

## Principios Técnicos

Estas convenciones aplican a toda la codebase y deben respetarse en cada PR.

### Python
- **Type hints obligatorios** en todas las funciones y métodos, incluyendo parámetros y valor de retorno
- **Docstrings en funciones públicas**: al menos una línea descriptiva; usar formato Google style para funciones complejas
- **Manejo explícito de errores**: no usar excepciones genéricas (`except Exception`) sin re-raise o logging; preferir excepciones personalizadas definidas en `backend/shared/exceptions.py`
- **Sin valores mágicos**: constantes nombradas o enums para categorías, niveles de riesgo, etc.

### TypeScript
- **Strict mode habilitado** en `tsconfig.json` (`"strict": true`)
- **Prohibido `any`** sin comentario explícito que justifique la excepción
- **Tipos explícitos** para props de componentes y respuestas de API; usar los tipos definidos en `frontend/src/types/contract.ts`

### Testing
- **Backend**: pytest con fixtures; cobertura mínima de módulos críticos (extractor, analyzer)
- **Frontend**: Vitest para lógica de componentes y transformaciones de datos

### Control de Versiones
- **Commits**: Conventional Commits — prefijos válidos: `feat`, `fix`, `chore`, `docs`, `test`
  - Ejemplos: `feat(analysis): add risk score calculation`, `fix(ingestion): handle empty PDF pages`
- **Branches**: una rama por módulo
  - `module/ingestion` — Módulo 1: ingesta y extracción de texto
  - `module/analysis` — Módulo 2: motor de análisis con Bedrock
  - `module/frontend` — Módulo 3: UI React + TypeScript
  - `infra/sam-setup` — infraestructura y configuración AWS SAM

### Logging en Lambda
- **Formato**: structured logging en JSON en todos los Lambda handlers
- **Campo obligatorio**: incluir `request_id` en cada log entry (obtener del `context.aws_request_id`)
- **Librería sugerida**: `aws-lambda-powertools` (Python) — incluye logger estructurado, tracer y métricas
- **Nivel de log**: `INFO` por defecto en producción; `DEBUG` habilitado via variable de entorno

### Variables de Entorno y Secretos
- **Producción**: AWS SSM Parameter Store para valores sensibles (ARNs, nombres de tablas, nombres de modelos)
- **Desarrollo local**: archivo `.env` en la raíz del módulo (nunca commiteado; incluido en `.gitignore`)
- **Prohibido**: hardcodear ARNs, nombres de recursos, claves de API, o region strings en el código

---

## Gestión de Costos

El equipo dispone de **$100 USD en créditos AWS**. Prioridades para mantener costos bajos:

- **Preferir serverless y pay-per-use**: Lambda, DynamoDB on-demand, API Gateway
- **Evitar servicios con costo fijo**: no usar RDS, ECS, ni EC2 para el MVP
- **Textract como fallback**: usarlo solo cuando pdfplumber falle; Textract tiene costo por página
- **Bedrock**: monitorear tokens consumidos; usar prompts eficientes y evitar llamadas redundantes
- **S3**: habilitar lifecycle policies para eliminar PDFs después de 24h (los datos del análisis se guardan en DynamoDB)
- **DynamoDB TTL**: habilitar TTL en la tabla `ContractExtractions` con expiración de 24h. El campo `raw_text` puede contener datos personales sensibles del contrato (nombres, DNI, domicilio, condiciones económicas) y no debe persistir indefinidamente. La tabla `ContractAnalyses` puede tener TTL más largo (ej: 7 días) ya que solo contiene el análisis procesado, sin texto original.
- **DynamoDB**: usar on-demand capacity mode (no provisioned) para el hackathon

---

## Protección de Endpoints y Control de Costos en API Gateway

El endpoint de análisis llama a Amazon Bedrock en cada request. Un consumo descontrolado puede agotar el presupuesto antes de la demo. Implementar como mínimo:

- **API Key + Usage Plan**: configurar un Usage Plan en API Gateway con límite diario de requests (ej: 500 requests/día durante el hackathon). Asociar una API Key requerida para todos los endpoints que disparen análisis. Esto evita consumo accidental desde el frontend en desarrollo o llamadas no autorizadas.
- **Throttling**: configurar rate limiting en API Gateway — rate: 10 requests/segundo, burst: 20 — para prevenir picos abusivos.
- **No exponer el endpoint de análisis sin protección**: el endpoint `POST /analyze` nunca debe estar públicamente accesible sin autenticación mínima durante el hackathon.

La API Key puede ser una constante en el frontend para el hackathon (no es seguridad production-grade, pero previene consumo accidental).

---

## Entorno de Desarrollo Local vs. AWS Real

El desarrollo backend se realiza contra LocalStack (S3, DynamoDB, y Lambda emulados vía Docker) hasta que el equipo tenga credenciales AWS reales disponibles. Esto permite desarrollar y correr tests de integración sin incurrir en costos ni depender de conectividad a AWS.

### Tres entornos del proyecto

| Variable `ENVIRONMENT` | Destino de los servicios AWS | Configuración |
|---|---|---|
| `localstack` | LocalStack en Docker (`http://localhost:4566`) | `.env` local con `AWS_ENDPOINT_URL` |
| `development` (o ausente) | AWS real con credenciales de desarrollo | `.env` local sin `AWS_ENDPOINT_URL` |
| `production` | AWS real | SSM Parameter Store |

### Regla de inicialización de boto3

Todos los clientes boto3 (S3, DynamoDB, Textract) deben inicializarse respetando la variable de entorno `AWS_ENDPOINT_URL`:

```python
import boto3
import os

def get_boto3_client(service_name: str):
    """Retorna un cliente boto3 apuntando a LocalStack si AWS_ENDPOINT_URL está definida."""
    kwargs = {}
    endpoint_url = os.getenv("AWS_ENDPOINT_URL")
    if endpoint_url:
        kwargs["endpoint_url"] = endpoint_url
    return boto3.client(service_name, **kwargs)
```

- Si `AWS_ENDPOINT_URL` está definida → boto3 apunta a ese endpoint (LocalStack en desarrollo local)
- Si `AWS_ENDPOINT_URL` está ausente → boto3 usa los endpoints reales de AWS (comportamiento por defecto)
- **La transición de LocalStack a AWS real requiere únicamente cambios de configuración (`.env`), no cambios de código**

### Configuración local para LocalStack

El archivo `backend/ingestion/.env` (y el equivalente de cada módulo) debe incluir en modo LocalStack:

```dotenv
ENVIRONMENT=localstack
AWS_ENDPOINT_URL=http://localhost:4566
AWS_DEFAULT_REGION=us-east-1
AWS_ACCESS_KEY_ID=test
AWS_SECRET_ACCESS_KEY=test
DYNAMODB_TABLE_NAME=ContractExtractions
S3_BUCKET_NAME=claro-y-simple-contracts
```

Las credenciales `test`/`test` son las que acepta LocalStack por defecto; no son credenciales reales.

### Script de bootstrap de LocalStack

Antes de correr tests de integración contra LocalStack, es necesario crear los recursos AWS emulados (bucket S3 con lifecycle policy, tablas DynamoDB con TTL). El container de LocalStack arranca vacío cada vez.

**Ejecutar una vez después de levantar el container:**

```bash
# Desde la raíz del repo
./scripts/setup-localstack.sh

# O especificando el .env explícitamente:
./scripts/setup-localstack.sh --env-file backend/ingestion/.env
```

El script `scripts/setup-localstack.sh`:
- Verifica que LocalStack esté corriendo antes de hacer nada
- Crea el bucket S3 `claro-y-simple-contracts` con lifecycle policy de 24h sobre el prefijo `contracts/`
- Crea la tabla `ContractExtractions` (on-demand, TTL de 24h sobre atributo `ttl`)
- Crea la tabla `ContractAnalyses` (on-demand, TTL de 7 días sobre atributo `ttl`)
- Es **idempotente**: correrlo dos veces no falla ni duplica recursos
- Imprime comandos de verificación al final

### Nota sobre Textract en LocalStack

LocalStack Community (gratuito) no incluye emulación de Amazon Textract. Durante el desarrollo local, el fallback a Textract debe ser mockeado en tests usando `moto` o `unittest.mock`. El flujo real con Textract se prueba únicamente contra AWS real.

---

## Repositorio

- **Tipo**: Monorepo público en GitHub
- **Estructura**: ver `.kiro/steering/structure.md` para el layout completo de carpetas
- **CI/CD**: GitHub Actions para tests en cada push y deploy a AWS en merge a `main`
