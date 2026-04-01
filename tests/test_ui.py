"""
Tests de integracion del endpoint GET /ui del Image Standardizer Service.

Cubre:
- UI-01: GET /ui retorna 200 con Content-Type text/html
- UI-01: HTML autocontenido — sin referencias a /static/
- UI-02: HTML contiene setInterval con fetch a /health para polling
- UI-03: HTML contiene inputs para todos los campos de AppConfig
- UI-04: Botones guardar, restaurar defaults y ver YAML presentes
- UI-05: CSS con prefers-color-scheme y viewport meta tag
- Pitfall 1: GET /health incluye model_swapping
"""
import pytest
from httpx import AsyncClient, ASGITransport
from unittest.mock import patch, MagicMock

from app.main import app


@pytest.fixture
async def ui_client():
    with patch("rembg.new_session", return_value=MagicMock()):
        async with app.router.lifespan_context(app):
            async with AsyncClient(
                transport=ASGITransport(app=app),
                base_url="http://test",
            ) as client:
                yield client


async def test_ui_returns_html(ui_client):
    """UI-01: GET /ui retorna 200 con Content-Type text/html."""
    resp = await ui_client.get("/ui")
    assert resp.status_code == 200
    assert "text/html" in resp.headers["content-type"]
    assert "<html" in resp.text.lower()


async def test_ui_no_static_references(ui_client):
    """UI-01: HTML autocontenido — sin referencias a /static/."""
    resp = await ui_client.get("/ui")
    assert "/static/" not in resp.text


async def test_ui_contains_polling_js(ui_client):
    """UI-02: HTML contiene setInterval con fetch a /health para polling."""
    resp = await ui_client.get("/ui")
    assert "setInterval" in resp.text
    assert "/health" in resp.text


async def test_ui_contains_all_config_fields(ui_client):
    """UI-03: HTML contiene inputs para todos los campos de AppConfig."""
    resp = await ui_client.get("/ui")
    html = resp.text
    # Rembg
    assert "rembg-model" in html
    assert "rembg-alpha-matting" in html
    # Output
    assert "output-size" in html
    assert "output-quality" in html
    assert "output-bg-color" in html
    # Padding
    assert "padding-enabled" in html
    assert "padding-percent" in html
    # Autocrop
    assert "autocrop-enabled" in html
    assert "autocrop-threshold" in html
    # Enhancement
    assert "enhancement-brightness" in html
    assert "enhancement-contrast" in html
    # Queue
    assert "queue-max-concurrent" in html
    assert "queue-max-queue-size" in html
    assert "queue-timeout" in html


async def test_ui_contains_save_button(ui_client):
    """UI-04: Boton guardar presente en HTML."""
    resp = await ui_client.get("/ui")
    assert "save-btn" in resp.text
    assert "saveConfig" in resp.text


async def test_ui_contains_restore_button(ui_client):
    """UI-04: Boton restaurar defaults presente en HTML."""
    resp = await ui_client.get("/ui")
    assert "restore-btn" in resp.text
    assert "restoreDefaults" in resp.text


async def test_ui_contains_yaml_button(ui_client):
    """UI-04: Boton ver YAML presente en HTML."""
    resp = await ui_client.get("/ui")
    assert "yaml-btn" in resp.text or "yaml-view" in resp.text


async def test_ui_contains_dark_mode_css(ui_client):
    """UI-05: HTML contiene prefers-color-scheme en CSS."""
    resp = await ui_client.get("/ui")
    assert "prefers-color-scheme" in resp.text


async def test_ui_mobile_meta_tag(ui_client):
    """UI-05: HTML contiene viewport meta tag (mobile-friendly)."""
    resp = await ui_client.get("/ui")
    assert "viewport" in resp.text
    assert "width=device-width" in resp.text


async def test_ui_contains_valid_models(ui_client):
    """UI-03: El dropdown de modelos contiene las opciones de VALID_MODELS."""
    resp = await ui_client.get("/ui")
    assert "isnet-general-use" in resp.text  # default model debe estar


async def test_ui_no_external_cdn(ui_client):
    """UI-01: HTML autocontenido — sin requests a CDNs externos."""
    import re
    resp = await ui_client.get("/ui")
    html = resp.text
    assert "fonts.googleapis.com" not in html
    assert "unpkg.com" not in html
    # No external URLs in src/href attributes (solo SVG namespace inline permitido)
    external_src_href = re.findall(r'(?:src|href)=["\']https?://[^\s"\'<>]+["\']', html)
    assert len(external_src_href) == 0, f"External src/href found: {external_src_href}"


async def test_health_includes_model_swapping(ui_client):
    """Pitfall 1: GET /health incluye model_swapping en la respuesta."""
    resp = await ui_client.get("/health")
    data = resp.json()
    assert "model_swapping" in data
    assert data["model_swapping"] is False
