# Deploy — Image Standardizer

## Instalacion rapida

```bash
curl -sL https://raw.githubusercontent.com/objetiva-comercios/objetiva-comercios-imgproc/main/install.sh | sudo bash
```

O desde una copia local del repo:

```bash
sudo bash install.sh
```

El servicio se instala en `/opt/objetiva-comercios/objetiva-comercios-imgproc/`.

## Requisitos

- **Docker** >= 20.10 con plugin compose v2 (`docker compose`)
- **Git**
- **Disco**: ~3 GB (imagen Docker + modelo ONNX isnet-general-use)
- **RAM**: 2 GB disponibles para el container (pico ~1.2 GB durante inferencia)
- **CPU**: 1.5 cores asignados al container

## Arquitectura

```
┌──────────────────────────────────────────────┐
│  Container: imgproc (python:3.11-slim)       │
│                                              │
│  FastAPI (uvicorn) :8010                     │
│    ├── POST /process   (pipeline de imagen)  │
│    ├── GET  /health    (health check)        │
│    ├── GET  /status    (metricas)            │
│    ├── GET  /config    (config activa)       │
│    ├── POST /config    (actualizar config)   │
│    └── GET  /ui        (Web UI)              │
│                                              │
│  Pipeline: decode → rembg → autocrop →       │
│    scale → composite → enhance → encode      │
│                                              │
│  Modelo: isnet-general-use (pre-descargado)  │
│  Cola: asyncio.Semaphore(max_concurrent=1)   │
│  Config: YAML + watchdog (hot-reload)        │
│                                              │
│  Volumes:                                    │
│    ./config → /app/config (hot-reload)       │
└──────────────────────────────────────────────┘
```

- **Sin dependencias externas**: no requiere Redis, PostgreSQL, ni ningun servicio adicional
- **Modelo embebido**: se descarga en build time, no en runtime
- **Config hot-reload**: modificar `config/settings.yaml` recarga automaticamente sin restart

## Configuracion

El archivo `config/settings.yaml` controla todo el comportamiento del servicio:

| Seccion | Parametros clave | Default |
|---------|-----------------|---------|
| `rembg` | `model`, `alpha_matting` | `isnet-general-use`, `false` |
| `output` | `size`, `format`, `quality`, `background_color` | `800`, `webp`, `85`, `[255,255,255]` |
| `padding` | `enabled`, `percent` | `true`, `10` |
| `autocrop` | `enabled`, `threshold` | `true`, `10` |
| `enhancement` | `brightness`, `contrast` | `1.0`, `1.0` |
| `queue` | `max_concurrent`, `max_queue_size`, `timeout_seconds` | `1`, `10`, `120` |
| `server` | `host`, `port`, `log_level` | `0.0.0.0`, `8010`, `info` |

Los cambios en este archivo se aplican en caliente (watchdog). No hace falta reiniciar el container.

Tambien se puede modificar la config via la Web UI (`/ui`) o via API (`POST /config`).

## Servicios

| Servicio | Puerto | Descripcion |
|----------|--------|-------------|
| `imgproc` | 8010 | API HTTP + Web UI de configuracion |

## Red y acceso

El servicio actualmente expone el puerto 8010 directamente (standalone, sin Traefik).

**Acceso local:**
```
http://localhost:8010
```

**Acceso desde otra maquina en la red:**
```
http://<IP-DEL-VPS>:8010
```

**Futura integracion con Traefik:**
Cuando se integre con Traefik, agregar labels al `docker-compose.yml`, comentar la seccion `ports:`, y conectar a la red de Traefik.

## Comandos utiles

```bash
cd /opt/objetiva-comercios/objetiva-comercios-imgproc

# Ver logs en tiempo real
docker compose logs -f

# Reiniciar el servicio
docker compose restart

# Detener
docker compose down

# Estado del container
docker compose ps

# Health check manual
curl http://localhost:8010/health

# Procesar una imagen de prueba
curl -X POST http://localhost:8010/process \
  -F "image=@mi-imagen.jpg" \
  -F "article_id=TEST001" \
  --output resultado.webp

# Ver metricas
curl http://localhost:8010/status

# Ver config activa
curl http://localhost:8010/config
```

## Actualizacion

```bash
cd /opt/objetiva-comercios/objetiva-comercios-imgproc
docker compose down
git pull
docker compose build
docker compose up -d
```

El `install.sh` tambien maneja actualizaciones: detecta la instalacion previa, respalda la config, y reinstala desde cero.

## Verificacion post-deploy

Despues de instalar, verificar que todo funciona:

```bash
# 1. Health check
curl http://localhost:8010/health

# 2. Procesar imagen de prueba
curl -X POST http://localhost:8010/process \
  -F "image=@cualquier-foto.jpg" \
  -F "article_id=TEST001" \
  --output test.webp

# 3. Verificar que el output es WebP 800x800
file test.webp
# test.webp: RIFF (little-endian) data, Web/P image
```

Si el health check responde `{"status":"healthy"}` y la imagen se procesa correctamente, el deploy esta completo.

## Troubleshooting

### El container tarda mucho en arrancar
Es normal. El modelo rembg (isnet-general-use) tarda 60-90 segundos en cargar en CPU. El HEALTHCHECK tiene `start_period: 90s` por esta razon.

### OOM Kill (el container se cierra solo)
El container tiene limite de 2 GB. Si el modelo + una imagen grande exceden la RAM:
- Verificar que `max_concurrent` sea 1 en `config/settings.yaml`
- Verificar que no haya otro proceso consumiendo RAM en el host

### Error 503 "Cola llena"
La cola tiene un maximo de 10 requests pendientes. Si se reciben mas, responde 503. Esperar a que se procesen las imagenes en cola o aumentar `max_queue_size` en la config.

### Error 504 "Timeout"
El procesamiento de una imagen tiene timeout de 120s. Si las imagenes son muy grandes, aumentar `timeout_seconds` en la config.

### El modelo no se descargo
Si el build fallo durante la descarga del modelo, reconstruir sin cache:
```bash
docker compose build --no-cache
```

## Estructura del proyecto

```
/opt/objetiva-comercios/objetiva-comercios-imgproc/
├── app/
│   ├── main.py           # Entrypoint FastAPI, startup/shutdown
│   ├── processor.py      # Pipeline de procesamiento de imagen
│   ├── queue.py          # Cola async con Semaphore
│   ├── config.py         # Carga y hot-reload de config YAML
│   ├── models.py         # Modelos Pydantic
│   ├── router_api.py     # Endpoints /process, /health
│   ├── router_config.py  # Endpoints /config, /status
│   ├── router_ui.py      # Endpoint /ui (Web UI)
│   ├── cli.py            # CLI con Typer
│   └── templates/
│       └── ui.html       # Web UI autocontenida
├── config/
│   └── settings.yaml     # Configuracion (hot-reload)
├── scripts/
│   └── download_models.py  # Descarga modelo en build time
├── tests/                # Tests unitarios e integracion
├── Dockerfile
├── docker-compose.yml
├── requirements.txt
├── requirements-dev.txt
├── pyproject.toml
└── install.sh
```
