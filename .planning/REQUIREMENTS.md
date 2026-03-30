# Requirements: Image Standardizer Service

**Defined:** 2026-03-30
**Core Value:** Recibir cualquier imagen de producto y devolver un WebP limpio, estandarizado, listo para catálogo — sin intervención manual, sin dependencias externas.

## v1 Requirements

Requirements for initial release. Each maps to roadmap phases.

### Pipeline (PIPE)

- [ ] **PIPE-01**: El servicio decodifica imágenes JPG, PNG, WebP, BMP y TIFF correctamente
- [ ] **PIPE-02**: El servicio aplica EXIF transpose antes de procesar (fotos de celular rotadas)
- [ ] **PIPE-03**: El servicio remueve el fondo de la imagen usando rembg con sesión global
- [ ] **PIPE-04**: El servicio recorta al bounding box del producto (autocrop via canal alpha)
- [ ] **PIPE-05**: El servicio escala el producto manteniendo aspect ratio (fit-inside, nunca distorsionar)
- [ ] **PIPE-06**: El servicio compone el producto centrado sobre canvas 800x800 con fondo blanco y padding
- [ ] **PIPE-07**: El servicio aplica ajustes de brightness y contrast si están configurados
- [ ] **PIPE-08**: El servicio codifica el resultado como WebP con calidad configurable
- [ ] **PIPE-09**: El output es siempre RGB (sin canal alpha) de exactamente el tamaño configurado
- [ ] **PIPE-10**: El pipeline ejecuta los steps en orden fijo: decode → rembg → autocrop → scale → composite → enhance → encode

### API (API)

- [ ] **API-01**: POST /process acepta multipart/form-data con image (file) y article_id (string)
- [ ] **API-02**: POST /process retorna image/webp con headers X-Article-Id, X-Processing-Time-Ms, X-Model-Used, X-Original-Size, X-Output-Size, X-Steps-Applied
- [ ] **API-03**: POST /process acepta override parcial de config (JSON string, deep merge)
- [ ] **API-04**: POST /process retorna 400 para imagen corrupta, 422 para campos faltantes, 503 para cola llena, 504 para timeout
- [ ] **API-05**: GET /health retorna status, estado de la cola, modelo cargado, uptime
- [ ] **API-06**: GET /status retorna estadísticas (total procesados, errores, avg time) e historial de últimos 50 jobs

### Queue (QUEUE)

- [ ] **QUEUE-01**: La cola usa asyncio.Semaphore con max_concurrent configurable (default 1)
- [ ] **QUEUE-02**: Requests que exceden max_queue_size reciben 503 inmediato
- [ ] **QUEUE-03**: Requests que esperan más de timeout_seconds reciben 504
- [ ] **QUEUE-04**: El trabajo CPU-bound (rembg, Pillow) se ejecuta en asyncio.to_thread
- [ ] **QUEUE-05**: La cola mantiene estado en memoria: active_jobs, queued_jobs, total_processed, total_errors, job_history (últimos 50)

### Config (CONF)

- [ ] **CONF-01**: La configuración se lee de un archivo YAML (settings.yaml)
- [ ] **CONF-02**: GET /config retorna la configuración activa como JSON
- [ ] **CONF-03**: POST /config actualiza valores con deep merge y guarda el YAML
- [ ] **CONF-04**: Si rembg.model cambia via POST /config, la sesión se recrea después de que termine el job activo
- [ ] **CONF-05**: El servicio detecta cambios en el YAML via watchdog y recarga sin restart
- [ ] **CONF-06**: El config snapshot se toma al inicio de cada job (inmutable durante procesamiento)

### Web UI (UI)

- [ ] **UI-01**: GET /ui sirve una página HTML autocontenida (Jinja2 + vanilla JS, sin dependencias externas)
- [ ] **UI-02**: La UI muestra estado del servicio en tiempo real (polling /health cada 5s)
- [ ] **UI-03**: La UI permite configurar modelo rembg, alpha matting, output size/quality/background, padding, autocrop, enhancement, y queue limits
- [ ] **UI-04**: La UI tiene botón guardar (POST /config), restaurar defaults, y ver YAML actual
- [ ] **UI-05**: La UI respeta prefers-color-scheme: dark y es mobile-friendly

### CLI (CLI)

- [ ] **CLI-01**: Comando `process` procesa una imagen individual usando el processor directamente (sin HTTP)
- [ ] **CLI-02**: Comando `batch` procesa un directorio completo secuencialmente con reporte CSV opcional
- [ ] **CLI-03**: Comando `serve` inicia el servidor HTTP (Uvicorn)
- [ ] **CLI-04**: Comando `config show` muestra la configuración activa y `config set` modifica valores
- [ ] **CLI-05**: El CLI reutiliza el processor directamente, sin duplicar lógica

### Docker (DOCK)

- [ ] **DOCK-01**: Dockerfile basado en python:3.11-slim con modelo pre-descargado en build time
- [ ] **DOCK-02**: docker-compose.yml con límites de recursos (mem_limit: 2g, cpus: 1.5)
- [ ] **DOCK-03**: HEALTHCHECK con start_period: 90s (modelo tarda en cargar)
- [ ] **DOCK-04**: Solo se monta config/ como volumen para hot-reload desde el host
- [ ] **DOCK-05**: El container arranca limpio desde cero sin dependencias externas

### Testing (TEST)

- [ ] **TEST-01**: Tests del processor: decode válido/inválido, autocrop, padding, aspect ratio, fondo blanco, tamaño output, formato WebP, enhancement, pipeline completo
- [ ] **TEST-02**: Tests del queue: job completo, 503 cuando lleno, max_concurrent respetado, timeout, estado actualizado
- [ ] **TEST-03**: Tests de API: process success + headers, campos faltantes, imagen inválida, health, config GET/POST, UI sirve HTML, status con historial

## v2 Requirements

Deferred to future release. Tracked but not in current roadmap.

### Integration

- **INTG-01**: Configuración de red Docker para integrar con stack n8n/Traefik existente
- **INTG-02**: Labels de Traefik para reverse proxy con HTTPS

### Extended Features

- **EXTF-01**: Múltiples formatos de salida (JPEG, PNG, AVIF)
- **EXTF-02**: Procesamiento batch vía API con job tracking
- **EXTF-03**: Webhooks/callbacks para notificación asíncrona de jobs completados
- **EXTF-04**: Preview de resultado en la Web UI antes de guardar config

## Out of Scope

Explicitly excluded. Documented to prevent scope creep.

| Feature | Reason |
|---------|--------|
| Autenticación / API keys | Servicio interno en VPS privado — complejidad sin reducción de riesgo real |
| GPU/CUDA | Hardware no lo tiene; onnxruntime-cpu suficiente para < 100 img/día |
| Redis/Celery/persistencia de jobs | < 100 img/día no justifica infraestructura durable; rompe principio de autonomía |
| Múltiples modelos simultáneos en RAM | 2GB RAM no soporta dos modelos; decisión de modelo es operacional |
| OAuth / login de usuarios | No hay usuarios del servicio — es una API interna |
| Mobile app | Es un microservicio backend, no un producto end-user |

## Traceability

Which phases cover which requirements. Updated during roadmap creation.

| Requirement | Phase | Status |
|-------------|-------|--------|
| PIPE-01 | Phase 1 | Pending |
| PIPE-02 | Phase 1 | Pending |
| PIPE-03 | Phase 1 | Pending |
| PIPE-04 | Phase 1 | Pending |
| PIPE-05 | Phase 1 | Pending |
| PIPE-06 | Phase 1 | Pending |
| PIPE-07 | Phase 1 | Pending |
| PIPE-08 | Phase 1 | Pending |
| PIPE-09 | Phase 1 | Pending |
| PIPE-10 | Phase 1 | Pending |
| API-01 | Phase 1 | Pending |
| API-02 | Phase 1 | Pending |
| API-03 | Phase 1 | Pending |
| API-04 | Phase 1 | Pending |
| API-05 | Phase 1 | Pending |
| API-06 | Phase 2 | Pending |
| QUEUE-01 | Phase 1 | Pending |
| QUEUE-02 | Phase 1 | Pending |
| QUEUE-03 | Phase 1 | Pending |
| QUEUE-04 | Phase 1 | Pending |
| QUEUE-05 | Phase 2 | Pending |
| CONF-01 | Phase 1 | Pending |
| CONF-02 | Phase 2 | Pending |
| CONF-03 | Phase 2 | Pending |
| CONF-04 | Phase 2 | Pending |
| CONF-05 | Phase 2 | Pending |
| CONF-06 | Phase 1 | Pending |
| UI-01 | Phase 4 | Pending |
| UI-02 | Phase 4 | Pending |
| UI-03 | Phase 4 | Pending |
| UI-04 | Phase 4 | Pending |
| UI-05 | Phase 4 | Pending |
| CLI-01 | Phase 3 | Pending |
| CLI-02 | Phase 3 | Pending |
| CLI-03 | Phase 3 | Pending |
| CLI-04 | Phase 3 | Pending |
| CLI-05 | Phase 3 | Pending |
| DOCK-01 | Phase 1 | Pending |
| DOCK-02 | Phase 1 | Pending |
| DOCK-03 | Phase 1 | Pending |
| DOCK-04 | Phase 1 | Pending |
| DOCK-05 | Phase 1 | Pending |
| TEST-01 | Phase 5 | Pending |
| TEST-02 | Phase 5 | Pending |
| TEST-03 | Phase 5 | Pending |

**Coverage:**
- v1 requirements: 45 total
- Mapped to phases: 45
- Unmapped: 0

---
*Requirements defined: 2026-03-30*
*Last updated: 2026-03-30 after roadmap creation*
