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
from datetime import datetime
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
            indexed_at TEXT NOT NULL
        );
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
@click.argument("folder", type=click.Path(exists=True, file_okay=False, path_type=Path))
@click.option(
    "--device",
    type=click.Choice(["auto", "cpu", "mps"]),
    default="auto",
    show_default=True,
)
def index(folder: Path, device: str):
    """Index all images under FOLDER."""

    paths = get_dbpaths()
    paths.root.mkdir(parents=True, exist_ok=True)

    conn = sqlite3.connect(paths.db)
    ensure_schema(conn)

    if device == "auto":
        device = "mps" if torch.backends.mps.is_available() else "cpu"

    console.print(f"[bold]Indexing[/bold] {folder}  ([dim]{device}[/dim])")
    model_name, pretrained, model, preprocess, tokenizer = load_model(device=device)

    # For the thin-slice MVP, we rebuild embeddings from scratch.
    # This avoids native-library conflicts (e.g., OpenMP) and keeps behavior predictable.
    meta = {"model": {"name": model_name, "pretrained": pretrained}, "paths": []}

    images = list(iter_images(folder))
    use_tqdm = sys.stderr.isatty()
    iterator = tqdm(images, desc="images") if use_tqdm else images

    vecs: List[np.ndarray] = []

    for i, p in enumerate(iterator, start=1):
        if not use_tqdm and i % 25 == 0:
            console.print(f"… processed {i}/{len(images)}")

        p_str = str(p)
        mtime, size = get_file_stats(p)

        vec = image_embedding(model, preprocess, device, p)
        if vec is None:
            continue

        w, h = get_image_size(p)
        now = datetime.utcnow().isoformat()

        conn.execute(
            """
            INSERT INTO assets(path, mtime, size_bytes, width, height, indexed_at)
            VALUES(?, ?, ?, ?, ?, ?)
            ON CONFLICT(path) DO UPDATE SET
              mtime=excluded.mtime,
              size_bytes=excluded.size_bytes,
              width=excluded.width,
              height=excluded.height,
              indexed_at=excluded.indexed_at
            """,
            (p_str, mtime, size, w, h, now),
        )

        meta["paths"].append(p_str)
        vecs.append(vec)

    conn.commit()

    if not vecs:
        raise click.ClickException("No embeddings produced. Check supported file types.")

    embs = np.stack(vecs).astype("float32")
    np.save(paths.embeddings, embs)
    paths.meta.write_text(json.dumps(meta, indent=2))

    console.print(f"[green]Done[/green]. Embedded {embs.shape[0]} images.")
    console.print(f"Embeddings: {paths.embeddings}")
    console.print(f"DB:         {paths.db}")


@cli.command()
@click.argument("query", type=str)
@click.option("--k", type=int, default=12)
@click.option(
    "--device",
    type=click.Choice(["auto", "cpu", "mps"]),
    default="auto",
    show_default=True,
)
def search(query: str, k: int, device: str):
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

    model_name = meta.get("model", {}).get("name", "ViT-B-32")
    pretrained = meta.get("model", {}).get("pretrained", "laion2b_s34b_b79k")

    model, _, _ = open_clip.create_model_and_transforms(model_name, pretrained=pretrained)
    tokenizer = open_clip.get_tokenizer(model_name)
    model.to(device)
    model.eval()

    q = text_embedding(model, tokenizer, device, query)

    # Cosine similarity via dot product (vectors are normalized).
    scores = embs @ q.reshape(-1, 1)
    scores = scores.reshape(-1)
    topk = np.argsort(-scores)[:k]

    table = Table(title=f"Merlian results for: {query!r}")
    table.add_column("rank", justify="right")
    table.add_column("score", justify="right")
    table.add_column("path")

    paths_list: List[str] = meta.get("paths", [])
    for rank, idx_id in enumerate(topk, start=1):
        if idx_id < 0 or idx_id >= len(paths_list):
            continue
        table.add_row(str(rank), f"{float(scores[idx_id]):.3f}", paths_list[idx_id])

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
