---
phase: 01-pipeline-core-api-basica
verified: 2026-03-30T15:00:00Z
status: passed
score: 5/5 must-haves verified
re_verification: false
gaps: []
human_verification:
  - test: "Docker build completa sin errores y el modelo queda embebido"
    expected: "docker compose build finaliza, la imagen no necesita descargar nada en runtime"
    why_human: "Requiere Docker disponible. La verificacion automatizada confirma el Dockerfile y scripts son correctos, pero no puede ejecutar el build."
  - test: "RAM bajo 2GB durante procesamiento real con isnet-general-use"
    expected: "docker stats muestra MEM USAGE < 2GB durante un POST /process real"
    why_human: "Requiere container corriendo con modelo ONNX cargado. El SUMMARY reporta 1.48GB pico pero no es verificable programaticamente."
  - test: "Calidad visual del output (fondo blanco limpio, producto centrado, sin halo)"
    expected: "WebP 800x800 RGB con fondo blanco, producto centrado con 10% padding, bordes suaves"
    why_human: "La calidad perceptual del resultado con rembg real no puede verificarse con asserts automatizados."
---

# Phase 01: Pipeline Core + API Basica — Verification Report

**Phase Goal:** El servicio acepta una imagen y devuelve un WebP estandarizado 800x800 con fondo blanco, corriendo en Docker con el modelo pre-descargado y listo para integrarse con n8n
**Verified:** 2026-03-30
**Status:** PASSED
**Re-verification:** No — verificacion inicial

---

## Goal Achievement

### Observable Truths (Success Criteria del ROADMAP)

| #   | Truth                                                                                                                      | Status     | Evidence                                                                                                                     |
|-----|----------------------------------------------------------------------------------------------------------------------------|------------|------------------------------------------------------------------------------------------------------------------------------|
| 1   | Se puede hacer POST /process con imagen JPG/PNG/WebP y recibir WebP exactamente 800x800 RGB con fondo blanco               | VERIFIED   | pipeline produce 800x800 RGB WEBP (spot check con PIL); test_full_pipeline pasa; composite() crea canvas blanco RGB          |
| 2   | GET /health responde con status del servicio, modelo cargado y uptime incluso mientras se procesa una imagen               | VERIFIED   | health_endpoint lee app.state directamente sin tocar el queue; spot check retorna `status: ok, model_loaded: True, uptime`   |
| 3   | docker compose up levanta el servicio sin descargar nada adicional (modelo embebido en la imagen)                          | VERIFIED   | Dockerfile descarga modelo en build time via `RUN python scripts/download_models.py isnet-general-use`; SUMMARY confirma OK  |
| 4   | Segunda request mientras hay una en proceso recibe 503 si la cola esta llena, o espera su turno si hay capacidad           | VERIFIED   | QueueFullError -> 503 confirmado en spot check; asyncio.Semaphore(max_concurrent=1) via asyncio.wait_for con timeout         |
| 5   | La configuracion se lee de settings.yaml al startup y el snapshot del config es inmutable durante cada job                 | VERIFIED   | ConfigManager.get_snapshot() usa model_copy(deep=True); spot check confirma que mutar snapshot no afecta config global       |

**Score:** 5/5 truths verified

**Nota sobre modelo:** El ROADMAP success criterion #3 menciona `birefnet-lite` pero la implementacion usa `isnet-general-use`. Este cambio fue deliberado y documentado en 01-05-SUMMARY (birefnet-general-lite requeria ~3.9GB pico, excediendo el limite de 2GB; isnet-general-use opera con ~1.5GB). El goal se cumple — el modelo esta embebido en la imagen.

---

### Required Artifacts

| Artifact                   | Expected                                                     | Status     | Details                                                                    |
|----------------------------|--------------------------------------------------------------|------------|----------------------------------------------------------------------------|
| `pyproject.toml`           | Configuracion de proyecto con asyncio_mode=auto              | VERIFIED   | Contiene `asyncio_mode = "auto"` bajo `[tool.pytest.ini_options]`          |
| `config/settings.yaml`     | Config default del servicio (model, size=800, queue)         | VERIFIED   | isnet-general-use, size=800, quality=85, max_concurrent=1                  |
| `app/models.py`            | Pydantic v2 models: AppConfig, ProcessingResult, ErrorResponse| VERIFIED  | Las 3 clases exportadas; AppConfig mapea 1:1 con settings.yaml             |
| `app/config.py`            | ConfigManager con yaml.safe_load y get_snapshot inmutable    | VERIFIED   | usa yaml.safe_load, model_copy(deep=True), 29 lineas — sustantivo          |
| `app/processor.py`         | Pipeline 7 steps + process_image()                           | VERIFIED   | 482 lineas (min_lines=150); todos los steps implementados como funciones puras |
| `app/queue.py`             | JobQueue con Semaphore, QueueFullError, QueueTimeoutError     | VERIFIED   | 238 lineas (min_lines=80); asyncio.Semaphore, asyncio.to_thread, asyncio.wait_for |
| `app/main.py`              | FastAPI app con lifespan, sesion rembg global, routers       | VERIFIED   | 87 lineas (min_lines=40); lifespan inicializa config, rembg session, queue  |
| `app/router_api.py`        | Endpoints POST /process y GET /health                        | VERIFIED   | 178 lineas (min_lines=80); ambos endpoints con todos los error codes       |
| `Dockerfile`               | Build con modelo pre-descargado, python:3.11-slim            | VERIFIED   | FROM python:3.11-slim, OMP_NUM_THREADS=2, HEALTHCHECK start-period=90s    |
| `docker-compose.yml`       | Compose con mem_limit=2g, cpus=1.5, volume config/           | VERIFIED   | mem_limit: 2g, cpus: "1.5", solo ./config:/app/config como volumen        |
| `scripts/download_models.py`| Script pre-descarga modelo en build time                     | VERIFIED   | Usa new_session(), invocado con `isnet-general-use` en Dockerfile          |
| `.dockerignore`            | Excluye .git, tests/, artefactos                             | VERIFIED   | Contiene .git, tests/, .venv, __pycache__                                  |
| `tests/conftest.py`        | Fixtures compartidos con sample_jpeg, config_manager         | VERIFIED   | sample_jpeg, sample_png_transparent, sample_cmyk, sample_large_image       |
| `tests/test_config.py`     | 4 tests del ConfigManager                                    | VERIFIED   | 4 test functions, todas pasan                                              |
| `tests/test_processor.py`  | 31+ tests unitarios del pipeline                             | VERIFIED   | 31 test functions; rembg mockeado en todos                                 |
| `tests/test_queue.py`      | 9+ tests del JobQueue                                        | VERIFIED   | 9 test functions; todos los escenarios cubiertos                           |
| `tests/test_api.py`        | 11 tests de integracion HTTP                                 | VERIFIED   | 11 test functions; 8 requeridos minimo                                     |

---

### Key Link Verification

| From                | To                   | Via                              | Status   | Details                                                              |
|---------------------|----------------------|----------------------------------|----------|----------------------------------------------------------------------|
| `app/config.py`     | `app/models.py`      | `from app.models import AppConfig` | WIRED  | Linea 4: `from app.models import AppConfig`                          |
| `app/config.py`     | `config/settings.yaml`| `yaml.safe_load`                | WIRED    | Linea 15: `data = yaml.safe_load(f) or {}`                           |
| `app/processor.py`  | `app/models.py`      | import AppConfig, ProcessingResult| WIRED  | Linea 17: `from app.models import AppConfig, ProcessingResult`       |
| `app/processor.py`  | `rembg`              | `rembg.remove()`                 | WIRED    | Linea 139: `result_bytes = rembg.remove(input_bytes, session=...)`   |
| `app/processor.py`  | `PIL`                | Image.open, ImageOps, ImageEnhance| WIRED  | Linea 13: `from PIL import Image, ImageEnhance, ImageFile, ImageOps` |
| `app/queue.py`      | `app/models.py`      | `from app.models import`         | WIRED    | No importa modelos directamente — recibe config_snapshot como Any (correcto, el caller es responsible) |
| `app/queue.py`      | `asyncio`            | Semaphore, to_thread, wait_for   | WIRED    | Lineas 88, 156, 180: las tres primitivas usadas correctamente        |
| `app/main.py`       | `app/config.py`      | ConfigManager en lifespan        | WIRED    | Linea 32: `from app.config import ConfigManager`; usado en lifespan  |
| `app/main.py`       | `app/queue.py`       | JobQueue en lifespan             | WIRED    | Linea 31: `from app.queue import JobQueue`; inicializado en lifespan |
| `app/main.py`       | `rembg`              | `new_session()` en lifespan      | WIRED    | Linea 19: `from rembg import new_session`; llamado en lifespan startup |
| `app/router_api.py` | `app/queue.py`       | `submit_job()` en POST /process  | WIRED    | Linea 83: `result = await queue.submit_job(...)`                     |
| `app/router_api.py` | `app/processor.py`   | `process_image` pasado a submit_job| WIRED | Linea 83: `process_fn=process_image` en submit_job call              |
| `docker-compose.yml`| `Dockerfile`         | `build: .`                       | WIRED    | Linea 3: `build: .`                                                  |
| `docker-compose.yml`| `config/settings.yaml`| `./config:/app/config` volume   | WIRED    | Linea 8: `- ./config:/app/config`                                    |
| `Dockerfile`        | `scripts/download_models.py` | `RUN python scripts/download_models.py` | WIRED | Linea 22: `RUN python scripts/download_models.py isnet-general-use` |

---

### Data-Flow Trace (Level 4)

| Artifact            | Data Variable     | Source                                       | Produces Real Data | Status   |
|---------------------|-------------------|----------------------------------------------|--------------------|----------|
| `app/router_api.py` | `result`          | `await queue.submit_job(process_image, ...)` | Si — pipeline real | FLOWING  |
| `app/router_api.py` | health response   | `queue.state.*`, `app.state.model_loaded`    | Si — estado en memoria actualizado en cada job | FLOWING |
| `app/processor.py`  | `result_bytes`    | `encode_webp(composite(autocrop(...)))`      | Si — procesamiento real con Pillow | FLOWING |
| `app/queue.py`      | `result`          | `asyncio.to_thread(process_fn, ...)`         | Si — delega a process_image real | FLOWING  |

---

### Behavioral Spot-Checks

| Behavior                                          | Command                                                | Result                                       | Status  |
|---------------------------------------------------|--------------------------------------------------------|----------------------------------------------|---------|
| Pipeline produce WebP 800x800 RGB                 | `process_image(jpeg_bytes, ...)` con rembg mockeado    | format=WEBP, size=(800,800), mode=RGB         | PASS    |
| GET /health retorna estado correcto               | `client.get('/health')` via ASGI sin servidor          | 200, status=ok, model_loaded=True, queue OK  | PASS    |
| POST /process con cola llena retorna 503          | `submit_job` mockeado con QueueFullError               | 503, error=queue_full                         | PASS    |
| ConfigManager carga settings.yaml correctamente  | `ConfigManager().config.rembg.model`                   | isnet-general-use, size=800, max_concurrent=1 | PASS    |
| Snapshot inmutable (CONF-06)                      | Mutar snap1.output.size; assert snap2.output.size==800 | No hubo fuga de mutacion                      | PASS    |
| Todos los imports y rutas registradas             | `from app.main import app; app.routes`                 | /process y /health presentes                  | PASS    |
| Suite de tests completa                           | `pytest tests/ -q`                                     | 55 passed, 4 warnings en 7.56s                | PASS    |

---

### Requirements Coverage

| Requirement | Source Plan | Description                                                                               | Status      | Evidence                                                              |
|-------------|-------------|-------------------------------------------------------------------------------------------|-------------|-----------------------------------------------------------------------|
| PIPE-01     | 01-02       | Decodifica JPG, PNG, WebP, BMP y TIFF correctamente                                       | SATISFIED   | `decode_and_validate()` + 5 tests de formato en TestDecodeAndValidate |
| PIPE-02     | 01-02       | Aplica EXIF transpose antes de procesar                                                    | SATISFIED   | `ImageOps.exif_transpose(img)` linea 71 processor.py; test_exif_transpose |
| PIPE-03     | 01-02       | Remueve fondo con rembg sesion global                                                      | SATISFIED   | `remove_background()` usa session pasada como parametro; sesion global en lifespan |
| PIPE-04     | 01-02       | Autocrop al bounding box via canal alpha                                                   | SATISFIED   | `autocrop()` con getbbox() sobre alpha binarizado; test_autocrop_basic |
| PIPE-05     | 01-02       | Escala manteniendo aspect ratio (fit-inside)                                               | SATISFIED   | `calculate_scale_and_position()` usa `min(available/w, available/h)` |
| PIPE-06     | 01-02       | Canvas 800x800 fondo blanco, producto centrado, padding                                    | SATISFIED   | `composite()` crea canvas RGB 800x800 con background_color; offset centrado |
| PIPE-07     | 01-02       | Aplica brightness/contrast si estan configurados                                           | SATISFIED   | `enhance()` con skip optimization si ambos son 1.0                   |
| PIPE-08     | 01-02       | Encode WebP con calidad configurable                                                       | SATISFIED   | `encode_webp()` usa config.output.quality; quality=0 activa lossless |
| PIPE-09     | 01-02       | Output siempre RGB sin canal alpha                                                         | SATISFIED   | `composite()` termina con `.convert("RGB")`; test_composite_output_rgb |
| PIPE-10     | 01-01, 01-04| Pipeline en orden fijo: decode->rembg->autocrop->scale->composite->enhance->encode         | SATISFIED   | `process_image()` ejecuta steps en orden fijo e inamovible            |
| API-01      | 01-04       | POST /process acepta multipart/form-data con image (file) y article_id (string)           | SATISFIED   | `UploadFile = File(...)`, `article_id: str = Form(...)` en router_api |
| API-02      | 01-04       | POST /process retorna image/webp con 6 headers X-*                                        | SATISFIED   | `Response(media_type="image/webp", headers={X-Article-Id, ...})`     |
| API-03      | 01-04       | POST /process acepta override parcial de config (JSON string, deep merge)                  | SATISFIED   | `_deep_merge(config_dict, override_dict)` + test_process_override    |
| API-04      | 01-04       | POST /process retorna 400/422/503/504 segun el caso                                        | SATISFIED   | Todos los except handlers presentes; tests individuales para cada codigo |
| API-05      | 01-04       | GET /health retorna status, queue state, model info, uptime                                | SATISFIED   | `health_endpoint()` retorna status, queue, model_loaded, model_name, uptime_seconds |
| QUEUE-01    | 01-03       | Cola usa asyncio.Semaphore con max_concurrent configurable (default 1)                     | SATISFIED   | `asyncio.Semaphore(max_concurrent)` en JobQueue.__init__             |
| QUEUE-02    | 01-03       | Requests que exceden max_queue_size reciben 503 inmediato                                  | SATISFIED   | Check `queued_jobs >= max_queue_size` antes de encolar; QueueFullError |
| QUEUE-03    | 01-03       | Requests que esperan mas de timeout_seconds reciben 504                                    | SATISFIED   | `asyncio.wait_for(semaphore.acquire(), timeout=self._timeout_seconds)` |
| QUEUE-04    | 01-03       | Trabajo CPU-bound se ejecuta en asyncio.to_thread                                          | SATISFIED   | `await asyncio.to_thread(process_fn, ...)` linea 180 queue.py        |
| CONF-01     | 01-01       | Configuracion se lee de un archivo YAML (settings.yaml)                                    | SATISFIED   | `yaml.safe_load(f)` en ConfigManager._load()                         |
| CONF-06     | 01-01       | Config snapshot se toma al inicio de cada job (inmutable durante procesamiento)             | SATISFIED   | `config_manager.get_snapshot()` en router_api antes de submit_job; model_copy(deep=True) |
| DOCK-01     | 01-05       | Dockerfile basado en python:3.11-slim con modelo pre-descargado en build time               | SATISFIED   | `FROM python:3.11-slim`; `RUN python scripts/download_models.py isnet-general-use` |
| DOCK-02     | 01-05       | docker-compose.yml con limites de recursos (mem_limit: 2g, cpus: 1.5)                     | SATISFIED   | `mem_limit: 2g`, `cpus: "1.5"` en docker-compose.yml                |
| DOCK-03     | 01-05       | HEALTHCHECK con start_period: 90s                                                          | SATISFIED   | `HEALTHCHECK --interval=30s --timeout=10s --start-period=90s --retries=3` |
| DOCK-04     | 01-05       | Solo se monta config/ como volumen                                                         | SATISFIED   | Un solo volume mount: `./config:/app/config`                         |
| DOCK-05     | 01-05       | Container arranca limpio desde cero sin dependencias externas                               | HUMAN NEEDED| Verificado por usuario en SUMMARY (task 2 checkpoint aprobado); no testeable sin Docker |

---

### Anti-Patterns Found

| File             | Line | Pattern                                                              | Severity | Impact                                           |
|------------------|------|----------------------------------------------------------------------|----------|--------------------------------------------------|
| `app/processor.py` | 115 | `alpha_channel.getdata()` — DeprecationWarning en Pillow 12         | Info     | Warning visible en tests; funcional hasta Pillow 14; no afecta behavior |

Ningun TODO/FIXME, placeholder, return null, o implementacion hueca encontrada en la codebase.

---

### Human Verification Required

#### 1. Docker Build — Modelo Embebido

**Test:** Ejecutar `docker compose build` desde el directorio del proyecto
**Expected:** Build completa sin errores; `RUN python scripts/download_models.py isnet-general-use` descarga el modelo durante el build y no se descarga nada en runtime
**Why human:** Requiere Docker instalado y conexion de red para el build inicial. Verificado en SUMMARY como aprobado por el usuario, pero no es reproducible programaticamente en esta verificacion.

#### 2. RAM Usage Under Load

**Test:** Ejecutar `docker compose up -d`, esperar 60s, hacer `POST /process` con una imagen real, luego `docker stats --no-stream imgproc`
**Expected:** MEM USAGE < 2GB durante el procesamiento
**Why human:** Requiere container corriendo con modelo ONNX cargado. El SUMMARY reporta 1.48GB pico.

#### 3. Calidad Visual del Output

**Test:** Hacer `POST /process` con una foto de producto real (JPG o PNG)
**Expected:** WebP 800x800 con fondo blanco limpio, producto centrado con padding visible, sin halo negro en bordes, sin artefactos de rembg
**Why human:** Calidad perceptual no verificable con asserts; depende del modelo de remocion de fondo sobre imagenes reales.

---

## Gaps Summary

No se encontraron gaps bloqueantes. El goal de la fase esta completamente alcanzado en el codigo:

- El pipeline completo (7 steps) esta implementado como funciones puras en `app/processor.py`
- La API HTTP expone `POST /process` y `GET /health` con todos los error codes y headers requeridos
- El JobQueue controla concurrencia con asyncio.Semaphore y ejecuta trabajo CPU-bound en asyncio.to_thread
- El ConfigManager carga settings.yaml y produce snapshots inmutables por job
- El Dockerfile embebe el modelo `isnet-general-use` en build time (cambio deliberado respecto al plan original de `birefnet-lite` por restriccion de RAM de 2GB)
- La suite de tests tiene 55 tests que pasan: 4 de config, 31 de processor, 9 de queue, 11 de API

La unica desviacion notable del plan original es el modelo rembg: el plan especificaba `birefnet-lite` pero la implementacion usa `isnet-general-use`. Este cambio fue necesario para cumplir la restriccion de RAM de 2GB (constraint critico del proyecto documentado en CLAUDE.md) y fue documentado y aprobado en el checkpoint humano del plan 01-05. El goal "servicio acepta imagen y devuelve WebP 800x800 con fondo blanco" sigue cumplido.

---

_Verified: 2026-03-30_
_Verifier: Claude (gsd-verifier)_
