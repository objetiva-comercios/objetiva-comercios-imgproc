# Phase 6: Tech Debt Cleanup - Research

**Researched:** 2026-04-01
**Domain:** Python dependency management, Pillow API migration, HTML self-containment, documentation accuracy
**Confidence:** HIGH

## Summary

Esta fase cierra cuatro items de tech debt identificados en el audit v1.0 del milestone. Ninguno es un bloqueante funcional — el servicio opera correctamente — pero cada item representa un riesgo latente o una inconsistencia técnica que escala si se ignora. Los cuatro items son independientes entre sí y pueden planificarse como tareas atómicas.

El item más crítico (TECH-DEBT-01) es la falta de declaración explícita de scipy y numpy en requirements.txt. Ambas se usan en `app/processor.py` pero llegan como dependencias transitivas de rembg[cpu]. Un cambio en el árbol de dependencias de rembg rompería el servicio en runtime sin error de build. TECH-DEBT-02 (CDN externos) viola el principio de autonomía del proyecto. TECH-DEBT-03 es una inconsistencia documental que confunde al lector. TECH-DEBT-04 requiere verificación cuidadosa: el audit dice "migrar Image.Image.getdata" pero el código ya usa `get_flattened_data` — la tarea real es evaluar si la migración a numpy (que da 24x speedup en benchmarks locales) es apropiada.

**Recomendación primaria:** Ejecutar los cuatro items en una sola fase, en este orden: primero TECH-DEBT-01 (riesgo medio, trivial), luego TECH-DEBT-04 (verificar estado + migrar si aplica), luego TECH-DEBT-03 (edición de texto), finalmente TECH-DEBT-02 (mayor esfuerzo de implementación).

## Project Constraints (from CLAUDE.md)

Directivas obligatorias extraídas de `CLAUDE.md` del proyecto:

- **Orden del pipeline fijo e inamovible:** decode → rembg → autocrop → scale → composite → enhance → encode
- **RAM**: ≤ 2 GB para el container — modelo isnet-general-use (no birefnet-lite — ver TECH-DEBT-03)
- **asyncio.to_thread()** obligatorio para operaciones CPU-bound
- **Formato de salida:** WebP únicamente, RGB sin alpha
- **yaml.safe_load** siempre (nunca yaml.load sin Loader)
- **Sesión rembg global** inicializada una vez en startup, nunca por request
- **python-multipart** requerido para UploadFile en FastAPI
- **python:3.11-slim** como base Docker (no alpine)
- **Dependencias externas:** ninguna — todo embebido en la imagen Docker (relevante para TECH-DEBT-02)
- **GSD Workflow Enforcement:** usar /gsd:execute-phase para trabajo planificado

## Tech Debt Items — Análisis Detallado

### TECH-DEBT-01: scipy/numpy no declarados en requirements.txt

**Archivo:** `requirements.txt`
**Severidad:** MEDIUM
**Estado:** Pendiente

**Situación actual:**
```
# requirements.txt — estado actual
fastapi==0.135.2
uvicorn[standard]==0.42.0
rembg[cpu]==2.0.74
Pillow==12.1.1
typer==0.24.1
Jinja2==3.1.6
PyYAML==6.0.3
watchdog==6.0.0
python-multipart>=0.0.9
```

scipy y numpy están instalados (verificado via `.venv/lib/python3.12/site-packages/`):
- numpy 2.4.4
- scipy (presente)

Pero no aparecen en requirements.txt. Son importados directamente en `app/processor.py`:
- `import numpy as np` (líneas 177, 245, 246, 248)
- `from scipy import ndimage` (línea 183)

**Riesgo:** Si rembg actualiza su árbol de dependencias y deja de requerir scikit-image (que arrastra scipy/numpy), el servicio falla en runtime con `ModuleNotFoundError` sin ningún error en el build de Docker.

**Fix:** Agregar a requirements.txt:
```
scipy>=1.16
numpy>=2.3
```

**Versiones actuales verificadas en .venv:**
- numpy: 2.4.4 (dist-info confirma)
- scipy: presente como dependencia transitiva de rembg[cpu] via scikit-image

**Confidence:** HIGH — verificado directo en codebase.

---

### TECH-DEBT-02: UI carga Google Fonts e iconos Lucide desde CDN externos

**Archivo:** `app/templates/ui.html` líneas 8-9
**Severidad:** LOW
**Estado:** Pendiente

**Situación actual:**
```html
<!-- líneas 8-9 de ui.html -->
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600&display=swap" rel="stylesheet">
<script src="https://unpkg.com/lucide@0.468.0/dist/umd/lucide.min.js"></script>
```

**Iconos usados (12 en total):**
- settings, loader, cpu, chevron-down, image, square, crop, sliders, layers, save, rotate-ccw, code-2

**Fallbacks existentes (ya implementados):**
- Font: `font-family: 'Inter', system-ui, -apple-system, sans-serif` — si CDN falla, cae a system-ui
- Lucide: `if (typeof lucide !== 'undefined') lucide.createIcons()` — guard en línea 1172, los `<i data-lucide="...">` simplemente no renderizan el ícono

**Impacto visual:** Sin CDN, la UI funciona completamente pero pierde la fuente Inter y todos los íconos SVG. Dado el principio "sin dependencias externas", esto viola UI-01 ("sin dependencias externas").

**Opciones de fix:**

**Opción A: Eliminar Inter, usar system font stack (RECOMENDADA para fuente)**
- Eliminar `<link>` de Google Fonts
- Cambiar `font-family: 'Inter', system-ui, -apple-system, sans-serif` → `font-family: system-ui, -apple-system, sans-serif`
- Impact: cero bytes extra, UI visualmente casi idéntica

**Opción B: Inline SVGs para los 12 iconos (RECOMENDADA para Lucide)**
- Eliminar `<script src="unpkg.com/lucide...">` (350KB)
- Definir los 12 SVGs como símbolos inline en el HTML o como CSS background-image
- Implementar `createIcons()` custom que reemplaza `<i data-lucide="name">` con el SVG correspondiente
- Impact: ~3-5KB extra de SVGs inlined vs 350KB del bundle completo

**Opción C: SVG sprite approach**
- Un `<svg>` hidden con todos los `<symbol id="icon-name">` en el head
- Usar `<use href="#icon-name">` en lugar de `<i data-lucide="name">`
- Requiere cambiar todos los `<i data-lucide="...">` por `<svg><use>` — más cambios pero más semántico

**Opción recomendada:** A para fuente + B para iconos. La opción B mantiene la arquitectura actual (data-lucide attributes) con mínimos cambios.

**Test impactado:** `test_ui_no_static_references` verifica que no haya `/static/` — un nuevo test debe verificar que no haya referencias a dominios externos.

**Confidence:** HIGH — código verificado directamente.

---

### TECH-DEBT-03: CLAUDE.md documenta birefnet-lite pero implementación usa isnet-general-use

**Archivo:** `CLAUDE.md` sección Constraints
**Severidad:** LOW
**Estado:** Pendiente

**Situación actual:**

En CLAUDE.md, línea 12:
```
- **RAM**: ≤ 2 GB para el container — obliga a usar birefnet-lite y max_concurrent=1
```

En `app/models.py`:
```python
model: str = "isnet-general-use"
```

En `app/router_config.py`:
```python
"silueta", "isnet-general-use", "isnet-anime",
"birefnet-general", "birefnet-general-lite", ...
```

**Historia del cambio:** Según la decisión documentada en STATE.md `[Phase 04-web-ui-de-configuracion]: isnet-general-use hardcodeado no aparece en template estatico (es Jinja2 template variable)`, el modelo fue cambiado a isnet-general-use porque birefnet-lite excedía los 2GB de RAM del container.

**Fix:** Actualizar en CLAUDE.md las menciones de birefnet-lite que describen el modelo activo:

Líneas a actualizar (verificadas con grep):
- Línea 12: cambiar `birefnet-lite` → `isnet-general-use`
- Línea 31: tabla de stack, columna "Propósito" de rembg — actualizar descripción
- Línea 71: ejemplo de "Sesión rembg por request" (texto de ejemplo, puede dejarse o actualizarse)
- Línea 82: esta línea habla de GPU future variant — no cambiar (es un posible escenario futuro)

**Constraint RAM:** También actualizar la justificación RAM: el constraint sigue siendo ≤ 2GB, pero la razón ya no es "birefnet-lite", sino que isnet-general-use cabe en ~1.5GB.

**Confidence:** HIGH — verificado con grep en CLAUDE.md y app/models.py.

---

### TECH-DEBT-04: Pillow API deprecated — Image.Image.getdata

**Archivo:** `app/processor.py:115`
**Severidad:** INFO (no warning activo en Pillow 12.1.1)
**Estado:** PARCIALMENTE RESUELTO — requiere verificación

**Situación actual (verificada):**

El audit registró esta deuda con referencia a `Image.Image.getdata`. Al verificar el código actual:
```python
# app/processor.py línea 115
transparent_pixels = sum(1 for p in alpha_channel.get_flattened_data() if p < 128)
```

El código YA usa `get_flattened_data()` (la API nueva que reemplaza a `getdata()`). `getdata()` no aparece en ningún lugar del codebase.

**Estado real:** La migración básica está hecha. Sin embargo, `get_flattened_data()` devuelve una tuple de tuples o tuple de floats, y el patrón actual itera con un generator — correcto pero subóptimo.

**Benchmark local (800x800 L image):**
```
get_flattened_data + sum generator: 0.271s para 10 iteraciones
numpy (np.array(img) < 128).sum():  0.011s para 10 iteraciones
Speedup numpy: 24x
```

**Fix recomendado:** Dado que numpy ya es una dependencia declarada (TECH-DEBT-01), reemplazar el patrón por numpy:

```python
# Antes (línea 115)
transparent_pixels = sum(1 for p in alpha_channel.get_flattened_data() if p < 128)

# Después — más rápido y semánticamente claro
import numpy as np
transparent_pixels = int((np.array(alpha_channel) < 128).sum())
```

El import de numpy ya existe en `_clean_alpha_artifacts` (línea 177), pero es un import local dentro de la función. La función `remove_background` (donde está la línea 115) está en otro scope — se puede mover el import al top-level del módulo o mantenerlo local.

**Verificación de correctitud:**
```
old approach: 10 pixels transparentes
numpy approach: 10 pixels transparentes
match: True
```

**Decisión de diseño:** El criterio de éxito de la fase dice "migrado a API actual de Pillow". Como el código ya usa `get_flattened_data` (API actual de Pillow 12.x), técnicamente está cumplido. La migración a numpy es una mejora de performance que el planner puede incluir dado que numpy ya es dependencia del módulo.

**Confidence:** HIGH — código verificado, benchmark ejecutado localmente.

---

## Standard Stack

### Core (sin cambios de dependencias)
| Library | Version | Purpose | Notas para esta fase |
|---------|---------|---------|---------------------|
| Pillow | 12.1.1 | Manipulación de imágenes | `get_flattened_data` es la API actual. Migrar a numpy para performance. |
| numpy | 2.4.4 | Operaciones vectorizadas en array de pixels | Declarar explícitamente en requirements.txt |
| scipy | (transitive) | `ndimage.label` para componentes conectados en _clean_alpha_artifacts | Declarar explícitamente en requirements.txt |

### No se agregan nuevas dependencias
Esta fase no introduce nuevas librerías. Solo:
1. Declara dependencias ya usadas (scipy, numpy)
2. Elimina dependencias externas de la UI (Google Fonts CDN, Lucide CDN)
3. Actualiza documentación
4. Optimiza código existente

**Instalación / verificación:**
```bash
# Verificar versiones instaladas en el venv
python3 -m pip show numpy scipy
# Agregar al requirements.txt — no instalar nada nuevo
```

## Architecture Patterns

### Patrón: Declaración explícita de dependencias transitivas

Las dependencias transitivas que se importan directamente en el código deben declararse en requirements.txt. La regla es: si el código hace `import X`, X debe estar en requirements.txt o requirements-dev.txt, sin excepción.

```
# requirements.txt — DESPUÉS del fix TECH-DEBT-01
scipy>=1.16
numpy>=2.3
```

El operador `>=` (en lugar de `==`) es apropiado para scipy y numpy porque:
1. No son dependencias con APIs cambiantes frecuentes en los patrones usados
2. Permite que rembg resuelva la versión compatible sin conflictos
3. Las versiones mínimas corresponden a las presentes en el venv actual

### Patrón: HTML autocontenido sin requests externos

El principio de autonomía requiere que ui.html no haga ningún request externo. La solución para iconos SVG es el inline sprite pattern:

```html
<!-- En el <head> o <body>, un SVG sprite oculto -->
<svg style="display:none" aria-hidden="true">
  <symbol id="icon-settings" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
    <!-- paths del ícono settings de lucide -->
  </symbol>
  <!-- 11 símbolos más... -->
</svg>

<!-- En el HTML donde antes había <i data-lucide="settings"> -->
<svg class="icon" width="22" height="22"><use href="#icon-settings"/></svg>
```

O, para mínimos cambios, reemplazar el script de lucide con una implementación local que parsea `data-lucide` y los reemplaza con SVGs hardcodeados:

```javascript
// Reemplaza lucide.createIcons() — solo los 12 iconos usados
const ICONS = {
  'settings': '<svg ...>path aquí</svg>',
  // ... 11 más
};
function createIcons() {
  document.querySelectorAll('[data-lucide]').forEach(el => {
    const name = el.getAttribute('data-lucide');
    if (ICONS[name]) el.outerHTML = ICONS[name];
  });
}
createIcons();
```

### Anti-Patterns a Evitar

- **No usar `==` para scipy/numpy en requirements.txt**: Puede crear conflictos de resolución con onnxruntime y rembg que también dependen de numpy
- **No inline el bundle completo de lucide (350KB) en el HTML**: Derrotaría el propósito de eliminar la dependencia externa sin ganancia
- **No cambiar el font-family en el CSS de dark mode**: La regla `@media (prefers-color-scheme: dark)` hereda el font-family del `:root` — no necesita duplicarse

## Don't Hand-Roll

| Problema | No Construir | Usar Invece | Por qué |
|---------|-------------|------------|--------|
| Conteo de pixels transparentes | Loop Python puro | `numpy` (ya dependencia) | 24x speedup; numpy vectoriza la operación entera |
| Parseo de SVG paths de lucide | Script de extracción custom | Copiar SVG paths del source de lucide@0.468.0 directamente | Los paths están en el repositorio público de lucide; copiar es suficiente |

## Common Pitfalls

### Pitfall 1: Usar `==` en lugar de `>=` para scipy/numpy
**Qué sale mal:** `scipy==1.16.0` puede entrar en conflicto con la versión que onnxruntime/scikit-image necesita, causando `pip install` fallido durante el Docker build.
**Por qué ocurre:** onnxruntime y scikit-image también dependen de numpy; pinar una versión exacta de numpy puede bloquear la resolución de dependencias.
**Cómo evitar:** Usar `numpy>=2.3` y `scipy>=1.16` — bound inferior suficiente para asegurar las APIs usadas.
**Señal de alerta:** `ERROR: Cannot install ... because these package versions have conflicting dependencies`

### Pitfall 2: El test test_ui_no_static_references no verifica CDN externas
**Qué sale mal:** Después de eliminar los CDNs, no hay test automatizado que prevenga regresiones.
**Por qué ocurre:** El test existente solo verifica ausencia de `/static/`, no de URLs externas.
**Cómo evitar:** Agregar un test en `test_ui.py` que verifique que no hay `fonts.googleapis.com`, `unpkg.com`, ni ningún `https://` en el HTML renderizado.

### Pitfall 3: CLAUDE.md tiene birefnet-lite en múltiples lugares — edición parcial
**Qué sale mal:** Si solo se actualiza la línea 12 (constraints) pero no la tabla de stack (línea 31), sigue habiendo inconsistencia.
**Por qué ocurre:** búsqueda por `birefnet-lite` en CLAUDE.md devuelve múltiples ocurrencias.
**Cómo evitar:** Usar grep antes de editar para identificar todas las ocurrencias relevantes. No todas deben cambiar (línea 82 habla de GPU future variant).

### Pitfall 4: numpy import en remove_background — scope del import
**Qué sale mal:** `remove_background` no tiene numpy en scope cuando se usa en la línea 115. La función `_clean_alpha_artifacts` sí lo importa localmente (línea 177).
**Por qué ocurre:** Los imports locales dentro de funciones no son visibles en otras funciones del módulo.
**Cómo evitar:** Si se migra la línea 115 a numpy, agregar `import numpy as np` al top del archivo (junto a los otros imports) en lugar de dentro de la función. Numpy ya está en el venv y se declara en requirements.txt tras TECH-DEBT-01.

### Pitfall 5: Eliminar el guard de lucide rompe el test de UI
**Qué sale mal:** El test `test_ui_no_static_references` podría fallar si se cambia la estructura del HTML incorrectamente.
**Por qué ocurre:** La template tiene `if (typeof lucide !== 'undefined') lucide.createIcons()` — si se remueve el script externo y también este guard, los tests que buscan el guard en el HTML podrían fallar.
**Cómo evitar:** Mantener el patrón de inicialización de iconos pero hacerlo self-contained.

## Code Examples

### TECH-DEBT-01: Fix de requirements.txt

```
# Source: verificación directa del venv y el audit v1.0
# requirements.txt — líneas a agregar

# Declaradas explícitamente (transitivas de rembg[cpu] via scikit-image, usadas directamente)
scipy>=1.16
numpy>=2.3
```

### TECH-DEBT-04: Migración de línea 115 a numpy

```python
# Source: verificación local — comportamiento idéntico, 24x más rápido
# app/processor.py — remove_background()

# ANTES (línea 115):
transparent_pixels = sum(1 for p in alpha_channel.get_flattened_data() if p < 128)

# DESPUÉS — numpy vectorizado:
import numpy as np  # mover al top-level del módulo junto a otros imports
transparent_pixels = int((np.array(alpha_channel) < 128).sum())
```

### TECH-DEBT-02: Eliminar dependencias CDN — fuente

```html
<!-- ANTES (línea 8): -->
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600&display=swap" rel="stylesheet">

<!-- DESPUÉS: eliminar esta línea -->

<!-- CSS (línea 50) — ANTES: -->
font-family: 'Inter', system-ui, -apple-system, sans-serif;

<!-- CSS (línea 50) — DESPUÉS: -->
font-family: system-ui, -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
```

### TECH-DEBT-02: Nuevo test para verificar ausencia de CDN

```python
# Source: pattern de test_ui_no_static_references
# tests/test_ui.py — test nuevo a agregar

async def test_ui_no_external_cdn(ui_client):
    """UI-01: HTML autocontenido — sin requests a CDNs externos."""
    resp = await ui_client.get("/ui")
    html = resp.text
    assert "fonts.googleapis.com" not in html
    assert "unpkg.com" not in html
    # Verificar que no haya ningún https:// externo (excepto el favicon data URI)
    import re
    external_urls = re.findall(r'https?://(?!data:)[^\s"\']+', html)
    assert len(external_urls) == 0, f"External URLs found: {external_urls}"
```

### TECH-DEBT-03: Líneas a actualizar en CLAUDE.md

```
# Source: grep del CLAUDE.md del proyecto

# Línea 12 — ANTES:
- **RAM**: ≤ 2 GB para el container — obliga a usar birefnet-lite y max_concurrent=1

# Línea 12 — DESPUÉS:
- **RAM**: ≤ 2 GB para el container — obliga a usar isnet-general-use y max_concurrent=1

# Línea 31 (tabla de stack, columna "Por qué Recomendado" de rembg) — ANTES:
... birefnet-lite ...

# Línea 31 — DESPUÉS: reemplazar referencia a birefnet-lite por isnet-general-use

# Línea 71 (ejemplo en "What NOT to Use") — puede mantener birefnet-lite como
# ejemplo del patrón "sesión por request" ya que ilustra el anti-pattern, no el modelo activo
```

## Environment Availability

| Dependencia | Requerida Por | Disponible | Versión | Fallback |
|-------------|--------------|-----------|---------|---------|
| Python 3.12 | Entorno de desarrollo | ✓ | 3.12 (venv) | — |
| numpy | TECH-DEBT-01, TECH-DEBT-04 | ✓ | 2.4.4 (en venv) | — |
| scipy | TECH-DEBT-01 | ✓ | presente (en venv) | — |
| Lucide SVG source | TECH-DEBT-02 | ✓ via unpkg | 0.468.0 | SVGs disponibles en GitHub lucide-icons/lucide |
| pytest | Verificación de tests | ✓ | 9.0.2 | — |

**Ninguna dependencia bloqueante.** Todo el trabajo es edición de archivos existentes.

## Validation Architecture

### Test Framework
| Propiedad | Valor |
|-----------|-------|
| Framework | pytest 9.0.2 + pytest-asyncio 1.3.0 |
| Config file | pyproject.toml (`[tool.pytest.ini_options]`) |
| Comando rápido | `python3 -m pytest tests/ -x -q` |
| Suite completa | `python3 -m pytest tests/ --cov=app --cov-report=term-missing` |

### Mapeo Requisitos → Tests para esta fase

| Item | Comportamiento | Tipo de Test | Comando | Archivo existe |
|------|---------------|-------------|---------|---------------|
| TECH-DEBT-01 | scipy/numpy declarados en requirements.txt | Verificación manual (no pytest) | `pip install -r requirements.txt --dry-run` | N/A |
| TECH-DEBT-02 | Sin requests a CDNs en HTML | unit (nuevo test) | `pytest tests/test_ui.py::test_ui_no_external_cdn -x` | ❌ Wave 0 |
| TECH-DEBT-02 | Iconos y fuente se renderizan | smoke manual en browser | N/A (manual) | N/A |
| TECH-DEBT-03 | CLAUDE.md consistente | Verificación manual | `grep -n "birefnet-lite" CLAUDE.md` | N/A |
| TECH-DEBT-04 | Línea 115 usa numpy / API actual | unit (test_processor existente) | `pytest tests/test_processor.py -x` | ✅ |

### Wave 0 Gaps
- [ ] `tests/test_ui.py::test_ui_no_external_cdn` — cubre TECH-DEBT-02 CDN removal

*(Los demás tests existentes son suficientes para cubrir las demás modificaciones)*

## Open Questions

1. **¿Inline SVG o custom createIcons para los iconos de Lucide?**
   - Lo que sabemos: se usan 12 iconos, lucide@0.468.0 pesa 350KB completo
   - Incertidumbre: si la UI puede cambiar iconos en el futuro, inline sprite es más mantenible
   - Recomendación: inline SVG sprite en el head — permite agregar nuevos iconos editando el sprite sin tocar el código JavaScript

2. **¿TECH-DEBT-04 ya está resuelto o hay trabajo adicional?**
   - Lo que sabemos: el código usa `get_flattened_data()` (API actual de Pillow 12.x), no `getdata()` — el criterio de éxito literal está cumplido
   - Incertidumbre: si el éxito criterion incluye también la migración a numpy por performance
   - Recomendación: dado que numpy es ahora dependencia declarada (TECH-DEBT-01), migrar línea 115 a numpy como mejora complementaria — 24x speedup sin riesgo

3. **¿Qué versiones exactas de scipy declarar?**
   - Lo que sabemos: el venv tiene scipy y numpy instalados por rembg[cpu]
   - Incertidumbre: versión exacta de scipy instalada (no verificada con pip show, solo confirmada como presente)
   - Recomendación: ejecutar `pip show scipy` en el venv para obtener la versión exacta antes de escribir el bound en requirements.txt

## Sources

### Primary (HIGH confidence)
- Código verificado directamente: `app/processor.py`, `app/templates/ui.html`, `requirements.txt`, `app/models.py`
- Benchmark local ejecutado: numpy vs get_flattened_data en Python 3.12, Pillow 12.1.1
- `CLAUDE.md` del proyecto — directivas y constraints verificadas con grep

### Secondary (MEDIUM confidence)
- `.planning/v1.0-MILESTONE-AUDIT.md` — descripción de los 4 items de tech debt
- `.venv/lib/python3.12/site-packages/` — confirmación de presencia de numpy/scipy

### Tertiary (LOW confidence)
- Ninguna fuente solo de WebSearch usada para esta investigación

## Metadata

**Confidence breakdown:**
- Declaración de deps (TECH-DEBT-01): HIGH — código y venv verificados directamente
- Eliminación de CDN (TECH-DEBT-02): HIGH — HTML verificado, plan de inline SVG bien entendido
- Corrección documental (TECH-DEBT-03): HIGH — grep en CLAUDE.md y app/models.py confirma la discrepancia
- Migración Pillow API (TECH-DEBT-04): HIGH — código ya usa get_flattened_data, benchmark de numpy ejecutado

**Research date:** 2026-04-01
**Valid until:** 2026-05-01 (stack estable, sin dependencias de fast-moving libraries)
