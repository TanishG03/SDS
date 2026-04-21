"""
adaptive_hilbert_indexer.py
Stage 2 — Adaptive Hilbert indexing + simulated tile store.

Reads segmentation_map.json (output of region_segmenter.py).
For each base tile:
  - Subdivides it into a sub-grid matching its assigned Hilbert order
    (order=2 → 4×4, order=3 → 8×8, order=4 → 16×16 sub-tiles)
  - Computes the Hilbert code for each sub-tile
  - Assembles the row key: [region_class(2b) | hilbert_order(4b) | local_x(8b) | local_y(8b) | hilbert_code(32b)]
  - Crops and saves the actual sub-tile PNG
  - Writes metadata JSON per tile

Output:
  tile_store/                    ← actual PNG sub-tiles
  tile_index.json                ← flat list of all indexed tile records
  adaptive_hilbert_index_vis.png ← full-image visualization
"""

import os
import json
import math
import struct
import logging
import numpy as np
from PIL import Image, ImageDraw, ImageFont

logging.basicConfig(level=logging.INFO, format="%(asctime)s  %(message)s")
log = logging.getLogger("AdaptiveHilbert")

# Paths are derived from input image name

# ── Hilbert curve (Butz algorithm) ────────────────────────────────
def xy_to_hilbert(x: int, y: int, order: int) -> int:
    grid = 2 ** order
    d, s, cx, cy = 0, grid // 2, x, y
    while s > 0:
        rx = 1 if (cx & s) > 0 else 0
        ry = 1 if (cy & s) > 0 else 0
        d += s * s * ((3 * rx) ^ ry)
        if ry == 0:
            if rx == 1:
                cx, cy = s - 1 - cx, s - 1 - cy
            cx, cy = cy, cx
        s //= 2
    return d


def hilbert_to_xy(d: int, order: int):
    """Inverse: Hilbert code → (x, y)."""
    grid = 2 ** order
    x = y = 0
    s = 1
    t = d
    while s < grid:
        rx = 1 if (t & 2) else 0
        ry = 1 if (t & 1) ^ rx else 0
        if ry == 0:
            if rx == 1:
                x, y = s - 1 - x, s - 1 - y
            x, y = y, x
        x += s * rx
        y += s * ry
        t >>= 2
        s <<= 1
    return x, y


# ── Row key encoding ──────────────────────────────────────────────
def encode_key(region_class: int, order: int,
               base_tx: int, base_ty: int,
               sub_x: int, sub_y: int, hilbert: int) -> str:
    """
    Composite key (sortable string):
      {class:1d}_{order:1d}_{base_tx:02d}{base_ty:02d}_{sub_x:02d}{sub_y:02d}_{hilbert:08x}
    """
    return (f"{region_class}_{order}_"
            f"{base_tx:02d}{base_ty:02d}_"
            f"{sub_x:02d}{sub_y:02d}_"
            f"{hilbert:08x}")


# ── Main indexing routine ─────────────────────────────────────────
def build_adaptive_index(image_path: str):
    base_name = os.path.splitext(os.path.basename(image_path))[0]
    seg_map = f"segmentation_map_{base_name}.json"
    tile_dir = f"tile_store_{base_name}"
    index_out = f"tile_index_{base_name}.json"
    vis_out = f"adaptive_hilbert_index_vis_{base_name}.png"

    log.info(f"Loading image: {image_path}")
    img = Image.open(image_path).convert("RGB")
    
    if not os.path.exists(seg_map):
        raise FileNotFoundError(f"Missing {seg_map}. Run region_segmenter.py first.")
        
    with open(seg_map) as f:
        seg = json.load(f)

    grid_size      = seg["grid_size"]
    img_w, img_h   = seg["image_size"]
    cell_w, cell_h = seg["cell_size"]

    # Apply same crop as segmenter
    w, h = img.size
    img  = img.crop(((w - img_w) // 2, (h - img_h) // 2,
                     (w - img_w) // 2 + img_w, (h - img_h) // 2 + img_h))

    os.makedirs(tile_dir, exist_ok=True)

    index_records = []
    arr = np.array(img)

    class_stats = {0: 0, 1: 0, 2: 0}

    for tile_info in seg["tiles"]:
        base_tx = tile_info["tile_x"]
        base_ty = tile_info["tile_y"]
        cls     = tile_info["class"]
        order   = tile_info["order"]
        x0, y0, x1, y1 = tile_info["pixel_bbox"]

        base_patch = arr[y0:y1, x0:x1]     # (cell_h, cell_w, 3)
        sub_grid   = 2 ** order             # e.g. 4, 8, or 16
        sub_w      = (x1 - x0) // sub_grid
        sub_h      = (y1 - y0) // sub_grid

        for sy in range(sub_grid):
            for sx in range(sub_grid):
                h_code = xy_to_hilbert(sx, sy, order)

                # Pixel bounds within the base patch
                px0 = sx * sub_w
                py0 = sy * sub_h
                sub_patch = base_patch[py0:py0+sub_h, px0:px0+sub_w]

                mean_color = sub_patch.mean(axis=(0, 1)).tolist()

                row_key = encode_key(cls, order, base_tx, base_ty,
                                     sx, sy, h_code)

                # Save PNG
                tile_img  = Image.fromarray(sub_patch.astype(np.uint8))
                tile_path = os.path.join(tile_dir, f"{row_key}.png")
                tile_img.save(tile_path)

                # Absolute pixel bbox in the full image
                abs_x0 = x0 + px0
                abs_y0 = y0 + py0

                record = {
                    "key":          row_key,
                    "region_class": cls,
                    "class_name":   tile_info["class_name"],
                    "hilbert_order": order,
                    "base_tx":      base_tx,
                    "base_ty":      base_ty,
                    "sub_x":        sx,
                    "sub_y":        sy,
                    "hilbert_code": h_code,
                    "mean_color":   mean_color,
                    "entropy":      tile_info["entropy"],
                    "abs_bbox":     [abs_x0, abs_y0,
                                     abs_x0+sub_w, abs_y0+sub_h],
                    "tile_path":    tile_path,
                }
                index_records.append(record)
                class_stats[cls] += 1

    # Sort by composite key → locality-preserving order
    index_records.sort(key=lambda r: r["key"])

    index_records.sort(key=lambda r: r["key"])

    with open(index_out, "w") as f:
        json.dump(index_records, f, indent=2)

    log.info(f"Indexed {len(index_records)} sub-tiles → {index_out}")
    for c, n in class_stats.items():
        log.info(f"  Class {c}: {n} sub-tiles")

    _visualize_index(img, index_records, img_w, img_h, vis_out)
    return index_records


# ── Visualization ─────────────────────────────────────────────────
def _visualize_index(img: Image.Image,
                     records: list[dict],
                     img_w: int, img_h: int,
                     vis_out: str):
    log.info("Rendering adaptive Hilbert index visualization...")

    CLASS_COLORS = {
        0: (30,  120, 210),
        1: (80,  180, 80),
        2: (220, 60,  60),
    }

    canvas = img.copy().convert("RGBA")
    overlay = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
    draw    = ImageDraw.Draw(overlay)

    try:
        font = ImageFont.truetype(
            "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 8)
    except Exception:
        font = ImageFont.load_default()

    for rec in records:
        x0, y0, x1, y1 = rec["abs_bbox"]
        cls  = rec["region_class"]
        h_id = rec["hilbert_code"]
        r, g, b = CLASS_COLORS[cls]

        # Semi-transparent fill
        draw.rectangle([x0, y0, x1-1, y1-1],
                       fill=(r, g, b, 35),
                       outline=(r, g, b, 160), width=1)

        # Print Hilbert code in small text (only if tile is large enough)
        if (x1 - x0) >= 12:
            draw.text((x0 + 1, y0 + 1), str(h_id),
                      fill=(255, 255, 255, 200), font=font)

    composite = Image.alpha_composite(canvas, overlay).convert("RGB")

    # ── Draw Hilbert path lines per base tile ─────────────────────
    draw2 = ImageDraw.Draw(composite)

    # Group by (base_tx, base_ty, class)
    from collections import defaultdict
    groups = defaultdict(list)
    for rec in records:
        key = (rec["base_tx"], rec["base_ty"])
        groups[key].append(rec)

    for (btx, bty), recs in groups.items():
        cls = recs[0]["region_class"]
        r, g, b = CLASS_COLORS[cls]
        # Sort by hilbert code for path
        recs_sorted = sorted(recs, key=lambda r: r["hilbert_code"])
        centers = []
        for rec in recs_sorted:
            x0, y0, x1, y1 = rec["abs_bbox"]
            centers.append(((x0+x1)//2, (y0+y1)//2))
        for i in range(len(centers)-1):
            draw2.line([centers[i], centers[i+1]],
                       fill=(r, g, b, 200), width=1)

    composite.save(vis_out)
    log.info(f"Saved: {vis_out}")


if __name__ == "__main__":
    import sys
    path = sys.argv[1] if len(sys.argv) > 1 else "test1.jpg"
    build_adaptive_index(path)