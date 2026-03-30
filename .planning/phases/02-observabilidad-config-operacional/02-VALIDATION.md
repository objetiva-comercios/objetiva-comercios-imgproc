---
phase: 2
slug: observabilidad-config-operacional
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-03-30
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
| **Full suite command** | `pytest tests/ --cov=src --cov-report=term-missing --timeout=60` |
| **Estimated runtime** | ~15 seconds |

---

## Sampling Rate

- **After every task commit:** Run `pytest tests/ -x -q --timeout=30`
- **After every plan wave:** Run `pytest tests/ --cov=src --cov-report=term-missing --timeout=60`
- **Before `/gsd:verify-work`:** Full suite must be green
- **Max feedback latency:** 30 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 02-01-01 | 01 | 1 | CONF-02 | unit | `pytest tests/test_config.py -k watchdog` | ❌ W0 | ⬜ pending |
| 02-01-02 | 01 | 1 | CONF-03 | unit | `pytest tests/test_config.py -k reload` | ❌ W0 | ⬜ pending |
| 02-02-01 | 02 | 1 | CONF-04 | integration | `pytest tests/test_api.py -k post_config` | ❌ W0 | ⬜ pending |
| 02-02-02 | 02 | 1 | CONF-05 | integration | `pytest tests/test_api.py -k model_swap` | ❌ W0 | ⬜ pending |
| 02-03-01 | 03 | 1 | API-06 | integration | `pytest tests/test_api.py -k get_status` | ❌ W0 | ⬜ pending |
| 02-03-02 | 03 | 1 | QUEUE-05 | unit | `pytest tests/test_queue.py -k history` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/test_config.py` — stubs for CONF-02, CONF-03 (watchdog reload, deep merge)
- [ ] `tests/test_api.py` — stubs for CONF-04, CONF-05, API-06 (POST /config, model swap, GET /status)
- [ ] `tests/test_queue.py` — stubs for QUEUE-05 (job history)
- [ ] `tests/conftest.py` — shared fixtures (mock config, test app client)

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| File edit on host triggers reload in container | CONF-02 | Requires Docker volume mount + file edit from host | 1. Edit settings.yaml on host 2. Check container logs for reload event within 5s |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 30s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
