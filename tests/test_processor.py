"""Tests unitarios para app/processor.py — pipeline de procesamiento de imagenes."""
import io
from unittest.mock import MagicMock, patch

import pytest
from PIL import Image

from app.models import AppConfig, ProcessingResult
from app.processor import (
    ProcessingError,
    autocrop,
    calculate_scale_and_position,
    composite,
    decode_and_validate,
    encode_webp,
    enhance,
    process_image,
    remove_background,
)


# ---------------------------------------------------------------------------
# Helpers auxiliares para tests
# ---------------------------------------------------------------------------


def make_jpeg(width: int = 200, height: int = 150, color=(255, 0, 0)) -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", (width, height), color).save(buf, format="JPEG")
    return buf.getvalue()


def make_png(width: int = 100, height: int = 100, mode="RGB", color=(0, 200, 0)) -> bytes:
    buf = io.BytesIO()
    Image.new(mode, (width, height), color).save(buf, format="PNG")
    return buf.getvalue()


def make_webp(width: int = 100, height: int = 100) -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", (width, height), (100, 100, 200)).save(buf, format="WEBP")
    return buf.getvalue()


def make_bmp(width: int = 100, height: int = 100) -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", (width, height), (50, 50, 50)).save(buf, format="BMP")
    return buf.getvalue()


def make_tiff(width: int = 100, height: int = 100, mode="RGB") -> bytes:
    buf = io.BytesIO()
    if mode == "CMYK":
        color = (0, 50, 100, 0)
    else:
        color = (100, 100, 100)
    Image.new(mode, (width, height), color).save(buf, format="TIFF")
    return buf.getvalue()


def make_png_transparent_majority() -> bytes:
    """PNG 100x100 RGBA donde >10% de pixeles son transparentes (alpha < 128)."""
    img = Image.new("RGBA", (100, 100), (0, 200, 0, 255))
    pixels = img.load()
    # Hacer 50% de los pixeles transparentes
    for y in range(50, 100):
        for x in range(100):
            pixels[x, y] = (0, 200, 0, 0)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def make_rgba_with_product_in_center() -> Image.Image:
    """RGBA 200x200 con producto en centro (60x60) rodeado de transparencia."""
    img = Image.new("RGBA", (200, 200), (0, 0, 0, 0))
    pixels = img.load()
    # Producto en el centro: x=[70,130), y=[70,130)
    for y in range(70, 130):
        for x in range(70, 130):
            pixels[x, y] = (255, 0, 0, 255)
    return img


def make_mostly_transparent_rgba() -> Image.Image:
    """RGBA donde casi todo es transparente — < 5% opaco para trigger autocrop guard."""
    img = Image.new("RGBA", (200, 200), (0, 0, 0, 0))
    pixels = img.load()
    # Solo 2x2 = 4 pixeles opacos en 200x200=40000 pixeles = 0.01%
    pixels[100, 100] = (255, 0, 0, 255)
    pixels[101, 100] = (255, 0, 0, 255)
    pixels[100, 101] = (255, 0, 0, 255)
    pixels[101, 101] = (255, 0, 0, 255)
    return img


def default_config() -> AppConfig:
    return AppConfig()


# ---------------------------------------------------------------------------
# Tests: decode_and_validate
# ---------------------------------------------------------------------------


class TestDecodeAndValidate:
    def test_decode_jpeg(self, sample_jpeg):
        config = default_config()
        img, original_size, mode = decode_and_validate(sample_jpeg, config)
        assert img.mode == "RGBA"
        assert img.size == (200, 150)

    def test_decode_png(self):
        png_bytes = make_png()
        config = default_config()
        img, original_size, mode = decode_and_validate(png_bytes, config)
        assert img.mode == "RGBA"

    def test_decode_webp(self):
        webp_bytes = make_webp()
        config = default_config()
        img, original_size, mode = decode_and_validate(webp_bytes, config)
        assert img.mode == "RGBA"

    def test_decode_bmp(self):
        bmp_bytes = make_bmp()
        config = default_config()
        img, original_size, mode = decode_and_validate(bmp_bytes, config)
        assert img.mode == "RGBA"

    def test_decode_tiff(self):
        tiff_bytes = make_tiff()
        config = default_config()
        img, original_size, mode = decode_and_validate(tiff_bytes, config)
        assert img.mode == "RGBA"

    def test_decode_invalid(self):
        invalid_bytes = b"not an image at all"
        config = default_config()
        with pytest.raises(ProcessingError) as exc_info:
            decode_and_validate(invalid_bytes, config)
        assert exc_info.value.step == "decode"

    def test_megapixel_limit(self, sample_large_image):
        """Imagen 6000x5000 = 30MP > 25MP debe lanzar ProcessingError."""
        config = default_config()
        with pytest.raises(ProcessingError) as exc_info:
            decode_and_validate(sample_large_image, config)
        assert exc_info.value.step == "decode"
        assert "exceeds maximum" in exc_info.value.detail.lower() or "exceeds" in str(exc_info.value).lower()

    def test_cmyk_conversion(self, sample_cmyk):
        """CMYK TIFF debe convertirse a RGBA silenciosamente."""
        config = default_config()
        img, original_size, mode = decode_and_validate(sample_cmyk, config)
        assert img.mode == "RGBA"

    def test_original_size_returned(self, sample_jpeg):
        config = default_config()
        img, original_size, mode = decode_and_validate(sample_jpeg, config)
        assert original_size == "200x150"

    def test_exif_transpose(self):
        """JPEG con EXIF Orientation=6 (rotado 90 CW) debe tener ancho/alto intercambiados."""
        import struct

        # Crear una imagen landscape 200x100
        img_original = Image.new("RGB", (200, 100), (255, 0, 0))

        # Crear un JPEG con EXIF Orientation=6 (90 CW rotation)
        # Orientation=6 significa que la imagen fue capturada rotada 90 grados CW
        # al leerla con exif_transpose, width y height se intercambian
        buf = io.BytesIO()
        # Guardar con exif orientation 6
        import piexif
        exif_dict = {"0th": {piexif.ImageIFD.Orientation: 6}}
        exif_bytes = piexif.dump(exif_dict)
        img_original.save(buf, format="JPEG", exif=exif_bytes)
        jpeg_with_exif = buf.getvalue()

        config = default_config()
        img, original_size, mode = decode_and_validate(jpeg_with_exif, config)
        # Orientation=6 => imagen original 200x100 se transpone a 100x200
        assert img.size == (100, 200), f"Expected (100, 200) after exif_transpose, got {img.size}"


# ---------------------------------------------------------------------------
# Tests: remove_background
# ---------------------------------------------------------------------------


class TestRemoveBackground:
    def test_skip_rembg_transparent(self):
        """PNG con >10% alpha transparente pre-existente debe saltar rembg."""
        png_bytes = make_png_transparent_majority()
        config = default_config()
        img = Image.open(io.BytesIO(png_bytes)).convert("RGBA")

        mock_session = MagicMock()
        with patch("rembg.remove") as mock_remove:
            result = remove_background(img, config, mock_session)
            mock_remove.assert_not_called()
        assert result.mode == "RGBA"

    def test_rembg_called_for_opaque(self):
        """Imagen RGB sin transparencia debe llamar a rembg."""
        jpeg_bytes = make_jpeg()
        config = default_config()
        img = Image.open(io.BytesIO(jpeg_bytes)).convert("RGBA")

        # Crear imagen de retorno valida RGBA para mock
        result_img = Image.new("RGBA", (200, 150), (100, 200, 100, 255))
        result_buf = io.BytesIO()
        result_img.save(result_buf, format="PNG")
        result_png = result_buf.getvalue()

        mock_session = MagicMock()
        with patch("rembg.remove", return_value=result_png) as mock_remove:
            result = remove_background(img, config, mock_session)
            mock_remove.assert_called_once()
        assert result.mode == "RGBA"


# ---------------------------------------------------------------------------
# Tests: autocrop
# ---------------------------------------------------------------------------


class TestAutocrop:
    def test_autocrop_basic(self):
        """Producto en centro rodeado de transparencia -> recortado al bbox del producto."""
        img = make_rgba_with_product_in_center()
        config = default_config()
        cropped = autocrop(img, config)
        # El producto ocupa x=[70,130), y=[70,130) => 60x60
        assert cropped.width == 60
        assert cropped.height == 60

    def test_autocrop_guard(self):
        """Imagen con < 5% opaco -> autocrop skipped, imagen original retornada."""
        img = make_mostly_transparent_rgba()
        original_size = img.size
        config = default_config()
        result = autocrop(img, config)
        assert result.size == original_size

    def test_autocrop_disabled(self):
        """autocrop.enabled=False -> imagen retornada sin cambios."""
        img = make_rgba_with_product_in_center()
        original_size = img.size
        config = default_config()
        config = config.model_copy(update={"autocrop": config.autocrop.model_copy(update={"enabled": False})})
        result = autocrop(img, config)
        assert result.size == original_size

    def test_autocrop_bbox_none(self):
        """autocrop retorna imagen original cuando alpha es todo cero (bbox=None)."""
        # Imagen RGBA con todos los pixeles alpha=0 (completamente transparente)
        img = Image.new("RGBA", (200, 200), (0, 0, 0, 0))
        config = default_config()
        result = autocrop(img, config)
        assert result.size == (200, 200)
        assert result.mode == "RGBA"

    def test_autocrop_removes_small_artifacts(self):
        """_clean_alpha_artifacts elimina artefacto pequeno; autocrop recorta solo el producto."""
        img = Image.new("RGBA", (200, 200), (0, 0, 0, 0))
        pixels = img.load()
        # Producto principal 50x50 en el centro (2500 pixeles opacos)
        for y in range(75, 125):
            for x in range(75, 125):
                pixels[x, y] = (255, 0, 0, 255)
        # Artefacto pequeno 2x2 en esquina (4 pixeles = 0.16% del producto)
        for y in range(5, 7):
            for x in range(5, 7):
                pixels[x, y] = (255, 0, 0, 255)
        config = default_config()
        cropped = autocrop(img, config)
        # Sin el artefacto, el bbox es solo el producto 50x50
        assert cropped.width == 50
        assert cropped.height == 50


# ---------------------------------------------------------------------------
# Tests: calculate_scale_and_position
# ---------------------------------------------------------------------------


class TestCalculateScaleAndPosition:
    def test_scale_landscape(self):
        """Producto 1000x500 -> debe caber en 640x640 (available con padding 10%)."""
        img = Image.new("RGBA", (1000, 500), (255, 0, 0, 255))
        config = default_config()  # size=800, padding=10% => available=640
        scaled_w, scaled_h, offset_x, offset_y = calculate_scale_and_position(img, config)
        # scale = 640/1000 = 0.64 => 640x320
        assert scaled_w == 640
        assert scaled_h == 320

    def test_scale_portrait(self):
        """Producto 500x1000 -> debe caber en 640x640 manteniendo ratio."""
        img = Image.new("RGBA", (500, 1000), (255, 0, 0, 255))
        config = default_config()
        scaled_w, scaled_h, offset_x, offset_y = calculate_scale_and_position(img, config)
        # scale = 640/1000 = 0.64 => 320x640
        assert scaled_w == 320
        assert scaled_h == 640

    def test_scale_square(self):
        """Producto 640x640 ya cabe exactamente, no escala."""
        img = Image.new("RGBA", (640, 640), (255, 0, 0, 255))
        config = default_config()
        scaled_w, scaled_h, offset_x, offset_y = calculate_scale_and_position(img, config)
        assert scaled_w == 640
        assert scaled_h == 640

    def test_offsets_center(self):
        """Producto 640x320 debe centrarse en canvas 800x800 => offset_y=240."""
        img = Image.new("RGBA", (1000, 500), (255, 0, 0, 255))
        config = default_config()
        scaled_w, scaled_h, offset_x, offset_y = calculate_scale_and_position(img, config)
        # Canvas 800, product 640x320 => offset_x=(800-640)//2=80, offset_y=(800-320)//2=240
        assert offset_x == 80
        assert offset_y == 240


# ---------------------------------------------------------------------------
# Tests: composite
# ---------------------------------------------------------------------------


class TestComposite:
    def test_composite_centering(self):
        """Producto 400x200 en canvas 800x800 debe estar centrado."""
        img = Image.new("RGBA", (400, 200), (255, 0, 0, 255))
        config = default_config()
        result = composite(img, config)
        assert result.size == (800, 800)

    def test_composite_output_rgb(self):
        """Output de composite debe ser RGB (sin alpha)."""
        img = Image.new("RGBA", (400, 400), (255, 0, 0, 255))
        config = default_config()
        result = composite(img, config)
        assert result.mode == "RGB"

    def test_composite_exact_size(self):
        """Output siempre debe ser exactamente (800, 800)."""
        img = Image.new("RGBA", (200, 600), (0, 255, 0, 255))
        config = default_config()
        result = composite(img, config)
        assert result.size == (800, 800)

    def test_composite_custom_background(self):
        """background_color=[200,200,200] -> esquinas del canvas son (200,200,200)."""
        img = Image.new("RGBA", (100, 100), (255, 0, 0, 255))
        config = default_config()
        config = config.model_copy(
            update={"output": config.output.model_copy(update={"background_color": [200, 200, 200]})}
        )
        result = composite(img, config)
        # Esquina (0, 0) debe ser el color de fondo
        pixel = result.getpixel((0, 0))
        assert pixel == (200, 200, 200)


# ---------------------------------------------------------------------------
# Tests: enhance
# ---------------------------------------------------------------------------


class TestEnhance:
    def test_enhancement_brightness(self):
        """brightness=1.5 -> imagen resultante mas brillante."""
        img = Image.new("RGB", (100, 100), (100, 100, 100))
        config = default_config()
        config = config.model_copy(
            update={"enhancement": config.enhancement.model_copy(update={"brightness": 1.5})}
        )
        result = enhance(img, config)
        # Media de pixeles original: 100 ; resultado debe ser mayor
        import numpy as np
        original_mean = sum(img.getpixel((50, 50))) / 3
        result_mean = sum(result.getpixel((50, 50))) / 3
        assert result_mean > original_mean

    def test_enhancement_contrast(self):
        """contrast=1.5 -> contraste aplicado en imagen con variacion de pixeles."""
        # Usar imagen con gradiente para que el contraste tenga efecto medible
        img = Image.new("RGB", (100, 100), (50, 50, 50))
        pixels = img.load()
        # Mitad superior oscura, mitad inferior clara — el contraste debe acentuar la diferencia
        for y in range(50, 100):
            for x in range(100):
                pixels[x, y] = (200, 200, 200)
        config = default_config()
        config = config.model_copy(
            update={"enhancement": config.enhancement.model_copy(update={"contrast": 2.0})}
        )
        result = enhance(img, config)
        # El pixel oscuro (50,50,50) debe volverse mas oscuro con mas contraste
        dark_pixel_before = img.getpixel((50, 25))
        dark_pixel_after = result.getpixel((50, 25))
        assert dark_pixel_after[0] < dark_pixel_before[0], (
            f"Expected darker pixel after contrast, got {dark_pixel_after} vs {dark_pixel_before}"
        )

    def test_enhancement_skip(self):
        """brightness=1.0 y contrast=1.0 -> imagen sin cambios."""
        img = Image.new("RGB", (100, 100), (100, 150, 200))
        config = default_config()  # default brightness=1.0, contrast=1.0
        result = enhance(img, config)
        assert result.getpixel((50, 50)) == img.getpixel((50, 50))


# ---------------------------------------------------------------------------
# Tests: encode_webp
# ---------------------------------------------------------------------------


class TestEncodeWebp:
    def test_encode_webp(self):
        """Imagen RGB -> bytes validos WebP (magic RIFF...WEBP)."""
        img = Image.new("RGB", (100, 100), (200, 100, 50))
        config = default_config()
        result = encode_webp(img, config)
        assert isinstance(result, bytes)
        assert len(result) > 0
        # WebP magic: RIFF en bytes 0-3 y WEBP en bytes 8-11
        assert result[:4] == b"RIFF"
        assert result[8:12] == b"WEBP"

    def test_encode_quality(self):
        """quality=50 produce menos bytes que quality=95 en imagen con detalle."""
        import random

        # Imagen con ruido (alta frecuencia) para que la diferencia de calidad sea visible
        random.seed(42)
        img = Image.new("RGB", (200, 200), (100, 100, 100))
        pixels = img.load()
        for y in range(200):
            for x in range(200):
                r = random.randint(0, 255)
                g = random.randint(0, 255)
                b = random.randint(0, 255)
                pixels[x, y] = (r, g, b)

        config_low = default_config()
        config_low = config_low.model_copy(
            update={"output": config_low.output.model_copy(update={"quality": 10})}
        )
        config_high = default_config()
        config_high = config_high.model_copy(
            update={"output": config_high.output.model_copy(update={"quality": 95})}
        )
        bytes_low = encode_webp(img, config_low)
        bytes_high = encode_webp(img, config_high)
        assert len(bytes_low) < len(bytes_high), (
            f"Expected quality=10 ({len(bytes_low)} bytes) < quality=95 ({len(bytes_high)} bytes)"
        )

    def test_encode_lossless(self):
        """quality=0 -> usa lossless=True (puede producir bytes mas grandes)."""
        img = Image.new("RGB", (100, 100), (50, 100, 150))
        config = default_config()
        config = config.model_copy(
            update={"output": config.output.model_copy(update={"quality": 0})}
        )
        result = encode_webp(img, config)
        assert isinstance(result, bytes)
        assert result[:4] == b"RIFF"


# ---------------------------------------------------------------------------
# Tests: process_image (pipeline completo)
# ---------------------------------------------------------------------------


class TestProcessImage:
    def test_output_mode_rgb(self, sample_jpeg):
        """Output final del pipeline debe ser RGB, size (800, 800)."""
        config = default_config()
        mock_session = MagicMock()

        # Mock rembg para retornar imagen RGBA valida
        result_img = Image.new("RGBA", (200, 150), (100, 200, 100, 255))
        result_buf = io.BytesIO()
        result_img.save(result_buf, format="PNG")
        result_png = result_buf.getvalue()

        with patch("rembg.remove", return_value=result_png):
            result = process_image(sample_jpeg, "ART-001", config, mock_session)

        output_img = Image.open(io.BytesIO(result.image_bytes))
        assert output_img.mode == "RGB"
        assert output_img.size == (800, 800)

    def test_full_pipeline(self, sample_jpeg):
        """process_image con rembg mockeado retorna ProcessingResult con todos los campos."""
        config = default_config()
        mock_session = MagicMock()

        result_img = Image.new("RGBA", (200, 150), (50, 100, 200, 255))
        result_buf = io.BytesIO()
        result_img.save(result_buf, format="PNG")
        result_png = result_buf.getvalue()

        with patch("rembg.remove", return_value=result_png):
            result = process_image(sample_jpeg, "ART-042", config, mock_session)

        assert isinstance(result, ProcessingResult)
        assert result.article_id == "ART-042"
        assert result.model_used == "isnet-general-use"
        assert result.original_size == "200x150"
        assert result.output_size == "800x800"
        assert isinstance(result.image_bytes, bytes)
        assert len(result.image_bytes) > 0
        assert result.processing_time_ms >= 0
        # steps_applied debe incluir los pasos clave
        assert "decode" in result.steps_applied
        assert "encode" in result.steps_applied

    def test_pipeline_unknown_exception_wrapped(self, sample_jpeg):
        """Excepcion no-ProcessingError en pipeline se envuelve en ProcessingError(step='unknown')."""
        config = default_config()
        mock_session = MagicMock()
        with patch("app.processor.autocrop", side_effect=ValueError("unexpected error")):
            with pytest.raises(ProcessingError) as exc_info:
                process_image(sample_jpeg, "ART-ERR", config, mock_session)
        assert exc_info.value.step == "unknown"
        assert "unexpected error" in exc_info.value.detail

    def test_process_image_enhance_not_in_steps_when_default(self, sample_jpeg):
        """Pipeline con brightness=1.0 y contrast=1.0 NO incluye 'enhance' en steps_applied."""
        config = default_config()
        # Asegurar valores default (no enhancement)
        config.enhancement.brightness = 1.0
        config.enhancement.contrast = 1.0
        mock_session = MagicMock()
        mock_rgba = Image.new("RGBA", (200, 150), (255, 0, 0, 255))
        mock_rgba_bytes = io.BytesIO()
        mock_rgba.save(mock_rgba_bytes, format="PNG")
        with patch("rembg.remove", return_value=mock_rgba_bytes.getvalue()):
            result = process_image(sample_jpeg, "ART-ENH", config, mock_session)
        assert "enhance" not in result.steps_applied
        assert "encode" in result.steps_applied
