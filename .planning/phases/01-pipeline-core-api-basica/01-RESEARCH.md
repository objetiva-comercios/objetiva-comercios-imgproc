# Phase 1: Pipeline Core + API Basica - Research

**Researched:** 2026-03-30
**Domain:** Python image processing microservice — rembg, Pillow, FastAPI, ONNX, Docker
**Confidence:** HIGH

---

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

**D-01:** Respuestas de error en JSON estructurado: `{"error": "tipo", "detail": "mensaje", "article_id": "..."}` con Content-Type: application/json

**D-02:** Error 400 (imagen corrupta) usa mensaje generico "Invalid or corrupt image" — sin exponer internals de Pillow

**D-03:** Formato structured JSON para todos los logs: `{"level": "info", "event": "rembg_complete", "duration_ms": 3200, "article_id": "ART-001"}`

**D-04:** Un log por cada step del pipeline (decode, rembg, autocrop, scale, composite, enhance, encode) con duracion individual. Permite identificar bottlenecks

**D-05:** Limite de megapixels en la entrada: rechazar imagenes > 25 megapixels con 400. Protege contra OOM (una imagen 8000x8000 RGBA = ~256MB en RAM)

**D-06:** Imagenes con alpha pre-existente (PNG transparente con >10% pixeles transparentes): saltear rembg y pasar directo a autocrop. Ahorra 3-10s de procesamiento innecesario

**D-07:** Imagenes CMYK: convertir automaticamente a RGB antes de procesar (silenciosamente). rembg requiere RGB/RGBA

**D-08:** EXIF transpose aplicado siempre antes de procesar (ya definido en PIPE-02)

**D-09:** Fail fast: si cualquier step falla, abortar inmediatamente y retornar 500 con detalle del step que fallo. Sin fallback ni imagen parcial

**D-10:** Solo timeout global (queue.timeout_seconds). Sin timeout por step individual. Si rembg se cuelga, el timeout global lo mata

### Claude's Discretion

Ninguna area delegada — todas las decisiones fueron tomadas explicitamente por el usuario.

### Deferred Ideas (OUT OF SCOPE)

Ninguna — la discusion se mantuvo dentro del scope de la fase.

</user_constraints>

---

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| PIPE-01 | Decodifica imagenes JPG, PNG, WebP, BMP y TIFF correctamente | Pillow Image.open() soporta todos estos formatos nativamente; convertir a RGBA post-decode |
| PIPE-02 | Aplica EXIF transpose antes de procesar (fotos de celular rotadas) | `ImageOps.exif_transpose(img)` — PRIMER step del pipeline, pre-verificado como pitfall critico |
| PIPE-03 | Remueve fondo usando rembg con sesion global | `rembg.remove(bytes, session=global_session)` — sesion inicializada en lifespan, NUNCA por request |
| PIPE-04 | Recorta al bounding box del producto via canal alpha | `img.split()[3].getbbox()` con threshold configurable; guardia si bbox < 5% area total |
| PIPE-05 | Escala el producto manteniendo aspect ratio (fit-inside) | `scale = min(available_px/w, available_px/h)` seguido de `Image.resize()` con LANCZOS |
| PIPE-06 | Compone el producto centrado sobre canvas 800x800 fondo blanco con padding | `Image.new("RGB", (800,800), (255,255,255))` + `canvas.paste(prod, offset, mask=alpha)` |
| PIPE-07 | Aplica ajustes de brightness y contrast si configurados | `ImageEnhance.Brightness/Contrast(img).enhance(factor)` — saltear si ambos son 1.0 |
| PIPE-08 | Codifica resultado como WebP con calidad configurable | `img.save(buf, format="WEBP", quality=q)` — si q==0 usar `lossless=True` |
| PIPE-09 | Output siempre RGB (sin alpha) de exactamente el tamano configurado | Garantizado por el composite step — el canvas final es `Image.new("RGB", ...)` |
| PIPE-10 | Pipeline en orden fijo: decode→rembg→autocrop→scale→composite→enhance→encode | Orden inamovible definido en PRD seccion 6; funciones puras en secuencia lineal |
| API-01 | POST /process acepta multipart/form-data con image (file) y article_id (string) | FastAPI `UploadFile` + `Form` con `python-multipart` instalado |
| API-02 | POST /process retorna image/webp con headers X-* de metadata | `Response(content=bytes, media_type="image/webp", headers={...})` |
| API-03 | POST /process acepta override parcial de config (JSON string, deep merge) | `Form(default=None)` para el campo override; deep merge sobre ConfigSnapshot antes del job |
| API-04 | POST /process retorna 400/422/503/504 segun el caso | `HTTPException(status_code=...)` con JSON body estructurado segun D-01 |
| API-05 | GET /health retorna status, estado de la cola, modelo cargado, uptime | Lee `app.state` directamente sin tocar la queue (respuesta instantanea) |
| QUEUE-01 | Cola usa asyncio.Semaphore con max_concurrent configurable (default 1) | `asyncio.Semaphore(config.queue.max_concurrent)` inicializado en lifespan |
| QUEUE-02 | Requests que exceden max_queue_size reciben 503 inmediato | Verificar `queued_jobs >= max_queue_size` ANTES de encolar, retornar 503 sin esperar |
| QUEUE-03 | Requests que esperan mas de timeout_seconds reciben 504 | `asyncio.wait_for(semaphore.acquire(), timeout=timeout_seconds)` + `TimeoutError` → 504 |
| QUEUE-04 | Trabajo CPU-bound se ejecuta en asyncio.to_thread | `await asyncio.to_thread(process_image_sync, bytes, config, session)` dentro del job |
| CONF-01 | Configuracion se lee de un archivo YAML (settings.yaml) | `yaml.safe_load()` al startup; `PyYAML 6.0.3` |
| CONF-06 | Config snapshot se toma al inicio de cada job (inmutable durante procesamiento) | `config_snapshot = config_manager.get_snapshot()` antes de `asyncio.to_thread()` |
| DOCK-01 | Dockerfile basado en python:3.11-slim con modelo pre-descargado en build time | `RUN python -c "from rembg import new_session; new_session('birefnet-lite')"` en Dockerfile |
| DOCK-02 | docker-compose.yml con limites de recursos (mem_limit: 2g, cpus: 1.5) | `deploy.resources.limits` en docker-compose v3.x |
| DOCK-03 | HEALTHCHECK con start_period: 90s | `HEALTHCHECK --start-period=90s CMD curl -f http://localhost:8010/health` |
| DOCK-04 | Solo se monta config/ como volumen | `volumes: - ./config:/app/config` — el resto es read-only en la imagen |
| DOCK-05 | Container arranca limpio sin dependencias externas | Modelo embebido en build time; `docker run --network none` debe funcionar |

</phase_requirements>

---

## Summary

Esta fase construye el microservicio completo desde cero: el pipeline de 7 steps (decode → rembg → autocrop → scale → composite → enhance → encode), la API HTTP basica (POST /process, GET /health), la cola in-memory con asyncio.Semaphore, la configuracion YAML y el Docker con modelo embebido.

Todo el stack esta ya especificado y versionado en CLAUDE.md y confirmado en la investigacion previa (STACK.md, ARCHITECTURE.md, PITFALLS.md). El PRD seccion 6 define cada step del pipeline con pseudocodigo ejecutable. Los pitfalls criticos son bien conocidos: sesion rembg global (no por request), asyncio.to_thread obligatorio para no bloquear el event loop, e intra_op_num_threads configurado para el container.

La estructura del proyecto esta definida en el PRD seccion 4. El orden de construccion recomendado es: config → processor (pipeline steps) → rembg session → queue manager → FastAPI app/routes → Dockerfile. Este orden garantiza que cada componente se puede testear antes de integrarlo al siguiente.

**Primary recommendation:** Construir en el orden definido en ARCHITECTURE.md (config → processor → session → queue → API → Docker), usando las funciones puras del pipeline con context managers de Pillow en cada step para evitar memory leaks.

---

## Standard Stack

### Core

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| Python | 3.11 | Runtime | rembg 2.0.74 requiere >=3.11; slim image para Docker minimo |
| FastAPI | 0.135.2 | API HTTP async | Estandar de facto Python async 2026; Pydantic v2 integrado |
| uvicorn[standard] | 0.42.0 | ASGI server | Unico ASGI maduro production-ready; `[standard]` incluye uvloop+httptools |
| rembg[cpu] | 2.0.74 | Background removal | Libreria referente; sesion ONNX reutilizable; `[cpu]` evita onnxruntime-gpu |
| Pillow | 12.1.1 | Manipulacion de imagenes | Unica opcion madura para crop/scale/composite/enhance/WebP en Python |
| onnxruntime | 1.24.4 | Inferencia ONNX | Dependencia de rembg; se instala via `rembg[cpu]`, NO pinear por separado |
| PyYAML | 6.0.3 | Config YAML | `yaml.safe_load()` siempre; nunca `yaml.load()` sin Loader |
| python-multipart | >=0.0.9 | Form-data upload | FastAPI requiere esto para `UploadFile`; sin esto POST /process falla en runtime |

### Supporting

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| watchdog | 6.0.0 | Hot-reload config YAML | En Fase 1: solo lectura al startup; watchdog se agrega en Fase 2. Ver nota abajo |
| Jinja2 | 3.1.6 | Templates Web UI | Incluida como dep transitiva de FastAPI; solo activa en Fase 4 |

> **Nota watchdog en Fase 1:** CONF-05 (hot-reload) esta en Fase 2. En Fase 1 la config se lee al startup y es inmutable. Sin embargo, watchdog debe estar en requirements.txt desde Fase 1 para que el Dockerfile sea consistente con versiones futuras. NO inicializar el Observer en el lifespan de Fase 1.

### Development & Testing

| Tool | Version | Purpose | Notes |
|------|---------|---------|-------|
| pytest | 9.0.2 | Test runner | Configurar via `pyproject.toml` |
| pytest-asyncio | 1.3.0 | Tests async FastAPI | `asyncio_mode = "auto"` en pyproject.toml |
| httpx | 0.28.1 | Cliente HTTP tests | `httpx.AsyncClient(app=app, base_url="http://test")` para tests sin servidor real |
| pytest-cov | >=6.0 | Coverage | `--cov=app --cov-report=term-missing` |

### Installation

```bash
# requirements.txt (produccion)
fastapi==0.135.2
uvicorn[standard]==0.42.0
rembg[cpu]==2.0.74
Pillow==12.1.1
typer==0.24.1
Jinja2==3.1.6
PyYAML==6.0.3
watchdog==6.0.0
python-multipart>=0.0.9
# onnxruntime se instala como dep transitiva de rembg[cpu] — no pinear

# requirements-dev.txt
pytest==9.0.2
pytest-asyncio==1.3.0
pytest-cov>=6.0
httpx==0.28.1
```

---

## Architecture Patterns

### Recommended Project Structure

```
image-standardizer/
├── app/
│   ├── __init__.py
│   ├── main.py              # FastAPI app + lifespan (startup/shutdown)
│   ├── config.py            # ConfigManager: carga YAML, get_snapshot()
│   ├── processor.py         # pipeline completo: process_image_sync()
│   ├── queue.py             # JobQueue: asyncio.Semaphore + contadores
│   ├── models.py            # Pydantic models: AppConfig, ProcessingResult, HealthResponse
│   ├── router_api.py        # Endpoints: POST /process, GET /health
│   └── router_config.py     # Placeholder Fase 2 (GET/POST /config)
├── config/
│   └── settings.yaml        # Config default (copiada al container en build)
├── scripts/
│   └── download_models.py   # Ejecutado en Dockerfile para pre-descargar modelo
├── Dockerfile
├── docker-compose.yml
├── requirements.txt
└── requirements-dev.txt
```

> **Diferencia del PRD:** El PRD sugiere `router_config.py` completo pero CONF-02, CONF-03, CONF-04, CONF-05 son Fase 2. En Fase 1 solo existe `router_api.py` (process + health). El placeholder de config router puede existir vacio para no romper imports futuros.

### Build Order (CRITICO — respetar dependencias)

1. **app/models.py** — Pydantic models para AppConfig, ConfigSnapshot, ProcessingResult, HealthResponse, ErrorResponse
2. **app/config.py** — ConfigManager: `load_config()`, `get_snapshot()` (sin watchdog en Fase 1)
3. **config/settings.yaml** — archivo de configuracion con todos los defaults del PRD seccion 5
4. **app/processor.py** — `process_image_sync()` con los 7 steps, funciones puras, context managers
5. **app/queue.py** — JobQueue con asyncio.Semaphore, contadores, `submit()` async
6. **app/router_api.py** — POST /process + GET /health
7. **app/main.py** — FastAPI lifespan: inicializa rembg session, queue, config
8. **Dockerfile** — python:3.11-slim + deps + pre-download modelo + env vars ONNX
9. **docker-compose.yml** — limits, volumes, healthcheck, puerto 8010

### Pattern 1: Lifespan Singleton para rembg Session

```python
# app/main.py
from contextlib import asynccontextmanager
from fastapi import FastAPI
from rembg import new_session

@asynccontextmanager
async def lifespan(app: FastAPI):
    # STARTUP: carga del modelo una sola vez (~5-15s, OK en startup)
    config = load_config()
    app.state.rembg_session = new_session(config.rembg.model)
    app.state.current_model = config.rembg.model
    app.state.job_queue = JobQueue(config.queue)
    app.state.config = config
    app.state.start_time = time.time()
    yield
    # SHUTDOWN: limpieza (no hay observer en Fase 1)

app = FastAPI(lifespan=lifespan)
app.include_router(api_router)
```

### Pattern 2: asyncio.to_thread en queue.submit()

```python
# app/queue.py
import asyncio
from dataclasses import dataclass, field
from collections import deque

@dataclass
class QueueState:
    active_jobs: int = 0
    queued_jobs: int = 0
    total_processed: int = 0
    total_errors: int = 0
    job_history: deque = field(default_factory=lambda: deque(maxlen=50))

class JobQueue:
    def __init__(self, queue_config):
        self._semaphore = asyncio.Semaphore(queue_config.max_concurrent)
        self._max_queue_size = queue_config.max_queue_size
        self._timeout = queue_config.timeout_seconds
        self.state = QueueState()

    async def submit(self, image_bytes, article_id, config_snapshot, rembg_session):
        # Rechazar si cola llena (503 inmediato)
        if self.state.queued_jobs >= self._max_queue_size:
            raise QueueFullError()

        self.state.queued_jobs += 1
        try:
            # Esperar turno con timeout global (504 si expira)
            await asyncio.wait_for(
                self._semaphore.acquire(),
                timeout=self._timeout
            )
        except asyncio.TimeoutError:
            self.state.queued_jobs -= 1
            raise TimeoutError()

        self.state.queued_jobs -= 1
        self.state.active_jobs += 1
        try:
            # CPU-bound corre en thread separado — event loop libre
            result = await asyncio.to_thread(
                process_image_sync,
                image_bytes, article_id, config_snapshot, rembg_session
            )
            self.state.total_processed += 1
            self.state.job_history.append(result)
            return result
        except Exception:
            self.state.total_errors += 1
            raise
        finally:
            self.state.active_jobs -= 1
            self._semaphore.release()
```

### Pattern 3: Pipeline con funciones puras y context managers

```python
# app/processor.py
from PIL import Image, ImageOps, ImageEnhance
from io import BytesIO
import rembg

def process_image_sync(image_bytes, article_id, config, rembg_session):
    """Pipeline completo. Corre en un thread (via asyncio.to_thread)."""
    steps_applied = []
    t_start = time.monotonic()

    # STEP 1: Decode & Validate
    try:
        with Image.open(BytesIO(image_bytes)) as raw:
            raw.verify()  # valida sin decodificar del todo
        with Image.open(BytesIO(image_bytes)) as img:
            # Verificar megapixels (D-05)
            if img.width * img.height > 25_000_000:
                raise ValidationError("Image exceeds 25 megapixel limit")
            # EXIF transpose (PIPE-02, D-08) — PRIMER step
            img = ImageOps.exif_transpose(img)
            # Normalizar modo de color (D-07)
            if img.mode == "CMYK":
                img = img.convert("RGB")
            if img.mode not in ("RGB", "RGBA"):
                img = img.convert("RGBA" if "transparency" in img.info else "RGB")
            img = img.copy()  # liberar el file handle
        steps_applied.append("decode")
        _log_step("decode", t_start, article_id, img.size)
    except (OSError, SyntaxError) as e:
        raise InvalidImageError("Invalid or corrupt image") from e  # D-02

    # STEP 2: Background Removal (rembg)
    # Saltear si ya tiene alpha significativo (D-06)
    skip_rembg = False
    if img.mode == "RGBA":
        alpha = img.split()[3]
        transparent_ratio = sum(1 for p in alpha.getdata() if p < 10) / (img.width * img.height)
        if transparent_ratio > 0.10:
            skip_rembg = True

    if not skip_rembg:
        t_rembg = time.monotonic()
        img_bytes_for_rembg = _pil_to_bytes(img)
        result_bytes = rembg.remove(img_bytes_for_rembg, session=rembg_session,
                                    alpha_matting=config.rembg.alpha_matting)
        img = Image.open(BytesIO(result_bytes)).copy()
        steps_applied.append("rembg")
        _log_step("rembg", t_rembg, article_id, img.size)

    # STEP 3: Autocrop
    if config.autocrop.enabled:
        img = _autocrop(img, config.autocrop.threshold)
        steps_applied.append("autocrop")

    # STEPS 4+5: Scale + Composite
    canvas_px = config.output.size
    padding_px = int(canvas_px * config.padding.percent / 100) if config.padding.enabled else 0
    available_px = canvas_px - 2 * padding_px
    scale = min(available_px / img.width, available_px / img.height)
    new_w = int(img.width * scale)
    new_h = int(img.height * scale)
    resample = Image.Resampling.LANCZOS if scale < 1 else Image.Resampling.BICUBIC
    img_scaled = img.resize((new_w, new_h), resample=resample)

    canvas = Image.new("RGB", (canvas_px, canvas_px), tuple(config.output.background_color))
    offset_x = (canvas_px - new_w) // 2
    offset_y = (canvas_px - new_h) // 2
    if img_scaled.mode == "RGBA":
        canvas.paste(img_scaled, (offset_x, offset_y), mask=img_scaled.split()[3])
    else:
        canvas.paste(img_scaled, (offset_x, offset_y))
    img_scaled.close()
    steps_applied.extend(["scale", "composite"])

    # STEP 6: Enhancement
    if config.enhancement.brightness != 1.0 or config.enhancement.contrast != 1.0:
        canvas = ImageEnhance.Brightness(canvas).enhance(config.enhancement.brightness)
        canvas = ImageEnhance.Contrast(canvas).enhance(config.enhancement.contrast)
        steps_applied.append("enhance")

    # STEP 7: Encode WebP
    buf = BytesIO()
    save_kwargs = {"format": "WEBP", "quality": config.output.quality}
    if config.output.quality == 0:
        save_kwargs["lossless"] = True
    canvas.save(buf, **save_kwargs)
    canvas.close()
    steps_applied.append("encode")

    processing_time_ms = int((time.monotonic() - t_start) * 1000)
    return ProcessingResult(
        article_id=article_id,
        webp_bytes=buf.getvalue(),
        processing_time_ms=processing_time_ms,
        model_used=config.rembg.model if not skip_rembg else "none",
        original_dimensions=f"{img.width}x{img.height}",
        output_dimensions=f"{canvas_px}x{canvas_px}",
        steps_applied=steps_applied,
    )
```

### Pattern 4: ConfigManager simple para Fase 1

```python
# app/config.py
import yaml
import threading
from app.models import AppConfig

class ConfigManager:
    def __init__(self, config_path: str):
        self._path = config_path
        self._lock = threading.RLock()
        self._config = self._load()

    def _load(self) -> AppConfig:
        with open(self._path) as f:
            data = yaml.safe_load(f)
        return AppConfig(**data)  # Pydantic valida

    def get_snapshot(self) -> AppConfig:
        """Thread-safe. Retorna config inmutable para el job."""
        with self._lock:
            return self._config  # AppConfig es inmutable (frozen=True en Pydantic)
```

### Pattern 5: POST /process con override parcial (API-03)

```python
# app/router_api.py
from fastapi import APIRouter, UploadFile, File, Form, Request, HTTPException
from fastapi.responses import Response
import json

router = APIRouter()

@router.post("/process")
async def process_image(
    request: Request,
    image: UploadFile = File(...),
    article_id: str = Form(...),
    override: str = Form(default=None),
):
    image_bytes = await image.read()
    config_snapshot = request.app.state.config.get_snapshot()

    # Aplicar override parcial si se provee (API-03)
    if override:
        try:
            override_dict = json.loads(override)
            config_snapshot = _deep_merge_config(config_snapshot, override_dict)
        except json.JSONDecodeError:
            raise HTTPException(status_code=422, detail="Invalid override JSON")

    try:
        result = await request.app.state.job_queue.submit(
            image_bytes, article_id, config_snapshot,
            request.app.state.rembg_session
        )
    except QueueFullError:
        raise HTTPException(status_code=503,
                           detail={"error": "queue_full", "detail": "Service at capacity", "article_id": article_id})
    except TimeoutError:
        raise HTTPException(status_code=504,
                           detail={"error": "timeout", "detail": "Job timed out waiting in queue", "article_id": article_id})
    except InvalidImageError as e:
        raise HTTPException(status_code=400,
                           detail={"error": "invalid_image", "detail": str(e), "article_id": article_id})

    return Response(
        content=result.webp_bytes,
        media_type="image/webp",
        headers={
            "X-Article-Id": result.article_id,
            "X-Processing-Time-Ms": str(result.processing_time_ms),
            "X-Model-Used": result.model_used,
            "X-Original-Size": result.original_dimensions,
            "X-Output-Size": result.output_dimensions,
            "X-Steps-Applied": ",".join(result.steps_applied),
        }
    )
```

### Pattern 6: Dockerfile con modelo pre-descargado

```dockerfile
FROM python:3.11-slim

# Variables de entorno CRITICAS para ONNX thread management (PITFALL-3)
ENV OMP_NUM_THREADS=2
ENV OPENBLAS_NUM_THREADS=2
ENV U2NET_HOME=/root/.u2net

# Deps del sistema para Pillow y onnxruntime
RUN apt-get update && apt-get install -y --no-install-recommends \
    libgl1-mesa-glx libglib2.0-0 curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Pre-descargar modelo en build time (evita delay 1-3 min en primer request)
RUN python -c "from rembg import new_session; new_session('birefnet-lite')"

COPY . .

HEALTHCHECK --interval=30s --timeout=10s --start-period=90s --retries=3 \
    CMD curl -f http://localhost:8010/health || exit 1

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8010"]
```

### Anti-Patterns to Avoid

- **new_session() por request:** Crea sesion ONNX (~300MB) por cada request — OOMKill garantizado. Usar sesion global en `app.state`.
- **CPU-bound sin asyncio.to_thread:** Llamar rembg/Pillow directamente en `async def` bloquea el event loop — `/health` no responde durante inferencia. Siempre `asyncio.to_thread()`.
- **yaml.load() sin Loader:** Vulnerable a ejecucion de codigo arbitrario. Siempre `yaml.safe_load()`.
- **Image.open() sin context manager:** Pillow buffer leaks en servicio de larga duracion. Siempre `with Image.open(...) as img:`.
- **onnxruntime-gpu:** El VPS no tiene GPU. Instala CUDA deps (~2GB) innecesarios. Usar `rembg[cpu]`.
- **asyncio.Semaphore sin timeout:** Request bloqueado indefinidamente si pipeline falla sin liberar. Usar `asyncio.wait_for()`.
- **Image.MAX_IMAGE_PIXELS = None:** Vulnerable a DoS por imagen maliciosa. Usar D-05 (limite 25MP) en lugar de deshabilitar la proteccion.
- **python:3.11 (imagen completa):** ~875MB vs ~121MB para slim. Usar siempre `python:3.11-slim` para Python con dependencias cientificas.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Background removal con IA | Modelo ONNX custom, algoritmo erosion/dilatacion | `rembg.remove(bytes, session=session)` | birefnet-lite ya entrenado, API de una linea, session reutilizable |
| Resize con aspect ratio | Calcular manualmente scale y centrado | Formula `min(available/w, available/h)` + `Image.resize(LANCZOS)` | Pillow LANCZOS es la mejor calidad para downscale; la formula es 3 lineas |
| EXIF orientation | Leer EXIF tags manualmente, rotar con angulos | `ImageOps.exif_transpose(img)` | Maneja todos los casos EXIF (8 orientaciones) con una linea |
| WebP encode con calidad | Implementar encoder WebP | `img.save(buf, format="WEBP", quality=q)` | Pillow wrappea libwebp nativo |
| Form-data parsing | Parsear manualmente multipart/form-data | `UploadFile = File(...)` + `python-multipart` | FastAPI lo resuelve con type hints |
| Config validation | Validar manualmente tipos YAML | Pydantic `BaseModel` con `AppConfig` | Pydantic v2 valida, convierte tipos, reporta errores con campo y valor |
| Semaphore con timeout | `while True: try acquire, check time` | `asyncio.wait_for(sem.acquire(), timeout=t)` | asyncio maneja el cancellation correctamente |

**Key insight:** En este dominio, los problemas de mayor complejidad oculta son el thread management de ONNX (no configurarlo causa throttling del container) y la gestion de memoria de Pillow (context managers obligatorios).

---

## Common Pitfalls

### Pitfall 1: rembg Session no global — OOMKill garantizado

**What goes wrong:** Instanciar `new_session()` en cada request. RAM crece indefinidamente — ONNX no libera memoria al destruir sesiones. Reportado con consumo >137GB hasta agotar RAM del host.

**Why it happens:** El patron "stateless" lleva a instanciar todo en el endpoint. La API de rembg acepta `remove(image)` sin session (lazy-create interna), ocultando el problema.

**How to avoid:** Una sola `new_session()` en el lifespan. Pasar `session=app.state.rembg_session` en cada `remove()`. Verificar que `new_session()` no aparece en ningun modulo de procesamiento por request.

**Warning signs:** `docker stats` muestra RAM creciendo lentamente. Primer request tarda igual que los subsiguientes.

### Pitfall 2: CPU-bound sin asyncio.to_thread — event loop bloqueado

**What goes wrong:** Llamar `rembg.remove()` o `Pillow.resize()` directamente en `async def endpoint`. `/health` no responde durante los 3-8s de inferencia.

**How to avoid:** TODO el pipeline en `asyncio.to_thread(process_image_sync, ...)`. Verificar: hacer `GET /health` mientras hay un request de proceso activo — debe responder en <100ms.

### Pitfall 3: ONNX intra_op_num_threads no configurado — CPU throttling

**What goes wrong:** ONNX Runtime lee cores del HOST (no del container). En un host de 8 cores con container limitado a 1.5 CPU, intenta crear 8+ threads. Resultado: CPU throttling agresivo del container por cgroups.

**How to avoid:** `OMP_NUM_THREADS=2` en el Dockerfile. Verificar con `docker inspect` que el env var esta presente.

### Pitfall 4: Pillow sin context managers — memory leak silencioso

**What goes wrong:** `Image.open()` sin `with` mantiene buffers C vivos. En servicio de larga duracion la RAM crece 100-200MB por cada 300K imagenes.

**How to avoid:** Siempre `with Image.open(...) as img:`. Para imagenes creadas con `Image.new()`, llamar `.close()` explicitamente cuando ya no se necesitan.

### Pitfall 5: OOMKill en pico de RAM durante inferencia

**What goes wrong:** Con mem_limit: 2g, un pico de inferencia de birefnet-lite (modelo 300MB + buffers ONNX ~400-500MB + imagen + overhead) puede superar el limite momentaneamente → exit code 137 sin logs.

**How to avoid:** `mem_limit: 2g` con margen real. `MALLOC_TRIM_THRESHOLD_=65536` para que glibc devuelva memoria mas agresivamente. `max_concurrent=1` es critico. Testear con `docker stats` durante 10 requests de imagenes de 8MP.

### Pitfall 6: Modelo no pre-descargado — cold start fatal

**What goes wrong:** Sin el modelo embebido en la imagen Docker, el primer `new_session()` descarga desde Hugging Face (1-3 min). En el VPS puede fallar por conectividad o timeout.

**How to avoid:** `RUN python -c "from rembg import new_session; new_session('birefnet-lite')"` en Dockerfile. Verificar: `docker build` → `docker run --network none` → servicio arranca y procesa.

### Pitfall 7: Modo de color no normalizado antes de rembg

**What goes wrong:** Imagenes CMYK, P (GIF), L, LA crashean con errores crípticos en Pillow post-rembg. CMYK es comun en imagenes de proveedores de impresion.

**How to avoid:** Normalizar modo inmediatamente despues de exif_transpose. CMYK → RGB silenciosamente (D-07). Otros modos no RGB/RGBA → convertir antes de enviar a rembg.

### Pitfall 8: asyncio.Semaphore sin timeout — deadlock

**What goes wrong:** Si el pipeline falla sin liberar el semaphore, todos los requests subsiguientes quedan bloqueados indefinidamente.

**How to avoid:** `asyncio.wait_for(semaphore.acquire(), timeout=config.queue.timeout_seconds)`. El `finally` en `submit()` debe siempre llamar `semaphore.release()`.

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| `u2net` / `u2netp` como modelos rembg | `birefnet-lite` / `birefnet-general` | 2023-2024 | birefnet-lite ofrece calidad significativamente superior con ~300MB RAM |
| FastAPI lifespan via `@app.on_event("startup")` | `@asynccontextmanager async def lifespan(app)` | FastAPI 0.93+ | `on_event` deprecado; lifespan es el patron actual |
| `PIL.Image.LANCZOS` (constante vieja) | `PIL.Image.Resampling.LANCZOS` | Pillow 9.1+ | La constante antigua genera DeprecationWarning en Pillow 10+ |
| `pytest-asyncio` modos de configuracion manual | `asyncio_mode = "auto"` en pyproject.toml | pytest-asyncio 0.21+ | Evita decorar cada test con `@pytest.mark.asyncio` |

**Deprecated/outdated:**
- `@app.on_event("startup")` / `@app.on_event("shutdown")`: Deprecado en FastAPI 0.93. Usar `lifespan` context manager.
- `Image.ANTIALIAS`: Removido en Pillow 10.0.0. Reemplazado por `Image.Resampling.LANCZOS`.
- `rembg` sin `[cpu]` extra: En entorno sin GPU instala onnxruntime que puede intentar resolver CUDA deps. Usar siempre `rembg[cpu]`.

---

## Project Constraints (from CLAUDE.md)

Directivas obligatorias del proyecto que el planner debe verificar:

| Constraint | Directiva |
|------------|-----------|
| RAM | Container <= 2GB. Obliga birefnet-lite y max_concurrent=1 |
| CPU | 2 cores disponibles, container usa 1.5. Sin GPU |
| Dependencias externas | Ninguna — todo embebido en imagen Docker |
| Modelo rembg | Sesion global inicializada una vez en startup, NUNCA por request |
| Event loop | asyncio.to_thread() OBLIGATORIO para operaciones CPU-bound (rembg, Pillow) |
| Formato de salida | WebP unicamente, RGB (sin alpha en output final) |
| Orden del pipeline | Fijo e inamovible: decode→rembg→autocrop→scale→composite→enhance→encode |
| yaml.load | NUNCA sin Loader — usar yaml.safe_load() siempre |
| Imagen base Docker | python:3.11-slim (NO alpine — musl libc rompe wheels de onnxruntime) |
| onnxruntime-gpu | JAMAS — el VPS no tiene GPU |
| FastAPI BackgroundTasks | JAMAS para rembg — BackgroundTasks corre en el event loop |
| Celery/Redis | Out of scope — volumen < 100 imgs/dia no justifica infraestructura |

---

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| Docker Engine | DOCK-01..05 | SI | 29.2.1 | — |
| Docker Compose | DOCK-02 | SI | v5.1.0 | — |
| Python 3.11 | Runtime (Dockerfile) | SI (3.12 en host) | 3.12.3 host | Solo se necesita en container; python:3.11-slim en Dockerfile |
| FastAPI | API-01..05 | SI (host) | 0.135.1 | — (prod usa container) |
| uvicorn | Servidor | SI (host) | 0.42.0 | — |
| pytest | Testing | SI (host) | 9.0.2 | — |
| httpx | Testing | SI (host) | 0.28.1 | — |
| rembg | Pipeline | NO (host) | — | Solo necesario en container; se instala via requirements.txt |
| Pillow | Pipeline | SI (host) | 10.2.0 (prod: 12.1.1) | Version en host difiere — usar container para prod |
| PyYAML | Config | SI (host) | 6.0.1 (prod: 6.0.3) | Version en host difiere — usar container para prod |
| watchdog | Config | NO (host) | — | Solo necesario en container; se instala via requirements.txt |
| pytest-asyncio | Testing | NO (host) | — | Instalar con pip antes de correr tests |

**Missing dependencies con fallback:**
- `rembg`, `watchdog`: No instalados en el host. El desarrollo y la ejecucion ocurren dentro del container Docker, por lo que las dependencias faltantes en el host no bloquean. Para correr tests en el host, instalar con `pip install rembg[cpu] watchdog pytest-asyncio`.
- `Pillow 10.2.0 vs 12.1.1`: La version en el host es inferior. El codigo debe usar `Image.Resampling.LANCZOS` (disponible desde Pillow 9.1) para compatibilidad con ambas versiones.

**Missing dependencies sin fallback:**
- Ninguna — Docker Engine disponible garantiza que el container funciona independientemente del entorno del host.

---

## Validation Architecture

### Test Framework

| Property | Value |
|----------|-------|
| Framework | pytest 9.0.2 + pytest-asyncio 1.3.0 |
| Config file | `pyproject.toml` (seccion `[tool.pytest.ini_options]`) |
| Quick run command | `pytest tests/ -x -q` |
| Full suite command | `pytest tests/ --cov=app --cov-report=term-missing` |

### pyproject.toml minimo

```toml
[tool.pytest.ini_options]
asyncio_mode = "auto"
testpaths = ["tests"]
```

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| PIPE-01 | Decode JPG/PNG/WebP/BMP/TIFF valido | unit | `pytest tests/test_processor.py::test_decode_formats -x` | No — Wave 0 |
| PIPE-01 | Decode imagen corrupta → InvalidImageError | unit | `pytest tests/test_processor.py::test_decode_corrupt -x` | No — Wave 0 |
| PIPE-02 | EXIF transpose aplicado en JPEG rotado | unit | `pytest tests/test_processor.py::test_exif_transpose -x` | No — Wave 0 |
| PIPE-03 | rembg produce imagen RGBA con fondo transparente | unit | `pytest tests/test_processor.py::test_rembg_removes_bg -x` | No — Wave 0 |
| PIPE-04 | Autocrop recorta al bounding box del producto | unit | `pytest tests/test_processor.py::test_autocrop -x` | No — Wave 0 |
| PIPE-05 | Scale mantiene aspect ratio (fit-inside) | unit | `pytest tests/test_processor.py::test_scale_aspect_ratio -x` | No — Wave 0 |
| PIPE-06 | Composite produce canvas 800x800 fondo blanco centrado | unit | `pytest tests/test_processor.py::test_composite_centering -x` | No — Wave 0 |
| PIPE-07 | Enhancement aplica brightness/contrast si != 1.0 | unit | `pytest tests/test_processor.py::test_enhancement -x` | No — Wave 0 |
| PIPE-08 | Output es WebP valido con calidad configurable | unit | `pytest tests/test_processor.py::test_encode_webp -x` | No — Wave 0 |
| PIPE-09 | Output mode es RGB (no RGBA) | unit | `pytest tests/test_processor.py::test_output_mode_rgb -x` | No — Wave 0 |
| PIPE-10 | Pipeline completo: input JPEG → output WebP 800x800 | integration | `pytest tests/test_processor.py::test_full_pipeline -x` | No — Wave 0 |
| D-05 | Imagen > 25MP rechazada con ValidationError | unit | `pytest tests/test_processor.py::test_megapixel_limit -x` | No — Wave 0 |
| D-06 | PNG con >10% transparencia saltea rembg | unit | `pytest tests/test_processor.py::test_skip_rembg_transparent -x` | No — Wave 0 |
| D-07 | Imagen CMYK convertida silenciosamente a RGB | unit | `pytest tests/test_processor.py::test_cmyk_conversion -x` | No — Wave 0 |
| API-01 | POST /process acepta multipart con image y article_id | integration | `pytest tests/test_api.py::test_process_success -x` | No — Wave 0 |
| API-02 | POST /process retorna WebP con todos los X-headers | integration | `pytest tests/test_api.py::test_process_headers -x` | No — Wave 0 |
| API-03 | POST /process con override JSON aplica deep merge | integration | `pytest tests/test_api.py::test_process_override -x` | No — Wave 0 |
| API-04 | POST /process retorna 400 para imagen corrupta | integration | `pytest tests/test_api.py::test_process_400_corrupt -x` | No — Wave 0 |
| API-04 | POST /process retorna 422 si falta article_id | integration | `pytest tests/test_api.py::test_process_422_missing_field -x` | No — Wave 0 |
| API-04 | POST /process retorna 503 si cola llena | integration | `pytest tests/test_api.py::test_process_503_queue_full -x` | No — Wave 0 |
| API-05 | GET /health retorna status, cola, modelo, uptime | integration | `pytest tests/test_api.py::test_health -x` | No — Wave 0 |
| QUEUE-01 | Semaphore respeta max_concurrent=1 | unit | `pytest tests/test_queue.py::test_max_concurrent -x` | No — Wave 0 |
| QUEUE-02 | 503 inmediato si queued_jobs >= max_queue_size | unit | `pytest tests/test_queue.py::test_503_queue_full -x` | No — Wave 0 |
| QUEUE-03 | 504 si job espera mas de timeout_seconds | unit | `pytest tests/test_queue.py::test_504_timeout -x` | No — Wave 0 |
| QUEUE-04 | CPU-bound en asyncio.to_thread (health disponible durante proceso) | integration | `pytest tests/test_api.py::test_health_during_processing -x` | No — Wave 0 |
| CONF-01 | Config se carga de settings.yaml al startup | unit | `pytest tests/test_config.py::test_config_loads_yaml -x` | No — Wave 0 |
| CONF-06 | Config snapshot inmutable durante job | unit | `pytest tests/test_config.py::test_config_snapshot_immutable -x` | No — Wave 0 |
| DOCK-01 | Dockerfile construye sin errores | smoke | `docker build -t imgproc-test . && docker run --rm imgproc-test python -c "from app.main import app; print('ok')"` | No — Wave 0 |
| DOCK-05 | Container funciona sin red (modelo embebido) | smoke | `docker run --rm --network none imgproc-test curl -f http://localhost:8010/health` | No — Wave 0 |

### Sampling Rate

- **Por commit:** `pytest tests/test_processor.py tests/test_queue.py -x -q`
- **Por wave merge:** `pytest tests/ --cov=app --cov-report=term-missing`
- **Phase gate:** Full suite green + smoke Docker tests antes de `/gsd:verify-work`

### Wave 0 Gaps

- [ ] `tests/conftest.py` — fixtures compartidos (imagen JPEG de prueba, imagen PNG transparente, imagen CMYK, app async client)
- [ ] `tests/test_processor.py` — tests unitarios del pipeline
- [ ] `tests/test_queue.py` — tests unitarios del JobQueue
- [ ] `tests/test_api.py` — tests de integracion de endpoints
- [ ] `tests/test_config.py` — tests del ConfigManager
- [ ] Framework install: `pip install pytest-asyncio==1.3.0 watchdog==6.0.0` si se corren tests en el host

---

## Open Questions

1. **Limite de megapixels para D-05: 25MP vs Image.MAX_IMAGE_PIXELS default de Pillow (178MP)**
   - Que se sabe: D-05 define 25MP como limite. Pillow tiene su propio limite de DecompressionBomb (178MP por defecto). Ambos pueden coexistir.
   - Recomendacion: Verificar que 25MP primero con `width * height > 25_000_000` y retornar 400 (no DecompressionBombWarning que Pillow convierte en Warning y no Exception). No deshabilitar `Image.MAX_IMAGE_PIXELS` — agregar el chequeo propio antes.

2. **Estructura de override deep merge para API-03**
   - Que se sabe: La request acepta un JSON string en el campo `override`. El PRD dice "deep merge con config actual".
   - Que no esta claro: Si el override debe fallar si incluye campos no reconocidos (strict) o ignorarlos (lenient). El PRD no especifica.
   - Recomendacion: Lenient — ignorar campos no reconocidos. Registrar un warning en el log con los campos ignorados.

3. **Comportamiento de autocrop cuando rembg produce mascara vacia**
   - Que se sabe: El PRD define la guardia "si bbox cubre < 5% del area total → omitir crop". Pero no define si esto es un error o un warning.
   - Recomendacion: Warning silencioso en el log, continuar con la imagen sin crop. El producto resultante puede no ser ideal pero no debe fallar el job.

---

## Sources

### Primary (HIGH confidence)

- `PRD-image-standardizer-v2.md` — Especificacion completa del pipeline (secciones 6, 7, 8, 11)
- `CLAUDE.md` del proyecto — Stack tecnologico con versiones pinned y anti-patterns
- `.planning/research/ARCHITECTURE.md` — Patrones arquitecturales verificados
- `.planning/research/PITFALLS.md` — Pitfalls con fuentes de issues GitHub de rembg/ONNX/Pillow
- `.planning/research/STACK.md` — Versiones verificadas contra PyPI el 2026-03-30
- `FastAPI Lifespan Events` — https://fastapi.tiangolo.com/advanced/events/
- `FastAPI Concurrency and async/await` — https://fastapi.tiangolo.com/async/
- `Pillow File Handling` — https://pillow.readthedocs.io/en/stable/reference/open_files.html
- `ONNX Runtime Thread Management` — https://onnxruntime.ai/docs/performance/tune-performance/threading.html

### Secondary (MEDIUM confidence)

- `docker stats` en el VPS — confirmacion de disponibilidad de Docker 29.2.1 y Compose v5.1.0
- PyPI verificacion de versiones (2026-03-30) — FastAPI 0.135.2, uvicorn 0.42.0, Pillow 12.1.1, rembg 2.0.74

### Tertiary (LOW confidence)

- Tiempo estimado de inferencia birefnet-lite en CPU del VPS (6-12s): no medido en este hardware especifico. Validar con `docker stats` en las primeras pruebas.
- Pico de RAM durante inferencia (~1.2-1.8GB): estimado del PITFALLS.md. Validar con `docker stats` durante stress test.

---

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — versiones verificadas contra PyPI y CLAUDE.md
- Architecture: HIGH — patterns del PRD y ARCHITECTURE.md pre-investigados
- Pipeline steps: HIGH — pseudocodigo ejecutable del PRD seccion 6 con Pillow API verificada
- Pitfalls: HIGH — todos documentados con issues de GitHub de rembg/ONNX/Pillow como fuente
- Docker: HIGH — pattern estandar python:3.11-slim con modelo pre-descargado
- Queue behavior: HIGH — asyncio.Semaphore con wait_for() pattern bien documentado

**Research date:** 2026-03-30
**Valid until:** 2026-04-30 (stack estable; solo invalidar si rembg o FastAPI publican breaking changes)
