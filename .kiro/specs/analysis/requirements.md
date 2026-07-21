# Requirements Document

## Introduction

Motor de Análisis de Contratos (Módulo 2) para la plataforma "Claro y Simple". Este módulo recibe un `document_id` vía endpoint HTTP `POST /analyze`, recupera el texto extraído del contrato desde DynamoDB (`ContractExtractions`), invoca Amazon Bedrock para analizar cláusulas riesgosas, calcula un score de riesgo de forma determinística, y persiste el resultado en DynamoDB (`ContractAnalyses`). El objetivo es transformar texto legal denso en información accionable para personas sin formación jurídica.

El orden de operaciones del flujo principal es: (1) validar el request, (2) buscar resultado cacheado en ContractAnalyses, (3) si no hay cache, buscar el texto en ContractExtractions, (4) validar contexto, (5) construir prompt e invocar Bedrock, (6) parsear y validar respuesta, (7) calcular risk_score, (8) persistir resultado, (9) retornar respuesta.

## Glossary

- **Analysis_Engine**: Módulo de software (Lambda function) que orquesta el flujo completo de análisis de contratos — desde la recepción del `document_id` hasta la persistencia del resultado.
- **Bedrock_Client**: Componente que gestiona la comunicación con Amazon Bedrock para invocar el modelo de IA.
- **Prompt_Builder**: Componente que construye el prompt estructurado enviado al modelo de IA a partir del texto del contrato.
- **Response_Parser**: Componente que valida y transforma la respuesta JSON del modelo de IA en un resultado parcial (sin `risk_score`) conforme al schema esperado.
- **Risk_Calculator**: Componente que calcula el `risk_score` (0-100) de forma determinística basándose en las cláusulas y sus `risk_level` — es la única fuente de este valor.
- **ContractExtractions**: Tabla DynamoDB que almacena el texto extraído de los contratos (Contrato 1, escrita por el Módulo 1). TTL: 24 horas.
- **ContractAnalyses**: Tabla DynamoDB que almacena los resultados de análisis (Contrato 2, escrita por este módulo). TTL: 7 días.
- **AnalysisResult**: Estructura de datos definida en el Contrato 2 que contiene `document_id`, `summary_plain`, `risk_score`, `clauses`, y `overall_recommendation`.
- **Clause**: Objeto que representa una cláusula riesgosa detectada, con campos `clause_text`, `category`, `risk_level`, `explanation`, y `suggested_question`.
- **ClauseCategory**: Enum con valores exactos: `renovacion_automatica`, `multa`, `jurisdiccion`, `cesion_datos`, `otro`.
- **RiskLevel**: Enum con valores exactos: `bajo`, `medio`, `alto`.
- **AnalyzeErrorCode**: Enum con los 10 códigos de error definidos en el Contrato 4.
- **UUID_v4**: Identificador universalmente único versión 4, formato `xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx`.
- **Context_Limit**: Límite máximo de tokens de entrada aceptados por el modelo de Bedrock seleccionado.

## Requirements

### Requisito 1: Validación del Request

**User Story:** Como cliente frontend, quiero que el endpoint de análisis valide mi request antes de procesarlo, para recibir feedback inmediato ante requests malformados.

#### Criterios de Aceptación

1. WHEN el cuerpo del request no incluye un campo `document_id` o el campo es un string vacío, THE Analysis_Engine SHALL retornar HTTP 400 con error_code `MISSING_DOCUMENT_ID`.
2. WHEN el campo `document_id` está presente pero no cumple el formato UUID v4, THE Analysis_Engine SHALL retornar HTTP 400 con error_code `INVALID_DOCUMENT_ID`.
3. WHEN el `document_id` es un UUID v4 válido, THE Analysis_Engine SHALL incluir el `document_id` en todas las respuestas de error subsiguientes.
4. THE Analysis_Engine SHALL retornar todas las respuestas de error con Content-Type `application/json` y un campo `message` no vacío.

---

### Requisito 2: Recuperación de Resultado Cacheado

**User Story:** Como operador del sistema, quiero que los documentos previamente analizados retornen el resultado cacheado, para que Bedrock no se invoque innecesariamente y se controlen los costos.

#### Criterios de Aceptación

1. WHEN se recibe un `document_id` válido, THE Analysis_Engine SHALL verificar en ContractAnalyses si ya existe un resultado para ese `document_id` ANTES de consultar ContractExtractions o invocar Bedrock.
2. WHEN se encuentra un AnalysisResult existente en ContractAnalyses para el `document_id` dado, THE Analysis_Engine SHALL retornar HTTP 200 con el AnalysisResult almacenado y `cached` establecido en `true`.
3. WHEN se retorna un resultado cacheado, THE Analysis_Engine SHALL NO consultar ContractExtractions ni invocar Amazon Bedrock.
4. IF ContractExtractions ya expiró el registro (TTL de 24h) pero ContractAnalyses aún conserva el resultado (TTL de 7 días), THEN THE Analysis_Engine SHALL retornar el resultado cacheado exitosamente sin fallar con DOCUMENT_NOT_FOUND.

---

### Requisito 3: Recuperación del Documento desde ContractExtractions

**User Story:** Como motor de análisis, quiero recuperar el texto extraído para un documento dado, para poder analizar su contenido.

#### Criterios de Aceptación

1. WHEN no existe un resultado cacheado en ContractAnalyses para el `document_id`, THE Analysis_Engine SHALL consultar la tabla ContractExtractions usando `document_id` como clave de partición.
2. WHEN el `document_id` no existe en ContractExtractions, THE Analysis_Engine SHALL retornar HTTP 404 con error_code `DOCUMENT_NOT_FOUND`.
3. WHEN el `document_id` existe en ContractExtractions, THE Analysis_Engine SHALL leer el campo `raw_text` para usarlo en los pasos de análisis subsiguientes.

---

### Requisito 4: Validación de Longitud de Contexto

**User Story:** Como motor de análisis, quiero validar que el texto del contrato cabe dentro de la ventana de contexto del modelo, para que las invocaciones a Bedrock no fallen por tamaño de input.

#### Criterios de Aceptación

1. WHEN el `raw_text` excede el Context_Limit configurado para el modelo de Bedrock seleccionado, THE Analysis_Engine SHALL retornar HTTP 422 con error_code `CONTEXT_TOO_LONG`.
2. THE Analysis_Engine SHALL evaluar la longitud del contexto antes de invocar Bedrock, usando un límite de caracteres configurable definido vía variable de entorno (`MAX_CONTEXT_CHARS`). Se usa un conteo de caracteres como aproximación razonable sin requerir un tokenizer específico del modelo.

---

### Requisito 5: Construcción del Prompt

**User Story:** Como responsable de producto, quiero que el prompt de análisis instruya al modelo a identificar cláusulas riesgosas con categorías y niveles de riesgo específicos, para que el análisis sea genuinamente útil y no un resumen genérico trivial.

#### Criterios de Aceptación

1. THE Prompt_Builder SHALL construir un prompt que instruya al modelo a retornar una respuesta JSON con los siguientes campos: `summary_plain`, `clauses` (array de objetos con `clause_text`, `category`, `risk_level`, `explanation`, `suggested_question`), y `overall_recommendation`. El prompt SHALL NO pedir al modelo que genere un campo `risk_score` — ese valor se calcula exclusivamente por el Risk_Calculator.
2. THE Prompt_Builder SHALL instruir al modelo a identificar cláusulas en exactamente las cinco categorías definidas en ClauseCategory: `renovacion_automatica`, `multa`, `jurisdiccion`, `cesion_datos`, `otro`.
3. THE Prompt_Builder SHALL instruir al modelo a clasificar cada cláusula con exactamente uno de los tres valores de RiskLevel: `bajo`, `medio`, `alto`.
4. THE Prompt_Builder SHALL instruir al modelo a generar explicaciones y preguntas sugeridas en lenguaje accesible y no legal (español).
5. THE Prompt_Builder SHALL instruir al modelo a producir un `summary_plain` del contrato en lenguaje simple con un máximo de 500 palabras.
6. THE Prompt_Builder SHALL cargar el template del prompt desde un archivo en `backend/analysis/prompts/` para permitir iteraciones sin cambios de código.

---

### Requisito 6: Invocación de Bedrock

**User Story:** Como motor de análisis, quiero invocar Amazon Bedrock con manejo de errores adecuado, para que las fallas transitorias se comuniquen claramente al caller.

#### Criterios de Aceptación

1. WHEN el Bedrock_Client invoca al modelo y recibe la respuesta dentro del timeout configurado, THE Analysis_Engine SHALL pasar la respuesta al Response_Parser.
2. WHEN el Bedrock_Client no recibe una respuesta dentro del timeout configurado, THE Analysis_Engine SHALL retornar HTTP 503 con error_code `BEDROCK_TIMEOUT`.
3. WHEN Amazon Bedrock rechaza la solicitud por throttling, THE Analysis_Engine SHALL retornar HTTP 503 con error_code `BEDROCK_THROTTLED`.
4. WHEN Amazon Bedrock retorna un error de servicio (5xx), THE Analysis_Engine SHALL retornar HTTP 502 con error_code `BEDROCK_SERVICE_ERROR`.
5. THE Bedrock_Client SHALL inicializar el cliente boto3 respetando la variable de entorno `AWS_ENDPOINT_URL` para compatibilidad con LocalStack.

---

### Requisito 7: Parseo y Validación de la Respuesta del Modelo

**User Story:** Como motor de análisis, quiero validar la respuesta del modelo contra el schema esperado, para que salidas malformadas de la IA no corrompan el almacén de datos.

#### Criterios de Aceptación

1. WHEN la respuesta del modelo no es JSON válido, THE Response_Parser SHALL lanzar un error que resulte en HTTP 422 con error_code `MODEL_RESPONSE_INVALID`.
2. WHEN la respuesta del modelo es JSON válido pero no contiene los campos requeridos (`summary_plain`, `clauses`, `overall_recommendation`) o los tipos son incorrectos, THE Response_Parser SHALL lanzar un error que resulte en HTTP 422 con error_code `MODEL_RESPONSE_INVALID`.
3. WHEN la respuesta del modelo contiene un valor de `category` que no está en ClauseCategory o un valor de `risk_level` que no está en RiskLevel, THE Response_Parser SHALL lanzar un error que resulte en HTTP 422 con error_code `MODEL_RESPONSE_INVALID`.
4. WHEN la respuesta del modelo es válida y conforma al schema esperado (sin `risk_score` — ese campo no se espera del modelo), THE Response_Parser SHALL retornar un resultado parcial validado listo para que el Risk_Calculator le agregue el `risk_score`.
5. THE Response_Parser SHALL NO esperar ni validar un campo `risk_score` en la respuesta cruda del modelo — ese campo es calculado exclusivamente por el Risk_Calculator.

---

### Requisito 8: Cálculo del Risk Score

**User Story:** Como usuario, quiero un número único que represente el riesgo general de mi contrato, para evaluar rápidamente qué tan preocupado debería estar.

#### Criterios de Aceptación

1. THE Risk_Calculator SHALL producir un `risk_score` entero en el rango 0 a 100 inclusive, de forma determinística a partir de las cláusulas identificadas por el modelo.
2. WHEN el modelo retorna cero cláusulas, THE Risk_Calculator SHALL asignar un `risk_score` de 0.
3. THE Risk_Calculator SHALL considerar la cantidad de cláusulas detectadas y sus valores individuales de `risk_level` para computar el score general.
4. THE Risk_Calculator SHALL asegurar que el score final quede limitado al rango 0-100 independientemente de la cantidad de cláusulas de entrada.
5. THE Risk_Calculator SHALL ser la única fuente del campo `risk_score` en el AnalysisResult — el modelo de IA nunca provee este valor directamente.

---

### Requisito 9: Persistencia del Resultado

**User Story:** Como sistema, quiero persistir los resultados de análisis en DynamoDB, para que puedan ser recuperados por el frontend y cacheados para requests futuros.

#### Criterios de Aceptación

1. WHEN se produce un AnalysisResult válido (con `risk_score` calculado por el Risk_Calculator), THE Analysis_Engine SHALL escribirlo en la tabla ContractAnalyses con `document_id` como clave de partición.
2. THE Analysis_Engine SHALL persistir todos los campos definidos en el Contrato 2: `document_id`, `summary_plain`, `risk_score`, `clauses`, `overall_recommendation`.
3. IF la operación `put_item` de DynamoDB falla, THEN THE Analysis_Engine SHALL retornar HTTP 502 con error_code `PERSISTENCE_FAILURE`.
4. THE Analysis_Engine SHALL establecer un atributo TTL en el ítem persistido con valor igual al timestamp Unix del momento de escritura más 604800 segundos (7 días).

---

### Requisito 10: Respuesta Exitosa

**User Story:** Como cliente frontend, quiero recibir el resultado completo del análisis después de un análisis exitoso, para poder renderizarlo al usuario.

#### Criterios de Aceptación

1. WHEN el análisis se completa exitosamente y el resultado queda persistido, THE Analysis_Engine SHALL retornar HTTP 200 con el AnalysisResult completo más `cached` establecido en `false`.
2. THE Analysis_Engine SHALL incluir todos los campos del Contrato 2 en la respuesta: `document_id`, `summary_plain`, `risk_score`, `clauses`, `overall_recommendation`.
3. THE Analysis_Engine SHALL incluir siempre el campo booleano `cached` en las respuestas HTTP 200.

---

### Requisito 11: Contrato Sin Cláusulas de Riesgo

**User Story:** Como usuario con un contrato seguro, quiero que el sistema confirme que no se encontraron cláusulas riesgosas, para tener tranquilidad.

#### Criterios de Aceptación

1. WHEN el modelo identifica cero cláusulas riesgosas, THE Analysis_Engine SHALL persistir y retornar un AnalysisResult con `clauses` como un array vacío.
2. WHEN `clauses` es un array vacío, THE Analysis_Engine SHALL igualmente incluir `summary_plain`, `risk_score` (valor 0, calculado por Risk_Calculator), y `overall_recommendation` en la respuesta.

---

### Requisito 12: Protección del Endpoint

**User Story:** Como operador del sistema, quiero que el endpoint /analyze esté protegido contra consumo no autorizado, para evitar que invocaciones accidentales o abusivas agoten el presupuesto de Bedrock antes de la demo.

#### Criterios de Aceptación

1. THE Analysis_Engine endpoint `POST /analyze` SHALL estar protegido con API Key + Usage Plan en API Gateway, conforme a lo definido en la sección "Protección de Endpoints y Control de Costos en API Gateway" de tech.md.
2. THE API Gateway SHALL rechazar con HTTP 403 cualquier request a `POST /analyze` que no incluya una API Key válida.
3. THE Usage Plan SHALL definir un límite diario de requests (configurable, ej: 500 requests/día durante el hackathon) para prevenir consumo accidental del presupuesto de Bedrock.
4. THE API Gateway SHALL aplicar throttling al endpoint `POST /analyze` con rate de 10 requests/segundo y burst de 20, conforme a lo definido en tech.md.

---

### Requisito 13: Logging Estructurado

**User Story:** Como desarrollador, quiero que todas las operaciones se logueen en formato JSON estructurado, para poder debuggear problemas en producción vía CloudWatch.

#### Criterios de Aceptación

1. THE Analysis_Engine SHALL loguear todos los requests y respuestas usando aws-lambda-powertools con logging JSON estructurado.
2. THE Analysis_Engine SHALL incluir `request_id` (del contexto Lambda) y `document_id` (cuando esté disponible) en cada entrada de log.
3. IF ocurre un error, THEN THE Analysis_Engine SHALL loguear los detalles del error con nivel ERROR incluyendo el error_code y un mensaje descriptivo.
4. THE Analysis_Engine SHALL NO loguear el contenido completo de `raw_text` para evitar almacenar datos personales sensibles en CloudWatch.

---

### Requisito 14: Manejo de Errores Inesperados

**User Story:** Como operador del sistema, quiero que las excepciones no esperadas sean capturadas y retornadas como un error genérico, para que los detalles internos nunca queden expuestos al cliente.

#### Criterios de Aceptación

1. IF una excepción no manejada ocurre en cualquier punto del flujo de análisis, THEN THE Analysis_Engine SHALL retornar HTTP 500 con error_code `INTERNAL_ERROR`.
2. IF una excepción no manejada ocurre, THEN THE Analysis_Engine SHALL loguear el traceback completo de la excepción con nivel ERROR para debugging.
3. THE Analysis_Engine SHALL NO incluir stack traces, nombres de variables internas, ni detalles de infraestructura en la respuesta HTTP de error.

---

### Requisito 15: Configuración vía Variables de Entorno

**User Story:** Como desarrollador, quiero que todos los valores configurables se lean desde variables de entorno, para que el mismo código funcione contra LocalStack y AWS sin modificación.

#### Criterios de Aceptación

1. THE Analysis_Engine SHALL leer los nombres de tablas DynamoDB (`EXTRACTIONS_TABLE_NAME`, `ANALYSES_TABLE_NAME`) desde variables de entorno.
2. THE Analysis_Engine SHALL leer el identificador del modelo de Bedrock desde una variable de entorno (`BEDROCK_MODEL_ID`).
3. THE Analysis_Engine SHALL leer el límite de caracteres de contexto desde una variable de entorno (`MAX_CONTEXT_CHARS`).
4. THE Analysis_Engine SHALL leer el timeout de invocación de Bedrock desde una variable de entorno (`BEDROCK_TIMEOUT_SECONDS`).
5. THE Analysis_Engine SHALL respetar `AWS_ENDPOINT_URL` para la inicialización de todos los clientes boto3 para soportar LocalStack en desarrollo.
6. THE Analysis_Engine SHALL NO definir `AWS_REGION` como variable de entorno en `infra/template.yaml` para el entorno production (Lambda la provee automáticamente del runtime); HOWEVER los archivos `.env` para los entornos `localstack` y `development` SHALL incluir `AWS_REGION` explícitamente — mismo patrón ya implementado en el Módulo 1.
