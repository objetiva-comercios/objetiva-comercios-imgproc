---
phase: 02-observabilidad-config-operacional
plan: "02"
subsystem: config-watchdog
tags: [watchdog, hot-reload, model-swap, rembg, asyncio, threading]

dependency_graph:
  requires:
    - phase: 02-01
      provides: ConfigManager.update_config, POST /config, app.state.model_name
  provides:
    - ConfigReloadHandler (watchdog FileSystemEventHandler)
    - _reload_config (async, bridge thread→event loop)
    - _swap_rembg_session (async, graceful ONNX session swap con 503 barrier)
    - suppress_flag para evitar double-reload POST /config
    - POST /process rechaza con 503 durante model swap
  affects: [app/main.py, app/router_config.py, app/router_api.py]

tech-stack:
  added: [watchdog==6.0.0]
  patterns:
    - asyncio.run_coroutine_threadsafe para bridge watchdog thread → event loop
    - threading.Event como suppress_flag para evitar double-reload
    - asyncio.to_thread para new_session (CPU-bound, nunca en event loop)
    - asyncio.wait_for + semaphore.acquire como barrier para esperar job activo antes de swap
    - getattr(app.state, 'model_swapping', False) para check graceful sin KeyError

key-files:
  created:
    - tests/test_watchdog.py
  modified:
    - app/main.py
    - app/router_config.py
    - app/router_api.py

key-decisions:
  - "watchdog Observer se inicia/detiene en lifespan de FastAPI — no en un thread separado del proceso"
  - "suppress_flag (threading.Event) se activa ANTES de escribir YAML en POST /config para evitar double-reload"
  - "_swap_rembg_session usa semaphore.acquire como barrier — espera el job activo antes de cargar nuevo modelo"
  - "Si new_session falla, rembg_session vieja queda intacta (D-02) — el finally garantiza model_swapping=False"
  - "asyncio.get_running_loop() en Python 3.12+ — no usar get_event_loop() (deprecated)"

patterns-established:
  - "Bridge thread→asyncio: asyncio.run_coroutine_threadsafe(coro, loop) desde handlers de watchdog"
  - "Suppress flag pattern: set() antes de escritura, clear() en on_modified si activo"
  - "Model swap pattern: model_swapping=True → barrier → to_thread → swap atomico → finally model_swapping=False"

requirements-completed: [CONF-04, CONF-05]

duration: ~6 min
completed: "2026-03-30"
---

# Phase 02 Plan 02: Watchdog Hot-Reload + Model Swap Summary

**Watchdog Observer en lifespan que recarga config.yaml sin restart y realiza swap graceful de sesion ONNX con supresion de double-reload y 503 durante el swap.**

## Performance

- **Duration:** ~6 min
- **Started:** 2026-03-30T18:32:00Z
- **Completed:** 2026-03-30T18:38:07Z
- **Tasks:** 2
- **Files modified:** 4 (3 modificados + 1 creado)

## Accomplishments

- Watchdog Observer corriendo en el lifespan de FastAPI: detecta cambios en settings.yaml y recarga config automaticamente (CONF-05)
- Model swap graceful: cuando se cambia el modelo via edicion YAML o POST /config, se carga el nuevo modelo en asyncio.to_thread y se hace swap atomico de la referencia en app.state (CONF-04)
- Suppress flag: threading.Event que se activa antes de que POST /config escriba el YAML, evitando que watchdog dispare un reload adicional (D-07)
- 503 durante model swap: POST /process verifica `model_swapping` flag y retorna 503 con error "model_swapping" mientras el swap esta en curso (D-01)
- Fallback D-02: si new_session falla, la sesion vieja queda intacta; model_swapping=False via finally

## Task Commits

1. **Task 1: Watchdog Observer + model swap + flag supresion + 503 durante swap** - `d0c529c` (feat)
2. **Task 2: Tests de watchdog reload, supresion, y model swap** - `2d4c417` (test)

## Files Created/Modified

- `app/main.py` - Agregados ConfigReloadHandler, _reload_config, _swap_rembg_session; lifespan extendido con watchdog Observer (paso 5)
- `app/router_config.py` - POST /config activa suppress_flag antes de escribir YAML; dispara _swap_rembg_session si el modelo cambio
- `app/router_api.py` - POST /process verifica model_swapping y retorna 503 si True
- `tests/test_watchdog.py` - 5 tests cubriendo hot-reload, suppress, model swap flag, 503, y fallback D-02

## Decisions Made

- Watchdog Observer se inicia/detiene en lifespan de FastAPI — no en un thread separado del proceso; alineado con el patron de ciclo de vida de la app
- suppress_flag (threading.Event) se activa ANTES de escribir YAML en POST /config para evitar double-reload; el on_modified lo limpia si esta activo
- _swap_rembg_session usa semaphore.acquire como barrier — espera el job activo antes de cargar nuevo modelo; evita race condition
- Si new_session falla, rembg_session vieja queda intacta (D-02) — el finally garantiza model_swapping=False
- asyncio.get_running_loop() en Python 3.12+ — no usar get_event_loop() (deprecated en 3.10+)

## Deviations from Plan

Ninguna — plan ejecutado exactamente como estaba escrito.

## Issues Encountered

Ninguno — los 5 tests pasaron en primera corrida (GREEN directo sin RED intermedio porque la implementacion de Task 1 ya era correcta).

## Known Stubs

Ninguno — todos los comportamientos estan implementados y testeados.

## Next Phase Readiness

- Hot-reload y model swap completos — el operador puede modificar settings.yaml sin restart
- POST /config ahora coordina correctamente watchdog, model swap, y 503
- Listo para Phase 03 (Web UI de configuracion) que consumira GET/POST /config

## Self-Check: PASSED

- tests/test_watchdog.py: FOUND
- app/main.py: FOUND
- app/router_config.py: FOUND
- app/router_api.py: FOUND
- Commit d0c529c: FOUND
- Commit 2d4c417: FOUND

---
*Phase: 02-observabilidad-config-operacional*
*Completed: 2026-03-30*
