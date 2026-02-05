# STATUS — Merlian

## Product intent (commercial)
Build a **local-first “visual memory” app** that makes people say: *“Holy shit — it found the exact screenshot/image I meant.”*  
Primary wedge: **screenshots + downloaded images** (high volume, high pain). Privacy-first by default.

## Current state (what works today)
- **UI** (Svelte forked from Dispict) supports:
  - Demo gallery (`#/demo`) and Local mode (`#/local`) via hash routing
  - Folder selection + local onboarding polish
  - Search UI w/ **OCR previews**
- **Engine** (`engine/`, Python) supports:
  - CLI: `merlian.py index/search/status/reset`
  - Local API (FastAPI/uvicorn on **8008**): `/health`, `/status`, `/index`, `/search`
  - Background indexing jobs + progress + cancel
  - Hybrid retrieval (CLIP + OCR) and OCR-only mode
  - Model caching + warm endpoint
- **Security**: file/asset endpoints are restricted to **localhost + indexed paths**.

## What’s missing (commercial “wow” blockers)
- Onboarding contract is still weak: user doesn’t immediately understand *why this is better than Spotlight/Finder*.
- Reliability: unclear success rate on real screenshot libraries; quality needs a measurable bar.
- Packaging/distribution: still dev-mode (Python env + npm). No “download → works.”
- Differentiation beyond Harvard art demo: need a repeatable, everyday wedge.

## Single next highest-leverage step
Define and ship a **“Wow Test” onboarding flow** that proves value in < 60 seconds on the user’s own machine:
1) default-select **~/Desktop & ~/Pictures/Screenshots (or user picks)**
2) index a small sample quickly (e.g., last 200 screenshots)
3) run 3 guided queries (chips) that usually hit (e.g., “error”, “receipt”, “calendar”, “confirmation”, “chart”)
4) show an undeniable result + instant open/reveal.

This gives us a concrete target to optimize retrieval + UX around.

## Plan (next 2 weeks)
### Week 1 — Define the wedge + make the wow reproducible
- Pick ICP: “heavy screenshot takers” (devs, PMs, students, ops).
- Implement the Wow Test flow + telemetry (local-only):
  - time-to-first-result, % queries with a click, top failure reasons
- Retrieval quality pass:
  - ensure OCR indexing for screenshots is on by default
  - tune ranking weights (CLIP vs OCR) and add simple heuristics (e.g., prefer recent screenshots)

### Week 2 — Packaging + trust
- Produce a single-command local run (already partially present via `run-local.sh`) → make it robust.
- Decide desktop wrapper direction:
  - MVP: keep browser UI + local engine
  - Next: Tauri shell w/ spotlight hotkey + background indexing
- Add trust surfaces:
  - “Nothing leaves your machine” banner + clear data locations
  - permissions help (macOS Files & Folders / Full Disk Access)

## Active risks / questions
- macOS permissions friction (Desktop/Screenshots access).
- OCR speed/quality tradeoffs on large libraries.
- Packaging Python + model weights without huge downloads.

## How to run (dev)
UI:
```bash
cd ui
npm install
npm run dev -- --host 127.0.0.1 --port 5173
```
Engine:
```bash
cd engine
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn server:app --port 8008
```
