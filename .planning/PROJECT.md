# Image Standardizer Service

## What This Is

Microservicio Docker 100% autónomo que recibe imágenes de producto de cualquier tamaño o formato, elimina el fondo automáticamente con rembg, estandariza el resultado (800x800, fondo blanco, producto centrado con padding) y devuelve un WebP listo para catálogo. Expone una API HTTP, un CLI y una Web UI de configuración. Diseñado para el catálogo de Objetiva Comercios.

## Core Value

Recibir cualquier imagen de producto y devolver un WebP limpio, estandarizado, listo para catálogo — sin intervención manual, sin dependencias externas, sin configuración compleja.

## Requirements

### Validated

(None yet — ship to validate)

### Active

- [ ] Pipeline de procesamiento: decode → rembg → autocrop → scale → composite → enhance → encode WebP
- [ ] API HTTP (FastAPI): POST /process, GET /health, GET /status
- [ ] API de configuración: GET/POST /config con hot-reload via watchdog
- [ ] Cola in-memory con asyncio.Semaphore (max_concurrent=1)
- [ ] Web UI de configuración autocontenida (Jinja2 + vanilla JS)
- [ ] CLI con Typer: process, batch, serve, config
- [ ] Configuración YAML con hot-reload (watchdog)
- [ ] Dockerfile con modelo pre-descargado en build time
- [ ] docker-compose.yml con límites de recursos (2GB RAM, 1.5 CPU)
- [ ] Tests unitarios e integración (processor, queue, API)

### Out of Scope

- Integración directa con n8n/Traefik — se integra después, por ahora es standalone
- GPU/CUDA — solo CPU (onnxruntime-cpu)
- Persistencia de jobs — todo in-memory, sin Redis ni DB
- Múltiples formatos de salida — solo WebP en v1
- Procesamiento batch vía API — solo el CLI tiene batch
- Autenticación — servicio interno, sin auth

## Context

- El servicio reemplaza un contenedor rembg standalone que solo removía fondos, sin estandarización
- Corre en un VPS con recursos limitados (2GB RAM disponibles para este container, 2 CPU cores)
- Volumen esperado: < 100 imágenes/día — no requiere infraestructura de cola compleja
- El modelo default es isnet-general-use por balance calidad/RAM
- Se integra a futuro con un pipeline n8n que procesa artículos de catálogo
- Stack: Python 3.11, FastAPI, rembg, Pillow, Typer, Docker

## Constraints

- **RAM**: ≤ 2 GB para el container — obliga a usar isnet-general-use y max_concurrent=1
- **CPU**: 2 cores disponibles, container usa 1.5 — sin GPU
- **Dependencias externas**: Ninguna — todo embebido en la imagen Docker
- **Modelo rembg**: sesión global inicializada una vez en startup, nunca por request
- **Event loop**: asyncio.to_thread() obligatorio para operaciones CPU-bound (rembg, Pillow)
- **Formato de salida**: WebP únicamente, RGB (sin alpha en output final)
- **Orden del pipeline**: fijo e inamovible (decode → rembg → autocrop → scale → composite → enhance → encode)

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| Python + FastAPI sobre Go/Rust | rembg es Python nativo; evitar IPC overhead | — Pending |
| birefnet-lite como modelo default | Balance calidad/RAM para ≤ 2GB | — Pending |
| asyncio.Semaphore sobre Celery/Redis | < 100 img/día no justifica infraestructura de cola | — Pending |
| Modelo pre-descargado en build time | Evitar delay de 1-3 min en primer request | — Pending |
| Web UI vanilla sin frameworks JS | Cero dependencias frontend, un solo archivo HTML | — Pending |
| YAML + watchdog para config | Cambios sin restart del container | — Pending |

## Evolution

This document evolves at phase transitions and milestone boundaries.

**After each phase transition** (via `/gsd:transition`):
1. Requirements invalidated? → Move to Out of Scope with reason
2. Requirements validated? → Move to Validated with phase reference
3. New requirements emerged? → Add to Active
4. Decisions to log? → Add to Key Decisions
5. "What This Is" still accurate? → Update if drifted

**After each milestone** (via `/gsd:complete-milestone`):
1. Full review of all sections
2. Core Value check — still the right priority?
3. Audit Out of Scope — reasons still valid?
4. Update Context with current state

---
*Last updated: 2026-04-01 — Phase 6 complete: Tech Debt Cleanup (4 items cerrados: deps explícitas, numpy vectorizado, docs modelo, UI autocontenida sin CDN). 103 tests, milestone v1.0 listo.*
