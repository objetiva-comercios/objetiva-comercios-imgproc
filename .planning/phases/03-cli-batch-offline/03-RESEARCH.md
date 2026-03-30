# Phase 03: CLI + Batch Offline - Research

**Researched:** 2026-03-30
**Domain:** CLI tools con Typer, batch file processing, CSV reporting, config management via dotpath
**Confidence:** HIGH

## Summary

Esta fase agrega una interfaz de línea de comandos completa (`imgproc`) sobre el pipeline ya existente en `app/processor.py`. El objetivo es que el operador pueda procesar imágenes individuales o directorios completos sin levantar el servidor HTTP, reutilizando exactamente el mismo código de pipeline. La implementación es directa porque todos los componentes ya están probados en fases anteriores.

La clave de esta fase es la **reutilización sin duplicación**: el CLI importa `process_image()`, `ConfigManager` y `AppConfig` directamente. No hay lógica de pipeline en `cli.py`. El único trabajo nuevo es el scaffolding CLI (Typer sub-apps, progress reporting con Rich, CSV report, dotpath config mutation).

El stack está completamente disponible en el entorno: Typer 0.24.1 instalado, Rich 13.7.1 disponible como dependencia de Typer, uvicorn 0.42.0 con API programática funcional. No hay dependencias nuevas que agregar a requirements.txt.

**Primary recommendation:** Implementar `app/cli.py` con Typer app + config sub-app, lazy-init de rembg, y reutilización directa de `process_image()` síncrona. Registrar entry point en `pyproject.toml`.

---

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
- **D-01:** Lazy init del modelo rembg — cargar sesión solo cuando `process` o `batch` lo necesitan. Los subcomandos `serve`, `config show`, `config set` NO cargan el modelo.
- **D-02:** El CLI instancia ConfigManager directamente con el mismo path default (`config/settings.yaml`), reutilizando la misma clase que el server.
- **D-03:** Flag `--output` / `-o` para directorio de salida. Default: `./output/` relativo al CWD. Crear si no existe.
- **D-04:** Nombre de archivo: mismo nombre que el original con extensión `.webp`. Si existe, sobreescribir sin preguntar.
- **D-05:** Reporte CSV con columnas: `article_id, input_path, output_path, status, processing_time_ms, error`. Flag `--report` / `-r` que acepta path del CSV.
- **D-06:** Progress reporting con Rich progress bar (nativo en Typer). Mostrar: imagen actual, progreso N/total, tiempo promedio.
- **D-07:** `config show` muestra el YAML tal cual está en disco (formato canónico).
- **D-08:** `config set` usa dotpath notation (`imgproc config set output.quality 95`). Parsear path, deep merge sobre config actual, validar con Pydantic, persistir YAML.
- **D-09:** App principal `imgproc` con subcomandos: `process`, `batch`, `serve`, `config`. `config` es un sub-app de Typer con `show` y `set`.
- **D-10:** Entry point via `app/cli.py` con `if __name__ == "__main__": app()`. Registrar en `pyproject.toml` como script `imgproc`.
- **D-11:** El CLI llama `process_image()` directamente (síncrono, sin asyncio.to_thread). No hay event loop en el CLI.
- **D-12:** Para `batch`, iterar archivos secuencialmente. Sin paralelismo — VPS con 1.5 CPU y 2GB RAM.

### Claude's Discretion
- Formato exacto de los mensajes de consola (colores, emojis, layout) — adaptar según lo que Typer/Rich ofrezcan nativamente.
- `article_id` para `process`: derivar del nombre del archivo sin extensión si no se provee via flag.
- `article_id` para `batch`: derivar del nombre de cada archivo sin extensión.

### Deferred Ideas (OUT OF SCOPE)
- Web UI (Fase 4)
- Test suite (Fase 5)
- Procesamiento batch via API (v2)
</user_constraints>

---

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| CLI-01 | Comando `process` procesa una imagen individual usando el processor directamente (sin HTTP) | `process_image()` es síncrona, llamada directa. `rembg.new_session()` en lazy-init. Typer Argument con `exists=True` valida el archivo. |
| CLI-02 | Comando `batch` procesa un directorio completo secuencialmente con reporte CSV opcional | `csv.DictWriter` con columnas definidas en D-05. Rich Progress para display. Iteración con `Path.glob()` sobre extensiones soportadas. |
| CLI-03 | Comando `serve` inicia el servidor HTTP (Uvicorn) | `uvicorn.run("app.main:app", host=..., port=..., log_level=...)` — API programática disponible. Leer host/port/log_level desde ConfigManager. |
| CLI-04 | Comando `config show` muestra la configuración activa y `config set` modifica valores | `show`: leer y mostrar YAML en disco con `typer.echo()`. `set`: dotpath → nested dict → deep merge → Pydantic validation → `ConfigManager.update_config()`. |
| CLI-05 | El CLI reutiliza el processor directamente, sin duplicar lógica | `from app.processor import process_image` — llamada directa síncrona, sin asyncio. Misma firma: `(image_bytes, article_id, config, rembg_session)`. |
</phase_requirements>

---

## Standard Stack

### Core (ya instalado)
| Library | Version | Purpose | Por qué estándar |
|---------|---------|---------|-----------------|
| Typer | 0.24.1 | Framework CLI — sub-apps, args/options, help automático | Elegido en CLAUDE.md. Instalado. API verificada. |
| Rich | 13.7.1 | Progress bar, colores, consola — dependencia de Typer | Instalado como dep de Typer. `from rich.progress import Progress` funciona. |
| uvicorn | 0.42.0 | API programática para `serve` command | Instalado. `uvicorn.run()` acepta host/port/log_level. |
| csv (stdlib) | Python stdlib | Generar reporte CSV para batch | No requiere instalación. `csv.DictWriter` verificado. |
| pathlib (stdlib) | Python stdlib | File/dir traversal en batch | Nativo. `Path.glob()` para filtrar extensiones. |

### Sin dependencias nuevas
Esta fase no requiere agregar nada a `requirements.txt`. Todo está disponible.

**Verificación de entorno:**
```bash
python3 -c "import typer, rich, uvicorn, csv, pathlib; print('OK')"
# Output: OK
```

## Architecture Patterns

### Estructura de archivos nueva
```
app/
├── cli.py        # NUEVO — app Typer principal + sub-app config
processor.py      # REUTILIZAR — process_image() síncrona
config.py         # REUTILIZAR — ConfigManager con update_config()
models.py         # REUTILIZAR — AppConfig, ProcessingResult
main.py           # REUTILIZAR — para serve command (import uvicorn + app)
```

### Pattern 1: Typer App con Sub-App de config

```python
# app/cli.py
import typer

app = typer.Typer(name="imgproc", help="Image Standardizer CLI")
config_app = typer.Typer(help="Gestionar configuración")
app.add_typer(config_app, name="config")

@app.command()
def process(...): ...

@app.command()
def batch(...): ...

@app.command()
def serve(...): ...

@config_app.command("show")
def config_show(): ...

@config_app.command("set")
def config_set(key: str, value: str): ...

if __name__ == "__main__":
    app()
```

**Verificado:** `CliRunner` de Typer puede invocar `app ['config', 'show']` y `app ['config', 'set', 'output.quality', '95']` — exit code 0 en ambos casos.

### Pattern 2: Lazy Init de rembg (D-01)

```python
# Variable módulo-nivel — None hasta que se necesita
_rembg_session = None

def _get_rembg_session(model: str):
    global _rembg_session
    if _rembg_session is None:
        typer.echo(f"Cargando modelo {model}...")
        import rembg
        _rembg_session = rembg.new_session(model)
    return _rembg_session
```

**Por qué lazy:** `serve` y `config` no deben pagar el costo de 5-15s de inicialización del modelo ONNX. Solo `process` y `batch` lo necesitan.

### Pattern 3: Typer Argument con validación de archivo

```python
from pathlib import Path
import typer

@app.command()
def process(
    image: Path = typer.Argument(..., help="Imagen a procesar", exists=True),
    output: Path = typer.Option(Path("./output"), "-o", "--output", help="Directorio de salida"),
    article_id: str = typer.Option("", "--article-id", help="ID del artículo (default: nombre de archivo)"),
):
    ...
```

**Verificado:** `exists=True` produce error Rich automático con exit code 2 si el archivo no existe. No requiere validación manual.

### Pattern 4: Batch con Rich Progress

```python
from rich.progress import Progress, BarColumn, TextColumn, TimeElapsedColumn, MofNCompleteColumn

def batch(...):
    archivos = [f for f in Path(directory).iterdir() if f.suffix.lower() in EXTENSIONES]

    with Progress(
        TextColumn("[bold blue]{task.fields[filename]}", justify="right"),
        BarColumn(),
        MofNCompleteColumn(),
        TimeElapsedColumn(),
    ) as progress:
        task = progress.add_task("Procesando", total=len(archivos), filename="")
        for archivo in archivos:
            progress.update(task, filename=archivo.name)
            # procesar...
            progress.advance(task)
```

**Verificado:** `MofNCompleteColumn`, `BarColumn`, `TimeElapsedColumn`, `TextColumn` importan sin error desde `rich.progress`.

### Pattern 5: CSV Report con csv.DictWriter

```python
import csv
from pathlib import Path
from typing import Optional

def _escribir_reporte(rows: list[dict], report_path: Path) -> None:
    """Escribe el reporte CSV al finalizar el batch."""
    fieldnames = ["article_id", "input_path", "output_path", "status", "processing_time_ms", "error"]
    with open(report_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
```

**Verificado:** `csv.DictWriter` con estas columnas produce CSV correcto.

### Pattern 6: config set con dotpath + deep merge + Pydantic

```python
def _dotpath_to_nested(path: str, value: str) -> dict:
    """Convierte 'output.quality' + '95' a {'output': {'quality': '95'}}"""
    keys = path.split(".")
    result: dict = value
    for k in reversed(keys):
        result = {k: result}
    return result

def _deep_merge(base: dict, override: dict) -> dict:
    merged = base.copy()
    for k, v in override.items():
        if k in merged and isinstance(merged[k], dict) and isinstance(v, dict):
            merged[k] = _deep_merge(merged[k], v)
        else:
            merged[k] = v
    return merged

@config_app.command("set")
def config_set(key: str = typer.Argument(...), value: str = typer.Argument(...)):
    cfg_manager = ConfigManager()
    current = cfg_manager.config.model_dump()
    override = _dotpath_to_nested(key, value)
    merged = _deep_merge(current, override)
    try:
        new_config = AppConfig(**merged)  # Pydantic valida + coerce tipos
    except Exception as e:
        typer.secho(f"Error: valor inválido — {e}", fg=typer.colors.RED, err=True)
        raise typer.Exit(1)
    cfg_manager.update_config(new_config)
    typer.secho(f"✓ {key} = {value}", fg=typer.colors.GREEN)
```

**Verificado:** Pydantic v2 hace coerción de string `"95"` a `int 95` para campos `int`. Deep merge preserva todos los otros campos.

### Pattern 7: serve command

```python
@app.command()
def serve():
    """Inicia el servidor HTTP con Uvicorn."""
    cfg = ConfigManager().config
    import uvicorn
    uvicorn.run(
        "app.main:app",
        host=cfg.server.host,
        port=cfg.server.port,
        log_level=cfg.server.log_level,
    )
```

**Verificado:** `uvicorn.run()` tiene parámetros `host`, `port`, `log_level`. Versión 0.42.0 instalada.

### Pattern 8: pyproject.toml entry point

```toml
[project.scripts]
imgproc = "app.cli:app"
```

Requiere `pip install -e .` para que `imgproc` sea disponible en PATH. Dentro del container Docker, se debe agregar al Dockerfile o al script de startup.

### Anti-Patterns a Evitar

- **asyncio en el CLI:** `process_image()` es síncrona — llamar directo. Envolver en `asyncio.run()` agrega overhead sin beneficio.
- **Importar rembg a nivel de módulo en cli.py:** Causa que todos los subcomandos (incluido `serve` y `config`) carguen el modelo al importar el módulo. Usar lazy init (Pattern 2).
- **Crear nueva ConfigManager por cada archivo en batch:** Instanciar una vez al inicio del comando, reutilizar el snapshot.
- **fail-fast en batch:** A diferencia de la API, el batch debe continuar ante errores individuales — registrar en CSV y seguir.
- **Usar `asyncio.to_thread()` en CLI:** El event loop no existe en el contexto del CLI. `process_image()` bloquea el thread principal, lo cual es correcto para un CLI.

## Don't Hand-Roll

| Problema | No construir | Usar en cambio | Por qué |
|----------|-------------|----------------|---------|
| Progress bar en terminal | Loop con `print(f"{n}/{total}")` | `rich.progress.Progress` | Maneja ANSI, redraw, ETA, columnas customizables |
| Validación de archivo existente | `if not path.exists(): sys.exit(1)` | `typer.Argument(..., exists=True)` | Typer produce error Rich formateado automáticamente |
| Help text y --help flag | Argparse manual | Typer decorators | Typer genera help de docstrings y type hints |
| CSV writing con escaping correcto | `f.write(f"{a},{b},{c}\n")` | `csv.DictWriter` | DictWriter maneja comas, comillas, newlines en valores |
| Type coercion de strings en config | `int(value)` manual | `AppConfig(**merged)` Pydantic | Pydantic coerce y valida con mensajes de error claros |

## Common Pitfalls

### Pitfall 1: Working directory vs config path
**Qué falla:** El ConfigManager usa path relativo `config/settings.yaml`. Si el operador corre `imgproc` desde un directorio distinto al root del proyecto, el archivo no se encuentra.
**Por qué ocurre:** `Path("config/settings.yaml")` es relativo al CWD del proceso.
**Cómo evitar:** Usar `Path(__file__).parent.parent / "config" / "settings.yaml"` como default, o documentar que el comando debe correrse desde el root del proyecto. La decisión D-02 acepta el path default relativo — es el comportamiento esperado.
**Señal de advertencia:** `FileNotFoundError` o `ConfigManager` retornando `AppConfig()` con defaults (sin settings.yaml).

### Pitfall 2: rembg session no cargada para batch multi-archivo
**Qué falla:** Si se instancia `rembg_session = None` dentro del loop del batch, cada archivo recarga el modelo.
**Por qué ocurre:** Olvidar que la sesión debe ser compartida entre todos los archivos del batch.
**Cómo evitar:** Inicializar `_get_rembg_session()` una sola vez antes del loop, pasar la misma sesión a todos los `process_image()` calls.

### Pitfall 3: article_id vacío en el report CSV
**Qué falla:** Si `article_id` se deriva del nombre de archivo pero la derivación falla (caracteres especiales, extensión múltiple), el CSV tiene article_id vacío.
**Por qué ocurre:** `Path(filename).stem` maneja `foto.jpg` → `foto` pero `foto.tar.gz` → `foto.tar`.
**Cómo evitar:** Usar `Path(filename).stem` — para imágenes de producto esto es suficiente. Documentar en help que solo se usa el primer stem.

### Pitfall 4: CSV report file ya existe
**Qué falla:** Si el operador re-corre el batch con el mismo `--report` path, el CSV anterior se sobreescribe silenciosamente.
**Por qué ocurre:** `open(report_path, "w")` sobreescribe por diseño (idempotente como D-04 para imágenes).
**Cómo evitar:** Este es el comportamiento correcto según D-04 (idempotente). Documentar en help.

### Pitfall 5: Typer sub-app y el orden de `add_typer`
**Qué falla:** Si `app.add_typer(config_app, name="config")` se llama antes de definir los comandos del `config_app`, Typer registra una app vacía.
**Por qué ocurre:** Python ejecuta el código de módulo en orden.
**Cómo evitar:** Definir todos los comandos de `config_app` antes de llamar a `app.add_typer()`, o definirlos en el mismo módulo sin importaciones circulares.

### Pitfall 6: `exists=True` en Typer Argument para directorio (batch)
**Qué falla:** `typer.Argument(..., exists=True)` valida que el path existe pero no que sea un directorio.
**Por qué ocurre:** Typer valida existencia pero no tipo.
**Cómo evitar:** Agregar validación explícita: `if not directory.is_dir(): raise typer.BadParameter("Debe ser un directorio")`.

### Pitfall 7: output directory no existe
**Qué falla:** `open(output / filename, "wb")` falla con `FileNotFoundError` si `output/` no existe.
**Por qué ocurre:** Python no crea directorios intermedios en `open()`.
**Cómo evitar:** `output.mkdir(parents=True, exist_ok=True)` al inicio del comando (D-03 explícitamente lo requiere).

## Code Examples

### Ejemplo completo: comando process

```python
# Source: Typer docs + verificado en entorno del proyecto
@app.command()
def process(
    image: Path = typer.Argument(..., help="Imagen a procesar (JPG, PNG, WebP, BMP, TIFF)"),
    output: Path = typer.Option(Path("./output"), "-o", "--output", help="Directorio de salida"),
    article_id: str = typer.Option("", "--article-id", "-a", help="ID del artículo (default: nombre del archivo)"),
):
    """Procesa una imagen individual y genera un WebP estandarizado."""
    # Validar que sea archivo
    if not image.is_file():
        typer.secho(f"Error: '{image}' no es un archivo", fg=typer.colors.RED, err=True)
        raise typer.Exit(1)

    # Derivar article_id si no se proveyó (Claude's Discretion)
    if not article_id:
        article_id = image.stem

    # Crear output dir si no existe (D-03)
    output.mkdir(parents=True, exist_ok=True)

    # Cargar config
    cfg_manager = ConfigManager()
    config = cfg_manager.get_snapshot()

    # Lazy init rembg (D-01)
    session = _get_rembg_session(config.rembg.model)

    # Leer bytes
    image_bytes = image.read_bytes()

    # Llamar pipeline síncrono directo (D-11, CLI-05)
    try:
        result = process_image(image_bytes, article_id, config, session)
    except ProcessingError as e:
        typer.secho(f"Error [{e.step}]: {e.detail}", fg=typer.colors.RED, err=True)
        raise typer.Exit(1)

    # Guardar output (D-04: sobreescribir si existe)
    output_path = output / f"{image.stem}.webp"
    output_path.write_bytes(result.image_bytes)

    typer.secho(
        f"✓ {article_id}: {result.processing_time_ms}ms → {output_path}",
        fg=typer.colors.GREEN,
    )
```

### Ejemplo completo: batch con Rich Progress

```python
EXTENSIONES_SOPORTADAS = {".jpg", ".jpeg", ".png", ".webp", ".bmp", ".tiff", ".tif"}

@app.command()
def batch(
    directory: Path = typer.Argument(..., help="Directorio con imágenes a procesar"),
    output: Path = typer.Option(Path("./output"), "-o", "--output"),
    report: Optional[Path] = typer.Option(None, "-r", "--report", help="Path del CSV de reporte"),
):
    """Procesa todas las imágenes de un directorio secuencialmente."""
    if not directory.is_dir():
        typer.secho(f"Error: '{directory}' no es un directorio", fg=typer.colors.RED, err=True)
        raise typer.Exit(1)

    archivos = sorted(f for f in directory.iterdir() if f.suffix.lower() in EXTENSIONES_SOPORTADAS)

    if not archivos:
        typer.secho("No se encontraron imágenes en el directorio", fg=typer.colors.YELLOW)
        raise typer.Exit(0)

    output.mkdir(parents=True, exist_ok=True)
    cfg_manager = ConfigManager()
    config = cfg_manager.get_snapshot()
    session = _get_rembg_session(config.rembg.model)

    rows = []

    with Progress(
        TextColumn("[bold cyan]{task.fields[filename]}", justify="right"),
        BarColumn(),
        MofNCompleteColumn(),
        TimeElapsedColumn(),
    ) as progress:
        task = progress.add_task("batch", total=len(archivos), filename="")

        for archivo in archivos:
            progress.update(task, filename=archivo.name)
            article_id = archivo.stem
            output_path = output / f"{archivo.stem}.webp"
            row = {
                "article_id": article_id,
                "input_path": str(archivo.resolve()),
                "output_path": str(output_path.resolve()),
                "status": "",
                "processing_time_ms": 0,
                "error": "",
            }

            try:
                result = process_image(archivo.read_bytes(), article_id, config, session)
                output_path.write_bytes(result.image_bytes)
                row["status"] = "ok"
                row["processing_time_ms"] = result.processing_time_ms
            except ProcessingError as e:
                row["status"] = "error"
                row["error"] = f"[{e.step}] {e.detail}"
            except Exception as e:
                row["status"] = "error"
                row["error"] = str(e)

            rows.append(row)
            progress.advance(task)

    ok = sum(1 for r in rows if r["status"] == "ok")
    typer.echo(f"\n{ok}/{len(rows)} imágenes procesadas correctamente")

    if report:
        _escribir_reporte(rows, report)
        typer.secho(f"Reporte guardado en {report}", fg=typer.colors.CYAN)
```

### Ejemplo: config set con dotpath

```python
@config_app.command("set")
def config_set(
    key: str = typer.Argument(..., help="Clave en dotpath (ej: output.quality)"),
    value: str = typer.Argument(..., help="Valor a asignar"),
):
    """Modifica un valor de configuración usando dotpath notation."""
    cfg_manager = ConfigManager()
    current = cfg_manager.config.model_dump()
    override = _dotpath_to_nested(key, value)
    merged = _deep_merge(current, override)
    try:
        new_config = AppConfig(**merged)
    except Exception as e:
        typer.secho(f"Error: valor inválido para '{key}': {e}", fg=typer.colors.RED, err=True)
        raise typer.Exit(1)
    cfg_manager.update_config(new_config)
    typer.secho(f"✓ {key} actualizado a: {value}", fg=typer.colors.GREEN)
```

### Ejemplo: pyproject.toml entry point

```toml
[project]
name = "image-standardizer"
version = "1.0.0"
requires-python = ">=3.11"

[project.scripts]
imgproc = "app.cli:app"
```

Activar con: `pip install -e .` desde el root del proyecto.

## Environment Availability

| Dependencia | Requerida por | Disponible | Versión | Fallback |
|-------------|--------------|------------|---------|----------|
| Typer | CLI framework | ✓ | 0.24.1 | — |
| Rich | Progress bar, colores | ✓ | 13.7.1 (dep de Typer) | — |
| uvicorn | `serve` command | ✓ | 0.42.0 | — |
| rembg | `process`, `batch` | ✓ | 2.0.74 | — |
| Pillow | pipeline (via processor.py) | ✓ | 12.1.1 | — |
| csv, pathlib | stdlib | ✓ | Python stdlib | — |
| ConfigManager | config commands | ✓ | Fase 2 implementado | — |
| process_image() | CLI-01, CLI-02, CLI-05 | ✓ | Fase 1 implementado | — |

**Sin dependencias bloqueantes.** Todo disponible en el entorno actual.

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest 9.0.2 + pytest-asyncio 1.3.0 |
| Config file | `pyproject.toml` → `[tool.pytest.ini_options]` |
| Quick run command | `pytest tests/test_cli.py -x` |
| Full suite command | `pytest tests/ -x` |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| CLI-01 | `process foto.jpg` produce WebP idéntico al pipeline directo | unit | `pytest tests/test_cli.py::test_process_command -x` | ❌ Wave 0 |
| CLI-01 | `process` falla correctamente en imagen corrupta | unit | `pytest tests/test_cli.py::test_process_invalid_image -x` | ❌ Wave 0 |
| CLI-02 | `batch ./dir` procesa todos los archivos soportados | unit | `pytest tests/test_cli.py::test_batch_command -x` | ❌ Wave 0 |
| CLI-02 | `batch` con `--report` genera CSV con columnas correctas | unit | `pytest tests/test_cli.py::test_batch_report_csv -x` | ❌ Wave 0 |
| CLI-02 | `batch` continúa ante error en un archivo (no fail-fast) | unit | `pytest tests/test_cli.py::test_batch_continues_on_error -x` | ❌ Wave 0 |
| CLI-03 | `serve` invoca uvicorn.run con host/port/log_level correctos | unit (mock) | `pytest tests/test_cli.py::test_serve_command -x` | ❌ Wave 0 |
| CLI-04 | `config show` muestra YAML del settings.yaml | unit | `pytest tests/test_cli.py::test_config_show -x` | ❌ Wave 0 |
| CLI-04 | `config set output.quality 95` persiste el cambio | unit | `pytest tests/test_cli.py::test_config_set_valid -x` | ❌ Wave 0 |
| CLI-04 | `config set` rechaza valores inválidos | unit | `pytest tests/test_cli.py::test_config_set_invalid -x` | ❌ Wave 0 |
| CLI-05 | CLI no duplica lógica de pipeline | code review | N/A — verificar en `cli.py` que no hay código de Pillow/rembg fuera de lazy-init | — |

### Notas de Testing para CLI con Typer
- Usar `typer.testing.CliRunner` para invocar comandos sin levantar proceso real.
- **Mockear `process_image`** (no rembg ni Pillow) — la interfaz pública del CLI es `process_image`. Evitar cargar el modelo ONNX en tests CLI.
- **Mockear `uvicorn.run`** para el comando `serve` — no levantar servidor real en tests.
- **Usar `tmp_path` de pytest** para directorios de output y CSV de reporte.
- El `CliRunner` de Typer captura stdout/stderr en `result.output` y `result.exit_code`.

```python
# Patrón de test para CLI con Typer
from typer.testing import CliRunner
from unittest.mock import patch, MagicMock
from app.cli import app

runner = CliRunner()

def test_process_command(tmp_path, sample_jpeg):
    input_file = tmp_path / "producto.jpg"
    input_file.write_bytes(sample_jpeg)
    output_dir = tmp_path / "output"

    mock_result = MagicMock()
    mock_result.image_bytes = b"fake_webp"
    mock_result.processing_time_ms = 100

    with patch("app.cli.process_image", return_value=mock_result) as mock_proc:
        result = runner.invoke(app, ["process", str(input_file), "--output", str(output_dir)])

    assert result.exit_code == 0
    assert mock_proc.called
    assert (output_dir / "producto.webp").exists()
```

### Sampling Rate
- **Por commit:** `pytest tests/test_cli.py -x`
- **Por wave merge:** `pytest tests/ -x`
- **Phase gate:** Suite completa verde antes de `/gsd:verify-work`

### Wave 0 Gaps
- [ ] `tests/test_cli.py` — cubre CLI-01 a CLI-04 (todos los tests listados arriba)
- [ ] `conftest.py` — las fixtures existentes son suficientes; agregar fixture `sample_webp_output` si hace falta

## State of the Art

| Viejo approach | Approach actual | Cuándo cambió | Impacto |
|---------------|-----------------|---------------|---------|
| `argparse` + `click` manual | Typer con type hints | 2021-present | Menos boilerplate, help automático, sub-commands declarativos |
| `print(f"{n}/{total}")` en loop | `rich.progress.Progress` | 2020-present | Progress bar real-time sin polling manual |
| `asyncio.run(process_image(...))` en CLI | `process_image()` llamada directa síncrona | N/A (diseño del proyecto) | No hay event loop overhead en CLI |
| `typer.Typer(invoke_without_command=True)` | `app.add_typer(sub, name="cmd")` | Typer 0.9+ | Sub-commands limpios, sin callback extra |

## Open Questions

1. **article_id via flag en `process`**
   - Qué sabemos: D-10 dice derivar del nombre de archivo si no se provee. Claude's Discretion.
   - Qué no está claro: ¿Exponer `--article-id` como flag opcional, o no exponerlo en esta fase?
   - Recomendación: Exponer `--article-id` como flag opcional con default vacío (se deriva del stem). Costo mínimo, máxima flexibilidad para el operador.

2. **Modo verbose/quiet en batch**
   - Qué sabemos: D-06 pide Rich progress bar. No se especificó flag `--quiet`.
   - Qué no está claro: ¿Debería haber un modo silencioso para scripting?
   - Recomendación: Dentro de Claude's Discretion — implementar sin `--quiet` por ahora. Rich Progress se puede deshabilitar con `Progress(disable=True)` si se detecta que stdout no es TTY.

3. **Formato del error en batch CSV vs consola**
   - Qué sabemos: D-05 define columna `error` en CSV. El mensaje va al CSV.
   - Qué no está claro: ¿Mostrar también el error en consola durante el batch?
   - Recomendación: Dentro de Claude's Discretion — mostrar el error como warning en la progress bar (`progress.console.print`) y también guardarlo en el CSV.

## Sources

### Primary (HIGH confidence)
- Typer 0.24.1 instalado localmente — API verificada via `python3 -c` en el entorno del proyecto
- Rich 13.7.1 instalado — `from rich.progress import Progress, BarColumn, TextColumn, MofNCompleteColumn, TimeElapsedColumn` verificado
- uvicorn 0.42.0 — `inspect.signature(uvicorn.run)` muestra parámetros `host`, `port`, `log_level`
- `typer.testing.CliRunner` — verificado con sub-apps y comandos anidados
- `csv.DictWriter` — stdlib Python, verificado
- Pydantic v2 coerción — `AppConfig(**{'output': {'quality': '95'}})` produce `int 95` correctamente

### Secondary (MEDIUM confidence)
- CONTEXT.md del proyecto — decisiones de diseño D-01 a D-12 (fuente: discusión con usuario)
- CLAUDE.md del proyecto — stack tecnológico (Typer 0.24.1, Rich incluido como dep)

### Tertiary (LOW confidence)
- Ninguna

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — todo instalado y verificado en el entorno local
- Architecture patterns: HIGH — Typer sub-app, Rich Progress, csv.DictWriter verificados con código ejecutable
- Pitfalls: HIGH — derivados del código existente (processor.py, config.py) y comportamiento verificado de las libs
- Testing patterns: HIGH — CliRunner verificado, patrón de mock de process_image alineado con decisiones de Fase 1

**Research date:** 2026-03-30
**Valid until:** 2026-04-30 (stack estable, versiones fijas en requirements.txt)

## Project Constraints (from CLAUDE.md)

Directivas extraídas de `CLAUDE.md` que el planner debe verificar en cada tarea:

| Directiva | Detalle |
|-----------|---------|
| RAM ≤ 2GB | No agregar dependencias pesadas. Esta fase no agrega nada nuevo a requirements.txt. |
| Sin GPU | onnxruntime CPU ya configurado. CLI no cambia esto. |
| Dependencias externas: ninguna | CLI usa solo lo que ya está en requirements.txt. |
| Sesión rembg global, nunca por request | En CLI: sesión módulo-level con lazy init (D-01). Misma sesión para todo el batch. |
| asyncio.to_thread() obligatorio para CPU-bound | Solo aplica en contexto asyncio (server). CLI es síncrono — `process_image()` directo. |
| Output: WebP únicamente, RGB | `encode_webp()` ya lo garantiza. CLI no cambia esto. |
| Pipeline order fijo | CLI no toca el pipeline — llama `process_image()` que ya lo implementa. |
| yaml.safe_load siempre | ConfigManager ya usa `yaml.safe_load`. CLI usa ConfigManager. |
| python:3.11-slim base Docker | No aplica directamente a esta fase (no hay cambios en Dockerfile). |
| Entry point via pyproject.toml | D-10 lo confirma: `[project.scripts] imgproc = "app.cli:app"`. |
