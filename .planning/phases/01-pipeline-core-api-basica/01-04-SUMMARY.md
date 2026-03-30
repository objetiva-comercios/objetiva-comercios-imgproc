---
phase: 01-pipeline-core-api-basica
plan: 04
subsystem: api
tags: [fastapi, httpx, pytest, rembg, asyncio, multipart, webp]

# Dependency graph
requires:
  - phase: 01-02
    provides: "process_image() + ProcessingError con pipeline completo"
  - phase: 01-03
    provides: "JobQueue con asyncio.Semaphore, QueueFullError, QueueTimeoutError"
provides:
  - "FastAPI app con lifespan: rembg session global, ConfigManager, JobQueue inicializados en startup"
  - "POST /process: multipart, override parcial JSON, respuesta WebP con 6 headers X-*, errores 400/422/503/504"
  - "GET /health: estado de cola, modelo cargado y uptime_seconds"
  - "11 tests de integracion cubriendo todos los endpoints y error codes"
affects: [01-05, cli, webui, docker]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Lifespan de FastAPI para inicializacion de recursos globales (rembg session, queue, config)"
    - "app.state para compartir recursos entre lifespan y endpoints"
    - "submit_job() como punto de entrada unico al queue — el endpoint no llama process_image directamente"
    - "Override parcial via _deep_merge(config_dict, override_dict) — preserva keys no tocadas"
    - "Tests de integracion con app.router.lifespan_context(app) para disparar lifespan sin servidor real"
    - "Fixture client_with_queue retorna (client, queue) para que los tests puedan patchear submit_job"

key-files:
  created:
    - app/main.py
    - app/router_api.py
    - tests/test_api.py
  modified: []

key-decisions:
  - "Fixture de test usa app.router.lifespan_context(app) + ASGITransport — unica forma de disparar lifespan de FastAPI sin levantar servidor real con uvicorn"
  - "Tests mockean submit_job (no process_image) — mas robusto porque submit_job es la interfaz publica del queue al endpoint"
  - "ProcessingError con step='decode' -> 400, otros steps -> 500 — errores de input del usuario vs errores internos del pipeline"

patterns-established:
  - "API entry: app/main.py importa router_api despues de crear app (evita circular imports con app.state)"
  - "Error responses siguen ErrorResponse model: {error, detail, article_id}"

requirements-completed: [API-01, API-02, API-03, API-04, API-05, PIPE-10]

# Metrics
duration: 5min
completed: 2026-03-30
---

# Phase 01 Plan 04: FastAPI API HTTP Summary

**FastAPI app con lifespan inicializando rembg session global, POST /process con override parcial y 6 headers X-*, GET /health, y 11 tests de integracion con httpx AsyncClient**

## Performance

- **Duration:** 5 min
- **Started:** 2026-03-30T11:32:17Z
- **Completed:** 2026-03-30T11:37:00Z
- **Tasks:** 2
- **Files modified:** 3

## Accomplishments
- FastAPI app con lifespan que inicializa ConfigManager, rembg session global y JobQueue una sola vez en startup
- POST /process acepta multipart, aplica override parcial via JSON string, retorna WebP con 6 headers X-* y maneja 400/422/503/504
- GET /health retorna estado completo de cola, modelo y uptime sin interactuar con el queue
- 11 tests de integracion cubriendo todos los endpoints y error codes, con rembg mockeado

## Task Commits

Cada tarea commiteada atomicamente:

1. **Task 1: FastAPI app + lifespan + router_api.py** - `86f09d0` (feat)
2. **Task 2: Tests de integracion de la API (TDD green)** - `a942ac2` (feat)

## Files Created/Modified
- `app/main.py` - FastAPI app con lifespan: ConfigManager, rembg session global, JobQueue, startup_time
- `app/router_api.py` - POST /process con override, 6 headers X-*, errores 400/422/503/504; GET /health con queue state
- `tests/test_api.py` - 11 tests de integracion con fixture client_with_queue (lifespan + rembg mockeado)

## Decisions Made
- Fixture de test usa `app.router.lifespan_context(app)` en lugar de `ASGITransport` alone — ASGITransport no dispara el lifespan de FastAPI automaticamente, `lifespan_context` lo hace explicitamente
- Tests mockean `submit_job` (no `process_image`) — submit_job es la interfaz publica del queue al endpoint; mockear ahi es mas limpio y no requiere parchear asyncio.to_thread
- `ProcessingError` con `step='decode'` mapea a HTTP 400 (error del cliente/input invalido); otros steps mapean a 500 (error interno del pipeline)

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Fixture de test rediseñada para disparar lifespan correctamente**
- **Found during:** Task 2 (tests de integracion)
- **Issue:** El plan especificaba usar `ASGITransport(app=app)` como unica forma de crear el client; `ASGITransport` no dispara el lifespan de FastAPI, por lo que `app.state.job_queue` no estaba disponible
- **Fix:** Fixture `client_with_queue` usa `app.router.lifespan_context(app)` como context manager exterior, luego `ASGITransport` dentro — lifespan corre correctamente, `app.state` disponible
- **Files modified:** tests/test_api.py
- **Verification:** 11 tests pasan, lifespan inicializa estado antes de cada test
- **Committed in:** a942ac2 (Task 2 commit)

---

**Total deviations:** 1 auto-fixed (Rule 1 - bug en setup de tests)
**Impact on plan:** Fix necesario para que los tests funcionen correctamente. Sin cambios en la implementacion de la API.

## Issues Encountered
- `ASGITransport` de httpx no dispara el lifespan ASGI automaticamente — resuelto usando `app.router.lifespan_context(app)` explicitamente en el fixture

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- API HTTP completa y testeada; lista para Phase 01-05 (CLI + Dockerfile)
- Los endpoints POST /process y GET /health estan listos para ser expuestos via docker-compose
- Patron de fixture `client_with_queue` reutilizable para futuros tests de la Web UI

---
*Phase: 01-pipeline-core-api-basica*
*Completed: 2026-03-30*
