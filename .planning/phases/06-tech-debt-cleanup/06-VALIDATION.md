---
phase: 6
slug: tech-debt-cleanup
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-04-01
---

# Phase 6 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 9.0.2 + pytest-asyncio 1.3.0 |
| **Config file** | pyproject.toml (`[tool.pytest.ini_options]`) |
| **Quick run command** | `python3 -m pytest tests/ -x -q` |
| **Full suite command** | `python3 -m pytest tests/ --cov=app --cov-report=term-missing` |
| **Estimated runtime** | ~15 seconds |

---

## Sampling Rate

- **After every task commit:** Run `python3 -m pytest tests/ -x -q`
- **After every plan wave:** Run `python3 -m pytest tests/ --cov=app --cov-report=term-missing`
- **Before `/gsd:verify-work`:** Full suite must be green
- **Max feedback latency:** 15 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 06-01-01 | 01 | 1 | TECH-DEBT-01 | manual | `pip install -r requirements.txt --dry-run` | N/A | ⬜ pending |
| 06-01-02 | 01 | 1 | TECH-DEBT-04 | unit | `pytest tests/test_processor.py -x` | ✅ | ⬜ pending |
| 06-01-03 | 01 | 1 | TECH-DEBT-03 | manual | `grep -n "birefnet-lite" CLAUDE.md` | N/A | ⬜ pending |
| 06-01-04 | 01 | 1 | TECH-DEBT-02 | unit (new) | `pytest tests/test_ui.py::test_ui_no_external_cdn -x` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/test_ui.py::test_ui_no_external_cdn` — stub for TECH-DEBT-02 CDN removal verification

*Existing infrastructure covers TECH-DEBT-01, TECH-DEBT-03, TECH-DEBT-04 requirements.*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Icons render correctly in UI | TECH-DEBT-02 | Visual verification of inline SVGs | Open /ui in browser, verify all 12 icons render |
| Font renders correctly after system-ui switch | TECH-DEBT-02 | Visual appearance check | Open /ui, verify text is legible and consistent |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 15s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
