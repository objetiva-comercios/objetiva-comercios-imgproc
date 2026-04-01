# Image Standardizer

Microservicio Docker que recibe imagenes de producto de cualquier tamaño o formato, elimina el fondo automaticamente con rembg, y devuelve un WebP estandarizado (800x800, fondo blanco, producto centrado con padding) listo para catalogo. Diseñado para el catalogo de Objetiva Comercios, corre 100% autonomo en un VPS sin dependencias externas, sin GPU, y sin costo por imagen.

## Tecnologias

| Categoria | Tecnologia |
|-----------|-----------|
| Lenguaje | Python 3.11 |
| API HTTP | FastAPI 0.135.2 |
| ASGI Server | uvicorn 0.42.0 (con uvloop + httptools) |
| Background Removal | rembg 2.0.74 (modelo isnet-general-use, ONNX CPU) |
| Manipulacion de imagen | Pillow 12.1.1 |
| CLI | Typer 0.24.1 |
| Configuracion | PyYAML 6.0.3 + watchdog 6.0.0 (hot-reload) |
| Web UI | Jinja2 3.1.6 + vanilla JS (autocontenida, sin CDN) |
| Contenedor | Docker (python:3.11-slim) |
| Testing | pytest 9.0.2 + pytest-asyncio 1.3.0 + httpx 0.28.1 |

## Requisitos previos

- **Docker** >= 20.10 con plugin compose v2 (`docker compose`)
- **Git**
- ~3 GB de disco (imagen Docker + modelo ONNX)
- 2 GB de RAM disponibles para el container
- 1.5 CPU cores

## Instalacion

### Opcion A: Script automatico

```bash
curl -sL https://raw.githubusercontent.com/objetiva-comercios/objetiva-comercios-imgproc/main/install.sh | bash
```

El script clona el repo, construye la imagen Docker (descarga el modelo rembg en build time), levanta el servicio y ejecuta health check.

### Opcion B: Manual

```bash
git clone https://github.com/objetiva-comercios/objetiva-comercios-imgproc.git
cd objetiva-comercios-imgproc
docker compose build
docker compose up -d
```

El primer build tarda varios minutos porque descarga el modelo ONNX (~300 MB). El servicio tarda 60-90 segundos en estar listo (carga del modelo en CPU).

## Configuracion

El archivo `config/settings.yaml` controla todo el comportamiento. Los cambios se aplican en caliente (watchdog) sin reiniciar el container.

```yaml
rembg:
  model: isnet-general-use
  alpha_matting: false
output:
  size: 800
  format: webp
  quality: 85
  background_color: [255, 255, 255]
padding:
  enabled: true
  percent: 10
autocrop:
  enabled: true
  threshold: 10
enhancement:
  brightness: 1.0
  contrast: 1.0
queue:
  max_concurrent: 1
  max_queue_size: 10
  timeout_seconds: 120
server:
  host: 0.0.0.0
  port: 8010
  log_level: info
```

| Seccion | Parametros clave | Default |
|---------|-----------------|---------|
| `rembg` | `model`, `alpha_matting` | `isnet-general-use`, `false` |
| `output` | `size`, `quality`, `background_color` | `800`, `85`, `[255,255,255]` |
| `padding` | `enabled`, `percent` | `true`, `10` |
| `autocrop` | `enabled`, `threshold` | `true`, `10` |
| `enhancement` | `brightness`, `contrast` | `1.0`, `1.0` |
| `queue` | `max_concurrent`, `max_queue_size`, `timeout_seconds` | `1`, `10`, `120` |

Tambien se puede modificar via Web UI (`/ui`) o via API (`POST /config`).

## Uso

### API HTTP

Procesar una imagen:

```bash
curl -X POST http://localhost:8010/process \
  -F "image=@foto-producto.jpg" \
  -F "article_id=SKU001" \
  --output resultado.webp
```

La respuesta incluye headers con metadata: `X-Article-Id`, `X-Processing-Time-Ms`, `X-Model-Used`, `X-Original-Size`, `X-Output-Size`, `X-Steps-Applied`.

Se puede enviar un override parcial de configuracion por request:

```bash
curl -X POST http://localhost:8010/process \
  -F "image=@foto.jpg" \
  -F "article_id=SKU002" \
  -F 'config={"output": {"quality": 95}, "padding": {"percent": 15}}' \
  --output resultado.webp
```

### CLI

El CLI reutiliza el mismo pipeline que la API, sin levantar servidor HTTP.

```bash
# Procesar una imagen individual
imgproc process foto.jpg --output resultado.webp

# Procesar un directorio completo con reporte CSV
imgproc batch ./fotos/ --output ./webp/ --csv reporte.csv

# Iniciar el servidor HTTP
imgproc serve

# Ver configuracion activa
imgproc config show

# Modificar un parametro
imgproc config set output.size 1200
```

### Web UI

Acceder a `http://localhost:8010/ui` para configurar y monitorear el servicio desde el browser. La UI es autocontenida (sin dependencias externas), soporta modo oscuro y es mobile-friendly.

### Comandos Docker

```bash
docker compose logs -f        # Ver logs en tiempo real
docker compose restart        # Reiniciar
docker compose down           # Detener
docker compose ps             # Estado
```

## API / Endpoints

| Metodo | Ruta | Descripcion |
|--------|------|-------------|
| `POST` | `/process` | Recibe imagen (multipart/form-data), devuelve WebP estandarizado |
| `GET` | `/health` | Health check: status, cola, modelo cargado, uptime |
| `GET` | `/status` | Metricas: total procesados, errores, tiempo promedio, historial (ultimos 50 jobs) |
| `GET` | `/config` | Configuracion activa como JSON |
| `POST` | `/config` | Actualizar configuracion con deep merge (persiste YAML) |
| `GET` | `/ui` | Web UI de configuracion |

**Codigos de error de POST /process:**

| Codigo | Causa |
|--------|-------|
| 400 | Imagen corrupta o formato no soportado |
| 422 | Campos requeridos faltantes |
| 503 | Cola llena (max_queue_size alcanzado) |
| 504 | Timeout de procesamiento excedido |

## Arquitectura del proyecto

```
objetiva-comercios-imgproc/
├── app/
│   ├── main.py              # FastAPI app, lifespan (carga modelo, watchdog)
│   ├── processor.py         # Pipeline: decode → rembg → autocrop → scale → composite → enhance → encode
│   ├── queue.py             # Cola async con Semaphore, job tracking
│   ├── config.py            # ConfigManager: YAML + watchdog hot-reload
│   ├── models.py            # Modelos Pydantic (AppConfig, JobRecord, etc.)
│   ├── router_api.py        # Endpoints /process, /health
│   ├── router_config.py     # Endpoints /config, /status
│   ├── router_ui.py         # Endpoint /ui
│   ├── cli.py               # CLI Typer (process, batch, serve, config)
│   └── templates/
│       └── ui.html          # Web UI autocontenida (Jinja2 + vanilla JS)
├── config/
│   └── settings.yaml        # Configuracion del servicio (hot-reload)
├── scripts/
│   └── download_models.py   # Descarga modelo rembg en build time
├── tests/                   # Tests unitarios e integracion (103 tests)
├── Dockerfile               # python:3.11-slim + modelo pre-descargado
├── docker-compose.yml       # Limites: 2GB RAM, 1.5 CPU
├── requirements.txt
├── requirements-dev.txt
└── pyproject.toml
```

### Pipeline de procesamiento

```
Imagen entrada (JPG/PNG/WebP/BMP/TIFF)
    │
    ├── decode        Decodificar + EXIF transpose
    ├── rembg         Remover fondo (isnet-general-use, ONNX CPU)
    ├── autocrop      Recortar al bounding box del producto
    ├── scale         Escalar manteniendo aspect ratio (fit-inside)
    ├── composite     Centrar sobre canvas 800x800 con fondo blanco + padding
    ├── enhance       Ajustar brightness/contrast si esta configurado
    └── encode        Codificar como WebP (calidad configurable)
    │
    ▼
WebP 800x800 RGB (fondo blanco, producto centrado)
```

## Docker

- **Imagen base**: `python:3.11-slim` (~121 MB)
- **Modelo**: isnet-general-use, descargado en build time (evita delay de 1-3 min en primer request)
- **HEALTHCHECK**: `curl /health` con `start_period: 90s` (el modelo tarda en cargar)
- **Limites**: `mem_limit: 2g`, `cpus: 1.5`
- **Volumen**: solo `./config` montado para hot-reload desde el host
- **Variables de entorno**: `OMP_NUM_THREADS=2`, `OPENBLAS_NUM_THREADS=2` (evitar thread explosion de ONNX)

## Deploy

Ver [DEPLOY.md](DEPLOY.md) para instrucciones completas de deploy y troubleshooting.

Instalacion rapida:

```bash
curl -sL https://raw.githubusercontent.com/objetiva-comercios/objetiva-comercios-imgproc/main/install.sh | bash
```

El script es idempotente: detecta instalaciones previas, respalda la configuracion, y reinstala limpio.

## Estado del proyecto

- **Milestone**: v1.0 completado — 6/6 fases finalizadas, 45/45 requisitos implementados
- **Tests**: 103 tests (unitarios + integracion)
- **Ultimo avance**: 2026-04-01 (Phase 6: Tech Debt Cleanup)
