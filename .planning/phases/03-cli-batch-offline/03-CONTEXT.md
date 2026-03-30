# Phase 3: CLI + Batch Offline - Context

**Gathered:** 2026-03-30
**Status:** Ready for planning

<domain>
## Phase Boundary

El operador puede procesar imágenes individuales o directorios completos desde la terminal sin levantar el servidor HTTP, reutilizando el mismo pipeline ya probado en Fase 1. Incluye: comandos `process` (imagen individual), `batch` (directorio completo con reporte CSV), `serve` (iniciar servidor HTTP), `config show` y `config set` (gestionar configuración). Todo via Typer.

No incluye: Web UI (Fase 4), test suite (Fase 5), procesamiento batch via API (v2).

</domain>

<decisions>
## Implementation Decisions

### Inicialización de rembg en CLI
- **D-01:** Lazy init del modelo rembg — cargar sesión solo cuando `process` o `batch` lo necesitan. Los subcomandos `serve`, `config show`, `config set` NO cargan el modelo (ahorra 5-15s de startup innecesario).
- **D-02:** El CLI instancia ConfigManager directamente con el mismo path default (`config/settings.yaml`), reutilizando la misma clase que el server.

### Output path convention
- **D-03:** Flag `--output` / `-o` para especificar directorio de salida. Default: `./output/` relativo al directorio de trabajo actual. Crear el directorio si no existe.
- **D-04:** Nombre de archivo de salida: mismo nombre que el original pero con extensión `.webp`. Si ya existe, sobreescribir sin preguntar (procesamiento idempotente).

### Reporte de batch
- **D-05:** Reporte CSV con columnas: `article_id, input_path, output_path, status, processing_time_ms, error`. Generado al final del batch con flag `--report` / `-r` que acepta path del CSV.
- **D-06:** Progress reporting con Rich progress bar (Typer integra Rich natively). Mostrar: imagen actual, progreso N/total, tiempo promedio por imagen.

### Config CLI UX
- **D-07:** `config show` muestra el YAML tal cual está en disco (formato canónico, sin traducción).
- **D-08:** `config set` usa dotpath notation: `imgproc config set output.quality 95`. Parsear el path, deep merge sobre config actual, validar con Pydantic, persistir YAML.

### Estructura de comandos Typer
- **D-09:** App principal `imgproc` con subcomandos: `process`, `batch`, `serve`, `config`. `config` es un sub-app de Typer con `show` y `set`.
- **D-10:** Entry point via `app/cli.py` con `if __name__ == "__main__": app()`. Registrar en pyproject.toml como script `imgproc`.

### Reutilización del processor (CLI-05)
- **D-11:** El CLI llama `process_image()` directamente (síncrono, sin asyncio.to_thread). No hay event loop en el CLI — la función ya es síncrona por diseño.
- **D-12:** Para `batch`, iterar archivos secuencialmente (sin paralelismo). El VPS tiene 1.5 CPU y 2GB RAM — no hay beneficio real en paralelizar rembg que ya usa todos los threads disponibles.

### Claude's Discretion
- Formato exacto de los mensajes de consola (colores, emojis, layout) — adaptar según lo que Typer/Rich ofrezcan nativamente.
- article_id para `process`: derivar del nombre del archivo sin extensión si no se provee via flag.
- article_id para `batch`: derivar del nombre de cada archivo sin extensión.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Especificación del proyecto
- `PRD-image-standardizer-v2.md` — PRD completo con estructura de proyecto y definición de CLI commands
- `.planning/PROJECT.md` — Vision, constraints (2GB RAM, 1.5 CPU, sin GPU)
- `.planning/REQUIREMENTS.md` — Requirements CLI-01 a CLI-05
- `CLAUDE.md` — Stack tecnológico (Typer 0.24.1), patterns, anti-patterns

### Código existente a reutilizar
- `app/processor.py` — `process_image()` síncrona, firma: `(image_bytes, article_id, config, rembg_session) -> ProcessingResult`
- `app/config.py` — `ConfigManager` con `reload()`, `get_snapshot()`, `update_config()`
- `app/models.py` — `AppConfig` (Pydantic v2), `ProcessingResult`

### Contexto de fases anteriores
- `.planning/phases/01-pipeline-core-api-basica/01-CONTEXT.md` — Decisiones de pipeline (D-05 límite megapixels, D-06 skip rembg transparente, D-09 fail fast)
- `.planning/phases/02-observabilidad-config-operacional/02-CONTEXT.md` — Decisiones de config (D-03 validación estricta, D-04 whitelist modelos)

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `app/processor.py:process_image()` — Pipeline completo síncrono. El CLI lo llama directo sin event loop.
- `app/config.py:ConfigManager` — Instanciable con path custom. Ya tiene `update_config()` para persistir YAML.
- `app/models.py:AppConfig` — Validación Pydantic v2. `model_dump()` para serializar config.
- `rembg.new_session()` — Inicialización del modelo. Misma función usada en `app/main.py` lifespan.

### Established Patterns
- Structured JSON logging con `json.dumps()` — el CLI puede usar logging normal (no JSON) ya que es interactivo
- `process_image()` es síncrona — llamada directa sin wrappear en asyncio
- ConfigManager path default: `config/settings.yaml`

### Integration Points
- `app/cli.py` — nuevo archivo, entry point del CLI
- `app/main.py` — el comando `serve` puede importar `app` y correr `uvicorn.run(app, ...)`
- No hay punto de integración con el queue (JobQueue) — el CLI no usa cola, procesa directo

</code_context>

<specifics>
## Specific Ideas

- El comando `serve` es un wrapper thin sobre uvicorn: `uvicorn.run("app.main:app", host=..., port=..., log_level=...)`
- Batch procesa todos los archivos con extensiones soportadas en el directorio (jpg, jpeg, png, webp, bmp, tiff)
- Si process_image falla para un archivo en batch, registrar error en el reporte y continuar con el siguiente (no fail-fast como en API)

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope

</deferred>

---

*Phase: 03-cli-batch-offline*
*Context gathered: 2026-03-30*
