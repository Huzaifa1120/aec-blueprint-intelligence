# Session Handoff — Spec v3 Accuracy-Conformance Execution

**Date:** 2026-08-25
**Branch:** `feature/spec-v3-accuracy-conformance` (pushed to origin through `7a72def`)
**Plan:** `docs/superpowers/plans/2026-08-25-spec-v3-accuracy-conformance.md` (14 tasks, two waves)
**Design spec:** `docs/superpowers/specs/2026-08-25-spec-v3-accuracy-conformance-design.md`
**SDD workspace (gitignored):** `.superpowers/sdd/2026-08-25-spec-v3-accuracy-conformance.md/` — ledger (`progress.md`), task briefs `task-N-brief.md`, implementer reports, review packages
**Execution mode:** Subagent-Driven Development, parallel across three disjoint streams

---

## 1. Read this first (resume protocol)

1. Read the ledger: `.superpowers/sdd/2026-08-25-spec-v3-accuracy-conformance.md/progress.md`. Its first line names this plan; every `Task N: complete` line is done work — do not redo it.
2. **Immediate next action:** Task 2 is implemented and controller-ratified but its REVIEW has not run. The review package already exists at `.superpowers/sdd/2026-08-25-spec-v3-accuracy-conformance.md/task-2-review-package.diff` (commit `7a72def`, diff vs base `44c72b2`). Dispatch a task reviewer (brief = `task-2-brief.md`, report = `task-2-report.md`, package path above). On clean verdict: append `Task 2: complete` to ledger, push, then continue with Task 3.
3. Then execute Tasks 3→4→7→8→9→10→12→13→14 (backend stream, strictly serial) and Task 11 (frontend stream, after T8+T10 land) per §4.

## 2. Commit inventory (this branch, oldest first)

| SHA | What | Task | Review status |
|---|---|---|---|
| `2b70064` | design spec committed | pre-plan | n/a |
| `1446b9c` | implementation plan committed | pre-plan | n/a |
| `28e419c` | spec v3 §7.3 amendment (FIRE ALARM out of electrical; P-/FP-/FA- families; RAIN DOWNPIPE→plumbing; changelog 2026-08-25) | T6 | ✅ reviewed clean |
| `ef87734` | frontend AssumedScaleBanner + EstimateBoq scale/data_quality types (vitest 63/63, lint/tsc green) | T5 | ✅ reviewed clean |
| `43a92c6` | fix: explicit `^FIRE ALARM`→fire_alarm rule added to §7.3 example | T6 fix r1 | ✅ re-reviewed CLEAN |
| `16ca1c1` | scale.py: ScaleResult dataclass + resolve_scale + parse_scale_denominator + _ARCH_DENOMINATORS (9 tests) | T1 | ✅ |
| `44c72b2` | fix: imperial branch reachable (`SCALE 1=N'-0"` → denominator N×12), ELECTRICAL-precedence test | T1 fix r1 | ✅ re-reviewed CLEAN |
| `7a72def` | honest scale wiring: routes.py 1:1 fallback → 100; e2e response `scale:{value,status}`; vector.py unified on resolve_scale; extraction schema gains scale_status/scale_str; phase2 E2 pin flipped detected→assumed | T2 | ⚠️ **REVIEW OUTSTANDING** (package ready) |

## 3. Rulings made (binding on the next session)

1. **Parallelism:** owner-mandated parallel execution overrides SDD's "never parallel implementers" — allowed only across provably disjoint file domains: backend/** stream, frontend/src/** stream, docs/** stream. Max one implementer per stream; never overlapping files. Reviews may overlap anything.
2. **No extra worktree:** owner created this branch deliberately; working directly on it.
3. **Push policy:** controller pushes after each task's review comes back clean (owner asked for pushes during work); implementers never push. Branch currently pushed through `7a72def`.
4. **T6 FIRE ALARM gap:** brief omitted the replacement rule when removing FIRE ALARM from electrical. Ruled per binding design-spec §3.4 C7: add explicit `^FIRE ALARM` → fire_alarm (landed in `43a92c6`).
5. **T1 imperial branch:** plan's own regex was dead code (`\'` escape trap) with a latent IndexError via `_from_ratio`. Ruled: `SCALE 1=N'-0"` means 1 inch = N feet → denominator N×12, ScaleResult built directly. Landed `44c72b2`.
6. **T2 MMC scale flip (important):** implementer flipped phase2 E2 pin from `detected` to `assumed`. Controller independently probed MMC with pymupdf: **384 text spans, only a bare `"SCALE"` token, no ratio anywhere** — the earlier audit claim "MMC carries ELECTRICAL.SCALE 1:100" was wrong. Honest `assumed`/1:100 is correct under the owner's flag-&-proceed decision. Consequence to surface to owner at merge time: real MMC runs will show the AssumedScaleBanner and (once T3 lands) length-derived rows become ASSUMED-tier, because the machine genuinely cannot read that sheet's scale.

## 4. Remaining work (with dependencies)

Backend stream (strictly serial, same files): **T2 review → T3** (confidence tiers in `_boq_line`; expect deliberate contract breaks — update MEASURED assertions on BOQ lines only, add `# contract change` comments) **→ T4** (DataQuality dataclass + counters at drop sites router.py:413-416/471-487/489-501/527-569 + measure_routes/fixture_units stats params) **→ T7** (one Alembic migration, head `c37396f6713e`: boq_items.source_bbox_json; estimates.data_quality_json/scale_status/source_pdf_path; review_actions.boq_item_id/reason/corrected_value — autogenerate strips drifted labor_rates table, hand-edit result; ALSO add one line to design-spec §4.1 noting corrections live as columns on review_actions instead of a separate table) **→ T8** (route bbox capture → payload source{page,bbox} + item_id; persist scale/dq) **→ T9** (store upload PDF to backend/data/uploads/<estimate_id>.pdf + GET /api/estimates/{id}/file; gitignore entry) **→ T10** (Literal-validated AddActionRequest + correction columns written) **→ T12** (labor BOQ lines w/ catalog→YAML rate fallback; total_labor_cost real; access_control_door.yaml gets hourly_rate/category; row-count baselines shift once — grep `114` and material-count asserts) **→ T13** (xlsx/pdf dq section + corrections annex; narration Assumptions & Data Quality section; verbatimism gate must stay green) **→ T14** (full sweep both stacks + Memory.md row).

Frontend stream: **T11** after T8+T10 land (normalizeBoq id-keying + source array→HighlightBBox object `{x1:b[0],y1:b[1],x2:b[2],y2:b[3]}`; logAction sends reason/corrected_value/boq_item_id; `<PDFViewer src={API_BASE}/api/estimates/{id}/file>`).

## 5. Environment notes (this machine, user Huzaifa)

- Backend venv exists at `backend/.venv` (Python 3.13). Run everything as `& ".venv\Scripts\python.exe" -m pytest/-m ruff` from `backend/`. No Git Bash `bash` on PATH — SDD helper scripts don't run; equivalents were done manually via PowerShell (briefs generated by slicing the plan; packages via `git show`).
- Pre-existing failures NOT caused by this work: `tests/test_spike_raster_reproof.py` collection error (`cv2` missing — opencv-python-headless not installed here) and one `alembic.__main__` migration test. Full suite otherwise reported 314 passed at T1-fix time.
- `.githooks` pre-commit IS active on this clone (core.hooksPath set 2026-08-25): eslint+tsc+prettier run on staged frontend commits; keep staged TS prettier-clean.
- Known cosmetic friction: repo-wide CRLF-vs-prettier; normalize only files you stage. Pre-existing eslint warning at EstimateClient.tsx (~line 129, shifted by T5 import).

## 6. Conventions for the next dispatcher

- Briefs for all 14 tasks already exist in the workspace (UTF-8 regenerated after mojibake). Report contract: implementer writes full report to `task-N-report.md`, replies ≤15 lines with Status/commits/test-summary/concerns/path. Record BASE before each dispatch; review package = `git show --stat` + `git show -U10` of the exact commit(s) into `task-N-review-package.diff`.
- Fix loop: resume same implementer rounds 1–3 (task tool `task_id`), fresh agent rounds 4–5; scoped re-review after every round; five-round breaker then adjudicate.
- Ledger every ruling and completion line immediately; the ledger survives context loss, memory doesn't.
