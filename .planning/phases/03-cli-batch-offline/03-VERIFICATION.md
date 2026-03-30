---
phase: 03-cli-batch-offline
verified: 2026-03-30T20:00:00Z
status: passed
score: 7/7 must-haves verified
re_verification: false
---

# Phase 03: CLI + Batch Offline — Verification Report

**Phase Goal:** El operador puede procesar imagenes individuales o carpetas completas desde la terminal sin levantar el servidor HTTP, reutilizando el mismo pipeline ya probado
**Verified:** 2026-03-30T20:00:00Z
**Status:** passed
**Re-verification:** No — initial verification

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | `imgproc process foto.jpg` produce un WebP en el directorio de salida | VERIFIED | `test_process_command` + `test_process_creates_output_dir` pasan; cli.py llama `process_image()` y escribe `{stem}.webp` |
| 2 | `imgproc batch ./fotos/` procesa todos los archivos soportados y genera reporte CSV | VERIFIED | `test_batch_command` + `test_batch_report_csv` pasan; CSV con columnas correctas verificado |
| 3 | `imgproc serve` arranca Uvicorn con host/port/log_level de la config | VERIFIED | `test_serve_command` pasa; cli.py linea 234-239: `uvicorn.run("app.main:app", host=cfg.server.host, port=cfg.server.port, log_level=cfg.server.log_level)` |
| 4 | `imgproc config show` muestra el YAML de settings.yaml | VERIFIED | `test_config_show` pasa; cli.py linea 253: `typer.echo(path.read_text())` cuando el archivo existe |
| 5 | `imgproc config set output.quality 95` persiste el cambio en disco | VERIFIED | `test_config_set_valid` pasa; AppConfig(**merged) coerce "95" a int 95, `update_config()` llamado |
| 6 | El CLI no duplica logica de pipeline — llama `process_image()` directo | VERIFIED | app/cli.py linea 24: `from app.processor import ProcessingError, process_image`; usado directamente en process y batch sin reimplementar pipeline |
| 7 | rembg se inicializa lazy solo para process y batch, no para serve ni config | VERIFIED | `import rembg` solo en la funcion `_get_rembg_session()` (linea 51, dentro de la funcion); modulo-level `_rembg_session = None`; serve y config no llaman `_get_rembg_session()` |

**Score:** 7/7 truths verified

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `app/cli.py` | CLI Typer app con todos los subcomandos | VERIFIED | 288 lineas (>=150). Contiene process, batch, serve, config_show, config_set, _get_rembg_session, _dotpath_to_nested, _deep_merge, _escribir_reporte, EXTENSIONES_SOPORTADAS |
| `tests/test_cli.py` | Tests unitarios para todos los comandos CLI | VERIFIED | 344 lineas (>=100). 15 tests cubren todos los subcomandos |
| `pyproject.toml` | Entry point `imgproc = "app.cli:app"` | VERIFIED | Seccion `[project.scripts]` presente con `imgproc = "app.cli:app"` |

### Key Link Verification

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| `app/cli.py` | `app/processor.py` | `from app.processor import ProcessingError, process_image` | WIRED | Import presente en linea 24; `process_image()` invocado en comandos process (linea 129) y batch (linea 202) |
| `app/cli.py` | `app/config.py` | `from app.config import ConfigManager` | WIRED | Import presente en linea 22; `ConfigManager()` instanciado en process, batch, serve, config_show, config_set |
| `app/cli.py` | `app/models.py` | `from app.models import AppConfig` | WIRED | Import presente en linea 23; `AppConfig(**merged)` usado en config_set para validacion Pydantic |
| `tests/test_cli.py` | `app/cli.py` | `from app.cli import app` + CliRunner | WIRED | Import presente en linea 13; CliRunner invocado en todos los 15 tests |

### Data-Flow Trace (Level 4)

| Artifact | Data Variable | Source | Produces Real Data | Status |
|----------|---------------|--------|--------------------|--------|
| `app/cli.py process()` | `result.image_bytes` | `process_image(image_bytes, article_id, config, session)` | Si — llama el pipeline real de app/processor.py | FLOWING |
| `app/cli.py batch()` | `rows` (reporte CSV) | `process_image()` por cada archivo; `row["status"]`, `row["processing_time_ms"]` de `result` | Si — datos reales del pipeline | FLOWING |
| `app/cli.py config_show()` | contenido YAML | `path.read_text()` del archivo `settings.yaml` real | Si — lee el archivo en disco | FLOWING |

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| CLI importa sin errores | `.venv/bin/python -c "from app.cli import app; print(type(app))"` | `<class 'typer.main.Typer'>` | PASS |
| 15 tests CLI pasan | `.venv/bin/pytest tests/test_cli.py -x` | `15 passed in 2.26s` | PASS |
| Suite completa no regresiona | `.venv/bin/pytest tests/ -x` | `83 passed in 15.01s` | PASS |
| Entry point registrado en pyproject.toml | `grep 'imgproc = "app.cli:app"' pyproject.toml` | Match encontrado | PASS |
| rembg NO importado a nivel de modulo | Inspeccion AST de linea 51 | `import rembg` solo dentro de `_get_rembg_session()` (funcion, no modulo) | PASS |

### Requirements Coverage

| Requirement | Descripcion | Estado | Evidencia |
|-------------|-------------|--------|-----------|
| CLI-01 | Comando `process` procesa imagen individual usando processor directamente (sin HTTP) | SATISFIED | `app/cli.py`: `process()` llama `process_image()` directamente; `test_process_command` verifica exit 0 y creacion de WebP |
| CLI-02 | Comando `batch` procesa directorio completo secuencialmente con reporte CSV opcional | SATISFIED | `app/cli.py`: `batch()` itera archivos con `EXTENSIONES_SOPORTADAS`, genera CSV via `_escribir_reporte()`; `test_batch_report_csv` verifica columnas correctas |
| CLI-03 | Comando `serve` inicia el servidor HTTP (Uvicorn) | SATISFIED | `app/cli.py`: `serve()` llama `uvicorn.run("app.main:app", ...)` con parametros de `cfg.server`; `test_serve_command` verifica los parametros |
| CLI-04 | Comando `config show` muestra configuracion activa y `config set` modifica valores | SATISFIED | `app/cli.py`: `config_show()` lee settings.yaml; `config_set()` usa dotpath + deep_merge + Pydantic validation; tests verifican ambos |
| CLI-05 | CLI reutiliza el processor directamente, sin duplicar logica | SATISFIED | Importa y llama `process_image()` de `app.processor`; no hay reimplementacion del pipeline en cli.py |

**Requisitos orphaned (mapeados a Phase 3 en REQUIREMENTS.md pero no declarados en PLAN):** Ninguno. Los 5 requisitos CLI-01 a CLI-05 estan declarados en el PLAN y cubiertos.

### Anti-Patterns Found

| File | Linea | Pattern | Severidad | Impacto |
|------|-------|---------|-----------|---------|
| Ninguno | — | — | — | — |

No se encontraron TODOs, FIXMEs, placeholders, returns vacios, ni implementaciones stub en los archivos de la fase.

### Human Verification Required

No hay items que requieran verificacion humana. Todos los comportamientos CLI son verificables programaticamente via CliRunner y las pruebas cubren todos los paths de exito y error.

Si se desea verificar la experiencia de terminal real (colores Rich, barra de progreso en batch, output formateado), puede ejecutarse manualmente:

1. `pip install -e . && imgproc --help` — verifica que el entry point funcione en PATH
2. `imgproc config show` — verifica que muestre el YAML de settings.yaml del proyecto
3. `imgproc process <imagen.jpg> -o /tmp/test_output` — verifica pipeline real (requiere modelo rembg descargado, ~300MB)

### Gaps Summary

No hay gaps. Todos los must-haves estan verificados. La fase alcanzo su objetivo completo.

---

## Resumen de Verificacion

La fase 03 alcanzo su objetivo: el operador puede procesar imagenes individuales (`imgproc process`) o carpetas completas (`imgproc batch`) desde la terminal sin levantar el servidor HTTP. El CLI reutiliza `process_image()` directamente de `app/processor.py` sin duplicar logica. La sesion rembg se inicializa en forma lazy (solo cuando se invoca process o batch). Los comandos serve y config no cargan el modelo ONNX. Todos los 15 tests CLI pasan, y los 83 tests de la suite completa siguen en verde sin regresiones.

---

_Verified: 2026-03-30T20:00:00Z_
_Verifier: Claude (gsd-verifier)_
