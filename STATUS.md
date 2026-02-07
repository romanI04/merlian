# STATUS — Merlian

## Product intent (commercial)
Build a **local-first "visual memory" app** that makes people say: *"Holy shit — it found the exact screenshot/image I meant."*
Primary wedge: **screenshots + downloaded images** (high volume, high pain). Privacy-first by default.

## Current state (what works today)

### Engine (`engine/`, Python)
- CLI: `merlian.py index/search/status/reset`
- Multi-folder indexing (pass multiple folders)
- Parallel CLIP+OCR indexing via ThreadPoolExecutor (~200 images in <30s)
- Pre-flight library size check (warns >5K images)
- Quality signals: textiness, quality_score, dup_group, recency — all active in search ranking
- Deduplication via perceptual hash (dup_group)
- Data stored at `~/Library/Application Support/Merlian/` (auto-migrated from old location)
- FastAPI server: `/health`, `/status`, `/index`, `/search`, `/warm`, `/warm-status`
- Demo endpoints: `/demo-search`, `/demo-thumb` (pre-computed, no live index needed)
- Smart folder detection: `/detect-folders`, `/check-permissions`
- Post-index suggestions: `/suggest-queries`
- Static frontend serving when `MERLIAN_SERVE_FRONTEND=1`
- Security: file/asset endpoints restricted to localhost + indexed paths

### Demo Dataset (`demo-dataset/`)
- 44 synthetic screenshots across 8 categories: errors, terminal, receipts, dashboards, messaging, settings, confirmations, code
- Generated via Playwright + Jinja2 (`engine/generate_demo_dataset.py`)
- Pre-computed CLIP embeddings + OCR catalog (`demo-catalog.json`, `demo-embeddings.npy`)
- Export script: `engine/export_demo_index.py`

### UI (Svelte, forked from Dispict)
- Welcome overlay: "Every screenshot you've ever taken. Findable in seconds."
- Demo gallery (`#/demo`) uses local engine's `/demo-search` (no external API dependency)
- Local mode (`#/local`) via hash routing
- Multi-folder Library modal with auto-detection + permission warnings
- "Build personal demo" (200 recent screenshots, fast)
- Post-index suggested queries with clickable chips
- Dark sidebar (stone-900) for local mode with rich metadata:
  - File creation date, size, dimensions, folder, OCR word count
  - OCR text with query-term highlighting (XSS-safe)
- 20+ starter prompts per mode (screenshot-focused)
- Model warm-up fires when Library modal opens
- Feedback toast after 5 searches

### DevOps
- `run-local.sh` with `--dev` / `--prod` flags + auto port discovery
- `install.sh` — one-command installer for macOS
- Claude commands: `/merlian`, `/demo`, `/ship`, `/landing`, `/fix`

## Known issues
- OCR quality on Playwright-rendered screenshots is mediocre (anti-aliased text confuses Apple Vision)
  - Error pages and receipts work well (large text), messaging screenshots are garbled
  - Could improve by using higher DPI rendering or different font rendering settings
- Demo dataset has 44 images (plan called for 120) — sufficient for demo but could be expanded

## What's needed for user testing
- Phase 8: Deploy web demo (Vercel + lightweight API), share installer, feedback collection
- README.md rewrite for public repo
- Create Tally/Typeform feedback form and link it in the toast

## How to run (dev)
```bash
./run-local.sh          # Dev mode (Vite HMR + API)
./run-local.sh --prod   # Production mode (single port)
```

Or manually:
```bash
cd engine && source .venv/bin/activate && uvicorn server:app --port 8008
cd dispict && npm run dev -- --host 127.0.0.1 --port 5173
```
