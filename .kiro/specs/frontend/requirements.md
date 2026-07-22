# Requirements Document

## Introduction

Interfaz de usuario del producto "Claro y Simple" que permite a personas sin formación legal subir un contrato en PDF y recibir un análisis comprensible de sus cláusulas de riesgo. El frontend consume exclusivamente los endpoints HTTP definidos en interface-contracts.md (Contrato 3: POST /ingest y Contrato 4: POST /analyze) y presenta los resultados de forma visual y accesible.

El módulo cubre el flujo completo del usuario: selección de archivo → subida → espera de ingesta → espera de análisis → visualización de resultados (score de riesgo, cláusulas detectadas, preguntas sugeridas, recomendación general).

## Glossary

- **Frontend**: Aplicación React + TypeScript servida por Vite que constituye la interfaz de usuario del producto Claro y Simple
- **Upload_Zone**: Componente de la interfaz que permite al usuario seleccionar un archivo PDF mediante drag & drop o file picker
- **Risk_Score_Display**: Componente visual que representa el score de riesgo (0-100) del contrato analizado
- **Clause_Card**: Componente que muestra una cláusula individual con su texto, categoría, nivel de riesgo, explicación y pregunta sugerida
- **Results_Page**: Página que muestra el resultado completo del análisis incluyendo resumen, score, cláusulas y recomendación
- **API_Client**: Módulo TypeScript responsable de realizar las llamadas HTTP a los endpoints POST /ingest y POST /analyze
- **Ingest_Endpoint**: Endpoint POST /ingest que recibe el archivo PDF y retorna un document_id (Contrato 3)
- **Analyze_Endpoint**: Endpoint POST /analyze que recibe un document_id y retorna el resultado del análisis (Contrato 4)
- **IngestErrorCode**: Enum de 10 códigos de error posibles en la respuesta del Ingest_Endpoint
- **AnalyzeErrorCode**: Enum de 10 códigos de error posibles en la respuesta del Analyze_Endpoint
- **Usuario**: Persona sin formación legal en Argentina/LatAm que necesita entender un contrato antes de firmarlo

## Requirements

### Requisito 1: Selección y validación de archivo PDF

**User Story:** Como Usuario, quiero subir un PDF de mi contrato mediante drag & drop o seleccionando el archivo, para que el sistema lo analice.

#### Acceptance Criteria

1. THE Upload_Zone SHALL permitir la selección de archivos mediante un componente de drag & drop y un botón de file picker
2. WHEN el Usuario arrastra un archivo sobre la Upload_Zone, THE Upload_Zone SHALL mostrar retroalimentación visual indicando que se puede soltar el archivo
3. WHEN el Usuario selecciona un archivo que no tiene extensión .pdf, THE Frontend SHALL mostrar el mensaje "Solo se aceptan archivos en formato PDF" sin enviar el archivo al servidor
4. WHEN el Usuario selecciona un archivo PDF que supera 10 MB, THE Frontend SHALL mostrar el mensaje "El archivo supera el tamaño máximo permitido (10 MB)" sin enviar el archivo al servidor
5. WHEN el Usuario selecciona un archivo PDF válido de 10 MB o menos, THE Frontend SHALL iniciar la llamada al Ingest_Endpoint

### Requisito 2: Estado de carga durante la ingesta

**User Story:** Como Usuario, quiero ver un indicador de progreso mientras se sube mi contrato, para saber que el sistema está procesando mi archivo.

#### Acceptance Criteria

1. WHILE la llamada al Ingest_Endpoint está en progreso, THE Frontend SHALL mostrar un indicador de carga con el texto "Subiendo tu contrato..."
2. WHILE la llamada al Ingest_Endpoint está en progreso, THE Upload_Zone SHALL deshabilitar la selección de un nuevo archivo
3. WHEN el Ingest_Endpoint retorna HTTP 200 con un document_id, THE Frontend SHALL iniciar automáticamente la llamada al Analyze_Endpoint con ese document_id

### Requisito 3: Estado de carga durante el análisis

**User Story:** Como Usuario, quiero ver un indicador de progreso mientras se analiza mi contrato, para entender que el análisis puede tomar unos segundos.

#### Acceptance Criteria

1. WHILE la llamada al Analyze_Endpoint está en progreso, THE Frontend SHALL mostrar un indicador de carga con el texto "Analizando tu contrato... Esto puede tomar unos segundos"
2. WHILE la llamada al Analyze_Endpoint está en progreso, THE Frontend SHALL deshabilitar la selección de un nuevo archivo
3. WHEN el Analyze_Endpoint retorna HTTP 200, THE Frontend SHALL navegar a la Results_Page y renderizar los datos del análisis

### Requisito 4: Manejo de errores del endpoint de ingesta

**User Story:** Como Usuario, quiero ver mensajes comprensibles cuando algo falla al subir mi contrato, para entender qué pasó y qué puedo hacer.

#### Acceptance Criteria

1. WHEN el Ingest_Endpoint retorna error_code MISSING_FILE, THE Frontend SHALL mostrar el mensaje "No se recibió el archivo. Intentá de nuevo."
2. WHEN el Ingest_Endpoint retorna error_code INVALID_FILE_TYPE, THE Frontend SHALL mostrar el mensaje "El archivo no es un PDF válido. Verificá que sea un documento PDF."
3. WHEN el Ingest_Endpoint retorna error_code FILE_TOO_LARGE, THE Frontend SHALL mostrar el mensaje "El archivo es demasiado grande. El máximo es 10 MB."
4. WHEN el Ingest_Endpoint retorna error_code EMPTY_EXTRACTION, THE Frontend SHALL mostrar el mensaje "No se pudo extraer texto del PDF. Es posible que sea una imagen escaneada sin texto reconocible."
5. WHEN el Ingest_Endpoint retorna error_code TEXTRACT_FAILURE, THE Frontend SHALL mostrar el mensaje "Hubo un problema al procesar el documento. Intentá de nuevo en unos minutos."
6. WHEN el Ingest_Endpoint retorna error_code S3_OBJECT_NOT_FOUND, THE Frontend SHALL mostrar el mensaje "Hubo un problema al procesar el documento. Intentá de nuevo en unos minutos."
7. WHEN el Ingest_Endpoint retorna error_code STORAGE_FAILURE, THE Frontend SHALL mostrar el mensaje "No pudimos guardar tu archivo. Intentá de nuevo en unos minutos."
8. WHEN el Ingest_Endpoint retorna error_code PERSISTENCE_FAILURE, THE Frontend SHALL mostrar el mensaje "Hubo un error interno. Intentá de nuevo en unos minutos."
9. WHEN el Ingest_Endpoint retorna error_code VALIDATION_FAILURE, THE Frontend SHALL mostrar el mensaje "Hubo un error interno. Intentá de nuevo en unos minutos."
10. WHEN el Ingest_Endpoint retorna error_code INTERNAL_ERROR, THE Frontend SHALL mostrar el mensaje "Ocurrió un error inesperado. Intentá de nuevo más tarde."
11. WHEN el Ingest_Endpoint retorna cualquier error, THE Frontend SHALL mostrar un botón "Intentar de nuevo" que permita al Usuario volver a subir un archivo

### Requisito 5: Manejo de errores del endpoint de análisis

**User Story:** Como Usuario, quiero ver mensajes comprensibles cuando algo falla durante el análisis, para entender qué pasó y qué puedo hacer.

#### Acceptance Criteria

1. WHEN el Analyze_Endpoint retorna error_code MISSING_DOCUMENT_ID, THE Frontend SHALL mostrar el mensaje "Hubo un error interno. Intentá subir el contrato de nuevo."
2. WHEN el Analyze_Endpoint retorna error_code INVALID_DOCUMENT_ID, THE Frontend SHALL mostrar el mensaje "Hubo un error interno. Intentá subir el contrato de nuevo."
3. WHEN el Analyze_Endpoint retorna error_code DOCUMENT_NOT_FOUND, THE Frontend SHALL mostrar el mensaje "No encontramos el documento. Es posible que haya expirado. Intentá subirlo de nuevo."
4. WHEN el Analyze_Endpoint retorna error_code CONTEXT_TOO_LONG, THE Frontend SHALL mostrar el mensaje "El contrato es demasiado extenso para analizar. Intentá con un documento más corto."
5. WHEN el Analyze_Endpoint retorna error_code MODEL_RESPONSE_INVALID, THE Frontend SHALL mostrar el mensaje "El análisis no se pudo completar correctamente. Intentá de nuevo."
6. WHEN el Analyze_Endpoint retorna error_code BEDROCK_TIMEOUT, THE Frontend SHALL mostrar el mensaje "El análisis está tardando demasiado. Intentá de nuevo en unos minutos."
7. WHEN el Analyze_Endpoint retorna error_code BEDROCK_THROTTLED, THE Frontend SHALL mostrar el mensaje "Hay muchas solicitudes en este momento. Intentá de nuevo en unos minutos."
8. WHEN el Analyze_Endpoint retorna error_code BEDROCK_SERVICE_ERROR, THE Frontend SHALL mostrar el mensaje "El servicio de análisis no está disponible. Intentá de nuevo más tarde."
9. WHEN el Analyze_Endpoint retorna error_code PERSISTENCE_FAILURE, THE Frontend SHALL mostrar el mensaje "Hubo un error al guardar el análisis. Intentá de nuevo en unos minutos."
10. WHEN el Analyze_Endpoint retorna error_code INTERNAL_ERROR, THE Frontend SHALL mostrar el mensaje "Ocurrió un error inesperado. Intentá de nuevo más tarde."
11. WHEN el Analyze_Endpoint retorna un error_code transitorio (MODEL_RESPONSE_INVALID, BEDROCK_TIMEOUT, BEDROCK_THROTTLED, BEDROCK_SERVICE_ERROR, PERSISTENCE_FAILURE, INTERNAL_ERROR), THE Frontend SHALL mostrar un botón "Intentar de nuevo" que dispare un nuevo POST /analyze usando el document_id ya obtenido del Ingest_Endpoint exitoso previo, sin pasar de nuevo por Upload_Zone ni por el Ingest_Endpoint — estos errores son transitorios y un reintento tiene probabilidad razonable de éxito
12. WHEN el Analyze_Endpoint retorna un error_code de documento (MISSING_DOCUMENT_ID, INVALID_DOCUMENT_ID, DOCUMENT_NOT_FOUND, CONTEXT_TOO_LONG), THE Frontend SHALL mostrar un botón "Intentar de nuevo" que vuelva al estado idle (Upload_Zone habilitado para seleccionar un nuevo archivo) — estos errores indican un problema con el documento en sí y reintentar con el mismo document_id fallaría de forma idéntica

### Requisito 6: Visualización del score de riesgo

**User Story:** Como Usuario, quiero ver el nivel de riesgo general de mi contrato de forma visual y clara, para entender rápidamente si debo preocuparme.

#### Acceptance Criteria

1. THE Risk_Score_Display SHALL mostrar el valor numérico del risk_score (0 a 100) de forma prominente
2. WHEN al menos una clause en el array de clauses tiene risk_level "alto", THE Risk_Score_Display SHALL usar color rojo y la etiqueta "Riesgo alto"
3. WHEN ninguna clause tiene risk_level "alto" pero al menos una tiene risk_level "medio", THE Risk_Score_Display SHALL usar color amarillo/naranja y la etiqueta "Riesgo medio"
4. WHEN todas las clauses tienen risk_level "bajo", o el array de clauses está vacío, THE Risk_Score_Display SHALL usar color verde y la etiqueta "Riesgo bajo"
5. THE Risk_Score_Display SHALL derivar el color y la etiqueta textual del risk_level más grave presente en las cláusulas, NO del valor numérico del risk_score — el valor numérico se muestra junto al color pero no lo determina

> **Nota de diseño**: el color se desacopla del valor numérico porque una sola cláusula de riesgo alto no debe quedar visualmente diluida por un score acumulado bajo. El color es el indicador que el usuario ve primero y con menos atención al detalle — debe reflejar la gravedad máxima detectada, no el promedio ponderado.

### Requisito 7: Visualización de cláusulas de riesgo

**User Story:** Como Usuario, quiero ver cada cláusula riesgosa identificada con su explicación y contexto, para entender qué partes del contrato requieren mi atención.

#### Acceptance Criteria

1. THE Results_Page SHALL mostrar cada cláusula en un Clause_Card individual
2. THE Clause_Card SHALL mostrar el campo clause_text como texto citado del contrato original
3. THE Clause_Card SHALL mostrar la category con una etiqueta legible en español: "Renovación automática", "Multa", "Jurisdicción", "Cesión de datos", u "Otro"
4. THE Clause_Card SHALL mostrar el risk_level con indicador visual de color: verde para "bajo", amarillo/naranja para "medio", rojo para "alto"
5. THE Clause_Card SHALL mostrar el campo explanation como texto explicativo en lenguaje simple
6. THE Clause_Card SHALL mostrar el campo suggested_question como una pregunta que el Usuario puede hacer antes de firmar
7. THE Results_Page SHALL ordenar las cláusulas por risk_level descendente: primero "alto", luego "medio", luego "bajo"

### Requisito 8: Contrato sin cláusulas de riesgo

**User Story:** Como Usuario, quiero recibir un mensaje positivo cuando mi contrato no tiene cláusulas riesgosas, para tener tranquilidad.

#### Acceptance Criteria

1. WHEN el campo clauses del análisis es un array vacío, THE Results_Page SHALL mostrar un mensaje positivo: "No se encontraron cláusulas de riesgo en tu contrato"
2. WHEN el campo clauses del análisis es un array vacío, THE Results_Page SHALL seguir mostrando el risk_score, el summary_plain y la overall_recommendation
3. WHEN el campo clauses del análisis es un array vacío, THE Results_Page SHALL usar un ícono o indicador visual positivo (no un estado vacío ni un mensaje de error)

### Requisito 9: Indicador de resultado cacheado

**User Story:** Como Usuario, quiero saber si el resultado que veo es de un análisis previo, para tener transparencia sobre la frescura de los datos.

#### Acceptance Criteria

1. WHEN el campo cached de la respuesta del Analyze_Endpoint es true, THE Results_Page SHALL mostrar una nota informativa: "Este resultado corresponde a un análisis previo del mismo documento"
2. WHEN el campo cached de la respuesta del Analyze_Endpoint es false, THE Results_Page SHALL no mostrar ninguna nota sobre caché
3. THE nota informativa de caché SHALL presentarse como información contextual neutra, no como advertencia ni error

### Requisito 10: Resumen y recomendación general

**User Story:** Como Usuario, quiero ver un resumen comprensible de mi contrato y una recomendación general, para tener una visión rápida antes de revisar los detalles.

#### Acceptance Criteria

1. THE Results_Page SHALL mostrar el campo summary_plain como sección de resumen en la parte superior de los resultados
2. THE Results_Page SHALL mostrar el campo overall_recommendation como sección de recomendación claramente diferenciada
3. THE Results_Page SHALL mostrar el summary_plain antes de las cláusulas individuales para proveer contexto general primero

### Requisito 11: Cliente HTTP para comunicación con el backend

**User Story:** Como desarrollador del frontend, quiero un módulo API client centralizado que maneje la comunicación con los endpoints de backend, para mantener la lógica de red aislada de los componentes.

#### Acceptance Criteria

1. THE API_Client SHALL exponer una función para enviar un archivo PDF al Ingest_Endpoint como multipart/form-data
2. THE API_Client SHALL exponer una función para enviar un document_id al Analyze_Endpoint como JSON
3. THE API_Client SHALL incluir la API Key configurada en cada request como header
4. IF la respuesta HTTP tiene status 4xx o 5xx, THEN THE API_Client SHALL parsear el body como error response tipada (IngestErrorResponse o AnalyzeErrorResponse) y retornarla de forma estructurada
5. IF la conexión de red falla o hay timeout, THEN THE API_Client SHALL retornar un error genérico con mensaje "No se pudo conectar con el servidor. Verificá tu conexión a internet."
6. THE API_Client SHALL usar los tipos definidos en frontend/src/types/contract.ts para todas las respuestas

### Requisito 12: Preguntas sugeridas consolidadas

**User Story:** Como Usuario, quiero ver un listado consolidado de todas las preguntas que debería hacer antes de firmar, para tener una referencia rápida y práctica.

#### Acceptance Criteria

1. WHEN existen cláusulas con suggested_question, THE Results_Page SHALL mostrar una sección "Preguntas para hacer antes de firmar" que consolide todas las preguntas sugeridas
2. THE sección de preguntas sugeridas SHALL listar cada pregunta como ítem individual asociada a la categoría de su cláusula
3. WHEN el campo clauses es un array vacío, THE Results_Page SHALL no mostrar la sección de preguntas sugeridas
