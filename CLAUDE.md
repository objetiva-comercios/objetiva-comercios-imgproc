<!-- GSD:project-start source:PROJECT.md -->
## Project

**Image Standardizer Service**

Microservicio Docker 100% autónomo que recibe imágenes de producto de cualquier tamaño o formato, elimina el fondo automáticamente con rembg, estandariza el resultado (800x800, fondo blanco, producto centrado con padding) y devuelve un WebP listo para catálogo. Expone una API HTTP, un CLI y una Web UI de configuración. Diseñado para el catálogo de Objetiva Comercios.

**Core Value:** Recibir cualquier imagen de producto y devolver un WebP limpio, estandarizado, listo para catálogo — sin intervención manual, sin dependencias externas, sin configuración compleja.

### Constraints

- **RAM**: ≤ 2 GB para el container — obliga a usar birefnet-lite y max_concurrent=1
- **CPU**: 2 cores disponibles, container usa 1.5 — sin GPU
- **Dependencias externas**: Ninguna — todo embebido en la imagen Docker
- **Modelo rembg**: sesión global inicializada una vez en startup, nunca por request
- **Event loop**: asyncio.to_thread() obligatorio para operaciones CPU-bound (rembg, Pillow)
- **Formato de salida**: WebP únicamente, RGB (sin alpha en output final)
- **Orden del pipeline**: fijo e inamovible (decode → rembg → autocrop → scale → composite → enhance → encode)
<!-- GSD:project-end -->

<!-- GSD:stack-start source:research/STACK.md -->
## Technology Stack

## Recommended Stack
### Core Technologies
| Technology | Version | Purpose | Why Recommended |
|------------|---------|---------|-----------------|
| Python | 3.11 | Runtime del microservicio | Versión LTS estable con soporte hasta Oct 2027. rembg 2.0.74 requiere >=3.11. Evita 3.12+ por posibles incompatibilidades de wheels con onnxruntime en el build inicial. |
| FastAPI | 0.135.2 | API HTTP async (POST /process, GET /health, GET /config) | Estándar de facto para APIs Python async en 2026. Pydantic v2 integrado, validación automática, OpenAPI/docs sin config adicional. Performance superior a Flask/Django para I/O-bound endpoints. |
| uvicorn | 0.42.0 | ASGI server de producción | Único server ASGI maduro y production-ready para FastAPI. Instalar con `uvicorn[standard]` para incluir uvloop + httptools y doblar throughput en Linux. |
| rembg | 2.0.74 | Remoción de fondo con IA (birefnet-lite) | La librería referente para background removal en Python. Soporta múltiples modelos ONNX incluyendo birefnet-lite. Sesión global reutilizable = el modelo carga una sola vez. Requiere Python >=3.11. |
| Pillow | 12.1.1 | Manipulación de imágenes (crop, scale, composite, enhance, encode WebP) | Librería PIL mantenida activamente. Soporte nativo de WebP. La única opción para manipulación de imágenes de propósito general en Python — no hay alternativa madura. |
| onnxruntime | 1.24.4 | Inferencia del modelo ONNX (dependencia de rembg) | Dependencia directa de rembg. Usar la versión CPU (`pip install onnxruntime`) — sin GPU en este VPS. Python 3.11 tiene wheels prebuilt para manylinux. |
### Supporting Libraries
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| Typer | 0.24.1 | CLI (process, batch, serve, config) | Siempre — definido en PROJECT.md. Typer usa type hints para inferir CLI, integra bien con asyncio, mismo autor que FastAPI. Typer 0.13+ incluye `typer-cli` integrado. |
| Jinja2 | 3.1.6 | Templates para Web UI de configuración | Siempre — la Web UI autocontenida usa Jinja2 + vanilla JS. Incluida como dependencia de FastAPI por lo que no agrega peso. |
| PyYAML | 6.0.3 | Parsing y escritura de config.yaml | Siempre — el formato de configuración elegido. Preferir `yaml.safe_load()` en lugar de `yaml.load()`. |
| watchdog | 6.0.0 | Hot-reload de config.yaml sin restart | Siempre — definido en PROJECT.md. Monitorea cambios en el archivo de config y recarga en caliente. Requiere un Observer thread separado del event loop de asyncio. |
| python-multipart | >=0.0.9 | Parsing de form-data multipart (upload de imágenes) | Siempre — FastAPI requiere esta dependencia para aceptar `UploadFile`. Sin esto, `POST /process` falla en runtime. |
### Development & Testing Tools
| Tool | Version | Purpose | Notes |
|------|---------|---------|-------|
| pytest | 9.0.2 | Test runner | Estándar. Configurar via `pyproject.toml` con `[tool.pytest.ini_options]`. |
| pytest-asyncio | 1.3.0 | Tests async para endpoints FastAPI | Usar `asyncio_mode = "auto"` en pyproject.toml para evitar decorar cada test. Versión 1.3.0 tiene event loop scoping estable. |
| httpx | 0.28.1 | Cliente HTTP para integration tests | FastAPI's `TestClient` está basado en httpx. Usar `httpx.AsyncClient(app=app, base_url="http://test")` para tests async sin levantar servidor real. |
| pytest-cov | >=6.0 | Coverage reports | Integrar con `pytest --cov=src --cov-report=term-missing`. |
## Installation
# ---- requirements.txt (producción) ----
# onnxruntime se instala como dependencia de rembg[cpu]
# ---- requirements-dev.txt (desarrollo y testing) ----
# Instalación de producción
# Instalación de desarrollo
## Alternatives Considered
| Recommended | Alternative | When to Use Alternative |
|-------------|-------------|-------------------------|
| `asyncio.to_thread()` + `asyncio.Semaphore` | Celery + Redis | Solo cuando volumen > 1000 imgs/día o se necesita persistencia de jobs, retries distribuidos, o múltiples workers. Para < 100 imgs/día es sobrearquitectura. |
| FastAPI | Flask | Cuando el equipo conoce mejor Flask o el proyecto no necesita async. FastAPI tiene un 30-40% más de boilerplate para casos simples pero mejor DX para APIs async. |
| FastAPI | Django REST Framework | Solo para proyectos con múltiples apps, ORM, admin panel. Overkill para un microservicio de imagen processing. |
| Pillow | OpenCV | OpenCV es superior para operaciones de computer vision (detección de contornos, etc.). Pillow es suficiente para crop/scale/composite/enhance y más liviano. Si se agrega detección de productos en el pipeline, reconsiderar. |
| `rembg[cpu]` | `backgroundremover` / `carvekit` | rembg tiene mejor soporte activo, más modelos, mejor documentación. backgroundremover está prácticamente abandonado. carvekit requiere más dependencias. |
| PyYAML | python-dotenv | dotenv es para variables de entorno simples. YAML permite estructuras de config anidadas necesarias para este proyecto (padding, calidad, pipeline steps). |
| `python:3.11-slim` (base Docker) | `python:3.11-alpine` | Alpine usa musl libc que rompe los wheels prebuilt de onnxruntime y Pillow. El rebuild desde fuente en Alpine tarda 10+ minutos. Usar slim siempre para Python con dependencias científicas. |
## What NOT to Use
| Avoid | Why | Use Instead |
|-------|-----|-------------|
| `onnxruntime-gpu` | El VPS no tiene GPU. Instala CUDA deps (~2GB) innecesarios y puede fallar en build. | `onnxruntime` (CPU) vía `rembg[cpu]` |
| `yaml.load(stream)` sin Loader | Vulnerable a ejecución de código arbitrario (CVE conocido). PyYAML advierte con DeprecationWarning. | `yaml.safe_load(stream)` siempre |
| FastAPI `BackgroundTasks` para rembg | `BackgroundTasks` corre en el event loop — operaciones CPU-bound como rembg bloquean todo el loop durante el procesamiento. | `asyncio.to_thread(process_fn)` dentro del endpoint |
| Sesión rembg por request | Crear `new_session("birefnet-lite")` por cada request carga el modelo (~300MB) en RAM repetidamente. Causa OOM en segundos. | Sesión global inicializada una vez en `startup` event de FastAPI |
| `python:3.11` (imagen Docker completa) | ~875MB vs ~121MB para slim. Build más lento, mayor superficie de ataque. Las dependencias del sistema necesarias para este proyecto están en slim. | `python:3.11-slim` |
| `threading.Thread` para watchdog + asyncio | Mezclar threads con el event loop de asyncio sin cuidado causa race conditions en la config. | Observer thread de watchdog con `asyncio.run_coroutine_threadsafe()` o un lock `asyncio.Lock` compartido para config reload |
| Celery | Infraestructura innecesaria (requiere Redis/RabbitMQ como broker). El proyecto explícitamente requiere cero dependencias externas. | `asyncio.Semaphore(1)` para limitar concurrencia a 1 |
| `uvicorn` sin `[standard]` | Sin `uvloop` y `httptools`, uvicorn usa la implementación pura de Python (~30% más lento). El overhead importa en un VPS con 1.5 CPU. | `uvicorn[standard]` |
## Stack Patterns by Variant
- Escalar `asyncio.Semaphore` a `max_concurrent=2` primero (si RAM lo permite)
- Si se necesita queue persistente: agregar Redis + ARQ (async task queue, mismo paradigma asyncio, sin Celery overhead)
- NO agregar PostgreSQL — el proyecto está explícitamente out-of-scope para persistencia
- Cambiar `rembg[cpu]` → `rembg[gpu]` en requirements
- Cambiar imagen base Docker a `nvidia/cuda:12.x-runtime-ubuntu22.04` + instalar Python
- Modelo: subir de `birefnet-lite` a `birefnet-general` (mayor calidad, misma RAM con GPU)
- Pillow soporta nativamente JPEG, PNG, WebP, AVIF (12.x)
- Solo agregar un parámetro `format` al endpoint — no hay cambio de dependencias
## Version Compatibility
| Package | Compatible Con | Notas |
|---------|----------------|-------|
| `rembg==2.0.74` | `Python >=3.11`, `onnxruntime >=1.17` | rembg instala la versión compatible de onnxruntime automáticamente. No pinear onnxruntime directamente — dejar que rembg lo resuelva. |
| `FastAPI==0.135.2` | `Pydantic >=2.0`, `Starlette >=0.41` | FastAPI 0.100+ requiere Pydantic v2. No intentar forzar Pydantic v1 — rompe el ecosistema. |
| `uvicorn==0.42.0` | `Python >=3.10` | 0.40.0+ droppea soporte para Python 3.9. Compatible con Python 3.11. |
| `pytest-asyncio==1.3.0` | `pytest >=9.0` | pytest-asyncio 1.x requiere pytest >=9. Versiones anteriores (0.23.x) pueden tener issues con event loop scoping. |
| `Pillow==12.1.1` | `Python 3.9-3.13` | Pillow 12.x tiene libwebp actualizado. Compatibilidad con Python 3.11 confirmada. |
## Docker Base Image Decision
# Dependencias del sistema necesarias para Pillow y onnxruntime
# Pre-descargar el modelo en build time (evita delay de 1-3 min en primer request)
# El modelo se descarga a U2NET_HOME durante el build
## Sources
- [rembg PyPI](https://pypi.org/project/rembg/) — versión 2.0.74, Python >=3.11 (verificado 2026-03-30) — **HIGH confidence**
- [FastAPI PyPI](https://pypi.org/project/fastapi/) — versión 0.135.2 (verificado 2026-03-30) — **HIGH confidence**
- [uvicorn PyPI](https://pypi.org/project/uvicorn/) — versión 0.42.0 (verificado 2026-03-30) — **HIGH confidence**
- [Pillow PyPI](https://pypi.org/project/pillow/) — versión 12.1.1 (verificado 2026-03-30) — **HIGH confidence**
- [Typer PyPI](https://pypi.org/project/typer/) — versión 0.24.1 (verificado 2026-03-30) — **HIGH confidence**
- [watchdog PyPI](https://pypi.org/project/watchdog/) — versión 6.0.0 (verificado 2026-03-30) — **HIGH confidence**
- [PyYAML PyPI](https://pypi.org/project/PyYAML/) — versión 6.0.3 (verificado via WebSearch, 2026-03-30) — **MEDIUM confidence**
- [onnxruntime PyPI](https://pypi.org/project/onnxruntime/) — versión 1.24.4 (verificado via WebSearch, 2026-03-30) — **MEDIUM confidence**
- [httpx PyPI](https://pypi.org/project/httpx/) — versión 0.28.1 stable (verificado 2026-03-30) — **HIGH confidence**
- [pytest PyPI](https://pypi.org/project/pytest/) — versión 9.0.2 (verificado 2026-03-30) — **HIGH confidence**
- [pytest-asyncio PyPI](https://pypi.org/project/pytest-asyncio/) — versión 1.3.0 (verificado 2026-03-30) — **HIGH confidence**
- [Python Docker slim vs alpine](https://pythonspeed.com/articles/base-image-python-docker-images/) — rationale para imagen base — **HIGH confidence**
- [FastAPI async CPU-bound guidance](https://fastapi.tiangolo.com/async/) — patrón asyncio.to_thread — **HIGH confidence**
<!-- GSD:stack-end -->

<!-- GSD:conventions-start source:CONVENTIONS.md -->
## Conventions

Conventions not yet established. Will populate as patterns emerge during development.
<!-- GSD:conventions-end -->

<!-- GSD:architecture-start source:ARCHITECTURE.md -->
## Architecture

Architecture not yet mapped. Follow existing patterns found in the codebase.
<!-- GSD:architecture-end -->

<!-- GSD:workflow-start source:GSD defaults -->
## GSD Workflow Enforcement

Before using Edit, Write, or other file-changing tools, start work through a GSD command so planning artifacts and execution context stay in sync.

Use these entry points:
- `/gsd:quick` for small fixes, doc updates, and ad-hoc tasks
- `/gsd:debug` for investigation and bug fixing
- `/gsd:execute-phase` for planned phase work

Do not make direct repo edits outside a GSD workflow unless the user explicitly asks to bypass it.
<!-- GSD:workflow-end -->



<!-- GSD:profile-start -->
## Developer Profile

> Profile not yet configured. Run `/gsd:profile-user` to generate your developer profile.
> This section is managed by `generate-claude-profile` -- do not edit manually.
<!-- GSD:profile-end -->
