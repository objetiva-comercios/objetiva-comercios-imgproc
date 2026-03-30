"""Endpoints de configuracion y status del servicio.

Endpoints:
  GET  /config  — Retorna configuracion activa como JSON (CONF-02)
  POST /config  — Actualiza config con deep merge, persiste YAML (CONF-03)
  GET  /status  — Metricas operacionales e historial de jobs (API-06)
"""
import asyncio
import json
import logging

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from app.models import AppConfig
from app.router_api import _deep_merge

logger = logging.getLogger(__name__)
router = APIRouter()

# Whitelist de modelos validos para rembg
try:
    from rembg.sessions import sessions_names
    VALID_MODELS = frozenset(sessions_names)
except ImportError:
    VALID_MODELS = frozenset([
        "u2net", "u2netp", "u2net_human_seg", "u2net_cloth_seg",
        "silueta", "isnet-general-use", "isnet-anime",
        "birefnet-general", "birefnet-general-lite", "birefnet-portrait",
        "birefnet-dis", "birefnet-hrsod", "birefnet-cod", "birefnet-massive",
        "sam", "bria-rmbg", "ben2-base",
    ])


@router.get("/config")
async def get_config(request: Request):
    """CONF-02: Retorna la configuracion activa como JSON."""
    return request.app.state.config_manager.config.model_dump()


@router.post("/config")
async def update_config(request: Request):
    """
    CONF-03: Actualiza la configuracion activa con deep merge y persiste en YAML.

    - Acepta JSON parcial — solo se actualizan los campos indicados
    - Valida el modelo rembg contra la whitelist antes de aplicar cambios
    - Valida el resultado con Pydantic — si falla, rechaza TODO el request (D-03)
    - Retorna la configuracion actualizada como JSON
    """
    config_manager = request.app.state.config_manager

    try:
        body = await request.json()
    except Exception as e:
        return JSONResponse(
            status_code=422,
            content={"error": "invalid_json", "detail": str(e)},
        )

    # Validar modelo rembg contra whitelist si viene en el body (D-04)
    rembg_override = body.get("rembg", {})
    if isinstance(rembg_override, dict) and "model" in rembg_override:
        requested_model = rembg_override["model"]
        if requested_model not in VALID_MODELS:
            return JSONResponse(
                status_code=422,
                content={
                    "error": "invalid_model",
                    "detail": f"Model '{requested_model}' not in whitelist. Valid: {sorted(VALID_MODELS)}",
                },
            )

    # Deep merge del body sobre la config actual
    current_dict = config_manager.config.model_dump()
    _deep_merge(current_dict, body)

    # Validacion estricta con Pydantic (D-03): si falla, rechazar todo
    try:
        new_config = AppConfig(**current_dict)
    except Exception as e:
        return JSONResponse(
            status_code=422,
            content={"error": "validation_error", "detail": str(e)},
        )

    # Detectar cambio de modelo ANTES de persistir
    old_model = request.app.state.model_name
    new_model = new_config.rembg.model
    model_changed = old_model != new_model

    # D-07: Activar flag de supresion ANTES de escribir YAML (evita double-reload via watchdog)
    # Se limpia con timer de 2s porque inotify en Linux puede disparar multiples IN_MODIFY
    suppress_flag = getattr(request.app.state, "watchdog_suppress_flag", None)
    if suppress_flag:
        suppress_flag.set()

    # Persistir config en YAML y actualizar estado en memoria
    config_manager.update_config(new_config)

    # Limpiar suppress_flag despues de 2s para permitir detecciones futuras de watchdog
    if suppress_flag:
        async def _clear_suppress():
            await asyncio.sleep(2)
            suppress_flag.clear()
        asyncio.create_task(_clear_suppress())

    logger.info(json.dumps({
        "event": "config_reloaded",
        "source": "api",
        "model": new_config.rembg.model,
        "model_changed": model_changed,
    }))

    # CONF-04: Si el modelo cambio, disparar swap de sesion ONNX
    if model_changed:
        from app.main import _swap_rembg_session
        asyncio.create_task(_swap_rembg_session(request.app, new_model))

    return config_manager.config.model_dump()


@router.get("/status")
async def status_endpoint(request: Request):
    """
    API-06: Retorna metricas operacionales e historial de jobs.

    Incluye:
    - total_processed, total_errors, avg_processing_time_ms
    - Historial de los ultimos 50 jobs (mas reciente primero)
    - Cada job incluye original_size y output_size (D-06)
    """
    queue = request.app.state.job_queue
    state = queue.state
    history = list(state.job_history)

    completed = [j for j in history if j.status == "completed"]
    avg_ms = (
        int(sum(j.processing_time_ms for j in completed) / len(completed))
        if completed else 0
    )

    return {
        "total_processed": state.total_processed,
        "total_errors": state.total_errors,
        "avg_processing_time_ms": avg_ms,
        "job_history": [
            {
                "article_id": j.article_id,
                "status": j.status,
                "processing_time_ms": j.processing_time_ms,
                "model_used": j.model_used,
                "original_size": j.original_size,
                "output_size": j.output_size,
                "timestamp": j.timestamp,
                "error": j.error,
            }
            for j in reversed(history)
        ],
    }
