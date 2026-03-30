---
phase: 01-pipeline-core-api-basica
plan: 05
subsystem: infra
tags: [docker, dockerfile, docker-compose, rembg, onnxruntime, birefnet-lite]

# Dependency graph
requires:
  - phase: 01-pipeline-core-api-basica
    provides: "FastAPI app, pipeline processor, config, queue, API endpoints (planes 01-04)"
provides:
  - "Dockerfile con python:3.11-slim y modelo birefnet-lite pre-descargado en build time"
  - "docker-compose.yml con limites de recursos (2GB RAM, 1.5 CPU) y volume mount de config"
  - "scripts/download_models.py para pre-descarga del modelo en build time"
  - ".dockerignore para excluir archivos innecesarios del build context"
affects: [deploy, vps-integration, n8n-pipeline]

# Tech tracking
tech-stack:
  added: [Docker, docker-compose]
  patterns:
    - "Modelo ONNX pre-descargado en build time — evita cold start de 1-3 min en primer request"
    - "OMP_NUM_THREADS=2 en ENV del Dockerfile para limitar threads ONNX en VPS"
    - "HEALTHCHECK con start-period=90s para dar tiempo al startup de birefnet-lite"
    - "Solo config/ montado como volumen — el resto del codigo esta embebido en la imagen"

key-files:
  created:
    - Dockerfile
    - docker-compose.yml
    - scripts/download_models.py
    - .dockerignore
  modified: []

key-decisions:
  - "python:3.11-slim como imagen base (no alpine — alpine rompe wheels de onnxruntime y Pillow)"
  - "pip install --no-cache-dir para no inflar la imagen con cache de pip"
  - "Solo config/ montado como volumen — permite hot-reload de config sin rebuild"
  - "restart: unless-stopped en compose para resiliencia operacional"

patterns-established:
  - "Modelo rembg pre-descargado via new_session() en build time: no hay descarga en runtime"
  - "OMP_NUM_THREADS=2 como ENV en Dockerfile + docker-compose environment para doble garantia"

requirements-completed: [DOCK-01, DOCK-02, DOCK-03, DOCK-04, DOCK-05]

# Metrics
duration: 5min
completed: 2026-03-30
---

# Phase 01 Plan 05: Docker Build + Compose Summary

**Dockerfile python:3.11-slim con birefnet-lite pre-descargado, docker-compose con mem_limit 2g/1.5 cpus, y HEALTHCHECK con start-period 90s para el servicio Image Standardizer**

## Performance

- **Duration:** ~5 min
- **Started:** 2026-03-30T11:39:26Z
- **Completed:** 2026-03-30T11:44:00Z
- **Tasks:** 1 completado (1 pendiente de verificacion humana)
- **Files modified:** 4

## Accomplishments
- Dockerfile con imagen python:3.11-slim, modelo birefnet-lite pre-descargado en build time via scripts/download_models.py
- docker-compose.yml con limites de recursos (2g RAM, 1.5 CPU), solo config/ montado como volumen, restart: unless-stopped
- HEALTHCHECK configurado con start-period=90s para respetar el tiempo de carga del modelo ONNX
- .dockerignore excluye .git, .planning, tests/, .venv y archivos generados para builds limpios

## Task Commits

1. **Task 1: Dockerfile + docker-compose.yml + download_models.py** - `6fbf84a` (feat)

**Plan metadata:** pendiente (se generara al completar verificacion humana)

## Files Created/Modified
- `Dockerfile` - Build de imagen con python:3.11-slim, sys deps, modelo pre-descargado, HEALTHCHECK, CMD uvicorn
- `docker-compose.yml` - Compose con mem_limit 2g, cpus 1.5, volume ./config:/app/config
- `scripts/download_models.py` - Pre-descarga birefnet-lite via rembg.new_session() en build time
- `.dockerignore` - Excluye .git, .planning, tests/, __pycache__, .venv del build context

## Decisions Made
- `python:3.11-slim` como imagen base: no alpine (musl libc rompe onnxruntime wheels), no imagen completa (875MB vs 121MB)
- `pip install --no-cache-dir`: evita que el cache de pip infle la imagen final
- Modelo descargado con `new_session(model)` durante build: queda en home del container, disponible en startup sin red
- Solo `./config:/app/config` montado: el codigo esta embebido, config editable en host para hot-reload
- `restart: unless-stopped`: resiliencia ante crashes sin loop infinito si se hace stop manual

## Deviations from Plan

None - plan ejecutado exactamente como estaba escrito.

## Issues Encountered
None.

## Known Stubs

None — todos los archivos generados son configuracion de infraestructura, sin datos hardcodeados ni placeholders.

## User Setup Required

**Task 2 pendiente de verificacion humana.** El usuario debe:

1. Buildear la imagen:
   ```bash
   cd /home/sanchez/proyectos/objetiva-comercios-imgproc
   docker compose build
   ```
   Verificar: build completa sin errores, modelo se descarga durante el build.

2. Levantar el servicio:
   ```bash
   docker compose up -d
   ```
   Esperar ~60 segundos para que el modelo cargue en RAM.

3. Verificar health:
   ```bash
   curl http://localhost:8010/health
   ```
   Esperado: `{"status":"ok","model_loaded":true,"model_name":"birefnet-lite",...}`

4. Probar procesamiento (con cualquier imagen JPG/PNG):
   ```bash
   curl -X POST http://localhost:8010/process \
     -F "image=@alguna_foto.jpg" \
     -F "article_id=TEST-001" \
     --output resultado.webp
   ```
   Esperado: archivo resultado.webp de ~800x800 con fondo blanco.

5. Verificar RAM:
   ```bash
   docker stats --no-stream imgproc
   ```
   Esperado: MEM USAGE < 2GB.

6. Limpiar:
   ```bash
   docker compose down
   ```

## Next Phase Readiness
- Empaquetado Docker completo, listo para deploy en VPS
- Pendiente: verificacion humana de docker build + servicio funcional (Task 2)
- Una vez verificado: la fase 01 queda completa y el servicio esta listo para integracion con n8n

---
*Phase: 01-pipeline-core-api-basica*
*Completed: 2026-03-30*

## Self-Check: PASSED

- FOUND: Dockerfile
- FOUND: docker-compose.yml
- FOUND: scripts/download_models.py
- FOUND: .dockerignore
- FOUND: .planning/phases/01-pipeline-core-api-basica/01-05-SUMMARY.md
- FOUND: commit 6fbf84a
