# Merlian

Merlian is a **local-first visual search** tool: describe what you remember, retrieve the right screenshot/image.

It supports **hybrid search**:
- what an image *looks like* (visual embeddings)
- what an image *says* (OCR text inside screenshots)

## What you can do
- Index a folder (Desktop / Screenshots / Downloads)
- Search in plain language: “error 403”, “invoice total”, “dark mode dashboard”, “chart about inflation”
- Open or reveal the result instantly

---

## Quickstart (UI)

### 1) Start the local engine API
```bash
cd engine
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn server:app --port 8008
```

### 2) Start the UI
```bash
cd dispict
npm install
npm run dev -- --host 127.0.0.1 --port 5173
```

Open:
- Demo gallery: <http://127.0.0.1:5173/#/demo>
- Local search: <http://127.0.0.1:5173/#/local>

---

## Demo dataset
The demo gallery uses the **Harvard Art Museums** dataset.

See: `CREDITS.md`.
