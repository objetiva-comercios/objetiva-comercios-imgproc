---
phase: 2
slug: observabilidad-config-operacional
status: draft
nyquist_compliant: true
wave_0_complete: false
created: 2026-03-30
updated: 2026-03-30
---

# Phase 2 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 9.x + pytest-asyncio 1.3.0 |
| **Config file** | `pyproject.toml` |
| **Quick run command** | `pytest tests/ -x -q --timeout=30` |
| **Full suite command** | `pytest tests/ --cov=app --cov-report=term-missing --timeout=60` |
| **Estimated runtime** | ~15 seconds |

---

## Sampling Rate

- **After every task commit:** Run `pytest tests/ -x -q --timeout=30`
- **After every plan wave:** Run `pytest tests/ --cov=app --cov-report=term-missing --timeout=60`
- **Before `/gsd:verify-work`:** Full suite must be green
- **Max feedback latency:** 30 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | Test File | Status |
|---------|------|------|-------------|-----------|-------------------|-----------|--------|
| 02-01 Task 1 | 01 | 1 | CONF-02, CONF-03, API-06, QUEUE-05 | integration | `pytest tests/test_config_router.py tests/test_queue.py tests/test_config.py -x -q` | tests/test_config_router.py | ⬜ pending |
| 02-01 Task 2 | 01 | 1 | CONF-02, CONF-03, API-06, QUEUE-05 | integration | `pytest tests/test_config_router.py -x -v` | tests/test_config_router.py | ⬜ pending |
| 02-02 Task 1 | 02 | 2 | CONF-04, CONF-05 | integration | `pytest tests/test_config_router.py tests/test_watchdog.py -x -q` | tests/test_watchdog.py | ⬜ pending |
| 02-02 Task 2 | 02 | 2 | CONF-04, CONF-05 | integration | `pytest tests/test_watchdog.py -x -v` | tests/test_watchdog.py | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Test Files Created by This Phase

| Test File | Created By | Covers |
|-----------|------------|--------|
| `tests/test_config_router.py` | 02-01 Task 2 | GET /config, POST /config (deep merge, validation, whitelist), GET /status (metrics, history, avg) |
| `tests/test_watchdog.py` | 02-02 Task 2 | Watchdog reload, suppress flag, model swap (503, failure fallback) |

---

## Wave 0 Requirements

No Wave 0 stubs needed — both plans create their test files as Task 2 (TDD: tests written before or alongside implementation within the same plan).

Existing test files from Phase 1 that must not regress:
- `tests/test_api.py` — POST /process, GET /health
- `tests/test_config.py` — ConfigManager load/reload
- `tests/test_queue.py` — JobQueue submit, state tracking
- `tests/conftest.py` — shared fixtures

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| File edit on host triggers reload in container | CONF-05 | Requires Docker volume mount + file edit from host | 1. Edit settings.yaml on host 2. Check container logs for reload event within 5s |

---

## Validation Sign-Off

- [x] All tasks have `<automated>` verify commands
- [x] Sampling continuity: no 3 consecutive tasks without automated verify
- [x] No Wave 0 gaps — test files created within plans
- [x] No watch-mode flags
- [x] Feedback latency < 30s
- [x] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
