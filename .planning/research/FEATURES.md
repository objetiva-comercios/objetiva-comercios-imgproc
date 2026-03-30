# Feature Research

**Domain:** Image standardization microservice — product catalog images (ecommerce)
**Researched:** 2026-03-30
**Confidence:** HIGH (stack ya definido en PROJECT.md; features validadas contra servicios comparables como remove.bg, Photoroom, ZYNG AI, ProductShots.ai)

---

## Feature Landscape

### Table Stakes (Usuarios esperan esto)

Estas son las features que cualquier servicio de procesamiento de imágenes de catálogo necesita. Si faltan, el servicio no cumple su propósito.

| Feature | Por qué se espera | Complejidad | Notas de implementación |
|---------|-------------------|-------------|-------------------------|
| Remoción de fondo automática | El caso de uso primario de toda herramienta de catálogo. Sin esto no hay servicio | HIGH | rembg + birefnet-lite; sesión global única, nunca por request — crítico para RAM |
| Fondo blanco estándar | Estándar de facto en catálogos (Amazon, Mercado Libre, GS1). Sin fondo blanco las imágenes no son "de catálogo" | LOW | Composite sobre canvas RGB blanco post-rembg |
| Tamaño de salida fijo (800x800) | Los catálogos requieren dimensiones consistentes para grillas de productos | LOW | Pillow resize con LANCZOS; mantener aspect ratio con padding |
| Producto centrado con padding | Imágenes con producto pegado al borde generan inconsistencia visual en la grilla | LOW | Autocrop del alpha mask → centrar → padding configurable |
| Salida WebP | Formato moderno obligatorio: -30-50% peso vs JPEG a calidad equivalente, soportado en todos los browsers modernos | LOW | Pillow save WebP con calidad configurable |
| Endpoint POST /process | Interface mínima para integraciones: recibir imagen → devolver imagen procesada | MEDIUM | FastAPI, multipart/form-data o base64; devolver binary WebP |
| Endpoint GET /health | Cualquier servicio en contenedor necesita health check para Docker/orquestadores | LOW | Retornar 200 + estado del modelo (cargado/no) |
| Dockerfile funcional | El servicio debe correr contenido, sin dependencias externas en runtime | MEDIUM | Modelo pre-descargado en build time — evitar 1-3 min de delay en primer request |
| CLI para procesamiento batch | Los usuarios procesan lotes de imágenes fuera de hora; no vía API | MEDIUM | Typer: `process`, `batch`, `serve` |
| Configuración vía YAML | Cambiar padding, calidad, tamaño sin rebuildar el contenedor | LOW | watchdog para hot-reload; evitar restart del container |

### Differentiators (Ventaja competitiva)

Features que elevan el servicio sobre un wrapper básico de rembg.

| Feature | Propuesta de valor | Complejidad | Notas de implementación |
|---------|--------------------|-------------|-------------------------|
| Hot-reload de configuración | Cambiar padding/calidad/tamaño sin reiniciar el contenedor — crítico en producción sin downtime | MEDIUM | watchdog observa config.yaml; recarga parámetros sin afectar requests en curso |
| Web UI de configuración | Ajustar parámetros sin tocar YAML ni CLI; reduce errores de ops no-técnicos | MEDIUM | Jinja2 + vanilla JS; un solo HTML autocontenido; GET /config + POST /config |
| Cola in-memory con límite de concurrencia | Previene OOM en hardware limitado (2GB RAM); garantiza procesamiento serializado sin infraestructura externa | MEDIUM | asyncio.Semaphore(max_concurrent=1) + asyncio.Queue; retorna 202 con job_id o procesa síncronamente |
| Modelo pre-cargado en startup | Elimina el cold start de 1-3 minutos que tienen los servicios que cargan el modelo por request | MEDIUM | Sesión rembg inicializada en lifespan de FastAPI; verificada en GET /health |
| Endpoint GET /status (procesamiento) | Feedback del estado del servicio: queue length, jobs procesados, RAM usada — útil para debugging operacional | LOW | Métricas en memoria: jobs_total, jobs_failed, queue_size, model_loaded |
| Pipeline configurable (orden fijo, parámetros variables) | El pipeline decode→rembg→autocrop→scale→composite→enhance→encode es fijo pero cada paso tiene parámetros ajustables | MEDIUM | Config schema: output_size, padding_pct, bg_color, webp_quality, enhance_sharpness |
| Límites de recursos explícitos en docker-compose | El contenedor no puede consumir RAM ilimitada en un VPS compartido; límites declarativos evitan OOM del host | LOW | deploy.resources.limits: memory=2g, cpus=1.5 |

### Anti-Features (No construir)

Features que parecen buenas pero crean problemas desproporcionados al valor que aportan en este contexto.

| Feature | Por qué se pide | Por qué es problemática | Alternativa |
|---------|-----------------|-------------------------|-------------|
| Autenticación / API keys | "Seguridad" | Servicio interno en VPS privado — agrega complejidad sin reducir riesgo real; la integración n8n se complica | Aislar el servicio con firewall/red Docker privada |
| Múltiples formatos de salida (JPEG, PNG, AVIF) | Flexibilidad | Agrega branching al pipeline, aumenta superficie de tests, la mayoría de casos de catálogo solo necesita WebP | WebP cubre el 99% del caso de uso; diferir otros formatos a v2 con validación real |
| Persistencia de jobs (Redis/DB) | Trazabilidad | < 100 imágenes/día no justifica infraestructura de cola durable; agrega dependencias externas que rompen el principio de ser 100% autónomo | Status en memoria suficiente para el volumen; logs en stdout para trazabilidad |
| GPU/CUDA | Performance | Hardware no lo tiene; la imagen Docker se vuelve 10x más grande; birefnet-lite en CPU es suficiente para < 100 img/día | onnxruntime-cpu — adecuado para el volumen real del servicio |
| Procesamiento batch vía API | Conveniencia | Complica el manejo de timeouts HTTP, errores parciales y concurrencia; la API síncrona es más predecible | CLI `batch` command para lotes; la API procesa de a una imagen |
| Preview en tiempo real en Web UI | UX mejorada | Requiere JavaScript complejo + estado en frontend; el canal de integración es programático, no visual | La Web UI es de configuración, no de procesamiento; el CLI cubre el caso de preview manual |
| Webhooks / callbacks asíncronos | Integración "moderna" | El pipeline n8n que consume el servicio puede esperar una respuesta síncrona; los webhooks complican la integración inicial | Response síncrona con timeout razonable; si el volumen escala, esto se reconsideraría |
| Múltiples modelos de remoción seleccionables por request | Flexibilidad de calidad | Cargar múltiples modelos en 2GB de RAM causa OOM; la decisión de modelo es operacional, no por imagen | Un modelo configurable vía YAML; cambiar requiere restart (aceptable para cambio operacional) |

---

## Feature Dependencies

```
[Remoción de fondo (rembg)]
    └──requiere──> [Modelo pre-cargado en startup]
                       └──requiere──> [Modelo en Docker image (build time)]

[Autocrop]
    └──requiere──> [Remoción de fondo] (necesita alpha mask del objeto)

[Composite sobre fondo blanco]
    └──requiere──> [Autocrop] (necesita objeto centrado y con padding)
    └──requiere──> [Scale a 800x800] (necesita tamaño target)

[Encode WebP]
    └──requiere──> [Composite sobre fondo blanco] (input debe ser RGB sin alpha)

[Cola in-memory / Semaphore]
    └──protege──> [Remoción de fondo] (operación CPU-bound que consume la RAM del modelo)

[Hot-reload de config]
    └──requiere──> [Configuración YAML] (el archivo que se observa)
    └──requiere──> [watchdog] (dependencia Python)

[Web UI de configuración]
    └──requiere──> [Endpoint GET /config] (leer config actual)
    └──requiere──> [Endpoint POST /config] (escribir config nueva)
    └──enhances──> [Hot-reload de config] (la UI triggerea el reload)

[CLI batch]
    └──requiere──> [Pipeline de procesamiento] (reutiliza el mismo pipeline que la API)
    └──independiente de──> [API HTTP] (puede correr sin servidor activo)

[GET /status]
    └──enhances──> [Cola in-memory] (expone métricas de la cola)
    └──enhances──> [Modelo pre-cargado] (reporta estado del modelo)
```

### Notas de dependencia

- **Modelo pre-cargado requiere Dockerfile correcto:** Si el modelo no está en la imagen, el primer request espera 1-3 minutos — rompe la experiencia de health check del orquestador.
- **Cola in-memory protege al pipeline:** Sin el semáforo, dos requests simultáneos con birefnet-lite cargan el modelo dos veces y causan OOM en 2GB RAM.
- **CLI es independiente de la API:** Esto es una ventaja — permite procesar lotes sin levantar el servidor HTTP, útil en contextos de CI o scripts de migración.
- **Web UI depende de endpoints /config:** La UI no hace nada si la API no está corriendo. No hay modo "offline" de la UI.

---

## MVP Definition

### Launch With (v1)

El mínimo para que el servicio reemplace al contenedor rembg standalone y sea usable en producción.

- [ ] Pipeline de procesamiento completo (decode → rembg → autocrop → scale → composite → enhance → encode WebP) — sin esto no hay servicio
- [ ] Endpoint POST /process — interface de integración mínima para n8n
- [ ] Endpoint GET /health — requerido por Docker y cualquier orquestador
- [ ] Modelo birefnet-lite pre-descargado en imagen Docker — evita cold start operacional
- [ ] Cola in-memory con asyncio.Semaphore(max_concurrent=1) — previene OOM en 2GB RAM
- [ ] Configuración YAML con valores default sensatos — permite ajuste sin rebuild
- [ ] Dockerfile + docker-compose con límites de recursos — deployment reproducible
- [ ] Tests unitarios del pipeline y tests de integración de la API — verificabilidad del comportamiento

### Add After Validation (v1.x)

Una vez que el core funciona y el servicio está en producción.

- [ ] Web UI de configuración — cuando ops necesite ajustar parámetros sin CLI
- [ ] Hot-reload de configuración (watchdog) — cuando cambiar config requiera restart y sea incómodo
- [ ] CLI completo (process, batch, serve, config) — cuando los lotes manuales sean frecuentes
- [ ] Endpoint GET /status con métricas — cuando sea necesario hacer debugging operacional

### Future Consideration (v2+)

Features a diferir hasta validar el volumen real y los casos de uso.

- [ ] Múltiples formatos de salida (JPEG, PNG) — solo si un consumidor real lo pide con justificación
- [ ] Procesamiento batch vía API — solo si el volumen supera los 1000 imágenes/día y el CLI es insuficiente
- [ ] Webhooks / callbacks — solo si n8n requiere procesamiento asíncrono real
- [ ] Cambio de modelo por request — solo si birefnet-lite demuestra ser insuficiente en calidad

---

## Feature Prioritization Matrix

| Feature | Valor para usuario | Costo de implementación | Prioridad |
|---------|--------------------|-------------------------|-----------|
| Pipeline completo (rembg → WebP) | HIGH | HIGH | P1 |
| Modelo pre-cargado en Docker | HIGH | MEDIUM | P1 |
| POST /process endpoint | HIGH | MEDIUM | P1 |
| Cola in-memory (semáforo) | HIGH | LOW | P1 |
| GET /health | HIGH | LOW | P1 |
| Configuración YAML | MEDIUM | LOW | P1 |
| docker-compose con límites | HIGH | LOW | P1 |
| Tests unitarios e integración | HIGH | MEDIUM | P1 |
| Hot-reload de config (watchdog) | MEDIUM | MEDIUM | P2 |
| Web UI de configuración | MEDIUM | MEDIUM | P2 |
| CLI (process, batch, serve) | MEDIUM | MEDIUM | P2 |
| GET /status con métricas | LOW | LOW | P2 |
| Múltiples formatos de salida | LOW | MEDIUM | P3 |
| Autenticación | LOW | MEDIUM | P3 |
| GPU/CUDA | LOW | HIGH | P3 |

**Priority key:**
- P1: Must have para v1 (MVP)
- P2: Should have, agregar en v1.x post-validación
- P3: Nice to have, diferir a v2 o no construir

---

## Competitor Feature Analysis

Análisis de servicios comparables para validar qué es table stakes y qué es diferenciador.

| Feature | remove.bg | Photoroom API | ProductShots.ai / ZYNG AI | Este servicio |
|---------|-----------|---------------|---------------------------|---------------|
| Remoción de fondo | Si (cloud) | Si (cloud, HD) | Si (cloud, batch) | Si (local, birefnet-lite) |
| Fondo blanco | Si | Si (configurable) | Si (estándar catálogo) | Si (fijo blanco) |
| Tamaño estandarizado | No (devuelve original) | Si (output_size param) | Si (800x800, etc.) | Si (800x800 fijo, configurable) |
| Padding / centrado | No | Si (uncertainty score ayuda) | Si | Si (autocrop + padding configurable) |
| Salida WebP | No (PNG) | No (PNG/JPEG) | Depende del plan | Si (fijo WebP) |
| Procesamiento batch | Si (via API loops) | Si | Si (core feature) | Si (CLI solamente en v1) |
| Self-hosted / sin dependencias externas | No | No | No | Si (100% local, Docker) |
| Configuración vía UI | No | No (solo API params) | Si (dashboard) | Si (Web UI Jinja2) |
| Hot-reload de config | N/A | N/A | N/A | Si (watchdog) |
| Límite de concurrencia explícito | N/A (cloud escala) | N/A | N/A | Si (semáforo, crítico para RAM) |
| Privacidad total (imágenes no salen del server) | No (procesa en cloud) | No (procesa en cloud) | No (procesa en cloud) | Si (todo local) |
| Costo por imagen | $0.03-0.10 USD | $0.01-0.05 USD | Variable (SaaS) | $0 (infraestructura propia) |

**Conclusión competitiva:** La diferenciación clave de este servicio no está en la calidad del modelo (los cloud APIs tienen mejor calidad con hardware especializado) sino en **self-hosted, sin costo por imagen, privacidad total, y configuración sin dependencias externas**. Para el caso de uso de Objetiva Comercios (< 100 img/día, VPS propio, integración n8n interna), esta es la propuesta correcta.

---

## Sources

- [ProductShots.ai — Catalog Image Standardization](https://www.productshots.ai/catalog-automations/standardize) — features de tabla stakes en servicios de catálogo
- [ZYNG AI — Batch Image Standardization](https://www.zyngai.com/Usecase_28_catalogstandard) — features diferenciadores en batch processing
- [Photoroom API Documentation](https://docs.photoroom.com) — referencia de features en API de background removal productivo
- [remove.bg API](https://www.remove.bg/api) — API de referencia en el dominio
- [BiRefNet vs rembg vs U2Net comparison](https://dev.to/om_prakash_3311f8a4576605/birefnet-vs-rembg-vs-u2net-which-background-removal-model-actually-works-in-production-4830) — comparación de modelos en producción
- [rembg GitHub](https://github.com/danielgatis/rembg) — features del tooling base
- [FastAPI concurrency patterns 2025](https://talent500.com/blog/fastapi-microservices-python-api-design-patterns-2025/) — patrones de concurrencia para servicios de procesamiento
- [GS1 Product Image Specification Standard](https://www.gs1.org/standards/gs1-product-image-specification-standard/current-standard) — estándares de imagen de catálogo
- [Ecommerce product image optimization guide 2025](https://www.squareshot.com/post/product-image-optimisation-guide-for-e-commerce-success) — estándares de catálogo y WebP
- [Scalable Image Processing with Microservices](https://medium.com/@API4AI/microservices-in-ai-building-scalable-image-processing-pipelines-1e37a774b9a0) — patrones de arquitectura para procesamiento de imágenes

---

*Feature research for: Image standardization microservice — product catalog (Objetiva Comercios)*
*Researched: 2026-03-30*
