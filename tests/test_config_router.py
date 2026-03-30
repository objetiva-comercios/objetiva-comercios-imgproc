"""
Tests de integracion para los endpoints de configuracion y status.

Cubre:
- GET /config: retorna configuracion activa completa (CONF-02)
- POST /config: deep merge, persistencia YAML, rechazo de invalidos (CONF-03)
- GET /status: metricas operacionales e historial con original_size/output_size (API-06, QUEUE-05)
"""
import time
import pytest
import yaml
from collections import deque
from contextlib import asynccontextmanager
from datetime import datetime, timezone

from fastapi import FastAPI
from httpx import AsyncClient, ASGITransport

from app.config import ConfigManager
from app.queue import JobQueue, JobRecord, QueueState
from app.router_config import router as config_router


# ---------------------------------------------------------------------------
# Lifespan de test (sin rembg real)
# ---------------------------------------------------------------------------

@asynccontextmanager
async def _mock_lifespan(app: FastAPI):
    yield


# ---------------------------------------------------------------------------
# Fixture: app de test con ConfigManager apuntando a YAML temporal
# ---------------------------------------------------------------------------

@pytest.fixture
def test_app(tmp_path):
    """App de test con ConfigManager apuntando a YAML temporal."""
    settings = {
        "rembg": {
            "model": "isnet-general-use",
            "alpha_matting": False,
            "alpha_matting_foreground_threshold": 240,
            "alpha_matting_background_threshold": 10,
            "alpha_matting_erode_size": 10,
        },
        "output": {"size": 800, "format": "webp", "quality": 85, "background_color": [255, 255, 255]},
        "padding": {"enabled": True, "percent": 10},
        "autocrop": {"enabled": True, "threshold": 10},
        "enhancement": {"brightness": 1.0, "contrast": 1.0},
        "queue": {"max_concurrent": 1, "max_queue_size": 10, "timeout_seconds": 120},
        "server": {"host": "0.0.0.0", "port": 8010, "log_level": "info"},
    }
    yaml_path = tmp_path / "settings.yaml"
    with open(yaml_path, "w") as f:
        yaml.dump(settings, f)

    app = FastAPI(lifespan=_mock_lifespan)
    app.include_router(config_router)

    cm = ConfigManager(config_path=str(yaml_path))
    app.state.config_manager = cm
    app.state.job_queue = JobQueue(max_concurrent=1, max_queue_size=10, timeout_seconds=120)
    app.state.model_loaded = True
    app.state.model_name = "isnet-general-use"
    app.state.startup_time = time.monotonic()

    return app


# ---------------------------------------------------------------------------
# GET /config
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_get_config(test_app):
    """GET /config retorna 200 con las claves principales de la configuracion."""
    async with AsyncClient(transport=ASGITransport(app=test_app), base_url="http://test") as client:
        response = await client.get("/config")

    assert response.status_code == 200
    body = response.json()
    assert "rembg" in body
    assert "output" in body
    assert "padding" in body
    assert "autocrop" in body
    assert "enhancement" in body
    assert "queue" in body
    assert "server" in body


# ---------------------------------------------------------------------------
# POST /config — deep merge
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_post_config_merge(test_app):
    """POST /config con {"output": {"quality": 95}} actualiza solo quality, el resto sin cambios."""
    async with AsyncClient(transport=ASGITransport(app=test_app), base_url="http://test") as client:
        response = await client.post("/config", json={"output": {"quality": 95}})

    assert response.status_code == 200
    body = response.json()
    assert body["output"]["quality"] == 95
    # El resto de output no debe cambiar
    assert body["output"]["size"] == 800
    assert body["output"]["format"] == "webp"
    # El modelo rembg no debe cambiar
    assert body["rembg"]["model"] == "isnet-general-use"


# ---------------------------------------------------------------------------
# POST /config — persistencia en disco
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_post_config_persist_yaml(test_app, tmp_path):
    """POST /config escribe el YAML en disco; releer el archivo muestra el valor actualizado."""
    async with AsyncClient(transport=ASGITransport(app=test_app), base_url="http://test") as client:
        response = await client.post("/config", json={"output": {"quality": 90}})

    assert response.status_code == 200

    # Obtener la ruta del YAML del ConfigManager
    yaml_path = test_app.state.config_manager._config_path
    with open(yaml_path) as f:
        saved = yaml.safe_load(f)

    assert saved["output"]["quality"] == 90


# ---------------------------------------------------------------------------
# POST /config — rechazo de invalidos
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_post_config_invalid_rejects_all(test_app):
    """POST /config con tipo invalido retorna 422 con error validation_error."""
    async with AsyncClient(transport=ASGITransport(app=test_app), base_url="http://test") as client:
        response = await client.post("/config", json={"output": {"quality": "no-es-int"}})

    assert response.status_code == 422
    body = response.json()
    assert body["error"] == "validation_error"
    # Verificar que la config no cambio
    assert test_app.state.config_manager.config.output.quality == 85


@pytest.mark.asyncio
async def test_post_config_invalid_model(test_app):
    """POST /config con modelo rembg no reconocido retorna 422 con error invalid_model."""
    async with AsyncClient(transport=ASGITransport(app=test_app), base_url="http://test") as client:
        response = await client.post("/config", json={"rembg": {"model": "modelo-inventado"}})

    assert response.status_code == 422
    body = response.json()
    assert body["error"] == "invalid_model"
    assert "modelo-inventado" in body["detail"]


# ---------------------------------------------------------------------------
# GET /status — estado inicial vacio
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_get_status_empty(test_app):
    """GET /status retorna 200 con metricas en cero y historial vacio."""
    async with AsyncClient(transport=ASGITransport(app=test_app), base_url="http://test") as client:
        response = await client.get("/status")

    assert response.status_code == 200
    body = response.json()
    assert body["total_processed"] == 0
    assert body["total_errors"] == 0
    assert body["avg_processing_time_ms"] == 0
    assert body["job_history"] == []


# ---------------------------------------------------------------------------
# GET /status — con historial inyectado
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_get_status_with_history(test_app):
    """Inyectar JobRecords en el historial; GET /status retorna historial con original_size y output_size."""
    test_app.state.job_queue.state.job_history.append(JobRecord(
        article_id="art-1",
        status="completed",
        processing_time_ms=150,
        model_used="isnet-general-use",
        timestamp=datetime.now(timezone.utc).isoformat(),
        original_size="200x150",
        output_size="800x800",
    ))

    async with AsyncClient(transport=ASGITransport(app=test_app), base_url="http://test") as client:
        response = await client.get("/status")

    assert response.status_code == 200
    body = response.json()
    assert len(body["job_history"]) == 1
    item = body["job_history"][0]
    assert item["article_id"] == "art-1"
    assert item["original_size"] == "200x150"
    assert item["output_size"] == "800x800"
    assert item["status"] == "completed"


# ---------------------------------------------------------------------------
# GET /status — calculo de promedio
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_status_avg_calculation(test_app):
    """Inyectar 3 jobs completados con tiempos 100, 200, 300ms; avg debe ser 200."""
    now = datetime.now(timezone.utc).isoformat()
    for ms in [100, 200, 300]:
        test_app.state.job_queue.state.job_history.append(JobRecord(
            article_id=f"art-{ms}",
            status="completed",
            processing_time_ms=ms,
            model_used="isnet-general-use",
            timestamp=now,
            original_size="100x100",
            output_size="800x800",
        ))

    async with AsyncClient(transport=ASGITransport(app=test_app), base_url="http://test") as client:
        response = await client.get("/status")

    assert response.status_code == 200
    body = response.json()
    assert body["avg_processing_time_ms"] == 200
    assert body["total_processed"] == 0   # contadores del queue no se tocan al inyectar directo
    assert len(body["job_history"]) == 3
