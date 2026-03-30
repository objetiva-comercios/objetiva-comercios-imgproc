---
phase: 01-pipeline-core-api-basica
plan: "03"
subsystem: queue
tags: [asyncio, semaphore, concurrency, queue, cpu-bound]
dependency_graph:
  requires: ["01-01"]
  provides: ["app/queue.py", "tests/test_queue.py"]
  affects: ["app/main.py (plan 04+)"]
tech_stack:
  added: []
  patterns:
    - asyncio.Semaphore para control de concurrencia sin Celery
    - asyncio.wait_for(semaphore.acquire(), timeout) para 504 timeout
    - asyncio.to_thread() para CPU-bound safe en event loop
    - deque(maxlen=50) para historial de jobs en memoria
key_files:
  created:
    - app/queue.py
    - tests/test_queue.py
  modified: []
decisions:
  - JobQueue acepta config_snapshot ya tomado (caller responsable de get_snapshot()) — alineado con CONF-06
  - QueueFullError verifica queued_jobs antes de encolar (check sin encolar = 503 inmediato per QUEUE-02)
  - semaphore.release() en finally block garantiza liberación incluso ante excepciones
metrics:
  duration: "2m 43s"
  completed_date: "2026-03-30"
  tasks_completed: 1
  files_created: 2
  files_modified: 0
  tests_added: 9
---

# Phase 01 Plan 03: JobQueue con asyncio.Semaphore Summary

**One-liner:** JobQueue con asyncio.Semaphore, to_thread CPU-safe, y control de 503/504 via QueueFullError/QueueTimeoutError.

## What Was Built

`app/queue.py` implementa el gateway entre la API HTTP y el processor. Controla concurrencia mediante `asyncio.Semaphore`, protege contra sobrecarga con rechazo inmediato 503 (cola llena), y garantiza que el trabajo CPU-bound (rembg + Pillow) nunca bloquee el event loop via `asyncio.to_thread()`.

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | JobQueue con semaphore, estado y submit_job | 4f8748b | app/queue.py, tests/test_queue.py |

## Decisions Made

1. **config_snapshot es responsabilidad del caller**: `submit_job()` recibe el snapshot ya tomado. El caller (el endpoint de FastAPI) es quien llama `config_manager.get_snapshot()` antes de encolar. Esto alinea con CONF-06 y hace el queue agnóstico al ConfigManager.

2. **Check de cola llena sin encolar**: La condición `queued_jobs >= max_queue_size` se evalúa antes de incrementar el contador. Si la cola está llena, el request obtiene 503 instantáneo — nunca se encola, nunca espera.

3. **semaphore.release() en finally**: La liberación del semaphore está en el bloque `finally` del procesamiento, garantizando que siempre se libere incluso ante excepciones no esperadas en process_fn.

## Test Coverage

9 tests cubriendo todos los escenarios del plan:

| Test | Escenario | Resultado |
|------|-----------|-----------|
| test_max_concurrent | Solo 1 activo con max_concurrent=1, segundo espera | PASS |
| test_503_queue_full | Tercer job cuando semaphore ocupado y cola llena -> QueueFullError | PASS |
| test_504_timeout | timeout_seconds=0.1, semaphore ocupado -> QueueTimeoutError | PASS |
| test_state_tracking | active_jobs=1 durante ejecución, total_processed incrementado al finalizar | PASS |
| test_error_tracking | Job que falla -> total_errors++, active_jobs vuelve a 0 | PASS |
| test_to_thread | process_fn corre en thread != MainThread | PASS |
| test_config_snapshot | Config llega intacto a process_fn | PASS |
| test_job_history | JobRecord creado con article_id, status, model_used, timestamp | PASS |
| test_multiple_jobs_sequential | 3 jobs en secuencia, total_processed=3 | PASS |

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] pytest-asyncio no estaba instalado**
- **Found during:** RED phase al correr los tests por primera vez
- **Issue:** `asyncio_mode = "auto"` en pyproject.toml requiere pytest-asyncio instalado. Sin él, todos los tests async fallan en colección.
- **Fix:** `pip3 install pytest-asyncio --break-system-packages`
- **Files modified:** ninguno (instalación de paquete del sistema)
- **Commit:** No aplica (instalación de dependencia)

### Out of scope (pre-existente)

- `tests/test_processor.py` falla con `ModuleNotFoundError: No module named 'app.processor'` — esto corresponde al plan 01-02 (no ejecutado aún en este contexto). No es causado por este plan y no fue modificado.

## Known Stubs

Ninguno. `app/queue.py` es funcional end-to-end con todos sus comportamientos implementados y testeados.

## Self-Check: PASSED

- [x] `app/queue.py` existe y tiene 238 líneas (min: 80)
- [x] `tests/test_queue.py` existe y tiene 9 tests (min: 7) y 284 líneas (min: 60)
- [x] Commit `4f8748b` existe en git log
- [x] Imports OK: `from app.queue import JobQueue, QueueFullError, QueueTimeoutError`
- [x] `pytest tests/test_queue.py -x` sale con exit code 0 (9 passed)
- [x] Todos los acceptance criteria del plan verificados
