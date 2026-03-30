# Phase 5: Tests + Hardening - Context

**Gathered:** 2026-03-30
**Status:** Ready for planning

<domain>
## Phase Boundary

Suite completa de tests unitarios e integracion que verifica el comportamiento del servicio bajo condiciones normales y edge cases. Los tests deben poder correrse en CI sin dependencias externas (modelo rembg mockeado). Cubre: processor (decode, autocrop, padding, aspect ratio, fondo blanco, tamano output, enhancement, pipeline completo), queue (job exitoso, 503 cola llena, max_concurrent, timeout 504, estado), y API (process success + headers, campos faltantes, imagen invalida, health, config GET/POST, UI HTML, status con historial).

No incluye: CI/CD pipeline setup (GitHub Actions, etc.), performance benchmarks, load testing, integracion con n8n/Traefik.

</domain>

<decisions>
## Implementation Decisions

### Estrategia de cobertura
- **D-01:** Auditar los tests existentes (2125 lineas, 80+ tests de fases 1-4) y completar los gaps contra TEST-01, TEST-02, TEST-03. No reescribir desde cero — los tests existentes ya cubren el camino feliz y muchos edge cases.
- **D-02:** Coverage target: 80%+ medido con `pytest --cov=app --cov-report=term-missing`. Sin configuracion de CI — solo ejecucion local.

### Edge cases del processor (TEST-01)
- **D-03:** Cubrir todos los edge cases documentados en decisiones de Fase 1: EXIF transpose (D-08), skip rembg para imagenes con alpha pre-existente (D-06), conversion CMYK a RGB (D-07), limite de megapixels con rechazo 400 (D-05), enhancement skip cuando brightness=1.0 y contrast=1.0.
- **D-04:** Pipeline completo end-to-end: verificar que una imagen JPEG de entrada produce un WebP de exactamente 800x800 con fondo blanco y producto centrado (mock de rembg).

### Tests de queue (TEST-02)
- **D-05:** Verificar: job completo exitoso con resultado correcto, 503 cuando cola llena (max_queue_size), max_concurrent=1 respetado (segundo job espera), timeout con 504 (queue.timeout_seconds), estado actualizado tras cada operacion (total_processed, total_errors, job_history).

### Tests de API (TEST-03)
- **D-06:** Verificar: POST /process success con todos los headers (X-Article-Id, X-Processing-Time-Ms, X-Model-Used, X-Original-Size, X-Output-Size, X-Steps-Applied), POST /process 422 para campos faltantes, POST /process 400 para imagen invalida, GET /health con estructura completa, GET/POST /config, GET /ui sirve HTML valido, GET /status con historial.
- **D-07:** Tests de API mockean submit_job (no process_image) — decision de Fase 1 que se mantiene.

### Estrategia de hardening
- **D-08:** Hardening = tests que verifican edge cases y comportamiento defensivo ya implementado en el codigo. No se agregan nuevas validaciones al codigo fuente — el codigo ya tiene: megapixel limit, CMYK conversion, fail fast, timeout global, 503 queue full.

### Claude's Discretion
- Organizacion interna de los tests (clases vs funciones planas)
- Nombres de tests y descripciones
- Fixtures adicionales si son necesarias para edge cases no cubiertos
- Orden de ejecucion de tests (pytest lo maneja automaticamente)

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Especificacion del proyecto
- `PRD-image-standardizer-v2.md` -- PRD completo con pipeline, endpoints, config, comportamiento esperado
- `.planning/PROJECT.md` -- Vision, constraints (2GB RAM, 1.5 CPU)
- `.planning/REQUIREMENTS.md` -- Requirements TEST-01, TEST-02, TEST-03 (definicion exacta de que testear)
- `CLAUDE.md` -- Stack tecnologico (pytest 9.0.2, pytest-asyncio 1.3.0, httpx 0.28.1, pytest-cov)

### Codigo fuente a testear
- `app/processor.py` -- Pipeline completo: decode, rembg, autocrop, scale, composite, enhance, encode
- `app/queue.py` -- JobQueue con asyncio.Semaphore, submit_job, QueueState, JobRecord
- `app/router_api.py` -- POST /process, GET /health
- `app/router_config.py` -- GET/POST /config, GET /status, VALID_MODELS
- `app/router_ui.py` -- GET /ui
- `app/config.py` -- ConfigManager con reload, get_snapshot, update_config
- `app/models.py` -- AppConfig, ProcessingResult, ProcessingError

### Tests existentes (auditar y completar)
- `tests/conftest.py` -- Fixtures compartidas (sample_jpeg, sample_png_transparent, sample_cmyk, sample_large_image, config_manager)
- `tests/test_processor.py` -- 493 lineas, cubre decode, autocrop, scale, composite, enhance, encode, pipeline
- `tests/test_queue.py` -- 284 lineas, cubre max_concurrent, 503, timeout, state tracking, job_history
- `tests/test_api.py` -- 293 lineas, cubre process success/headers/errors, health
- `tests/test_config_router.py` -- 236 lineas, cubre GET/POST /config, GET /status
- `tests/test_ui.py` -- 122 lineas, cubre UI returns HTML
- `tests/test_cli.py` -- 344 lineas, cubre process, batch, serve, config commands
- `tests/test_config.py` -- 46 lineas, cubre config load, defaults, snapshot, reload
- `tests/test_watchdog.py` -- 210 lineas, cubre hot-reload watchdog

### Contexto de fases anteriores
- `.planning/phases/01-pipeline-core-api-basica/01-CONTEXT.md` -- Decisiones de pipeline (D-05 megapixels, D-06 skip rembg, D-09 fail fast, D-10 timeout global)
- `.planning/phases/02-observabilidad-config-operacional/02-CONTEXT.md` -- Decisiones de config (D-01 503 durante swap, D-03 validacion estricta)

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `tests/conftest.py` -- Fixtures de imagenes de prueba (JPEG, PNG transparente, CMYK, imagen grande). Reutilizar y extender si hace falta.
- Pattern de mock de rembg: `unittest.mock.patch("app.processor.remove")` usado en test_processor.py
- Pattern de mock de submit_job: usado en test_api.py para evitar dependencia del queue real
- Pattern de lifespan: `app.router.lifespan_context(app)` en tests de API para inicializar state

### Established Patterns
- Tests sync para processor (funciones puras)
- Tests async con pytest-asyncio para queue (asyncio.Semaphore)
- Tests de API con httpx.AsyncClient + ASGITransport
- Clases de test en test_processor.py (TestDecodeAndValidate, TestRemoveBackground, etc.)
- Funciones planas en test_api.py y test_queue.py

### Integration Points
- `pyproject.toml` -- asyncio_mode = "auto", testpaths = ["tests"]
- pytest-cov a agregar en requirements-dev.txt
- Correr con: `pytest --cov=app --cov-report=term-missing`

</code_context>

<specifics>
## Specific Ideas

- La audit de tests existentes debe mapear cada test a un requirement especifico (TEST-01.x, TEST-02.x, TEST-03.x) para identificar gaps
- Los tests de Fase 5 son la "red de seguridad" antes de deploy — deben cubrir los edge cases que las fases anteriores implementaron pero no siempre testearon exhaustivamente
- El mock de rembg es critico: nunca cargar el modelo ONNX en tests (decision de Fase 1)

</specifics>

<deferred>
## Deferred Ideas

None -- discussion stayed within phase scope

</deferred>

---

*Phase: 05-tests-hardening*
*Context gathered: 2026-03-30*
