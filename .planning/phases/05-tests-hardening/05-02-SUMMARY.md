---
phase: 05-tests-hardening
plan: "02"
subsystem: testing
tags: [pytest, httpx, fastapi, asyncmock, coverage]

requires:
  - phase: 05-tests-hardening-01
    provides: "pytest-cov instalado, suite base en verde con 94 tests"

provides:
  - "3 tests nuevos cubriendo paths de error en router_api.py y router_config.py"
  - "router_api.py al 100% de cobertura (lineas 150-157 cubiertas)"
  - "router_config.py al 95% de cobertura (lineas 55-56, 117-118 cubiertas)"
  - "Suite completa: 97 tests, 94% cobertura total"

affects: [tests, router_api, router_config]

tech-stack:
  added: []
  patterns:
    - "Mockear submit_job con AsyncMock(side_effect=RuntimeError) para triggear catch Exception generico en /process"
    - "Patchear app.main._swap_rembg_session (no app.router_config) porque es import local dentro de funcion"
    - "Enviar body no-JSON con Content-Type application/json para triggear invalid_json en /config"

key-files:
  created: []
  modified:
    - tests/test_api.py
    - tests/test_config_router.py

key-decisions:
  - "Patchear app.main._swap_rembg_session en lugar de app.router_config._swap_rembg_session — el import local dentro de la funcion hace que solo el namespace de app.main funcione"
  - "AsyncMock importado desde unittest.mock agregado a test_config_router.py (no estaba presente)"

patterns-established:
  - "Para cubrir catch Exception en endpoints: mockear la interfaz publica (submit_job) con side_effect=RuntimeError"

requirements-completed: [TEST-03]

duration: 5min
completed: 2026-03-30
---

# Phase 05 Plan 02: API Test Gaps Summary

**3 tests de error paths cubriendo router_api.py al 100% y router_config.py al 95%, suite completa en 97 tests con 94% cobertura**

## Performance

- **Duration:** 5 min
- **Started:** 2026-03-30T23:36:40Z
- **Completed:** 2026-03-30T23:41:00Z
- **Tasks:** 2
- **Files modified:** 2

## Accomplishments

- `test_process_500_internal_error`: cubre el catch Exception generico en router_api.py (lineas 150-157), router_api.py sube a 100% de cobertura
- `test_post_config_invalid_json_body`: cubre el bloque invalid_json en router_config.py (lineas 55-56)
- `test_post_config_model_change`: cubre el trigger de _swap_rembg_session en router_config.py (lineas 117-118)
- Suite total: 97 tests, 94% cobertura (partimos de 94 tests, 94% preexistente — los gaps ya estaban cubiertos parcialmente)

## Task Commits

1. **Task 1: test_process_500_internal_error en test_api.py** - `d30fcaa` (test)
2. **Task 2: tests invalid_json y model_change en test_config_router.py** - `da14184` (test)

## Files Created/Modified

- `tests/test_api.py` - Agrega test_process_500_internal_error al final del archivo
- `tests/test_config_router.py` - Agrega import AsyncMock/patch y 2 tests nuevos al final

## Decisions Made

- Patchear `app.main._swap_rembg_session` en lugar de `app.router_config._swap_rembg_session`: el import es local dentro de la funcion `update_config`, por lo que el patch sobre el namespace donde esta definido (app.main) es el unico que funciona.
- Agregar `from unittest.mock import AsyncMock, patch` a test_config_router.py — no estaba importado y era necesario para ambos tests nuevos.

## Deviations from Plan

None - plan ejecutado exactamente como estaba especificado. El unico ajuste menor fue agregar `patch` ademas de `AsyncMock` en el import (el plan mencionaba solo `AsyncMock` pero `patch` tambien faltaba). Esto es un fix trivial de import, no una desviacion de comportamiento.

## Issues Encountered

None.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- TEST-03 satisfecho: los 3 gaps de tests documentados en el PLAN estan cubiertos
- router_api.py al 100%, router_config.py al 95%
- Suite completa en verde: 97 tests, 94% cobertura
- Phase 05 completa (ambos planes ejecutados)

---
*Phase: 05-tests-hardening*
*Completed: 2026-03-30*
