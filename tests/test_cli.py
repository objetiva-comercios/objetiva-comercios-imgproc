"""Tests unitarios para el CLI de Image Standardizer.

Cubre todos los subcomandos: process, batch, serve, config show, config set.
"""
import csv
import io
from pathlib import Path
from unittest.mock import MagicMock, patch, PropertyMock

import pytest
from typer.testing import CliRunner

from app.cli import app
from app.processor import ProcessingError

runner = CliRunner()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def make_mock_result(article_id: str = "test", processing_time_ms: int = 100) -> MagicMock:
    """Crea un MagicMock simulando ProcessingResult."""
    mock_result = MagicMock()
    mock_result.image_bytes = b"fake_webp_content"
    mock_result.processing_time_ms = processing_time_ms
    mock_result.article_id = article_id
    return mock_result


# ---------------------------------------------------------------------------
# Tests: comando process
# ---------------------------------------------------------------------------


def test_process_command(tmp_path):
    """process con archivo valido retorna exit_code 0 y crea {stem}.webp."""
    input_file = tmp_path / "foto.jpg"
    input_file.write_bytes(b"fake_image_data")
    output_dir = tmp_path / "output"

    mock_result = make_mock_result(article_id="foto")

    with patch("app.cli.process_image", return_value=mock_result) as mock_proc, \
         patch("app.cli._get_rembg_session", return_value=MagicMock()):
        result = runner.invoke(app, ["process", str(input_file), "-o", str(output_dir)])

    assert result.exit_code == 0, f"Expected exit 0, got {result.exit_code}. Output: {result.output}"
    assert mock_proc.called
    assert (output_dir / "foto.webp").exists()
    assert (output_dir / "foto.webp").read_bytes() == b"fake_webp_content"


def test_process_with_article_id(tmp_path):
    """process con --article-id pasa el article_id correcto a process_image."""
    input_file = tmp_path / "foto.jpg"
    input_file.write_bytes(b"fake_image_data")
    output_dir = tmp_path / "output"

    mock_result = make_mock_result(article_id="ART-001")

    with patch("app.cli.process_image", return_value=mock_result) as mock_proc, \
         patch("app.cli._get_rembg_session", return_value=MagicMock()):
        result = runner.invoke(app, [
            "process", str(input_file),
            "--article-id", "ART-001",
            "-o", str(output_dir),
        ])

    assert result.exit_code == 0, f"Output: {result.output}"
    # Verificar que se pasó el article_id correcto
    call_args = mock_proc.call_args
    assert call_args[0][1] == "ART-001" or call_args.args[1] == "ART-001"


def test_process_default_article_id(tmp_path):
    """Sin --article-id, usa el stem del archivo como article_id."""
    input_file = tmp_path / "producto_001.jpg"
    input_file.write_bytes(b"fake_image_data")
    output_dir = tmp_path / "output"

    mock_result = make_mock_result(article_id="producto_001")

    with patch("app.cli.process_image", return_value=mock_result) as mock_proc, \
         patch("app.cli._get_rembg_session", return_value=MagicMock()):
        result = runner.invoke(app, ["process", str(input_file), "-o", str(output_dir)])

    assert result.exit_code == 0, f"Output: {result.output}"
    call_args = mock_proc.call_args
    assert call_args[0][1] == "producto_001" or call_args.args[1] == "producto_001"


def test_process_invalid_image(tmp_path):
    """process_image lanza ProcessingError -> exit_code 1, output contiene 'Error'."""
    input_file = tmp_path / "corrupta.jpg"
    input_file.write_bytes(b"not_an_image")
    output_dir = tmp_path / "output"

    with patch("app.cli.process_image", side_effect=ProcessingError("decode", "corrupt file")), \
         patch("app.cli._get_rembg_session", return_value=MagicMock()):
        result = runner.invoke(app, ["process", str(input_file), "-o", str(output_dir)])

    assert result.exit_code == 1
    assert "Error" in result.output or "error" in result.output.lower()


def test_process_nonexistent_file(tmp_path):
    """process con archivo inexistente -> exit_code != 0."""
    nonexistent = tmp_path / "no_existe.jpg"
    output_dir = tmp_path / "output"

    result = runner.invoke(app, ["process", str(nonexistent), "-o", str(output_dir)])

    assert result.exit_code != 0


def test_process_creates_output_dir(tmp_path):
    """Si output dir no existe, se crea automaticamente."""
    input_file = tmp_path / "foto.jpg"
    input_file.write_bytes(b"fake_image_data")
    output_dir = tmp_path / "nuevo" / "directorio" / "output"

    assert not output_dir.exists()

    mock_result = make_mock_result()

    with patch("app.cli.process_image", return_value=mock_result), \
         patch("app.cli._get_rembg_session", return_value=MagicMock()):
        result = runner.invoke(app, ["process", str(input_file), "-o", str(output_dir)])

    assert result.exit_code == 0, f"Output: {result.output}"
    assert output_dir.exists()


# ---------------------------------------------------------------------------
# Tests: comando batch
# ---------------------------------------------------------------------------


def test_batch_command(tmp_path):
    """batch con directorio con 2 archivos jpg -> procesa ambos, crea 2 webp."""
    input_dir = tmp_path / "fotos"
    input_dir.mkdir()
    (input_dir / "foto1.jpg").write_bytes(b"fake1")
    (input_dir / "foto2.jpg").write_bytes(b"fake2")
    output_dir = tmp_path / "output"

    mock_result = make_mock_result()

    with patch("app.cli.process_image", return_value=mock_result) as mock_proc, \
         patch("app.cli._get_rembg_session", return_value=MagicMock()):
        result = runner.invoke(app, ["batch", str(input_dir), "-o", str(output_dir)])

    assert result.exit_code == 0, f"Output: {result.output}"
    assert mock_proc.call_count == 2
    assert (output_dir / "foto1.webp").exists()
    assert (output_dir / "foto2.webp").exists()


def test_batch_report_csv(tmp_path):
    """batch con --report genera CSV con columnas correctas."""
    input_dir = tmp_path / "fotos"
    input_dir.mkdir()
    (input_dir / "producto.jpg").write_bytes(b"fake")
    output_dir = tmp_path / "output"
    report_path = tmp_path / "reporte.csv"

    mock_result = make_mock_result(article_id="producto", processing_time_ms=150)

    with patch("app.cli.process_image", return_value=mock_result), \
         patch("app.cli._get_rembg_session", return_value=MagicMock()):
        result = runner.invoke(app, [
            "batch", str(input_dir),
            "-o", str(output_dir),
            "-r", str(report_path),
        ])

    assert result.exit_code == 0, f"Output: {result.output}"
    assert report_path.exists()

    with open(report_path, "r", newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        fieldnames = reader.fieldnames
        rows = list(reader)

    assert fieldnames == ["article_id", "input_path", "output_path", "status", "processing_time_ms", "error"]
    assert len(rows) == 1
    assert rows[0]["status"] == "ok"
    assert rows[0]["article_id"] == "producto"


def test_batch_continues_on_error(tmp_path):
    """Un archivo falla, el otro se procesa ok. CSV tiene ambas filas con status correcto."""
    input_dir = tmp_path / "fotos"
    input_dir.mkdir()
    (input_dir / "buena.jpg").write_bytes(b"fake_good")
    (input_dir / "mala.jpg").write_bytes(b"fake_bad")
    output_dir = tmp_path / "output"
    report_path = tmp_path / "reporte.csv"

    mock_ok = make_mock_result(article_id="buena")
    processing_error = ProcessingError("decode", "corrupt file")

    def side_effect(image_bytes, article_id, config, session):
        if article_id == "mala":
            raise processing_error
        return mock_ok

    with patch("app.cli.process_image", side_effect=side_effect), \
         patch("app.cli._get_rembg_session", return_value=MagicMock()):
        result = runner.invoke(app, [
            "batch", str(input_dir),
            "-o", str(output_dir),
            "-r", str(report_path),
        ])

    assert result.exit_code == 0, f"Output: {result.output}"
    assert report_path.exists()

    with open(report_path, "r", newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        rows = {row["article_id"]: row for row in reader}

    assert rows["buena"]["status"] == "ok"
    assert rows["mala"]["status"] == "error"
    assert "corrupt file" in rows["mala"]["error"] or "decode" in rows["mala"]["error"]


def test_batch_empty_directory(tmp_path):
    """Directorio sin imagenes -> exit_code 0, mensaje 'No se encontraron'."""
    input_dir = tmp_path / "vacio"
    input_dir.mkdir()
    output_dir = tmp_path / "output"

    result = runner.invoke(app, ["batch", str(input_dir), "-o", str(output_dir)])

    assert result.exit_code == 0, f"Output: {result.output}"
    assert "No se encontraron" in result.output


def test_batch_not_a_directory(tmp_path):
    """Path es un archivo, no directorio -> exit_code 1."""
    not_a_dir = tmp_path / "archivo.jpg"
    not_a_dir.write_bytes(b"fake")
    output_dir = tmp_path / "output"

    result = runner.invoke(app, ["batch", str(not_a_dir), "-o", str(output_dir)])

    assert result.exit_code == 1


# ---------------------------------------------------------------------------
# Tests: comando serve
# ---------------------------------------------------------------------------


def test_serve_command():
    """serve mockea uvicorn.run y verifica llamada con host, port, log_level del config."""
    with patch("uvicorn.run") as mock_uvicorn, \
         patch("app.cli.ConfigManager") as mock_cfg_cls:
        mock_cfg = MagicMock()
        mock_cfg.config.server.host = "0.0.0.0"
        mock_cfg.config.server.port = 8010
        mock_cfg.config.server.log_level = "info"
        mock_cfg_cls.return_value = mock_cfg

        result = runner.invoke(app, ["serve"])

    # Verificar que uvicorn.run fue llamado con los parametros correctos
    assert mock_uvicorn.called
    call_kwargs = mock_uvicorn.call_args
    # host, port, log_level deben estar en args o kwargs
    args = call_kwargs.args
    kwargs = call_kwargs.kwargs
    assert kwargs.get("host") == "0.0.0.0" or "0.0.0.0" in str(args)
    assert kwargs.get("port") == 8010 or 8010 in str(args)
    assert kwargs.get("log_level") == "info" or "info" in str(args)


# ---------------------------------------------------------------------------
# Tests: config show
# ---------------------------------------------------------------------------


def test_config_show(tmp_path):
    """config show muestra el contenido del settings.yaml."""
    settings_content = """output:
  quality: 85
  size: 800
"""
    settings_file = tmp_path / "settings.yaml"
    settings_file.write_text(settings_content)

    with patch("app.cli.ConfigManager") as mock_cfg_cls:
        mock_cfg = MagicMock()
        mock_cfg._config_path = settings_file
        mock_cfg_cls.return_value = mock_cfg

        result = runner.invoke(app, ["config", "show"])

    assert result.exit_code == 0, f"Output: {result.output}"
    assert "quality" in result.output
    assert "85" in result.output


# ---------------------------------------------------------------------------
# Tests: config set
# ---------------------------------------------------------------------------


def test_config_set_valid(tmp_path):
    """config set output.quality 95 llama update_config con AppConfig donde output.quality == 95."""
    from app.models import AppConfig

    with patch("app.cli.ConfigManager") as mock_cfg_cls:
        mock_cfg = MagicMock()
        mock_cfg.config = AppConfig()
        mock_cfg_cls.return_value = mock_cfg

        result = runner.invoke(app, ["config", "set", "output.quality", "95"])

    assert result.exit_code == 0, f"Output: {result.output}"
    assert mock_cfg.update_config.called
    # Verificar que el AppConfig pasado tiene output.quality == 95
    called_config = mock_cfg.update_config.call_args[0][0]
    assert isinstance(called_config, AppConfig)
    assert called_config.output.quality == 95


def test_config_set_invalid(tmp_path):
    """config set con valor invalido -> exit_code 1, output contiene 'Error'."""
    from app.models import AppConfig

    with patch("app.cli.ConfigManager") as mock_cfg_cls:
        mock_cfg = MagicMock()
        mock_cfg.config = AppConfig()
        mock_cfg_cls.return_value = mock_cfg

        result = runner.invoke(app, ["config", "set", "output.quality", "no_es_numero"])

    assert result.exit_code == 1
    assert "Error" in result.output or "error" in result.output.lower()


def test_config_set_invalid_key():
    """config set con clave raiz inexistente -> exit_code 1, muestra claves validas."""
    from app.models import AppConfig

    with patch("app.cli.ConfigManager") as mock_cfg_cls:
        mock_cfg = MagicMock()
        mock_cfg.config = AppConfig()
        mock_cfg_cls.return_value = mock_cfg

        result = runner.invoke(app, ["config", "set", "nonexistent.key", "value"])

    assert result.exit_code == 1
    assert "no existe" in result.output.lower() or "nonexistent" in result.output.lower()
    assert "output" in result.output  # muestra claves validas
