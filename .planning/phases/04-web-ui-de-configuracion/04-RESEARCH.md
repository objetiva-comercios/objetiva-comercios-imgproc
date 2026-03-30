# Phase 4: Web UI de Configuracion - Research

**Researched:** 2026-03-30
**Domain:** FastAPI + Jinja2 + Vanilla JS (SSR, no framework JS)
**Confidence:** HIGH

---

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

- **D-01:** Single page con secciones colapsables. Sin routing ni tabs — una sola pagina HTML con secciones que se colapsan/expanden.
- **D-02:** Orden de secciones: Status del servicio arriba, configuracion abajo agrupada por seccion de AppConfig (rembg, output, padding, autocrop, enhancement, queue).
- **D-03:** Toast notifications inline para confirmar cambios exitosos o reportar errores. Implementacion vanilla JS sin dependencias — un div fijo que aparece/desaparece con timeout.
- **D-04:** Banner de warning visible mientras el servicio esta en model swap (model_swapping=true en /health). Polling de /health detecta inicio y fin del swap.
- **D-05:** Mapeo de controles 1:1 con AppConfig (dropdown modelo, toggles, sliders, number inputs, color picker nativo HTML5).
- **D-06:** Boton "Restaurar defaults" carga AppConfig() defaults via POST /config. Boton "Ver YAML" muestra YAML raw en modal/seccion expandible.
- **D-07:** Card de status: indicador verde/rojo, jobs en cola, modelo activo, uptime. Polling /health cada 5 segundos.
- **D-08:** Tabla de ultimos 10 jobs debajo del status card. Datos de GET /status. Columnas: article_id, status (badge coloreado), processing_time_ms, timestamp. Se actualiza con cada polling.
- **D-09:** Fuente Inter via CDN Google Fonts (unica dependencia externa aceptada), fallback system-ui. Iconos Lucide via CDN. Usar skill frontend-design para maquetado.
- **D-10:** Dark mode via `prefers-color-scheme: dark` con CSS custom properties. Mobile-friendly con CSS responsive (media queries, no framework).

### Claude's Discretion

- Paleta de colores especifica (dentro del estilo que elija frontend-design)
- Animaciones y transiciones de las secciones colapsables
- Disposicion exacta de los controles dentro de cada seccion (grid, flexbox)
- Estilo visual de los toasts y el banner de warning

### Deferred Ideas (OUT OF SCOPE)

- Preview de imagen procesada en la UI (EXTF-04, v2)
</user_constraints>

---

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| UI-01 | GET /ui sirve una pagina HTML autocontenida (Jinja2 + vanilla JS, sin dependencias externas) | Patron TemplateResponse + CSS/JS inline en template; Inter/Lucide via CDN son la unica excepcion aceptada segun D-09 |
| UI-02 | La UI muestra estado del servicio en tiempo real (polling /health cada 5s) | setInterval + fetch() a /health; patron documentado con vanilla JS |
| UI-03 | La UI permite configurar todos los campos de AppConfig | Mapeo 1:1 con modelos Pydantic documentados; controles HTML nativos (slider, color, number, select, checkbox) |
| UI-04 | La UI tiene boton guardar (POST /config), restaurar defaults, ver YAML actual | POST /config ya funciona con deep merge; AppConfig() default serializable via Pydantic; GET /config retorna YAML-equivalent JSON |
| UI-05 | La UI respeta prefers-color-scheme: dark y es mobile-friendly | CSS custom properties con @media prefers-color-scheme, media queries responsive; patron MDN verificado |
</phase_requirements>

---

## Summary

La Fase 4 implementa una Web UI de administracion autocontenida servida por FastAPI. El stack esta completamente definido por decisiones previas: FastAPI (ya instalado) + Jinja2 3.1.6 (ya instalado como dependencia de FastAPI) + vanilla JS sin frameworks. No hay dependencias nuevas de produccion que agregar.

El patron tecnico central es: un nuevo `router_ui.py` con `GET /ui` que retorna `TemplateResponse` desde un template Jinja2 en `app/templates/ui.html`. El template embebe todo CSS y JS inline para ser autocontenido — no se monta `StaticFiles`. El JS usa `setInterval` + `fetch()` para el polling de `/health` y `/status` cada 5 segundos. Los formularios envian `POST /config` con `fetch()` y JSON.

La integracion con el backend es limpia: todos los endpoints necesarios ya existen y funcionan (`GET /health`, `GET /config`, `POST /config`, `GET /status`). El modelo `AppConfig` con sus defaults esta disponible para inyectar via contexto Jinja2. La whitelist `VALID_MODELS` de `router_config.py` puede pasarse como variable de contexto al template para popular el dropdown de modelos.

**Primary recommendation:** Un solo archivo `app/templates/ui.html` con CSS y JS embebidos, servido por `app/router_ui.py`. Registrar el router en `app/main.py`. Usar `Path(__file__).parent / "templates"` para la resolucion de ruta del directorio de templates.

---

## Standard Stack

### Core (ya instalado — sin dependencias nuevas de produccion)

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| FastAPI | 0.135.1 | Servidor HTTP; endpoint `GET /ui` | Ya instalado. `TemplateResponse` disponible via `fastapi.templating`. |
| Jinja2 | 3.1.6 | Renderizado del template HTML con contexto (config, modelos validos) | Ya es dependencia de FastAPI — instalado. Soporta `{% for %}`, `{% if %}`, filtros de string. |
| Python stdlib `pathlib` | stdlib | Resolucion del directorio `app/templates/` independiente del CWD | Stdlib — no agregar. |

### CDN Dependencies (externas — aceptadas segun D-09)

| Resource | URL | Purpose |
|----------|-----|---------|
| Inter font | `https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600&display=swap` | Tipografia (D-09) |
| Lucide icons | `https://unpkg.com/lucide@latest` o `https://cdn.jsdelivr.net/npm/lucide@latest/dist/umd/lucide.min.js` | Iconos (D-09) |

### Development & Testing (ya instalado)

| Tool | Version | Purpose |
|------|---------|---------|
| pytest | 9.0.2 | Test runner (ya configurado) |
| pytest-asyncio | 1.3.0 | Tests async (ya configurado con `asyncio_mode = "auto"`) |
| httpx | 0.28.1 | `AsyncClient` para tests de integración del endpoint `/ui` |

**Installation:** No se requiere `pip install` adicional para produccion. Todo esta disponible.

---

## Architecture Patterns

### Recommended Project Structure

```
app/
├── main.py              # Registrar router_ui (agregar include_router)
├── router_ui.py         # GET /ui — nuevo archivo
├── templates/
│   └── ui.html          # Template Jinja2 con CSS+JS inline — nuevo archivo
├── router_api.py        # Existente (GET /health)
├── router_config.py     # Existente (GET /config, POST /config, GET /status)
└── models.py            # Existente (AppConfig con defaults)
tests/
└── test_ui.py           # Tests del endpoint GET /ui — nuevo archivo
```

### Pattern 1: TemplateResponse con contexto de configuracion

**Que:** El endpoint `GET /ui` instancia `Jinja2Templates` con path absoluto relativo a `__file__`, obtiene la config activa y la lista de modelos validos desde `app.state`, y los pasa como contexto al template.

**Cuando usar:** Siempre para este endpoint — permite que Jinja2 renderize la config actual directamente en el HTML inicial (sin necesidad de un fetch adicional al cargar la pagina).

```python
# app/router_ui.py
# Source: https://fastapi.tiangolo.com/advanced/templates/ + patron __file__ de github.com/fastapi/fastapi/issues/2357
from pathlib import Path
from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

router = APIRouter()

# Resolucion de path absoluta — independiente del CWD de ejecucion
_TEMPLATES_DIR = Path(__file__).parent / "templates"
templates = Jinja2Templates(directory=str(_TEMPLATES_DIR))


@router.get("/ui", response_class=HTMLResponse)
async def ui_endpoint(request: Request):
    config = request.app.state.config_manager.config
    from app.router_config import VALID_MODELS
    return templates.TemplateResponse(
        request=request,
        name="ui.html",
        context={
            "config": config.model_dump(),
            "valid_models": sorted(VALID_MODELS),
        },
    )
```

```python
# app/main.py — agregar al final (junto a los otros include_router)
from app.router_ui import router as ui_router
app.include_router(ui_router)
```

### Pattern 2: CSS custom properties para dark mode (sin JS)

**Que:** Variables CSS en `:root` para tema claro, override en `@media (prefers-color-scheme: dark)`. Cero JavaScript necesario para el theming automatico basado en preferencia del sistema.

**Cuando usar:** Siempre (UI-05, D-10). La spec CSS es ampliamente soportada (96.7% de usuarios globales, baseline desde Jan 2020).

```css
/* Source: https://developer.mozilla.org/en-US/docs/Web/CSS/@media/prefers-color-scheme */
:root {
  --bg-primary: #ffffff;
  --bg-secondary: #f5f5f5;
  --text-primary: #1a1a1a;
  --text-secondary: #666666;
  --border-color: #e0e0e0;
  --accent: #2563eb;
  --success: #16a34a;
  --warning: #d97706;
  --danger: #dc2626;
}

@media (prefers-color-scheme: dark) {
  :root {
    --bg-primary: #0f0f0f;
    --bg-secondary: #1a1a1a;
    --text-primary: #f0f0f0;
    --text-secondary: #a0a0a0;
    --border-color: #333333;
    --accent: #3b82f6;
    --success: #22c55e;
    --warning: #f59e0b;
    --danger: #ef4444;
  }
}
```

### Pattern 3: Polling fetch con setInterval y manejo de errores

**Que:** `setInterval` llama a `/health` y `/status` cada 5 segundos. El handler actualiza el DOM directamente. Si el fetch falla (network error, 503), muestra estado degradado sin romper el loop.

**Cuando usar:** Para el status card (UI-02, D-07) y la tabla de jobs (D-08).

```javascript
// Patron vanilla JS para polling — sin dependencias
async function fetchHealth() {
  try {
    const resp = await fetch('/health');
    if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
    const data = await resp.json();
    updateStatusCard(data);
    // D-04: banner de model swap
    document.getElementById('swap-banner').style.display =
      data.model_swapping ? 'block' : 'none';
  } catch (err) {
    // Estado degradado — no romper el loop
    document.getElementById('status-indicator').className = 'status-dot offline';
  }
}

async function fetchStatus() {
  try {
    const resp = await fetch('/status');
    if (!resp.ok) return;
    const data = await resp.json();
    updateJobsTable(data.job_history.slice(0, 10));
  } catch (_) { /* ignorar — tabla queda con datos anteriores */ }
}

// Iniciar polling al cargar la pagina
fetchHealth();
fetchStatus();
setInterval(fetchHealth, 5000);
setInterval(fetchStatus, 5000);
```

### Pattern 4: Conversion hex <-> RGB para el color picker

**Que:** El input `<input type="color">` de HTML5 trabaja con valores `#RRGGBB`. El backend espera `[R, G, B]` (array de enteros). Se necesita conversion bidireccional en JS.

**Cuando usar:** Al cargar el formulario (RGB array → hex para el input) y al guardar (hex → RGB array para el JSON del POST).

```javascript
// Source: MDN + https://css-tricks.com/converting-color-spaces-in-javascript/
function rgbArrayToHex([r, g, b]) {
  return '#' + [r, g, b].map(v =>
    v.toString(16).padStart(2, '0')
  ).join('');
}

function hexToRgbArray(hex) {
  const n = parseInt(hex.slice(1), 16);
  return [(n >> 16) & 255, (n >> 8) & 255, n & 255];
}

// Al cargar: poblar el color picker con el valor actual de config
document.getElementById('background-color').value =
  rgbArrayToHex(config.output.background_color);

// Al guardar: convertir hex del input a array para el JSON
const payload = {
  output: {
    background_color: hexToRgbArray(
      document.getElementById('background-color').value
    )
  }
};
```

### Pattern 5: Toast notification sin dependencias

**Que:** Un `<div id="toast">` fijo en la pantalla, oculto por default. La funcion `showToast(msg, type)` lo hace visible con CSS transition y lo oculta despues de 3 segundos con `setTimeout`.

```javascript
function showToast(message, type = 'success') {
  const toast = document.getElementById('toast');
  toast.textContent = message;
  toast.className = `toast toast-${type} visible`;
  clearTimeout(toast._timer);
  toast._timer = setTimeout(() => {
    toast.className = 'toast';
  }, 3000);
}
```

### Anti-Patterns to Avoid

- **Crear `Jinja2Templates` con path relativo:** `Jinja2Templates(directory="app/templates")` falla si `uvicorn` se lanza desde un directorio distinto al root del proyecto. Usar siempre `Path(__file__).parent / "templates"`.
- **Montar StaticFiles para un solo archivo:** Para UI autocontenida, embeber CSS y JS inline en el template Jinja2 es mas simple y cumple UI-01 sin StaticFiles.
- **Usar `fetch` sin manejo de errores en el polling:** Si el servicio esta en model swap (503), el fetch falla. Sin try/catch el setInterval se rompe silenciosamente.
- **Pasar `model_swapping` como campo de la config:** `model_swapping` es estado de `app.state`, NO es parte de `AppConfig`. Leerlo de `/health` (que ya lo expone), no de `/config`.
- **Enviar el JSON completo de AppConfig en cada POST /config:** El backend acepta deep merge parcial. Enviar solo la seccion modificada reduce el riesgo de sobreescribir campos no tocados.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Template rendering | String formatting Python manual | `Jinja2Templates.TemplateResponse` | Escaping XSS automatico, loops, condicionales, herencia de templates |
| Color picker | Input texto + validacion | `<input type="color">` HTML5 nativo | Soportado en todos los browsers modernos; UX consistente con OS; cero JS |
| Slider con valor visible | Componente JS custom | `<input type="range">` + `<output>` o span con `oninput` | HTML nativo + una linea de JS |
| Toggle boolean | Checkbox estilizado custom | `<input type="checkbox">` con CSS | Accesible, keyboard-navigable, sin JS adicional |
| Dark mode detection | JS que lee localStorage + sistema | `@media (prefers-color-scheme: dark)` CSS puro | Baseline ampliamente soportado; cero JS; respeta preferencia del sistema automaticamente |

**Key insight:** El navegador ya resuelve la mayoria de los controles de formulario de forma nativa. El CSS custom properties para dark mode es mas robusto que cualquier implementacion JS porque no requiere hidratacion ni flicker al cargar.

---

## Common Pitfalls

### Pitfall 1: `model_swapping` no esta en /health response actual

**What goes wrong:** El codigo JS busca `data.model_swapping` en la respuesta de `/health` pero el endpoint actual (verificado en `router_api.py`) NO incluye ese campo en su response.

**Why it happens:** `model_swapping` esta en `app.state.model_swapping` pero `health_endpoint()` no lo serializa.

**How to avoid:** Agregar `"model_swapping": request.app.state.model_swapping` al dict de respuesta de `GET /health` como parte de esta fase (o el template JS debe ser robusto ante campo ausente con `data.model_swapping ?? false`).

**Warning signs:** El banner de swap nunca aparece aunque el modelo este cambiando.

### Pitfall 2: Jinja2Templates path relativo falla en Docker

**What goes wrong:** `Jinja2Templates(directory="app/templates")` funciona localmente pero falla en el container Docker si el WORKDIR es `/app` (el directorio seria `/app/app/templates`).

**Why it happens:** Path relativo se resuelve desde el CWD del proceso, no desde el archivo Python.

**How to avoid:** Usar siempre `Path(__file__).parent / "templates"` — resolucion absoluta basada en la ubicacion del archivo Python.

**Warning signs:** `TemplateNotFound: ui.html` en los logs al arrancar el container.

### Pitfall 3: Formulario con secciones colapsables pierde datos no visibles

**What goes wrong:** Si una seccion esta colapsada (display: none), los inputs dentro de ella pueden ser ignorados por el formulario HTML nativo al hacer submit.

**Why it happens:** HTML form submission ignora inputs dentro de elementos con `display: none` en algunos casos; pero mas importante, la UI usa `fetch()` + JSON (no form submit nativo), por lo que este comportamiento no aplica directamente.

**How to avoid:** Usar `fetch()` con JSON explicitamente construido por JS — NO usar form submit nativo. Recolectar todos los valores de inputs directamente via `document.getElementById`, independiente de visibilidad.

### Pitfall 4: GET /config retorna `output.background_color` como lista, no como hex

**What goes wrong:** Al cargar el formulario, el valor `[255, 255, 255]` se asigna directamente al `<input type="color">` que espera `#ffffff`.

**Why it happens:** El backend retorna el array RGB nativo del modelo Pydantic.

**How to avoid:** Aplicar `rgbArrayToHex()` al popular el formulario en el JS de carga inicial (ver Pattern 4).

### Pitfall 5: Inter font y Lucide via CDN fallan en entornos sin internet

**What goes wrong:** Si el servicio corre en un VPS sin acceso a Google Fonts o unpkg, la UI se renderiza sin fuente Inter y sin iconos.

**Why it happens:** CDN dependency (aceptada explicitamente en D-09 como unica excepcion).

**How to avoid:** Especificar `font-display: swap` y fallback system fonts. Para los iconos, asegurar que el layout no dependa estructuralmente de ellos (usar texto como fallback). El proyecto acepta este tradeoff (D-09).

---

## Code Examples

### Registrar el router UI en main.py

```python
# app/main.py — al final del archivo, junto a los otros include_router existentes
# Source: patron establecido en router_api.py y router_config.py
from app.router_ui import router as ui_router  # noqa: E402
app.include_router(ui_router)
```

### Poblar formulario desde config al cargar pagina

```javascript
// Patron: GET /config al cargar y aplicar valores a cada control
async function loadConfig() {
  const resp = await fetch('/config');
  const config = await resp.json();

  // Rembg
  document.getElementById('rembg-model').value = config.rembg.model;
  document.getElementById('rembg-alpha-matting').checked = config.rembg.alpha_matting;
  toggleAlphaMatting(config.rembg.alpha_matting);

  // Output
  document.getElementById('output-size').value = config.output.size;
  document.getElementById('output-quality').value = config.output.quality;
  document.getElementById('output-quality-display').textContent = config.output.quality;
  document.getElementById('output-bg-color').value = rgbArrayToHex(config.output.background_color);

  // ... demas campos ...
}
document.addEventListener('DOMContentLoaded', loadConfig);
```

### Guardar config con fetch y POST /config

```javascript
async function saveConfig() {
  const payload = {
    rembg: {
      model: document.getElementById('rembg-model').value,
      alpha_matting: document.getElementById('rembg-alpha-matting').checked,
      alpha_matting_foreground_threshold: parseInt(document.getElementById('am-fg').value),
      alpha_matting_background_threshold: parseInt(document.getElementById('am-bg').value),
      alpha_matting_erode_size: parseInt(document.getElementById('am-erode').value),
    },
    output: {
      size: parseInt(document.getElementById('output-size').value),
      quality: parseInt(document.getElementById('output-quality').value),
      background_color: hexToRgbArray(document.getElementById('output-bg-color').value),
    },
    // ... resto de secciones ...
  };

  try {
    const resp = await fetch('/config', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });
    if (resp.ok) {
      showToast('Configuracion guardada', 'success');
    } else {
      const err = await resp.json();
      showToast(`Error: ${err.detail}`, 'error');
    }
  } catch (e) {
    showToast('Error de red', 'error');
  }
}
```

### Restaurar defaults con AppConfig() serializado

```python
# app/router_ui.py — el endpoint puede exponer los defaults como JSON
# O simplemente: desde JS, hacer POST /config con los defaults hardcodeados en el template
# via Jinja2: {{ config_defaults | tojson }}
```

En el template Jinja2, pasar los defaults desde Python:

```python
# router_ui.py — en el contexto del TemplateResponse
from app.models import AppConfig
context={
    "config": config.model_dump(),
    "config_defaults": AppConfig().model_dump(),  # defaults limpios
    "valid_models": sorted(VALID_MODELS),
}
```

En el template JS:

```javascript
const CONFIG_DEFAULTS = {{ config_defaults | tojson }};

function restoreDefaults() {
  if (!confirm('Restaurar todos los valores por defecto?')) return;
  fetch('/config', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(CONFIG_DEFAULTS),
  }).then(r => r.ok && loadConfig());
}
```

### Test del endpoint GET /ui

```python
# tests/test_ui.py
# Source: patron existente en tests/test_api.py con AsyncClient + lifespan mock
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
    resp = await ui_client.get("/ui")
    assert resp.status_code == 200
    assert "text/html" in resp.headers["content-type"]
    assert "<html" in resp.text.lower()


async def test_ui_contains_config_fields(ui_client):
    resp = await ui_client.get("/ui")
    assert "rembg-model" in resp.text
    assert "output-quality" in resp.text


async def test_ui_works_without_internet(ui_client):
    """La pagina sirve correctamente — CDN puede fallar pero HTML se entrega."""
    resp = await ui_client.get("/ui")
    assert resp.status_code == 200
```

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| `templates.TemplateResponse("name.html", {"request": request})` | `templates.TemplateResponse(request=request, name="name.html", context={...})` | FastAPI 0.108.0 | La vieja firma sigue funcionando pero genera deprecation warning. Usar siempre la nueva. |
| `StaticFiles` para cada asset | CSS+JS inline en el template para UIs autocontenidas | Patron emergente 2024+ | Simplifica el deploy — un solo archivo template es mas facil de mantener que un directorio static separado cuando no hay muchos assets. |
| `window.matchMedia` JS para dark mode | `@media (prefers-color-scheme: dark)` CSS puro | CSS nivel 5, baseline 2020 | Cero JS, sin flicker al cargar, respeta preferencia del sistema automaticamente. |
| `light-dark()` CSS function | CSS custom properties con @media | CSS nivel 5 (soporte parcial 2024) | `light-dark()` es mas conciso pero con soporte menor (~90%). Para maxima compatibilidad, usar el patron @media con custom properties. |

---

## Open Questions

1. **`model_swapping` falta en GET /health response**
   - What we know: `app.state.model_swapping` existe y se setea en `_swap_rembg_session()`. El JS de D-04 necesita este campo.
   - What's unclear: Si agregarlo a `/health` entra en el scope de Fase 4 o es un ajuste menor a Fase 2.
   - Recommendation: Agregar en `router_api.py:health_endpoint()` como tarea Wave 0 de esta fase — es un cambio de 1 linea en un endpoint existente, necesario para que D-04 funcione.

2. **Lucide iconos — version a pinear**
   - What we know: CDN `unpkg.com/lucide@latest` siempre trae la ultima version. Puede haber breaking changes de nombres de iconos entre versiones.
   - What's unclear: Version exacta de Lucide a usar.
   - Recommendation: Usar `https://unpkg.com/lucide@0.468.0/dist/umd/lucide.min.js` (version estable diciembre 2024) o latest con fallback a texto si el icono no carga. El planificador puede elegir la version exacta.

---

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| Python 3.11+ | Runtime | ✓ | 3.12.3 | — |
| FastAPI | HTTP server | ✓ | 0.135.1 | — |
| Jinja2 | Template rendering | ✓ | 3.1.6 | — |
| pytest | Test runner | ✓ | 9.0.2 | — |
| pytest-asyncio | Async tests | ✓ | 1.3.0 | — |
| httpx | Integration tests | ✓ | 0.28.1 | — |
| Google Fonts CDN | Inter font | Depende del entorno runtime | — | `font-family: system-ui, sans-serif` |
| unpkg CDN | Lucide icons | Depende del entorno runtime | — | Texto/emoji como fallback |

**Missing dependencies with no fallback:** Ninguna. Todas las dependencias de produccion estan instaladas.

**Missing dependencies with fallback:** Google Fonts y unpkg son CDN — si el VPS no tiene acceso a internet outbound, la UI se renderiza con system-ui font y sin iconos Lucide. El layout no debe depender estructuralmente de los iconos.

---

## Validation Architecture

### Test Framework

| Property | Value |
|----------|-------|
| Framework | pytest 9.0.2 + pytest-asyncio 1.3.0 |
| Config file | `pyproject.toml` (sección `[tool.pytest.ini_options]`) |
| Quick run command | `pytest tests/test_ui.py -x -q` |
| Full suite command | `pytest tests/ -x -q` |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| UI-01 | GET /ui retorna 200 con Content-Type text/html | integration | `pytest tests/test_ui.py::test_ui_returns_html -x` | ❌ Wave 0 |
| UI-01 | HTML es autocontenido (sin referencias a /static/) | integration | `pytest tests/test_ui.py::test_ui_no_static_references -x` | ❌ Wave 0 |
| UI-02 | HTML contiene setInterval con fetch a /health | smoke | `pytest tests/test_ui.py::test_ui_contains_polling_js -x` | ❌ Wave 0 |
| UI-03 | HTML contiene inputs para todos los campos de AppConfig | integration | `pytest tests/test_ui.py::test_ui_contains_all_config_fields -x` | ❌ Wave 0 |
| UI-04 | Boton guardar presente en HTML | smoke | `pytest tests/test_ui.py::test_ui_contains_save_button -x` | ❌ Wave 0 |
| UI-04 | Boton restaurar defaults presente en HTML | smoke | `pytest tests/test_ui.py::test_ui_contains_restore_button -x` | ❌ Wave 0 |
| UI-05 | HTML contiene `prefers-color-scheme` en CSS | smoke | `pytest tests/test_ui.py::test_ui_contains_dark_mode_css -x` | ❌ Wave 0 |
| UI-05 | HTML contiene viewport meta tag (mobile-friendly) | smoke | `pytest tests/test_ui.py::test_ui_mobile_meta_tag -x` | ❌ Wave 0 |

### Sampling Rate

- **Per task commit:** `pytest tests/test_ui.py -x -q`
- **Per wave merge:** `pytest tests/ -x -q`
- **Phase gate:** Full suite green antes de `/gsd:verify-work`

### Wave 0 Gaps

- [ ] `tests/test_ui.py` — cubre UI-01 a UI-05 (8 tests listados arriba)
- [ ] `app/templates/` — directorio nuevo, crear antes de los tests
- [ ] `app/router_ui.py` — stub minimo con endpoint `GET /ui` que retorne 200 para que los tests puedan arrancar

*(Conftest existente en `tests/conftest.py` es reutilizable — las fixtures `tmp_settings_yaml` y `config_manager` aplican. No es necesario agregar fixtures nuevas para los tests de UI.)*

---

## Project Constraints (from CLAUDE.md)

Directivas del archivo `CLAUDE.md` del proyecto que el planificador DEBE verificar:

| Constraint | Aplicacion en esta fase |
|------------|------------------------|
| RAM ≤ 2 GB para container | La UI no agrega memoria en runtime — es HTML estatico renderizado en startup/request. Sin impacto. |
| No dependencias externas embebidas | CSS y JS deben estar inline en el template. NO montar StaticFiles para assets. Inter/Lucide via CDN son la excepcion explicita (D-09). |
| Event loop: asyncio.to_thread() para CPU-bound | No aplica — rendering Jinja2 es rapido (< 1ms), no es CPU-bound. `TemplateResponse` puede llamarse directamente en el endpoint async. |
| Formato de salida WebP | No aplica a la UI. |
| Orden del pipeline: fijo e inamovible | No aplica a la UI. |
| Sesion rembg global — nunca por request | No aplica a la UI directamente. El endpoint `/ui` NO toca `rembg_session`. |
| yaml.safe_load siempre | No aplica a la UI — la UI usa `/config` endpoint que ya usa `yaml.safe_load` internamente. |
| GSD Workflow Enforcement | Toda implementacion debe pasar por GSD execute-phase. No editar archivos directamente fuera del workflow. |
| `frontend-design` skill para maquetado UI | El planificador DEBE invocar la skill `frontend-design` para todo el trabajo de maquetado del template HTML. Es una decision explicita del usuario (D-09, CONTEXT.md `<specifics>`). |

---

## Sources

### Primary (HIGH confidence)

- [FastAPI Templates Docs](https://fastapi.tiangolo.com/advanced/templates/) — patron TemplateResponse, sintaxis con keyword args (FastAPI 0.108.0+), setup con router
- `app/router_config.py` (codigo fuente verificado) — VALID_MODELS frozenset, endpoints GET/POST /config, GET /status — contratos exactos de API
- `app/router_api.py` (codigo fuente verificado) — health_endpoint() response dict — confirma que `model_swapping` NO esta incluido actualmente
- `app/models.py` (codigo fuente verificado) — AppConfig completo con todos los campos y defaults
- `pyproject.toml` (codigo fuente verificado) — `asyncio_mode = "auto"`, pytest paths
- [MDN prefers-color-scheme](https://developer.mozilla.org/en-US/docs/Web/CSS/@media/prefers-color-scheme) — patron CSS custom properties dark mode, browser support 96.7%

### Secondary (MEDIUM confidence)

- [FastAPI GitHub Issue #2357](https://github.com/fastapi/fastapi/issues/2357) — resolucion de path para templates en subdirectorios, patron `Path(__file__).parent`
- [FastAPI GitHub Discussion #2630](https://github.com/fastapi/fastapi/discussions/2630) — Jinja2 template inheritance y routers
- [CSS-Tricks Converting Color Spaces](https://css-tricks.com/converting-color-spaces-in-javascript/) — algoritmo hex <-> RGB en JS
- [FastAPI Async Tests](https://fastapi.tiangolo.com/advanced/async-tests/) — patron AsyncClient para tests de integracion

### Tertiary (LOW confidence)

- WebSearch resultados sobre polling fetch + dark mode — multiples fuentes concordantes, sin verificacion oficial adicional necesaria dado que se usan APIs nativas del browser.

---

## Metadata

**Confidence breakdown:**

- Standard stack: HIGH — todas las dependencias verificadas con `pip show`, versiones confirmadas, ya instaladas.
- Architecture patterns: HIGH — patron TemplateResponse verificado en docs oficiales, patron `Path(__file__)` verificado en issues de FastAPI.
- API contracts: HIGH — codigo fuente leido directamente, contratos exactos conocidos.
- Pitfalls: HIGH para los 3 primeros (verificados en codigo fuente); MEDIUM para Inter/Lucide CDN (depende del entorno runtime del VPS).
- Frontend JS patterns: MEDIUM — fetch API y setInterval son APIs nativas del browser ampliamente documentadas, sin version staleness concern.

**Research date:** 2026-03-30
**Valid until:** 2026-06-30 (stack estable; Jinja2 y FastAPI son librerias maduras con APIs estables)
