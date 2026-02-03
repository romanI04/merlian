"""Merlian engine (MVP)

Thin-slice CLI to validate the core value prop:
- index a folder of images locally (embeddings + metadata)
- search by text and return top file paths

This is intentionally minimal and not production-ready.
"""

from __future__ import annotations

import json
import os
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable, List, Optional, Tuple

import click
import numpy as np
import open_clip
import torch
from PIL import Image
from rich.console import Console
from rich.table import Table
from tqdm import tqdm
import sys
import subprocess
import re

console = Console()

SUPPORTED_EXTS = {".png", ".jpg", ".jpeg", ".webp"}


@dataclass
class DbPaths:
    root: Path
    db: Path
    embeddings: Path
    meta: Path


def app_dir() -> Path:
    # Keep local to repo for now, to avoid polluting user machine.
    return Path(__file__).resolve().parent / ".merlian"


def get_dbpaths() -> DbPaths:
    root = app_dir()
    return DbPaths(
        root=root,
        db=root / "merlian.sqlite",
        embeddings=root / "embeddings.npy",
        meta=root / "meta.json",
    )


def ensure_schema(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS assets (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            path TEXT UNIQUE NOT NULL,
            mtime REAL NOT NULL,
            size_bytes INTEGER NOT NULL,
            width INTEGER,
            height INTEGER,
            ocr_text TEXT,
            indexed_at TEXT NOT NULL
        );
        """
    )

    # Lightweight migration for older DBs.
    cols = [r[1] for r in conn.execute("PRAGMA table_info(assets)").fetchall()]
    if "ocr_text" not in cols:
        conn.execute("ALTER TABLE assets ADD COLUMN ocr_text TEXT")

    # OCR full-text index (SQLite FTS5).
    # We keep this separate and simple to avoid trigger complexity.
    conn.execute(
        """
        CREATE VIRTUAL TABLE IF NOT EXISTS ocr_fts
        USING fts5(path UNINDEXED, ocr_text);
        """
    )

    conn.commit()


def iter_images(folder: Path) -> Iterable[Path]:
    for p in folder.rglob("*"):
        if p.is_file() and p.suffix.lower() in SUPPORTED_EXTS:
            yield p


def load_model(device: str = "cpu"):
    # OpenCLIP default choice for MVP.
    model_name = "ViT-B-32"
    pretrained = "laion2b_s34b_b79k"
    model, _, preprocess = open_clip.create_model_and_transforms(
        model_name, pretrained=pretrained
    )
    tokenizer = open_clip.get_tokenizer(model_name)

    model.to(device)
    model.eval()

    return model_name, pretrained, model, preprocess, tokenizer


def image_embedding(
    model, preprocess, device: str, image_path: Path
) -> Optional[np.ndarray]:
    try:
        img = Image.open(image_path).convert("RGB")
    except Exception:
        return None

    with torch.no_grad():
        image = preprocess(img).unsqueeze(0).to(device)
        feats = model.encode_image(image)
        feats = feats / feats.norm(dim=-1, keepdim=True)
        vec = feats.detach().cpu().numpy().astype("float32")[0]
        return vec


def ocr_text_apple_vision(image_path: Path) -> str:
    """Extract text using Apple Vision OCR (macOS only).

    Returns empty string if OCR is unavailable or fails.
    """

    try:
        from Foundation import NSURL
        from Vision import (
            VNImageRequestHandler,
            VNRecognizeTextRequest,
        )
        from Quartz import CGImageSourceCreateWithURL, CGImageSourceCreateImageAtIndex

        url = NSURL.fileURLWithPath_(str(image_path))
        src = CGImageSourceCreateWithURL(url, None)
        if src is None:
            return ""
        cg_img = CGImageSourceCreateImageAtIndex(src, 0, None)
        if cg_img is None:
            return ""

        out: list[str] = []

        def handler(request, error):
            if error is not None:
                return
            for obs in request.results() or []:
                top = obs.topCandidates_(1)
                if top and len(top) > 0:
                    out.append(str(top[0].string()))

        req = VNRecognizeTextRequest.alloc().initWithCompletionHandler_(handler)
        # Practical defaults for screenshots.
        req.setRecognitionLevel_(1)  # Accurate
        req.setUsesLanguageCorrection_(True)

        img_handler = VNImageRequestHandler.alloc().initWithCGImage_options_(
            cg_img, None
        )
        ok = img_handler.performRequests_error_([req], None)
        if not ok:
            return ""

        text = "\n".join(out)
        return text.strip()

    except Exception:
        return ""


def text_embedding(model, tokenizer, device: str, query: str) -> np.ndarray:
    with torch.no_grad():
        text = tokenizer([query]).to(device)
        feats = model.encode_text(text)
        feats = feats / feats.norm(dim=-1, keepdim=True)
        return feats.detach().cpu().numpy().astype("float32")[0]


def get_file_stats(path: Path) -> Tuple[float, int]:
    st = path.stat()
    return st.st_mtime, st.st_size


def get_image_size(path: Path) -> Tuple[Optional[int], Optional[int]]:
    try:
        with Image.open(path) as img:
            return img.width, img.height
    except Exception:
        return None, None


def load_embeddings(emb_path: Path) -> Optional[np.ndarray]:
    if not emb_path.exists():
        return None
    return np.load(emb_path)


@click.group()
def cli():
    pass


@cli.command()
@click.argument(
    "folder",
    required=False,
    type=click.Path(exists=True, file_okay=False, path_type=Path),
)
@click.option(
    "--device",
    type=click.Choice(["auto", "cpu", "mps"]),
    default="auto",
    show_default=True,
)
@click.option(
    "--ocr/--no-ocr",
    default=True,
    show_default=True,
    help="Extract text from images using Apple Vision OCR (macOS).",
)
def index(folder: Path | None, device: str, ocr: bool):
    """Index images under FOLDER (or the last indexed folder)."""

    paths = get_dbpaths()
    paths.root.mkdir(parents=True, exist_ok=True)

    # Allow running `merlian index` with no folder by reusing the last one.
    if folder is None:
        if paths.meta.exists():
            try:
                meta_prev = json.loads(paths.meta.read_text())
                prev_root = meta_prev.get("root")
                if prev_root:
                    folder = Path(prev_root)
            except Exception:
                pass
        if folder is None:
            raise click.ClickException("No folder provided and no previous index found.")

    conn = sqlite3.connect(paths.db)
    ensure_schema(conn)

    if device == "auto":
        device = "mps" if torch.backends.mps.is_available() else "cpu"

    console.print(
        f"[bold]Indexing[/bold] {folder}  ([dim]{device}[/dim], ocr={'on' if ocr else 'off'})"
    )
    model_name, pretrained, model, preprocess, tokenizer = load_model(device=device)

    # Incremental indexing (single-folder MVP):
    # - skip unchanged files
    # - update changed files in-place
    # - append new files
    # - drop deleted files

    meta = {"model": {"name": model_name, "pretrained": pretrained}, "paths": [], "root": str(folder)}
    embs_existing = load_embeddings(paths.embeddings)

    if paths.meta.exists() and embs_existing is not None:
        try:
            meta = json.loads(paths.meta.read_text())
        except Exception:
            meta = {"model": {"name": model_name, "pretrained": pretrained}, "paths": [], "root": str(folder)}

    meta.setdefault("model", {"name": model_name, "pretrained": pretrained})
    meta["model"] = {"name": model_name, "pretrained": pretrained}
    meta["root"] = str(folder)

    paths_list: List[str] = list(meta.get("paths", []))
    if embs_existing is None or len(paths_list) != embs_existing.shape[0]:
        # If anything is inconsistent, start fresh.
        paths_list = []
        embs_existing = None

    seen: set[str] = set()
    path_to_idx = {p: i for i, p in enumerate(paths_list)}

    images = list(iter_images(folder))
    use_tqdm = sys.stderr.isatty()
    iterator = tqdm(images, desc="images") if use_tqdm else images

    # Work on a mutable embeddings store.
    if embs_existing is None:
        vecs: List[np.ndarray] = []
    else:
        vecs = [embs_existing[i] for i in range(embs_existing.shape[0])]

    added = 0
    updated = 0
    skipped = 0

    for i, p in enumerate(iterator, start=1):
        if not use_tqdm and i % 25 == 0:
            console.print(f"… processed {i}/{len(images)}")

        p_str = str(p)
        seen.add(p_str)
        mtime, size = get_file_stats(p)

        # Skip unchanged if we have it indexed.
        row = conn.execute(
            "SELECT mtime, size_bytes FROM assets WHERE path=?",
            (p_str,),
        ).fetchone()
        if row is not None and p_str in path_to_idx:
            if float(row[0]) == float(mtime) and int(row[1]) == int(size):
                skipped += 1
                continue

        vec = image_embedding(model, preprocess, device, p)
        if vec is None:
            continue

        w, h = get_image_size(p)
        now = datetime.now(timezone.utc).isoformat()

        ocr_txt = ocr_text_apple_vision(p) if ocr else ""

        conn.execute(
            """
            INSERT INTO assets(path, mtime, size_bytes, width, height, ocr_text, indexed_at)
            VALUES(?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(path) DO UPDATE SET
              mtime=excluded.mtime,
              size_bytes=excluded.size_bytes,
              width=excluded.width,
              height=excluded.height,
              ocr_text=excluded.ocr_text,
              indexed_at=excluded.indexed_at
            """,
            (p_str, mtime, size, w, h, ocr_txt, now),
        )

        # Update OCR full-text index.
        conn.execute("DELETE FROM ocr_fts WHERE path=?", (p_str,))
        if ocr_txt:
            conn.execute(
                "INSERT INTO ocr_fts(path, ocr_text) VALUES(?, ?)", (p_str, ocr_txt)
            )

        if p_str in path_to_idx:
            vecs[path_to_idx[p_str]] = vec
            updated += 1
        else:
            path_to_idx[p_str] = len(paths_list)
            paths_list.append(p_str)
            vecs.append(vec)
            added += 1

    # Drop paths that no longer exist under folder.
    removed = 0
    if paths_list:
        keep_indices = [i for i, p in enumerate(paths_list) if p in seen]
        removed = len(paths_list) - len(keep_indices)
        if removed > 0:
            removed_paths = [p for p in paths_list if p not in seen]
            # Remove from DB + FTS.
            for rp in removed_paths:
                conn.execute("DELETE FROM assets WHERE path=?", (rp,))
                conn.execute("DELETE FROM ocr_fts WHERE path=?", (rp,))

            paths_list = [paths_list[i] for i in keep_indices]
            vecs = [vecs[i] for i in keep_indices]

    conn.commit()

    if not vecs:
        raise click.ClickException("No embeddings produced. Check supported file types.")

    embs = np.stack(vecs).astype("float32")
    np.save(paths.embeddings, embs)
    meta["paths"] = paths_list
    paths.meta.write_text(json.dumps(meta, indent=2))

    console.print(
        f"[green]Done[/green]. Total {embs.shape[0]} images. +{added} new, ~{updated} updated, -{removed} removed, ={skipped} unchanged."
    )
    console.print(f"Embeddings: {paths.embeddings}")
    console.print(f"DB:         {paths.db}")


@cli.command()
@click.argument("query", type=str)
@click.option("--k", type=int, default=12, show_default=True)
@click.option(
    "--device",
    type=click.Choice(["auto", "cpu", "mps"]),
    default="auto",
    show_default=True,
)
@click.option(
    "--mode",
    type=click.Choice(["clip", "ocr", "hybrid"]),
    default="hybrid",
    show_default=True,
    help="How to rank results.",
)
@click.option(
    "--ocr-weight",
    type=float,
    default=0.55,
    show_default=True,
    help="In hybrid mode: weight for OCR score (0..1).",
)
@click.option(
    "--why/--no-why",
    default=False,
    show_default=True,
    help="Show matched OCR tokens for each result (debug).",
)
@click.option(
    "--open",
    "open_rank",
    type=int,
    default=None,
    help="Open the Nth result (1-based) after searching.",
)
@click.option(
    "--reveal",
    "reveal_rank",
    type=int,
    default=None,
    help="Reveal the Nth result in Finder (1-based) after searching.",
)
def search(
    query: str,
    k: int,
    device: str,
    mode: str,
    ocr_weight: float,
    why: bool,
    open_rank: int | None,
    reveal_rank: int | None,
):
    """Search indexed images by text."""

    if device == "auto":
        device = "mps" if torch.backends.mps.is_available() else "cpu"

    paths = get_dbpaths()
    if not paths.embeddings.exists() or not paths.meta.exists():
        raise click.ClickException("No index found. Run: merlian index <folder>")

    meta = json.loads(paths.meta.read_text())
    embs = load_embeddings(paths.embeddings)
    if embs is None:
        raise click.ClickException("No embeddings found. Run: merlian index <folder>")

    paths_list: List[str] = meta.get("paths", [])
    if len(paths_list) != embs.shape[0]:
        raise click.ClickException(
            "Index metadata mismatch. Re-run: merlian reset && merlian index <folder>"
        )

    # Build CLIP score
    model_name = meta.get("model", {}).get("name", "ViT-B-32")
    pretrained = meta.get("model", {}).get("pretrained", "laion2b_s34b_b79k")

    model, _, _ = open_clip.create_model_and_transforms(model_name, pretrained=pretrained)
    tokenizer = open_clip.get_tokenizer(model_name)
    model.to(device)
    model.eval()

    q = text_embedding(model, tokenizer, device, query)

    # Cosine similarity via dot product (vectors are normalized).
    clip_scores = (embs @ q.reshape(-1, 1)).reshape(-1)

    # Build OCR score using SQLite FTS5 (much better than naive substring matching).
    # We score only files that match the OCR query, and normalize bm25 scores to 0..1.
    q_tokens = [
        t for t in re.split(r"[^a-zA-Z0-9]+", query.lower()) if len(t) >= 3 or t.isdigit()
    ]
    ocr_scores = np.zeros_like(clip_scores)
    ocr_hits: dict[str, list[str]] = {}

    if q_tokens:
        conn = sqlite3.connect(paths.db)

        # Prefer AND for precision; fall back to OR if nothing matches.
        match_and = " AND ".join(q_tokens)
        match_or = " OR ".join(q_tokens)

        try:
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

            # Some SQLite builds/tokenizers can be surprisingly bad at indexing pure-number tokens.
            # If FTS yields nothing and the query contains digits (e.g. "403"), fall back to LIKE.
            if not rows:
                digit_tokens = [t for t in q_tokens if t.isdigit()]
                if digit_tokens:
                    clauses = " OR ".join(["ocr_text LIKE ?" for _ in digit_tokens])
                    like_args = [f"%{t}%" for t in digit_tokens]
                    like_rows = conn.execute(
                        f"SELECT path FROM assets WHERE {clauses} LIMIT 2000",
                        tuple(like_args),
                    ).fetchall()
                    if like_rows:
                        # Give a decent OCR score to digit matches.
                        for (p,) in like_rows:
                            try:
                                i = paths_list.index(str(p))
                                ocr_scores[i] = max(ocr_scores[i], 0.95)
                            except ValueError:
                                pass
                        if why:
                            for (p,) in like_rows[: min(len(like_rows), k * 5)]:
                                ocr_hits[str(p)] = digit_tokens

            # bm25: lower is better; convert to 0..1 where 1 is best.
            if rows:
                raw = np.array([float(r[1]) for r in rows], dtype="float32")
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

                if why:
                    # Fetch snippets for the top candidates we might display.
                    # For debug only — keep it lightweight.
                    top_paths = [p for (p, _) in rows[: min(len(rows), k * 5)]]
                    ph = ",".join("?" for _ in top_paths)
                    texts = conn.execute(
                        f"SELECT path, COALESCE(ocr_text,'') FROM assets WHERE path IN ({ph})",
                        tuple(top_paths),
                    ).fetchall()
                    for p, txt in texts:
                        txt_l = (txt or "").lower()
                        ocr_hits[str(p)] = [t for t in q_tokens if t in txt_l]

        except sqlite3.OperationalError:
            # FTS not available; fall back to naive matching.
            rows = conn.execute("SELECT path, COALESCE(ocr_text, '') FROM assets").fetchall()
            ocr_map = {p: (txt or "").lower() for p, txt in rows}
            for i, p in enumerate(paths_list):
                txt = ocr_map.get(p, "")
                if not txt:
                    continue
                hits = sum(1 for t in q_tokens if t in txt)
                ocr_scores[i] = hits / max(1, len(q_tokens))
                if why and hits:
                    ocr_hits[p] = [t for t in q_tokens if t in txt]

    # Choose scoring mode
    if mode == "clip":
        scores = clip_scores
    elif mode == "ocr":
        scores = ocr_scores
    else:
        # hybrid
        w = float(ocr_weight)

        # Auto-boost OCR for “texty” queries (very common for screenshots):
        # - contains digits (error codes, amounts, dates)
        # - contains likely keywords
        q_lower = query.lower()
        has_digits = any(ch.isdigit() for ch in query)
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

    topk = np.argsort(-scores)[:k]

    title_extra = ""
    if mode == "hybrid":
        title_extra = f" w={w:.2f}"

    table = Table(title=f"Merlian results for: {query!r} ({mode}{title_extra})")
    table.add_column("rank", justify="right")
    table.add_column("score", justify="right")
    table.add_column("clip", justify="right")
    table.add_column("ocr", justify="right")
    if why:
        table.add_column("why")
    table.add_column("path")

    ranked_paths: List[str] = []
    for rank, idx_id in enumerate(topk, start=1):
        p = paths_list[idx_id]
        ranked_paths.append(p)

        row = [
            str(rank),
            f"{float(scores[idx_id]):.3f}",
            f"{float(clip_scores[idx_id]):.3f}",
            f"{float(ocr_scores[idx_id]):.2f}",
        ]
        if why:
            row.append(", ".join(ocr_hits.get(p, []))
            )
        row.append(p)
        table.add_row(*row)

    console.print(table)

    def resolve_rank(r: int | None) -> str | None:
        if r is None:
            return None
        if r < 1 or r > len(ranked_paths):
            raise click.ClickException(
                f"Rank {r} is out of range (1..{len(ranked_paths)})."
            )
        return ranked_paths[r - 1]

    target_open = resolve_rank(open_rank)
    target_reveal = resolve_rank(reveal_rank)

    if target_open and target_reveal:
        raise click.ClickException("Use only one of --open or --reveal.")

    if target_open:
        subprocess.run(["open", target_open], check=False)
    elif target_reveal:
        subprocess.run(["open", "-R", target_reveal], check=False)


@cli.command()
def status():
    """Show current index status."""
    paths = get_dbpaths()

    if not paths.root.exists() or not paths.meta.exists() or not paths.db.exists():
        console.print("No index found. Run: merlian index <folder>")
        return

    meta = json.loads(paths.meta.read_text())
    root = meta.get("root")
    model = meta.get("model", {})
    embs = load_embeddings(paths.embeddings)
    n_embs = int(embs.shape[0]) if embs is not None else 0

    conn = sqlite3.connect(paths.db)
    total = conn.execute("SELECT count(*) FROM assets").fetchone()[0]
    with_ocr = conn.execute(
        "SELECT count(*) FROM assets WHERE length(coalesce(ocr_text,'')) > 0"
    ).fetchone()[0]

    table = Table(title="Merlian index status")
    table.add_column("field")
    table.add_column("value")
    table.add_row("root", str(root))
    table.add_row("model", f"{model.get('name')} / {model.get('pretrained')}")
    table.add_row("assets (db)", str(total))
    table.add_row("with OCR", str(with_ocr))
    table.add_row("embeddings", str(n_embs))
    table.add_row("db path", str(paths.db))
    table.add_row("embeddings path", str(paths.embeddings))

    console.print(table)


@cli.command()
def reset():
    """Delete local index artifacts (repo-local)."""
    paths = get_dbpaths()
    if paths.root.exists():
        for p in paths.root.glob("*"):
            p.unlink(missing_ok=True)
        console.print(f"Removed {paths.root}")


if __name__ == "__main__":
    cli()
