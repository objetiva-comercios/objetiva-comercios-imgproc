---
phase: 03-cli-batch-offline
plan: 01
subsystem: cli
tags: [typer, rich, cli, batch, csv, rembg, lazy-init]

requires:
  - phase: 01-pipeline-core-api-basica
    provides: process_image() sincrona, ProcessingError, AppConfig, ProcessingResult
  - phase: 02-observabilidad-config-operacional
    provides: ConfigManager con update_config, config property, get_snapshot

provides:
  - CLI Typer completo con comandos process, batch, serve, config show, config set
  - Lazy init de sesion rembg a nivel modulo (_rembg_session global)
  - Reporte CSV para batch con columnas definidas en D-05
  - Entry point imgproc registrado en pyproject.toml
  - 15 tests unitarios CLI con CliRunner cubriendo CLI-01 a CLI-04

affects:
  - fase-04-web-ui (usa misma CLI para serve)
  - dockerfile (entry point imgproc ya disponible)
  - docs (imgproc como herramienta del operador)

tech-stack:
  added: []
  patterns:
    - "Typer sub-app: config_app registrada con app.add_typer(config_app, name='config') despues de definir sus comandos"
    - "Lazy rembg init: _rembg_session = None a nivel de modulo, cargado solo para process y batch"
    - "Batch continue-on-error: ProcessingError capturada por archivo, status ok/error en CSV"
    - "dotpath config mutation: _dotpath_to_nested + _deep_merge + AppConfig(**merged) para validacion Pydantic"
    - "CliRunner mock pattern: patch app.cli.process_image y app.cli._get_rembg_session en todos los tests CLI"

key-files:
  created:
    - app/cli.py
    - tests/test_cli.py
  modified:
    - pyproject.toml

key-decisions:
  - "CLI llama process_image() directamente sincrono (D-11): no hay event loop en CLI, to_thread seria overhead innecesario"
  - "Lazy init de rembg (D-01): _get_rembg_session() usa global _rembg_session — serve y config no pagan costo de 5-15s de carga del modelo"
  - "Batch secuencial sin paralelismo (D-12): VPS con 1.5 CPU y 2GB RAM, < 100 imgs/dia no justifica concurrencia"
  - "article_id para process derivado del stem del archivo si no se provee via --article-id (Claude's Discretion)"

patterns-established:
  - "Pattern CLI-TDD: CliRunner + patch app.cli.X para aislar comandos de dependencias pesadas (rembg, uvicorn)"
  - "Pattern batch continue-on-error: try/except ProcessingError + except Exception dentro del loop, nunca fail-fast"

requirements-completed: [CLI-01, CLI-02, CLI-03, CLI-04, CLI-05]

duration: 15min
completed: 2026-03-30
---

# Phase 03 Plan 01: CLI + Batch Offline Summary

**CLI Typer completo con process/batch/serve/config usando lazy init de rembg y reporte CSV batch**

## Performance

- **Duration:** ~15 min
- **Started:** 2026-03-30T19:21:00Z
- **Completed:** 2026-03-30T19:36:00Z
- **Tasks:** 2 (TDD: RED + GREEN)
- **Files modified:** 3

## Accomplishments

- Implementado app/cli.py con 5 subcomandos Typer: process, batch, serve, config show, config set
- 15 tests unitarios con CliRunner cubren CLI-01 a CLI-04, todos pasan en verde
- Suite completa de 83 tests sigue verde tras la implementacion
- Entry point `imgproc = "app.cli:app"` registrado en pyproject.toml

## Task Commits

1. **Task 1: Tests CLI (RED phase)** - `76c450c` (test)
2. **Task 2: app/cli.py + pyproject.toml (GREEN phase)** - `9524481` (feat)

## Files Created/Modified

- `app/cli.py` — CLI Typer con todos los subcomandos (220 lineas)
- `tests/test_cli.py` — 15 tests con CliRunner + mocks (344 lineas)
- `pyproject.toml` — Seccion [project.scripts] con entry point imgproc

## Decisions Made

- Lazy init de rembg via `_rembg_session = None` modulo-level + `_get_rembg_session()`: evita que `serve` y `config` paguen el costo de carga del modelo ONNX (5-15s)
- CLI llama `process_image()` directamente sin asyncio — correcto para context CLI sincrono (D-11)
- Batch continua ante errores individuales (no fail-fast): registra status "error" en CSV y sigue con el siguiente archivo (D-12)
- `article_id` derivado de `image.stem` cuando no se provee `--article-id` (Claude's Discretion segun D-10)

## Deviations from Plan

None - plan ejecutado exactamente como especificado.

## Issues Encountered

None.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- CLI completo y testeado, listo para uso del operador
- `imgproc process`, `imgproc batch`, `imgproc serve`, `imgproc config show/set` disponibles
- Pendiente `pip install -e .` en el container Docker para que el entry point sea accesible en PATH
- Fase 04 (Web UI) puede usar el serve command directamente

---
*Phase: 03-cli-batch-offline*
*Completed: 2026-03-30*
