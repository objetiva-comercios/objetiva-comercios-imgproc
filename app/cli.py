"""CLI del Image Standardizer Service.

Comandos disponibles:
  imgproc process <imagen>     — procesa una imagen individual
  imgproc batch <directorio>   — procesa todas las imagenes de un directorio
  imgproc serve                — inicia el servidor HTTP con Uvicorn
  imgproc config show          — muestra la configuracion activa
  imgproc config set <key> <v> — modifica un valor via dotpath notation

Reutiliza process_image() directamente sin duplicar logica de pipeline (CLI-05).
La sesion rembg es lazy: solo se carga para process y batch (D-01).
"""
import csv
import time
from pathlib import Path
from typing import Optional

import typer
import yaml
from rich.progress import BarColumn, MofNCompleteColumn, Progress, TextColumn, TimeElapsedColumn

from app.config import ConfigManager
from app.models import AppConfig
from app.processor import ProcessingError, process_image

# ---------------------------------------------------------------------------
# Constantes
# ---------------------------------------------------------------------------

EXTENSIONES_SOPORTADAS = {".jpg", ".jpeg", ".png", ".webp", ".bmp", ".tiff", ".tif"}

# ---------------------------------------------------------------------------
# Typer apps
# ---------------------------------------------------------------------------

app = typer.Typer(name="imgproc", help="Image Standardizer CLI")
config_app = typer.Typer(help="Gestionar configuracion")

# ---------------------------------------------------------------------------
# Estado global de la sesion rembg (lazy init — D-01)
# ---------------------------------------------------------------------------

_rembg_session = None


def _get_rembg_session(model: str):
    """Carga la sesion rembg una sola vez (lazy). No se invoca en serve ni config."""
    global _rembg_session
    if _rembg_session is None:
        typer.echo(f"Cargando modelo {model}...")
        import rembg
        _rembg_session = rembg.new_session(model)
    return _rembg_session


# ---------------------------------------------------------------------------
# Helpers internos
# ---------------------------------------------------------------------------


def _dotpath_to_nested(path: str, value: str) -> dict:
    """Convierte dotpath + valor a dict anidado.

    Ejemplo: 'output.quality', '95' -> {'output': {'quality': '95'}}
    """
    keys = path.split(".")
    result: object = value
    for k in reversed(keys):
        result = {k: result}
    return result  # type: ignore[return-value]


def _deep_merge(base: dict, override: dict) -> dict:
    """Merge recursivo: override sobreescribe base, mergeando dicts anidados."""
    merged = base.copy()
    for k, v in override.items():
        if k in merged and isinstance(merged[k], dict) and isinstance(v, dict):
            merged[k] = _deep_merge(merged[k], v)
        else:
            merged[k] = v
    return merged


def _escribir_reporte(rows: list[dict], report_path: Path) -> None:
    """Escribe el reporte CSV al finalizar el batch."""
    fieldnames = ["article_id", "input_path", "output_path", "status", "processing_time_ms", "error"]
    with open(report_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


# ---------------------------------------------------------------------------
# Comando: process
# ---------------------------------------------------------------------------


@app.command()
def process(
    image: Path = typer.Argument(..., help="Imagen a procesar (JPG, PNG, WebP, BMP, TIFF)"),
    output: Path = typer.Option(Path("./output"), "-o", "--output", help="Directorio de salida"),
    article_id: str = typer.Option("", "--article-id", "-a", help="ID del articulo (default: nombre del archivo)"),
) -> None:
    """Procesa una imagen individual y genera un WebP estandarizado."""
    # Validar que el path sea un archivo existente
    if not image.is_file():
        typer.secho(f"Error: '{image}' no es un archivo", fg=typer.colors.RED, err=True)
        raise typer.Exit(1)

    # Derivar article_id del stem si no se provee (Claude's Discretion)
    if not article_id:
        article_id = image.stem

    # Crear directorio de salida si no existe (D-03)
    output.mkdir(parents=True, exist_ok=True)

    # Cargar config (D-02: mismo path default que el server)
    cfg_manager = ConfigManager()
    config = cfg_manager.get_snapshot()

    # Lazy init rembg (D-01: solo para process y batch)
    session = _get_rembg_session(config.rembg.model)

    # Leer bytes de la imagen
    image_bytes = image.read_bytes()

    # Llamar pipeline sincrono directo (D-11, CLI-05: sin asyncio)
    try:
        result = process_image(image_bytes, article_id, config, session)
    except ProcessingError as e:
        typer.secho(f"Error [{e.step}]: {e.detail}", fg=typer.colors.RED, err=True)
        raise typer.Exit(1)

    # Guardar output con mismo nombre y extension .webp (D-04: sobreescribir si existe)
    output_path = output / f"{image.stem}.webp"
    output_path.write_bytes(result.image_bytes)

    typer.secho(
        f"OK {article_id}: {result.processing_time_ms}ms -> {output_path}",
        fg=typer.colors.GREEN,
    )


# ---------------------------------------------------------------------------
# Comando: batch
# ---------------------------------------------------------------------------


@app.command()
def batch(
    directory: Path = typer.Argument(..., help="Directorio con imagenes a procesar"),
    output: Path = typer.Option(Path("./output"), "-o", "--output", help="Directorio de salida"),
    report: Optional[Path] = typer.Option(None, "-r", "--report", help="Path del CSV de reporte"),
) -> None:
    """Procesa todas las imagenes de un directorio secuencialmente."""
    # Validar que sea directorio (Pitfall 6)
    if not directory.is_dir():
        typer.secho(f"Error: '{directory}' no es un directorio", fg=typer.colors.RED, err=True)
        raise typer.Exit(1)

    # Listar archivos soportados
    archivos = sorted(f for f in directory.iterdir() if f.suffix.lower() in EXTENSIONES_SOPORTADAS)

    if not archivos:
        typer.secho("No se encontraron imagenes en el directorio", fg=typer.colors.YELLOW)
        raise typer.Exit(0)

    # Crear directorio de salida (D-03)
    output.mkdir(parents=True, exist_ok=True)

    # Instanciar ConfigManager UNA vez (Pitfall 3)
    cfg_manager = ConfigManager()
    config = cfg_manager.get_snapshot()

    # Lazy init rembg UNA vez antes del loop (Pitfall 2: no reinicializar por archivo)
    session = _get_rembg_session(config.rembg.model)

    rows: list[dict] = []

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
            row: dict = {
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

    ok_count = sum(1 for r in rows if r["status"] == "ok")
    typer.echo(f"\n{ok_count}/{len(rows)} imagenes procesadas correctamente")

    if report:
        _escribir_reporte(rows, report)
        typer.secho(f"Reporte guardado en {report}", fg=typer.colors.CYAN)


# ---------------------------------------------------------------------------
# Comando: serve
# ---------------------------------------------------------------------------


@app.command()
def serve() -> None:
    """Inicia el servidor HTTP con Uvicorn."""
    cfg = ConfigManager().config
    import uvicorn
    uvicorn.run(
        "app.main:app",
        host=cfg.server.host,
        port=cfg.server.port,
        log_level=cfg.server.log_level,
    )


# ---------------------------------------------------------------------------
# Sub-app: config
# ---------------------------------------------------------------------------


@config_app.command("show")
def config_show() -> None:
    """Muestra la configuracion activa (YAML)."""
    cfg_manager = ConfigManager()
    path = cfg_manager._config_path
    if path.exists():
        typer.echo(path.read_text())
    else:
        typer.echo(yaml.dump(cfg_manager.config.model_dump(), default_flow_style=False, sort_keys=False))


@config_app.command("set")
def config_set(
    key: str = typer.Argument(..., help="Clave en dotpath (ej: output.quality)"),
    value: str = typer.Argument(..., help="Valor a asignar"),
) -> None:
    """Modifica un valor de configuracion usando dotpath notation."""
    cfg_manager = ConfigManager()
    current = cfg_manager.config.model_dump()
    override = _dotpath_to_nested(key, value)
    merged = _deep_merge(current, override)
    try:
        new_config = AppConfig(**merged)
    except Exception as e:
        typer.secho(f"Error: valor invalido para '{key}': {e}", fg=typer.colors.RED, err=True)
        raise typer.Exit(1)
    cfg_manager.update_config(new_config)
    typer.secho(f"OK: {key} = {value}", fg=typer.colors.GREEN)


# ---------------------------------------------------------------------------
# Registrar sub-app DESPUES de definir sus comandos (Pitfall 5)
# ---------------------------------------------------------------------------

app.add_typer(config_app, name="config")

# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    app()
