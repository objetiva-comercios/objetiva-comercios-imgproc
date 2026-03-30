---
phase: 03
slug: cli-batch-offline
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-03-30
---

# Phase 03 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 9.0.2 + pytest-asyncio 1.3.0 |
| **Config file** | pyproject.toml |
| **Quick run command** | `.venv/bin/python -m pytest tests/test_cli.py -x -q` |
| **Full suite command** | `.venv/bin/python -m pytest tests/ -x -q` |
| **Estimated runtime** | ~15 seconds |

---

## Sampling Rate

- **After every task commit:** Run `.venv/bin/python -m pytest tests/test_cli.py -x -q`
- **After every plan wave:** Run `.venv/bin/python -m pytest tests/ -x -q`
- **Before `/gsd:verify-work`:** Full suite must be green
- **Max feedback latency:** 15 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 03-01-01 | 01 | 1 | CLI-01, CLI-05 | unit+integration | `.venv/bin/python -m pytest tests/test_cli.py -x -q` | ❌ W0 | ⬜ pending |
| 03-01-02 | 01 | 1 | CLI-02 | unit+integration | `.venv/bin/python -m pytest tests/test_cli.py -x -q` | ❌ W0 | ⬜ pending |
| 03-02-01 | 02 | 1 | CLI-03, CLI-04 | unit+integration | `.venv/bin/python -m pytest tests/test_cli.py -x -q` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/test_cli.py` — stubs for CLI-01 through CLI-05
- [ ] Typer CliRunner fixture for testing CLI commands

*Existing test infrastructure (conftest.py, pytest config) covers framework needs.*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Rich progress bar renders correctly | CLI-02 | Visual rendering depends on terminal | Run `imgproc batch ./test-images/ -o ./output/` and verify progress bar appears |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 15s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
