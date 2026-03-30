"""
Tests para watchdog hot-reload, flag de supresion y model swap graceful.

Cubre:
- CONF-05: Hot-reload via watchdog (editar YAML recarga config automaticamente)
- CONF-05: Flag de supresion (POST /config no genera double-reload)
- CONF-04: Model swap graceful con 503 durante el proceso
- D-01: POST /process retorna 503 cuando model_swapping es True
- D-02: Si new_session falla, sesion vieja sigue activa
"""
import asyncio
import threading
import time
import yaml
import pytest
from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, MagicMock, patch

from fastapi import FastAPI
from httpx import AsyncClient, ASGITransport

from app.config import ConfigManager
from app.queue import JobQueue
from app.router_config import router as config_router
from app.router_api import router as api_router
from app.main import ConfigReloadHandler, _reload_config, _swap_rembg_session
from watchdog.observers import Observer


# ---------------------------------------------------------------------------
# Fixture con watchdog real
# ---------------------------------------------------------------------------

@pytest.fixture
async def app_with_watchdog(tmp_path):
    """App de test con watchdog Observer real apuntando a tmp_path."""
    settings = {
        "rembg": {"model": "isnet-general-use"},
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

    @asynccontextmanager
    async def noop_lifespan(app):
        yield

    app = FastAPI(lifespan=noop_lifespan)
    app.include_router(config_router)
    app.include_router(api_router)

    cm = ConfigManager(config_path=str(yaml_path))
    app.state.config_manager = cm
    app.state.job_queue = JobQueue(max_concurrent=1, max_queue_size=10, timeout_seconds=120)
    app.state.model_loaded = True
    app.state.model_name = "isnet-general-use"
    app.state.startup_time = time.monotonic()
    app.state.model_swapping = False
    app.state.rembg_session = MagicMock()  # sesion mock, no real rembg

    loop = asyncio.get_running_loop()
    suppress_flag = threading.Event()
    app.state.watchdog_suppress_flag = suppress_flag

    handler = ConfigReloadHandler(loop, app, suppress_flag)
    observer = Observer()
    observer.schedule(handler, path=str(tmp_path), recursive=False)
    observer.start()
    app.state.watchdog_observer = observer

    yield app, yaml_path

    observer.stop()
    observer.join()


# ---------------------------------------------------------------------------
# test_watchdog_reload
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_watchdog_reload(app_with_watchdog):
    """Editar settings.yaml en disco recarga config automaticamente (CONF-05)."""
    app, yaml_path = app_with_watchdog
    assert app.state.config_manager.config.output.quality == 85

    # Escribir YAML con quality modificada
    settings = {
        "rembg": {"model": "isnet-general-use"},
        "output": {"size": 800, "format": "webp", "quality": 70, "background_color": [255, 255, 255]},
        "padding": {"enabled": True, "percent": 10},
        "autocrop": {"enabled": True, "threshold": 10},
        "enhancement": {"brightness": 1.0, "contrast": 1.0},
        "queue": {"max_concurrent": 1, "max_queue_size": 10, "timeout_seconds": 120},
        "server": {"host": "0.0.0.0", "port": 8010, "log_level": "info"},
    }
    with open(yaml_path, "w") as f:
        yaml.dump(settings, f)

    # Polling hasta 3 segundos para que watchdog detecte y recargue
    deadline = time.monotonic() + 3.0
    while time.monotonic() < deadline:
        await asyncio.sleep(0.2)
        if app.state.config_manager.config.output.quality == 70:
            break

    assert app.state.config_manager.config.output.quality == 70, (
        f"Expected quality=70, got {app.state.config_manager.config.output.quality}"
    )


# ---------------------------------------------------------------------------
# test_no_double_reload_after_post
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_no_double_reload_after_post(app_with_watchdog):
    """POST /config no debe disparar _reload_config via watchdog (flag de supresion funciona)."""
    app, yaml_path = app_with_watchdog

    with patch("app.main._reload_config", new_callable=AsyncMock) as mock_reload:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post("/config", json={"output": {"quality": 60}})

        assert response.status_code == 200

        # Esperar 1.5 segundos para dar tiempo al watchdog de procesar el evento
        await asyncio.sleep(1.5)

        # El flag de supresion debio haber evitado que _reload_config se llamara
        mock_reload.assert_not_called()


# ---------------------------------------------------------------------------
# test_model_swap_sets_flag
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_model_swap_sets_flag(app_with_watchdog):
    """_swap_rembg_session setea model_swapping=True durante el swap y False al terminar."""
    app, yaml_path = app_with_watchdog

    with patch("rembg.new_session", return_value=MagicMock()) as mock_new_session:
        await _swap_rembg_session(app, "birefnet-general-lite")

    # Al terminar, model_swapping debe ser False (el finally lo reseteo)
    assert app.state.model_swapping is False
    # El model_name debe estar actualizado
    assert app.state.model_name == "birefnet-general-lite"


# ---------------------------------------------------------------------------
# test_process_503_during_swap
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_process_503_during_swap(app_with_watchdog):
    """POST /process retorna 503 con error 'model_swapping' cuando model_swapping es True."""
    app, yaml_path = app_with_watchdog

    # Simular que hay un swap en curso
    app.state.model_swapping = True

    import io
    from PIL import Image

    buf = io.BytesIO()
    img = Image.new("RGB", (100, 100), (255, 0, 0))
    img.save(buf, format="JPEG")
    image_bytes = buf.getvalue()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post(
            "/process",
            files={"image": ("test.jpg", image_bytes, "image/jpeg")},
            data={"article_id": "test-art-001"},
        )

    assert response.status_code == 503
    body = response.json()
    assert body["error"] == "model_swapping"

    # Limpiar
    app.state.model_swapping = False


# ---------------------------------------------------------------------------
# test_model_swap_failure_keeps_old_session
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_model_swap_failure_keeps_old_session(app_with_watchdog):
    """Si new_session() falla, la sesion vieja sigue en app.state.rembg_session (D-02)."""
    app, yaml_path = app_with_watchdog

    old_session = app.state.rembg_session

    with patch("rembg.new_session", side_effect=RuntimeError("download failed")):
        await _swap_rembg_session(app, "modelo-que-falla")

    # La sesion vieja debe seguir activa (D-02)
    assert app.state.rembg_session is old_session
    # model_swapping debe ser False (el finally lo reseteo)
    assert app.state.model_swapping is False
