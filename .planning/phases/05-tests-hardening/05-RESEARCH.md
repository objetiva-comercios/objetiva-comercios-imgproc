# Phase 5: Tests + Hardening — Research

**Researched:** 2026-03-30
**Domain:** pytest, pytest-asyncio, httpx, coverage — auditoría y completado de suite de tests
**Confidence:** HIGH

## Summary

La suite de tests del proyecto ya existe con 94 tests distribuidos en 8 archivos (2125+ líneas) que cubren el camino feliz y muchos edge cases de cada componente. Los tests corren todos en verde con 93% de cobertura total sin modificaciones. La fase 5 es un trabajo de **auditoría + completado de gaps**: identificar qué falta contra TEST-01, TEST-02, TEST-03 y agregar los tests que cubran los ~44 statements no cubiertos.

El stack de testing está completamente instalado y operativo: pytest 9.0.2, pytest-asyncio 1.3.0 con `asyncio_mode="auto"`, httpx 0.28.1 con ASGITransport, pytest-cov. Todos los patrones de mock ya están establecidos. El venv está en `.venv/` y el comando de ejecución es `.venv/bin/python -m pytest`.

**Primary recommendation:** No reescribir. Auditar los 44 statements no cubiertos (detallados abajo), agregar tests específicos para cada gap, y verificar que pytest pasa con cobertura >= 80%. El target real es ~96%+ ya que partimos de 93% con solo 44 statements faltantes.

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
- **D-01:** Auditar los tests existentes (2125 lineas, 80+ tests de fases 1-4) y completar los gaps contra TEST-01, TEST-02, TEST-03. No reescribir desde cero — los tests existentes ya cubren el camino feliz y muchos edge cases.
- **D-02:** Coverage target: 80%+ medido con `pytest --cov=app --cov-report=term-missing`. Sin configuracion de CI — solo ejecucion local.
- **D-03:** Cubrir todos los edge cases documentados en decisiones de Fase 1: EXIF transpose (D-08), skip rembg para imagenes con alpha pre-existente (D-06), conversion CMYK a RGB (D-07), limite de megapixels con rechazo 400 (D-05), enhancement skip cuando brightness=1.0 y contrast=1.0.
- **D-04:** Pipeline completo end-to-end: verificar que una imagen JPEG de entrada produce un WebP de exactamente 800x800 con fondo blanco y producto centrado (mock de rembg).
- **D-05:** Verificar: job completo exitoso con resultado correcto, 503 cuando cola llena (max_queue_size), max_concurrent=1 respetado (segundo job espera), timeout con 504 (queue.timeout_seconds), estado actualizado tras cada operacion (total_processed, total_errors, job_history).
- **D-06:** Verificar: POST /process success con todos los headers (X-Article-Id, X-Processing-Time-Ms, X-Model-Used, X-Original-Size, X-Output-Size, X-Steps-Applied), POST /process 422 para campos faltantes, POST /process 400 para imagen invalida, GET /health con estructura completa, GET/POST /config, GET /ui sirve HTML valido, GET /status con historial.
- **D-07:** Tests de API mockean submit_job (no process_image) — decision de Fase 1 que se mantiene.
- **D-08:** Hardening = tests que verifican edge cases y comportamiento defensivo ya implementado en el codigo. No se agregan nuevas validaciones al codigo fuente.

### Claude's Discretion
- Organizacion interna de los tests (clases vs funciones planas)
- Nombres de tests y descripciones
- Fixtures adicionales si son necesarias para edge cases no cubiertos
- Orden de ejecucion de tests (pytest lo maneja automaticamente)

### Deferred Ideas (OUT OF SCOPE)
None — discussion stayed within phase scope
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| TEST-01 | Tests del processor: decode válido/inválido, autocrop, padding, aspect ratio, fondo blanco, tamaño output, formato WebP, enhancement, pipeline completo | Ya existen TestDecodeAndValidate, TestAutocrop, TestComposite, TestEnhance, TestEncodeWebp, TestProcessImage. Gaps: _clean_alpha_artifacts multi-component, autocrop bbox=None, ProcessingError unknown-step wrapping |
| TEST-02 | Tests del queue: job completo, 503 cuando lleno, max_concurrent respetado, timeout, estado actualizado | Ya existen test_max_concurrent, test_503_queue_full, test_504_timeout, test_state_tracking, test_error_tracking, test_job_history. Ningún gap identificado — cobertura 100% en queue.py |
| TEST-03 | Tests de API: process success + headers, campos faltantes, imagen inválida, health, config GET/POST, UI sirve HTML, status con historial | Ya existen test_process_*, test_health_*, test_get_config, test_post_config_*, test_get_status_*, test_ui_*. Gaps: 500 internal error en /process, invalid JSON en POST /config, model_changed trigger en POST /config |
</phase_requirements>

---

## Standard Stack

### Core (ya instalado y operativo)
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| pytest | 9.0.2 | Test runner | Estándar. Configurado en `pyproject.toml` con `asyncio_mode = "auto"` |
| pytest-asyncio | 1.3.0 | Tests async | `asyncio_mode = "auto"` evita `@pytest.mark.asyncio` en cada test |
| httpx | 0.28.1 | Cliente HTTP para tests de API | `AsyncClient(transport=ASGITransport(app=app))` sin servidor real |
| pytest-cov | >=6.0 | Coverage | En `requirements-dev.txt`. **Pendiente instalar en venv** — actualmente no está disponible en el venv del proyecto |

### Verificacion de estado actual
```
COBERTURA ACTUAL (sin pytest-cov instalado en venv):
  94 tests pasando en verde
  93% cobertura total (649 statements, 44 faltantes)

  Por archivo:
  - app/queue.py:          100% (75 stmts, 0 miss)
  - app/models.py:         100% (50 stmts, 0 miss)
  - app/config.py:         100% (24 stmts, 0 miss)
  - app/router_ui.py:      100% (13 stmts, 0 miss)
  - app/__init__.py:       100%
  - app/router_api.py:      94% (51 stmts, 3 miss: lineas 150-157)
  - app/main.py:            93% (92 stmts, 6 miss: lineas 87-89, 111-118)
  - app/cli.py:             92% (126 stmts, 10 miss: lineas 49-53, 209-211, 255, 288)
  - app/processor.py:       89% (158 stmts, 18 miss: lineas 180, 190-203, 225, 457-458, 467-470)
  - app/router_config.py:   88% (60 stmts, 7 miss: lineas 25-26, 55-56, 105, 117-118)
```

**Instalacion de pytest-cov en venv:**
```bash
.venv/bin/pip install "pytest-cov>=6.0"
```

**Comando de ejecucion:**
```bash
.venv/bin/python -m pytest tests/ --cov=app --cov-report=term-missing
```

---

## Audit de Gaps — Mapa Exacto de 44 Statements Faltantes

### processor.py — 18 statements (lineas 180, 190-203, 225, 457-458, 467-470)

| Lineas | Funcion | Que hace | Test necesario |
|--------|---------|----------|----------------|
| 180 | `_clean_alpha_artifacts` | `return alpha` cuando `arr.max() == 0` (alpha completamente transparente) | `test_clean_alpha_all_transparent` — pasar imagen 100% transparente |
| 190-203 | `_clean_alpha_artifacts` | Rama multi-componente: hay 2+ regiones conectadas, eliminar las pequeñas | `test_clean_alpha_removes_small_artifacts` — imagen con producto central + pixel aislado |
| 225 | `autocrop` | `return img` cuando `clean_alpha.getbbox() is None` (alpha completamente negro tras binarizar) | `test_autocrop_bbox_none` — imagen RGBA con todos los píxeles con alpha=0 |
| 457-458 | `process_image` | `img = enhance(img, config)` sin append "enhance" cuando brightness=1.0 y contrast=1.0 | Ya existe `test_full_pipeline` pero no verifica que "enhance" NO está en steps_applied |
| 467-470 | `process_image` | Re-raise `ProcessingError` + wrapping de excepción genérica en `ProcessingError(step="unknown")` | `test_pipeline_unknown_exception_wrapped` — mock de `autocrop` que lanza `ValueError` |

### router_api.py — 3 statements (lineas 150-157)

| Lineas | Funcion | Que hace | Test necesario |
|--------|---------|----------|----------------|
| 150-157 | `process_endpoint` | Catch de `Exception` genérica → 500 internal_error | `test_process_500_internal_error` — mock de `submit_job` lanzando `RuntimeError` |

### router_config.py — 7 statements (lineas 25-26, 55-56, 105, 117-118)

| Lineas | Funcion | Que hace | Test necesario |
|--------|---------|----------|----------------|
| 25-26 | módulo | `VALID_MODELS` fallback cuando `from rembg.sessions import sessions_names` lanza `ImportError` | Difícil de testear directamente (module-level). Verificar que VALID_MODELS contiene los modelos esperados — ya verificado indirectamente por `test_post_config_invalid_model` |
| 55-56 | `update_config` | `return JSONResponse(422, {"error": "invalid_json"})` cuando body no es JSON válido | `test_post_config_invalid_json` — enviar cuerpo que no es JSON |
| 105 | `update_config` | `asyncio.create_task(_clear_suppress())` — la tarea de cleanup del suppress_flag | Difícil testear directamente (fire-and-forget). Puede quedar como LOW priority |
| 117-118 | `update_config` | `asyncio.create_task(_swap_rembg_session(...))` cuando el modelo cambia | `test_post_config_model_change_triggers_swap` — POST /config con nuevo modelo, verificar `model_changed` triggerea la tarea |

### main.py — 6 statements (lineas 87-89, 111-118)

| Lineas | Funcion | Que hace | Test necesario |
|--------|---------|----------|----------------|
| 87-89 | `_swap_rembg_session` | `return` cuando `asyncio.wait_for` timeout (semaphore no liberado a tiempo) | LOW priority — requiere manipulación del semaphore interno; omitir en fase 5 |
| 111-118 | `_swap_rembg_session` | Exception handler cuando `new_session()` falla; garantiza `model_swapping=False` via finally | LOW priority — testeado indirectamente por test_watchdog.py; omitir en fase 5 |

### cli.py — 10 statements (lineas 49-53, 209-211, 255, 288)

| Lineas | Funcion | Que hace | Test necesario |
|--------|---------|----------|----------------|
| 49-53 | `_get_rembg_session` | Lazy init de la sesión | Testeado en test_cli.py pero con mock — la rama de init real no se ejercita |
| 209-211, 255, 288 | `batch`, `serve`, `config` | Paths de error en CLI | LOW priority — no requeridos por TEST-01/02/03 |

**Resumen de gaps por prioridad:**
- **Alta prioridad (requeridas por TEST-01/02/03):** 5 tests nuevos (processor gaps, router_api 500, router_config gaps)
- **Baja prioridad (fuera de scope TEST):** main.py swap paths, cli.py error paths

---

## Architecture Patterns

### Patrones establecidos en el proyecto (usar estos, no inventar nuevos)

**Pattern 1: Tests de processor — funciones puras, sync, clases de test**
```python
# Patrón usado en tests/test_processor.py
class TestDecodeAndValidate:
    def test_decode_jpeg(self, sample_jpeg):
        config = default_config()
        img, original_size, mode = decode_and_validate(sample_jpeg, config)
        assert img.mode == "RGBA"

# Para _clean_alpha_artifacts (función privada) — llamar via autocrop con imagen controlada
# NO testear _clean_alpha_artifacts directamente (es privada)
```

**Pattern 2: Mock de rembg en tests de pipeline**
```python
# Patrón establecido — nunca cargar el modelo ONNX en tests
with patch("rembg.remove", return_value=result_png) as mock_remove:
    result = remove_background(img, config, mock_session)
    mock_remove.assert_called_once()
```

**Pattern 3: Tests async con pytest-asyncio `asyncio_mode="auto"`**
```python
# NO necesita decorador — asyncio_mode="auto" en pyproject.toml lo maneja
async def test_503_queue_full():
    queue = JobQueue(max_concurrent=1, max_queue_size=1, timeout_seconds=5)
    with pytest.raises(QueueFullError):
        await queue.submit_job(...)
```

**Pattern 4: Tests de API con lifespan completo**
```python
# Fixture establecida — reutilizar client_with_queue para tests que necesitan queue real
@pytest.fixture
async def client_with_queue():
    mock_session = MagicMock()
    with patch("app.main.new_session", return_value=mock_session):
        async with app.router.lifespan_context(app):
            async with AsyncClient(
                transport=ASGITransport(app=app),
                base_url="http://test",
            ) as client:
                queue = app.state.job_queue
                yield client, queue
```

**Pattern 5: Tests de config router con app de test aislada**
```python
# test_app fixture en test_config_router.py — NO usa el app principal
app = FastAPI(lifespan=_mock_lifespan)
app.include_router(config_router)
cm = ConfigManager(config_path=str(yaml_path))
app.state.config_manager = cm
app.state.job_queue = JobQueue(...)
```

**Pattern 6: patch.object para submit_job**
```python
# Mockear el queue instance, no process_image — D-07
with patch.object(queue, "submit_job", new=AsyncMock(side_effect=RuntimeError("boom"))):
    response = await client.post("/process", ...)
assert response.status_code == 500
```

### Anti-Patterns a Evitar
- **Importar rembg sin mock:** Cualquier test que importe `app.main` sin patchear `new_session` intentará cargar el modelo ONNX y fallará o tardará minutos.
- **Testear `_clean_alpha_artifacts` directamente:** Es función privada — testear via `autocrop()` con imágenes controladas que ejerciten la rama interna.
- **Usar `asyncio.sleep()` largo en tests:** Los tests de queue ya usan tiempos cortos (0.1-0.3s). Mantener el mismo patrón.
- **Crear fixtures globales para lo que ya existe:** `conftest.py` ya tiene `sample_jpeg`, `sample_png_transparent`, `sample_cmyk`, `sample_large_image`, `config_manager`. No duplicar.

---

## Don't Hand-Roll

| Problema | No construir | Usar en cambio | Por qué |
|----------|-------------|----------------|---------|
| Comparación de imágenes pixel-a-pixel | Comparador custom | `PIL.Image.getpixel()` + `assert` | Ya establece el patrón en el proyecto |
| Mock de operaciones async | `threading.Event` manual | `AsyncMock` de `unittest.mock` | AsyncMock maneja `await` automáticamente |
| Fixtures de imágenes de prueba | Archivos PNG en disco | `io.BytesIO` + `Image.new()` en código | Ya establecido — sin archivos binarios en el repo |
| Verificación de WebP válido | Parser custom | `result[:4] == b"RIFF" and result[8:12] == b"WEBP"` | Ya establecido en `test_encode_webp` |

---

## Common Pitfalls

### Pitfall 1: piexif no disponible para test_exif_transpose
**Qué pasa:** `test_exif_transpose` en test_processor.py usa `import piexif` que puede no estar instalado.
**Por qué ocurre:** `piexif` no está en requirements.txt ni requirements-dev.txt.
**Cómo evitar:** Verificar `piexif` está disponible en el venv antes de ejecutar. Si falta, agregar a requirements-dev.txt o reescribir el test con datos EXIF hardcodeados en bytes.
**Detección:** Correr los 94 tests existentes primero — si `test_exif_transpose` pasa, piexif está instalado.

**Estado actual:** Los 94 tests pasan en verde, incluyendo `test_exif_transpose`. piexif está disponible en el venv.

### Pitfall 2: asyncio_mode="auto" requiere pytest-asyncio >= 0.21
**Qué pasa:** Con pytest-asyncio < 0.21, `asyncio_mode="auto"` no existe y falla con error de configuración.
**Por qué ocurre:** El pyproject.toml tiene `asyncio_mode = "auto"` sin `@pytest.mark.asyncio`.
**Cómo evitar:** pytest-asyncio 1.3.0 ya está instalado — compatible. No degradar.

### Pitfall 3: Mock de `new_session` debe patchear en el módulo correcto
**Qué pasa:** `patch("rembg.new_session")` no funciona — hay que patchear donde se usa.
**Por qué ocurre:** Python resuelve la referencia al importar. `app.main` importa `from rembg import new_session`.
**Correcto:** `patch("app.main.new_session", return_value=MagicMock())`
**Estado actual:** Ya establecido correctamente en todas las fixtures existentes.

### Pitfall 4: ASGITransport no dispara lifespan automáticamente
**Qué pasa:** Si se usa `AsyncClient(transport=ASGITransport(app=app))` sin `lifespan_context`, `app.state.job_queue` no existe y los endpoints fallan con AttributeError.
**Por qué ocurre:** ASGITransport en httpx no es un servidor real y no dispara el lifespan de FastAPI.
**Correcto:** Usar `app.router.lifespan_context(app)` como context manager, o construir una app de test con lifespan propio (patrón de test_config_router.py).
**Estado actual:** Ya manejado correctamente en todas las fixtures existentes.

### Pitfall 5: `_clean_alpha_artifacts` usa scipy (ndimage)
**Qué pasa:** `processor.py:176` importa `from scipy import ndimage`. Si scipy no está instalado, el import falla en runtime cuando hay > 1 componente conectado.
**Por qué ocurre:** scipy es dependencia de rembg, no de Pillow — instalada indirectamente.
**Cómo evitar:** Verificar que los tests que ejerciten `_clean_alpha_artifacts` multi-componente pasan sin error de import.
**Detección:** Los tests actuales no ejercitan ese path (189-203 son statements faltantes). Al agregar el test, verificar que scipy está disponible.

### Pitfall 6: Cobertura de lineas 25-26 en router_config.py requiere mock de import
**Qué pasa:** Las líneas 25-26 son el fallback `except ImportError` del import de `sessions_names`. No se puede testear directamente sin manipular el import system.
**Cómo evitar:** Aceptar estas 2 líneas como no cubiertas. El fallback está verificado indirectamente (los modelos válidos aparecen en los tests de validación de modelo). No recomendable usar `importlib.reload()` para esto.

---

## Code Examples

### Ejemplo 1: Test de _clean_alpha_artifacts via autocrop (multi-componente)
```python
# Source: patrón del proyecto (test_processor.py helpers existentes)
def make_rgba_two_regions() -> Image.Image:
    """RGBA con producto principal (50x50) + artefacto pequeño (2x2) aislado."""
    img = Image.new("RGBA", (200, 200), (0, 0, 0, 0))
    pixels = img.load()
    # Producto principal en centro
    for y in range(75, 125):
        for x in range(75, 125):
            pixels[x, y] = (255, 0, 0, 255)
    # Artefacto pequeño en esquina (2x2 = 4 pixeles vs 2500 del producto = 0.16%)
    pixels[5, 5] = (255, 0, 0, 255)
    pixels[6, 5] = (255, 0, 0, 255)
    pixels[5, 6] = (255, 0, 0, 255)
    pixels[6, 6] = (255, 0, 0, 255)
    return img

def test_autocrop_removes_small_artifacts():
    """_clean_alpha_artifacts elimina el artefacto pequeño; autocrop recorta solo el producto."""
    img = make_rgba_two_regions()
    config = default_config()
    cropped = autocrop(img, config)
    # Sin el artefacto: el bbox es solo el producto 50x50
    assert cropped.width == 50
    assert cropped.height == 50
```

### Ejemplo 2: Test de error 500 en POST /process
```python
# Source: patrón de test_api.py (test_process_503_queue_full)
@pytest.mark.asyncio
async def test_process_500_internal_error(client_with_queue):
    """POST /process con excepcion generica retorna 500 con error internal_error."""
    client, queue = client_with_queue
    with patch.object(
        queue,
        "submit_job",
        new=AsyncMock(side_effect=RuntimeError("unexpected failure")),
    ):
        response = await client.post(
            "/process",
            files={"image": ("test.jpg", _make_jpeg(), "image/jpeg")},
            data={"article_id": "ERR-001"},
        )
    assert response.status_code == 500
    body = response.json()
    assert body["error"] == "internal_error"
```

### Ejemplo 3: Test de invalid JSON en POST /config
```python
# Source: patrón de test_config_router.py
@pytest.mark.asyncio
async def test_post_config_invalid_json_body(test_app):
    """POST /config con body que no es JSON retorna 422 con error invalid_json."""
    async with AsyncClient(transport=ASGITransport(app=test_app), base_url="http://test") as client:
        response = await client.post(
            "/config",
            content=b"this is not json at all",
            headers={"Content-Type": "application/json"},
        )
    assert response.status_code == 422
    body = response.json()
    assert body["error"] == "invalid_json"
```

### Ejemplo 4: Test de pipeline — unknown exception wrapping
```python
# Source: patrón del proyecto
def test_pipeline_unknown_exception_wrapped(sample_jpeg):
    """Excepcion no-ProcessingError en pipeline se envuelve en ProcessingError(step='unknown')."""
    config = default_config()
    mock_session = MagicMock()

    with patch("app.processor.autocrop", side_effect=ValueError("unexpected error")):
        with pytest.raises(ProcessingError) as exc_info:
            process_image(sample_jpeg, "ART-ERR", config, mock_session)

    assert exc_info.value.step == "unknown"
```

---

## State of the Art

| Aspecto | Estado actual | Impacto en Phase 5 |
|---------|--------------|-------------------|
| pytest-asyncio `asyncio_mode="auto"` | Activo — todos los tests async corren sin decorador | Tests nuevos no necesitan `@pytest.mark.asyncio` |
| httpx AsyncClient + ASGITransport | Establecido — sin servidor real | Los tests de API son rápidos y deterministas |
| Mock de rembg via `patch("rembg.remove")` | Establecido — nunca carga ONNX en tests | Mantener en todos los tests de pipeline |
| pytest-cov | En requirements-dev.txt pero **no instalado en .venv** | Instalar antes de medir cobertura |

**Nota sobre Python 3.12:** El proyecto corre con Python 3.12 (único disponible en el VPS, declarado compatible en decisions de Phase 01). El pyproject.toml dice `requires-python = ">=3.11"`. Los tests pasan sin problemas.

---

## Open Questions

1. **piexif en requirements-dev.txt**
   - Qué sabemos: `test_exif_transpose` usa `import piexif`. El test pasa actualmente.
   - Qué no está claro: ¿Está piexif en requirements.txt o es una dependencia transitiva?
   - Recomendación: Verificar con `.venv/bin/pip show piexif`. Si es transitiva (no en requirements-dev.txt), agregar explícitamente para evitar que desaparezca en builds futuros.

2. **Cobertura objetivo vs. alcanzable**
   - Qué sabemos: Partimos de 93% con 44 statements faltantes. Los gaps de main.py (swap paths) y cli.py son difíciles de testear y fuera de TEST-01/02/03.
   - Qué no está claro: ¿Agregar 5-6 tests de alta prioridad llevará a > 80%? Sí, definitivamente — ya estamos en 93%.
   - Recomendación: El target de 80% ya está cumplido. Los tests de fase 5 deben buscar cubrir los gaps de TEST-01/02/03 específicamente, no maximizar cobertura por cobertura.

---

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| Python 3.12 | Tests | ✓ | 3.12.3 | — |
| pytest | Tests | ✓ (en .venv) | 9.0.2 | — |
| pytest-asyncio | Tests async | ✓ (en .venv) | 1.3.0 | — |
| httpx | Tests de API | ✓ (en .venv) | 0.28.1 | — |
| pytest-cov | Coverage | ✗ (no en .venv) | — | Instalar con `.venv/bin/pip install "pytest-cov>=6.0"` |
| scipy | _clean_alpha_artifacts | ✓ (transitiva vía rembg) | verificar | — |
| piexif | test_exif_transpose | ✓ (en .venv, transitiva) | verificar | Reescribir test con EXIF hardcodeado |

**Missing dependencies con no fallback:** ninguna que bloquee.

**Missing dependencies con fallback:**
- pytest-cov: instalar antes de medir cobertura. El plan debe incluir este paso como Wave 0.

---

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest 9.0.2 + pytest-asyncio 1.3.0 |
| Config file | `pyproject.toml` — `[tool.pytest.ini_options]` con `asyncio_mode = "auto"` y `testpaths = ["tests"]` |
| Quick run command | `.venv/bin/python -m pytest tests/ -q` |
| Full suite command | `.venv/bin/python -m pytest tests/ --cov=app --cov-report=term-missing` |

### Phase Requirements → Test Map
| Req ID | Comportamiento | Tipo | Comando | Archivos existentes |
|--------|---------------|------|---------|---------------------|
| TEST-01 | decode válido/inválido, formatos, megapixel limit, CMYK, EXIF | unit | `.venv/bin/python -m pytest tests/test_processor.py -x` | ✅ tests/test_processor.py |
| TEST-01 | autocrop básico, guard <5%, disabled | unit | `.venv/bin/python -m pytest tests/test_processor.py::TestAutocrop -x` | ✅ |
| TEST-01 | _clean_alpha_artifacts multi-componente (GAP) | unit | `.venv/bin/python -m pytest tests/test_processor.py -k "artifact" -x` | ❌ Wave 0 |
| TEST-01 | autocrop bbox=None (GAP) | unit | `.venv/bin/python -m pytest tests/test_processor.py -k "bbox_none" -x` | ❌ Wave 0 |
| TEST-01 | pipeline unknown exception wrapping (GAP) | unit | `.venv/bin/python -m pytest tests/test_processor.py -k "unknown_exception" -x` | ❌ Wave 0 |
| TEST-01 | pipeline completo end-to-end 800x800 | unit | `.venv/bin/python -m pytest tests/test_processor.py::TestProcessImage -x` | ✅ |
| TEST-02 | job completo, 503, max_concurrent, timeout, estado | async unit | `.venv/bin/python -m pytest tests/test_queue.py -x` | ✅ tests/test_queue.py (100% cov) |
| TEST-03 | POST /process success + 6 headers | integration | `.venv/bin/python -m pytest tests/test_api.py::test_process_headers -x` | ✅ |
| TEST-03 | POST /process 422 campos faltantes, 400 imagen inválida | integration | `.venv/bin/python -m pytest tests/test_api.py -k "422 or 400" -x` | ✅ |
| TEST-03 | POST /process 500 internal error (GAP) | integration | `.venv/bin/python -m pytest tests/test_api.py -k "500" -x` | ❌ Wave 0 |
| TEST-03 | GET /health estructura completa + model_swapping | integration | `.venv/bin/python -m pytest tests/test_api.py tests/test_ui.py -k "health" -x` | ✅ |
| TEST-03 | GET/POST /config — merge, persistencia, rechazo | integration | `.venv/bin/python -m pytest tests/test_config_router.py -x` | ✅ |
| TEST-03 | POST /config invalid JSON body (GAP) | integration | `.venv/bin/python -m pytest tests/test_config_router.py -k "invalid_json" -x` | ❌ Wave 0 |
| TEST-03 | GET /ui sirve HTML válido, autocontenido | integration | `.venv/bin/python -m pytest tests/test_ui.py -x` | ✅ |
| TEST-03 | GET /status con historial | integration | `.venv/bin/python -m pytest tests/test_config_router.py -k "status" -x` | ✅ |

### Sampling Rate
- **Por task commit:** `.venv/bin/python -m pytest tests/ -q`
- **Por wave merge:** `.venv/bin/python -m pytest tests/ --cov=app --cov-report=term-missing`
- **Phase gate:** Full suite verde con coverage >= 80% antes de `/gsd:verify-work`

### Wave 0 Gaps
- [ ] `pytest-cov` — instalar en .venv: `.venv/bin/pip install "pytest-cov>=6.0"`
- [ ] `tests/test_processor.py` — agregar: `test_autocrop_removes_small_artifacts`, `test_autocrop_bbox_none`, `test_pipeline_unknown_exception_wrapped`, `test_process_image_enhance_not_in_steps_when_default`
- [ ] `tests/test_api.py` — agregar: `test_process_500_internal_error`
- [ ] `tests/test_config_router.py` — agregar: `test_post_config_invalid_json_body`, `test_post_config_model_change`

*(Archivos de test existentes — solo agregar funciones, no crear nuevos archivos)*

---

## Project Constraints (from CLAUDE.md)

Directivas del CLAUDE.md del proyecto aplicables a esta fase:

| Directiva | Impacto en Phase 5 |
|-----------|-------------------|
| RAM: ≤ 2 GB para el container | No aplica a tests (corren localmente, no en container) |
| Modelo rembg: sesión global inicializada una vez en startup, nunca por request | **Crítico:** tests NUNCA crean `new_session()` real. Siempre mockear con `patch("app.main.new_session", return_value=MagicMock())` |
| asyncio.to_thread() obligatorio para operaciones CPU-bound | Ya manejado en queue.py — los tests de queue verifican esto en `test_to_thread` |
| Formato de salida: WebP únicamente, RGB (sin alpha en output final) | `test_full_pipeline` ya verifica mode="RGB" y size=(800,800) |
| pytest 9.0.2, pytest-asyncio 1.3.0, httpx 0.28.1, pytest-cov | Stack fijo — no usar alternativas |
| yaml.safe_load siempre | No aplica a tests directamente — ya en el código fuente |
| Orden del pipeline: fijo e inamovible | `test_full_pipeline` verifica steps_applied contiene decode y encode |

---

## Sources

### Primary (HIGH confidence)
- Código fuente del proyecto — auditoría directa de `app/` y `tests/` — HIGH
- Ejecución de `pytest` con coverage — 94 tests, 93% cobertura, 44 statements faltantes — HIGH

### Secondary (MEDIUM confidence)
- `pyproject.toml` — configuración de pytest y dependencias — HIGH
- `requirements-dev.txt` — stack de testing declarado — HIGH
- `.planning/phases/05-tests-hardening/05-CONTEXT.md` — decisiones locked — HIGH

---

## Metadata

**Confidence breakdown:**
- Gaps identificados: HIGH — derivado de ejecución real de pytest --cov
- Patrones establecidos: HIGH — derivados del código fuente existente
- Tests nuevos necesarios: HIGH — 5-6 tests concretos mapeados a líneas específicas

**Research date:** 2026-03-30
**Valid until:** Mientras el código fuente no cambie — los gaps son deterministas
