# Merlian

**Merlian is a local-first visual memory app for screenshots and images.**
Type what you remember → get the exact capture instantly, with evidence (OCR preview/highlight) and one-click actions.

**Positioning (v1):** *Spotlight for screenshots — private and evidence-based.*

---

## Who it’s for (v1)
**Screenshot power users on macOS** who capture information to “remember later,” then can’t reliably retrieve it:
- Engineers: errors, configs, dashboards, docs
- PM/ops/analysts: admin panels, receipts, confirmations, metrics
- Students/researchers: slides, papers, charts

## Why it matters
Screenshots are the modern “memory prosthetic.” The problem is they’re unstructured: Finder/Spotlight are filename/path-first, and cloud AI search has a privacy ceiling.

Merlian’s contract:
- **Local-only** (files never leave your machine)
- **Fast** (instant-feeling retrieval once warm)
- **Evidence-first** (shows why it matched)
- **Actionable** (open/reveal/copy in one click)

---

## Demo vs Product
Merlian has two modes:
- **Demo gallery**: a curated dataset (Harvard Art Museums) to prove the core retrieval loop
- **Local mode (the product)**: your own library, indexed locally (OCR + embeddings)

The commercial product must be a direct proof of what the demo shows:
> type natural language → instantly get the right visual thing → click → see it.

---

## Quickstart (dev)
### One-command runner
```bash
./run-local.sh
```

Open:
- Demo gallery: <http://127.0.0.1:5173/#/demo>
- Local search: <http://127.0.0.1:5173/#/local>

### Manual
Engine API:
```bash
cd engine
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn server:app --port 8008
```

UI:
```bash
cd ui
npm install
npm run dev -- --host 127.0.0.1 --port 5173
```

---

## Product docs (read these first)
- **Product definition:** `PRODUCT.md`
- **Build plan:** `TASKS.md`
- **Credits / dataset:** `CREDITS.md`

---

## Notes
- This repo started as a fork/accelerator from **Dispict** (MIT). See `CREDITS.md`.
- Current focus is commercial v1: a "personal demo" onboarding + curated local gallery + evidence-first results.
