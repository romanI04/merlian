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

from fastapi import FastAPI
from pydantic import BaseModel, Field

# Reuse engine functions directly.
import merlian as core

app = FastAPI(title="Merlian Local API", version="0.1")


class IndexRequest(BaseModel):
    folder: str | None = None
    device: Literal["auto", "cpu", "mps"] = "auto"
    ocr: bool = True


class SearchRequest(BaseModel):
    query: str
    k: int = Field(default=12, ge=1, le=200)
    device: Literal["auto", "cpu", "mps"] = "auto"
    mode: Literal["clip", "ocr", "hybrid"] = "hybrid"
    ocr_weight: float = Field(default=0.55, ge=0.0, le=1.0)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


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

    return {
        "indexed": True,
        "root": meta.get("root"),
        "model": meta.get("model"),
        "assets": int(total),
        "with_ocr": int(with_ocr),
        "embeddings": int(n_embs),
    }


@app.post("/index")
def index(req: IndexRequest) -> dict[str, Any]:
    # Call the same logic as CLI by invoking the function directly.
    folder = Path(req.folder).expanduser() if req.folder else None

    # We call core.index() directly, but it is a click command.
    # Instead we call the underlying function content by importing and reusing it.
    # For MVP: replicate call using the same core functions.

    # Use the CLI function via its callback (works because we defined index() as a python function).
    core.index.callback(folder, req.device, req.ocr)  # type: ignore[attr-defined]

    # Return fresh status.
    return status()


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

    model, _, _ = core.open_clip.create_model_and_transforms(
        model_name, pretrained=pretrained
    )
    tokenizer = core.open_clip.get_tokenizer(model_name)
    model.to(device)
    model.eval()

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

    results = []
    for idx_id in topk:
        results.append(
            {
                "path": paths_list[int(idx_id)],
                "score": float(scores[int(idx_id)]),
                "clip": float(clip_scores[int(idx_id)]),
                "ocr": float(ocr_scores[int(idx_id)]),
            }
        )

    return {"results": results}
