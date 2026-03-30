---
phase: 01-pipeline-core-api-basica
plan: 05
subsystem: infra
tags: [docker, dockerfile, docker-compose, rembg, onnxruntime, isnet-general-use]

# Dependency graph
requires:
  - phase: 01-pipeline-core-api-basica
    provides: "FastAPI app, pipeline processor, config, queue, API endpoints (planes 01-04)"
provides:
  - "Dockerfile con python:3.11-slim y modelo isnet-general-use pre-descargado en build time"
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
    - "HEALTHCHECK con start-period=90s para dar tiempo al startup del modelo"
    - "Solo config/ montado como volumen — el resto del codigo esta embebido en la imagen"

key-files:
  created:
    - Dockerfile
    - docker-compose.yml
    - scripts/download_models.py
    - .dockerignore
  modified:
    - app/processor.py
    - app/models.py
    - config/settings.yaml

key-decisions:
  - "isnet-general-use como modelo rembg: birefnet-general-lite requiere ~3.9GB pico (OOM en 2-4GB), isnet-general-use funciona con ~1.5GB pico"
  - "python:3.11-slim como imagen base (no alpine — alpine rompe wheels de onnxruntime y Pillow)"
  - "libgl1 en vez de libgl1-mesa-glx (obsoleto en Debian Trixie)"
  - "alpha_composite en vez de paste(mask=) para bordes suaves sin halo negro"
  - "_clean_alpha_artifacts con scipy.ndimage.label para centrado correcto del producto"

patterns-established:
  - "Modelo rembg pre-descargado via new_session() en build time: no hay descarga en runtime"
  - "LOAD_TRUNCATED_IMAGES = True para tolerar JPEGs parciales"
  - "Connected components para limpiar artefactos de rembg antes de autocrop"

requirements-completed: [DOCK-01, DOCK-02, DOCK-03, DOCK-04, DOCK-05]

# Metrics
duration: 45min
completed: 2026-03-30
---

# Phase 01 Plan 05: Docker Build + Compose Summary

**Dockerfile python:3.11-slim con isnet-general-use pre-descargado, docker-compose con mem_limit 2g/1.5 cpus, y fixes de producción verificados con imagen real**

## Performance

- **Duration:** ~45 min (incluye debugging OOM y fixes de bordes)
- **Started:** 2026-03-30T11:39:00Z
- **Completed:** 2026-03-30T12:45:00Z
- **Tasks:** 2/2 completados (checkpoint humano aprobado)
- **Files modified:** 11

## Accomplishments
- Dockerfile con imagen python:3.11-slim, modelo isnet-general-use pre-descargado en build time
- docker-compose.yml con limites de recursos (2g RAM, 1.5 CPU), solo config/ como volumen
- HEALTHCHECK con start-period=90s para el tiempo de carga del modelo ONNX
- Fixes de producción: modelo viable para 2GB, bordes suaves, centrado correcto, JPEGs parciales

## Task Commits

1. **Task 1: Dockerfile + docker-compose.yml + download_models.py** - `6fbf84a`
2. **Task 2: Verificación Docker + fixes de producción** - `ec9f383`

## Deviations from Plan

- **Modelo:** birefnet-general-lite → isnet-general-use. birefnet pico ~3.9GB RAM, probado hasta 4GB mem_limit sin éxito. isnet-general-use pico ~1.5GB, calidad adecuada para catálogo de productos.
- **libgl1-mesa-glx → libgl1:** paquete obsoleto en Debian Trixie
- **Fixes adicionales en processor.py:** LOAD_TRUNCATED_IMAGES, _clean_alpha_artifacts (scipy connected components), alpha_composite para bordes

## Verification (Docker)

- Build: OK
- Health: OK (model_loaded: true, model_name: isnet-general-use)
- POST /process: HTTP 200, ~4s, WebP 800x800 RGB, producto centrado, bordes suaves
- RAM pico: 1.48GB / 2GB — sin OOM, sin restarts
- 55 tests unitarios verdes

## Self-Check: PASSED

- FOUND: Dockerfile
- FOUND: docker-compose.yml
- FOUND: scripts/download_models.py
- FOUND: .dockerignore
- FOUND: commit 6fbf84a
- FOUND: commit ec9f383
