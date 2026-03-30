# Phase 2: Observabilidad + Config Operacional - Context

**Gathered:** 2026-03-30
**Status:** Ready for planning

<domain>
## Phase Boundary

El operador puede cambiar parametros del servicio (modelo, calidad, padding, limites de cola) sin reiniciar el container, y puede consultar metricas e historial de jobs via API. Incluye: hot-reload de YAML via watchdog, endpoints GET/POST /config, recreacion de sesion rembg al cambiar modelo, GET /status con metricas e historial, y estado completo del queue en memoria.

No incluye: CLI (Fase 3), Web UI (Fase 4), test suite (Fase 5).

</domain>

<decisions>
## Implementation Decisions

### Model Swap (CONF-04)
- **D-01:** Bloquear cola con 503 durante el swap de modelo rembg. Requests entrantes reciben rechazo inmediato mientras se recrea la sesion ONNX (~5-15s). Predecible para el operador.
- **D-02:** Swap graceful: crear nueva sesion ONNX primero, verificar que cargo OK, y recien entonces reemplazar la referencia en app.state. Si la carga falla, la sesion vieja sigue funcionando sin interrupcion.

### Validacion de Config (CONF-03)
- **D-03:** Validacion estricta: si POST /config recibe cualquier campo invalido, rechazar TODO el request con 422 y detalle de que fallo. No aplicar parcialmente.
- **D-04:** Validar nombre de modelo rembg contra whitelist de modelos conocidos (birefnet-lite, isnet-general-use, u2net, etc.). Rechazar nombres desconocidos antes de intentar cargar.

### GET /status (API-06)
- **D-05:** Respuesta enfocada en metricas operacionales: total_processed, total_errors, avg_processing_time_ms, historial de ultimos 50 jobs. Sin incluir config activa (ya esta en GET /config).
- **D-06:** Historial de jobs enriquecido: cada JobRecord incluye original_size y output_size ademas de article_id, status, processing_time_ms, model_used, timestamp, error.

### Watchdog + POST /config (CONF-05)
- **D-07:** Flag de supresion temporal tras POST /config para evitar double reload. Cuando POST /config escribe el YAML, se activa un flag que indica al watchdog ignorar el proximo evento de modificacion del archivo.
- **D-08:** Log structured JSON en cada reload de config: `{"event": "config_reloaded", "source": "watchdog"|"api", ...}`. Consistente con el patron de logging D-03/D-04 de Fase 1.

### Claude's Discretion
Ninguna area delegada — todas las decisiones fueron tomadas explicitamente por el usuario.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Especificacion del proyecto
- `PRD-image-standardizer-v2.md` — PRD completo con estructura de proyecto, pipeline, config defaults, endpoints HTTP
- `.planning/PROJECT.md` — Vision, constraints (2GB RAM, 1.5 CPU, sin GPU), key decisions
- `.planning/REQUIREMENTS.md` — Requirements CONF-02 a CONF-05, API-06, QUEUE-05
- `CLAUDE.md` — Stack tecnologico con versiones, patterns, anti-patterns (watchdog 6.0.0, PyYAML 6.0.3)

### Contexto de Fase 1
- `.planning/phases/01-pipeline-core-api-basica/01-CONTEXT.md` — Decisiones de Fase 1 (logging structured JSON, fail fast, timeout global)

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `app/config.py` — ConfigManager con reload() ya implementado (sin watchdog). get_snapshot() retorna copia profunda (CONF-06)
- `app/queue.py` — QueueState con active_jobs, queued_jobs, total_processed, total_errors, job_history (deque maxlen=50). JobRecord ya definido. QUEUE-05 parcialmente cubierto
- `app/router_api.py` — `_deep_merge()` ya implementado para override parcial en POST /process. Reutilizable para POST /config
- `app/models.py` — AppConfig (Pydantic v2) con model_dump(). Todas las secciones de config ya modeladas

### Established Patterns
- Pydantic v2 para validacion de config (model_copy, model_dump)
- Structured JSON logging con `json.dumps()` en todos los modulos
- app.state para recursos globales (config_manager, rembg_session, job_queue, startup_time)
- asyncio.to_thread() para CPU-bound work

### Integration Points
- `app/main.py` lifespan: aca se inicializa ConfigManager y rembg session. Watchdog Observer debe arrancar aca
- `app.state.rembg_session`: referencia global que debe poder swapearse (D-02 graceful swap)
- `app.state.config_manager`: ya accesible desde todos los endpoints
- Nuevo router necesario: `router_config.py` para GET/POST /config y GET /status

</code_context>

<specifics>
## Specific Ideas

- JobRecord necesita extenderse con original_size y output_size (D-06). Esto requiere que queue.py reciba esos valores del ProcessingResult
- La whitelist de modelos rembg (D-04) podria extraerse de rembg.sessions o hardcodearse. Verificar que la libreria expone la lista
- El flag de supresion de watchdog (D-07) puede ser un simple threading.Event o un timestamp de ultima escritura con ventana de tolerancia

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope

</deferred>

---

*Phase: 02-observabilidad-config-operacional*
*Context gathered: 2026-03-30*
