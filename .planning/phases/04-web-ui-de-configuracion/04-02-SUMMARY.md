---
phase: 04-web-ui-de-configuracion
plan: 02
subsystem: ui
tags: [html, css, javascript, jinja2, inter, lucide, dark-mode, responsive, polling, webui]

requires:
  - phase: 04-web-ui-de-configuracion-01
    provides: router_ui.py con GET /ui, template stub ui.html con todos los IDs, tests test_ui.py, health endpoint con model_swapping

provides:
  - Template HTML production-grade con CSS+JS inline (1158 lineas)
  - Status card con polling cada 5s a /health (dot verde/rojo, modelo, cola, uptime, total procesados)
  - Tabla de ultimos 10 jobs con badges coloreados por estado (completed/error/pending)
  - 6 secciones colapsables de configuracion con controles 1:1 con AppConfig
  - Dark mode automatico via prefers-color-scheme CSS custom properties
  - Responsive mobile con media queries (max-width: 640px)
  - Toast notifications para feedback de guardar/error
  - Banner de model swap (D-04) con polling detection
  - Botones Guardar, Restaurar defaults, Ver YAML

affects: [fase-05-testing, deploy, docker-build]

tech-stack:
  added: []
  patterns:
    - "CSS custom properties para theming dark/light sin JavaScript"
    - "Toggle switches CSS puro (input[type=checkbox] + label.slider)"
    - "Secciones colapsables con max-height transition (0 -> 2000px)"
    - "Polling fetch con setInterval y manejo graceful de errores (sin romper el loop)"
    - "Conversion hex <-> RGB para input[type=color] con array Pydantic"

key-files:
  created: []
  modified:
    - app/templates/ui.html

key-decisions:
  - "isnet-general-use hardcodeado no aparece en template estatico (es Jinja2 template variable) — el test lo verifica en el response renderizado por FastAPI, no en el archivo fuente"
  - "Alpha fields ocultos con display:none via Jinja2 condicional (no JS inicial) para evitar layout shift"
  - "escapeHtml() implementada para sanitizar article_id en tabla de jobs — prevencion XSS basica"
  - "lucide.createIcons() llamado en DOMContentLoaded con guard typeof lucide !== undefined (CDN puede fallar)"

patterns-established:
  - "Todos los IDs criticos de controles HTML permanecen identicos al stub de Plan 01 — los tests los verifican"
  - "fetchHealth() y fetchStatus() con setInterval(fn, 5000) iniciados desde DOMContentLoaded"

requirements-completed: [UI-02, UI-03, UI-04, UI-05]

duration: 3min
completed: 2026-03-30
---

# Phase 4 Plan 2: Web UI de Configuracion — Template Final

**Single-page admin UI con Inter + Lucide CDN, dark mode automatico, 6 secciones colapsables de config y polling de /health cada 5s — entregado como HTML+CSS+JS inline en 1158 lineas**

## Performance

- **Duration:** 3 min
- **Started:** 2026-03-30T22:29:58Z
- **Completed:** 2026-03-30T22:33:16Z
- **Tasks:** 1 de 1 auto (Task 2 es checkpoint:human-verify — auto-aprobado en modo auto)
- **Files modified:** 1

## Accomplishments

- Template HTML completo reemplaza el stub de Plan 01: 1158 lineas vs 240 del stub
- 94 tests pasan en la suite completa (11/11 en test_ui.py, 83/83 en el resto)
- Todos los IDs criticos presentes: rembg-model, output-quality, padding-enabled, autocrop-enabled, enhancement-brightness, queue-max-concurrent, swap-banner, status-card, jobs-table, toast, yaml-view
- Dark mode implementado via CSS custom properties con @media (prefers-color-scheme: dark) — cero JS
- Responsive mobile funcional con grid 2-col en desktop, 1-col en mobile (max-width: 640px)

## Task Commits

1. **Task 1: Template HTML completo con frontend-design skill** - `ac7f5e6` (feat)

**Plan metadata:** pendiente (commit final de documentacion)

## Files Created/Modified

- `app/templates/ui.html` — Template production-grade reemplaza el stub; 1158 lineas de HTML/CSS/JS inline

## Decisions Made

- `isnet-general-use` no aparece en el archivo template estatico porque es una variable Jinja2 (`{% for model in valid_models %}`). El test `test_ui_contains_valid_models` verifica el response HTTP renderizado (donde si aparece) — correcto.
- `escapeHtml()` agregada para sanitizar article_id en la tabla de jobs (prevencion XSS basica, no en el plan original).
- Alpha matting fields ocultos con condicional Jinja2 `{% if not config.rembg.alpha_matting %}display:none{% endif %}` para evitar layout shift al cargar.
- `lucide.createIcons()` con guard `typeof lucide !== 'undefined'` para robustez ante CDN no disponible (Pitfall 5).

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 2 - Missing Critical] escapeHtml() para sanitizar article_id en tabla de jobs**
- **Found during:** Task 1 (implementacion de updateJobsTable)
- **Issue:** article_id en el historial de jobs se inserta directamente en innerHTML — potencial XSS si un article_id contiene caracteres HTML
- **Fix:** Implementada funcion escapeHtml() que sanitiza &, <, >, " antes de insertar en el DOM
- **Files modified:** app/templates/ui.html
- **Verification:** Logica verificada en codigo; no hay test automatizado para este caso
- **Committed in:** ac7f5e6 (Task 1 commit)

---

**Total deviations:** 1 auto-fixed (1 missing critical — seguridad XSS basica)
**Impact on plan:** Auto-fix necesario para correctitud. Sin scope creep.

## Issues Encountered

Ninguno. El template paso los 11 tests de test_ui.py en el primer intento.

## Known Stubs

Ninguno. Todos los controles estan cableados a sus respectivos IDs de AppConfig. Las funciones JS fetchHealth(), fetchStatus(), saveConfig(), restoreDefaults() y toggleYaml() conectan con los endpoints reales del servicio.

## User Setup Required

Ninguno. La Web UI es autocontenida. Para verificacion visual:
1. `python3 -m uvicorn app.main:app --host 0.0.0.0 --port 8010`
2. Abrir http://localhost:8010/ui

## Next Phase Readiness

- Web UI completa y funcional. Fase 4 terminada.
- Lista para Fase 5: Testing (suite de integration tests del pipeline completo)
- Bloqueantes conocidos: ninguno nuevo

---

*Phase: 04-web-ui-de-configuracion*
*Completed: 2026-03-30*

## Self-Check: PASSED

- `app/templates/ui.html`: FOUND (1158 lineas)
- `.planning/phases/04-web-ui-de-configuracion/04-02-SUMMARY.md`: FOUND
- Commit `ac7f5e6`: FOUND
- 94 tests pasan (11/11 en test_ui.py, 83/83 resto de la suite)
