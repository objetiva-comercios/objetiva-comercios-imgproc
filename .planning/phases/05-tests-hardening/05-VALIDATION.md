---
phase: 5
slug: tests-hardening
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-03-30
---

# Phase 5 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 9.0.2 + pytest-asyncio 1.3.0 |
| **Config file** | pyproject.toml (`[tool.pytest.ini_options]`) |
| **Quick run command** | `.venv/bin/python -m pytest tests/ -x -q` |
| **Full suite command** | `.venv/bin/python -m pytest tests/ --cov=app --cov-report=term-missing` |
| **Estimated runtime** | ~15 seconds |

---

## Sampling Rate

- **After every task commit:** Run `.venv/bin/python -m pytest tests/ -x -q`
- **After every plan wave:** Run `.venv/bin/python -m pytest tests/ --cov=app --cov-report=term-missing`
- **Before `/gsd:verify-work`:** Full suite must be green
- **Max feedback latency:** 15 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 05-01-01 | 01 | 1 | TEST-01 | unit | `.venv/bin/python -m pytest tests/test_processor.py -x -q` | ✅ | ⬜ pending |
| 05-01-02 | 01 | 1 | TEST-02 | unit | `.venv/bin/python -m pytest tests/test_queue.py -x -q` | ✅ | ⬜ pending |
| 05-01-03 | 01 | 1 | TEST-03 | integration | `.venv/bin/python -m pytest tests/test_api.py tests/test_config_router.py tests/test_ui.py -x -q` | ✅ | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `pytest-cov>=6.0` — install in .venv for coverage measurement

*Existing test infrastructure (conftest.py, all test files) covers all phase requirements.*

---

## Manual-Only Verifications

*All phase behaviors have automated verification.*

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 15s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
