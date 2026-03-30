"""Pipeline de procesamiento de imagenes para Image Standardizer Service.

Orden del pipeline (fijo e inamovible per CLAUDE.md):
  decode -> rembg -> autocrop -> scale -> composite -> enhance -> encode
"""
import io
import json
import logging
import time
from io import BytesIO

import rembg
from PIL import Image, ImageEnhance, ImageOps, UnidentifiedImageError

from app.models import AppConfig, ProcessingResult

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Excepcion del pipeline
# ---------------------------------------------------------------------------


class ProcessingError(Exception):
    """Error durante procesamiento del pipeline. Incluye step donde fallo."""

    def __init__(self, step: str, detail: str):
        self.step = step
        self.detail = detail
        super().__init__(f"[{step}] {detail}")


# ---------------------------------------------------------------------------
# Step 1: decode_and_validate
# ---------------------------------------------------------------------------


def decode_and_validate(
    image_bytes: bytes,
    config: AppConfig,
    article_id: str = "unknown",
) -> tuple[Image.Image, str, str]:
    """Decodifica y valida la imagen de entrada.

    Returns:
        (img_rgba, original_size_str, original_mode)
    Raises:
        ProcessingError: si la imagen es invalida, corrupta o supera 25 megapixels.
    """
    try:
        img = Image.open(BytesIO(image_bytes))
        img.load()  # forzar decodificacion completa
    except (UnidentifiedImageError, Exception) as exc:
        raise ProcessingError("decode", f"Invalid or corrupt image: {exc}") from exc

    original_w, original_h = img.size
    original_mode = img.mode

    # Verificar megapixels (per D-05)
    if original_w * original_h > 25_000_000:
        raise ProcessingError(
            "decode",
            f"Image {original_w}x{original_h} exceeds maximum 25 megapixels "
            f"({original_w * original_h:,} pixels)",
        )

    # Aplicar EXIF transpose SIEMPRE, antes de cualquier otro procesamiento (per PIPE-02, D-08)
    img = ImageOps.exif_transpose(img)

    # Convertir CMYK a RGB silenciosamente (per D-07)
    if img.mode == "CMYK":
        img = img.convert("RGB")

    # Convertir a RGBA para el resto del pipeline
    img = img.convert("RGBA")

    logger.info(
        json.dumps(
            {
                "level": "info",
                "event": "decode_complete",
                "article_id": article_id,
                "original_size": f"{original_w}x{original_h}",
                "mode": original_mode,
            }
        )
    )

    return img, f"{original_w}x{original_h}", original_mode


# ---------------------------------------------------------------------------
# Step 2: remove_background
# ---------------------------------------------------------------------------


def remove_background(
    img: Image.Image,
    config: AppConfig,
    rembg_session,
) -> Image.Image:
    """Remueve el fondo de la imagen usando rembg.

    Si la imagen ya tiene >10% de pixeles transparentes, salta rembg (per D-06).
    """
    t_start = time.monotonic()

    # Deteccion de alpha pre-existente (per D-06)
    alpha_channel = img.split()[3]
    total_pixels = img.width * img.height
    # Contar pixeles con alpha < 128 (considerados transparentes)
    transparent_pixels = sum(1 for p in alpha_channel.getdata() if p < 128)  # type: ignore[arg-type]
    transparent_ratio = transparent_pixels / total_pixels

    if transparent_ratio > 0.10:
        duration_ms = int((time.monotonic() - t_start) * 1000)
        logger.info(
            json.dumps(
                {
                    "level": "info",
                    "event": "rembg_complete",
                    "duration_ms": duration_ms,
                    "skipped": True,
                    "reason": "pre-existing transparency",
                    "transparent_ratio": round(transparent_ratio, 3),
                }
            )
        )
        return img

    # Convertir a bytes PNG para rembg
    input_buf = BytesIO()
    img.save(input_buf, format="PNG")
    input_bytes = input_buf.getvalue()

    result_bytes = rembg.remove(
        input_bytes,
        session=rembg_session,
        alpha_matting=config.rembg.alpha_matting,
        alpha_matting_foreground_threshold=config.rembg.alpha_matting_foreground_threshold,
        alpha_matting_background_threshold=config.rembg.alpha_matting_background_threshold,
        alpha_matting_erode_size=config.rembg.alpha_matting_erode_size,
    )

    result = Image.open(BytesIO(result_bytes)).convert("RGBA")

    duration_ms = int((time.monotonic() - t_start) * 1000)
    logger.info(
        json.dumps(
            {
                "level": "info",
                "event": "rembg_complete",
                "duration_ms": duration_ms,
                "skipped": False,
            }
        )
    )

    return result


# ---------------------------------------------------------------------------
# Step 3: autocrop
# ---------------------------------------------------------------------------


def autocrop(img: Image.Image, config: AppConfig) -> Image.Image:
    """Recorta la imagen al bounding box del producto via canal alpha.

    Guard: si el area del bbox < 5% del total, skippea el crop.
    """
    if not config.autocrop.enabled:
        return img

    alpha = img.split()[3]
    # Binarizar alpha: 255 si opaco, 0 si transparente
    alpha = alpha.point(lambda p: 255 if p > config.autocrop.threshold else 0)

    bbox = alpha.getbbox()

    if bbox is None:
        return img

    # Guard: area del bbox vs area total (per spec: < 5% -> skip)
    bbox_area = (bbox[2] - bbox[0]) * (bbox[3] - bbox[1])
    total_area = img.width * img.height
    if bbox_area / total_area < 0.05:
        logger.warning(
            json.dumps(
                {
                    "level": "warning",
                    "event": "autocrop_skipped",
                    "reason": "product area too small",
                    "bbox_area_ratio": round(bbox_area / total_area, 4),
                }
            )
        )
        return img

    img = img.crop(bbox)

    logger.info(
        json.dumps(
            {
                "level": "info",
                "event": "autocrop_complete",
                "bbox": bbox,
                "cropped_size": f"{img.width}x{img.height}",
            }
        )
    )

    return img


# ---------------------------------------------------------------------------
# Step 4: calculate_scale_and_position
# ---------------------------------------------------------------------------


def calculate_scale_and_position(
    img: Image.Image,
    config: AppConfig,
) -> tuple[int, int, int, int]:
    """Calcula escala y posicion del producto en el canvas.

    Returns:
        (scaled_w, scaled_h, offset_x, offset_y)
    """
    canvas_px = config.output.size  # 800
    padding_px = int(canvas_px * config.padding.percent / 100) if config.padding.enabled else 0
    available_px = canvas_px - (2 * padding_px)  # 640 con padding 10%

    scale = min(available_px / img.width, available_px / img.height)

    scaled_w = int(img.width * scale)
    scaled_h = int(img.height * scale)

    offset_x = (canvas_px - scaled_w) // 2
    offset_y = (canvas_px - scaled_h) // 2

    return (scaled_w, scaled_h, offset_x, offset_y)


# ---------------------------------------------------------------------------
# Step 5: composite
# ---------------------------------------------------------------------------


def composite(img: Image.Image, config: AppConfig) -> Image.Image:
    """Escala el producto y lo compone sobre un canvas de fondo blanco (800x800 RGB)."""
    canvas_px = config.output.size
    padding_px = int(canvas_px * config.padding.percent / 100) if config.padding.enabled else 0
    available_px = canvas_px - (2 * padding_px)

    scale = min(available_px / img.width, available_px / img.height)

    scaled_w, scaled_h, offset_x, offset_y = calculate_scale_and_position(img, config)

    # LANCZOS para downscale (calidad maxima), BICUBIC para upscale
    resample = Image.LANCZOS if scale <= 1.0 else Image.BICUBIC
    scaled = img.resize((scaled_w, scaled_h), resample)

    canvas = Image.new(
        "RGB",
        (config.output.size, config.output.size),
        tuple(config.output.background_color),
    )

    # Pegar usando canal alpha como mascara
    canvas.paste(scaled, (offset_x, offset_y), mask=scaled.split()[3])

    logger.info(
        json.dumps(
            {
                "level": "info",
                "event": "composite_complete",
                "canvas_size": f"{config.output.size}x{config.output.size}",
                "product_size": f"{scaled_w}x{scaled_h}",
            }
        )
    )

    return canvas


# ---------------------------------------------------------------------------
# Step 6: enhance
# ---------------------------------------------------------------------------


def enhance(img: Image.Image, config: AppConfig) -> Image.Image:
    """Aplica mejoras de brillo y contraste.

    Optimizacion: si ambos factores son 1.0, retorna la imagen sin cambios.
    """
    if config.enhancement.brightness == 1.0 and config.enhancement.contrast == 1.0:
        return img

    if config.enhancement.brightness != 1.0:
        img = ImageEnhance.Brightness(img).enhance(config.enhancement.brightness)

    if config.enhancement.contrast != 1.0:
        img = ImageEnhance.Contrast(img).enhance(config.enhancement.contrast)

    logger.info(
        json.dumps(
            {
                "level": "info",
                "event": "enhance_complete",
                "brightness": config.enhancement.brightness,
                "contrast": config.enhancement.contrast,
            }
        )
    )

    return img


# ---------------------------------------------------------------------------
# Step 7: encode_webp
# ---------------------------------------------------------------------------


def encode_webp(img: Image.Image, config: AppConfig) -> bytes:
    """Codifica la imagen a bytes WebP con la calidad configurada.

    quality=0 activa modo lossless.
    """
    buf = BytesIO()

    if config.output.quality == 0:
        img.save(buf, format="WEBP", lossless=True)
    else:
        img.save(buf, format="WEBP", quality=config.output.quality)

    logger.info(
        json.dumps(
            {
                "level": "info",
                "event": "encode_complete",
                "format": "webp",
                "size_bytes": buf.tell(),
            }
        )
    )

    return buf.getvalue()


# ---------------------------------------------------------------------------
# Funcion principal: process_image
# ---------------------------------------------------------------------------


def process_image(
    image_bytes: bytes,
    article_id: str,
    config: AppConfig,
    rembg_session,
) -> ProcessingResult:
    """Ejecuta el pipeline completo de procesamiento de imagenes.

    Pipeline: decode -> rembg -> autocrop -> scale -> composite -> enhance -> encode

    IMPORTANTE: Esta funcion es SINCRONA (CPU-bound). Llamar desde asyncio con
    asyncio.to_thread(process_image, ...) para no bloquear el event loop.

    Args:
        image_bytes: Bytes de la imagen de entrada (cualquier formato soportado)
        article_id: Identificador del articulo para logging y resultado
        config: Configuracion completa de la aplicacion
        rembg_session: Sesion global de rembg (inicializada una vez en startup)

    Returns:
        ProcessingResult con imagen WebP y metadatos del procesamiento

    Raises:
        ProcessingError: si cualquier step del pipeline falla (per D-09 fail-fast)
    """
    start = time.monotonic()
    steps_applied: list[str] = []

    try:
        # Step 1: decode
        img, original_size, original_mode = decode_and_validate(image_bytes, config, article_id)
        steps_applied.append("decode")

        # Step 2: rembg
        img = remove_background(img, config, rembg_session)
        steps_applied.append("rembg")

        # Step 3: autocrop
        if config.autocrop.enabled:
            img = autocrop(img, config)
            steps_applied.append("autocrop")

        # Step 4+5: scale + composite (se calculan en composite)
        img = composite(img, config)
        steps_applied.append("scale")
        steps_applied.append("composite")

        # Step 6: enhance (solo si se aplica)
        if config.enhancement.brightness != 1.0 or config.enhancement.contrast != 1.0:
            img = enhance(img, config)
            steps_applied.append("enhance")
        else:
            # Llamar igual para que sea consistente pero sin append si no hubo cambio
            img = enhance(img, config)

        # Step 7: encode
        result_bytes = encode_webp(img, config)
        steps_applied.append("encode")

    except ProcessingError:
        raise
    except Exception as exc:
        raise ProcessingError(step="unknown", detail=str(exc)) from exc

    elapsed_ms = int((time.monotonic() - start) * 1000)

    return ProcessingResult(
        image_bytes=result_bytes,
        article_id=article_id,
        processing_time_ms=elapsed_ms,
        model_used=config.rembg.model,
        original_size=original_size,
        output_size=f"{config.output.size}x{config.output.size}",
        steps_applied=steps_applied,
    )
