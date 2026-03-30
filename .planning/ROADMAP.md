# Roadmap: Image Standardizer Service

## Overview

El servicio parte de cero y se construye en cinco fases ordenadas por dependencia real. Primero el pipeline de procesamiento y la API minima —sin esto no hay nada que operar. Segundo, la capa de observabilidad que hace el servicio operable sin restarts. Tercero el CLI que reutiliza el processor ya probado. Cuarto la Web UI que se apoya en los endpoints de config de Fase 2. Y finalmente la consolidacion de tests e integration hardening. Cada fase entrega una capacidad verificable de forma independiente.

## Phases

**Phase Numbering:**
- Integer phases (1, 2, 3): Planned milestone work
- Decimal phases (2.1, 2.2): Urgent insertions (marcadas con INSERTED)

Decimal phases appear between their surrounding integers in numeric order.

- [ ] **Phase 1: Pipeline Core + API Basica** - Pipeline completo de procesamiento de imagenes corriendo en Docker, integrable con n8n desde el dia 1
- [ ] **Phase 2: Observabilidad + Config Operacional** - Hot-reload de YAML sin restart, metricas de estado y config via API
- [ ] **Phase 3: CLI + Batch Offline** - Comandos process, batch, serve y config via Typer reutilizando el processor directamente
- [ ] **Phase 4: Web UI de Configuracion** - Interfaz visual autocontenida para configurar y monitorear el servicio desde el browser
- [ ] **Phase 5: Tests + Hardening** - Suite completa de tests unitarios e integracion, cobertura de edge cases documentados

## Phase Details

### Phase 1: Pipeline Core + API Basica
**Goal**: El servicio acepta una imagen y devuelve un WebP estandarizado 800x800 con fondo blanco, corriendo en Docker con el modelo pre-descargado y listo para integrarse con n8n
**Depends on**: Nothing (first phase)
**Requirements**: PIPE-01, PIPE-02, PIPE-03, PIPE-04, PIPE-05, PIPE-06, PIPE-07, PIPE-08, PIPE-09, PIPE-10, API-01, API-02, API-03, API-04, API-05, QUEUE-01, QUEUE-02, QUEUE-03, QUEUE-04, CONF-01, CONF-06, DOCK-01, DOCK-02, DOCK-03, DOCK-04, DOCK-05
**Success Criteria** (what must be TRUE):
  1. Se puede hacer POST /process con una imagen JPG/PNG/WebP y recibir de vuelta un WebP de exactamente 800x800 pixeles con fondo blanco y el producto centrado
  2. GET /health responde con status del servicio, modelo cargado y uptime — incluso mientras se procesa una imagen en paralelo
  3. `docker compose up` levanta el servicio sin descargar nada adicional (modelo birefnet-lite embebido en la imagen)
  4. Una segunda request mientras hay una en proceso recibe 503 si la cola esta llena, o espera su turno si hay capacidad
  5. La configuracion se lee de settings.yaml al startup y el snapshot del config es inmutable durante cada job
**Plans:** 2/5 plans executed

Plans:
- [x] 01-01-PLAN.md — Scaffold proyecto + config + models + test infrastructure
- [x] 01-02-PLAN.md — Pipeline de procesamiento completo (7 steps)
- [x] 01-03-PLAN.md — Queue manager con asyncio.Semaphore
- [ ] 01-04-PLAN.md — FastAPI app + endpoints HTTP + tests integracion
- [ ] 01-05-PLAN.md — Docker (Dockerfile + compose + modelo pre-descargado)

### Phase 2: Observabilidad + Config Operacional
**Goal**: El operador puede cambiar parametros del servicio (modelo, calidad, padding, limites de cola) sin reiniciar el container, y puede consultar metricas e historial de jobs via API
**Depends on**: Phase 1
**Requirements**: CONF-02, CONF-03, CONF-04, CONF-05, API-06, QUEUE-05
**Success Criteria** (what must be TRUE):
  1. Editar settings.yaml en el host recarga la configuracion en el container activo en segundos, sin downtime
  2. POST /config con un JSON parcial actualiza solo los campos indicados y persiste el YAML en disco
  3. Si se cambia el modelo rembg via POST /config, la sesion ONNX se recrea despues de que termine el job activo (sin interrumpir requests en vuelo)
  4. GET /status retorna total procesados, errores, tiempo promedio e historial de los ultimos 50 jobs
**Plans**: TBD

### Phase 3: CLI + Batch Offline
**Goal**: El operador puede procesar imagenes individuales o carpetas completas desde la terminal sin levantar el servidor HTTP, reutilizando el mismo pipeline ya probado
**Depends on**: Phase 1
**Requirements**: CLI-01, CLI-02, CLI-03, CLI-04, CLI-05
**Success Criteria** (what must be TRUE):
  1. `imgproc process foto.jpg` produce un WebP identico al que devuelve la API para la misma imagen y configuracion
  2. `imgproc batch ./fotos/ --csv reporte.csv` procesa todas las imagenes del directorio y genera el reporte con resultados por archivo
  3. `imgproc serve` inicia Uvicorn con la misma configuracion que docker-compose
  4. `imgproc config show` muestra la configuracion activa; `imgproc config set output.size 1200` la modifica
**Plans**: TBD

### Phase 4: Web UI de Configuracion
**Goal**: El operador puede ver el estado del servicio y modificar su configuracion desde un browser, sin tocar la terminal ni editar YAML a mano
**Depends on**: Phase 2
**Requirements**: UI-01, UI-02, UI-03, UI-04, UI-05
**Success Criteria** (what must be TRUE):
  1. GET /ui sirve una pagina HTML completa que funciona sin internet y sin dependencias externas (CSS y JS inline)
  2. La UI muestra estado del servicio (activo/inactivo, jobs en cola, modelo cargado) que se actualiza cada 5 segundos sin recargar la pagina
  3. Cambiar el modelo rembg, el padding o la calidad WebP en la UI y presionar Guardar persiste el cambio via POST /config
  4. La UI se ve correctamente en modo oscuro (prefers-color-scheme: dark) y en un telefono movil
**UI hint**: yes
**Plans**: TBD

### Phase 5: Tests + Hardening
**Goal**: El comportamiento del servicio bajo condiciones normales y edge cases esta verificado por tests automatizados que se pueden correr en CI
**Depends on**: Phase 4
**Requirements**: TEST-01, TEST-02, TEST-03
**Success Criteria** (what must be TRUE):
  1. `pytest` pasa en verde cubriendo: decode de todos los formatos, autocrop, padding, aspect ratio, fondo blanco, tamano output, enhancement, pipeline completo
  2. Los tests de queue verifican: job completo exitoso, 503 cuando la cola esta llena, max_concurrent respetado, timeout con 504, estado actualizado correctamente
  3. Los tests de API verifican: process success con todos los headers, campos faltantes, imagen invalida, health, config GET/POST, UI sirve HTML valido, status con historial
**Plans**: TBD

## Progress

**Execution Order:**
Phases execute in numeric order: 1 → 2 → 3 → 4 → 5

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 1. Pipeline Core + API Basica | 2/5 | In Progress|  |
| 2. Observabilidad + Config Operacional | 0/TBD | Not started | - |
| 3. CLI + Batch Offline | 0/TBD | Not started | - |
| 4. Web UI de Configuracion | 0/TBD | Not started | - |
| 5. Tests + Hardening | 0/TBD | Not started | - |
