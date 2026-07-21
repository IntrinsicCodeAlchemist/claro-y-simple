---
inclusion: always
---

# Claro y Simple — Product Steering

## Nombre y Tagline

**Claro y Simple**
*"Entendé lo que firmás."*

---

## Problema que Resuelve

En Argentina y LatAm, millones de personas firman contratos de alquiler, servicios, suscripciones y acuerdos laborales sin entender realmente lo que aceptan. Las cláusulas abusivas están escritas en lenguaje legal denso, deliberadamente difícil de interpretar para alguien sin formación jurídica.

El acceso a asesoría legal es costoso y está fuera del alcance económico de la mayoría de la población. El resultado: personas que firman contratos con cláusulas de renovación automática que no pueden cancelar, multas desproporcionadas por rescisión, cesión de datos personales sin límites, o jurisdicciones inconvenientes para resolver conflictos.

Claro y Simple existe para democratizar el acceso a la comprensión legal.

---

## Qué Hace el Producto

El usuario sube un PDF de un contrato y recibe:

### 1. Resumen en lenguaje simple
Un resumen en lenguaje cotidiano y accesible de qué dice el contrato, qué se está comprometiendo a hacer, y cuáles son las condiciones principales.

### 2. Lista de cláusulas de riesgo
Cada cláusula riesgosa identificada incluye:
- **Texto original**: la cláusula tal como aparece en el contrato
- **Categoría**: una de las siguientes —
  - `renovacion_automatica`: cláusulas que renuevan el contrato sin acción explícita del usuario
  - `multa`: penalizaciones económicas por incumplimiento o rescisión
  - `jurisdiccion`: cláusulas que definen dónde se resuelven conflictos (a menudo inconveniente para el usuario)
  - `cesion_datos`: permisos para compartir o ceder datos personales a terceros
  - `otro`: cláusulas riesgosas que no entran en las categorías anteriores
- **Nivel de riesgo**: `bajo`, `medio`, o `alto`
- **Explicación**: por qué esta cláusula puede ser problemática, en lenguaje simple

### 3. Score de riesgo general
Un número entero de 0 a 100 que indica el riesgo global del contrato. 0 = sin riesgos detectados, 100 = contrato extremadamente riesgoso.

### 4. Sugerencias de preguntas
Una lista de preguntas concretas que el usuario debería hacer a la otra parte antes de firmar, basadas en las cláusulas detectadas.

---

## Usuarios Objetivo

Personas en Argentina y LatAm que:
- Alquilan una vivienda o local comercial
- Contratan servicios (internet, telefonía, seguros)
- Se suscriben a plataformas o servicios digitales
- Firman contratos de trabajo o freelance
- Solicitan préstamos o créditos

Característica común: no tienen acceso económico a asesoría legal y necesitan tomar decisiones informadas rápidamente.

---

## Objetivo de Impacto y Escala

El impacto inmediato es proteger a personas individuales de cláusulas abusivas en contratos cotidianos.

El potencial de escala es significativo:
- **Seguros**: pólizas con exclusiones ocultas y condiciones de cancelación abusivas
- **Préstamos y créditos**: tasas de interés variables, cláusulas de aceleración, garantías desproporcionadas
- **Empleo**: contratos laborales con cláusulas de no competencia, confidencialidad excesiva, o renuncia implícita a derechos
- **Telecomunicaciones**: permanencias mínimas, penalizaciones por portabilidad, cesión de datos a terceros

A largo plazo, el mismo motor de análisis puede adaptarse a otros países de la región con sus marcos legales específicos.

---

## Principios de Producto e Ingeniería

Estos principios guían las decisiones de diseño, priorización e implementación en todo el proyecto.

### El análisis debe ser genuinamente útil
El motor de IA no es un wrapper trivial de un prompt genérico. Debe identificar cláusulas riesgosas con precisión suficiente para que un usuario sin formación legal pueda tomar decisiones informadas. Si el análisis no agrega valor real sobre leer el contrato directamente, no cumple su propósito.

### El MVP cubre el flujo completo antes que cualquier otra cosa
La prioridad absoluta es que el flujo end-to-end funcione: subida de PDF → extracción de texto → análisis → resultados en pantalla. Ninguna optimización, feature adicional, o mejora de UX justifica agregar complejidad antes de que ese flujo esté estable y demostrable.

### La IA se usa donde agrega valor diferencial
Amazon Bedrock no es un componente decorativo. El análisis de cláusulas y la generación de resúmenes deben demostrar que la IA hace algo que no se puede hacer con reglas simples: entender contexto, identificar riesgo implícito, y explicar en lenguaje accesible.

### La arquitectura refleja las decisiones del producto
Cada servicio AWS tiene un rol claro y justificado. No se agrega infraestructura por moda o por completitud; se agrega porque resuelve un problema concreto del producto.

### Simplicidad sobre completitud
En un proyecto con tiempo y presupuesto acotados, la decisión correcta es casi siempre la más simple que funciona. Una feature que no llegó al flujo principal es peor que no tenerla.

---

## Contexto del Proyecto

- **Evento**: Hackathon Kiro AI — Powered by AWS
- **Duración**: 7 días
- **Equipo**: 3 integrantes con conocimiento básico de AWS
- **Presupuesto**: $100 USD en créditos AWS

Estas restricciones son reales y deben tenerse en cuenta en cada decisión técnica: preferir servicios serverless, evitar costos fijos, y mantener el scope acotado al flujo principal.
