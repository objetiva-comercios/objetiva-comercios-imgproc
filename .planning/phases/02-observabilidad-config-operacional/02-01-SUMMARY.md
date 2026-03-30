---
phase: 02-observabilidad-config-operacional
plan: "01"
subsystem: config-api
tags: [config, api, status, queue, fastapi, pydantic]
dependency_graph:
  requires: []
  provides: [GET /config, POST /config, GET /status, ConfigManager.update_config, JobRecord.original_size]
  affects: [app/router_config.py, app/config.py, app/queue.py, app/main.py]
tech_stack:
  added: []
  patterns: [deep-merge-config, pydantic-strict-validation, model-whitelist, YAML-persist]
key_files:
  created:
    - app/router_config.py
    - tests/test_config_router.py
  modified:
    - app/queue.py
    - app/config.py
    - app/main.py
decisions:
  - "POST /config usa deep merge parcial + validacion Pydantic estricta — rechaza TODO el request si cualquier campo es invalido"
  - "Modelo rembg validado contra whitelist de rembg.sessions (fallback hardcoded si rembg no disponible en CI)"
  - "JobRecord usa getattr(result, 'original_size', None) para compatibilidad con mocks de test que retornan strings"
  - "test_lifespan renombrado a _mock_lifespan para evitar que pytest lo detecte como test"
metrics:
  duration: "~8 min"
  completed_date: "2026-03-30"
  tasks_completed: 2
  files_changed: 5
---

# Phase 02 Plan 01: Config API + Status Endpoints Summary

**One-liner:** GET/POST /config con deep merge y persistencia YAML, GET /status con metricas e historial enriquecido via FastAPI router modular.

## What Was Built

Nuevo router `app/router_config.py` con 3 endpoints operacionales:

- **GET /config** (CONF-02): retorna la configuracion activa completa del servicio como JSON usando `config_manager.config.model_dump()`
- **POST /config** (CONF-03): deep merge del JSON parcial sobre la config activa, validacion de modelo rembg contra whitelist, validacion Pydantic estricta, persistencia en YAML via `update_config()`, log estructurado del evento
- **GET /status** (API-06): metricas operacionales (`total_processed`, `total_errors`, `avg_processing_time_ms`) e historial de jobs con `original_size`/`output_size` en cada item

Cambios de soporte:
- `app/queue.py`: JobRecord extendido con campos `original_size` y `output_size` (QUEUE-05, D-06)
- `app/config.py`: metodo `update_config(new_config)` que persiste YAML con `yaml.dump()` (CONF-03)
- `app/main.py`: router registrado via `app.include_router(config_router)`

## Tests

`tests/test_config_router.py` — 8 tests de integracion todos en verde:

| Test | Cubre |
|------|-------|
| test_get_config | CONF-02 — claves rembg/output/queue/server presentes |
| test_post_config_merge | CONF-03 — deep merge parcial, otros campos sin cambios |
| test_post_config_persist_yaml | CONF-03 — escritura en disco verificada con yaml.safe_load |
| test_post_config_invalid_rejects_all | D-03 — 422 validation_error, config no se modifica |
| test_post_config_invalid_model | D-04 — 422 invalid_model con modelo inventado |
| test_get_status_empty | API-06 — metricas en cero, historial vacio |
| test_get_status_with_history | QUEUE-05, D-06 — original_size y output_size en historial |
| test_status_avg_calculation | API-06 — avg 200ms para jobs de 100/200/300ms |

## Commits

| Task | Commit | Descripcion |
|------|--------|-------------|
| Task 1 | 4bce717 | feat(02-01): extend JobRecord, add update_config(), create router_config.py |
| Task 2 | 9af6d6f | test(02-01): integration tests for GET/POST /config and GET /status |

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] getattr para compatibilidad de result en submit_job**
- **Found during:** Task 1 verification (tests/test_queue.py failing)
- **Issue:** `result.original_size` fallaba cuando el mock de process_fn retornaba strings en lugar de ProcessingResult
- **Fix:** Cambiar a `getattr(result, "original_size", None)` y `getattr(result, "output_size", None)` en queue.py
- **Files modified:** app/queue.py
- **Commit:** 4bce717

**2. [Rule 1 - Bug] test_lifespan renombrado**
- **Found during:** Task 2 RED phase
- **Issue:** pytest detectaba la funcion `test_lifespan` como un test fixture fallido (`fixture 'app' not found`)
- **Fix:** Renombrado a `_mock_lifespan` con prefijo underscore
- **Files modified:** tests/test_config_router.py
- **Commit:** 9af6d6f

## Known Stubs

Ninguno — todos los endpoints retornan datos reales desde `app.state`.

## Self-Check: PASSED
