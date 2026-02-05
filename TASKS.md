# Merlian — Build Plan (execution)

This is the concrete work plan that turns the current prototype harness into a commercial v1.

## Milestone 0 — Freeze north star (today)
- [x] `PRODUCT.md` exists and matches our commercial intent.
- [ ] Keep `STATUS.md` current (single source of truth).

## Milestone 1 — The “Personal Demo” (Wow Onboarding) (2–4 days)
Goal: reproduce the Harvard demo feeling on the user’s own screenshots in <60s.

### UX deliverable
- A single button: **“Build my personal demo”**
- Default: index *recent screenshots* (cap N, e.g. last 200)
- After indexing, land the user in **Local Gallery** view that looks like a curated dataset.

### Engine deliverables
- `POST /index` accepts:
  - `max_items` (cap)
  - `recent_only` (sort by mtime desc)
- Add lightweight per-asset fields (stored in SQLite):
  - `kind` (screenshot/photo/document-ish)
  - `quality_score`
  - `dup_group` (near-duplicate id)
  - `textiness` (amount of OCR)

### UI deliverables
- Local Gallery page:
  - “Recent” grid
  - Lenses: **Errors**, **Codes/Confirmations**, **Receipts/Totals**, **Charts/Dashboards** (these are views, not hard-coded artifacts)
  - Search works immediately from this view.

## Milestone 2 — Evidence-first results (3–6 days)
Goal: users trust matches.

- Add OCR region boxes during indexing for screenshots (store normalized bboxes)
- In result detail view, highlight matched region(s)
- Add one-click actions:
  - copy extracted snippet (best line)
  - open / reveal

## Milestone 3 — Reliability + trust surfaces (1 week)
- Permissions helper (macOS Files & Folders / Full Disk Access guidance)
- “What’s indexed” panel + remove library + nuke index
- Performance guardrails:
  - background indexing control (pause)
  - throttle options (later)

## Milestone 4 — Packaging (alpha) (1–2 weeks)
- Decide wrapper: Tauri recommended for hotkey + background
- Bundle engine (no manual Python install)
- Private alpha to 5–20 users

## Acceptance criteria for v1 alpha
- Cold start to first meaningful result ≤ 60s on a typical laptop for a capped sample
- Users can reliably retrieve: 2FA/code, an error screenshot, a receipt total, a dashboard/chart screenshot
- Zero network dependency for local libraries
