"""FastAPI app con lifespan para Image Standardizer Service.

Inicializa en startup:
  - ConfigManager (YAML config con hot-reload via watchdog)
  - Sesion rembg GLOBAL (cargada una sola vez — nunca por request)
  - JobQueue (asyncio.Semaphore con max_concurrent desde config)
  - Watchdog Observer (hot-reload de config.yaml sin restart — CONF-05)

Orden de inicializacion obligatorio:
  1. Config
  2. rembg session (usa config.rembg.model)
  3. JobQueue (usa config.queue.*)
  4. startup_time
  5. Watchdog Observer
"""
import asyncio
import json
import logging
import threading
import time
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from rembg import new_session
from watchdog.events import FileSystemEventHandler
from watchdog.observers import Observer

from app.config import ConfigManager
from app.queue import JobQueue

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Watchdog handler para hot-reload de config.yaml (CONF-05)
# ---------------------------------------------------------------------------

class ConfigReloadHandler(FileSystemEventHandler):
    """Detecta cambios en settings.yaml y recarga config via bridge asyncio. Per CONF-05."""

    def __init__(self, loop: asyncio.AbstractEventLoop, app: FastAPI, suppress_flag: threading.Event):
        self._loop = loop
        self._app = app
        self._suppress_flag = suppress_flag

    def on_modified(self, event):
        if not event.src_path.endswith("settings.yaml"):
            return
        # D-07: si el flag de supresion esta activo, ignorar este evento (fue escrito por POST /config)
        # Usa ventana de tiempo (2s) en lugar de clear inmediato porque inotify en Linux
        # puede disparar multiples IN_MODIFY para una sola escritura.
        if self._suppress_flag.is_set():
            logger.info(json.dumps({
                "level": "info",
                "event": "watchdog_suppressed",
                "detail": "Ignoring filesystem event — config was written by API",
            }))
            return
        # Bridge thread → asyncio event loop
        asyncio.run_coroutine_threadsafe(
            _reload_config(self._app),
            self._loop,
        )


# ---------------------------------------------------------------------------
# Funciones async de modulo para reload y model swap
# ---------------------------------------------------------------------------

async def _reload_config(app: FastAPI) -> None:
    """Recarga config desde YAML. Se ejecuta en el event loop. Per D-08."""
    try:
        app.state.config_manager.reload()
        new_model = app.state.config_manager.config.rembg.model
        old_model = app.state.model_name

        logger.info(json.dumps({
            "level": "info",
            "event": "config_reloaded",
            "source": "watchdog",
            "model": new_model,
        }))

        # Si el modelo cambio via edicion del YAML, disparar swap
        if old_model != new_model:
            asyncio.create_task(_swap_rembg_session(app, new_model))
    except Exception as e:
        logger.error(json.dumps({
            "level": "error",
            "event": "config_reload_failed",
            "source": "watchdog",
            "error": str(e),
        }))


async def _swap_rembg_session(app: FastAPI, new_model: str) -> None:
    """
    Swap graceful de sesion rembg.
    D-01: app.state.model_swapping = True bloquea cola con 503.
    D-02: Si new_session falla, sesion vieja sigue activa.
    """
    app.state.model_swapping = True
    try:
        # Esperar que termine el job activo usando el semaphore como barrier
        queue = app.state.job_queue
        timeout = app.state.config_manager.config.queue.timeout_seconds + 10
        try:
            await asyncio.wait_for(queue._semaphore.acquire(), timeout=timeout)
            queue._semaphore.release()
        except asyncio.TimeoutError:
            logger.error(json.dumps({
                "level": "error",
                "event": "model_swap_timeout",
                "new_model": new_model,
                "detail": f"Waited {timeout}s for active job to finish",
            }))
            return  # Abortar swap — sesion vieja sigue activa (D-02)

        # Cargar nueva sesion en thread (CPU-bound — per constraint asyncio.to_thread)
        new_sess = await asyncio.to_thread(new_session, new_model)

        # Swap atomico de referencia
        app.state.rembg_session = new_sess
        app.state.model_name = new_model

        logger.info(json.dumps({
            "level": "info",
            "event": "model_swapped",
            "new_model": new_model,
        }))
    except Exception as e:
        # D-02: no modificar rembg_session — sesion vieja sigue activa
        logger.error(json.dumps({
            "level": "error",
            "event": "model_swap_failed",
            "new_model": new_model,
            "error": str(e),
        }))
    finally:
        app.state.model_swapping = False


# ---------------------------------------------------------------------------
# Lifespan
# ---------------------------------------------------------------------------

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Inicializa recursos globales al startup, limpia al shutdown."""
    start = time.monotonic()

    # 1. Cargar config
    config_manager = ConfigManager()
    app.state.config_manager = config_manager
    config = config_manager.config

    logger.info(json.dumps({
        "level": "info",
        "event": "config_loaded",
        "model": config.rembg.model,
    }))

    # 2. Inicializar sesion rembg GLOBAL (una sola vez, NUNCA por request)
    # OMP_NUM_THREADS debe estar seteado en el environment (Dockerfile)
    rembg_session = new_session(config.rembg.model)
    app.state.rembg_session = rembg_session
    app.state.model_loaded = True
    app.state.model_name = config.rembg.model

    logger.info(json.dumps({
        "level": "info",
        "event": "rembg_session_ready",
        "model": config.rembg.model,
    }))

    # 3. Inicializar job queue
    queue = JobQueue(
        max_concurrent=config.queue.max_concurrent,
        max_queue_size=config.queue.max_queue_size,
        timeout_seconds=config.queue.timeout_seconds,
    )
    app.state.job_queue = queue

    # 4. Guardar startup time para /health uptime
    app.state.startup_time = time.monotonic()

    logger.info(json.dumps({
        "level": "info",
        "event": "startup_complete",
        "elapsed_ms": int((time.monotonic() - start) * 1000),
    }))

    # 5. Watchdog para hot-reload de config (CONF-05)
    loop = asyncio.get_running_loop()  # Python 3.12+ — no usar get_event_loop()
    suppress_flag = threading.Event()
    app.state.watchdog_suppress_flag = suppress_flag
    app.state.model_swapping = False

    config_dir = str(Path(config_manager._config_path).parent)
    handler = ConfigReloadHandler(loop, app, suppress_flag)
    observer = Observer()
    observer.schedule(handler, path=config_dir, recursive=False)
    observer.start()
    app.state.watchdog_observer = observer

    logger.info(json.dumps({
        "level": "info",
        "event": "watchdog_started",
        "watch_path": config_dir,
    }))

    yield

    # Shutdown — detener watchdog primero
    observer.stop()
    observer.join()
    logger.info(json.dumps({"level": "info", "event": "shutdown"}))


app = FastAPI(
    title="Image Standardizer",
    version="1.0.0",
    lifespan=lifespan,
)

# Importar y registrar routers
from app.router_api import router as api_router  # noqa: E402
app.include_router(api_router)

from app.router_config import router as config_router  # noqa: E402
app.include_router(config_router)
