# Merlian engine (thin-slice)

This folder contains a minimal CLI prototype to validate the local-first core:

- index a folder of images (compute CLIP embeddings locally)
- search by text and print top matches

## Setup

```bash
cd engine
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Index

```bash
source .venv/bin/activate

# first run (builds index)
python merlian.py index ~/Desktop

# subsequent runs are incremental (fast): only new/changed files are processed
python merlian.py index ~/Desktop

# or re-index the last folder (no argument)
python merlian.py index
```

### macOS permissions note
If you see `Directory '.../Desktop' is not readable`, macOS is blocking terminal access.
Grant your terminal (or the app running this command) access in:
- System Settings → Privacy & Security → **Files and Folders** (Desktop), or
- System Settings → Privacy & Security → **Full Disk Access**

As a quick workaround, copy a few images into a folder under this repo (e.g. `~/clawd/projects/merlian/test-images/`) and index that.

## Search

```bash
source .venv/bin/activate

# hybrid ranking (CLIP + OCR) by default
python merlian.py search "red sneaker" --k 10

# open the top result
python merlian.py search "red sneaker" --k 10 --open 1

# reveal result #3 in Finder
python merlian.py search "red sneaker" --k 10 --reveal 3

# force OCR-only search (great for text-heavy screenshots)
python merlian.py search "RESOLV" --k 10 --mode ocr --open 1
```

## Status

```bash
source .venv/bin/activate
python merlian.py status
```

## Reset

```bash
source .venv/bin/activate
python merlian.py reset
```

## Local API (for UI integration)

```bash
source .venv/bin/activate
uvicorn server:app --reload --port 8008
```

Endpoints:
- `GET /health`
- `GET /status`
- `POST /index`  (JSON: `{ "folder": "~/Desktop", "ocr": true }`)
- `POST /search` (JSON: `{ "query": "error 403", "k": 10 }`)

### Notes
- Index artifacts are stored under `engine/.merlian/` (repo-local for now).
- This is not optimized; it’s a validation harness.
