# Phase 3: CLI + Batch Offline - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-03-30
**Phase:** 03-cli-batch-offline
**Areas discussed:** Reporte batch, Init rembg CLI, Output path, Config CLI UX
**Mode:** auto (all decisions auto-selected with recommended defaults)

---

## Init rembg CLI

| Option | Description | Selected |
|--------|-------------|----------|
| Eager init (cargar siempre) | Cargar modelo al inicio de cualquier subcomando | |
| Lazy init (solo process/batch) | Cargar modelo solo cuando se necesita procesar imágenes | ✓ |

**User's choice:** [auto] Lazy init — recommended default
**Notes:** Evita 5-15s de carga innecesaria para subcomandos config/serve

## Output Path

| Option | Description | Selected |
|--------|-------------|----------|
| Mismo directorio que input | Sobreescribir con extensión .webp | |
| ./output/ relativo a CWD | Default predecible, flag --output para override | ✓ |
| Requiere --output explícito | Sin default, forzar al usuario a especificar | |

**User's choice:** [auto] ./output/ con flag --output — recommended default
**Notes:** No sobreescribe originales, directorio creado automáticamente

## Reporte Batch

| Option | Description | Selected |
|--------|-------------|----------|
| Sin reporte | Solo output a consola | |
| CSV con flag --report | CSV generado al final con métricas por imagen | ✓ |
| JSON lines | Una línea JSON por imagen procesada | |

**User's choice:** [auto] CSV con flag --report — recommended default
**Notes:** Columnas: article_id, input_path, output_path, status, processing_time_ms, error

| Option | Description | Selected |
|--------|-------------|----------|
| Texto plano | Contador simple N/total | |
| Rich progress bar | Barra visual con Typer/Rich integrado | ✓ |
| Silencioso (solo errores) | Minimal output | |

**User's choice:** [auto] Rich progress bar — recommended default

## Config CLI UX

| Option | Description | Selected |
|--------|-------------|----------|
| YAML formateado | Mostrar archivo tal cual | ✓ |
| Tabla key-value | Formato tabla con columnas | |
| JSON | Serializar como JSON | |

**User's choice:** [auto] YAML formateado — recommended default

| Option | Description | Selected |
|--------|-------------|----------|
| Dotpath notation | `config set output.quality 95` | ✓ |
| JSON parcial | `config set '{"output": {"quality": 95}}'` | |
| Flag-based | `config set --section output --key quality --value 95` | |

**User's choice:** [auto] Dotpath notation — recommended default

## Claude's Discretion

- Formato exacto de mensajes de consola (colores, emojis, layout)
- Derivación de article_id desde nombre de archivo
- article_id en batch: nombre del archivo sin extensión

## Deferred Ideas

None
