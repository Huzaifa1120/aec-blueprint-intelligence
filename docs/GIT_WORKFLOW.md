# Git Workflow — Three‑Layer Model

This project uses a **three‑layer Git branching model** to keep production code (`main`) stable, while allowing ongoing development (`dev`) and isolated feature work (`feature/*`).

## Branch hierarchy

| Branch | Purpose | Typical content |
|--------|---------|-----------------|
| `main` | Production / release candidate | Merged, tested code that is ready for deployment. |
| `dev`   | Integration branch | Latest completed features, ready for the next release. |
| `feature/*` | isolated work for a single phase or feature | Work-in‑progress that is not yet ready for `dev`. |

## Typical workflow

1. **Create a feature branch** from `dev`

   ```bash
   git checkout -b feature/phase-0-foundation dev
   ```

2. **Work on the phase** – add, modify, or delete files as needed.  
   Commit with meaningful messages, e.g.:

   ```bash
   git add docs/phase-0-foundation-feature.txt
   git commit -m "feat: add phase‑0 foundation feature placeholder documentation"
   ```

3. **Push the feature branch** to the remote

   ```bash
   git push -u origin feature/phase-0-foundation
   ```

   This creates a pull‑request‑ready branch on GitHub.

4. **Merge feature into `dev`** (once the phase is complete and reviewed)

   ```bash
   git checkout dev
   git merge --no-ff feature/phase-0-foundation -m "merge: feature‑0‑foundation into dev"
   git push -u origin dev
   ```

   The `--no‑ff` flag keeps a merge commit, making the history explicit.

5. **Merge `dev` into `main`** (when the release is ready)

   ```bash
   git checkout main
   git merge --no-ff dev -m "merge: dev into main for production release"
   git push -u origin main
   ```

   After this, `main` reflects a production‑ready state.

## Guidelines

- **Branch names** should be descriptive: `feature/phase‑<number>-<short‑description>`.
- **Commit messages** follow the conventional format: `type: short description` where `type` can be `feat`, `fix`, `docs`, `refactor`, etc.
- **Never push directly to `main`** – all changes must travel through `feature` → `dev` → `main`.
- Keep `dev` green (tests passing) before merging into `main`.

## Visual summary

```
feature/phase-xxx  <-- commits, PR
         |
   dev branch <-- merges from many feature branches
         |
   main branch <-- final release candidate (protected)
```