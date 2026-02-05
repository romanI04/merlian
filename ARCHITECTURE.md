# Merlian — Architecture (current)

Merlian is built as a **local-first system**:

- **UI:** Svelte (forked/accelerated from Dispict)
- **Engine:** Python (local), provides indexing + retrieval
- **API:** FastAPI over localhost (127.0.0.1)

## Data + privacy
- User files are never uploaded.
- Index artifacts are stored locally under `engine/.merlian/` (repo-local for now).
- File endpoints are restricted to **localhost + indexed paths only**.

## Core pipeline (v1)
1) Scan library folders
2) Extract metadata + thumbnails
3) OCR screenshots (Apple Vision)
4) Compute visual embeddings (OpenCLIP)
5) Store metadata in SQLite + OCR FTS
6) Store vectors in `embeddings.npy`

## Why this split (UI + local API)
- Iterate quickly on retrieval + onboarding
- Keep UI responsive
- Maintain a clean boundary for future packaging (Tauri wrapper)

## Planned evolution
- Replace repo-local storage with app data directory
- Add OCR region bboxes for evidence highlights
- Improve dedupe + gallery shaping signals
- Bundle engine for distribution
