# Phase 4: Web UI de Configuracion - Context

**Gathered:** 2026-03-30
**Status:** Ready for planning

<domain>
## Phase Boundary

El operador puede ver el estado del servicio y modificar su configuracion desde un browser, sin tocar la terminal ni editar YAML a mano. La UI es una pagina HTML autocontenida servida por FastAPI (Jinja2 + vanilla JS), sin dependencias externas — CSS y JS inline. Soporta dark mode y es mobile-friendly.

Incluye: GET /ui sirviendo HTML completo, polling de /health cada 5s, formulario de config con todos los campos de AppConfig, guardar (POST /config), restaurar defaults, ver YAML actual, dark mode, responsive.
No incluye: preview de imagenes procesadas (v2 — EXTF-04), test suite (Fase 5).

</domain>

<decisions>
## Implementation Decisions

### Layout y organizacion
- **D-01:** Single page con secciones colapsables. Sin routing ni tabs — una sola pagina HTML con secciones que se colapsan/expanden. Cumple UI-01 (autocontenida) con la minima complejidad.
- **D-02:** Orden de secciones: Status del servicio arriba (lo primero que ve el operador), configuracion abajo agrupada por seccion de AppConfig (rembg, output, padding, autocrop, enhancement, queue).

### Feedback visual
- **D-03:** Toast notifications inline para confirmar cambios exitosos o reportar errores. Implementacion vanilla JS sin dependencias — un div fijo que aparece/desaparece con timeout.
- **D-04:** Banner de warning visible mientras el servicio esta en model swap (model_swapping=true en /health). Polling de /health detecta inicio y fin del swap. Alineado con D-01 de Fase 2 (503 durante swap).

### Controles de configuracion
- **D-05:** Mapeo de controles 1:1 con AppConfig:
  - `rembg.model`: Dropdown con opciones de la whitelist de modelos validos (VALID_MODELS de router_config.py)
  - `rembg.alpha_matting`: Toggle (boolean)
  - `rembg.alpha_matting_*`: Number inputs (solo visibles cuando alpha_matting=true)
  - `output.size`: Number input
  - `output.quality`: Slider (1-100) con valor visible
  - `output.background_color`: Color picker HTML5 nativo (convertir hex <-> [R,G,B])
  - `padding.enabled`: Toggle
  - `padding.percent`: Slider (0-50) con valor visible
  - `autocrop.enabled`: Toggle
  - `autocrop.threshold`: Number input
  - `enhancement.brightness`: Slider (0.1-3.0, step 0.1)
  - `enhancement.contrast`: Slider (0.1-3.0, step 0.1)
  - `queue.max_concurrent`: Number input
  - `queue.max_queue_size`: Number input
  - `queue.timeout_seconds`: Number input
- **D-06:** Boton "Restaurar defaults" carga los defaults de AppConfig() y los aplica via POST /config. Boton "Ver YAML" muestra el contenido raw del YAML en un modal/seccion expandible.

### Estado en tiempo real
- **D-07:** Card de status en la parte superior con: indicador verde/rojo (activo/inactivo), cantidad de jobs en cola, modelo activo, uptime. Polling via fetch() a /health cada 5 segundos (UI-02).
- **D-08:** Tabla compacta de ultimos 10 jobs debajo del status card. Datos de GET /status. Columnas: article_id, status (con badge coloreado), processing_time_ms, timestamp. Se actualiza con cada polling.

### Tecnologia frontend
- **D-09:** Fuente Inter (cargada via CDN Google Fonts como unica dependencia externa aceptada, con fallback a system-ui). Iconos Lucide via CDN. Usar skill frontend-design para todo el maquetado.
- **D-10:** Dark mode via `prefers-color-scheme: dark` con CSS custom properties. Mobile-friendly con CSS responsive (media queries, no framework).

### Claude's Discretion
- Paleta de colores especifica (dentro del estilo que elija frontend-design)
- Animaciones y transiciones de las secciones colapsables
- Disposicion exacta de los controles dentro de cada seccion (grid, flexbox)
- Estilo visual de los toasts y el banner de warning

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Especificacion del proyecto
- `PRD-image-standardizer-v2.md` — PRD completo con definicion de Web UI (seccion correspondiente)
- `.planning/PROJECT.md` — Vision, constraints, key decision "Web UI vanilla sin frameworks JS"
- `.planning/REQUIREMENTS.md` — Requirements UI-01 a UI-05
- `CLAUDE.md` — Stack tecnologico (Jinja2 3.1.6, FastAPI 0.135.2)

### Modelo de datos y APIs existentes
- `app/models.py` — AppConfig completo con todas las secciones y defaults. La UI mapea 1:1 con este modelo
- `app/router_config.py` — GET/POST /config y GET /status. La UI consume estos endpoints directamente
- `app/router_api.py` — GET /health. La UI pollea este endpoint cada 5s

### Contexto de fases anteriores
- `.planning/phases/01-pipeline-core-api-basica/01-CONTEXT.md` — Logging structured JSON (D-03/D-04)
- `.planning/phases/02-observabilidad-config-operacional/02-CONTEXT.md` — D-01 (503 durante swap), D-02 (graceful swap), D-03 (validacion estricta POST /config), D-04 (whitelist modelos)

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `app/router_config.py:VALID_MODELS` — frozenset con modelos validos. La UI puede hardcodear esta lista o consultar un endpoint (VALID_MODELS ya esta disponible en el modulo)
- `app/router_config.py:get_config()` — GET /config retorna AppConfig.model_dump(). La UI lo usa para popular el formulario al cargar
- `app/router_config.py:update_config()` — POST /config acepta JSON parcial con deep merge. La UI envia solo los campos modificados
- `app/router_config.py:status_endpoint()` — GET /status retorna metricas + historial de jobs
- `app/router_api.py:health_check()` — GET /health retorna status, modelo, uptime, cola
- `app/models.py:AppConfig` — Modelo Pydantic v2 con todos los campos y defaults

### Established Patterns
- FastAPI routers en archivos separados (router_api.py, router_config.py). La UI necesita un nuevo router o endpoint en main.py
- Structured JSON logging en todos los modulos
- app.state para recursos globales (config_manager, rembg_session, job_queue)

### Integration Points
- `app/main.py` — Registrar el endpoint GET /ui y configurar Jinja2 templates
- `app/templates/` — Directorio nuevo para el template HTML (o inline en el router)
- Jinja2 ya es dependencia de FastAPI — no agrega peso al requirements

</code_context>

<specifics>
## Specific Ideas

- El formulario carga valores actuales via GET /config al abrir la pagina y al hacer polling
- POST /config envia solo el JSON de la seccion modificada (deep merge en el backend ya funciona)
- La whitelist de modelos rembg puede exponerse como un mini-endpoint o embedirse en el template Jinja2
- Inter como fuente (decision explicita del usuario) y Lucide para iconos
- Usar el skill frontend-design para todo el trabajo de UI (decision explicita del usuario)

</specifics>

<deferred>
## Deferred Ideas

- **Preview de imagen procesada en la UI** — EXTF-04 en v2 requirements. No pertenece a esta fase.

</deferred>

---

*Phase: 04-web-ui-de-configuracion*
*Context gathered: 2026-03-30*
