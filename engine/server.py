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

from fastapi import FastAPI, HTTPException
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
    device: Literal["auto", "cpu", "mps"] = "auto"
    ocr: bool = True


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


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/thumb")
def thumb(path: str, max_px: int = 640, width: int | None = None) -> Response:
    p = _normalize_path(path)
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
def open_path(req: OpenRequest) -> dict[str, Any]:
    p = _normalize_path(req.path)
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


@app.post("/warm")
def warm(device: Literal["auto", "cpu", "mps"] = "auto") -> dict[str, Any]:
    """Warm the CLIP model so first search is instant."""
    if device == "auto":
        device = "mps" if core.torch.backends.mps.is_available() else "cpu"

    paths = core.get_dbpaths()
    if not paths.meta.exists():
        return {"ok": False, "error": "no index"}

    meta = core.json.loads(paths.meta.read_text())
    model_name = meta.get("model", {}).get("name", "ViT-B-32")
    pretrained = meta.get("model", {}).get("pretrained", "laion2b_s34b_b79k")

    _get_model(device, model_name, pretrained)
    return {"ok": True, "device": device, "model": {"name": model_name, "pretrained": pretrained}}


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
        "model": meta.get("model"),
        "assets": int(total),
        "with_ocr": int(with_ocr),
        "embeddings": int(n_embs),
        "last_indexed_at": last_indexed_at,
    }


def _job_update(job_id: str, **patch: Any) -> None:
    with JOB_LOCK:
        j = JOBS.get(job_id)
        if not j:
            return
        data = j.model_dump()
        data.update(patch)
        JOBS[job_id] = Job(**data)


def _run_index_job(job_id: str, folder: str | None, device: str, ocr: bool) -> None:
    _job_update(job_id, status="running", started_at=time.time(), message="Starting…")

    # Use the CLI as a subprocess so we can parse progress without major refactors.
    # This also isolates any native-library issues.
    cmd = [
        sys.executable,
        "-u",
        str(Path(__file__).parent / "merlian.py"),
        "index",
    ]
    if folder:
        cmd.append(folder)
    cmd.extend(["--device", device])
    cmd.append("--ocr" if ocr else "--no-ocr")

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
    folder = str(Path(req.folder).expanduser()) if req.folder else None

    job_id = uuid.uuid4().hex
    job = Job(id=job_id, kind="index", status="queued", folder=folder, processed=0, total=None)

    with JOB_LOCK:
        JOBS[job_id] = job

    t = threading.Thread(
        target=_run_index_job,
        args=(job_id, folder, req.device, req.ocr),
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
        # hybrid
        w = float(req.ocr_weight)
        q_lower = req.query.lower()
        has_digits = any(ch.isdigit() for ch in req.query)
        texty_keywords = [
            "error",
            "code",
            "http",
            "forbidden",
            "denied",
            "invoice",
            "receipt",
            "total",
            "$",
            "usd",
            "cad",
        ]
        looks_texty = has_digits or any(k in q_lower for k in texty_keywords)
        if looks_texty:
            w = max(w, 0.80)
        w = 0.0 if w < 0 else (1.0 if w > 1 else w)
        scores = (1.0 - w) * clip_scores + w * ocr_scores

    topk = core.np.argsort(-scores)[: req.k]

    # Pull OCR preview text for just the top results (helps UX without exposing full text everywhere).
    conn = core.sqlite3.connect(paths.db)
    top_paths = [paths_list[int(i)] for i in topk]
    ph = ",".join(["?"] * len(top_paths)) if top_paths else ""
    ocr_preview: dict[str, str] = {}
    if top_paths:
        rows = conn.execute(
            f"SELECT path, COALESCE(ocr_text,'') FROM assets WHERE path IN ({ph})",
            tuple(top_paths),
        ).fetchall()
        for p, txt in rows:
            t = (txt or "").replace("\n", " ").strip()
            if len(t) > 180:
                t = t[:180] + "…"
            ocr_preview[str(p)] = t

    results = []
    for idx_id in topk:
        p = paths_list[int(idx_id)]
        w = h = None
        try:
            with Image.open(p) as im:
                w, h = im.size
        except Exception:
            pass

        results.append(
            {
                "path": p,
                "score": float(scores[int(idx_id)]),
                "clip": float(clip_scores[int(idx_id)]),
                "ocr": float(ocr_scores[int(idx_id)]),
                "ocr_preview": ocr_preview.get(p, ""),
                "width": w,
                "height": h,
                "thumb_url": f"/thumb?path={p}",
            }
        )

    return {"results": results}
