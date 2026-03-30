---
phase: 1
slug: pipeline-core-api-basica
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-03-30
---

# Phase 1 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 9.0.2 + pytest-asyncio 1.3.0 |
| **Config file** | `pyproject.toml` (seccion `[tool.pytest.ini_options]`) |
| **Quick run command** | `pytest tests/ -x -q` |
| **Full suite command** | `pytest tests/ --cov=app --cov-report=term-missing` |
| **Estimated runtime** | ~15 seconds |

---

## Sampling Rate

- **After every task commit:** Run `pytest tests/ -x -q`
- **After every plan wave:** Run `pytest tests/ --cov=app --cov-report=term-missing`
- **Before `/gsd:verify-work`:** Full suite must be green
- **Max feedback latency:** 15 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 01-01 | 01 | 0 | PIPE-01..10 | setup | `pytest tests/ --collect-only` | No — Wave 0 | ⬜ pending |
| 01-02 | 01 | 1 | PIPE-01 | unit | `pytest tests/test_processor.py::test_decode_formats -x` | No — Wave 0 | ⬜ pending |
| 01-03 | 01 | 1 | PIPE-02 | unit | `pytest tests/test_processor.py::test_exif_transpose -x` | No — Wave 0 | ⬜ pending |
| 01-04 | 01 | 1 | PIPE-03 | unit | `pytest tests/test_processor.py::test_rembg_removes_bg -x` | No — Wave 0 | ⬜ pending |
| 01-05 | 01 | 1 | PIPE-04 | unit | `pytest tests/test_processor.py::test_autocrop -x` | No — Wave 0 | ⬜ pending |
| 01-06 | 01 | 1 | PIPE-05 | unit | `pytest tests/test_processor.py::test_scale_aspect_ratio -x` | No — Wave 0 | ⬜ pending |
| 01-07 | 01 | 1 | PIPE-06 | unit | `pytest tests/test_processor.py::test_composite_centering -x` | No — Wave 0 | ⬜ pending |
| 01-08 | 01 | 1 | PIPE-07 | unit | `pytest tests/test_processor.py::test_enhancement -x` | No — Wave 0 | ⬜ pending |
| 01-09 | 01 | 1 | PIPE-08 | unit | `pytest tests/test_processor.py::test_encode_webp -x` | No — Wave 0 | ⬜ pending |
| 01-10 | 01 | 1 | PIPE-09 | unit | `pytest tests/test_processor.py::test_output_mode_rgb -x` | No — Wave 0 | ⬜ pending |
| 01-11 | 01 | 1 | PIPE-10 | integration | `pytest tests/test_processor.py::test_full_pipeline -x` | No — Wave 0 | ⬜ pending |
| 01-12 | 01 | 1 | D-05 | unit | `pytest tests/test_processor.py::test_megapixel_limit -x` | No — Wave 0 | ⬜ pending |
| 01-13 | 01 | 1 | D-06 | unit | `pytest tests/test_processor.py::test_skip_rembg_transparent -x` | No — Wave 0 | ⬜ pending |
| 01-14 | 01 | 1 | D-07 | unit | `pytest tests/test_processor.py::test_cmyk_conversion -x` | No — Wave 0 | ⬜ pending |
| 01-15 | 02 | 2 | API-01 | integration | `pytest tests/test_api.py::test_process_success -x` | No — Wave 0 | ⬜ pending |
| 01-16 | 02 | 2 | API-02 | integration | `pytest tests/test_api.py::test_process_headers -x` | No — Wave 0 | ⬜ pending |
| 01-17 | 02 | 2 | API-03 | integration | `pytest tests/test_api.py::test_process_override -x` | No — Wave 0 | ⬜ pending |
| 01-18 | 02 | 2 | API-04 | integration | `pytest tests/test_api.py::test_process_400_corrupt -x` | No — Wave 0 | ⬜ pending |
| 01-19 | 02 | 2 | API-04 | integration | `pytest tests/test_api.py::test_process_422_missing_field -x` | No — Wave 0 | ⬜ pending |
| 01-20 | 02 | 2 | API-04 | integration | `pytest tests/test_api.py::test_process_503_queue_full -x` | No — Wave 0 | ⬜ pending |
| 01-21 | 02 | 2 | API-05 | integration | `pytest tests/test_api.py::test_health -x` | No — Wave 0 | ⬜ pending |
| 01-22 | 03 | 1 | QUEUE-01 | unit | `pytest tests/test_queue.py::test_max_concurrent -x` | No — Wave 0 | ⬜ pending |
| 01-23 | 03 | 1 | QUEUE-02 | unit | `pytest tests/test_queue.py::test_503_queue_full -x` | No — Wave 0 | ⬜ pending |
| 01-24 | 03 | 1 | QUEUE-03 | unit | `pytest tests/test_queue.py::test_504_timeout -x` | No — Wave 0 | ⬜ pending |
| 01-25 | 03 | 2 | QUEUE-04 | integration | `pytest tests/test_api.py::test_health_during_processing -x` | No — Wave 0 | ⬜ pending |
| 01-26 | 04 | 1 | CONF-01 | unit | `pytest tests/test_config.py::test_config_loads_yaml -x` | No — Wave 0 | ⬜ pending |
| 01-27 | 04 | 1 | CONF-06 | unit | `pytest tests/test_config.py::test_config_snapshot_immutable -x` | No — Wave 0 | ⬜ pending |
| 01-28 | 05 | 3 | DOCK-01 | smoke | `docker build -t imgproc-test .` | No — Wave 0 | ⬜ pending |
| 01-29 | 05 | 3 | DOCK-05 | smoke | `docker run --rm imgproc-test python -c "from app.main import app; print('ok')"` | No — Wave 0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/conftest.py` — fixtures compartidos (imagen JPEG de prueba, imagen PNG transparente, imagen CMYK, app async client)
- [ ] `tests/test_processor.py` — stubs para tests unitarios del pipeline
- [ ] `tests/test_queue.py` — stubs para tests unitarios del JobQueue
- [ ] `tests/test_api.py` — stubs para tests de integracion de endpoints
- [ ] `tests/test_config.py` — stubs para tests del ConfigManager
- [ ] `pyproject.toml` — seccion `[tool.pytest.ini_options]` con `asyncio_mode = "auto"`

*Framework install: `pip install pytest pytest-asyncio httpx pytest-cov`*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Container funciona sin red | DOCK-05 | Requiere Docker con --network none | `docker run --rm --network none imgproc-test python -c "from app.main import app; print('ok')"` |
| RAM < 2GB durante procesamiento | Constraint | Requiere docker stats en runtime | `docker stats --no-stream` durante POST /process |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 15s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
