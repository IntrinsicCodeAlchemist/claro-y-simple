# Requirements Document

## Introduction

El Módulo de Ingesta y Extracción es el punto de entrada del sistema Claro y Simple. Recibe un archivo PDF subido por el usuario, lo almacena en S3, extrae su texto completo usando `pdfplumber` como método principal y Amazon Textract como fallback, genera un identificador único de documento (`document_id` UUID v4), y persiste el resultado en la tabla DynamoDB `ContractExtractions` siguiendo exactamente el Contrato 1.

El módulo termina su responsabilidad cuando el documento queda persistido y disponible por `document_id`. El análisis de riesgo con IA y la interfaz de usuario son responsabilidad de otros módulos.

---

## Glossary

- **Ingestion_Handler**: Lambda handler expuesto via API Gateway (`POST /ingest`). Punto de entrada del módulo.
- **Extractor**: Componente de extracción de texto implementado en `backend/ingestion/extractor.py`. Orquesta pdfplumber y Textract.
- **PDF_Validator**: Lógica de validación del archivo recibido antes de iniciar la extracción.
- **S3_Storage**: Servicio AWS S3 usado para almacenar los PDFs originales subidos por los usuarios.
- **Textract_Client**: Cliente de Amazon Textract utilizado exclusivamente como fallback cuando pdfplumber no produce texto extraíble.
- **ContractExtractions**: Tabla DynamoDB donde se persisten los resultados de extracción. Clave de partición: `document_id`.
- **ExtractionResult**: Modelo Pydantic v2 definido en `backend/ingestion/models.py` que representa el Contrato 1.
- **document_id**: Identificador único UUID v4 generado por el Módulo 1 para cada documento procesado exitosamente.
- **raw_text**: Texto completo extraído del PDF. Nunca puede ser un string vacío ni contener únicamente espacios en blanco.
- **extraction_method**: Enum con dos valores posibles: `"text"` (extracción con pdfplumber) o `"ocr"` (extracción con Textract).
- **uploaded_at**: Timestamp ISO 8601 en UTC con sufijo `Z` que registra el momento de recepción del PDF.
- **PDF_embebido**: PDF cuyo texto está codificado directamente en el archivo (caso nominal — la mayoría de contratos digitales).
- **PDF_escaneado**: PDF cuyo contenido es una imagen del documento físico; requiere OCR para extraer texto.
- **TTL**: Time-To-Live de DynamoDB. Campo entero (Unix timestamp) que controla la expiración automática del registro a las 24 horas.

---

## Requirements

### Requisito 1: Recepción y Validación del Archivo

**User Story:** Como usuario de Claro y Simple, quiero subir un archivo PDF y recibir confirmación de que fue aceptado, para saber que el proceso de análisis puede continuar.

#### Criterios de Aceptación

1. WHEN el usuario envía una solicitud `POST /ingest` con un archivo adjunto, THE Ingestion_Handler SHALL validar que el archivo recibido sea un PDF válido antes de iniciar cualquier procesamiento.
2. IF la solicitud `POST /ingest` llega sin ningún archivo adjunto, THEN THE PDF_Validator SHALL rechazar la solicitud con HTTP 400 y un cuerpo JSON que contenga `error_code: "MISSING_FILE"` y un campo `message` descriptivo.
3. WHEN el archivo recibido no cumple el Content-Type `application/pdf` O no comienza con la firma de bytes PDF (`%PDF`), THE PDF_Validator SHALL rechazar el archivo con HTTP 400 y un cuerpo JSON que contenga `error_code: "INVALID_FILE_TYPE"` y un campo `message` descriptivo.
4. WHEN el archivo recibido es un PDF válido, THE Ingestion_Handler SHALL generar un `document_id` UUID v4 único para el documento antes de continuar con el almacenamiento.
5. WHEN el Ingestion_Handler recibe una solicitud que incluye un campo `document_id` en el cuerpo o parámetros, THE Ingestion_Handler SHALL ignorar silenciosamente ese valor y SHALL usar el `document_id` generado internamente.
6. WHEN el archivo recibido supera los 10 MB de tamaño, THE PDF_Validator SHALL rechazar el archivo con HTTP 413 y un cuerpo JSON que contenga `error_code: "FILE_TOO_LARGE"` y un campo `message` descriptivo.

---

### Requisito 2: Almacenamiento del PDF en S3

**User Story:** Como operador del sistema, quiero que los PDFs originales se almacenen en S3 antes de la extracción, para garantizar trazabilidad y permitir reprocesamiento si fuera necesario.

#### Criterios de Aceptación

1. WHEN el PDF supera la validación inicial, THE Ingestion_Handler SHALL subir el archivo a S3 bajo la clave `contracts/{document_id}.pdf` usando el `document_id` generado, antes de iniciar la extracción de texto.
2. IF la operación de subida a S3 falla, THEN THE Ingestion_Handler SHALL retornar HTTP 502 con un cuerpo JSON que contenga `error_code: "STORAGE_FAILURE"` y un campo `message` descriptivo, sin iniciar la extracción ni escribir ningún registro en DynamoDB.
3. WHEN la subida a S3 retorna confirmación exitosa, THE Ingestion_Handler SHALL verificar que el objeto existe en S3 con la clave `contracts/{document_id}.pdf` antes de continuar con la extracción de texto.
4. THE S3_Storage SHALL tener habilitada una lifecycle policy que elimine automáticamente los objetos bajo el prefijo `contracts/` exactamente 24 horas después de su creación, para minimizar costos y evitar retención innecesaria de datos personales.

---

### Requisito 3: Extracción de Texto con pdfplumber (Caso Principal)

**User Story:** Como sistema, quiero extraer el texto de PDFs con contenido embebido usando pdfplumber, para procesar la mayoría de contratos digitales sin incurrir en el costo de Textract.

#### Criterios de Aceptación

1. WHEN el PDF fue almacenado exitosamente en S3, THE Extractor SHALL intentar la extracción de texto usando `pdfplumber` como método principal.
2. WHEN `pdfplumber` extrae texto de al menos una página del PDF, THE Extractor SHALL concatenar el texto de todas las páginas en un único string, separando el contenido de cada página con un carácter de nueva línea (`\n`), y establecer `extraction_method` como `"text"`.
3. WHEN `pdfplumber` completa la extracción exitosamente, THE Extractor SHALL registrar en el resultado el `page_count` igual al número total de páginas del PDF procesado, siendo este valor un entero positivo mayor a 0.
4. WHEN `pdfplumber` produce un resultado cuyo texto concatenado, tras eliminar espacios en blanco extremos, tiene longitud igual a 0, THE Extractor SHALL clasificar este caso como falla de extracción y SHALL proceder al fallback con Textract.
5. IF `pdfplumber` lanza una excepción al intentar abrir o procesar el PDF, THEN THE Extractor SHALL registrar la excepción en el log estructurado con nivel `ERROR`, incluyendo `document_id` y el mensaje de la excepción original.
6. IF `pdfplumber` lanza una excepción al intentar abrir o procesar el PDF, THEN THE Extractor SHALL proceder al fallback con Textract sin re-lanzar la excepción de `pdfplumber`.

---

### Requisito 4: Extracción de Texto con Textract (Fallback)

**User Story:** Como sistema, quiero usar Amazon Textract como fallback para PDFs escaneados o con texto como imagen, para garantizar que el flujo completo funciona también con contratos físicos digitalizados.

#### Criterios de Aceptación

1. WHEN la extracción con `pdfplumber` falla (excepción) o produce texto con cero caracteres no-whitespace, THE Extractor SHALL invocar Amazon Textract usando el objeto S3 del PDF almacenado como entrada.
2. WHEN Textract completa el análisis y retorna un string con al menos 1 carácter no-whitespace, THE Extractor SHALL usar ese texto como `raw_text` y establecer `extraction_method` como `"ocr"`.
3. WHEN Textract completa el análisis y retorna texto válido, THE Extractor SHALL establecer `page_count` igual al número de páginas reportado por Textract, siendo este valor un entero positivo mayor a 0.
4. IF Textract retorna un resultado con cero caracteres no-whitespace o valor nulo, THEN THE Extractor SHALL lanzar una excepción `ExtractionError` con código `EMPTY_EXTRACTION` y mensaje indicando que el documento no produjo texto extraíble por ningún método.
5. IF Textract lanza una excepción de servicio, THEN THE Extractor SHALL capturar la excepción, registrarla en el log estructurado con nivel `ERROR` incluyendo `document_id` y el mensaje de la excepción original, y SHALL lanzar una excepción `ExtractionError` con código `TEXTRACT_FAILURE`.
6. THE Textract_Client SHALL ser invocado únicamente como fallback; THE Extractor SHALL intentar `pdfplumber` primero en todos los casos.
7. IF el objeto S3 referenciado por el Textract_Client no existe o no es accesible, THEN THE Extractor SHALL lanzar una excepción `ExtractionError` con código `S3_OBJECT_NOT_FOUND`.

---

### Requisito 5: Manejo de PDFs Corruptos

**User Story:** Como sistema, quiero detectar y reportar explícitamente los PDFs que no pueden procesarse, para evitar persistir resultados inválidos y dar feedback claro al usuario.

#### Criterios de Aceptación

1. IF el PDF falla la extracción tanto con `pdfplumber` como con Textract (incluyendo el caso de PDF corrupto donde ambos métodos no producen texto), THEN THE Ingestion_Handler SHALL retornar HTTP 422 con un cuerpo JSON que contenga `error_code: "EMPTY_EXTRACTION"`, un campo `message` con descripción del fallo de no más de 200 caracteres, y el campo `document_id`. Este es el mismo `error_code` que el Requisito 6 — ambos requisitos describen facetas del mismo escenario de fallo: ningún método produjo texto extraíble.
2. IF `pdfplumber` no puede abrir el archivo (archivo corrupto o truncado), THEN THE Extractor SHALL registrar el error con nivel `ERROR` en el log estructurado incluyendo `document_id` y el mensaje de la excepción original, antes de intentar el fallback con Textract.
3. WHEN cualquier excepción `ExtractionError` es capturada por THE Ingestion_Handler, THE Ingestion_Handler SHALL incluir el `document_id` en la respuesta de error únicamente cuando `error_code` es `"EMPTY_EXTRACTION"` (el único caso donde el documento ya fue parcialmente procesado y tiene un `document_id` asignado relevante para el usuario); para los demás `error_code` de `ExtractionError` (`TEXTRACT_FAILURE`, `S3_OBJECT_NOT_FOUND`), THE Ingestion_Handler SHALL omitir el campo `document_id` del cuerpo de la respuesta. IF el `document_id` aún no fue generado al momento del fallo, THEN THE Ingestion_Handler SHALL omitir el campo `document_id` independientemente del `error_code`.
4. THE Ingestion_Handler SHALL garantizar que un `ExtractionResult` con `raw_text` vacío nunca sea persistido en `ContractExtractions`.

---

### Requisito 6: Manejo de PDFs Sin Texto Extraíble

**User Story:** Como sistema, quiero fallar explícitamente cuando un PDF no produce ningún texto extraíble por ningún método, para garantizar que el Módulo 2 nunca reciba un `raw_text` vacío.

#### Criterios de Aceptación

1. IF ambos métodos de extracción (`pdfplumber` y Textract) producen un resultado con cero caracteres no-whitespace, THEN THE Extractor SHALL lanzar una excepción `ExtractionError` con código `EMPTY_EXTRACTION`.
2. WHEN THE Ingestion_Handler captura una excepción `ExtractionError` con código `EMPTY_EXTRACTION`, THE Ingestion_Handler SHALL retornar HTTP 422 con un cuerpo JSON que contenga `error_code: "EMPTY_EXTRACTION"` y un campo `message` en español indicando que el documento no contiene texto extraíble.
3. WHEN THE Ingestion_Handler captura una excepción `ExtractionError` con código `EMPTY_EXTRACTION`, THE Ingestion_Handler SHALL registrar el evento en el log estructurado con nivel `WARNING`, incluyendo `document_id`, `filename`, `page_count`, y `extraction_methods` (lista de los métodos intentados).
4. IF THE Extractor lanza una excepción `ExtractionError` con código `EMPTY_EXTRACTION`, THEN THE Ingestion_Handler SHALL omitir la escritura del documento en DynamoDB `ContractExtractions`, garantizando que ningún registro con `raw_text` vacío o ausente sea persistido.

---

### Requisito 7: Persistencia en DynamoDB según el Contrato 1

**User Story:** Como sistema, quiero persistir el resultado de la extracción en DynamoDB siguiendo exactamente el Contrato 1, para que el Módulo 2 pueda leer el `raw_text` usando el `document_id`.

#### Criterios de Aceptación

1. WHEN la extracción de texto es exitosa, THE Ingestion_Handler SHALL persistir un ítem en la tabla `ContractExtractions` de DynamoDB que contenga exactamente los campos definidos en el Contrato 1: `document_id`, `raw_text`, `extraction_method`, `page_count`, y `metadata`.
2. WHEN el Ingestion_Handler está por persistir el `ExtractionResult`, THE Ingestion_Handler SHALL validar el objeto contra el modelo `ExtractionResult` de Pydantic v2; IF la validación falla, THEN THE Ingestion_Handler SHALL retornar HTTP 500 con `error_code: "VALIDATION_FAILURE"` sin escribir en DynamoDB.
3. THE Ingestion_Handler SHALL incluir en `metadata.filename` el nombre original del archivo subido por el usuario, truncado a 255 caracteres si excede ese límite.
4. THE Ingestion_Handler SHALL incluir en `metadata.uploaded_at` un timestamp en formato `YYYY-MM-DDTHH:MM:SSZ` en UTC, generado en el momento de recepción de la solicitud.
5. THE Ingestion_Handler SHALL incluir un campo `ttl` entero en el ítem de DynamoDB con valor igual al timestamp Unix del momento de escritura más 86400 segundos (24 horas).
6. IF la operación de escritura en DynamoDB falla, THEN THE Ingestion_Handler SHALL retornar HTTP 502 con un cuerpo JSON que contenga `error_code: "PERSISTENCE_FAILURE"` y SHALL registrar el error con nivel `ERROR` incluyendo `document_id` y el mensaje de error original.
7. WHEN la persistencia es exitosa, THE Ingestion_Handler SHALL retornar HTTP 200 con un cuerpo JSON que contenga únicamente `{ "document_id": "<uuid_v4>" }`.

---

### Requisito 8: Conformidad del Contrato 1 (Invariantes de Datos)

**User Story:** Como integrante del equipo responsable del Módulo 2, quiero que el Contrato 1 sea respetado sin excepciones, para poder consumir los datos de `ContractExtractions` con confianza.

#### Criterios de Aceptación

1. THE Ingestion_Handler SHALL garantizar que todo ítem persistido en `ContractExtractions` tenga un `document_id` que cumpla el patrón UUID v4 (`^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$`); IF el `document_id` generado no cumple el patrón, la construcción del `ExtractionResult` fallará la validación de Pydantic y THE Ingestion_Handler SHALL retornar HTTP 500 con `error_code: "VALIDATION_FAILURE"` sin escribir en DynamoDB.
2. THE Ingestion_Handler SHALL garantizar que todo ítem persistido en `ContractExtractions` tenga un `raw_text` que, tras eliminar los espacios en blanco de los extremos, tenga longitud mínima de 1 carácter.
3. THE Ingestion_Handler SHALL garantizar que el campo `extraction_method` de todo ítem persistido en `ContractExtractions` sea exactamente `"text"` o exactamente `"ocr"`; IF `extraction_method` tiene cualquier otro valor, la construcción del `ExtractionResult` fallará la validación de Pydantic y THE Ingestion_Handler SHALL retornar HTTP 500 con `error_code: "VALIDATION_FAILURE"` sin escribir en DynamoDB.
4. THE Ingestion_Handler SHALL garantizar que el campo `page_count` de todo ítem persistido en `ContractExtractions` sea un entero mayor o igual a 1; los valores 0, negativos, o no enteros son inválidos y deben rechazar la escritura.
5. THE Ingestion_Handler SHALL garantizar que `metadata.uploaded_at` de todo ítem persistido en `ContractExtractions` sea un string con formato `YYYY-MM-DDTHH:MM:SSZ` (ej: `2024-01-15T10:30:00Z`); IF el valor no es un datetime válido en UTC, la construcción del `ExtractionResult` fallará la validación de Pydantic y THE Ingestion_Handler SHALL retornar HTTP 500 con `error_code: "VALIDATION_FAILURE"` sin escribir en DynamoDB.
6. WHEN un `ExtractionResult` es serializado a DynamoDB y luego deserializado de vuelta, THE resultado SHALL tener los campos `document_id`, `raw_text`, `extraction_method`, `page_count`, `metadata.filename`, y `metadata.uploaded_at` con valores idénticos a los del objeto original.

---

### Requisito 9: Logging Estructurado

**User Story:** Como operador del sistema, quiero que el módulo emita logs estructurados en JSON con `request_id` en cada entrada, para facilitar el diagnóstico de errores en producción.

#### Criterios de Aceptación

1. THE Ingestion_Handler SHALL emitir logs en formato JSON estructurado usando `aws-lambda-powertools` Logger en todas las operaciones.
2. WHEN el Lambda es invocado con un context que contiene `aws_request_id`, THE Ingestion_Handler SHALL incluir el valor de `context.aws_request_id` como campo `request_id` en cada entrada de log.
3. IF el Lambda es invocado sin un context válido (ej: ejecución local o tests), THEN THE Ingestion_Handler SHALL usar el string `"local"` como valor del campo `request_id`.
4. WHEN una extracción es exitosa, THE Ingestion_Handler SHALL emitir un log con nivel `INFO` que incluya `document_id`, `extraction_method`, `page_count`, y `filename`.
5. WHEN una excepción con severidad de error ocurre (ExtractionError, StorageError, ValidationError), THE Ingestion_Handler SHALL emitir un log con nivel `ERROR` que incluya `document_id`, el tipo de excepción, y el mensaje de la excepción original.
6. WHEN una condición degradada ocurre (ej: fallback a Textract por texto vacío de pdfplumber), THE Ingestion_Handler SHALL emitir un log con nivel `WARNING` que incluya `document_id` y la razón del fallback.
7. IF la variable de entorno `LOG_LEVEL` está configurada como `DEBUG`, THEN THE Ingestion_Handler SHALL activar el nivel `DEBUG` para trazas de operaciones internas; en cualquier otro caso (incluyendo ausencia de la variable), SHALL usar `INFO` como nivel por defecto.

---

### Requisito 10: Configuración via Variables de Entorno

**User Story:** Como operador del sistema, quiero que el módulo lea su configuración desde variables de entorno, LocalStack o SSM Parameter Store según el entorno activo, para que no existan valores hardcodeados en el código y la transición entre entornos sea solo de configuración, sin cambios de código.

#### Criterios de Aceptación

1. THE Ingestion_Handler SHALL leer en tiempo de inicialización las variables requeridas `DYNAMODB_TABLE_NAME`, `S3_BUCKET_NAME`, y `AWS_REGION` desde variables de entorno, nunca desde valores hardcodeados en el código fuente.
2. IF alguna de las variables requeridas (`DYNAMODB_TABLE_NAME`, `S3_BUCKET_NAME`, `AWS_REGION`) no está presente al iniciar el handler, THEN THE Ingestion_Handler SHALL lanzar una excepción `ConfigurationError` identificando la variable faltante en el mensaje, y SHALL abortar sin operar sobre ningún servicio AWS.
3. THE Ingestion_Handler SHALL ejecutar la validación de todas las variables requeridas en la fase de inicialización del módulo Lambda (fuera del event handler), garantizando que el fallo ocurre en cold start y no en tiempo de request.
4. WHERE la variable de entorno `ENVIRONMENT` tiene valor `localstack`, THE Ingestion_Handler SHALL inicializar todos los clientes boto3 (S3, DynamoDB, Textract) usando el valor de `AWS_ENDPOINT_URL` como `endpoint_url`; IF `AWS_ENDPOINT_URL` no está definida en este modo, THEN THE Ingestion_Handler SHALL lanzar una excepción `ConfigurationError` con mensaje que indique la variable faltante.
5. WHERE la variable de entorno `ENVIRONMENT` tiene valor `production`, WHEN el Lambda es inicializado, THE Ingestion_Handler SHALL obtener valores sensibles desde AWS SSM Parameter Store, y SHALL inicializar los clientes boto3 sin `endpoint_url` (usando los endpoints reales de AWS).
6. WHERE la variable de entorno `ENVIRONMENT` tiene cualquier valor distinto de `localstack` y `production` (incluyendo ausencia de la variable), THE Ingestion_Handler SHALL inicializar los clientes boto3 sin `endpoint_url`, apuntando a AWS real, y SHALL leer la configuración desde el archivo `.env` ubicado en `backend/ingestion/.env`; IF el archivo no existe, THE Ingestion_Handler SHALL lanzar una excepción `ConfigurationError`.
7. WHEN la variable de entorno `AWS_ENDPOINT_URL` está definida, THE Ingestion_Handler SHALL pasar su valor como `endpoint_url` al inicializar cada cliente boto3 (S3, DynamoDB, Textract); WHEN `AWS_ENDPOINT_URL` está ausente, THE Ingestion_Handler SHALL omitir el parámetro `endpoint_url` en la inicialización de clientes boto3, usando el comportamiento por defecto del SDK.
8. THE Ingestion_Handler SHALL garantizar que la lógica de negocio (extracción, validación, persistencia) sea idéntica independientemente del entorno activo; el entorno solo afecta la inicialización de clientes boto3 y la fuente de configuración, no el flujo de procesamiento.

---

### Requisito 11: Manejo de Excepciones con Tipos Personalizados

**User Story:** Como desarrollador del módulo, quiero que todos los errores del dominio usen excepciones personalizadas definidas en `backend/shared/exceptions.py`, para mantener consistencia y facilitar el manejo de errores entre módulos.

#### Criterios de Aceptación

1. WHEN el Extractor detecta un error de extracción de texto, THE Extractor SHALL lanzar únicamente excepciones del tipo `ExtractionError` con un campo `error_code` que use valores del enum `ExtractionErrorCode`; ninguna otra excepción del Extractor SHALL propagarse al Ingestion_Handler.
2. WHEN el Ingestion_Handler detecta un error de almacenamiento en S3, THE Ingestion_Handler SHALL lanzar una excepción `StorageError` con `error_code: "STORAGE_FAILURE"`; WHEN detecta un error de escritura en DynamoDB, SHALL lanzar una excepción `StorageError` con `error_code: "PERSISTENCE_FAILURE"`; ninguna excepción AWS SDK sin wrappear SHALL propagarse fuera del handler de almacenamiento.
3. WHEN el PDF_Validator detecta un archivo inválido, THE PDF_Validator SHALL lanzar únicamente excepciones del tipo `ValidationError` con un campo `error_code` que use uno de los valores: `MISSING_FILE`, `INVALID_FILE_TYPE`, `FILE_TOO_LARGE`.
4. WHEN una excepción de dominio (`ExtractionError`, `StorageError`, `ValidationError`) alcanza el punto de entrada del Lambda, THE Ingestion_Handler SHALL convertirla en una respuesta HTTP con el código de estado correspondiente: `ValidationError` → 400, `StorageError` → 502, `ExtractionError` → 422; el cuerpo SHALL contener `error_code` y `message`.
5. WHEN una excepción no esperada (no de dominio) alcanza el punto de entrada del Lambda, THE Ingestion_Handler SHALL capturarla, registrarla con nivel `ERROR` incluyendo el traceback completo, y SHALL retornar HTTP 500 con `error_code: "INTERNAL_ERROR"` sin exponer detalles internos en la respuesta.
6. THE Ingestion_Handler SHALL usar únicamente constantes o enums para valores de `extraction_method`, `error_code`, y cualquier otro campo con valores restringidos; strings literales con esos valores no SHALL aparecer en lógica de aplicación fuera de las definiciones de constantes y enums.
