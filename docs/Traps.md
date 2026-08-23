# TRAPS.md (System Traps & Anti-Patterns)

**Purpose:** This document highlights the critical technical traps, non-negotiables, and anti-patterns for the AEC Blueprint Intelligence System. 

**Reference:** This file serves as an explicit extension to `AGENTS.md`. All coding agents and developers must strictly adhere to these rules to prevent architectural drift, inaccurate data generation, and environment breakage.

---

## 1. The Ultimate Trap: AI Hallucination in Math
*   **TRAP:** Asking an LLM or Computer Vision model to count items, measure lengths, calculate areas, or derive prices directly.
*   **SOLUTION:** **"AI proposes. Geometry calculates. Engineering rules derive. Humans approve."** No LLM or vision model ever outputs a final quantity. All quantities must trace back to deterministic calculation via vector geometry or bounding-box spatial analysis.

## 2. Dependency & Library Traps
*   **PyMuPDF Alias Breakage:** **NEVER** import `fitz`. You must always use `import pymupdf`. The `fitz` alias is deprecated and will break the application.
*   **Hardcoded Values:** **NEVER** hardcode material unit prices or labor productivity rates in the source code. These must live strictly in the catalog DB or YAML configuration.
*   **Python Executables (Windows Environment):** **NEVER** run console-script executables directly (e.g., `pytest.exe` or `ruff.exe`). They embed absolute paths that break after the virtual environment is moved. Always run modules via python (e.g., `python -m pytest`, `python -m uvicorn`).
*   **Pip Upgrades:** **NEVER** run `pip install --upgrade pip` inside the running venv, as this causes a WinError 32 file lock. Recreate the venv instead.

## 3. Scope & Phasing Traps
*   **Skipping to CV (Raster):** **DO NOT** build the raster/CV fallback (Phase 1.5) or multi-sheet features before the v1 vector MVP (Phase 1) is fully proven and the Definition of Done is met.
*   **Raw Materials from Single-Discipline Sheets:** **DO NOT** attempt to estimate raw materials (like concrete, formwork, or rebar) from a single-discipline sheet like an Electrical or Access Control plan. These require the structural/architectural set.

## 4. Frontend / Next.js Traps
*   **Next.js Breaking Changes:** The frontend stack uses React 19 and a major Next.js version with breaking changes. Rely exclusively on `node_modules/next/dist/docs/` before writing Next.js code, and do not blindly trust older Next.js tutorials or generated code patterns.
*   **Package Management:** The frontend utilizes Turbopack (`npm run dev`). Ensure strict TypeScript adherence (`npm run build`).
