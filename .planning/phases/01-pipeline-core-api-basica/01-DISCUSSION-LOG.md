# Phase 1: Pipeline Core + API Basica - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-03-30
**Phase:** 01-pipeline-core-api-basica
**Areas discussed:** Formato de errores API, Estrategia de logging, EXIF y formatos edge, Resiliencia del pipeline

---

## Formato de errores API

### Formato de respuesta de error

| Option | Description | Selected |
|--------|-------------|----------|
| JSON estructurado | Body JSON con {"error", "detail", "article_id"}. Facil de parsear desde n8n | ✓ |
| Solo HTTP status + header | Sin body, info en headers X-Error-*. Minimo overhead | |
| JSON + HTTP Problem (RFC 7807) | Formato estandar RFC 7807. Mas formal, FastAPI tiene soporte nativo | |

**User's choice:** JSON estructurado
**Notes:** Elegido por facilidad de parseo desde n8n con IF node

### Detalle del error 400

| Option | Description | Selected |
|--------|-------------|----------|
| Mensaje generico | "Invalid or corrupt image" sin exponer internals de Pillow | ✓ |
| Mensaje con detalle de Pillow | Incluir error especifico de Pillow. Util para debugging | |

**User's choice:** Mensaje generico
**Notes:** Sin exposicion de internals

---

## Estrategia de logging

### Formato de logs

| Option | Description | Selected |
|--------|-------------|----------|
| Structured JSON | Cada linea JSON parseable. Ideal para Loki/Grafana a futuro | ✓ |
| Texto plano legible | Formato clasico con timestamp. Mas legible en docker logs | |
| Vos decidi | Claude elige | |

**User's choice:** Structured JSON
**Notes:** Ninguna

### Nivel de detalle

| Option | Description | Selected |
|--------|-------------|----------|
| Un log por step del pipeline | decode, rembg, autocrop, etc. con duracion individual | ✓ |
| Solo inicio y fin | Log al recibir request y al completar/fallar | |
| Configurable por nivel | INFO = inicio/fin, DEBUG = cada step | |

**User's choice:** Un log por step del pipeline
**Notes:** Permite identificar cual step es lento

---

## EXIF y formatos edge

### Limites de tamano de entrada

| Option | Description | Selected |
|--------|-------------|----------|
| Limite de megapixels | Rechazar > 25MP. Previene OOM | ✓ |
| Limite de filesize | Rechazar > 20MB. No protege contra PNG livianos pero enormes | |
| Ambos limites | Filesize + megapixels | |
| Sin limite | Aceptar cualquier imagen | |

**User's choice:** Limite de megapixels
**Notes:** Proteccion contra OOM con 2GB RAM

### Alpha pre-existente

| Option | Description | Selected |
|--------|-------------|----------|
| Saltear rembg | Si >10% pixeles transparentes, skip rembg. Ahorra 3-10s | ✓ |
| Siempre pasar por rembg | Procesar todo igual. Mas predecible | |
| Vos decidi | Claude elige | |

**User's choice:** Saltear rembg
**Notes:** Ahorro de tiempo en imagenes ya procesadas

### CMYK

| Option | Description | Selected |
|--------|-------------|----------|
| Convertir automaticamente | Detectar CMYK y convertir a RGB silenciosamente | ✓ |
| Rechazar con 400 | No aceptar CMYK | |
| Vos decidi | Claude elige | |

**User's choice:** Convertir automaticamente
**Notes:** Ninguna

---

## Resiliencia del pipeline

### Fallo de step individual

| Option | Description | Selected |
|--------|-------------|----------|
| Fail fast con error | Abortar inmediatamente, retornar 500 con detalle del step | ✓ |
| Fallback inteligente | Retornar imagen original redimensionada sin remocion de fondo | |
| Retry del step | Reintentar una vez antes de abortar | |

**User's choice:** Fail fast con error
**Notes:** Sin fallback ni imagen parcial

### Timeout por step

| Option | Description | Selected |
|--------|-------------|----------|
| Solo timeout global | queue.timeout_seconds es suficiente. Sin timers por step | ✓ |
| Timeout por step | Cada step con su limite individual | |
| Vos decidi | Claude elige | |

**User's choice:** Solo timeout global
**Notes:** Sin complejidad extra

---

## Claude's Discretion

Ninguna area delegada — todas las decisiones fueron tomadas explicitamente.

## Deferred Ideas

Ninguna — la discusion se mantuvo dentro del scope de la fase.
