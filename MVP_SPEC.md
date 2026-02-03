# Merlian — Local‑First MVP Spec (Draft)

**Goal:** A desktop-first, local-only app that indexes images/screenshots on disk and lets you retrieve them by typing what you remember.

This spec is intentionally **thin-slice**: one user, one machine, one library.

---

## 0) Non-goals (MVP)

- No accounts, auth, teams, sharing
- No cloud uploads/sync
- No mobile
- No “collections” or complex organization
- No heavy editing/annotation workflows
- No external hosting of user files (privacy-first)

---

## 1) Core user story

> “I took/saved a screenshot or image. Later I remember what it *looks like* or *contains*, but not the filename or folder. I type a description and open the right image in seconds.”

Success = user finds **5–10 previously hard-to-find images** in <3 minutes.

---

## 2) MVP features (must-have)

### 2.1 Library management
- Add one or more **folders** to index.
- Recursively scan for supported files.
- Show status: number of images, last indexed time.

Supported file types (MVP):
- `.png`, `.jpg/.jpeg`, `.webp` (optional later: `.heic`)

### 2.2 Indexing pipeline (local)
- Generate a **stable file id** (path + inode or hash) for dedupe.
- Extract basic metadata:
  - path, filename, size, mtime, dimensions
- Generate a **thumbnail** (fast preview)
- Compute **image embeddings** (local)
- Store embeddings + metadata in a local DB

### 2.3 Search
- Text query → compute text embedding
- Nearest-neighbor retrieval (top-k)
- Show results grid (thumbnail + filename/path)
- Click result → open preview/details
- Open in Finder / open file with default app

### 2.4 Updates / incremental indexing
- Re-scan folders on demand (button)
- Detect changes:
  - new files → index
  - deleted files → remove
  - modified files → re-index (if mtime/size differs)

---

## 3) “Wow effect” UX (MVP)

- Very fast search feedback (sub-second for top results once indexed)
- Example queries / onboarding chips
- Keyboard-first flow:
  - `Cmd+K` focus search (if desktop app)
  - arrows to select result
  - `Enter` to open

---

## 4) Architecture (proposed)

### 4.1 Recommended stack (fast path)

**Desktop app:** Tauri (Rust shell) + web UI (Svelte/React)
- Pros: lightweight, good for “Spotlight-like” UX, simple packaging
- Cons: slightly more plumbing

**Core engine:** Python service (local)
- Fast iteration for embeddings/indexing
- Reuse existing CLIP/OpenCLIP tooling

**Vector search:** FAISS (CPU) or sqlite-vss (later)
- MVP: FAISS flat index (simple + reliable)

**Metadata store:** SQLite
- Single-file DB, easy migrations

**Thumbnails:** stored as files under app data dir or as blobs in SQLite

> Alternative (later): all-Rust engine using candle + tantivy/annoy-like index, but that’s slower to build now.

### 4.2 Process boundaries

Option A (simplest):
- Desktop UI calls a **local HTTP API** (Python FastAPI)

Option B (tighter):
- UI talks to Rust, Rust invokes Python via stdin/stdout or embedded

For MVP speed + debugging: **Option A**.

---

## 5) Data model (SQLite)

Tables (suggested):

### `libraries`
- `id` (pk)
- `path` (unique)
- `created_at`, `updated_at`

### `assets`
- `id` (pk)
- `library_id` (fk)
- `path` (unique within library)
- `mtime`, `size_bytes`
- `width`, `height`
- `sha256` (optional; expensive)
- `thumb_path` (or blob)
- `indexed_at`

### `embeddings`
- `asset_id` (pk/fk)
- `model` (text)
- `dim` (int)
- `vector` (blob) OR stored separately in FAISS index

---

## 6) Embedding model choice (MVP)

**Default recommendation:** OpenCLIP ViT-B/32 (local)
- Good enough quality
- Reasonable CPU performance

Compute modes:
- CPU by default
- Optional GPU acceleration later

---

## 7) Performance targets (MVP)

- Indexing: incremental; initial index time depends on dataset size
- Search: top-k results in < 500ms after index is warm
- Memory: stable for 10k images (prototype target)

---

## 8) Privacy & security (MVP)

- All processing local
- No network calls required for user libraries
- Clear statement in UI: “Files never leave your machine”

---

## 9) Milestones (thin-slice)

### M1 — CLI prototype (1–2 days)
- `merlian index <folder>`
- `merlian search "query"` → prints top file paths

### M2 — Minimal desktop UI (2–4 days)
- Folder picker
- Index status
- Search box + results grid

### M3 — Incremental updates + polish (2–3 days)
- Rescan
- Deletions/updates
- Open in Finder

---

## 10) Open questions

1) Do we require HEIC (Mac screenshots can be PNG by default, but many photos are HEIC)?
2) Do we store embeddings inside SQLite blobs, or always externalize to FAISS?
3) Packaging: bundle Python runtime vs require user to install?

---

## 11) Next step (for this sprint)

- Validate the thin-slice via a CLI prototype (M1)
- Decide stack final (Tauri+Python vs Electron+Python)
- Define how we’ll package/distribute a local engine without user pain
