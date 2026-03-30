# Phase 2: Observabilidad + Config Operacional - Research

**Researched:** 2026-03-30
**Domain:** watchdog hot-reload, FastAPI config endpoints, rembg session swap, asyncio/threading bridge
**Confidence:** HIGH

---

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

**Model Swap (CONF-04)**
- **D-01:** Bloquear cola con 503 durante el swap de modelo rembg. Requests entrantes reciben rechazo inmediato mientras se recrea la sesion ONNX (~5-15s). Predecible para el operador.
- **D-02:** Swap graceful: crear nueva sesion ONNX primero, verificar que cargo OK, y recien entonces reemplazar la referencia en app.state. Si la carga falla, la sesion vieja sigue funcionando sin interrupcion.

**Validacion de Config (CONF-03)**
- **D-03:** Validacion estricta: si POST /config recibe cualquier campo invalido, rechazar TODO el request con 422 y detalle de que fallo. No aplicar parcialmente.
- **D-04:** Validar nombre de modelo rembg contra whitelist de modelos conocidos (birefnet-lite, isnet-general-use, u2net, etc.). Rechazar nombres desconocidos antes de intentar cargar.

**GET /status (API-06)**
- **D-05:** Respuesta enfocada en metricas operacionales: total_processed, total_errors, avg_processing_time_ms, historial de ultimos 50 jobs. Sin incluir config activa (ya esta en GET /config).
- **D-06:** Historial de jobs enriquecido: cada JobRecord incluye original_size y output_size ademas de article_id, status, processing_time_ms, model_used, timestamp, error.

**Watchdog + POST /config (CONF-05)**
- **D-07:** Flag de supresion temporal tras POST /config para evitar double reload. Cuando POST /config escribe el YAML, se activa un flag que indica al watchdog ignorar el proximo evento de modificacion del archivo.
- **D-08:** Log structured JSON en cada reload de config: `{"event": "config_reloaded", "source": "watchdog"|"api", ...}`. Consistente con el patron de logging D-03/D-04 de Fase 1.

### Claude's Discretion

Ninguna area delegada — todas las decisiones fueron tomadas explicitamente por el usuario.

### Deferred Ideas (OUT OF SCOPE)

None — discussion stayed within phase scope

</user_constraints>

---

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| CONF-02 | GET /config retorna la configuracion activa como JSON | ConfigManager.get_snapshot().model_dump() serializa correctamente via Pydantic v2 |
| CONF-03 | POST /config actualiza valores con deep merge y guarda el YAML | _deep_merge() ya existe en router_api.py; reutilizable. PyYAML yaml.dump() escribe el YAML. Validacion estricta D-03/D-04. |
| CONF-04 | Si rembg.model cambia via POST /config, la sesion se recrea despues de que termine el job activo | Flag de swap + asyncio.Semaphore para esperar que termine el job activo antes de swap |
| CONF-05 | El servicio detecta cambios en el YAML via watchdog y recarga sin restart | watchdog 6.0.0 Observer + FileSystemEventHandler + asyncio.run_coroutine_threadsafe() |
| API-06 | GET /status retorna estadisticas e historial de ultimos 50 jobs | QueueState ya tiene los contadores; JobRecord necesita extension con original_size/output_size (D-06) |
| QUEUE-05 | La cola mantiene estado en memoria: active_jobs, queued_jobs, total_processed, total_errors, job_history (50) | QueueState ya implementado en queue.py; job_history deque(maxlen=50) ya existe. Falta exponer via endpoint |

</phase_requirements>

---

## Summary

La Fase 2 agrega observabilidad operacional y config en caliente sobre la base de la Fase 1. El trabajo se divide en tres areas independientes: (1) endpoints GET/POST /config + GET /status en un nuevo router_config.py, (2) hot-reload via watchdog con bridge asyncio, y (3) model swap graceful al cambiar rembg.model.

El codigo de Fase 1 ya tiene la mayoria de las piezas: ConfigManager con reload(), QueueState con los contadores, JobRecord con los campos principales, y _deep_merge() en router_api.py. Lo que falta es: watchdog Observer en el lifespan, el nuevo router, extender JobRecord con original_size/output_size, y la logica de swap de sesion ONNX.

El riesgo tecnico mas alto es el bridge watchdog→asyncio: watchdog corre en un thread del Observer mientras el event loop de FastAPI corre en otro thread. La comunicacion debe ser thread-safe usando asyncio.run_coroutine_threadsafe() o loop.call_soon_threadsafe(). El flag de supresion (D-07) para evitar double-reload puede implementarse como threading.Event con auto-clear via asyncio.get_event_loop().

**Primary recommendation:** Implementar en este orden — (1) extender JobRecord, (2) crear router_config.py con los tres endpoints, (3) agregar watchdog al lifespan con bridge asyncio, (4) agregar logica de model swap. Este orden permite tests incrementales y reduce riesgo de regresion.

---

## Standard Stack

### Core (ya definido en CLAUDE.md — no cambia)
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| watchdog | 6.0.0 | Observer de filesystem + FileSystemEventHandler | Ya en requirements.txt. Observer thread-based, event-driven. |
| PyYAML | 6.0.3 | yaml.safe_dump() para escribir config actualizada | Ya en requirements.txt. Unica libreria YAML del proyecto. |
| FastAPI | 0.135.2 | Nuevos endpoints GET/POST /config, GET /status | Ya instalado. APIRouter en router_config.py. |
| Pydantic v2 | (via FastAPI) | Validacion estricta del body de POST /config | model_copy(update=...) para deep merge estructurado. |

### Primitivas de sincronizacion
| Primitiva | Modulo | Purpose |
|-----------|--------|---------|
| `asyncio.run_coroutine_threadsafe()` | asyncio | Llamar coroutines desde el thread de watchdog al event loop de FastAPI |
| `threading.Event` | threading | Flag de supresion de double-reload (D-07) |
| `asyncio.Lock` | asyncio | Proteger el swap de sesion ONNX durante POST /config (D-02) |

### rembg sessions registry (para whitelist D-04)
```python
# Verificado en rembg 2.0.74
from rembg.sessions import sessions_names
# sessions_names es una lista de strings con todos los nombres validos
# Ejemplo: ['u2net', 'u2netp', 'u2net_human_seg', 'u2net_cloth_seg',
#           'silueta', 'isnet-general-use', 'isnet-anime',
#           'birefnet-general', 'birefnet-general-lite', 'birefnet-portrait',
#           'birefnet-dis', 'birefnet-hrsod', 'birefnet-cod', 'birefnet-massive',
#           'sam', 'bria-rmbg', 'ben2-base',
#           'u2net_custom', 'dis_custom', 'ben_custom']
```

**Instalacion:** Sin cambios en requirements.txt — watchdog ya esta listado.

---

## Architecture Patterns

### Estructura de archivos para esta fase

```
app/
├── config.py          # Agregar: write_config(), lock asyncio, supresion flag
├── queue.py           # Modificar: JobRecord + original_size/output_size, avg_processing_time_ms
├── models.py          # Modificar: JobRecord ya en queue.py (no en models.py)
├── main.py            # Modificar: arrancar watchdog Observer en lifespan, app.state.model_swap_lock
├── router_api.py      # Sin cambios
└── router_config.py   # NUEVO: GET /config, POST /config, GET /status
```

### Pattern 1: Bridge watchdog → asyncio (CONF-05)

**Que:** El Observer de watchdog corre en su propio thread de sistema operativo. FastAPI corre en el event loop de asyncio. Para que un cambio en el YAML dispare una coroutine (config reload), se necesita un bridge thread-safe.

**Cuando usar:** Siempre que se necesite disparar codigo asyncio desde un thread externo (watchdog, threading.Timer, etc.).

**Implementacion recomendada:**

```python
# app/main.py — dentro del lifespan
import asyncio
import threading
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

class ConfigReloadHandler(FileSystemEventHandler):
    def __init__(self, loop: asyncio.AbstractEventLoop, app: FastAPI, suppress_flag: threading.Event):
        self._loop = loop
        self._app = app
        self._suppress_flag = suppress_flag

    def on_modified(self, event):
        if event.src_path.endswith("settings.yaml"):
            # D-07: si el flag de supresion esta activo, ignorar este evento
            if self._suppress_flag.is_set():
                self._suppress_flag.clear()
                return
            # Bridge thread -> asyncio
            asyncio.run_coroutine_threadsafe(
                _reload_config(self._app),
                self._loop,
            )

async def _reload_config(app: FastAPI) -> None:
    """Recarga config desde YAML. Se ejecuta en el event loop, no en el thread de watchdog."""
    app.state.config_manager.reload()
    import json, logging
    logging.getLogger(__name__).info(json.dumps({
        "level": "info",
        "event": "config_reloaded",
        "source": "watchdog",
        "model": app.state.config_manager.config.rembg.model,
    }))

# En lifespan:
loop = asyncio.get_event_loop()
suppress_flag = threading.Event()
app.state.watchdog_suppress_flag = suppress_flag

handler = ConfigReloadHandler(loop, app, suppress_flag)
observer = Observer()
observer.schedule(handler, path="config/", recursive=False)
observer.start()
app.state.watchdog_observer = observer

yield  # app corriendo

observer.stop()
observer.join()
```

**Nota:** `asyncio.run_coroutine_threadsafe()` retorna un concurrent.futures.Future — no es necesario await-arlo desde el thread de watchdog. La coroutine se ejecuta en el event loop de FastAPI.

### Pattern 2: POST /config con deep merge + validacion estricta (CONF-03, D-03, D-04)

```python
# app/router_config.py
from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
import json, yaml
from app.models import AppConfig
from app.router_api import _deep_merge   # reutilizar helper existente

router = APIRouter()

@router.post("/config")
async def update_config(request: Request, body: dict):
    """
    D-03: Validacion estricta — si algun campo es invalido, rechazar TODO el request con 422.
    D-04: Validar rembg.model contra whitelist antes de intentar cargar sesion.
    """
    config_manager = request.app.state.config_manager

    # Validar modelo contra whitelist si viene en el body
    if "rembg" in body and "model" in body["rembg"]:
        from rembg.sessions import sessions_names
        if body["rembg"]["model"] not in sessions_names:
            return JSONResponse(status_code=422, content={
                "error": "invalid_model",
                "detail": f"Model '{body['rembg']['model']}' not in whitelist. Valid: {sessions_names}",
            })

    # Deep merge contra config actual
    current_dict = config_manager.config.model_dump()
    _deep_merge(current_dict, body)

    # Validacion estricta via Pydantic — si falla, 422 con detalle
    try:
        new_config = AppConfig(**current_dict)
    except Exception as e:
        return JSONResponse(status_code=422, content={
            "error": "validation_error",
            "detail": str(e),
        })

    # Aplicar: escribir YAML + activar flag de supresion antes de escribir
    suppress_flag = request.app.state.watchdog_suppress_flag
    suppress_flag.set()   # D-07: watchdog ignorara el proximo evento sobre este archivo

    config_manager.update_config(new_config)  # escribe YAML + actualiza _config en memoria

    # Si el modelo cambio, disparar swap de sesion ONNX
    old_model = request.app.state.model_name
    new_model = new_config.rembg.model
    if old_model != new_model:
        # swap graceful async — ver Pattern 3
        asyncio.create_task(_swap_rembg_session(request.app, new_model))

    import json as _json, logging
    logging.getLogger(__name__).info(_json.dumps({
        "level": "info",
        "event": "config_reloaded",
        "source": "api",
        "model": new_model,
    }))

    return config_manager.config.model_dump()
```

### Pattern 3: Model swap graceful (CONF-04, D-01, D-02)

**Que:** Cambiar el modelo rembg requiere liberar el modelo ONNX viejo y cargar el nuevo (~5-15s). Durante el swap, la cola debe rechazar requests nuevos con 503 (D-01). Si la carga falla, la sesion vieja sigue activa (D-02).

**Flag de swap:** `app.state.model_swapping: bool` — seteado a True durante el swap. El endpoint POST /process verifica este flag antes de encolar.

```python
# app/main.py
async def _swap_rembg_session(app: FastAPI, new_model: str) -> None:
    """
    Swap graceful de sesion rembg. Bloquea cola durante la operacion.
    D-01: 503 durante swap (app.state.model_swapping = True)
    D-02: Si new_session falla, sesion vieja sigue activa
    """
    from rembg import new_session
    import logging, json

    app.state.model_swapping = True
    logger = logging.getLogger(__name__)

    try:
        # Esperar que termine el job activo (si hay uno)
        # asyncio.Semaphore ya esta en job_queue — esperar acquire + release inmediato
        queue = app.state.job_queue
        await asyncio.wait_for(queue._semaphore.acquire(), timeout=300)
        queue._semaphore.release()

        # Cargar nueva sesion en thread (CPU-bound)
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
        logger.error(json.dumps({
            "level": "error",
            "event": "model_swap_failed",
            "new_model": new_model,
            "error": str(e),
        }))
        # D-02: no modificar app.state.rembg_session — sesion vieja sigue activa
    finally:
        app.state.model_swapping = False
```

**POST /process debe verificar model_swapping:**
```python
# Al inicio del endpoint process_endpoint:
if getattr(request.app.state, "model_swapping", False):
    return JSONResponse(status_code=503, content=ErrorResponse(
        error="model_swapping",
        detail="Model swap in progress, retry in a few seconds",
        article_id=article_id,
    ).model_dump())
```

### Pattern 4: ConfigManager.update_config() — escritura de YAML

**Que:** POST /config necesita (a) actualizar `_config` en memoria, y (b) escribir el YAML en disco para persistencia.

```python
# Agregar a app/config.py
def update_config(self, new_config: AppConfig) -> None:
    """Actualiza config en memoria y persiste en YAML. Thread-safe via GIL."""
    self._config = new_config
    with open(self._config_path, "w") as f:
        yaml.dump(new_config.model_dump(), f, default_flow_style=False, allow_unicode=True)
```

**Nota:** `yaml.dump()` con `default_flow_style=False` produce YAML legible en bloque (no inline). Sin `yaml.safe_dump()` para dicts — los dicts de model_dump() no tienen objetos peligrosos.

### Pattern 5: GET /status con avg_processing_time_ms calculado

**Que:** El historial de jobs esta en `queue.state.job_history` (deque maxlen=50). avg_processing_time_ms se calcula en el momento del request, no se acumula.

```python
@router.get("/status")
async def status_endpoint(request: Request):
    queue = request.app.state.job_queue
    state = queue.state
    history = list(state.job_history)

    completed = [j for j in history if j.status == "completed"]
    avg_ms = (
        int(sum(j.processing_time_ms for j in completed) / len(completed))
        if completed else 0
    )

    return {
        "total_processed": state.total_processed,
        "total_errors": state.total_errors,
        "avg_processing_time_ms": avg_ms,
        "job_history": [
            {
                "article_id": j.article_id,
                "status": j.status,
                "processing_time_ms": j.processing_time_ms,
                "model_used": j.model_used,
                "original_size": j.original_size,   # D-06
                "output_size": j.output_size,         # D-06
                "timestamp": j.timestamp,
                "error": j.error,
            }
            for j in reversed(history)  # mas reciente primero
        ],
    }
```

### Pattern 6: Extender JobRecord con original_size y output_size (D-06)

**Que:** JobRecord en queue.py necesita dos campos nuevos. El procesador ya retorna `original_size` y `output_size` en ProcessingResult (ya implementado en Fase 1).

```python
# app/queue.py — modificar JobRecord
@dataclass
class JobRecord:
    article_id: str
    status: str
    processing_time_ms: int
    model_used: str
    timestamp: str
    original_size: str | None = None   # nuevo — "WxH"
    output_size: str | None = None     # nuevo — "WxH"
    error: str | None = None
```

**En submit_job — actualizar los dos puntos donde se crea JobRecord:**
```python
# Job exitoso:
self._state.job_history.append(JobRecord(
    ...,
    original_size=result.original_size,
    output_size=result.output_size,
))
# Job fallido — original_size/output_size quedan None (error ocurrio antes de tenerlos)
```

### Anti-Patrones a Evitar

- **Llamar reload() directamente desde on_modified():** on_modified() corre en el thread de watchdog, NO en el event loop. Llamar a config_manager.reload() desde ahi es tecnicamente seguro (no es async) pero si se necesita disparar efectos secundarios async (como model swap), se necesita el bridge. Usar siempre asyncio.run_coroutine_threadsafe() para mantener consistencia.
- **asyncio.create_task() desde el thread de watchdog:** create_task() solo puede llamarse desde el event loop — falla silenciosamente desde otro thread. Usar asyncio.run_coroutine_threadsafe() con la referencia al loop.
- **yaml.load() sin Loader:** El CLAUDE.md lo prohibe explicitamente. Usar yaml.safe_load() siempre para leer, yaml.dump() para escribir dicts.
- **new_session() en el event loop:** new_session() carga el modelo ONNX (~300MB, ~5-15s) — es CPU/IO-bound. SIEMPRE envolver con asyncio.to_thread().
- **Modificar QueueState._semaphore durante el swap:** No recrear el Semaphore. Solo cambiar app.state.rembg_session. El semaphore existente sigue coordinando concurrencia normalmente.
- **Flag de supresion sin clear():** Si suppress_flag.set() queda seteado permanentemente, watchdog ignora todos los reloads futuros. El clear() debe ocurrir en el handler (D-07: "ignorar el PROXIMO evento"), no en POST /config.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Detectar cambios en archivos | Loop polling con os.stat() | watchdog 6.0.0 Observer | Usa inotify/FSEvents/kqueue segun OS — eficiente, sin busy-wait |
| Comunicacion thread→asyncio | Queue propia o variables globales | asyncio.run_coroutine_threadsafe() | Garantia de thread-safety + integra con el event loop existente |
| Validar modelos rembg | Hardcodear lista en config.py | `from rembg.sessions import sessions_names` | Lista actualizada automaticamente con la version de rembg instalada |
| Serializar config a YAML | json.dumps + rename extension | yaml.dump(model_dump(), ...) | Produce YAML bien formateado, legible, con soporte unicode |
| Calcular avg en cada job | Acumulador running average | Calcular en el momento del GET /status | Mas simple, correcto, sin estado adicional |

**Key insight:** El proyecto ya tiene la infraestructura de datos completa (QueueState, JobRecord, ConfigManager). Esta fase es principalmente "plomeria" — conectar lo que existe con nuevas interfaces y el Observer de watchdog.

---

## Common Pitfalls

### Pitfall 1: Double-reload watchdog → POST /config

**What goes wrong:** POST /config escribe el YAML con yaml.dump(). watchdog detecta la modificacion y llama on_modified(), lo que dispara un segundo reload redundante (y potencialmente conflictivo si el modelo cambio).

**Why it happens:** watchdog monitorea el filesystem — cualquier escritura al archivo activa el evento, independientemente del origen.

**How to avoid:** D-07 — threading.Event como flag de supresion. El flujo correcto es:
1. `suppress_flag.set()` — activa supresion
2. Escribir YAML con `update_config()`
3. En `on_modified()`: si `suppress_flag.is_set()` → `suppress_flag.clear()` + return (sin reload)

**Warning signs:** Logs con dos entradas `config_reloaded` con source="watchdog" seguidas de una con source="api" en el mismo segundo.

### Pitfall 2: asyncio.create_task() desde thread de watchdog

**What goes wrong:** Llamar `asyncio.create_task(_reload_config(app))` desde `on_modified()` genera `RuntimeError: no running event loop` o el task se schedula en el loop equivocado y nunca ejecuta.

**Why it happens:** on_modified() corre en el thread del Observer, que no tiene un event loop de asyncio asociado.

**How to avoid:** Capturar el loop en el lifespan (`loop = asyncio.get_event_loop()`) y pasarlo al handler. Usar `asyncio.run_coroutine_threadsafe(coro, loop)` en lugar de `create_task()`.

**Warning signs:** RuntimeError en logs de watchdog, o config que nunca se recarga a pesar de modificar el YAML.

### Pitfall 3: Model swap sin esperar que termine el job activo

**What goes wrong:** Swap de sesion ONNX mientras un job esta en medio de `rembg.remove()` — el job activo usa la sesion vieja mientras se libera memoria, causando SIGSEGV o resultados incorrectos.

**Why it happens:** app.state.rembg_session es una referencia mutable. Si se reemplaza durante el procesamiento, el job activo puede quedar con una referencia invalida.

**How to avoid (D-02):** Esperar que el semaphore este libre antes de swapear. El semaphore del JobQueue garantiza que si `acquire()` tiene exito, no hay jobs activos. Hacer `await semaphore.acquire()` + `semaphore.release()` inmediato actua como barrier de espera.

**Warning signs:** Crashes ONNX, resultados de imagen corruptos, o errores `use after free` en onnxruntime.

### Pitfall 4: JobRecord original_size/output_size cuando el job falla en decode

**What goes wrong:** Si el job falla antes de llegar al step de procesamiento (ej. decode error), original_size y output_size no estan disponibles en el ProcessingResult. Intentar acceder a result.original_size causa AttributeError.

**Why it happens:** En el bloque except de submit_job, `result` no existe si process_fn lanzo excepcion.

**How to avoid:** En el bloque except, dejar original_size=None y output_size=None (valores default del JobRecord extendido). No intentar acceder a `result` cuando no existe.

**Warning signs:** AttributeError en submit_job al procesar imagenes invalidas.

### Pitfall 5: yaml.dump() altera el formato del settings.yaml

**What goes wrong:** yaml.dump() puede cambiar el orden de claves, quitar comentarios, o usar formato diferente al original. Esto es tecnicamnte correcto pero puede confundir al operador que edita el YAML a mano.

**Why it happens:** yaml.dump() serializa desde el dict de Python, no preserva el formato original.

**How to avoid:** Documentar que POST /config reescribe el YAML con formato estandar (sin comentarios). Es el comportamiento esperado y aceptable para este caso de uso. Usar `default_flow_style=False` para que sea legible en bloque.

---

## Code Examples

### Iniciar y detener watchdog Observer en FastAPI lifespan

```python
# Source: watchdog 6.0.0 docs + asyncio bridge pattern (verified GitHub gist)
@asynccontextmanager
async def lifespan(app: FastAPI):
    import threading
    from watchdog.observers import Observer
    from watchdog.events import FileSystemEventHandler

    # ... inicializar config, rembg, queue ...

    # Watchdog setup
    loop = asyncio.get_event_loop()
    suppress_flag = threading.Event()
    app.state.watchdog_suppress_flag = suppress_flag
    app.state.model_swapping = False

    handler = ConfigReloadHandler(loop, app, suppress_flag)
    observer = Observer()
    observer.schedule(handler, path="config/", recursive=False)
    observer.start()
    app.state.watchdog_observer = observer

    yield

    # Shutdown limpio
    observer.stop()
    observer.join()
```

### Obtener sessions_names de rembg para whitelist

```python
# Source: rembg 2.0.74 sessions/__init__.py (verified)
from rembg.sessions import sessions_names
# sessions_names: list[str] con todos los modelos validos instalados

VALID_MODELS: frozenset[str] = frozenset(sessions_names)

def validate_model_name(name: str) -> bool:
    return name in VALID_MODELS
```

### GET /config — respuesta simple

```python
@router.get("/config")
async def get_config(request: Request):
    """CONF-02: Retorna config activa como JSON."""
    return request.app.state.config_manager.config.model_dump()
```

---

## Runtime State Inventory

> Esta es una fase de nueva funcionalidad (no rename/refactor). No aplica inventario de estado en runtime.

---

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| watchdog | CONF-05 hot-reload | En requirements.txt — se instala en Docker | 6.0.0 (pinned) | — (sin fallback — requerido) |
| rembg.sessions module | CONF-04 whitelist D-04 | En requirements.txt via rembg[cpu] | 2.0.74 | Hardcodear lista en codigo |
| PyYAML | CONF-03 escritura YAML | En requirements.txt | 6.0.3 (pinned) | — (sin fallback — ya usado) |
| Python asyncio | Bridge thread→loop | Python stdlib | Python 3.12 (ambiente real) | — (stdlib) |

**Missing dependencies con fallback:**
- `rembg.sessions.sessions_names`: si por alguna razon el import falla (version antigua), hardcodear la lista como constante en config.py. Lista verified: `['u2net', 'u2netp', 'u2net_human_seg', 'u2net_cloth_seg', 'silueta', 'isnet-general-use', 'isnet-anime', 'birefnet-general', 'birefnet-general-lite', 'birefnet-portrait', 'birefnet-dis', 'birefnet-hrsod', 'birefnet-cod', 'birefnet-massive', 'sam', 'bria-rmbg', 'ben2-base', 'u2net_custom', 'dis_custom', 'ben_custom']`

---

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest 9.0.2 + pytest-asyncio 1.3.0 |
| Config file | `pyproject.toml` — `asyncio_mode = "auto"` ya configurado |
| Quick run command | `pytest tests/test_config.py tests/test_queue.py -x` |
| Full suite command | `pytest tests/ -x` |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| CONF-02 | GET /config retorna config activa | integration | `pytest tests/test_config_router.py::test_get_config -x` | ❌ Wave 0 |
| CONF-03 | POST /config deep merge + persist YAML | integration | `pytest tests/test_config_router.py::test_post_config_merge -x` | ❌ Wave 0 |
| CONF-03 | POST /config validacion estricta — campo invalido rechaza todo | integration | `pytest tests/test_config_router.py::test_post_config_invalid_rejects_all -x` | ❌ Wave 0 |
| CONF-03 | POST /config modelo invalido retorna 422 | integration | `pytest tests/test_config_router.py::test_post_config_invalid_model -x` | ❌ Wave 0 |
| CONF-04 | Cambio de modelo dispara swap, 503 durante swap | integration | `pytest tests/test_config_router.py::test_model_swap_blocks_queue -x` | ❌ Wave 0 |
| CONF-05 | Modificar YAML dispara reload sin restart | integration | `pytest tests/test_watchdog.py::test_watchdog_reload -x` | ❌ Wave 0 |
| CONF-05 | POST /config no genera double-reload (flag supresion) | integration | `pytest tests/test_watchdog.py::test_no_double_reload_after_post -x` | ❌ Wave 0 |
| API-06 | GET /status retorna metricas + historial 50 jobs | integration | `pytest tests/test_config_router.py::test_get_status -x` | ❌ Wave 0 |
| API-06 | GET /status historial incluye original_size y output_size | integration | `pytest tests/test_config_router.py::test_status_job_history_fields -x` | ❌ Wave 0 |
| QUEUE-05 | JobRecord tiene original_size y output_size | unit | `pytest tests/test_queue.py::test_job_record_has_size_fields -x` | ❌ Wave 0 |

### Sampling Rate
- **Per task commit:** `pytest tests/test_config.py tests/test_queue.py -x`
- **Per wave merge:** `pytest tests/ -x`
- **Phase gate:** Full suite green antes de `/gsd:verify-work`

### Wave 0 Gaps
- [ ] `tests/test_config_router.py` — cubre CONF-02, CONF-03, CONF-04, API-06
- [ ] `tests/test_watchdog.py` — cubre CONF-05 con asyncio event loop real y filesystem temp

**Nota sobre test_watchdog.py:** Testear watchdog requiere escribir un archivo YAML en un tmp_path real y esperar que el Observer lo detecte. Usar `asyncio.sleep(0.5)` para dar tiempo al Observer. El fixture debe arrancar/detener el Observer explicitamente.

*(Infraestructura existente: conftest.py con fixtures, asyncio_mode=auto, httpx AsyncClient — cubre todo lo necesario para los nuevos tests)*

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| threading.Lock para config reload | asyncio.run_coroutine_threadsafe() | watchdog + asyncio maduros | Thread-safe sin blocking del event loop |
| Polling de archivo con os.stat() | watchdog Observer con inotify | watchdog 1.x+ | Sin busy-wait, event-driven |
| Pydantic v1 model.dict() | Pydantic v2 model_dump() | Pydantic v2 (2023) | model_dump() es la API actual — no usar .dict() |

**Deprecated/outdated:**
- `loop.call_soon_threadsafe(asyncio.ensure_future, coro)`: patron obsoleto. Usar `asyncio.run_coroutine_threadsafe(coro, loop)` — mas claro y correcto.
- `yaml.load(stream)` sin Loader: prohibido en CLAUDE.md — CVE conocido.

---

## Open Questions

1. **Observer path: "config/" vs Path absoluto**
   - What we know: Observer.schedule() acepta string o Path. El container monta config/ como volumen.
   - What's unclear: Si se instancia ConfigManager con path relativo "config/settings.yaml", el Observer debe usar el mismo directorio relativo. En Docker, el cwd es la raiz del proyecto.
   - Recommendation: Usar `str(Path(config_manager._config_path).parent)` para derivar el path del Observer desde el ConfigManager — evita hardcodear "config/".

2. **asyncio.get_event_loop() deprecation en Python 3.12**
   - What we know: En Python 3.10+, `asyncio.get_event_loop()` emite DeprecationWarning cuando no hay loop corriendo. El ambiente real usa Python 3.12.
   - What's unclear: Dentro del lifespan de FastAPI (que ya esta en un loop), `asyncio.get_event_loop()` deberia funcionar correctamente. Alternativa: `asyncio.get_running_loop()`.
   - Recommendation: Usar `asyncio.get_running_loop()` dentro del lifespan — es la API correcta para Python 3.10+ cuando se sabe que hay un loop activo.

3. **Model swap timeout de 300s — muy generoso?**
   - What we know: El swap espera hasta 300s a que el job activo termine (timeout de queue es 120s).
   - What's unclear: Si el job activo ya esta en ejecucion con timeout 120s, el wait del swap solo necesita 120s max.
   - Recommendation: Usar `timeout=config.queue.timeout_seconds + 10` para el wait del semaphore en el swap.

---

## Project Constraints (from CLAUDE.md)

Directivas aplicables a esta fase:

| Directiva | Impacto en Fase 2 |
|-----------|-------------------|
| RAM ≤ 2GB — modelo birefnet-lite | El swap de modelo no debe cargar dos modelos simultaneamente. new_session() del nuevo modelo DEBE llamarse despues de confirmar que el viejo ya no esta en uso (el semaphore garantiza esto). |
| Modelo rembg: sesion global una sola vez en startup | El swap es la unica excepcion — y debe ser atomico (swap de referencia, no recreation durante un job activo). |
| asyncio.to_thread() obligatorio para CPU-bound | new_session() en el swap DEBE correr en asyncio.to_thread() — no directamente en el endpoint ni en el event loop. |
| yaml.safe_load() siempre, yaml.load() prohibido | Para LEER settings.yaml. Para ESCRIBIR, yaml.dump() sobre dicts de model_dump() es seguro (no hay objetos Python en el output). |
| No usar FastAPI BackgroundTasks para rembg | El swap de modelo (asyncio.create_task()) es diferente a BackgroundTasks — usa el event loop directamente, no el sistema de background de FastAPI. |
| Structured JSON logging en todos los modulos | D-08: cada reload de config logea `{"event": "config_reloaded", "source": "watchdog"|"api", ...}` |
| Python 3.12 es el runtime real (no 3.11) | Usar asyncio.get_running_loop() en lugar de asyncio.get_event_loop() (deprecado en 3.12). |

---

## Sources

### Primary (HIGH confidence)
- rembg 2.0.74 GitHub `sessions/__init__.py` — lista de sessions_names y SessionClass registry
- FastAPI docs `https://fastapi.tiangolo.com/tutorial/body-updates/` — partial update pattern con exclude_unset
- watchdog GitHub `https://github.com/gorakhargosh/watchdog` — Observer API y FileSystemEventHandler
- asyncio.run_coroutine_threadsafe docs (Python 3.12 stdlib) — bridge thread→loop

### Secondary (MEDIUM confidence)
- GitHub gist `https://gist.github.com/mivade/f4cb26c282d421a62e8b9a341c7c65f6` — watchdog + asyncio queue bridge pattern (verificado con docs oficiales)
- DeepWiki rembg session management `https://deepwiki.com/danielgatis/rembg/4.2-session-and-model-management` — model names (corroborado con sessions/__init__.py)

### Tertiary (LOW confidence)
- Ninguno — todas las afirmaciones tecnicas criticas tienen respaldo en fuentes HIGH o MEDIUM.

---

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — todo el stack ya esta instalado en requirements.txt, verificado en Fase 1
- Architecture: HIGH — patrones verificados con codigo existente + docs oficiales de watchdog y asyncio
- Pitfalls: HIGH — basados en comportamiento documentado de watchdog Observer threads y asyncio constraints
- rembg sessions_names whitelist: MEDIUM — lista extraida del codigo fuente de rembg, puede variar si se actualiza la version

**Research date:** 2026-03-30
**Valid until:** 2026-06-30 (stack estable, watchdog y rembg no son fast-moving)
