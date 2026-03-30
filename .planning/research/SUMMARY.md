# Project Research Summary

**Project:** objetiva-comercios-imgproc — Image Standardization Microservice
**Domain:** Python image processing microservice (background removal + catalog normalization)
**Researched:** 2026-03-30
**Confidence:** HIGH

## Executive Summary

Este proyecto es un microservicio de procesamiento de imágenes para catálogos de ecommerce, diseñado para correr 100% self-hosted en un VPS con 2GB de RAM y sin dependencias externas. El patrón de implementación correcto es un pipeline determinístico secuencial (decode → rembg → autocrop → scale → composite → encode WebP) protegido por un `asyncio.Semaphore(1)` que serializa el acceso al modelo ONNX. La diferenciación principal frente a alternativas cloud (remove.bg, Photoroom) es la privacidad total, costo cero por imagen, y control operacional completo — no la calidad del modelo.

El stack recomendado converge de forma natural en FastAPI + rembg[cpu] + Pillow + Typer sobre Python 3.11-slim en Docker. No hay decisiones de stack controversiales: todas las tecnologías son la primera opción en su categoría para este tipo de servicio. La única complejidad arquitectural real es la gestión del ciclo de vida de la sesión ONNX (singleton en startup, nunca por request) y el bridge correcto entre el watchdog threaded y el event loop de asyncio para el hot-reload de configuración.

El riesgo principal no es técnico sino operacional: el servicio puede colapsar en el primer deploy si el modelo birefnet-lite no está pre-descargado en la imagen Docker, si la sesión rembg se instancia por request en lugar de globalmente, o si el pipeline CPU-bound bloquea el event loop. Los tres riesgos son prevenibles con patrones documentados y deben establecerse en la Fase 1 antes de cualquier otra funcionalidad.

---

## Key Findings

### Recommended Stack

El stack está completamente definido con versiones verificadas contra PyPI. Python 3.11 es obligatorio (rembg 2.0.74 requiere `>=3.11`). FastAPI 0.135.2 con uvicorn[standard] es el servidor ASGI de producción. rembg[cpu] 2.0.74 maneja la inferencia ONNX con birefnet-lite. Pillow 12.1.1 cubre todas las transformaciones de imagen. La imagen Docker base debe ser `python:3.11-slim` — nunca Alpine (rompe wheels de onnxruntime).

**Core technologies:**
- **Python 3.11 / python:3.11-slim**: Runtime y base Docker — LTS hasta Oct 2027, compatibilidad garantizada con todos los wheels
- **FastAPI 0.135.2 + uvicorn[standard]**: API async con Pydantic v2, documentación automática, 30-40% más throughput que uvicorn sin `[standard]`
- **rembg[cpu] 2.0.74**: Background removal con birefnet-lite; el extra `[cpu]` previene instalación accidental de onnxruntime-gpu
- **Pillow 12.1.1**: Todas las transformaciones post-rembg (autocrop, scale, composite, enhance, encode WebP)
- **Typer 0.24.1**: CLI (process, batch, serve, config) con type hints
- **watchdog 6.0.0 + PyYAML 6.0.3**: Hot-reload de config.yaml sin restart del container
- **asyncio.Semaphore(1)**: Control de concurrencia in-memory — alternativa correcta a Celery+Redis para < 100 img/día

### Expected Features

**Must have (table stakes — MVP v1):**
- Pipeline completo: decode → rembg → autocrop → scale 800x800 → composite fondo blanco → encode WebP
- `POST /process` — endpoint de integración para n8n
- `GET /health` — requerido por Docker y orquestadores
- Modelo birefnet-lite pre-descargado en imagen Docker — elimina cold start de 1-3 minutos
- Cola in-memory con `asyncio.Semaphore(max_concurrent=1)` — previene OOM en 2GB RAM
- Configuración vía YAML con valores default sensatos
- Dockerfile + docker-compose con límites de recursos (`memory=2g, cpus=1.5`)
- Tests unitarios del pipeline + tests de integración de la API

**Should have (post-validación v1.x):**
- Hot-reload de config con watchdog — cambios sin restart del container
- Web UI de configuración (Jinja2 + vanilla JS) — ajuste de parámetros sin CLI
- CLI completo (process, batch, serve, config) — procesamiento batch offline
- `GET /status` con métricas en memoria (jobs_total, queue_size, RAM, model_loaded)

**Defer (v2+):**
- Múltiples formatos de salida (JPEG, PNG) — solo si un consumidor real lo justifica
- Procesamiento batch vía API — diferir hasta > 1000 img/día
- Webhooks/callbacks — solo si n8n requiere async real
- Autenticación — el servicio es interno; aislar con firewall Docker

### Architecture Approach

El servicio tiene 4 capas: Entry (HTTP API + Web UI + CLI), Concurrency (asyncio.Queue + Semaphore), Processing (pipeline stateless), e Infrastructure (Config Manager + rembg Session singleton). La clave arquitectural es que el `ImageProcessor` es completamente stateless — recibe bytes y un `ConfigSnapshot` inmutable, devuelve bytes WebP. La sesión rembg y la configuración son estado externo inyectado, no leído desde globales. Esto garantiza que aumentar `max_concurrent` en el futuro no introduzca race conditions.

**Major components:**
1. **FastAPI lifespan** — único punto de inicialización de rembg Session, QueueManager y ConfigManager; almacenados en `app.state`
2. **QueueManager** — `asyncio.Semaphore(1)` + `asyncio.to_thread()` que despacha el pipeline CPU-bound sin bloquear el event loop
3. **ImageProcessor** — pipeline stateless con steps independientes (decode, remove_bg, autocrop, scale, composite, enhance, encode); testeable de forma unitaria
4. **ConfigManager** — YAML + watchdog Observer + `threading.RLock`; expone `get_snapshot()` thread-safe
5. **rembg Session** — singleton ONNX inicializado una sola vez; ~600MB RAM, 5-15s de startup

**Orden de construcción recomendado por la investigación:**
ConfigManager → ImageProcessor (pipeline steps) → rembg Session → QueueManager → FastAPI routes → Web UI → CLI → Docker

### Critical Pitfalls

1. **Sesión rembg por request (no global)** — Crea una sesión ONNX nueva por cada imagen. La RAM crece hasta OOMKill documentado en >137GB. Prevención: `new_session("birefnet-lite")` exactamente una vez en el `lifespan` de FastAPI, pasada como parámetro a cada llamada `remove(img, session=session)`.

2. **Pipeline CPU-bound en `async def` sin `asyncio.to_thread`** — rembg tarda 2-8s en CPU. Sin `to_thread`, bloquea el event loop completo: `GET /health` no responde durante inferencia. Prevención: `await asyncio.to_thread(ImageProcessor.run, bytes, config)` — todo el pipeline dentro del thread.

3. **Modelo no pre-descargado en Docker build** — Sin el `RUN python -c "from rembg import new_session; new_session('birefnet-lite')"` en el Dockerfile, el primer request espera 1-3 minutos descargando de HuggingFace. En el VPS puede timeout o fallar sin internet. Prevención: pre-download obligatorio en build time.

4. **ONNX Runtime ignorando límites de CPU del container** — ONNX lee topología del host, no del cgroup. En un VPS de 8 cores con `--cpus=1.5`, crea 8 threads generando CPU throttling severo. Prevención: `opts.intra_op_num_threads = 2` + `OMP_NUM_THREADS=2` en docker-compose environment.

5. **watchdog callback modificando estado async sin lock** — El observer de watchdog corre en un thread del OS; `asyncio.to_thread` corre en el thread pool. Sin `threading.RLock`, un config reload durante un request en vuelo puede producir outputs con dimensiones incorrectas o `KeyError`. Prevención: `threading.RLock` en ConfigManager + `ConfigSnapshot` inmutable pasado por parámetro al Processor.

**Pitfalls adicionales documentados:** EXIF orientation ignorada (usar `ImageOps.exif_transpose()` como primer step), modos de color inesperados CMYK/P/LA (normalizar antes de rembg), Pillow images sin cerrar (usar context managers), `Image.MAX_IMAGE_PIXELS = None` como DoS vector (setear límite a 50MP).

---

## Implications for Roadmap

La arquitectura tiene dependencias claras que dictan el orden de construcción. El pipeline es el núcleo y todo lo demás se construye sobre él. Los pitfalls críticos se concentran en la Fase 1.

### Phase 1: Foundation — Pipeline Core + API Mínima
**Rationale:** El pipeline es la única feature que importa. Sin él no hay nada. Los pitfalls 1, 2, 3, 4 y la mayoría de los pitfalls de imagen (EXIF, color mode, Pillow leaks) deben resolverse aquí o se vuelven deuda que contamina todo lo construido encima.
**Delivers:** Servicio funcional en Docker que acepta una imagen y devuelve WebP con fondo blanco 800x800. Integrable con n8n desde el día 1.
**Addresses:** Pipeline completo, `POST /process`, `GET /health`, modelo en Docker, Semaphore, Config YAML, Dockerfile + docker-compose con límites
**Avoids:** Pitfalls 1 (sesión global), 2 (to_thread), 3 (modelo en Docker), 4 (ONNX threads), 6 (EXIF), 7 (color modes), 4 (Pillow leaks), 9 (OOMKill)
**Research flag:** NO requiere investigación adicional — todos los patrones están documentados con código de ejemplo en ARCHITECTURE.md y PITFALLS.md

### Phase 2: Observability + Config Operacional
**Rationale:** El servicio está en producción pero el operador no tiene visibilidad. Hot-reload y status son las features que hacen operable el servicio sin restarts. El pitfall 5 (watchdog race condition) se aborda aquí.
**Delivers:** Hot-reload de config.yaml sin restart, `GET /status` con métricas en memoria, watchdog correctamente integrado con el event loop
**Addresses:** watchdog + hot-reload, `GET/POST /config`, `GET /status`
**Avoids:** Pitfall 5 (watchdog + asyncio race condition), UX pitfall de config sin feedback de reload
**Research flag:** NO requiere investigación adicional — los patrones de `threading.RLock` + ConfigSnapshot están documentados en ARCHITECTURE.md

### Phase 3: CLI + Batch Offline
**Rationale:** El CLI reutiliza el ImageProcessor directamente (sin HTTP) — es una fase de integración, no de nuevos algoritmos. Permite procesamiento batch sin levantar el servidor.
**Delivers:** Comandos `process`, `batch`, `serve`, `config` via Typer; procesamiento offline de carpetas de imágenes
**Addresses:** CLI batch, reutilización del pipeline sin API
**Avoids:** No introduce nuevos pitfalls — el CLI es stateless y no comparte event loop
**Research flag:** NO requiere investigación — Typer es bien documentado y el patrón de reutilizar el Processor directamente está en ARCHITECTURE.md

### Phase 4: Web UI de Configuración
**Rationale:** La Web UI es la feature con mayor valor para operadores no técnicos pero depende de los endpoints `/config` ya funcionando (Fase 2). Una sola página Jinja2 + vanilla JS es suficiente — sin framework frontend.
**Delivers:** Interfaz visual para editar y guardar configuración desde el browser; no requiere CLI ni edición manual de YAML
**Addresses:** Web UI de configuración, `GET /ui`
**Avoids:** Anti-feature de preview en tiempo real (no construir — ver FEATURES.md anti-features)
**Research flag:** PUEDE necesitar investigación sobre patrones de Jinja2 + FastAPI StaticFiles si el equipo no los conoce, pero es LOW priority dado que el patrón es straightforward

### Phase 5: Tests + Hardening
**Rationale:** Los tests son parte del MVP definido en FEATURES.md pero se pueden paralelizar con las fases anteriores o consolidar al final. Sin tests de integración no hay garantía de comportamiento bajo las condiciones edge documentadas en PITFALLS.md.
**Delivers:** Tests unitarios del pipeline (todos los modos de color, EXIF edge cases), tests de integración de la API (pytest-asyncio + httpx), coverage report, checklist de "Looks Done But Isn't" de PITFALLS.md verificada
**Addresses:** Cobertura de modos CMYK/P/L/LA, OOM test con imágenes 8MP, semaphore timeout test, config reload bajo carga
**Research flag:** NO requiere investigación — pytest-asyncio 1.x con `asyncio_mode = "auto"` está documentado en STACK.md

### Phase Ordering Rationale

- **Pipeline primero:** Sin el pipeline funcionando, el resto es plomería sin agua. La sesión rembg, el Semaphore y el Dockerfile son bloqueantes para todo lo demás.
- **Observability en Fase 2:** El servicio que va a producción sin métricas ni hot-reload es opaco. El costo de operar es alto sin estas herramientas.
- **CLI en Fase 3:** Reutiliza código ya escrito — es la fase de menor riesgo. El batch offline es una feature útil que sale casi gratis una vez que el Processor es stateless.
- **Web UI al final:** Tiene el mayor costo de implementación relativo a su valor. Es conveniente pero no bloqueante para operar el servicio. Depende de los endpoints de config de Fase 2.
- **Tests integrados desde Fase 1** pero formalizados en Fase 5: Los tests unitarios del pipeline deben escribirse en Fase 1 junto con el código (TDD recomendado). La consolidación en Fase 5 es para los tests de integración completos y el hardening.

### Research Flags

**Fases que NO necesitan `/gsd:research-phase`:**
- **Fase 1 (Pipeline Core):** Todos los patrones documentados con código. PITFALLS.md tiene ejemplos concretos de cada caso edge.
- **Fase 2 (Observability):** Patrones de watchdog + asyncio bridge están en ARCHITECTURE.md con código.
- **Fase 3 (CLI):** Typer es simple y el patrón de reutilizar el Processor está claro.
- **Fase 5 (Tests):** pytest-asyncio + httpx es estándar documentado.

**Fases que PODRÍAN necesitar investigación corta:**
- **Fase 4 (Web UI):** Solo si el equipo nunca usó Jinja2 + FastAPI `TemplateResponse`. La investigación es de 30 minutos, no de horas.

---

## Confidence Assessment

| Area | Confidence | Notes |
|------|------------|-------|
| Stack | HIGH | Todas las versiones verificadas contra PyPI oficial (2026-03-30). Compatibilidades cruzadas confirmadas. |
| Features | HIGH | Validado contra servicios comparables (remove.bg, Photoroom, ProductShots.ai, ZYNG AI) + estándares GS1. El scope de < 100 img/día clarifica qué simplificar. |
| Architecture | HIGH | Basado en documentación oficial de FastAPI lifespan, patrones de concurrencia async, y DeepWiki de rembg session management. |
| Pitfalls | HIGH (técnicos) / MEDIUM (watchdog threading) | Los pitfalls de memoria ONNX están documentados en issues reales de GitHub con casos reproducidos. El watchdog + asyncio es MEDIUM por ser menos frecuentemente documentado en combinación. |

**Overall confidence:** HIGH

### Gaps to Address

- **Consumo real de RAM de birefnet-lite en runtime:** PITFALLS.md cita ~600-800MB para el modelo + ~200-400MB de buffers ONNX durante inferencia. El rango es amplio. Validar con `docker stats` en las primeras pruebas reales antes de fijar `mem_limit` en docker-compose.
- **Tiempo real de inferencia en el VPS específico:** La investigación cita 2-8s en CPU. El VPS de Objetiva tiene 1.5 vCPU limitados — el tiempo real puede ser 6-12s en carga. Impacta el timeout del HTTP client en n8n (configurar con margen).
- **Versión exacta de PyYAML y onnxruntime:** STACK.md marca estas como MEDIUM confidence (verificadas via WebSearch, no PyPI directo). Validar al crear requirements.txt con `pip install rembg[cpu]==2.0.74` y revisar qué versiones resuelve pip automáticamente.

---

## Sources

### Primary (HIGH confidence)
- rembg PyPI + GitHub — sesión global, modelos soportados, Python >=3.11
- FastAPI docs (lifespan, async, concurrency) — patrones de to_thread y singleton
- PyPI oficial — versiones de FastAPI, uvicorn, Pillow, Typer, watchdog, httpx, pytest, pytest-asyncio
- ONNX Runtime threading docs — intra_op_num_threads, OMP_NUM_THREADS
- Python Docker slim vs alpine (pythonspeed.com) — decisión de imagen base

### Secondary (MEDIUM confidence)
- GitHub issues de rembg (#752, #289) — memory leak con sesiones por request
- GitHub issues de ONNX Runtime (#18749, #22271, #24101) — memory leaks, threading
- GitHub issues de Pillow (#7961, #7935) — memory leak con images no cerradas
- Frigate GitHub (#22620) — pthread_setaffinity_np en containers LXC
- ProductShots.ai, ZYNG AI, Photoroom, remove.bg — feature landscape de catálogo
- GS1 Product Image Specification Standard — estándares de tamaño/fondo

### Tertiary (LOW confidence / inferencia)
- Tiempos de inferencia de birefnet-lite en CPU (2-8s) — varían por hardware, no medidos en el VPS target
- Consumo de RAM en pico de inferencia (2.2-2.5GB) — estimado de casos reportados, no medido

---
*Research completed: 2026-03-30*
*Ready for roadmap: yes*
