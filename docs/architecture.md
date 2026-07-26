# Arquitectura — Claro y Simple

> Material de referencia para el video del hackathon.
> Generado el 26/07/2026 a partir del código en producción.

---

## Diagrama 1 — Flujo de datos: cómo viaja un contrato desde que se sube hasta que se analiza

El sistema funciona en **dos pasos**: primero se extrae el texto del PDF, y una vez que se tiene el `document_id`, se dispara el análisis con inteligencia artificial. El frontend orquesta ambas llamadas — el usuario solo ve "subir PDF" y "ver resultado".

```mermaid
%%{init: {'theme': 'base', 'themeVariables': {'primaryColor': '#fff7ed', 'primaryTextColor': '#1e293b', 'primaryBorderColor': '#ea580c', 'lineColor': '#475569', 'secondaryColor': '#fdf2f8', 'tertiaryColor': '#eef2ff', 'noteBkgColor': '#fef9c3', 'noteTextColor': '#1e293b', 'actorTextColor': '#1e293b', 'actorBkg': '#e0f2fe', 'actorBorder': '#0369a1'}}}%%
sequenceDiagram
    actor Usuario
    participant FE as Frontend (S3)
    participant APIGW as API Gateway
    participant ING as Lambda de Ingestion
    participant S3 as S3 (PDFs)
    participant DDB1 as DynamoDB (extracciones)
    participant AN as Lambda de Analisis
    participant BR as Amazon Bedrock
    participant DDB2 as DynamoDB (analisis)

    rect rgb(255, 247, 237)
    Note over Usuario,DDB1: PASO 1 — Extraccion de texto
    Usuario->>FE: Sube el PDF
    FE->>APIGW: POST /ingest
    APIGW->>ING: Activa el Lambda
    Note over ING: Verifica que sea un PDF valido<br/>y que no pese mas de 10 MB
    ING->>S3: Guarda el PDF
    ING->>S3: Confirma que se guardo bien
    Note over ING,S3: El PDF se guarda ANTES de extraer texto<br/>porque si hace falta usar OCR<br/>este lee el archivo desde S3
    ING->>ING: Extrae el texto<br/>lector incluido o servicio OCR
    Note over ING: Se intenta primero la opcion gratuita<br/>sin costo. Solo si falla se usa OCR<br/>que cobra por pagina
    ING->>ING: Calcula una huella digital del texto<br/>para detectar si ya se subio antes
    Note over ING: La huella se saca del texto no del PDF<br/>dos archivos distintos del mismo contrato<br/>dan la misma huella
    ING->>DDB1: Consulta si esa huella ya existe
    DDB1-->>ING: No existe
    Note over ING,DDB1: Si esta consulta falla por cualquier motivo<br/>el sistema sigue como si fuera nuevo
    ING->>DDB1: Guarda el texto extraido<br/>vence en 24 h
    ING-->>APIGW: OK aca esta tu ID de documento
    APIGW-->>FE: ID de documento
    end

    rect rgb(253, 242, 248)
    Note over FE,DDB2: PASO 2 — Analisis con IA
    FE->>APIGW: POST /analyze con el ID
    APIGW->>AN: Activa el Lambda
    AN->>DDB2: Ya analizamos este documento antes?
    DDB2-->>AN: No es la primera vez
    Note over AN,DDB2: Se consulta el cache PRIMERO porque<br/>si ya existe nos ahorramos todo el resto<br/>Bedrock cobra por palabra procesada
    AN->>DDB1: Pedi el texto extraido
    DDB1-->>AN: Aca esta
    AN->>BR: Envia el texto a la IA
    BR-->>AN: Devuelve resumen lista de clausulas<br/>riesgosas y recomendacion
    Note over AN: La IA detecta las clausulas y su nivel de riesgo<br/>pero el puntaje numerico de 0 a 100 lo calcula<br/>nuestro sistema con una formula fija
    AN->>DDB2: Guarda el analisis<br/>vence en 7 dias
    AN-->>APIGW: Resultado completo
    APIGW-->>FE: Puntaje clausulas resumen y recomendacion
    end
```

---

## Diagrama 2 — Componentes del sistema

```mermaid
%%{init: {'theme': 'base', 'themeVariables': {'primaryColor': '#fff7ed', 'primaryTextColor': '#1e293b', 'primaryBorderColor': '#ea580c', 'lineColor': '#475569', 'secondaryColor': '#fdf2f8', 'tertiaryColor': '#eef2ff', 'noteBkgColor': '#fef9c3', 'noteTextColor': '#1e293b', 'actorTextColor': '#1e293b', 'actorBkg': '#e0f2fe', 'actorBorder': '#0369a1'}}}%%
flowchart LR
    Usuario((Usuario)) --> FE[Pagina web]

    FE -->|clave de API| APIGW[API Gateway<br/>limite 500/dia]

    APIGW -->|POST /ingest| ING[Lambda Ingestion<br/>lector PDF + OCR]
    APIGW -->|POST /analyze| AN[Lambda Analisis]

    subgraph Mod1["Modulo 1 — Extraccion"]
        ING --> S3B[(S3 PDFs 24 h)]
    end

    subgraph Mod2["Modulo 2 — Analisis"]
        AN --> BR{{Amazon Bedrock<br/>IA}}
    end

    subgraph BD["Base de datos"]
        DDB1[(Extracciones 24 h)]
        DDB2[(Analisis 7 dias)]
    end

    ING --> DDB1
    DDB1 -.->|lee texto| AN
    AN --> DDB2
```

---

## Decisiones clave que muestra el Diagrama 1

Cada nota del diagrama anterior refleja una decisión de diseño real del sistema:

1. **El PDF se guarda en S3 antes de extraer el texto** porque el servicio de OCR (para PDFs escaneados) no recibe el archivo — necesita la referencia de dónde está guardado.

2. **Se prefiere el lector de PDF incluido sobre el OCR** siempre que sea posible: el primero no tiene costo adicional, el OCR cobra por página procesada. Solo se usa OCR cuando el otro no pudo leer nada.

3. **La huella digital se calcula sobre el texto extraído**, no sobre el archivo PDF original. Dos personas que escanean el mismo contrato en papel producen archivos distintos, pero el texto es igual — y eso permite detectar que es el mismo documento y no analizarlo dos veces.

4. **La detección de duplicados es a prueba de fallos**: si la consulta falla por un error momentáneo, el sistema avanza como si fuera un documento nuevo. Es una optimización de costo, no un requisito indispensable.

5. **El caché se consulta antes de leer el texto y antes de llamar a la IA** porque es el mayor ahorro del sistema: si un documento ya fue analizado, se devuelve el resultado guardado sin gastar ni un centavo en inteligencia artificial.

6. **El puntaje de riesgo (0 a 100) no lo inventa la IA**: lo calcula nuestro sistema con una fórmula fija a partir de la cantidad y gravedad de las cláusulas detectadas. Esto garantiza que el mismo contrato, analizado dos veces, dé siempre el mismo puntaje.
