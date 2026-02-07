#!/usr/bin/env python3
"""Export the current Merlian index as a static demo catalog.

Outputs:
  ../demo-dataset/demo-catalog.json   — metadata + OCR for each image
  ../demo-dataset/demo-embeddings.npy — pre-computed CLIP vectors (N x dim)

These files power the demo mode without requiring a live index.
"""

import json
import sqlite3
import numpy as np
from pathlib import Path

from merlian import app_dir


def main():
    data = app_dir()
    db_path = data / "merlian.sqlite"
    emb_path = data / "embeddings.npy"
    meta_path = data / "meta.json"

    if not db_path.exists():
        print("No index found. Run `python merlian.py index ../demo-dataset --ocr` first.")
        return

    # Load meta.json — paths list is the embedding index mapping
    with open(meta_path) as f:
        meta = json.load(f)
    paths_list = meta.get("paths", [])

    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row

    # Build lookup from path to asset data
    rows = conn.execute(
        """SELECT path, width, height, textiness, quality_score,
                  dup_group, mtime, ocr_text
           FROM assets"""
    ).fetchall()
    asset_map = {row["path"]: dict(row) for row in rows}
    conn.close()

    embeddings = np.load(str(emb_path))
    demo_root = Path(__file__).parent.parent / "demo-dataset"

    catalog = []
    emb_list = []

    for i, raw_path in enumerate(paths_list):
        if i >= len(embeddings):
            break

        # Convert to absolute for relative_to check
        p = Path(raw_path)
        if not p.is_absolute():
            p = (Path(__file__).parent / p).resolve()

        try:
            rel = p.relative_to(demo_root.resolve())
        except ValueError:
            continue

        asset = asset_map.get(raw_path, {})

        catalog.append({
            "path": str(rel),
            "width": asset.get("width") or 1440,
            "height": asset.get("height") or 900,
            "textiness": asset.get("textiness") or 0.0,
            "quality_score": asset.get("quality_score") or 0.5,
            "dup_group": asset.get("dup_group"),
            "mtime": asset.get("mtime") or 0,
            "ocr_text": asset.get("ocr_text") or "",
        })
        emb_list.append(embeddings[i])

    if not catalog:
        print("No demo-dataset images found in the index. Did you index ../demo-dataset?")
        return

    out_catalog = demo_root / "demo-catalog.json"
    out_emb = demo_root / "demo-embeddings.npy"

    with open(out_catalog, "w") as f:
        json.dump(catalog, f, indent=2)

    np.save(str(out_emb), np.array(emb_list, dtype=np.float32))

    print(f"Exported {len(catalog)} items:")
    print(f"  {out_catalog}  ({out_catalog.stat().st_size / 1024:.1f} KB)")
    print(f"  {out_emb}  ({out_emb.stat().st_size / 1024:.1f} KB)")


if __name__ == "__main__":
    main()
