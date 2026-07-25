# Claro y Simple — Frontend

Interfaz de usuario para analizar contratos con IA. Permite subir un PDF y recibir un resumen en lenguaje simple, cláusulas de riesgo identificadas, un score de riesgo general, y preguntas sugeridas para hacer antes de firmar.

## Stack

- React 18 + TypeScript (strict mode)
- Vite como bundler
- Tailwind CSS para estilos
- Vitest + Testing Library para tests
- React Router para navegación

## Requisitos previos

- Node.js >= 18
- npm >= 9

## Instalación

```bash
npm install
```

## Variables de entorno

Copiar `.env.example` a `.env` y completar los valores:

```bash
cp .env.example .env
```

| Variable | Descripción |
|----------|-------------|
| `VITE_API_BASE_URL` | URL base del API Gateway (sin barra final). Ej: `http://localhost:3000` |
| `VITE_API_KEY` | API Key para el header `x-api-key` |

## Desarrollo

```bash
npm run dev
```

Levanta el servidor de desarrollo en `http://localhost:5173` con hot reload.

## Tests

```bash
npm run test
```

Ejecuta Vitest en modo watch. Para una corrida única:

```bash
npm run test -- --run
```

## Build de producción

```bash
npm run build
```

Genera el bundle optimizado en `dist/`. El comando ejecuta primero el chequeo de tipos con TypeScript y luego el build de Vite.

## Preview del build

```bash
npm run preview
```

Sirve el contenido de `dist/` localmente para verificar el build de producción.

## Estructura del proyecto

```
src/
├── api/           # Cliente HTTP para API Gateway
├── components/    # Componentes reutilizables (UploadZone, RiskScore, ClauseCard, etc.)
├── constants/     # Constantes: mensajes de error, categorías
├── pages/         # Páginas: Home (upload + flujo) y Results (visualización)
├── types/         # Tipos TypeScript (contratos de interfaz)
└── main.tsx       # Entry point
```
