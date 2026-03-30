"""Endpoints HTTP de la API del Image Standardizer Service.

Endpoints:
  POST /process  — Recibe imagen + article_id, retorna WebP estandarizado
  GET  /health   — Health check con estado de la cola y modelo

Per:
  - API-01: POST /process acepta multipart/form-data con image file y article_id
  - API-02: POST /process retorna image/webp con 6 headers X-* de metadata
  - API-03: POST /process acepta override parcial de config como JSON string
  - API-04: POST /process retorna 400, 422, 503, 504 segun el caso con JSON estructurado
  - API-05: GET /health retorna status, queue state, model info y uptime
"""
import json
import logging
import time
from typing import Optional

from fastapi import APIRouter, File, Form, Request, Response, UploadFile
from fastapi.responses import JSONResponse

from app.models import AppConfig, ErrorResponse
from app.processor import ProcessingError, process_image
from app.queue import QueueFullError, QueueTimeoutError

logger = logging.getLogger(__name__)
router = APIRouter()


def _deep_merge(base: dict, override: dict) -> None:
    """Deep merge override into base dict (in-place)."""
    for key, value in override.items():
        if key in base and isinstance(base[key], dict) and isinstance(value, dict):
            _deep_merge(base[key], value)
        else:
            base[key] = value


@router.post("/process")
async def process_endpoint(
    request: Request,
    image: UploadFile = File(...),
    article_id: str = Form(...),
    override: Optional[str] = Form(default=None),
):
    """
    Procesa una imagen de producto y retorna WebP estandarizado.

    - Acepta multipart/form-data con image file y article_id string (per API-01)
    - Acepta override parcial de config como JSON string (per API-03)
    - Retorna image/webp con 6 headers X-* de metadata (per API-02)
    - Maneja errores 400, 422, 503, 504 con JSON estructurado (per API-04)
    """
    queue = request.app.state.job_queue
    config_manager = request.app.state.config_manager
    rembg_session = request.app.state.rembg_session

    # Tomar snapshot del config (per CONF-06 — inmutable para este job)
    config_snapshot = config_manager.get_snapshot()

    # Aplicar override parcial si viene (per API-03)
    if override:
        try:
            override_dict = json.loads(override)
            # Deep merge: convertir config a dict, mergear, recrear
            config_dict = config_snapshot.model_dump()
            _deep_merge(config_dict, override_dict)
            config_snapshot = AppConfig(**config_dict)
        except (json.JSONDecodeError, Exception) as e:
            return JSONResponse(
                status_code=422,
                content=ErrorResponse(
                    error="invalid_override",
                    detail=f"Invalid override JSON: {str(e)}",
                    article_id=article_id,
                ).model_dump(),
            )

    # Leer bytes de la imagen
    image_bytes = await image.read()

    try:
        result = await queue.submit_job(
            process_fn=process_image,
            image_bytes=image_bytes,
            article_id=article_id,
            config_snapshot=config_snapshot,
            rembg_session=rembg_session,
        )

        # Retornar WebP con headers de metadata (per API-02)
        return Response(
            content=result.image_bytes,
            media_type="image/webp",
            headers={
                "X-Article-Id": result.article_id,
                "X-Processing-Time-Ms": str(result.processing_time_ms),
                "X-Model-Used": result.model_used,
                "X-Original-Size": result.original_size,
                "X-Output-Size": result.output_size,
                "X-Steps-Applied": ",".join(result.steps_applied),
            },
        )

    except QueueFullError:
        return JSONResponse(
            status_code=503,
            content=ErrorResponse(
                error="queue_full",
                detail="Service busy, try again later",
                article_id=article_id,
            ).model_dump(),
        )

    except QueueTimeoutError:
        return JSONResponse(
            status_code=504,
            content=ErrorResponse(
                error="queue_timeout",
                detail="Request timed out waiting in queue",
                article_id=article_id,
            ).model_dump(),
        )

    except ProcessingError as e:
        # Per D-09: fail fast con detalle del step
        # decode errors -> 400 (imagen invalida, input del usuario)
        # otros steps -> 500 (error interno del pipeline)
        status = 400 if e.step == "decode" else 500
        return JSONResponse(
            status_code=status,
            content=ErrorResponse(
                error=f"processing_error_{e.step}",
                detail=e.detail if e.step == "decode" else f"Processing failed at step: {e.step}",
                article_id=article_id,
            ).model_dump(),
        )

    except Exception as e:
        logger.error(json.dumps({
            "level": "error",
            "event": "unhandled_error",
            "article_id": article_id,
            "error": str(e),
        }))
        return JSONResponse(
            status_code=500,
            content=ErrorResponse(
                error="internal_error",
                detail="Internal server error",
                article_id=article_id,
            ).model_dump(),
        )


@router.get("/health")
async def health_endpoint(request: Request):
    """
    Health check rapido (per API-05).

    Lee app.state directamente, sin tocar el queue.
    Retorna: status, queue state, model info, uptime_seconds.
    """
    queue = request.app.state.job_queue
    uptime = int(time.monotonic() - request.app.state.startup_time)

    return {
        "status": "ok",
        "queue": {
            "active_jobs": queue.state.active_jobs,
            "queued_jobs": queue.state.queued_jobs,
            "max_concurrent": queue.max_concurrent,
            "max_queue_size": queue._max_queue_size,
        },
        "model_loaded": request.app.state.model_loaded,
        "model_name": request.app.state.model_name,
        "uptime_seconds": uptime,
    }
