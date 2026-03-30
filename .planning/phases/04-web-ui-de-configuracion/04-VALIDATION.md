---
phase: 4
slug: web-ui-de-configuracion
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-03-30
---

# Phase 4 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 9.0.2 + httpx 0.28.1 (AsyncClient) |
| **Config file** | pyproject.toml `[tool.pytest.ini_options]` |
| **Quick run command** | `pytest tests/ -x -q --no-header` |
| **Full suite command** | `pytest tests/ -v --tb=short` |
| **Estimated runtime** | ~5 seconds (no ONNX model needed — UI tests only) |

---

## Sampling Rate

- **After every task commit:** Run `pytest tests/ -x -q --no-header`
- **After every plan wave:** Run `pytest tests/ -v --tb=short`
- **Before `/gsd:verify-work`:** Full suite must be green
- **Max feedback latency:** 5 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 04-01-01 | 01 | 1 | UI-01 | integration | `pytest tests/test_api.py -k "ui" -x` | ❌ W0 | ⬜ pending |
| 04-01-02 | 01 | 1 | UI-02 | integration | `pytest tests/test_api.py -k "health_polling" -x` | ❌ W0 | ⬜ pending |
| 04-01-03 | 01 | 1 | UI-03 | integration | `pytest tests/test_api.py -k "config_form" -x` | ❌ W0 | ⬜ pending |
| 04-01-04 | 01 | 1 | UI-04 | integration | `pytest tests/test_api.py -k "config_save" -x` | ❌ W0 | ⬜ pending |
| 04-01-05 | 01 | 1 | UI-05 | manual | Browser check dark mode + mobile | N/A | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] Phase 5 handles full test suite — this phase focuses on HTML/JS correctness verifiable via endpoint tests
- [ ] Basic test for GET /ui returning 200 + HTML content type

*Note: Comprehensive API tests are Phase 5 scope (TEST-03). Phase 4 validation focuses on ensuring endpoints serve correct content.*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Dark mode rendering | UI-05 | CSS prefers-color-scheme requires browser | Open /ui in browser, toggle system dark mode, verify colors adapt |
| Mobile responsive layout | UI-05 | Responsive breakpoints require visual check | Open /ui on mobile or resize browser to 375px width, verify no overflow |
| Real-time polling visual | UI-02 | Visual update requires human verification | Open /ui, watch status card update every 5s without page reload |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 5s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
