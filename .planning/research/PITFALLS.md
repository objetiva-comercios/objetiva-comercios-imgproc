# Pitfalls Research

**Domain:** Image standardization microservice — rembg/Pillow/FastAPI/ONNX/Docker
**Researched:** 2026-03-30
**Confidence:** HIGH (ONNX/rembg memory issues, FastAPI event loop, Pillow leaks) | MEDIUM (watchdog config reload, Docker cgroup threading)

---

## Critical Pitfalls

### Pitfall 1: rembg Session Creada por Request (No Global)

**What goes wrong:**
Si se instancia `new_session()` de rembg en cada request en lugar de una sola vez al startup, la RAM crece indefinidamente. ONNX Runtime no libera la memoria del modelo correctamente al destruir sesiones en Python. En produccion con carga sostenida, se reportaron consumos de >137 GB hasta agotar la RAM del host.

**Why it happens:**
El patrón "sin estado" convierte a los desarrolladores en instanciar todo en la función del endpoint, incluyendo la sesión ONNX. La documentación de rembg no advierte explícitamente sobre esto. La llamada `remove(image)` acepta un argumento `session=` opcional que muchos ignoran.

**How to avoid:**
Inicializar la sesión exactamente una vez en el startup de la aplicación usando el `lifespan` de FastAPI, guardarla en el estado de la app (`app.state.rembg_session`), y pasarla explícitamente en cada llamada:
```python
# CORRECTO
session = new_session("birefnet-lite")
result = remove(image_bytes, session=session)

# INCORRECTO — nueva sesión por request
result = remove(image_bytes)  # descarga el modelo si no está cacheado
```

**Warning signs:**
- `docker stats` muestra RAM del container creciendo lentamente y nunca bajando
- Primer request tarda 3-10s, los siguientes tardan lo mismo (no hay warmup)
- Logs de ONNX Runtime mostrando "Loading model..." en requests subsiguientes

**Phase to address:**
Fase de implementación del pipeline — debe establecerse en el diseño del startup antes de escribir el endpoint `/process`.

---

### Pitfall 2: Bloqueo del Event Loop con Trabajo CPU-Bound

**What goes wrong:**
`rembg.remove()` y las operaciones de Pillow (resize, composite, enhance) son CPU-bound puras. Si se llaman directamente dentro de un endpoint `async def`, bloquean el event loop completo de asyncio. Durante el tiempo que dura la inferencia (2-8s en CPU), todos los demás requests — incluyendo `/health` — quedan congelados sin respuesta.

**Why it happens:**
Malentendido común: `async def` no hace mágicamente concurrente al código síncrono. La coroutine suspende en `await` solamente. Si no hay `await`, el event loop no puede cambiar de tarea. FastAPI corre en un event loop single-threaded con uvicorn por defecto.

**How to avoid:**
Envolver TODO el pipeline de procesamiento en `asyncio.to_thread()`:
```python
# CORRECTO
result = await asyncio.to_thread(process_image_sync, image_bytes)

# INCORRECTO — bloquea el event loop
@app.post("/process")
async def process(file: UploadFile):
    result = remove(await file.read(), session=app.state.session)  # BLOQUEA
```
El `asyncio.Semaphore(max_concurrent=1)` debe adquirirse ANTES de despachar a `to_thread`, no dentro del thread.

**Warning signs:**
- `GET /health` demora varios segundos cuando hay un request de procesamiento activo
- Logs de uvicorn muestran requests en cola acumulándose
- `asyncio.get_event_loop().time()` en middleware muestra latencias anormales

**Phase to address:**
Fase de implementación del pipeline y la API — diseñar la integración de `asyncio.to_thread` desde el primer endpoint, no como refactor posterior.

---

### Pitfall 3: ONNX Runtime Ignorando Límites de CPU del Container (intra_op_num_threads)

**What goes wrong:**
ONNX Runtime por defecto intenta crear tantos threads INTRA como cores físicos detecte en el host (no en el container). Dentro de Docker con `--cpus=1.5`, el runtime puede intentar crear 8+ threads (del host de 8 cores), lo que genera:
1. Contención masiva de threads sobre 1.5 cores reales
2. Llamadas a `pthread_setaffinity_np()` fallando con EINVAL en algunos hosts Linux con cgroups v1
3. CPU throttling del container mucho más agresivo de lo esperado

**Why it happens:**
ONNX Runtime lee la topología de CPU del host via `/proc/cpuinfo` o `sysconf()`, que no respeta los límites de cgroup. Esta es una limitación documentada del runtime.

**How to avoid:**
Configurar explícitamente `intra_op_num_threads` al crear la sesión rembg, y también setear variables de entorno:
```python
# En SessionOptions al crear la sesión ONNX
opts = onnxruntime.SessionOptions()
opts.intra_op_num_threads = 2  # ≤ CPU cores asignados al container
```
En Dockerfile o docker-compose:
```yaml
environment:
  - OMP_NUM_THREADS=2
  - OPENBLAS_NUM_THREADS=2
```

**Warning signs:**
- `docker stats` muestra CPU% constantemente por encima del límite configurado durante inferencia
- `htop` en el host muestra el container usando cores que no le corresponden
- Timeouts erráticos en requests que normalmente completan

**Phase to address:**
Fase de Dockerización — configurar en el mismo paso que se define `deploy.resources` en docker-compose.

---

### Pitfall 4: Pillow Images Sin Cerrar en el Pipeline (Memory Accumulation)

**What goes wrong:**
Cada `Image.open()`, `Image.new()`, y operación de composición en Pillow crea objetos que tienen referencias a buffers C subyacentes. Python's GC no garantiza liberación determinística de estos buffers. En un servicio de larga duración procesando decenas de imágenes, la RAM crece ~100-200MB por cada 300K imágenes procesadas, pero incluso a escala pequeña, un leak por request acumula lentamente hasta el límite del container.

**Why it happens:**
`Image.close()` destruye el core C del objeto pero Pillow emite una advertencia de que el context manager cierra el archivo pero no necesariamente destruye el core. Además, referencias circulares o variables locales en funciones de pipeline mantienen las imágenes vivas hasta que el GC decide liberar.

**How to avoid:**
Usar context managers (`with`) para cada imagen abierta, y llamar explícitamente `.close()` en imágenes intermedias creadas con `Image.new()`:
```python
# CORRECTO
with Image.open(BytesIO(image_bytes)) as img:
    img_rgb = img.convert("RGB")
    # procesamiento...
    img_rgb.close()

# INCORRECTO — leak potencial
img = Image.open(BytesIO(image_bytes))
result = process(img)
# img nunca se cierra explícitamente
```

**Warning signs:**
- `docker stats` muestra crecimiento lento pero continuo de RAM incluso con requests normales
- El container se acerca al límite de 2GB después de horas de operación sin ningún request anormal
- `tracemalloc` muestra acumulación en `PIL/Image.py`

**Phase to address:**
Fase de implementación del pipeline — establecer el patrón de context manager como estándar en el código desde el inicio.

---

### Pitfall 5: OOMKill del Container por Pico de RAM Durante Inferencia

**What goes wrong:**
Un container configurado con `mem_limit: 2g` puede ser killed por el OOM killer del kernel incluso si el uso promedio es de ~800MB. La inferencia de birefnet-lite carga el modelo (~300MB) más los buffers de la imagen de entrada (~50-100MB a 1024x1024 RGBA float32) más los buffers intermedios de ONNX (~200-400MB). Un pico momentáneo de 2.2-2.5GB durante la inferencia puede superar el límite.

**Why it happens:**
Python y ONNX Runtime no respetan proactivamente los límites de cgroup. Python lee la memoria total del host para sus heurísticas de allocator. El OOM killer del kernel actúa sin aviso cuando el cgroup excede su límite, resultando en exit code 137 sin stack trace ni log de error.

**How to avoid:**
1. Setear el límite de RAM con margen real: si la app usa ~1.2GB en pico, setear `mem_limit: 1.8g` o `mem_limit: 2g` con `memswap_limit: 2g` (sin swap extra).
2. Configurar `MALLOC_TRIM_THRESHOLD_=65536` para que glibc devuelva memoria al OS más agresivamente.
3. Monitorear con `docker stats` durante pruebas de carga antes de definir el límite final.
4. El `max_concurrent=1` del Semaphore es crítico — dos inferencias simultáneas duplicarían el pico.

**Warning signs:**
- Container aparece como "Exited (137)" sin mensaje de error en los logs
- `docker inspect` muestra `"OOMKilled": true` en el State del container
- RAM del container llega a >90% del límite durante procesamiento de imágenes grandes

**Phase to address:**
Fase de Dockerización — testear con imágenes de tamaño máximo real antes de fijar límites de recursos.

---

### Pitfall 6: EXIF Orientation Ignorada — Productos Rotados en el Catálogo

**What goes wrong:**
Imágenes tomadas con cámaras de smartphones tienen orientación codificada en metadatos EXIF (tag 274). Pillow NO aplica esta rotación automáticamente al abrir la imagen. El pipeline recibe una imagen "de costado" (rotada 90°), rembg remueve el fondo correctamente pero el producto aparece rotado en el output final del catálogo.

**Why it happens:**
Es un comportamiento deliberado de Pillow por compatibilidad. La mayoría de los desarrolladores no están al tanto de que los datos de pixel y la orientación EXIF son independientes en el formato JPEG.

**How to avoid:**
Aplicar `ImageOps.exif_transpose(img)` como primer paso del pipeline, inmediatamente después de abrir la imagen y antes de cualquier procesamiento:
```python
from PIL import Image, ImageOps

with Image.open(BytesIO(image_bytes)) as img:
    img = ImageOps.exif_transpose(img)  # PRIMER PASO SIEMPRE
    # resto del pipeline...
```

**Warning signs:**
- QA manual con fotos de celular muestra productos rotados en el output
- Imágenes JPEG de cámara funcionan mal, PNG y WebP funcionan bien (los PNG raramente tienen EXIF de orientación)

**Phase to address:**
Fase de implementación del pipeline — agregar como step explícito en la spec del pipeline antes de codificar.

---

### Pitfall 7: Modo de Color Inesperado Crashea o Corrompe el Pipeline

**What goes wrong:**
Los inputs pueden llegar como CMYK (fotos de impresión profesional), P (paleta GIF), LA (grayscale con alpha), o incluso I (enteros de 32 bits). Cualquier operación de Pillow que asuma RGB o RGBA fallará silenciosamente o lanzará una excepción críptica. El peor caso: el composite final produce colores incorrectos si se hace sobre una imagen CMYK convertida a RGB sin gamma correction.

**Why it happens:**
El pipeline de rembg acepta bytes y hace su propia conversión interna, pero las operaciones de Pillow posteriores (autocrop, composite, enhance) se realizan en el modo de color que tenga la imagen resultado de rembg, que siempre es RGBA. El problema real ocurre en la imagen original antes de pasarla a rembg.

**How to avoid:**
Normalizar el modo de color al principio del pipeline, después de exif_transpose:
```python
img = ImageOps.exif_transpose(img)
if img.mode not in ("RGB", "RGBA"):
    img = img.convert("RGBA" if "transparency" in img.info else "RGB")
```
El output final debe convertirse explícitamente a RGB antes de guardar como WebP (WebP puede aceptar RGBA pero el proyecto requiere fondo blanco sin alpha):
```python
final = Image.new("RGB", (800, 800), (255, 255, 255))
final.paste(processed, mask=processed.split()[3])  # mask = alpha channel
```

**Warning signs:**
- Excepciones `ValueError: image has wrong mode` o `cannot convert` en producción
- Imágenes de proveedores de impresión o stock photos causan errores que las fotos de celular no causan
- Output WebP muestra fondo negro en lugar de blanco (RGBA guardado sin composite con fondo blanco)

**Phase to address:**
Fase de implementación del pipeline — cubrir con tests unitarios los modos CMYK, P, L, LA.

---

### Pitfall 8: birefnet-lite Requiere Input a 1024x1024 — No Cualquier Tamaño

**What goes wrong:**
A diferencia de modelos más simples, birefnet-lite fue entrenado y optimizado para inputs de exactamente 1024x1024 pixels. Pasar imágenes en su tamaño original sin redimensionar primero produce máscaras de peor calidad o errores de forma en la inferencia ONNX. El post-procesamiento en ONNX puede propagar silenciosamente tensores de forma incorrecta sin lanzar excepción.

**Why it happens:**
rembg internamente redimensiona la imagen antes de la inferencia, pero si la imagen original es muy pequeña (ej: 100x100) o tiene aspect ratio extremo (ej: 2000x100), la máscara resultante puede tener artefactos que rembg no puede suavizar correctamente durante el unpad/resize de vuelta.

**How to avoid:**
No depender únicamente de rembg para el preprocessing interno. Validar dimensiones mínimas de input (recomendado: mínimo 200x200 pixels) y aspect ratio razonable antes de enviar al pipeline. Documentar las limitaciones de calidad en el endpoint.

**Warning signs:**
- Imágenes muy pequeñas o panorámicas producen máscaras con "halos" o bordes dentados
- El autocrop posterior no encuentra contenido útil (bbox demasiado pequeña o vacía)

**Phase to address:**
Fase de implementación del pipeline — agregar validación de input en el endpoint antes de encolar.

---

### Pitfall 9: Modelo No Pre-descargado en Build Time — Delay Fatal en Primer Request

**What goes wrong:**
Si el modelo birefnet-lite no está embebido en la imagen Docker, rembg lo descarga de Hugging Face Hub en el primer `new_session()`. La descarga tarda 1-3 minutos en una conexión normal, pero en el VPS con acceso lento a HuggingFace o sin internet, el container startup falla silenciosamente o el primer request al `/process` da timeout.

**Why it happens:**
El comportamiento default de rembg es lazy-download al primer uso. En desarrollo local esto es conveniente. En producción Docker es un anti-patrón: la imagen no es autónoma, requiere conectividad externa en runtime, y el startup es no-determinístico.

**How to avoid:**
En el Dockerfile, forzar la descarga del modelo durante el build con un script Python:
```dockerfile
RUN python -c "from rembg import new_session; new_session('birefnet-lite')"
```
Esto embebe el modelo (~300MB) en la imagen Docker. La imagen pesa más pero es 100% autónoma. Verificar que `~/.u2net/` o `~/.cache/` esté correctamente ubicado en la layer del build.

**Warning signs:**
- El container demora 2-3 minutos en responder al primer `/process` después de `docker run`
- `/health` responde 200 pero el primer request de proceso falla por timeout
- `docker build` no muestra ningún download de modelo durante la construcción

**Phase to address:**
Fase de Dockerización — el Dockerfile debe incluir el pre-download como step de build explícito y verificado.

---

### Pitfall 10: watchdog + YAML Config Reload Sin Lock — Race Condition

**What goes wrong:**
Si el handler de watchdog modifica el objeto de configuración global mientras un thread de procesamiento (vía `asyncio.to_thread`) está leyendo los valores de config (umbral de padding, tamaño de output, etc.), se produce una race condition. Los efectos son sutiles: una imagen se procesa con config a medio actualizar, produciendo output con dimensiones o padding incorrectos. En el peor caso, un dict parcialmente modificado lanza `KeyError` o `TypeError`.

**Why it happens:**
watchdog dispara el callback del file observer en un thread separado (el thread de watchdog). `asyncio.to_thread` corre el pipeline en otro thread del thread pool de asyncio. Ambos acceden al mismo objeto de configuración sin sincronización. El GIL de Python protege operaciones atómicas pero no operaciones compuestas como actualizar múltiples campos de un dict.

**How to avoid:**
Usar `threading.RLock` para envolver las lecturas y escrituras del objeto de config. Alternativamente, usar el patrón de config inmutable con reemplazo atómico:
```python
import threading
_config_lock = threading.RLock()

def reload_config():
    new_config = load_yaml("config.yaml")
    with _config_lock:
        app.state.config = new_config  # reemplazo atómico del objeto entero

def get_config():
    with _config_lock:
        return app.state.config  # copia de referencia bajo lock
```

**Warning signs:**
- Outputs ocasionales con dimensiones incorrectas (ej: 800x400 en lugar de 800x800)
- `KeyError` esporádico en el pipeline durante un config reload
- El bug sólo aparece cuando se modifica el YAML mientras hay un request en curso

**Phase to address:**
Fase de hot-reload de configuración — diseñar el mecanismo de lock antes de implementar el watchdog handler.

---

## Technical Debt Patterns

| Shortcut | Immediate Benefit | Long-term Cost | When Acceptable |
|----------|-------------------|----------------|-----------------|
| `Image.MAX_IMAGE_PIXELS = None` | Elimina DecompressionBombError en imágenes grandes | Servicio vulnerable a DoS con imágenes maliciosas | Nunca — setear un límite razonable (ej: 50MP) |
| Sesión rembg creada en cada request | Código más simple, sin estado global | Memory leak garantizado, OOMKill en producción | Nunca |
| `async def endpoint` sin `asyncio.to_thread` | Menos código boilerplate | Event loop bloqueado, `/health` no responde durante inferencia | Nunca en endpoints que llaman a rembg/Pillow |
| Sin validación de modo de color en input | Pipeline más simple | Crash con imágenes CMYK o P de clientes reales | Nunca — agregar en MVP |
| `intra_op_num_threads` no configurado | Cero config extra | ONNX usa todos los cores del host, CPU throttling del container | Nunca en deployment containerizado |
| Modelo descargado en runtime (no en build) | Imagen Docker ~300MB más liviana | Container no es autónomo, primer request falla en VPS sin internet | Nunca en producción |

---

## Integration Gotchas

| Integration | Common Mistake | Correct Approach |
|-------------|----------------|------------------|
| rembg `remove()` | Llamar sin pasar `session=` — crea sesión interna nueva | Pasar siempre `session=app.state.rembg_session` |
| FastAPI `UploadFile` | Llamar `await file.read()` dentro de `async def` y pasar bytes directamente a rembg | Leer los bytes primero con `await file.read()`, luego despachar el procesamiento a `asyncio.to_thread()` |
| Pillow `Image.open(BytesIO(...))` | Cerrar el BytesIO antes de terminar con la imagen | El BytesIO debe mantenerse vivo mientras la imagen esté en uso; usar context manager anidado |
| watchdog `Observer` | Iniciar el observer fuera del `lifespan` context de FastAPI | Iniciar en lifespan startup y detener en lifespan shutdown para evitar threads huérfanos |
| docker-compose `mem_limit` | Setear límite exactamente al uso promedio, sin margen para picos de inferencia | Agregar al menos 30-40% de headroom sobre el pico máximo medido con `docker stats` |

---

## Performance Traps

| Trap | Symptoms | Prevention | When It Breaks |
|------|----------|------------|----------------|
| Un thread de ONNX por request sin pool global | CPU al 100% durante inferencia aunque max_concurrent=1, alto tiempo de kernel | Configurar `intra_op_num_threads=2` y `OMP_NUM_THREADS=2` en el container | Siempre en container con CPU limits |
| WebP encode con `method=6` (máxima compresión) | Encoding tarda 3-5x más que con `method=4` sin diferencia visual notable | Usar `method=4, quality=85` para catálogo — balance calidad/velocidad | Cualquier volumen > 10 imágenes/hora |
| Pillow `thumbnail()` vs `resize()` para autocrop | `thumbnail()` modifica in-place y no upscales, breaks pipeline si producto es más pequeño que 800x800 | Usar `resize()` explícito con `Image.Resampling.LANCZOS` | Imágenes de producto pequeñas (<200px) |
| asyncio.Semaphore sin timeout | Request bloqueado indefinidamente si el procesamiento falla sin liberar el semaphore | Envolver en `asyncio.wait_for()` con timeout razonable (ej: 60s) | Cualquier error no manejado en el pipeline |

---

## Security Mistakes

| Mistake | Risk | Prevention |
|---------|------|------------|
| `Image.MAX_IMAGE_PIXELS = None` para evitar DecompressionBombError | Un archivo de 4KB puede expandirse a 1GB en RAM, DoS del servicio | Setear `Image.MAX_IMAGE_PIXELS = 50_000_000` (50MP) y retornar HTTP 413 si se excede |
| No validar Content-Type del upload | Un archivo SVG o PDF puede ser interpretado por Pillow con comportamientos inesperados | Validar magic bytes del archivo, no solo Content-Type header (puede ser spoofed) |
| Exponer el endpoint sin rate limiting en el futuro | Aunque es servicio interno ahora, si se expone vía Traefik sin auth, cualquiera puede hacer inferencias costosas | Documentar que cualquier exposición externa requiere rate limiting y autenticación |

---

## UX Pitfalls

| Pitfall | User Impact | Better Approach |
|---------|-------------|-----------------|
| Respuesta HTTP 200 con JSON `{"error": "..."}` en lugar de HTTP 4xx/5xx | El cliente n8n upstream no detecta el error automáticamente y considera la imagen "procesada" | Usar HTTP 422 para errores de validación, 500 para errores de procesamiento, nunca 200 con error en body |
| Sin progress/status en requests largos (5-15s de inferencia en CPU) | El caller no sabe si el servicio está vivo o colgado | Documentar el tiempo esperado en `/status`, incluir `X-Processing-Time` header en la respuesta |
| Config UI que modifica el YAML sin feedback visual del reload | El operador no sabe si el hot-reload fue aplicado o si el watchdog falló | La API de config debe confirmar explícitamente si el reload fue exitoso en la respuesta POST |

---

## "Looks Done But Isn't" Checklist

- [ ] **Sesión rembg global:** El modelo se inicializa UNA sola vez en startup — verificar que `new_session()` no aparece en ninguna función de procesamiento por request
- [ ] **asyncio.to_thread en TODO el pipeline:** rembg AND todas las operaciones de Pillow deben estar dentro del `to_thread` — verificar con `/health` bajo carga
- [ ] **EXIF transpose como primer step:** Testear con foto de celular rotada 90° — el output debe estar derecho
- [ ] **Modos de color cubiertos:** Testear con imagen CMYK, imagen P (GIF), imagen L (grayscale) — ninguna debe crashear
- [ ] **Modelo en imagen Docker:** `docker build` seguido de `docker run --network none` — el servicio debe arrancar y procesar sin acceso a internet
- [ ] **OOM test:** Correr 10 requests seguidos con imágenes de 8MP — `docker stats` no debe superar 1.8GB
- [ ] **Semaphore con timeout:** Un request que falla a mitad debe liberar el semaphore — verificar que el siguiente request no queda bloqueado
- [ ] **Config reload bajo carga:** Modificar el YAML mientras hay un request activo — no debe producir output corrupto ni excepción
- [ ] **WebP output es RGB no RGBA:** El WebP final no debe tener canal alpha — verificar con `Image.open(output).mode == "RGB"`
- [ ] **intra_op_num_threads configurado:** `OMP_NUM_THREADS` visible en el environment del container — verificar con `docker inspect`

---

## Recovery Strategies

| Pitfall | Recovery Cost | Recovery Steps |
|---------|---------------|----------------|
| OOMKill del container | LOW | Ajustar `mem_limit` con margen, reiniciar container, monitorear `docker stats` en carga |
| Sesión rembg per-request | MEDIUM | Refactor del startup, mover `new_session()` al lifespan, revisar todos los calls a `remove()` para pasar `session=` |
| Event loop bloqueado (sin `to_thread`) | MEDIUM | Envolver pipeline completo en `asyncio.to_thread()`, testear `/health` bajo carga |
| Race condition en config reload | HIGH | Agregar `threading.RLock`, revisar todos los accesos al objeto config, testing concurrente |
| Modelo no en imagen Docker | LOW | Agregar step de pre-download al Dockerfile, rebuild, push |
| Memory leak de Pillow sin close() | MEDIUM | Auditar todo el pipeline buscando `Image.open()` sin context manager, agregar `.close()` explícito |

---

## Pitfall-to-Phase Mapping

| Pitfall | Prevention Phase | Verification |
|---------|------------------|--------------|
| Sesión rembg no global | Pipeline Core (Fase 1) | Test de 20 requests seguidos — RAM en `docker stats` no crece |
| Event loop bloqueado | Pipeline Core (Fase 1) | `/health` responde en <100ms durante un request de procesamiento activo |
| ONNX `intra_op_num_threads` | Dockerización (Fase de container) | `OMP_NUM_THREADS=2` en `docker inspect`, CPU% no supera el límite configurado |
| OOMKill en pico de RAM | Dockerización (Fase de container) | 10 requests con imágenes 8MP sin exit 137 |
| EXIF orientation | Pipeline Core (Fase 1) | Test con JPEG de celular — output derecho |
| Modo de color inesperado | Pipeline Core (Fase 1) | Tests unitarios con CMYK, P, L, LA inputs |
| birefnet-lite resolution | Pipeline Core (Fase 1) | Test con imagen 50x50 y con imagen 5000x100 — no crash |
| Modelo no en Docker | Dockerización (Fase de container) | `docker run --network none` debe funcionar |
| watchdog race condition | Config hot-reload (Fase de config) | Test de stress: `curl POST /config` mientras se procesan imágenes en loop |
| Pillow images sin close | Pipeline Core (Fase 1) | Revisión de código + test de larga duración (100 requests) sin crecimiento de RAM |
| WebP RGBA sin composite | Pipeline Core (Fase 1) | `Image.open(output_file).mode == "RGB"` en test de integración |
| Semaphore sin timeout | API (Fase de API) | Simular fallo en pipeline mientras semaphore está tomado — siguiente request no queda bloqueado |

---

## Sources

- [rembg Issue #752 — Memory Leak Server Mode Under Sustained Load](https://github.com/danielgatis/rembg/issues/752)
- [rembg Issue #289 — Simultaneous Requests Causing Memory Leak](https://github.com/danielgatis/rembg/issues/289)
- [ONNX Runtime Issue #18749 — Memory Leak in Python](https://github.com/microsoft/onnxruntime/issues/18749)
- [ONNX Runtime Issue #22271 — Memory Leak After Running Model Numerous Times](https://github.com/microsoft/onnxruntime/issues/22271)
- [ONNX Runtime Thread Management Docs](https://onnxruntime.ai/docs/performance/tune-performance/threading.html)
- [ONNX Runtime Issue #24101 — Performance Bottleneck intra_op_num_threads Global](https://github.com/microsoft/onnxruntime/issues/24101)
- [Frigate Issue #22620 — onnxruntime pthread_setaffinity_np fails in LXC containers](https://github.com/blakeblackshear/frigate/issues/22620)
- [FastAPI Concurrency and async/await Docs](https://fastapi.tiangolo.com/async/)
- [FastAPI Discussion #8842 — Blocking Long Running Requests](https://github.com/fastapi/fastapi/discussions/8842)
- [FastAPI Best Practices — zhanymkanov](https://github.com/zhanymkanov/fastapi-best-practices)
- [Making Python Respect Docker Memory Limits — Carlos Becker](https://carlosbecker.com/posts/python-docker-limits/)
- [Docker Resource Constraints Docs](https://docs.docker.com/engine/containers/resource_constraints/)
- [Pillow Issue #7961 — Memory Leak Opening Images](https://github.com/python-pillow/Pillow/issues/7961)
- [Pillow Issue #7935 — Memory of Copied PIL Images Not Released](https://github.com/python-pillow/Pillow/issues/7935)
- [Pillow File Handling Documentation](https://pillow.readthedocs.io/en/stable/reference/open_files.html)
- [Pillow Issue #4537 — EXIF Orientation Not Updated When Saving Rotated Image](https://github.com/python-pillow/Pillow/issues/4537)
- [Why is Pillow Rotating My Image When I Save It — alexwlchan](https://alexwlchan.net/til/2024/photos-can-have-orientation-in-exif/)
- [rembg Session and Model Management — DeepWiki](https://deepwiki.com/danielgatis/rembg/4.2-session-and-model-management)
- [Reducing CPU Usage in ML Inference with ONNX Runtime — Inworld AI](https://inworld.ai/blog/reducing-cpu-usage-in-machine-learning-model-inference-with-onnx-runtime)
- [BiRefNet vs rembg vs U2Net: Production Comparison — DEV Community](https://dev.to/om_prakash_3311f8a4576605/birefnet-vs-rembg-vs-u2net-which-background-removal-model-actually-works-in-production-4830)
- [BiRefNet Input Resolution — ZhengPeng7/BiRefNet](https://github.com/ZhengPeng7/BiRefNet)
- [FastAPI UploadFile Large Files — Medium/HashBlock](https://medium.com/@connect.hashblock/async-file-uploads-in-fastapi-handling-gigabyte-scale-data-smoothly-aec421335680)

---
*Pitfalls research for: Image standardization microservice (rembg/Pillow/FastAPI/ONNX/Docker)*
*Researched: 2026-03-30*
