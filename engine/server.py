"""Merlian local API server (MVP)

This is a thin wrapper around the existing CLI logic so we can plug a UI into it.
Not production-ready.

Run:
  source .venv/bin/activate
  uvicorn server:app --reload --port 8008

Then:
  GET  http://127.0.0.1:8008/health
  GET  http://127.0.0.1:8008/status
  POST http://127.0.0.1:8008/index
  POST http://127.0.0.1:8008/search
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Literal

import threading
import time
import uuid
import re

from PIL import Image
import io
import os
import subprocess
import sys

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, Response

# Cache CLIP model/tokenizer per device for reliability + speed.
MODEL_CACHE: dict[str, tuple[str, str, Any, Any]] = {}
MODEL_LOCK = threading.Lock()

from pydantic import BaseModel, Field


class Job(BaseModel):
    id: str
    kind: Literal["index"]
    status: Literal["queued", "running", "done", "error", "cancelled"] = "queued"
    folder: str | None = None
    processed: int = 0
    total: int | None = None
    message: str | None = None
    error: str | None = None
    started_at: float | None = None
    finished_at: float | None = None

# Ensure local imports work regardless of working directory.
sys.path.insert(0, str(Path(__file__).parent))

# Reuse engine functions directly.
import merlian as core

app = FastAPI(title="Merlian Local API", version="0.1")


def _get_model(device: str, model_name: str, pretrained: str):
    key = f"{device}:{model_name}:{pretrained}"
    with MODEL_LOCK:
        if key in MODEL_CACHE:
            return MODEL_CACHE[key]

    model, _, _ = core.open_clip.create_model_and_transforms(
        model_name, pretrained=pretrained
    )
    tok = core.open_clip.get_tokenizer(model_name)
    model.to(device)
    model.eval()

    with MODEL_LOCK:
        MODEL_CACHE[key] = (model_name, pretrained, model, tok)

    return MODEL_CACHE[key]

# Dev-friendly: allow Vite dev server to call us.
app.add_middleware(
    CORSMiddleware,
    # Vite dev server may hop ports (5173, 5174, ...). Allow localhost on any port.
    allow_origin_regex=r"http://(localhost|127\.0\.0\.1):\d+",
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


class IndexRequest(BaseModel):
    folder: str | None = None
    folders: list[str] | None = None
    device: Literal["auto", "cpu", "mps"] = "auto"
    ocr: bool = True
    recent_only: bool = False
    max_items: int | None = Field(default=None, ge=1, le=5000)


# In-memory job store (MVP)
JOBS: dict[str, Job] = {}
JOB_LOCK = threading.Lock()
JOB_PROCS: dict[str, subprocess.Popen] = {}


class SearchRequest(BaseModel):
    query: str
    k: int = Field(default=12, ge=1, le=200)
    device: Literal["auto", "cpu", "mps"] = "auto"
    mode: Literal["clip", "ocr", "hybrid"] = "hybrid"
    ocr_weight: float = Field(default=0.55, ge=0.0, le=1.0)


class OpenRequest(BaseModel):
    path: str
    reveal: bool = False


def _normalize_path(p: str) -> Path:
    # Expand and normalize. No sandboxing yet (MVP), but we at least canonicalize.
    # Some frontend paths may accidentally append query params into this field (e.g. "...png?width=400").
    p = p.split("?", 1)[0]
    return Path(os.path.expanduser(p)).resolve()


def _require_localhost(req: Request) -> None:
    host = req.client.host if req.client else ""
    if host not in ("127.0.0.1", "::1"):
        raise HTTPException(status_code=403, detail="localhost only")


def _is_indexed(path: str) -> bool:
    # Only allow file operations on files that are already in the index.
    paths = core.get_dbpaths()
    if not paths.db.exists():
        return False
    conn = core.sqlite3.connect(paths.db)
    row = conn.execute("SELECT 1 FROM assets WHERE path=? LIMIT 1", (path,)).fetchone()
    return row is not None


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/thumb")
def thumb(req: Request, path: str, max_px: int = 640, width: int | None = None) -> Response:
    _require_localhost(req)

    # Enforce indexed-only access.
    raw = path.split("?", 1)[0]
    normalized = str(_normalize_path(raw))
    if not _is_indexed(normalized):
        raise HTTPException(status_code=403, detail="not indexed")

    p = Path(normalized)
    if not p.exists() or not p.is_file():
        raise HTTPException(status_code=404, detail="file not found")

    try:
        img = Image.open(p).convert("RGB")
        target = width if width is not None else max_px
        img.thumbnail((target, target))
        buf = io.BytesIO()
        img.save(buf, format="JPEG", quality=85)
        return Response(content=buf.getvalue(), media_type="image/jpeg")
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"cannot render: {e}")


@app.post("/open")
def open_path(http_req: Request, req: OpenRequest) -> dict[str, Any]:
    _require_localhost(http_req)

    p_norm = str(_normalize_path(req.path))
    if not _is_indexed(p_norm):
        raise HTTPException(status_code=403, detail="not indexed")

    p = Path(p_norm)
    if not p.exists() or not p.is_file():
        raise HTTPException(status_code=404, detail="file not found")

    if req.reveal:
        subprocess.run(["open", "-R", str(p)], check=False)
    else:
        subprocess.run(["open", str(p)], check=False)

    return {"ok": True}


@app.post("/pick-folder")
def pick_folder() -> dict[str, Any]:
    """Open a native folder picker (macOS) and return selected folder."""

    try:
        # Available via pyobjc-framework-Cocoa.
        from AppKit import NSOpenPanel

        panel = NSOpenPanel.openPanel()
        panel.setCanChooseFiles_(False)
        panel.setCanChooseDirectories_(True)
        panel.setAllowsMultipleSelection_(False)
        panel.setCanCreateDirectories_(False)
        panel.setTitle_("Choose a folder to index")
        panel.setPrompt_("Choose")

        result = panel.runModal()
        # NSModalResponseOK = 1
        if int(result) != 1:
            return {"ok": False, "cancelled": True}

        url = panel.URL()
        if url is None:
            return {"ok": False}

        path = str(url.path())
        return {"ok": True, "path": path}

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"picker failed: {e}")


@app.get("/detect-folders")
def detect_folders() -> dict[str, Any]:
    """Detect common screenshot/image folders on macOS."""
    candidates = [
        Path.home() / "Desktop",
        Path.home() / "Pictures" / "Screenshots",
        Path.home() / "Downloads",
    ]

    # Check macOS screencapture location
    try:
        result = subprocess.run(
            ["defaults", "read", "com.apple.screencapture", "location"],
            capture_output=True, text=True, timeout=5,
        )
        if result.returncode == 0 and result.stdout.strip():
            custom = Path(result.stdout.strip()).expanduser()
            if custom.is_dir() and custom not in candidates:
                candidates.insert(0, custom)
    except Exception:
        pass

    folders: list[dict] = []
    for folder in candidates:
        if not folder.exists():
            continue
        # Quick count: non-recursive scandir for speed
        count = 0
        accessible = True
        try:
            for entry in os.scandir(folder):
                if entry.is_file() and entry.name.lower().split(".")[-1] in ("png", "jpg", "jpeg", "webp"):
                    count += 1
        except PermissionError:
            accessible = False
        except Exception:
            pass

        folders.append({
            "path": str(folder),
            "count": count,
            "accessible": accessible,
        })

    return {"folders": folders}


@app.get("/check-permissions")
def check_permissions() -> dict[str, Any]:
    """Check filesystem permissions for detected folders."""
    det = detect_folders()
    accessible = [f for f in det["folders"] if f["accessible"]]
    denied = [f for f in det["folders"] if not f["accessible"]]
    suggestion = ""
    if denied:
        suggestion = "Grant Full Disk Access in System Preferences > Privacy & Security > Full Disk Access"
    return {
        "accessible": accessible,
        "denied": denied,
        "suggestion": suggestion,
    }


@app.post("/suggest-queries")
def suggest_queries() -> dict[str, Any]:
    """Suggest relevant search queries based on indexed OCR content."""
    paths = core.get_dbpaths()
    if not paths.db.exists():
        return {"suggestions": []}

    conn = core.sqlite3.connect(paths.db)
    rows = conn.execute(
        "SELECT ocr_text FROM assets WHERE length(COALESCE(ocr_text,'')) > 20 ORDER BY mtime DESC LIMIT 500"
    ).fetchall()

    if not rows:
        return {"suggestions": []}

    # Score against known patterns
    import re as _re
    patterns = [
        (_re.compile(r'\$\d+|total|invoice|receipt', _re.I), "receipt or invoice", 0),
        (_re.compile(r'error|exception|traceback|failed|errno', _re.I), "error message", 0),
        (_re.compile(r'confirm|code|verification|OTP|2FA', _re.I), "confirmation code", 0),
        (_re.compile(r'meeting|calendar|invite|schedule|agenda', _re.I), "calendar or meeting", 0),
        (_re.compile(r'dashboard|analytics|chart|graph|metrics', _re.I), "dashboard or chart", 0),
        (_re.compile(r'terminal|bash|\$\s|>>>', _re.I), "terminal output", 0),
        (_re.compile(r'order|shipping|tracking|delivered', _re.I), "order or shipping", 0),
    ]

    # Count matches
    scored = []
    for pattern, label, _ in patterns:
        hits = sum(1 for (txt,) in rows if pattern.search(txt or ""))
        if hits > 0:
            scored.append({"query": label, "confidence": min(1.0, hits / 20.0), "hits": hits})

    scored.sort(key=lambda x: x["confidence"], reverse=True)
    return {"suggestions": scored[:3]}


@app.get("/warm-status")
def warm_status() -> dict[str, Any]:
    """Non-blocking check if CLIP model is already cached/loaded."""
    cached = _is_model_cached()
    loaded = len(MODEL_CACHE) > 0
    if loaded:
        return {"status": "ready", "cached": True, "loaded": True}
    elif cached:
        return {"status": "cached", "cached": True, "loaded": False, "message": "Model cached, loading..."}
    else:
        return {"status": "downloading", "cached": False, "loaded": False, "message": "Downloading AI model (577 MB)..."}


def _is_model_cached(model_name: str = "ViT-B-32", pretrained: str = "laion2b_s34b_b79k") -> bool:
    """Check if CLIP model weights are already downloaded."""
    cache_dir = Path.home() / ".cache" / "huggingface" / "hub"
    if cache_dir.exists():
        # open_clip stores in huggingface cache; check for any matching blob
        for p in cache_dir.rglob("*.bin"):
            if p.stat().st_size > 300_000_000:  # >300MB = likely the model
                return True
    # Also check open_clip's own cache
    oc_cache = Path.home() / ".cache" / "open_clip"
    if oc_cache.exists():
        for p in oc_cache.rglob("*"):
            if p.stat().st_size > 300_000_000:
                return True
    return False


@app.post("/warm")
def warm(device: Literal["auto", "cpu", "mps"] = "auto") -> dict[str, Any]:
    """Warm the CLIP model so first search is instant."""
    if device == "auto":
        device = "mps" if core.torch.backends.mps.is_available() else "cpu"

    model_name = "ViT-B-32"
    pretrained = "laion2b_s34b_b79k"

    # Check if we have a pre-existing index with model info
    paths = core.get_dbpaths()
    if paths.meta.exists():
        meta = core.json.loads(paths.meta.read_text())
        model_name = meta.get("model", {}).get("name", model_name)
        pretrained = meta.get("model", {}).get("pretrained", pretrained)

    cached = _is_model_cached(model_name, pretrained)

    _get_model(device, model_name, pretrained)
    return {
        "ok": True,
        "device": device,
        "model": {"name": model_name, "pretrained": pretrained},
        "was_cached": cached,
        "status": "ready",
    }


@app.get("/status")
def status() -> dict[str, Any]:
    paths = core.get_dbpaths()

    if not paths.root.exists() or not paths.meta.exists() or not paths.db.exists():
        return {"indexed": False}

    meta = core.json.loads(paths.meta.read_text())
    embs = core.load_embeddings(paths.embeddings)
    n_embs = int(embs.shape[0]) if embs is not None else 0

    conn = core.sqlite3.connect(paths.db)
    total = conn.execute("SELECT count(*) FROM assets").fetchone()[0]
    with_ocr = conn.execute(
        "SELECT count(*) FROM assets WHERE length(coalesce(ocr_text,'')) > 0"
    ).fetchone()[0]
    last_indexed_at = conn.execute("SELECT MAX(indexed_at) FROM assets").fetchone()[0]

    return {
        "indexed": True,
        "root": meta.get("root"),
        "roots": meta.get("roots", [meta.get("root")] if meta.get("root") else []),
        "model": meta.get("model"),
        "assets": int(total),
        "with_ocr": int(with_ocr),
        "embeddings": int(n_embs),
        "last_indexed_at": last_indexed_at,
        "data_dir": str(paths.root),
    }


def _job_update(job_id: str, **patch: Any) -> None:
    with JOB_LOCK:
        j = JOBS.get(job_id)
        if not j:
            return
        data = j.model_dump()
        data.update(patch)
        JOBS[job_id] = Job(**data)


def _run_index_job(job_id: str, folders: list[str], device: str, ocr: bool, recent_only: bool, max_items: int | None) -> None:
    _job_update(job_id, status="running", started_at=time.time(), message="Starting…")

    # Use the CLI as a subprocess so we can parse progress without major refactors.
    # This also isolates any native-library issues.
    cmd = [
        sys.executable,
        "-u",
        str(Path(__file__).parent / "merlian.py"),
        "index",
    ]
    for f in folders:
        cmd.append(f)
    cmd.extend(["--device", device])
    cmd.append("--ocr" if ocr else "--no-ocr")
    if recent_only:
        cmd.append("--recent-only")
    if max_items is not None:
        cmd.extend(["--max-items", str(int(max_items))])

    try:
        proc = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
        )
        JOB_PROCS[job_id] = proc

        # Parse progress lines like: “… processed 75/121”
        prog_re = re.compile(r"processed\s+(\d+)/(\d+)")

        for line in proc.stdout or []:
            line = line.strip()
            m = prog_re.search(line)
            if m:
                _job_update(
                    job_id,
                    processed=int(m.group(1)),
                    total=int(m.group(2)),
                    message=line,
                )
            elif line.startswith("Done.") or line.startswith("Done"):
                _job_update(job_id, message=line)

            # cancelled?
            with JOB_LOCK:
                if JOBS.get(job_id) and JOBS[job_id].status == "cancelled":
                    try:
                        proc.terminate()
                    except Exception:
                        pass
                    break

        rc = proc.wait()

        # If cancelled, keep it cancelled.
        with JOB_LOCK:
            st = JOBS.get(job_id).status if JOBS.get(job_id) else None

        if st == "cancelled":
            _job_update(job_id, finished_at=time.time(), message="Cancelled")
        elif rc == 0:
            _job_update(job_id, status="done", finished_at=time.time(), processed=JOBS[job_id].processed, total=JOBS[job_id].total)
        else:
            _job_update(job_id, status="error", finished_at=time.time(), error=f"Indexing failed (code {rc})")

    except Exception as e:
        _job_update(job_id, status="error", finished_at=time.time(), error=str(e))
    finally:
        JOB_PROCS.pop(job_id, None)


@app.get("/jobs/{job_id}")
def get_job(job_id: str) -> Job:
    with JOB_LOCK:
        j = JOBS.get(job_id)
        if not j:
            raise HTTPException(status_code=404, detail="job not found")
        return j


@app.post("/jobs/{job_id}/cancel")
def cancel_job(job_id: str) -> Job:
    with JOB_LOCK:
        j = JOBS.get(job_id)
        if not j:
            raise HTTPException(status_code=404, detail="job not found")
        if j.status in ("done", "error"):
            return j
        JOBS[job_id] = Job(**{**j.model_dump(), "status": "cancelled"})

    proc = JOB_PROCS.get(job_id)
    if proc:
        try:
            proc.terminate()
        except Exception:
            pass

    return get_job(job_id)


@app.post("/index")
def index(req: IndexRequest) -> dict[str, Any]:
    # Support both single folder and multi-folder
    folders: list[str] = []
    if req.folders:
        folders = [str(Path(f).expanduser()) for f in req.folders]
    elif req.folder:
        folders = [str(Path(req.folder).expanduser())]

    job_id = uuid.uuid4().hex
    job = Job(id=job_id, kind="index", status="queued", folder=folders[0] if folders else None, processed=0, total=None)

    with JOB_LOCK:
        JOBS[job_id] = job

    t = threading.Thread(
        target=_run_index_job,
        args=(job_id, folders, req.device, req.ocr, bool(req.recent_only), req.max_items),
        daemon=True,
    )
    t.start()

    return {"job_id": job_id}


@app.post("/search")
def search(req: SearchRequest) -> dict[str, Any]:
    paths = core.get_dbpaths()
    if not paths.embeddings.exists() or not paths.meta.exists():
        return {"results": []}

    meta = core.json.loads(paths.meta.read_text())
    embs = core.load_embeddings(paths.embeddings)
    if embs is None:
        return {"results": []}

    # Use the same scoring code by calling the click command callback.
    # The callback prints; we want data. So we reimplement the core scoring here in a small way.

    # Compute scores using core's internal logic.
    # NOTE: This duplicates logic from core.search; kept minimal for now.
    if req.device == "auto":
        device = "mps" if core.torch.backends.mps.is_available() else "cpu"
    else:
        device = req.device

    paths_list = list(meta.get("paths", []))

    model_name = meta.get("model", {}).get("name", "ViT-B-32")
    pretrained = meta.get("model", {}).get("pretrained", "laion2b_s34b_b79k")

    _, _, model, tokenizer = _get_model(device, model_name, pretrained)

    q = core.text_embedding(model, tokenizer, device, req.query)
    clip_scores = (embs @ q.reshape(-1, 1)).reshape(-1)

    # OCR score via existing search logic: call into SQLite.
    q_tokens = [
        t
        for t in core.re.split(r"[^a-zA-Z0-9]+", req.query.lower())
        if len(t) >= 3 or t.isdigit()
    ]
    ocr_scores = core.np.zeros_like(clip_scores)

    if q_tokens:
        conn = core.sqlite3.connect(paths.db)
        match_and = " AND ".join(q_tokens)
        match_or = " OR ".join(q_tokens)
        rows = conn.execute(
            """
            SELECT path, bm25(ocr_fts) as score
            FROM ocr_fts
            WHERE ocr_fts MATCH ?
            ORDER BY score
            LIMIT 2000
            """,
            (match_and,),
        ).fetchall()
        if not rows and len(q_tokens) > 1:
            rows = conn.execute(
                """
                SELECT path, bm25(ocr_fts) as score
                FROM ocr_fts
                WHERE ocr_fts MATCH ?
                ORDER BY score
                LIMIT 2000
                """,
                (match_or,),
            ).fetchall()

        if rows:
            raw = core.np.array([float(r[1]) for r in rows], dtype="float32")
            best = float(raw.min())
            worst = float(raw.max())
            denom = max(1e-6, worst - best)
            score_map = {}
            for (p, s) in rows:
                s = float(s)
                norm = 1.0 - ((s - best) / denom)
                score_map[str(p)] = float(norm)
            for i, p in enumerate(paths_list):
                v = score_map.get(p)
                if v is not None:
                    ocr_scores[i] = v
        else:
            digit_tokens = [t for t in q_tokens if t.isdigit()]
            if digit_tokens:
                clauses = " OR ".join(["ocr_text LIKE ?" for _ in digit_tokens])
                like_args = [f"%{t}%" for t in digit_tokens]
                like_rows = conn.execute(
                    f"SELECT path FROM assets WHERE {clauses} LIMIT 2000",
                    tuple(like_args),
                ).fetchall()
                for (p,) in like_rows:
                    try:
                        i = paths_list.index(str(p))
                        ocr_scores[i] = max(ocr_scores[i], 0.95)
                    except ValueError:
                        pass

    if req.mode == "clip":
        scores = clip_scores
    elif req.mode == "ocr":
        scores = ocr_scores
    else:
        # hybrid — per-asset OCR weighting based on textiness (1.1)
        conn_sig = core.sqlite3.connect(paths.db)
        base_w = float(req.ocr_weight)

        # Build per-asset arrays for quality signals
        n_assets = len(paths_list)
        textiness_arr = core.np.full(n_assets, 0.0, dtype="float32")
        quality_arr = core.np.full(n_assets, 0.5, dtype="float32")
        mtime_arr = core.np.full(n_assets, 0.0, dtype="float32")
        dup_group_arr: list[str] = [""] * n_assets

        ph = ",".join(["?"] * n_assets) if n_assets else ""
        if n_assets:
            rows_sig = conn_sig.execute(
                f"SELECT path, COALESCE(textiness,0), COALESCE(quality_score,0.5), COALESCE(mtime,0), COALESCE(dup_group,'') FROM assets WHERE path IN ({ph})",
                tuple(paths_list),
            ).fetchall()
            sig_map = {r[0]: r[1:] for r in rows_sig}
            for i, p in enumerate(paths_list):
                vals = sig_map.get(p)
                if vals:
                    textiness_arr[i] = float(vals[0])
                    quality_arr[i] = float(vals[1])
                    mtime_arr[i] = float(vals[2])
                    dup_group_arr[i] = str(vals[3])

        # 1.1: Per-asset OCR weight based on textiness
        q_lower = req.query.lower()
        has_digits = any(ch.isdigit() for ch in req.query)
        texty_keywords = [
            "error", "code", "http", "forbidden", "denied",
            "invoice", "receipt", "total", "$", "usd", "cad",
        ]
        looks_texty = has_digits or any(k in q_lower for k in texty_keywords)
        if looks_texty:
            base_w = max(base_w, 0.80)

        w_per = core.np.clip(base_w + 0.25 * textiness_arr, 0.0, 1.0)
        scores = (1.0 - w_per) * clip_scores + w_per * ocr_scores

        # 1.2: Quality score dampening
        scores *= (0.3 + 0.7 * quality_arr)

        # 1.3: Recency bias
        import time as _time
        now_ts = _time.time()
        days_ago = (now_ts - mtime_arr) / 86400.0
        recency = 1.0 + 0.15 * core.np.clip(1.0 - days_ago / 365.0, 0.0, 1.0)
        scores *= recency

    # 1.4: Deduplication via dup_group — pull extra candidates, then deduplicate
    if req.mode == "hybrid":
        # Get more candidates than needed, then deduplicate
        candidate_k = min(len(scores), req.k * 3)
        all_sorted = core.np.argsort(-scores)[:candidate_k]
        seen_groups: set[str] = set()
        topk_list: list[int] = []
        for idx in all_sorted:
            dg = dup_group_arr[int(idx)]
            if dg and dg in seen_groups:
                continue
            if dg:
                seen_groups.add(dg)
            topk_list.append(int(idx))
            if len(topk_list) >= req.k:
                break
        topk = core.np.array(topk_list, dtype=int)
    else:
        topk = core.np.argsort(-scores)[: req.k]

    # Pull OCR preview + metadata for just the top results.
    conn = core.sqlite3.connect(paths.db)
    top_paths = [paths_list[int(i)] for i in topk]
    ph = ",".join(["?"] * len(top_paths)) if top_paths else ""
    ocr_preview: dict[str, str] = {}
    asset_meta: dict[str, dict] = {}
    if top_paths:
        rows = conn.execute(
            f"SELECT path, COALESCE(ocr_text,''), size_bytes, mtime, width, height FROM assets WHERE path IN ({ph})",
            tuple(top_paths),
        ).fetchall()
        for p, txt, sz, mt, aw, ah in rows:
            t = (txt or "").replace("\n", " ").strip()
            if len(t) > 300:
                t = t[:300] + "…"
            ocr_preview[str(p)] = t
            asset_meta[str(p)] = {"file_size": sz, "mtime": mt, "db_width": aw, "db_height": ah}

    results = []
    for idx_id in topk:
        p = paths_list[int(idx_id)]
        meta_info = asset_meta.get(p, {})
        w = meta_info.get("db_width")
        h = meta_info.get("db_height")
        if not w or not h:
            try:
                with Image.open(p) as im:
                    w, h = im.size
            except Exception:
                pass

        # Compute matched tokens for highlighting
        ocr_text_full = ocr_preview.get(p, "")
        matched = [t for t in q_tokens if t in ocr_text_full.lower()] if q_tokens else []

        # File metadata for sidebar
        file_path = Path(p)
        folder_path = str(file_path.parent)
        file_size = meta_info.get("file_size", 0)
        created_at = meta_info.get("mtime", 0)

        results.append(
            {
                "path": p,
                "score": float(scores[int(idx_id)]),
                "clip": float(clip_scores[int(idx_id)]),
                "ocr": float(ocr_scores[int(idx_id)]),
                "ocr_preview": ocr_preview.get(p, ""),
                "matched_tokens": matched,
                "width": w,
                "height": h,
                "file_size": file_size,
                "created_at": created_at,
                "folder": folder_path,
                "thumb_url": f"/thumb?path={p}",
            }
        )

    return {"results": results, "matched_tokens": q_tokens}


# ── Demo search (pre-computed, no live index needed) ──────────────────────────

DEMO_CATALOG: list[dict] | None = None
DEMO_EMBEDDINGS: Any = None
DEMO_DIR = Path(__file__).parent.parent / "demo-dataset"

def _load_demo_data():
    global DEMO_CATALOG, DEMO_EMBEDDINGS
    if DEMO_CATALOG is not None:
        return
    catalog_path = DEMO_DIR / "demo-catalog.json"
    emb_path = DEMO_DIR / "demo-embeddings.npy"
    if not catalog_path.exists() or not emb_path.exists():
        return
    import json as _json
    with open(catalog_path) as f:
        DEMO_CATALOG = _json.load(f)
    emb = core.np.load(str(emb_path))
    # Normalize for cosine similarity
    norms = core.np.linalg.norm(emb, axis=1, keepdims=True)
    norms[norms == 0] = 1
    DEMO_EMBEDDINGS = emb / norms


@app.post("/demo-search")
def demo_search(req: SearchRequest):
    _load_demo_data()
    if DEMO_CATALOG is None or DEMO_EMBEDDINGS is None:
        raise HTTPException(status_code=503, detail="Demo data not available. Run export_demo_index.py first.")

    if req.device == "auto":
        device = "mps" if core.torch.backends.mps.is_available() else "cpu"
    else:
        device = req.device
    model_name = "ViT-B-32"
    pretrained = "laion2b_s34b_b79k"
    _, _, model, tokenizer = _get_model(device, model_name, pretrained)

    # Encode query with CLIP
    tokens = tokenizer([req.query])
    with core.torch.no_grad():
        text_features = model.encode_text(tokens.to(device))
    text_features = text_features.cpu().numpy().astype("float32")
    text_features /= core.np.linalg.norm(text_features, axis=1, keepdims=True)

    # CLIP similarity
    clip_scores = (DEMO_EMBEDDINGS @ text_features.T).flatten()

    # OCR scoring
    q_lower = req.query.lower()
    q_tokens = re.findall(r'\w+', q_lower)
    n = len(DEMO_CATALOG)
    ocr_scores = core.np.zeros(n, dtype="float32")
    for i, item in enumerate(DEMO_CATALOG):
        ocr_text = (item.get("ocr_text") or "").lower()
        if not ocr_text or not q_tokens:
            continue
        # Simple token match scoring
        matches = sum(1 for t in q_tokens if t in ocr_text)
        if matches > 0:
            ocr_scores[i] = matches / len(q_tokens)

    # Hybrid scoring with quality signals
    base_w = float(req.ocr_weight)
    has_digits = any(ch.isdigit() for ch in req.query)
    texty_keywords = ["error", "code", "http", "receipt", "total", "$", "invoice"]
    if has_digits or any(k in q_lower for k in texty_keywords):
        base_w = max(base_w, 0.80)

    textiness_arr = core.np.array([item.get("textiness", 0.0) for item in DEMO_CATALOG], dtype="float32")
    quality_arr = core.np.array([item.get("quality_score", 0.5) for item in DEMO_CATALOG], dtype="float32")

    w_per = core.np.clip(base_w + 0.25 * textiness_arr, 0.0, 1.0)
    scores = (1.0 - w_per) * clip_scores + w_per * ocr_scores
    scores *= (0.3 + 0.7 * quality_arr)

    # Top-k
    k = min(req.k, n)
    topk = core.np.argsort(-scores)[:k]

    results = []
    for idx in topk:
        idx = int(idx)
        item = DEMO_CATALOG[idx]
        ocr_text = (item.get("ocr_text") or "").replace("\n", " ").strip()
        if len(ocr_text) > 300:
            ocr_text = ocr_text[:300] + "…"
        matched = [t for t in q_tokens if t in (item.get("ocr_text") or "").lower()] if q_tokens else []
        rel_path = item["path"]
        results.append({
            "path": rel_path,
            "score": float(scores[idx]),
            "clip": float(clip_scores[idx]),
            "ocr": float(ocr_scores[idx]),
            "ocr_preview": ocr_text,
            "matched_tokens": matched,
            "width": item.get("width", 1440),
            "height": item.get("height", 900),
            "file_size": 0,
            "created_at": item.get("mtime", 0),
            "folder": str(Path(rel_path).parent),
            "thumb_url": f"/demo-thumb?path={rel_path}",
        })

    return {"results": results, "matched_tokens": q_tokens}


@app.get("/demo-thumb")
def demo_thumb(path: str, width: int = 400) -> Response:
    # Serve thumbnail from demo-dataset directory
    safe_path = path.replace("..", "").lstrip("/")
    full_path = DEMO_DIR / safe_path
    if not full_path.exists() or not full_path.is_file():
        raise HTTPException(status_code=404, detail="not found")
    # Ensure path is within demo-dataset
    try:
        full_path.resolve().relative_to(DEMO_DIR.resolve())
    except ValueError:
        raise HTTPException(status_code=403, detail="forbidden")
    try:
        img = Image.open(full_path).convert("RGB")
        img.thumbnail((width, width))
        buf = io.BytesIO()
        img.save(buf, format="JPEG", quality=85)
        return Response(content=buf.getvalue(), media_type="image/jpeg")
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"cannot render: {e}")


# Static file serving: serve built frontend from FastAPI when MERLIAN_SERVE_FRONTEND=1
# This allows single-process deployment (one port for API + frontend).
if os.environ.get("MERLIAN_SERVE_FRONTEND") == "1":
    dist_dir = Path(__file__).parent.parent / "dispict" / "dist"
    if dist_dir.is_dir():
        from fastapi.staticfiles import StaticFiles
        app.mount("/", StaticFiles(directory=str(dist_dir), html=True), name="frontend")
