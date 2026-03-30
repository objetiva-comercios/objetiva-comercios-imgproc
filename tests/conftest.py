import io
import os
import tempfile

import pytest
from PIL import Image

from app.config import ConfigManager


@pytest.fixture
def sample_jpeg() -> bytes:
    """Imagen JPEG 200x150 RGB en bytes."""
    buf = io.BytesIO()
    img = Image.new("RGB", (200, 150), (255, 0, 0))
    img.save(buf, format="JPEG")
    return buf.getvalue()


@pytest.fixture
def sample_png_transparent() -> bytes:
    """Imagen PNG 100x100 RGBA con mitad superior opaca y mitad inferior transparente."""
    img = Image.new("RGBA", (100, 100), (0, 200, 0, 255))
    pixels = img.load()
    for y in range(50, 100):
        for x in range(100):
            pixels[x, y] = (0, 200, 0, 0)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


@pytest.fixture
def sample_cmyk() -> bytes:
    """Imagen CMYK 100x100 guardada como TIFF en bytes."""
    img = Image.new("CMYK", (100, 100), (0, 50, 100, 0))
    buf = io.BytesIO()
    img.save(buf, format="TIFF")
    return buf.getvalue()


@pytest.fixture
def sample_large_image() -> bytes:
    """Imagen 6000x5000 RGB JPEG (>25 megapixels) para test D-05."""
    buf = io.BytesIO()
    img = Image.new("RGB", (6000, 5000), (100, 150, 200))
    img.save(buf, format="JPEG")
    return buf.getvalue()


@pytest.fixture
def tmp_settings_yaml(tmp_path):
    """Crea un archivo temporal settings.yaml con contenido default. Retorna su path."""
    settings_content = """rembg:
  model: "birefnet-lite"
  alpha_matting: false
  alpha_matting_foreground_threshold: 240
  alpha_matting_background_threshold: 10
  alpha_matting_erode_size: 10

output:
  size: 800
  format: "webp"
  quality: 85
  background_color: [255, 255, 255]

padding:
  enabled: true
  percent: 10

autocrop:
  enabled: true
  threshold: 10

enhancement:
  brightness: 1.0
  contrast: 1.0

queue:
  max_concurrent: 1
  max_queue_size: 10
  timeout_seconds: 120

server:
  host: "0.0.0.0"
  port: 8010
  log_level: "info"
"""
    settings_file = tmp_path / "settings.yaml"
    settings_file.write_text(settings_content)
    return str(settings_file)


@pytest.fixture
def config_manager(tmp_settings_yaml):
    """ConfigManager configurado con settings.yaml temporal."""
    return ConfigManager(config_path=tmp_settings_yaml)
