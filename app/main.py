"""FastAPI app con lifespan para Image Standardizer Service.

Inicializa en startup:
  - ConfigManager (YAML config con hot-reload futuro)
  - Sesion rembg GLOBAL (cargada una sola vez — nunca por request)
  - JobQueue (asyncio.Semaphore con max_concurrent desde config)

Orden de inicializacion obligatorio:
  1. Config
  2. rembg session (usa config.rembg.model)
  3. JobQueue (usa config.queue.*)
"""
import json
import logging
import time
from contextlib import asynccontextmanager

from fastapi import FastAPI
from rembg import new_session

from app.config import ConfigManager
from app.queue import JobQueue

logger = logging.getLogger(__name__)


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

    yield

    # Shutdown
    logger.info(json.dumps({"level": "info", "event": "shutdown"}))


app = FastAPI(
    title="Image Standardizer",
    version="1.0.0",
    lifespan=lifespan,
)

# Importar y registrar routers
from app.router_api import router as api_router  # noqa: E402
app.include_router(api_router)
