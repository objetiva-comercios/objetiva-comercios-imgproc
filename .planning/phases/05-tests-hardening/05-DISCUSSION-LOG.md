# Phase 5: Tests + Hardening - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md -- this log preserves the alternatives considered.

**Date:** 2026-03-30
**Phase:** 05-tests-hardening
**Areas discussed:** Cobertura vs existentes, Edge cases processor, Estrategia de hardening, Coverage target y CI
**Mode:** --auto (all decisions auto-selected)

---

## Cobertura vs tests existentes

| Option | Description | Selected |
|--------|-------------|----------|
| Auditar existentes + completar faltantes | Los tests de fases 1-4 ya cubren camino feliz y muchos edge cases. Solo cerrar gaps contra TEST-01/02/03. | [auto] |
| Reescribir suite desde cero | Descartaria 2125 lineas de tests funcionales. Sin justificacion. | |

**User's choice:** [auto] Auditar existentes + completar faltantes (recommended default)
**Notes:** 80+ tests ya existentes, 9 archivos de test. Reescribir seria desperdicio.

---

## Edge cases del processor

| Option | Description | Selected |
|--------|-------------|----------|
| Todos los documentados en requisitos + decisiones de contexto | EXIF transpose, skip rembg transparentes, CMYK->RGB, megapixels, enhancement skip, pipeline E2E | [auto] |
| Solo los listados en TEST-01 | Minimo viable, podria dejar gaps en edge cases de decisiones | |

**User's choice:** [auto] Todos los documentados (recommended default)
**Notes:** Las decisiones de Fase 1 (D-05 a D-08) definen edge cases criticos que deben estar testeados.

---

## Estrategia de hardening

| Option | Description | Selected |
|--------|-------------|----------|
| Solo tests | El codigo ya tiene validaciones defensivas. Hardening = verificar que funcionan. | [auto] |
| Tests + validaciones adicionales en codigo | Agregaria scope no definido en la fase. | |

**User's choice:** [auto] Solo tests (recommended default)
**Notes:** El codigo ya implementa megapixel limit, CMYK conversion, fail fast, timeout global, 503 queue full.

---

## Coverage target y CI

| Option | Description | Selected |
|--------|-------------|----------|
| pytest --cov 80%+ sin CI setup | Coverage local. CI es scope futuro. | [auto] |
| pytest --cov + GitHub Actions CI | Agregaria infraestructura no scoped en esta fase. | |
| Sin coverage formal | No se podria medir el progreso. | |

**User's choice:** [auto] pytest --cov 80%+ sin CI setup (recommended default)
**Notes:** El proyecto no tiene CI configurado. Deploy es via Docker directo al VPS.

---

## Claude's Discretion

- Organizacion interna de tests (clases vs funciones)
- Nombres y descripciones de tests
- Fixtures adicionales necesarias
- Orden de ejecucion

## Deferred Ideas

None -- discussion stayed within phase scope
