# Phase 1: Pipeline Core + API Basica - Context

**Gathered:** 2026-03-30
**Status:** Ready for planning

<domain>
## Phase Boundary

El servicio acepta una imagen de producto de cualquier formato/tamano, elimina el fondo con rembg, estandariza el resultado (800x800, fondo blanco, producto centrado con padding) y devuelve un WebP listo para catalogo. Corre en Docker con el modelo birefnet-lite pre-descargado. Expone POST /process, GET /health, y maneja cola in-memory con asyncio.Semaphore.

Incluye: pipeline completo (7 steps), API HTTP basica, queue con semaphore, config YAML (lectura al startup), Dockerfile y docker-compose.yml.
No incluye: hot-reload de config (Fase 2), GET /status con historial (Fase 2), CLI (Fase 3), Web UI (Fase 4), test suite (Fase 5).

</domain>

<decisions>
## Implementation Decisions

### Formato de errores API
- **D-01:** Respuestas de error en JSON estructurado: `{"error": "tipo", "detail": "mensaje", "article_id": "..."}` con Content-Type: application/json
- **D-02:** Error 400 (imagen corrupta) usa mensaje generico "Invalid or corrupt image" — sin exponer internals de Pillow

### Estrategia de logging
- **D-03:** Formato structured JSON para todos los logs: `{"level": "info", "event": "rembg_complete", "duration_ms": 3200, "article_id": "ART-001"}`
- **D-04:** Un log por cada step del pipeline (decode, rembg, autocrop, scale, composite, enhance, encode) con duracion individual. Permite identificar bottlenecks

### EXIF y formatos edge
- **D-05:** Limite de megapixels en la entrada: rechazar imagenes > 25 megapixels con 400. Protege contra OOM (una imagen 8000x8000 RGBA = ~256MB en RAM)
- **D-06:** Imagenes con alpha pre-existente (PNG transparente con >10% pixeles transparentes): saltear rembg y pasar directo a autocrop. Ahorra 3-10s de procesamiento innecesario
- **D-07:** Imagenes CMYK: convertir automaticamente a RGB antes de procesar (silenciosamente). rembg requiere RGB/RGBA
- **D-08:** EXIF transpose aplicado siempre antes de procesar (ya definido en PIPE-02)

### Resiliencia del pipeline
- **D-09:** Fail fast: si cualquier step falla, abortar inmediatamente y retornar 500 con detalle del step que fallo. Sin fallback ni imagen parcial
- **D-10:** Solo timeout global (queue.timeout_seconds). Sin timeout por step individual. Si rembg se cuelga, el timeout global lo mata

### Claude's Discretion
Ninguna area delegada — todas las decisiones fueron tomadas explicitamente por el usuario.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Especificacion del proyecto
- `PRD-image-standardizer-v2.md` — PRD completo con estructura de proyecto, pipeline detallado step-by-step, config defaults (settings.yaml), endpoints HTTP, comportamiento del queue, y formato de respuestas
- `.planning/PROJECT.md` — Vision, constraints (2GB RAM, 1.5 CPU, sin GPU), key decisions
- `.planning/REQUIREMENTS.md` — Requirements PIPE-01 a PIPE-10, API-01 a API-05, QUEUE-01 a QUEUE-04, CONF-01, CONF-06, DOCK-01 a DOCK-05
- `CLAUDE.md` — Stack tecnologico completo con versiones pinned, patterns, y anti-patterns

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- Ninguno — proyecto greenfield, no hay codigo existente

### Established Patterns
- Estructura de proyecto definida en PRD: `app/` con main.py, config.py, processor.py, queue.py, models.py, router_api.py, router_config.py
- Pipeline de 7 steps con funciones puras e independientes (definido en PRD seccion 6)
- Queue con asyncio.Semaphore (definido en PRD seccion 7)

### Integration Points
- FastAPI lifespan para inicializar sesion rembg global
- asyncio.to_thread() para wrappear proceso CPU-bound
- settings.yaml como unica fuente de configuracion al startup

</code_context>

<specifics>
## Specific Ideas

- El PRD ya define la firma publica del processor: `async def process_image(image_bytes, article_id, config, rembg_session) -> ProcessingResult`
- Config snapshot inmutable durante cada job (CONF-06): se toma al inicio del job, no se modifica durante procesamiento
- OMP_NUM_THREADS=2 + intra_op_num_threads=2 en el Dockerfile para evitar thread explosion de ONNX

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope

</deferred>

---

*Phase: 01-pipeline-core-api-basica*
*Context gathered: 2026-03-30*
