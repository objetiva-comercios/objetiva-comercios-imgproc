# PRD — Image Standardizer Service
**Versión:** 2.0 (autónomo, sin dependencias externas)
**Target:** Claude Code
**Estado:** Listo para implementar

---

## 1. Objetivo

Construir un microservicio Docker 100% autónomo que reciba una imagen de producto
de cualquier tamaño o formato, elimine el fondo automáticamente, estandarice el
resultado y devuelva un WebP listo para catálogo (800×800, fondo blanco, producto
centrado con padding).

El container no comparte nada con el entorno exterior: no usa volúmenes del host,
no asume nada instalado, no llama a servicios externos. Llega, levanta, funciona.

---

## 2. Restricciones de entorno (hard constraints)

| Recurso | Disponible | Impacto en diseño |
|---|---|---|
| RAM para este container | ≤ 2 GB | Modelo rembg: `birefnet-lite` como default. `max_concurrent: 1` obligatorio |
| CPU cores | 2 | `cpus: "1.5"` en docker-compose; dejar margen para el host |
| GPU | No | `onnxruntime-cpu` únicamente; sin CUDA |
| Volumen diario | < 100 imágenes | Cola in-memory simple; sin Redis ni persistencia |
| Dependencias externas | Ninguna | rembg integrado como library Python, modelos descargados en build time |

---

## 3. Stack tecnológico

| Componente | Elección | Motivo |
|---|---|---|
| Lenguaje | Python 3.11-slim | rembg es Python nativo; integración directa sin overhead de IPC |
| HTTP framework | FastAPI + Uvicorn | async nativo, perfecto para cola in-memory con Semaphore |
| Background removal | rembg (library) | Integrado directamente, modelo cargado una vez en RAM al startup |
| Modelo default | `birefnet-lite` | Balance calidad/RAM: ~300 MB cargado vs ~1.2 GB del general |
| Modelo alternativo | `birefnet-general` | Mejor calidad, configurable, requiere ~1.2 GB RAM (con advertencia) |
| Post-processing | Pillow (PIL) | Resize, compositing, WebP encode; sin overhead de libvips |
| Config | YAML + watchdog (hot reload) | Sin restart para cambios de parámetros |
| Web UI | Jinja2 + HTML/CSS/JS vanilla | Un solo archivo, cero dependencias frontend |
| CLI | Typer | Mismo código que la API, sin duplicación |
| Container | Docker (python:3.11-slim) | Imagen base mínima, modelos pre-descargados en build |

---

## 4. Estructura del proyecto

```
image-standardizer/
├── app/
│   ├── __init__.py
│   ├── main.py              # FastAPI app + lifespan (startup/shutdown)
│   ├── config.py            # ConfigManager: carga YAML + watchdog hot-reload
│   ├── processor.py         # ImageProcessor: pipeline completo, función por step
│   ├── queue.py             # JobQueue: asyncio.Semaphore + estado en memoria
│   ├── models.py            # Pydantic models: config, request, response, job status
│   ├── router_api.py        # Endpoints: /process, /health, /status
│   ├── router_config.py     # Endpoints: GET/POST /config
│   └── templates/
│       └── config_ui.html   # Web UI (Jinja2, autocontenida)
├── cli/
│   └── main.py              # CLI Typer: process, batch, serve, config
├── config/
│   └── settings.yaml        # Config default (copiada al container en build)
├── scripts/
│   └── download_models.py   # Script ejecutado en build para pre-descargar modelos
├── tests/
│   ├── conftest.py
│   ├── test_processor.py
│   ├── test_queue.py
│   └── test_api.py
├── Dockerfile
├── docker-compose.yml
├── requirements.txt
└── README.md
```

---

## 5. Archivo de configuración `config/settings.yaml`

Fuente de verdad única. El servicio lo recarga automáticamente al detectar cambios
(watchdog), sin reiniciar el container.

```yaml
# ── Modelo de remoción de fondo ─────────────────────────────────────────────
rembg:
  # Modelos disponibles y su consumo de RAM aproximado:
  #   birefnet-lite     → ~300 MB  (RECOMENDADO para ≤ 2 GB RAM)
  #   u2netp            → ~4 MB    (muy liviano, calidad básica)
  #   u2net             → ~170 MB  (calidad media)
  #   birefnet-general  → ~1.2 GB  (máxima calidad, CUIDADO con RAM < 2 GB)
  #   isnet-general-use → ~170 MB  (buena alternativa)
  model: "birefnet-lite"

  # Alpha matting: mejora bordes complejos (pelo, bordes finos)
  # Activar solo si hay problemas de bordes; es más lento y usa más RAM
  alpha_matting: false
  alpha_matting_foreground_threshold: 240
  alpha_matting_background_threshold: 10
  alpha_matting_erode_size: 10

# ── Output final ─────────────────────────────────────────────────────────────
output:
  size: 800                        # Lado del cuadrado final en píxeles
  format: "webp"                   # Formato de salida (webp es el único soportado en v1)
  quality: 85                      # Calidad WebP: 1-100 (0 = lossless)
  background_color: [255, 255, 255] # RGB del fondo; default blanco

# ── Padding alrededor del producto ──────────────────────────────────────────
padding:
  enabled: true
  percent: 10                      # % del canvas usado como margen en cada lado

# ── Auto-crop al bounding box del producto ───────────────────────────────────
autocrop:
  enabled: true
  # Umbral alpha: píxeles con alpha < threshold se consideran fondo transparente
  # Subir si quedan restos del fondo original; bajar si recorta partes del producto
  threshold: 10

# ── Mejoras de imagen ────────────────────────────────────────────────────────
enhancement:
  brightness: 1.0                  # 1.0 = sin cambio; >1.0 = más claro
  contrast: 1.0                    # 1.0 = sin cambio; >1.0 = más contraste

# ── Control de carga (CRÍTICO para ≤ 2 GB RAM) ───────────────────────────────
queue:
  # Con birefnet-lite y 2 GB RAM, max_concurrent DEBE ser 1
  # Solo subir a 2 si se cambia a u2netp y hay RAM de sobra
  max_concurrent: 1

  # Requests rechazados con 503 cuando hay este número esperando en cola
  max_queue_size: 10

  # Segundos máximos que un job puede esperar para empezar a procesarse
  timeout_seconds: 120

# ── Servidor ─────────────────────────────────────────────────────────────────
server:
  host: "0.0.0.0"
  port: 8010
  log_level: "info"                # debug | info | warning | error
```

---

## 6. Pipeline de procesamiento — `app/processor.py`

Cada step es una función pura e independiente. El orden es fijo e inamovible;
cambiar el orden produce resultados incorrectos.

```
INPUT: bytes de imagen cruda (cualquier formato, cualquier tamaño)
       + article_id (string)
       + config snapshot (tomado al inicio del job; inmutable durante el procesamiento)

──────────────────────────────────────────────────────────────────
STEP 1 · Decode & Validate
──────────────────────────────────────────────────────────────────
- Abrir con Pillow desde bytes
- Verificar que sea una imagen válida (try/except, raise ProcessingError si falla)
- Convertir a RGBA (necesario para preservar alpha durante todo el pipeline)
- Loggear: article_id, dimensiones originales, modo/formato detectado

──────────────────────────────────────────────────────────────────
STEP 2 · Background Removal (rembg)
──────────────────────────────────────────────────────────────────
- Llamar rembg.remove(input_bytes, session=app.state.rembg_session)
  ↑ La sesión se inicializa UNA SOLA VEZ en startup y se reutiliza.
  ↑ NUNCA crear new_session() dentro de esta función.
- Pasar parámetros de alpha_matting desde config si está habilitado
- Output: imagen PIL en modo RGBA con fondo transparente
- Loggear: tiempo de rembg, dimensiones resultantes

──────────────────────────────────────────────────────────────────
STEP 3 · Auto-crop al bounding box (si autocrop.enabled = true)
──────────────────────────────────────────────────────────────────
- Obtener canal alpha de la imagen RGBA
- Binarizar: píxeles con alpha > autocrop.threshold → foreground
- Calcular bounding box del foreground (getbbox sobre el canal alpha binarizado)
- GUARDIA: si el bbox cubre < 5% del área total de la imagen → omitir crop
  (indica error de rembg o imagen completamente transparente)
- Recortar imagen al bbox
- Loggear: bbox original, dimensiones tras crop

──────────────────────────────────────────────────────────────────
STEP 4 · Calcular escala y posición
──────────────────────────────────────────────────────────────────
canvas_px    = output.size                            # ej: 800
padding_px   = int(canvas_px * padding.percent / 100) # ej: 80
available_px = canvas_px - (2 * padding_px)           # ej: 640

- Calcular factor de escala: fit-inside (nunca distorsionar)
  scale = min(available_px / producto.width, available_px / producto.height)
- Calcular tamaño escalado del producto
- Calcular offset para centrarlo en el canvas:
  offset_x = (canvas_px - scaled_w) // 2
  offset_y = (canvas_px - scaled_h) // 2

──────────────────────────────────────────────────────────────────
STEP 5 · Compositing
──────────────────────────────────────────────────────────────────
- Crear imagen RGB nueva de canvas_px × canvas_px
  rellena con output.background_color
- Redimensionar el producto al tamaño escalado
  usando Image.LANCZOS (mejor calidad para downscale) o Image.BICUBIC (upscale)
- Pegar el producto sobre el fondo blanco usando su canal alpha como máscara:
  canvas.paste(producto_escalado, (offset_x, offset_y), mask=producto_escalado.split()[3])
- Output: imagen RGB (sin canal alpha)

──────────────────────────────────────────────────────────────────
STEP 6 · Enhancement (si brightness != 1.0 o contrast != 1.0)
──────────────────────────────────────────────────────────────────
- Aplicar ImageEnhance.Brightness(img).enhance(config.enhancement.brightness)
- Aplicar ImageEnhance.Contrast(img).enhance(config.enhancement.contrast)
- Omitir si ambos valores son exactamente 1.0 (sin overhead)

──────────────────────────────────────────────────────────────────
STEP 7 · Encode WebP
──────────────────────────────────────────────────────────────────
- Guardar imagen en BytesIO con format="WEBP", quality=output.quality
- Si quality == 0: lossless=True
- Retornar bytes del WebP + metadata del job

OUTPUT: bytes WebP + ProcessingResult(
  article_id, processing_time_ms, model_used,
  original_dimensions, output_dimensions, steps_applied
)
```

### Función principal del processor

```python
# Firma pública del processor — lo que llama el queue y el CLI:

async def process_image(
    image_bytes: bytes,
    article_id: str,
    config: AppConfig,
    rembg_session,          # Pasado desde app.state; no se crea aquí
) -> ProcessingResult:
    """
    Ejecuta el pipeline completo.
    Es una corutina async pero el trabajo CPU-bound ocurre
    dentro de asyncio.to_thread() en queue.py, no aquí.
    """
```

---

## 7. Cola de procesamiento — `app/queue.py`

### Por qué asyncio.Semaphore y no threads/workers separados

Con < 100 imágenes/día y `max_concurrent: 1`, el modelo de Semaphore es suficiente
y elimina toda complejidad (Redis, Celery, RQ, etc.). El único truco obligatorio:
rembg y Pillow son **bloqueantes** (CPU-bound), por lo que deben ejecutarse en un
thread pool para no freezar el event loop de FastAPI.

### Comportamiento esperado

```
Request entrante
       │
       ▼
¿ queue_size >= max_queue_size ?
       │ sí → 503 Service Unavailable (inmediato, no encolar)
       │ no
       ▼
Incrementar queue_counter
       │
       ▼
await semaphore.acquire()   ← espera aquí si hay max_concurrent jobs activos
       │
       ├─ Si espera > timeout_seconds → 504 Gateway Timeout
       │
       ▼
Decrementar queue_counter
Incrementar active_counter
       │
       ▼
result = await asyncio.to_thread(process_image_sync, ...)
  ↑ CRÍTICO: todo el trabajo CPU va aquí; el event loop sigue libre
       │
       ▼
semaphore.release()
Decrementar active_counter
Agregar a job_history (circular, últimos 50)
       │
       ▼
Retornar result
```

### Estado en memoria del queue

```python
@dataclass
class QueueState:
    active_jobs: int = 0          # Jobs procesando ahora mismo
    queued_jobs: int = 0          # Jobs esperando en cola
    total_processed: int = 0      # Contador histórico total
    total_errors: int = 0
    job_history: deque = field(   # Últimos 50 jobs (circular)
        default_factory=lambda: deque(maxlen=50)
    )
```

---

## 8. Endpoints HTTP — `app/router_api.py` y `app/router_config.py`

### `POST /process`

**Request:** `multipart/form-data`

| Campo | Tipo | Requerido | Descripción |
|---|---|---|---|
| `image` | file | ✓ | Imagen de entrada. Formatos: JPG, PNG, WebP, BMP, TIFF |
| `article_id` | string | ✓ | ID del artículo. Aparece en headers de respuesta |
| `override` | JSON string | ✗ | Override parcial de config solo para este job. Ej: `{"output":{"size":1200}}` |

**Response 200:**
```
Content-Type: image/webp
X-Article-Id: ART-001
X-Processing-Time-Ms: 3200
X-Model-Used: birefnet-lite
X-Original-Size: 2400x1800
X-Output-Size: 800x800
X-Steps-Applied: decode,rembg,autocrop,scale,composite,encode
```
Body: bytes WebP

**Responses de error:**

| Código | Cuándo |
|---|---|
| 400 | Imagen corrupta o no legible por Pillow |
| 422 | Falta `article_id` o campo `image` |
| 503 | Cola llena (`queued_jobs >= max_queue_size`) |
| 504 | Job esperó más de `timeout_seconds` |
| 500 | Error inesperado en pipeline (loggear stack trace) |

---

### `GET /health`

Respuesta rápida (sin tocar el queue). Usada por Docker HEALTHCHECK y n8n.

```json
{
  "status": "ok",
  "queue": {
    "active_jobs": 0,
    "queued_jobs": 0,
    "max_concurrent": 1,
    "max_queue_size": 10
  },
  "model_loaded": true,
  "model_name": "birefnet-lite",
  "uptime_seconds": 7200
}
```

---

### `GET /status`

Estado detallado con historial de jobs recientes.

```json
{
  "status": "ok",
  "queue": { ... },
  "stats": {
    "total_processed": 42,
    "total_errors": 1,
    "avg_processing_time_ms": 2840
  },
  "recent_jobs": [
    {
      "article_id": "ART-001",
      "status": "completed",
      "processing_time_ms": 2840,
      "model_used": "birefnet-lite",
      "timestamp": "2025-03-29T14:00:00Z"
    }
  ],
  "config_version": "2025-03-29T13:00:00Z"
}
```

---

### `GET /config`

Devuelve la configuración activa completa como JSON.

---

### `POST /config`

Actualiza uno o más valores y guarda el `settings.yaml`.

**Request:** `application/json` — objeto parcial (deep merge con config actual).

```json
{ "queue": { "max_concurrent": 1 }, "enhancement": { "brightness": 1.1 } }
```

**Comportamiento especial:** si el campo `rembg.model` cambia, el servicio debe:
1. Terminar de procesar el job activo (si hay uno).
2. Recrear la sesión rembg con el nuevo modelo.
3. Actualizar `app.state.rembg_session`.
4. Loggear el cambio de modelo con RAM estimada del nuevo modelo.

**Response:** config completa actualizada + advertencia si el modelo requiere más RAM
de la recomendada.

---

### `GET /ui`

Sirve la interfaz web de configuración (HTML completo generado con Jinja2).

---

## 9. Web UI de configuración — `app/templates/config_ui.html`

Página HTML autocontenida (estilos en `<style>`, scripts en `<script>`).
Servida por FastAPI en `/ui`. Sin dependencias externas (sin CDN, sin npm).

### Secciones del formulario

**1. Estado del servicio** (barra superior, siempre visible)
- Polling a `/health` cada 5 segundos
- Muestra: jobs activos, en cola, total procesados, modelo cargado
- Indicador visual: verde (idle), amarillo (procesando), rojo (cola llena)

**2. Modelo de remoción de fondo**
- Select dropdown con los modelos disponibles y su consumo de RAM
- Advertencia visual si se selecciona `birefnet-general` con la restricción de RAM
- Checkbox: alpha matting + sus 3 parámetros numéricos (mostrar solo si está activo)

**3. Output**
- Slider: tamaño (400-2000 px, step 100), muestra valor en tiempo real
- Slider: calidad WebP (50-100, step 5)
- Color picker: color de fondo (default #FFFFFF)

**4. Padding y crop**
- Toggle: padding habilitado + slider de % (5-30)
- Toggle: auto-crop habilitado + slider de threshold (0-50)

**5. Mejoras de imagen**
- Slider: brillo (0.5 - 2.0, step 0.1, default 1.0)
- Slider: contraste (0.5 - 2.0, step 0.1, default 1.0)
- Preview visual de los valores (texto: "sin cambio" en 1.0)

**6. Control de carga**
- Number input: max_concurrent (1-4, con advertencia si > 1 y RAM < 4 GB)
- Number input: max_queue_size (5-50)
- Number input: timeout_seconds (30-300)

**7. Botones**
- "Guardar configuración" → POST `/config` → feedback visual de éxito/error
- "Restaurar defaults" → recarga desde el YAML original
- "Ver YAML actual" → modal con el YAML completo, botón copiar

### Diseño
- Fondo claro, tipografía sans-serif del sistema
- Respeta `prefers-color-scheme: dark`
- Mobile-friendly (una columna en pantallas < 768px)
- Feedback inline en cada campo (cambios no guardados se marcan visualmente)
- Sin JavaScript externo; solo `fetch()` nativo y DOM API

---

## 10. CLI — `cli/main.py`

Implementado con **Typer**. Importa `app.processor` directamente (no llama a la
API HTTP). La lógica de procesamiento no se duplica.

### Comandos

#### `process` — procesar una imagen

```bash
image-standardizer process INPUT_FILE [OPCIONES]

Argumentos:
  INPUT_FILE          Ruta a la imagen de entrada

Opciones:
  --article-id TEXT   ID del artículo [default: nombre del archivo sin extensión]
  --output FILE       Archivo de salida [default: {INPUT}_standardized.webp]
  --config FILE       YAML alternativo [default: /app/config/settings.yaml]
  --override TEXT     JSON string con overrides de config
  --verbose           Mostrar detalle de cada step

Ejemplos:
  image-standardizer process foto.jpg --article-id ART-001
  image-standardizer process foto.jpg --output resultado.webp --verbose
  image-standardizer process foto.jpg --override '{"output":{"size":1200}}'
```

#### `batch` — procesar directorio completo

```bash
image-standardizer batch INPUT_DIR OUTPUT_DIR [OPCIONES]

Opciones:
  --pattern TEXT      Glob pattern [default: *.jpg *.jpeg *.png *.webp *.bmp *.tiff]
  --config FILE       YAML alternativo
  --report FILE       Exportar CSV con resultados (article_id, status, time_ms, error)
  --fail-fast         Detener al primer error [default: continuar y loggear errores]

Ejemplos:
  image-standardizer batch ./raw/ ./processed/
  image-standardizer batch ./raw/ ./processed/ --report reporte.csv
```

Nota: el batch es secuencial (un job a la vez) para respetar la restricción de RAM.
No usar multiprocessing.

#### `serve` — iniciar el servidor HTTP

```bash
image-standardizer serve [OPCIONES]

Opciones:
  --host TEXT    [default: desde config]
  --port INT     [default: desde config]
  --reload       Hot reload de código (solo desarrollo)
```

#### `config show` — ver configuración activa

```bash
image-standardizer config show
# Muestra el YAML con colores (rich)

image-standardizer config set rembg.model birefnet-general
# Modifica un valor y guarda el YAML
```

---

## 11. Startup y gestión de sesión — `app/main.py`

```python
@asynccontextmanager
async def lifespan(app: FastAPI):
    # ── STARTUP ──────────────────────────────────────────────
    config = load_config()

    # Inicializar sesión rembg UNA SOLA VEZ
    # Si el modelo no está en caché local, se descarga aquí
    # (en producción, ya fue descargado en build time)
    session = new_session(config.rembg.model)
    app.state.rembg_session = session
    app.state.current_model = config.rembg.model

    # Inicializar queue
    app.state.job_queue = JobQueue(config.queue)

    # Iniciar watchdog para hot-reload del YAML
    app.state.config_watcher = start_config_watcher(
        on_change=lambda new_config: reload_config(app, new_config)
    )

    logger.info(f"Startup completo. Modelo: {config.rembg.model}")
    logger.info(f"Endpoint: http://{config.server.host}:{config.server.port}")

    yield  # ── App corriendo ──────────────────────────────────

    # ── SHUTDOWN ─────────────────────────────────────────────
    app.state.config_watcher.stop()
    logger.info("Shutdown limpio.")


async def reload_config(app, new_config):
    """Llamado por watchdog cuando el YAML cambia."""
    old_model = app.state.current_model
    new_model = new_config.rembg.model

    app.state.config = new_config
    app.state.job_queue.update_limits(new_config.queue)

    if new_model != old_model:
        logger.info(f"Modelo cambiando: {old_model} → {new_model}")
        # Esperar a que termine el job activo (si hay)
        await app.state.job_queue.wait_for_idle(timeout=60)
        app.state.rembg_session = new_session(new_model)
        app.state.current_model = new_model
        logger.info(f"Nuevo modelo cargado: {new_model}")
```

---

## 12. Dockerfile

```dockerfile
FROM python:3.11-slim

LABEL maintainer="image-standardizer"
LABEL description="Servicio autónomo de estandarización de imágenes de catálogo"

# Dependencias del sistema para Pillow y rembg (onnxruntime-cpu)
RUN apt-get update && apt-get install -y --no-install-recommends \
    libgl1-mesa-glx \
    libglib2.0-0 \
    libgomp1 \
    libpng-dev \
    libjpeg-dev \
    libwebp-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Instalar dependencias Python primero (aprovechar cache de Docker)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copiar código
COPY app/ ./app/
COPY cli/ ./cli/
COPY config/ ./config/
COPY scripts/ ./scripts/

# ── Descargar modelo en build time ──────────────────────────────────────────
# Esto evita el delay de descarga en el primer request en producción.
# El modelo queda embebido en la imagen Docker (~300 MB para birefnet-lite).
# Si se quiere una imagen más liviana, comentar esta línea y aceptar
# que el primer arranque descargará el modelo (puede tardar 1-3 minutos).
RUN python scripts/download_models.py birefnet-lite

# Instalar CLI como comando del sistema
RUN pip install -e . --no-cache-dir

EXPOSE 8010

# Health check: el servicio tarda ~20-60s en cargar el modelo en RAM
HEALTHCHECK --interval=30s --timeout=10s --start-period=90s --retries=3 \
    CMD curl -f http://localhost:8010/health || exit 1

CMD ["image-standardizer", "serve"]
```

---

## 13. `scripts/download_models.py`

Script ejecutado en `docker build`. Descarga y cachea el modelo rembg para que
el primer request no tenga que esperar.

```python
#!/usr/bin/env python3
"""
Descarga modelos rembg en build time.
Uso: python scripts/download_models.py birefnet-lite [modelo2 ...]
"""
import sys
from rembg import new_session

def download_model(model_name: str):
    print(f"Descargando modelo: {model_name}...")
    try:
        session = new_session(model_name)
        print(f"✓ Modelo '{model_name}' descargado y cacheado.")
        del session
    except Exception as e:
        print(f"✗ Error descargando '{model_name}': {e}")
        sys.exit(1)

if __name__ == "__main__":
    models = sys.argv[1:] if len(sys.argv) > 1 else ["birefnet-lite"]
    for model in models:
        download_model(model)
```

---

## 14. `requirements.txt`

```
# HTTP framework
fastapi>=0.111.0
uvicorn[standard]>=0.30.0
python-multipart>=0.0.9

# Background removal
# onnxruntime (CPU-only) se instala automáticamente como dependencia de rembg
rembg>=2.0.57

# Image processing
Pillow>=10.3.0

# Config y validación
pydantic>=2.7.0
pydantic-settings>=2.2.0
PyYAML>=6.0.1

# Hot reload de config
watchdog>=4.0.0

# CLI
typer[all]>=0.12.0
rich>=13.7.0

# Templates web UI
jinja2>=3.1.4

# Async file I/O (CLI batch)
aiofiles>=23.2.1

# Testing
pytest>=8.2.0
pytest-asyncio>=0.23.0
httpx>=0.27.0          # Cliente async para tests de API
```

---

## 15. `docker-compose.yml`

Container completamente autónomo. Sin volúmenes compartidos, sin redes externas
asumidas. Para integrarlo al stack existente (n8n, Traefik), agregar la red.

```yaml
services:
  image-standardizer:
    build:
      context: ./image-standardizer
      dockerfile: Dockerfile
    container_name: image-standardizer
    restart: unless-stopped

    ports:
      - "8010:8010"

    volumes:
      # Solo se monta la config para poder editarla desde el host
      # y aprovechar el hot-reload sin reconstruir la imagen
      - ./image-standardizer/config:/app/config

    environment:
      - CONFIG_PATH=/app/config/settings.yaml
      - LOG_LEVEL=info
      - PYTHONUNBUFFERED=1

    # Límites de recursos: conservador para servidor con ≤ 2 GB disponibles
    mem_limit: 2g
    mem_reservation: 1g     # RAM garantizada al container
    cpus: "1.5"             # Deja 0.5 core libre para el host y otros servicios

    # Para agregar al stack de n8n, incluir la red existente:
    # networks:
    #   - tu_red_interna
    # Y quitar el mapeo de ports si n8n accede por nombre de container

    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8010/health"]
      interval: 30s
      timeout: 10s
      start_period: 90s     # El modelo tarda en cargarse en RAM
      retries: 3
```

---

## 16. Modelos disponibles y guía de selección

| Modelo | RAM aprox. | Calidad | Cuándo usar |
|---|---|---|---|
| `u2netp` | ~4 MB | ★★☆☆☆ | RAM extremadamente limitada o pruebas rápidas |
| `u2net` | ~170 MB | ★★★☆☆ | Fallback liviano con buena calidad general |
| `isnet-general-use` | ~170 MB | ★★★★☆ | Buena alternativa a birefnet si RAM es crítica |
| **`birefnet-lite`** | **~300 MB** | **★★★★☆** | **Default recomendado para ≤ 2 GB RAM** |
| `birefnet-general` | ~1.2 GB | ★★★★★ | Máxima calidad; requiere ≥ 3 GB RAM disponibles |

> **Advertencia importante:** con `mem_limit: 2g`, el modelo `birefnet-general`
> puede hacer que el container sea killed por OOM killer del kernel. Si se quiere
> usar, subir `mem_limit` a mínimo `3g` y verificar que el servidor lo soporte.

---

## 17. Guía de parámetros de fine-tuning (para la web UI)

| Parámetro | Default | Subir cuando... | Bajar cuando... |
|---|---|---|---|
| `padding.percent` | 10 | El producto se ve "pegado" al borde | Ocupa demasiado espacio vacío |
| `autocrop.threshold` | 10 | Quedan restos del fondo original en los bordes | Recorta partes del producto (bordes oscuros) |
| `enhancement.brightness` | 1.0 | Las fotos de origen son oscuras | Las fotos quedan sobreexpuestas |
| `enhancement.contrast` | 1.0 | Las fotos se ven "planas" o lavadas | El producto parece demasiado duro |
| `output.quality` | 85 | Hay artefactos visibles en gradientes | El archivo WebP pesa demasiado |
| `rembg.alpha_matting` | false | Bordes del producto quedan "pixelados" (pelo, bordes finos) | (es lento; activar solo si es necesario) |
| `queue.max_concurrent` | 1 | El throughput es muy bajo Y hay RAM libre | OOM errors o lentitud general |

---

## 18. Integración con n8n

El nodo que antes llamaba a `rembg:3010/api/remove` se reemplaza así:

```
HTTP Request Node
  Método: POST
  URL:    http://image-standardizer:8010/process
  Auth:   ninguna (interno)

  Body → Form Data:
    image      → [binary field con la imagen]
    article_id → {{ $json.article_id }}

  Response:
    Tipo: Binary
    Nombre del campo: data

  En caso de error:
    - Continuar en error: sí (para no romper el pipeline completo)
    - Loggear X-Processing-Time-Ms del header de respuesta
```

Para leer los headers de respuesta en n8n y guardar el tiempo de procesamiento,
agregar un nodo Function después del HTTP Request:

```javascript
// Leer metadata del header de respuesta
return [{
  json: {
    ...items[0].json,
    processing_time_ms: parseInt($response.headers['x-processing-time-ms']),
    model_used: $response.headers['x-model-used'],
    article_id: $response.headers['x-article-id'],
  },
  binary: items[0].binary
}];
```

---

## 19. Tests requeridos

### `tests/conftest.py`

```python
# Fixtures globales:
# - config_default(): AppConfig con valores default
# - sample_image_bytes(): imagen JPG sintética 500×400 para tests rápidos
# - rembg_session(): sesión real con birefnet-lite (scope="session", se crea una vez)
# - client(): TestClient de FastAPI con la app inicializada
```

### Tests de processor (`tests/test_processor.py`)

| Test | Input | Verifica |
|---|---|---|
| `test_decode_valid_jpg` | JPG 500×400 | Decodifica sin error, dimensiones correctas |
| `test_decode_valid_png_rgba` | PNG con alpha | Mantiene RGBA |
| `test_decode_invalid_file` | bytes random | Lanza ProcessingError |
| `test_autocrop_removes_empty_space` | Imagen con mucho espacio vacío | Bounding box recortado |
| `test_autocrop_skip_if_too_small` | Imagen casi transparente | Crop omitido, no falla |
| `test_padding_applied` | Producto 400×400, canvas 800 | Producto no ocupa más de 720px |
| `test_aspect_ratio_preserved` | Imagen 800×400 (2:1) | Output 800×800 sin distorsión |
| `test_background_is_white` | Cualquier imagen | Pixel (0,0) del output = (255,255,255) |
| `test_output_size` | Cualquier imagen | Output siempre 800×800 |
| `test_output_format_webp` | Cualquier imagen | Output es WebP válido |
| `test_brightness_enhancement` | brightness=1.5 | Imagen más clara que con 1.0 |
| `test_contrast_enhancement` | contrast=1.5 | Contraste diferente al default |
| `test_full_pipeline` | JPG real 2000×1500 | Completa sin errores, output 800×800 WebP |

### Tests de queue (`tests/test_queue.py`)

| Test | Verifica |
|---|---|
| `test_single_job_completes` | Job se procesa y retorna resultado |
| `test_503_when_queue_full` | Al superar max_queue_size → JobQueueFullError |
| `test_max_concurrent_respected` | Con max_concurrent=1, el segundo job espera al primero |
| `test_timeout_raises_error` | Job que tarda más de timeout → TimeoutError |
| `test_queue_state_updates` | active_jobs y queued_jobs reflejan estado real |

### Tests de API (`tests/test_api.py`)

| Test | Verifica |
|---|---|
| `test_process_success` | POST /process → 200 + WebP en body |
| `test_process_headers` | Response incluye X-Article-Id, X-Processing-Time-Ms |
| `test_process_missing_article_id` | POST sin article_id → 422 |
| `test_process_invalid_image` | POST con archivo texto → 400 |
| `test_health_ok` | GET /health → 200 con status "ok" |
| `test_health_model_loaded` | GET /health → model_loaded: true |
| `test_config_get` | GET /config → JSON con config completa |
| `test_config_update` | POST /config → config actualizada |
| `test_config_invalid_field` | POST /config con campo inválido → 422 |
| `test_ui_serves_html` | GET /ui → 200 con Content-Type text/html |
| `test_status_has_history` | GET /status → recent_jobs array presente |

---

## 20. Instrucciones para Claude Code

### Orden de implementación recomendado

1. **`app/models.py`** — Primero los tipos. Define `AppConfig`, `ProcessingResult`,
   `JobStatus`, `QueueState`. Todo lo demás los importa.

2. **`app/config.py`** — `ConfigManager`: carga YAML, valida con Pydantic,
   expone `get_config()`. Agregar watchdog al final de esta tarea.

3. **`app/processor.py`** — El núcleo. Implementar cada step como función
   privada `_step_N_nombre()`. Testear con imágenes reales antes de continuar.

4. **`app/queue.py`** — `JobQueue` con Semaphore. **CRÍTICO:** usar
   `asyncio.to_thread()` para llamar al processor. Sin esto el event loop freezea.

5. **`app/main.py`** — Lifespan (startup/shutdown), inicialización de sesión
   rembg, inicialización de queue, arranque de watchdog.

6. **`app/router_api.py`** — Endpoints `/process`, `/health`, `/status`.

7. **`app/router_config.py`** — Endpoints `/config` GET/POST, `/ui` GET.

8. **`app/templates/config_ui.html`** — Web UI completa.

9. **`cli/main.py`** — Comandos Typer. Reutilizar processor directamente.

10. **`Dockerfile` + `docker-compose.yml`** — Build y validar que el container
    arranca limpio desde cero.

11. **`tests/`** — Tests unitarios e integración.

### Reglas críticas que Claude Code debe respetar

- **La sesión rembg es global**: inicializar en startup, pasar como parámetro,
  nunca crear dentro del processor. Si se crea por request, el RAM explota.

- **asyncio.to_thread es obligatorio**: rembg y Pillow bloquean el thread.
  Sin `await asyncio.to_thread(...)`, FastAPI no puede responder al health check
  mientras procesa una imagen.

- **Pillow Image.LANCZOS para downscale, BICUBIC para upscale**: usar el algoritmo
  correcto según si se está reduciendo o agrandando la imagen.

- **El canal alpha del output final debe eliminarse**: el WebP de catálogo es
  RGB puro (fondo blanco), no RGBA.

- **El override de config por request debe ser un deep merge**, no un reemplazo.
  Un override `{"output": {"size": 1200}}` no debe borrar `output.quality`.

- **El Dockerfile descarga el modelo en build time** via `scripts/download_models.py`.
  El modelo queda en `~/.u2net/` dentro de la imagen. Verificar que el path de
  caché de rembg sea consistente entre el script de descarga y el runtime.

- **El HEALTHCHECK usa `start_period: 90s`**: cargar birefnet-lite en RAM tarda
  entre 20 y 60 segundos. Sin este delay, Docker marca el container como unhealthy
  antes de que termine de inicializar.

- **Logging estructurado en cada step**: usar `logging.getLogger(__name__)` con
  el formato `%(asctime)s | %(levelname)s | %(name)s | %(message)s`. Incluir
  `article_id` en todos los logs del pipeline de procesamiento.
