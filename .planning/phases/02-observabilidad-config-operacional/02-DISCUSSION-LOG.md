# Phase 2: Observabilidad + Config Operacional - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-03-30
**Phase:** 02-observabilidad-config-operacional
**Areas discussed:** Model swap, Validacion de config, Detalle de GET /status, Watchdog + POST /config

---

## Model Swap

### Comportamiento durante swap

| Option | Description | Selected |
|--------|-------------|----------|
| Bloquear cola | Rechazar nuevos requests con 503 mientras se recrea la sesion ONNX (~5-15s) | :heavy_check_mark: |
| Encolar y esperar | Requests se encolan y esperan a que el swap termine | |
| Drain + swap | Dejar terminar jobs activos, bloquear nuevos, reanudar despues | |

**User's choice:** Bloquear cola
**Notes:** Predecible y simple — el operador sabe que hay una ventana de downtime breve

### Tipo de swap

| Option | Description | Selected |
|--------|-------------|----------|
| Graceful | Crear nueva sesion primero, verificar que cargo OK, reemplazar referencia | :heavy_check_mark: |
| Instantaneo | Destruir vieja y crear nueva directamente | |

**User's choice:** Graceful
**Notes:** Si falla la carga de la nueva sesion, la vieja sigue funcionando

---

## Validacion de Config

### Respuesta ante valores invalidos

| Option | Description | Selected |
|--------|-------------|----------|
| Rechazar todo | 422 con detalle de que fallo, no aplicar nada | :heavy_check_mark: |
| Aplicar lo valido | Aceptar validos, ignorar invalidos, retornar warnings | |
| Validar sin aplicar | Endpoint separado POST /config/validate | |

**User's choice:** Rechazar todo
**Notes:** Simple y predecible para el operador

### Validacion de nombre de modelo

| Option | Description | Selected |
|--------|-------------|----------|
| Validar contra lista | Whitelist de modelos conocidos, rechazar desconocidos | :heavy_check_mark: |
| Intentar y fallar | Aceptar cualquier string, rollback si falla la carga | |

**User's choice:** Validar contra lista
**Notes:** Previene errores antes de intentar cargar un modelo inexistente

---

## Detalle de GET /status

### Nivel de detalle

| Option | Description | Selected |
|--------|-------------|----------|
| Solo metricas | Contadores + avg time + historial 50 jobs. Sin config activa | :heavy_check_mark: |
| Metricas + config | Todo + config activa embebida | |
| Metricas enriquecidas | Contadores + throughput/min + uptime + modelo activo | |

**User's choice:** Solo metricas
**Notes:** Config activa ya disponible en GET /config — sin duplicar

### Campos del historial

| Option | Description | Selected |
|--------|-------------|----------|
| Ligero | article_id, status, processing_time_ms, model_used, timestamp, error | |
| Con tamanos | Agregar original_size y output_size a cada JobRecord | :heavy_check_mark: |

**User's choice:** Con tamanos
**Notes:** Util para detectar imagenes problematicas

---

## Watchdog + POST /config

### Interaccion watchdog-POST

| Option | Description | Selected |
|--------|-------------|----------|
| Suprimir watchdog tras POST | Flag temporal para ignorar proximo evento | :heavy_check_mark: |
| Reload idempotente | Dejar que watchdog recargue aunque ya se aplico | |
| Debounce en watchdog | Acumular eventos, recargar maximo cada N segundos | |

**User's choice:** Suprimir watchdog tras POST
**Notes:** Evita reload redundante y posible race condition

### Logging de reload

| Option | Description | Selected |
|--------|-------------|----------|
| Structured log | JSON con event: config_reloaded, source: watchdog/api | :heavy_check_mark: |
| Solo si cambio algo | Comparar config vieja vs nueva, loggear solo diferencias | |

**User's choice:** Structured log siempre
**Notes:** Consistente con patron D-03/D-04 de Fase 1

---

## Claude's Discretion

Ninguna area delegada — todas las decisiones fueron tomadas por el usuario.

## Deferred Ideas

Ninguna — la discusion se mantuvo dentro del scope de la fase.
