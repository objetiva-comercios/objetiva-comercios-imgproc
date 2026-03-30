---
phase: 01-pipeline-core-api-basica
plan: "02"
subsystem: processor
tags: [pipeline, rembg, pillow, image-processing, tdd]
dependency_graph:
  requires: ["01-01"]
  provides: ["processor.py", "process_image", "ProcessingError"]
  affects: ["app/queue.py", "app/api.py"]
tech_stack:
  added: [rembg==2.0.74, piexif==1.1.3]
  patterns:
    - funciones puras por step del pipeline
    - mock de rembg.remove en tests unitarios
    - TDD Red-Green por bloque de steps
key_files:
  created:
    - app/processor.py
    - tests/test_processor.py
  modified: []
decisions:
  - "process_image es sincrona (CPU-bound); la llamada async se delega a asyncio.to_thread() en queue.py"
  - "getdata() marcado con type:ignore por DeprecationWarning de Pillow 12 (funciona hasta Pillow 14)"
  - "Test de contrast usa imagen con gradiente, no gris uniforme (midpoint de PIL no cambia con contraste)"
  - "Test de quality usa imagen ruidosa (aleatoria) para diferencia medible entre quality=10 y quality=95"
metrics:
  duration: "~15 min"
  completed: "2026-03-30"
  tasks_completed: 2
  tasks_total: 2
  files_created: 2
  files_modified: 0
---

# Phase 01 Plan 02: Image Processing Pipeline Summary

**One-liner:** Pipeline completo de 7 steps (decode→rembg→autocrop→scale→composite→enhance→encode) con ProcessingError y 31 tests unitarios con rembg mockeado.

## What Was Built

### `app/processor.py` — Pipeline completo

**`class ProcessingError(Exception)`** — Excepcion del pipeline con atributos `step` y `detail`.

**Step 1 — `decode_and_validate(image_bytes, config, article_id)`**
- Soporta JPEG, PNG, WebP, BMP, TIFF
- `ImageOps.exif_transpose()` SIEMPRE antes de cualquier otro procesamiento (D-08)
- Rechaza imagenes > 25 megapixels con ProcessingError (D-05)
- Convierte CMYK → RGB silenciosamente (D-07)
- Convierte todo a RGBA para el pipeline
- Logging JSON structured en cada step

**Step 2 — `remove_background(img, config, rembg_session)`**
- Deteccion de alpha pre-existente: si > 10% de pixeles con alpha < 128, salta rembg (D-06)
- Llama `rembg.remove()` con todos los parametros de config (alpha_matting, thresholds)
- Retorna imagen RGBA

**Step 3 — `autocrop(img, config)`**
- Binariza canal alpha con `config.autocrop.threshold`
- `getbbox()` sobre alpha binarizado
- Guard: si bbox < 5% del area total, skippea el crop y loggea warning
- Respeta `config.autocrop.enabled`

**Step 4 — `calculate_scale_and_position(img, config)`**
- `available_px = canvas_px - 2 * padding_px` (640px con config default)
- `scale = min(available_px / w, available_px / h)` — fit-inside, nunca distorsiona
- Retorna `(scaled_w, scaled_h, offset_x, offset_y)` para centrado perfecto

**Step 5 — `composite(img, config)`**
- LANCZOS para downscale, BICUBIC para upscale
- Canvas RGB 800x800 con `config.output.background_color`
- Pega con canal alpha como mascara

**Step 6 — `enhance(img, config)`**
- Skip optimization: si brightness==1.0 y contrast==1.0, retorna sin cambios
- Aplica `ImageEnhance.Brightness` y/o `ImageEnhance.Contrast`

**Step 7 — `encode_webp(img, config)`**
- `quality=0` activa `lossless=True`
- Retorna bytes WebP validos (magic RIFF...WEBP)

**`process_image(image_bytes, article_id, config, rembg_session)`** — Orquestador sincronico:
- Ejecuta los 7 steps en orden fijo
- Acumula `steps_applied` con nombres de steps ejecutados
- Wrappea excepciones desconocidas en ProcessingError(step="unknown")
- Retorna `ProcessingResult` con todos los campos poblados

### `tests/test_processor.py` — 31 tests unitarios

Tests agrupados por clase por step:
- `TestDecodeAndValidate`: 10 tests (JPEG/PNG/WebP/BMP/TIFF, invalid, megapixel, CMYK, size string, EXIF)
- `TestRemoveBackground`: 2 tests (skip con >10% alpha, llamada con imagen opaca mockeada)
- `TestAutocrop`: 3 tests (basico, guard 5%, disabled)
- `TestCalculateScaleAndPosition`: 4 tests (landscape, portrait, square, offsets)
- `TestComposite`: 4 tests (centering, output RGB, exact size, custom background)
- `TestEnhance`: 3 tests (brightness, contrast, skip)
- `TestEncodeWebp`: 3 tests (magic bytes, quality diff, lossless)
- `TestProcessImage`: 2 tests (output mode/size, full pipeline con ProcessingResult)

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Test de contrast con imagen gris uniforme no detecta cambio**
- **Found during:** Task 2 ejecucion de tests
- **Issue:** Pillow `ImageEnhance.Contrast` no modifica pixeles en el punto medio exacto (128, 128, 128) — es matematicamente correcto pero el test fallaba
- **Fix:** Test reformulado con imagen de gradiente (mitad oscura 50,50,50 / mitad clara 200,200,200) y contrast=2.0 para diferencia medible
- **Files modified:** tests/test_processor.py
- **Commit:** 63c7c5a

**2. [Rule 1 - Bug] Test de quality con imagen solida no muestra diferencia de tamano**
- **Found during:** Task 2 ejecucion de tests
- **Issue:** Imagen RGB solida uniforme produce bytes casi identicos con quality=50 y quality=95 (encoder optimiza igual)
- **Fix:** Test reformulado con imagen de ruido aleatorio (random.seed(42)) y quality=10 vs quality=95 para diferencia garantizada
- **Files modified:** tests/test_processor.py
- **Commit:** 63c7c5a

**3. [Rule 3 - Blocker] rembg y piexif no instalados en el entorno local**
- **Found during:** Task 1 RED phase
- **Issue:** `rembg` no estaba instalado en el entorno de desarrollo (el plan asume Docker); `piexif` necesario para test de EXIF
- **Fix:** Instalados via `pip3 install --break-system-packages rembg[cpu]==2.0.74 piexif`
- **Files modified:** ninguno (entorno, no repositorio)
- **Nota:** El Dockerfile ya tiene estas dependencias; solo afecta el entorno local de testing

## Known Stubs

None — el pipeline esta completamente implementado con logica real.

## Verification Results

```
pytest tests/test_processor.py -x -v       -> 31 passed
pytest tests/ -x -v                        -> 44 passed (tests de plan 01 + 02)
python3 -c "from app.processor import process_image, ProcessingError; print('imports OK')"  -> OK
```

## Self-Check: PASSED

- [x] app/processor.py exists (confirmed)
- [x] tests/test_processor.py exists (confirmed)
- [x] Commit 317094f exists (Task 1 - steps 1-4)
- [x] Commit 63c7c5a exists (Task 2 - steps 5-7 + process_image)
- [x] 31 tests pass, 0 failures
- [x] All acceptance criteria met:
  - ProcessingError con step y detail
  - decode_and_validate retorna tuple
  - remove_background acepta rembg_session
  - autocrop con guard 5%
  - calculate_scale_and_position retorna tuple de 4 ints
  - verificacion > 25_000_000 megapixels
  - deteccion alpha con umbral 0.10
  - composite con Image.new canvas RGB
  - enhance con skip cuando ambos 1.0
  - encode_webp con lossless cuando quality==0
  - process_image retorna ProcessingResult
  - steps_applied acumula nombres de steps
  - Image.LANCZOS para downscale
  - test_full_pipeline verifica ProcessingResult completo
  - 31 funciones test_* en total (>25 requeridas)
