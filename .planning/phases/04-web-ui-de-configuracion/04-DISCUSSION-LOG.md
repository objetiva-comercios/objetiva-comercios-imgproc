# Phase 4: Web UI de Configuracion - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-03-30
**Phase:** 04-web-ui-de-configuracion
**Areas discussed:** Layout y organizacion, Feedback visual, Controles de configuracion, Estado en tiempo real
**Mode:** --auto (all decisions auto-selected with recommended defaults)

---

## Layout y organizacion

| Option | Description | Selected |
|--------|-------------|----------|
| Single page con secciones colapsables | Una sola pagina HTML, secciones expand/collapse | ✓ |
| Tabs por seccion | Tab navigation entre Status, Config rembg, Config output, etc. | |
| Sidebar + content | Menu lateral con secciones, contenido a la derecha | |

**User's choice:** [auto] Single page con secciones colapsables (recommended default)
**Notes:** Cumple UI-01 (autocontenida) con minima complejidad. Sin routing ni framework.

| Option | Description | Selected |
|--------|-------------|----------|
| Status arriba, Config abajo | El operador ve primero el estado del servicio | ✓ |
| Config arriba, Status abajo | Priorizando la configuracion sobre el monitoreo | |

**User's choice:** [auto] Status arriba, Config abajo (recommended default)
**Notes:** El operador abre la UI principalmente para verificar que el servicio funciona; config es secundario.

---

## Feedback visual

| Option | Description | Selected |
|--------|-------------|----------|
| Toast notifications inline | Div fijo que aparece/desaparece con timeout | ✓ |
| Alert boxes | Alert nativo del browser o custom modal | |
| Inline messages | Mensaje junto al boton que disparo la accion | |

**User's choice:** [auto] Toast notifications inline (recommended default)
**Notes:** Sin dependencias externas, implementable con vanilla JS.

| Option | Description | Selected |
|--------|-------------|----------|
| Banner de warning durante model swap | Banner amarillo visible mientras model_swapping=true | ✓ |
| Solo deshabilitar formulario | Inputs disabled durante swap, sin indicacion visual prominente | |

**User's choice:** [auto] Banner de warning durante model swap (recommended default)
**Notes:** Alineado con D-01 Fase 2 — el operador necesita saber que el servicio devuelve 503.

---

## Controles de configuracion

| Option | Description | Selected |
|--------|-------------|----------|
| Mapeo 1:1 con AppConfig (mixed controls) | Dropdown modelo, sliders quality/brightness/contrast, toggles booleans, number inputs | ✓ |
| Solo number inputs | Todos los campos como text/number inputs simples | |
| JSON editor raw | Textarea con JSON editable directamente | |

**User's choice:** [auto] Mapeo 1:1 con AppConfig con controles especificos por tipo (recommended default)
**Notes:** Cada field type tiene el control HTML mas apropiado. Color picker nativo para background_color.

---

## Estado en tiempo real

| Option | Description | Selected |
|--------|-------------|----------|
| Status card + tabla de jobs | Card verde/rojo arriba, tabla ultimos 10 jobs debajo | ✓ |
| Solo indicador de status | Badge minimo sin historial de jobs | |
| Dashboard completo | Graficos de metricas, historial paginado | |

**User's choice:** [auto] Status card + tabla de ultimos 10 jobs (recommended default)
**Notes:** /status ya expone historial de 50 jobs. Mostrar 10 agrega valor sin scope creep.

---

## Claude's Discretion

- Paleta de colores (dentro del estilo elegido por frontend-design)
- Animaciones y transiciones
- Layout exacto de controles (grid/flexbox)
- Estilo de toasts y banner

## Deferred Ideas

- Preview de imagen procesada en la UI (EXTF-04 — v2)
