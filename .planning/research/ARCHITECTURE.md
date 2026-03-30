# Architecture Research

**Domain:** Image standardization microservice (background removal + normalization pipeline)
**Researched:** 2026-03-30
**Confidence:** HIGH

## Standard Architecture

### System Overview

```
┌─────────────────────────────────────────────────────────────────────┐
│                          Entry Layer                                 │
│  ┌──────────────────┐  ┌──────────────────┐  ┌──────────────────┐  │
│  │   HTTP API       │  │    Web UI        │  │      CLI         │  │
│  │  (FastAPI)       │  │  (Jinja2 +       │  │   (Typer)        │  │
│  │  POST /process   │  │   vanilla JS)    │  │  process/batch/  │  │
│  │  GET  /health    │  │  GET /ui         │  │  serve/config    │  │
│  │  GET  /status    │  │  POST /config    │  └────────┬─────────┘  │
│  │  GET/POST /config│  └────────┬─────────┘           │            │
│  └────────┬─────────┘           │                     │            │
├───────────┼─────────────────────┼─────────────────────┼────────────┤
│                      Concurrency Layer                               │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │           Queue Manager (asyncio.Queue + Semaphore)          │   │
│  │           max_concurrent=1, back-pressure signaling          │   │
│  └─────────────────────────────┬───────────────────────────────┘   │
├─────────────────────────────────┼──────────────────────────────────┤
│                      Processing Layer                                │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │                   Image Processor                            │   │
│  │  decode → rembg → autocrop → scale → composite →            │   │
│  │  enhance → encode WebP                                       │   │
│  │  (runs in asyncio.to_thread — never blocks event loop)       │   │
│  └─────────────────────────────┬───────────────────────────────┘   │
├─────────────────────────────────┼──────────────────────────────────┤
│                      Infrastructure Layer                            │
│  ┌──────────────────┐  ┌───────────────────┐                       │
│  │  Config Manager  │  │   rembg Session   │                       │
│  │  (YAML + watchdog│  │   (ONNX, global   │                       │
│  │   hot-reload)    │  │   singleton,      │                       │
│  │   thread-safe    │  │   loaded once at  │                       │
│  │   RWLock         │  │   startup)        │                       │
│  └──────────────────┘  └───────────────────┘                       │
└─────────────────────────────────────────────────────────────────────┘
```

### Component Responsibilities

| Component | Responsibility | Implementación recomendada |
|-----------|----------------|---------------------------|
| **HTTP API** | Recibir imágenes, devolver resultados, exponer health/status/config | FastAPI router, Pydantic models para validación |
| **Web UI** | Interfaz visual para editar y guardar configuración | FastAPI `TemplateResponse` + Jinja2 + un solo archivo HTML con vanilla JS |
| **CLI** | Procesamiento standalone sin levantar servidor | Typer app separada, reutiliza ImageProcessor directamente |
| **Queue Manager** | Serializar requests al procesador, backpressure, status tracking | `asyncio.Queue` + `asyncio.Semaphore(1)`, estado en memoria |
| **Image Processor** | Pipeline de transformación de imagen, puro y determinista | Clase stateless con métodos para cada paso del pipeline |
| **rembg Session** | Instancia ONNX reutilizable para background removal | Singleton cargado en lifespan, inyectado vía `app.state` |
| **Config Manager** | Leer/escribir YAML, notificar cambios a componentes, thread-safe | Dataclass + watchdog Observer + RWLock |

## Recommended Project Structure

```
src/
├── api/
│   ├── __init__.py
│   ├── routes/
│   │   ├── process.py      # POST /process, GET /status
│   │   ├── health.py       # GET /health
│   │   └── config.py       # GET/POST /config
│   └── schemas.py          # Pydantic request/response models
├── processor/
│   ├── __init__.py
│   ├── pipeline.py         # Clase ImageProcessor con el pipeline completo
│   ├── steps/
│   │   ├── decode.py       # Decode multipart → PIL.Image
│   │   ├── remove_bg.py    # rembg wrapper
│   │   ├── autocrop.py     # Detectar bbox del sujeto y recortar
│   │   ├── scale.py        # Scale to target canvas con padding
│   │   ├── composite.py    # Componer sobre fondo blanco
│   │   ├── enhance.py      # Ajustes opcionales (sharpness, contrast)
│   │   └── encode.py       # PIL → bytes WebP
│   └── session.py          # rembg new_session, inicialización única
├── queue/
│   ├── __init__.py
│   └── manager.py          # AsyncQueue con Semaphore y tracking de jobs
├── config/
│   ├── __init__.py
│   ├── schema.py           # Dataclass / Pydantic model del config YAML
│   ├── loader.py           # Leer/escribir config.yaml
│   └── watcher.py          # watchdog Observer para hot-reload
├── ui/
│   ├── templates/
│   │   └── config.html     # Única plantilla Jinja2 (UI de config)
│   └── static/             # CSS/JS inline o mínimos assets
├── cli/
│   └── main.py             # Typer app: process, batch, serve, config
├── main.py                 # FastAPI app, lifespan, router registration
└── settings.py             # Constantes de entorno (puerto, paths, etc.)
```

### Structure Rationale

- **api/:** Separar routing de lógica de negocio — los routes son delgados, delegan al Queue Manager o Config Manager.
- **processor/steps/:** Cada paso del pipeline es una función pura independiente. Facilita tests unitarios, permite reordenar o desactivar pasos via config.
- **queue/:** Aislado del API — el manager no sabe de HTTP, solo de jobs. Permite testear la cola sin levantar FastAPI.
- **config/:** Schema + Loader + Watcher como unidad cohesiva. El Watcher notifica al Loader; el Loader notifica a quien esté suscrito (Processor usa los valores en runtime).
- **cli/:** Typer app que importa `processor.pipeline` directamente, sin pasar por HTTP. Útil para batch offline y testing manual.
- **main.py (lifespan):** El único lugar donde se toca `app.state` — inicializa rembg Session, Queue Manager y Config Watcher.

## Architectural Patterns

### Pattern 1: Lifespan Singleton para recursos costosos

**What:** Inicializar rembg Session y Queue Manager una sola vez en el lifespan de FastAPI, almacenarlos en `app.state`, e inyectarlos via dependency injection.

**When to use:** Siempre que haya recursos que tarden segundos en inicializar (modelos ML, pools de conexiones). En este proyecto: rembg carga birefnet-lite (~300MB) en 5-15s — no puede ocurrir por request.

**Trade-offs:** `app.state` no tiene type hints nativos (requiere cast o TypedDict); a cambio, evita globals mutables y permite cleanup limpio en shutdown.

**Example:**
```python
# main.py
from contextlib import asynccontextmanager
from fastapi import FastAPI
from processor.session import create_session
from queue.manager import QueueManager

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: carga del modelo (bloqueante, OK porque es startup)
    app.state.rembg_session = create_session("birefnet-lite")
    app.state.queue = QueueManager(max_concurrent=1)
    app.state.config = ConfigManager("config.yaml")
    app.state.config.start_watcher()
    yield
    # Shutdown
    app.state.config.stop_watcher()

app = FastAPI(lifespan=lifespan)
```

### Pattern 2: asyncio.to_thread para CPU-bound en async endpoint

**What:** Envolver todo el pipeline CPU-bound (rembg + Pillow) en `asyncio.to_thread()` para no bloquear el event loop de FastAPI.

**When to use:** Cualquier operación que tarde >10ms y no sea I/O puro. rembg puede tardar 2-8s por imagen en CPU — bloquearía el event loop si se llama directamente desde `async def`.

**Trade-offs:** Python GIL limita el paralelismo real de CPU; el beneficio es que el event loop puede seguir respondiendo a `/health` mientras procesa. Con `max_concurrent=1` esto es suficiente para < 100 img/día.

**Example:**
```python
# queue/manager.py
import asyncio
from processor.pipeline import ImageProcessor

class QueueManager:
    def __init__(self, max_concurrent: int = 1):
        self._semaphore = asyncio.Semaphore(max_concurrent)
        self._queue: asyncio.Queue = asyncio.Queue()

    async def submit(self, job: ProcessJob) -> ProcessResult:
        async with self._semaphore:
            return await asyncio.to_thread(
                ImageProcessor.run, job.image_bytes, job.config
            )
```

### Pattern 3: Config Manager con watchdog + callbacks

**What:** Un observer de watchdog corre en un thread separado, detecta cambios en `config.yaml` y llama callbacks registrados para que los consumidores actualicen su estado.

**When to use:** Cuando se necesita hot-reload de config sin restart del container. El callback pattern desacopla el watcher del consumidor.

**Trade-offs:** Threading + async no mezclan limpiamente — el callback del watcher ocurre en un thread, no en el event loop. Si el callback necesita ser async, usar `asyncio.run_coroutine_threadsafe()`.

**Example:**
```python
# config/watcher.py
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
import threading

class ConfigWatcher(FileSystemEventHandler):
    def __init__(self, config_path: str, on_change_callback):
        self._path = config_path
        self._callback = on_change_callback
        self._lock = threading.RLock()

    def on_modified(self, event):
        if event.src_path.endswith(self._path):
            with self._lock:
                self._callback()
```

## Data Flow

### Request Flow (HTTP API)

```
Cliente HTTP
    │
    ▼  POST /process (multipart: imagen)
FastAPI Route (process.py)
    │  Valida Content-Type, extrae bytes
    ▼
QueueManager.submit(job)
    │  asyncio.Semaphore — bloquea si ya hay 1 job activo
    ▼
asyncio.to_thread(ImageProcessor.run, bytes, config)
    │
    ▼  [Thread separado — no bloquea event loop]
ImageProcessor.run(bytes, config)
    │
    ├─→ decode(bytes) → PIL.Image (RGBA)
    ├─→ remove_bg(image, rembg_session) → PIL.Image (RGBA, fondo transparente)
    ├─→ autocrop(image) → PIL.Image (recortado al sujeto)
    ├─→ scale(image, target=800x800, padding=0.05) → PIL.Image
    ├─→ composite(image, background="white") → PIL.Image (RGB)
    ├─→ enhance(image, config.enhance) → PIL.Image
    └─→ encode(image, format="webp") → bytes
    │
    ▼  [Regresa al event loop]
FastAPI Response
    │  200 OK, Content-Type: image/webp, bytes del WebP
    ▼
Cliente HTTP
```

### Config Hot-Reload Flow

```
Usuario edita config.yaml (o POST /config desde la Web UI)
    │
    ▼
watchdog Observer (thread)
    │  FileModifiedEvent
    ▼
ConfigWatcher.on_modified()
    │  Relee YAML, valida schema
    ▼
ConfigManager.reload()
    │  Actualiza config en memoria (con RLock)
    ▼
Callbacks notificados (si los hay)
    │
    ▼
Próximo request del ImageProcessor lee nueva config
    (config se pasa por parámetro en cada job — no hay estado mutable en el processor)
```

### CLI Batch Flow

```
typer batch --input ./fotos/ --output ./webp/
    │
    ▼
CLI carga ConfigManager (sin watchdog)
    │
    ▼
CLI carga rembg Session (igual que el servidor)
    │
    ▼
Para cada archivo en input/:
    │
    ▼
ImageProcessor.run(bytes, config) — llamada directa, sin queue, sin async
    │
    ▼
Escribe .webp en output/
```

### Key Data Flows

1. **Image bytes como unidad de transferencia:** El procesador recibe `bytes` crudos y devuelve `bytes` WebP. No hay paths en disco durante el procesamiento (todo en memoria). Esto simplifica tests y evita gestión de archivos temporales.

2. **Config como parámetro inmutable por job:** El `ImageProcessor` no lee config global — recibe un snapshot de `ConfigSnapshot` en cada invocación. Esto garantiza que un cambio de config no afecta jobs en vuelo.

3. **rembg Session como estado separado del config:** La sesión es el único estado global del procesador. No se recrea por request ni por cambio de config. Solo cambia si el modelo cambia (requiere restart).

## Scaling Considerations

| Escala | Ajuste arquitectural |
|--------|----------------------|
| < 100 img/día (target actual) | asyncio.Semaphore(1) + todo en memoria — sin infraestructura externa |
| 100-1000 img/día | Aumentar max_concurrent a 2-3 (si RAM lo permite), mantener misma arquitectura |
| 1000+ img/día | Reemplazar cola in-memory con Redis + Celery/ARQ; escalar a múltiples workers |
| Multi-tenant / multi-modelo | Separar el session pool por modelo; agregar caché de sesiones |

### Scaling Priorities

1. **Primer cuello de botella:** CPU del procesamiento rembg (~3-6s/imagen en birefnet-lite, CPU). Con `max_concurrent=1` el throughput máximo es ~10-20 imágenes/hora. Para el volumen target (< 100/día) es suficiente.

2. **Segundo cuello de botella:** RAM. birefnet-lite usa ~600-800MB en runtime. Con 2GB de límite hay margen, pero subir a birefnet-general (~1.2GB) puede ser problemático. Monitorear con `/health` metrics.

## Anti-Patterns

### Anti-Pattern 1: Crear nueva rembg Session por request

**What people do:** Llamar `new_session("birefnet-lite")` dentro del endpoint o del processor para cada imagen.

**Why it's wrong:** La sesión ONNX tarda 5-15s en inicializar y usa ~600MB de RAM. Crear una por request colapsa el servicio en el primer request concurrente y agota la RAM en segundos.

**Do this instead:** Inicializar una sola vez en lifespan, almacenar en `app.state.rembg_session`, inyectar via dependency o pasar como parámetro al Processor.

### Anti-Pattern 2: Llamar operaciones CPU-bound directamente en async def

**What people do:**
```python
@app.post("/process")
async def process(file: UploadFile):
    result = remove(await file.read(), session=session)  # BLOQUEA EL EVENT LOOP
    return Response(result, media_type="image/webp")
```

**Why it's wrong:** rembg/Pillow son CPU-bound y pueden tardar segundos. Llamarlos directamente en `async def` bloquea el event loop, haciendo que `/health` y otras rutas no respondan durante el procesamiento.

**Do this instead:** `await asyncio.to_thread(process_image, bytes_data, session)`.

### Anti-Pattern 3: Watchdog callback que modifica estado async sin coordinación

**What people do:** El callback del watchdog intenta actualizar directamente un objeto que el event loop de asyncio está usando.

**Why it's wrong:** El watchdog Observer corre en un thread del sistema operativo, no en el event loop de asyncio. Modificar estado compartido sin locking causa race conditions.

**Do this instead:** Usar `threading.RLock` para proteger el estado del ConfigManager. El Processor lee una copia inmutable del config en cada job (ConfigSnapshot), eliminando la necesidad de sincronización fine-grained.

### Anti-Pattern 4: Pipeline con estado mutable en el Processor

**What people do:** Guardar el estado intermedio del pipeline (imagen decodificada, imagen sin fondo) como atributos de instancia del Processor.

**Why it's wrong:** Si el Processor es un singleton compartido (o si alguna vez se aumenta `max_concurrent`), hay race conditions entre jobs concurrentes.

**Do this instead:** El Processor es stateless — cada invocación de `run()` crea sus variables locales. El único estado externo que necesita son la `Session` (inmutable durante el job) y el `ConfigSnapshot`.

## Integration Points

### External Services

| Service | Integration Pattern | Notas |
|---------|---------------------|-------|
| n8n (futuro) | HTTP POST al endpoint `/process` | n8n tiene nodo HTTP Request nativo; el servicio no necesita cambios |
| Traefik (futuro) | Label en `docker-compose.yml` | Solo routing — el servicio no sabe de Traefik |
| Storage S3/MinIO (futuro) | Agregar paso `upload` al pipeline o endpoint nuevo | Out of scope v1 — output es response body |

### Internal Boundaries

| Boundary | Comunicación | Consideraciones |
|----------|-------------|-----------------|
| API Route ↔ Queue Manager | Llamada directa async (`await queue.submit(job)`) | El route obtiene el QueueManager de `request.app.state` |
| Queue Manager ↔ Image Processor | `asyncio.to_thread(processor.run, ...)` | Processor no conoce a la Queue — dependencia unidireccional |
| Image Processor ↔ rembg Session | Parámetro en la llamada a `remove_bg(image, session)` | Session es inmutable durante el procesamiento |
| Image Processor ↔ Config | Recibe `ConfigSnapshot` por parámetro | Snapshot tomado en el momento de `queue.submit()` — no cambia mid-job |
| Config Manager ↔ watchdog Observer | Callback en thread — protegido con RLock | Config Manager expone `get_snapshot()` thread-safe para el Queue Manager |
| Web UI ↔ Config Manager | Via HTTP API (`GET/POST /config`) — el route llama a ConfigManager | La UI no escribe YAML directamente — pasa por la API |
| CLI ↔ Image Processor | Import directo Python — sin HTTP, sin Queue | CLI gestiona su propia Session y Config (sin watchdog) |

## Suggested Build Order

La arquitectura tiene dependencias claras que dictan el orden de construcción:

1. **Config Manager** (base de todo — define los parámetros que el Processor usa)
2. **Image Processor + pipeline steps** (lógica de negocio pura — testeable sin API)
3. **rembg Session singleton** (integra con el Processor)
4. **Queue Manager** (wrappea el Processor con control de concurrencia)
5. **FastAPI app + lifespan + routes** (ensambla todo, expone HTTP)
6. **Web UI** (depende de los endpoints de config ya funcionando)
7. **CLI** (reutiliza Processor y Config directamente)
8. **Docker + docker-compose** (empaqueta todo con el modelo pre-descargado)
9. **Tests** (unitarios por capa, integración end-to-end)

## Sources

- [FastAPI Lifespan Events — documentación oficial](https://fastapi.tiangolo.com/advanced/events/)
- [FastAPI Concurrency and async/await](https://fastapi.tiangolo.com/async/)
- [rembg Session and Model Management — DeepWiki](https://deepwiki.com/danielgatis/rembg/4.2-session-and-model-management)
- [rembg PyPI — batch processing with session reuse](https://pypi.org/project/rembg/)
- [Concurrency For Starlette Apps — Answer.AI](https://www.answer.ai/posts/2024-10-10-concurrency.html)
- [FastAPI Mistakes That Kill Performance — DEV Community](https://dev.to/igorbenav/fastapi-mistakes-that-kill-your-performance-2b8k)
- [How to Build a Config System with Hot Reload in Python — OneUptime](https://oneuptime.com/blog/post/2026-01-22-config-hot-reload-python/view)
- [Microservices in AI: Building Scalable Image Processing Pipelines — Medium](https://medium.com/@API4AI/microservices-in-ai-building-scalable-image-processing-pipelines-1e37a774b9a0)
- [FastAPI for Microservices: Design Patterns — talent500.com](https://talent500.com/blog/fastapi-microservices-python-api-design-patterns-2025/)
- [Singleton Pattern in FastAPI — Hrekov](https://hrekov.com/blog/singleton-fastapi-dependency)
- [FastAPI and Background Tasks — UnfoldAI](https://unfoldai.com/fastapi-background-tasks/)

---
*Architecture research for: Image Standardizer Microservice (Objetiva Comercios)*
*Researched: 2026-03-30*
