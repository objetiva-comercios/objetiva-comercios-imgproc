"""
Tests de integracion de la API HTTP del Image Standardizer Service.

Cubre:
- POST /process: exito, headers X-*, override parcial, errores 400/422/503/504
- GET /health: estado completo de la cola y modelo

Todos los tests mockean rembg.new_session y submit_job para evitar
cargar el modelo ONNX en tests (pesado, lento, no requerido para testear la API).
"""
import io
import json
import pytest
from contextlib import asynccontextmanager
from httpx import AsyncClient, ASGITransport
from unittest.mock import patch, MagicMock, AsyncMock
from PIL import Image

from app.main import app
from app.models import ProcessingResult
from app.queue import QueueFullError, QueueTimeoutError
from app.processor import ProcessingError


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_fake_result(article_id: str = "TEST-001", output_size: int = 800) -> ProcessingResult:
    """Genera un ProcessingResult con imagen WebP real (generada con Pillow)."""
    buf = io.BytesIO()
    Image.new("RGB", (output_size, output_size), (255, 255, 255)).save(buf, format="WEBP", quality=85)
    return ProcessingResult(
        image_bytes=buf.getvalue(),
        article_id=article_id,
        processing_time_ms=100,
        model_used="birefnet-lite",
        original_size="200x150",
        output_size=f"{output_size}x{output_size}",
        steps_applied=["decode", "rembg", "autocrop", "scale", "composite", "encode"],
    )


def _make_jpeg(width: int = 200, height: int = 150) -> bytes:
    """Genera imagen JPEG valida en bytes."""
    buf = io.BytesIO()
    Image.new("RGB", (width, height), (200, 100, 50)).save(buf, format="JPEG")
    return buf.getvalue()


# ---------------------------------------------------------------------------
# Fixture: async_client con rembg mockeado y lifespan completo
# Retorna tupla (client, queue) para que los tests puedan patchear submit_job
# ---------------------------------------------------------------------------

@pytest.fixture
async def client_with_queue():
    """
    Fixture que retorna (AsyncClient, job_queue) con lifespan completo.
    rembg.new_session mockeado para evitar carga del modelo ONNX.

    Usa app.router.lifespan_context(app) para disparar el lifespan de FastAPI
    y ASGITransport para peticiones HTTP sin servidor real.
    """
    mock_session = MagicMock()
    with patch("app.main.new_session", return_value=mock_session):
        async with app.router.lifespan_context(app):
            async with AsyncClient(
                transport=ASGITransport(app=app),
                base_url="http://test",
            ) as client:
                # El lifespan ya corrio: app.state.job_queue esta disponible
                queue = app.state.job_queue
                yield client, queue


@pytest.fixture
async def async_client(client_with_queue):
    """Fixture de conveniencia que solo retorna el client."""
    client, _ = client_with_queue
    yield client


# ---------------------------------------------------------------------------
# POST /process — casos de exito
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_process_success(client_with_queue):
    """POST /process con JPEG valido retorna 200 con content-type image/webp."""
    client, queue = client_with_queue
    fake_result = _make_fake_result()
    with patch.object(queue, "submit_job", new=AsyncMock(return_value=fake_result)):
        response = await client.post(
            "/process",
            files={"image": ("test.jpg", _make_jpeg(), "image/jpeg")},
            data={"article_id": "TEST-001"},
        )

    assert response.status_code == 200
    assert response.headers["content-type"] == "image/webp"
    assert len(response.content) > 0


@pytest.mark.asyncio
async def test_process_headers(client_with_queue):
    """POST /process exitoso retorna los 6 headers X-* de metadata."""
    client, queue = client_with_queue
    fake_result = _make_fake_result(article_id="ART-999")
    with patch.object(queue, "submit_job", new=AsyncMock(return_value=fake_result)):
        response = await client.post(
            "/process",
            files={"image": ("test.jpg", _make_jpeg(), "image/jpeg")},
            data={"article_id": "ART-999"},
        )

    assert response.status_code == 200
    assert response.headers["x-article-id"] == "ART-999"
    assert response.headers["x-processing-time-ms"] == "100"
    assert response.headers["x-model-used"] == "birefnet-lite"
    assert response.headers["x-original-size"] == "200x150"
    assert response.headers["x-output-size"] == "800x800"
    assert "decode" in response.headers["x-steps-applied"]
    assert "encode" in response.headers["x-steps-applied"]


@pytest.mark.asyncio
async def test_process_override(client_with_queue):
    """POST /process con override={"output":{"size":400}} envia config modificada al job."""
    client, queue = client_with_queue
    fake_result = _make_fake_result(output_size=400)
    captured_config = {}

    async def capture_submit_job(process_fn, image_bytes, article_id, config_snapshot, rembg_session):
        captured_config["output_size"] = config_snapshot.output.size
        return fake_result

    with patch.object(queue, "submit_job", new=capture_submit_job):
        response = await client.post(
            "/process",
            files={"image": ("test.jpg", _make_jpeg(), "image/jpeg")},
            data={
                "article_id": "OVERRIDE-001",
                "override": json.dumps({"output": {"size": 400}}),
            },
        )

    assert response.status_code == 200
    # El override fue aplicado al config_snapshot enviado al job
    assert captured_config["output_size"] == 400
    # El resultado retornado refleja el output_size del fake result
    assert "400x400" in response.headers["x-output-size"]


# ---------------------------------------------------------------------------
# POST /process — errores
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_process_400_corrupt(client_with_queue):
    """POST /process con procesamiento que falla en decode retorna 400."""
    client, queue = client_with_queue
    with patch.object(
        queue,
        "submit_job",
        new=AsyncMock(side_effect=ProcessingError("decode", "Invalid or corrupt image: cannot identify")),
    ):
        corrupt_bytes = b"not an image at all -- definitely corrupt"
        response = await client.post(
            "/process",
            files={"image": ("bad.jpg", corrupt_bytes, "image/jpeg")},
            data={"article_id": "CORRUPT-001"},
        )

    assert response.status_code == 400
    body = response.json()
    assert body["error"] == "processing_error_decode"
    assert body["article_id"] == "CORRUPT-001"


@pytest.mark.asyncio
async def test_process_422_missing_article_id(async_client: AsyncClient):
    """POST /process sin article_id retorna 422 (validacion FastAPI)."""
    response = await async_client.post(
        "/process",
        files={"image": ("test.jpg", _make_jpeg(), "image/jpeg")},
        # article_id intencionalmente ausente
    )

    assert response.status_code == 422


@pytest.mark.asyncio
async def test_process_422_invalid_override(async_client: AsyncClient):
    """POST /process con override JSON invalido retorna 422."""
    response = await async_client.post(
        "/process",
        files={"image": ("test.jpg", _make_jpeg(), "image/jpeg")},
        data={
            "article_id": "TEST-001",
            "override": "this is not valid json {{{",
        },
    )

    assert response.status_code == 422
    body = response.json()
    assert body["error"] == "invalid_override"


@pytest.mark.asyncio
async def test_process_503_queue_full(client_with_queue):
    """POST /process con cola llena retorna 503 con error queue_full."""
    client, queue = client_with_queue
    with patch.object(
        queue,
        "submit_job",
        new=AsyncMock(side_effect=QueueFullError("Queue full")),
    ):
        response = await client.post(
            "/process",
            files={"image": ("test.jpg", _make_jpeg(), "image/jpeg")},
            data={"article_id": "BUSY-001"},
        )

    assert response.status_code == 503
    body = response.json()
    assert body["error"] == "queue_full"
    assert body["article_id"] == "BUSY-001"


@pytest.mark.asyncio
async def test_process_504_queue_timeout(client_with_queue):
    """POST /process con timeout en cola retorna 504 con error queue_timeout."""
    client, queue = client_with_queue
    with patch.object(
        queue,
        "submit_job",
        new=AsyncMock(side_effect=QueueTimeoutError("Timeout")),
    ):
        response = await client.post(
            "/process",
            files={"image": ("test.jpg", _make_jpeg(), "image/jpeg")},
            data={"article_id": "TIMEOUT-001"},
        )

    assert response.status_code == 504
    body = response.json()
    assert body["error"] == "queue_timeout"


# ---------------------------------------------------------------------------
# GET /health
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_health(async_client: AsyncClient):
    """GET /health retorna 200 con status ok, model_loaded true y uptime >= 0."""
    response = await async_client.get("/health")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["model_loaded"] is True
    assert body["uptime_seconds"] >= 0


@pytest.mark.asyncio
async def test_health_has_queue_state(async_client: AsyncClient):
    """GET /health retorna queue con active_jobs, queued_jobs y max_concurrent."""
    response = await async_client.get("/health")

    assert response.status_code == 200
    body = response.json()
    assert "queue" in body
    queue = body["queue"]
    assert "active_jobs" in queue
    assert "queued_jobs" in queue
    assert "max_concurrent" in queue
    # Valores iniciales en idle
    assert queue["active_jobs"] == 0
    assert queue["queued_jobs"] == 0
    assert queue["max_concurrent"] >= 1


@pytest.mark.asyncio
async def test_health_has_model_info(async_client: AsyncClient):
    """GET /health retorna model_name con el nombre del modelo cargado."""
    response = await async_client.get("/health")

    assert response.status_code == 200
    body = response.json()
    assert "model_name" in body
    assert body["model_name"] == "birefnet-lite"
