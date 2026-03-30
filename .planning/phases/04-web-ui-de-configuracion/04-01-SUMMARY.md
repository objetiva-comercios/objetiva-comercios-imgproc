---
phase: 04-web-ui-de-configuracion
plan: 01
subsystem: ui
tags: [fastapi, jinja2, html, vanilla-js, rembg, polling]

# Dependency graph
requires:
  - phase: 02-observabilidad-config-operacional
    provides: GET/POST /config con hot-reload, AppConfig Pydantic models, ConfigManager
  - phase: 01-pipeline-core-api-basica
    provides: app/main.py con lifespan FastAPI, router_api.py con /health, modelos Pydantic
provides:
  - GET /ui endpoint con Jinja2TemplateResponse retornando HTML autocontenido
  - app/templates/ui.html stub funcional con todos los controles de AppConfig
  - model_swapping en GET /health (necesario para banner de swap en la UI)
  - 11 tests de integracion en test_ui.py cubriendo UI-01 a UI-05 + Pitfall 1
affects: [04-02-web-ui-de-configuracion]

# Tech tracking
tech-stack:
  added: [Jinja2Templates via fastapi.templating, Path(__file__).parent para path absoluto de templates]
  patterns:
    - "router_ui.py usa Path(__file__).parent / templates — path absoluto, robusto ante CWD changes"
    - "ui_client fixture: patch rembg.new_session + lifespan_context + ASGITransport (mismo patron que test_api.py)"
    - "getattr(app.state, field, default) para campos opcionales en app.state"

key-files:
  created:
    - app/router_ui.py
    - app/templates/ui.html
    - tests/test_ui.py
  modified:
    - app/router_api.py
    - app/main.py

key-decisions:
  - "Jinja2Templates inicializado con Path(__file__).parent / templates (path absoluto) — evita fallo por CWD relativo en uvicorn"
  - "Template stub ui.html incluye todos los IDs de controles requeridos por test_ui.py — Plan 02 reemplaza solo el HTML/CSS visual"
  - "model_swapping agregado con getattr(state, model_swapping, False) — retrocompatible si state no tiene el atributo"

patterns-established:
  - "Template HTML autocontenido: sin /static/, sin dependencias externas JS/CSS"
  - "Polling via setInterval fetch(/health) cada 5s para estado en tiempo real"

requirements-completed: [UI-01]

# Metrics
duration: 8min
completed: 2026-03-30
---

# Phase 04 Plan 01: Web UI Backend + Template Stub Summary

**Endpoint GET /ui con Jinja2TemplateResponse, template stub HTML autocontenido con todos los controles de AppConfig y polling JS, model_swapping en /health, 11 tests pasando**

## Performance

- **Duration:** ~8 min
- **Started:** 2026-03-30T22:16:00Z
- **Completed:** 2026-03-30T22:24:00Z
- **Tasks:** 2
- **Files modified:** 5 (3 creados, 2 modificados)

## Accomplishments

- Endpoint GET /ui registrado en main.py que retorna HTML con Jinja2TemplateResponse inyectando config activa, defaults y modelos validos
- Template stub ui.html autocontenido con todos los controles de AppConfig (rembg, output, padding, autocrop, enhancement, queue), dark mode CSS, viewport mobile, polling JS y funciones saveConfig/restoreDefaults/toggleYaml
- Campo model_swapping agregado a GET /health — habilita el banner de swap en la UI sin romper la API existente
- 11 tests de integracion en test_ui.py — todos pasan, suite completa de 94 tests sigue verde

## Task Commits

1. **Task 1: Router UI + health fix + main.py registration** - `0851767` (feat)
2. **Task 2: Tests de integracion para GET /ui** - `293d11e` (test)

## Files Created/Modified

- `app/router_ui.py` - Endpoint GET /ui con Jinja2Templates via Path(__file__).parent
- `app/templates/ui.html` - Template stub HTML con todos los controles de AppConfig
- `tests/test_ui.py` - 11 tests de integracion cubriendo UI-01 a UI-05 + Pitfall 1
- `app/router_api.py` - model_swapping agregado a health_endpoint
- `app/main.py` - ui_router registrado via include_router

## Decisions Made

- Jinja2Templates inicializado con `Path(__file__).parent / "templates"` (path absoluto) para evitar fallo por CWD relativo al lanzar uvicorn desde otra ubicacion
- Template stub incluye todos los IDs de controles HTML — Plan 02 reemplaza el HTML/CSS visual sin cambiar los IDs que los tests verifican
- `getattr(request.app.state, "model_swapping", False)` — retrocompatible con instancias de app.state que no tengan el atributo

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

- `watchdog` no estaba instalado en el sistema Python host (solo disponible en Docker). Instalado con `pip install --break-system-packages watchdog` para poder correr los tests localmente. El Dockerfile ya incluye watchdog en requirements.txt.

## User Setup Required

None - no external service configuration required.

## Known Stubs

- `app/templates/ui.html`: Template stub funcional con todos los controles requeridos. Tiene estilos minimos (system-ui, inputs basicos). Plan 02 reemplaza el HTML/CSS visual con la UI final usando skill frontend-design. Los IDs y la logica JS permanecen intactos — no es un stub bloqueante para el objetivo de este plan.

## Next Phase Readiness

- Plan 02 puede tomar `app/templates/ui.html` y reemplazarlo con la UI visual final (skill frontend-design + ui-ux-pro-max)
- Los tests en test_ui.py validan los contratos funcionales — cualquier reemplazo del template debe mantener los IDs verificados
- GET /health ya incluye model_swapping — D-04 (banner de swap) funcionara en cuanto Plan 02 construya la UI final

---
*Phase: 04-web-ui-de-configuracion*
*Completed: 2026-03-30*

## Self-Check: PASSED

- app/router_ui.py: FOUND
- app/templates/ui.html: FOUND
- tests/test_ui.py: FOUND
- 04-01-SUMMARY.md: FOUND
- commit 0851767: FOUND
- commit 293d11e: FOUND
