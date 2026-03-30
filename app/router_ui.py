"""Endpoint de la Web UI de configuracion.

Endpoint:
  GET /ui — Retorna la interfaz HTML de configuracion (UI-01)
"""
from pathlib import Path

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from app.models import AppConfig
from app.router_config import VALID_MODELS

router = APIRouter()

_TEMPLATES_DIR = Path(__file__).parent / "templates"
templates = Jinja2Templates(directory=str(_TEMPLATES_DIR))


@router.get("/ui", response_class=HTMLResponse)
async def ui_endpoint(request: Request):
    """
    Retorna la Web UI de configuracion como HTML autocontenido.

    Pasa al template:
      - config: configuracion activa como dict
      - config_defaults: valores por defecto de AppConfig
      - valid_models: lista ordenada de modelos rembg disponibles
    """
    config = request.app.state.config_manager.config
    return templates.TemplateResponse(
        request=request,
        name="ui.html",
        context={
            "config": config.model_dump(),
            "config_defaults": AppConfig().model_dump(),
            "valid_models": sorted(VALID_MODELS),
        },
    )
