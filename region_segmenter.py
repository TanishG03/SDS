
# """
# region_segmenter.py
# Stage 1 — Tile segmentation for adaptive Hilbert indexing.

# FIXED: Two-stage classification — colour-first, then entropy.
#   Stage A: Water detection via a "water score" = (B - R) / (R+G+B).
#            This cleanly separates blue/teal ocean AND shallow reef water
#            from green vegetation and red/brown urban tiles, regardless of
#            how textured (high-entropy) the reef surface appears.
#   Stage B: Remaining (non-water) tiles are split into transition vs urban
#            by 1-D k-means on Shannon gradient entropy.

# Classes:
#   0 → water/flat     → Hilbert order 2  (4×4 sub-grid, coarse)
#   1 → transition     → Hilbert order 3  (8×8 sub-grid, medium)
#   2 → urban/detail   → Hilbert order 4  (16×16 sub-grid, fine)

# Output:
#   segmentation_map.json
#   segmentation_vis.png
# """

# import os
# import json
# import logging
# import numpy as np
# from PIL import Image, ImageDraw, ImageFont

# logging.basicConfig(level=logging.INFO, format="%(asctime)s  %(message)s")
# log = logging.getLogger("Segmenter")

# # ── Config ────────────────────────────────────────────────────────
# BASE_GRID   = 8
# ORDER_MAP   = {0: 2, 1: 3, 2: 4}
# CLASS_NAMES = {0: "water/flat", 1: "transition", 2: "urban/detail"}
# CLASS_COLORS = {
#     0: (30,  120, 210),   # blue
#     1: (80,  180, 80),    # green
#     2: (220, 60,  60),    # red
# }
# OUTPUT_JSON = "segmentation_map.json"
# OUTPUT_VIS  = "segmentation_vis.png"

# # Water score = (B - R) / (R+G+B+eps)
# # Deep ocean:     ~+0.16   Shallow reef teal: ~+0.08
# # Green land:     ~-0.03   Urban/brown:       ~-0.14
# # Threshold of 0.04 cleanly captures all water variants while excluding land.
# WATER_SCORE_THRESH = 0.04


# def water_score(mean_rgb):
#     r, g, b = mean_rgb
#     return (b - r) / (r + g + b + 1e-6)


# def compute_entropy(patch: np.ndarray) -> float:
#     gray = patch.mean(axis=2).astype(np.float32)
#     dx   = np.diff(gray, axis=1)
#     dy   = np.diff(gray, axis=0)
#     mag  = np.sqrt(dx[:-1, :]**2 + dy[:, :-1]**2).ravel()
#     if mag.max() == 0:
#         return 0.0
#     hist, _ = np.histogram(mag, bins=32, range=(0, mag.max() + 1e-6))
#     hist     = hist.astype(np.float64)
#     hist    /= hist.sum()
#     mask     = hist > 0
#     return float(-np.sum(hist[mask] * np.log2(hist[mask])))


# def kmeans_1d(values: np.ndarray, k: int, iters: int = 100) -> np.ndarray:
#     """1-D k-means; returns labels sorted so 0 = lowest centroid."""
#     centers = np.percentile(values, np.linspace(0, 100, k))
#     labels  = np.zeros(len(values), dtype=int)
#     for _ in range(iters):
#         dists  = np.abs(values[:, None] - centers[None, :])
#         labels = dists.argmin(axis=1)
#         for i in range(k):
#             m = labels == i
#             if m.any():
#                 centers[i] = values[m].mean()
#     order        = np.argsort(centers)
#     remap        = np.empty(k, dtype=int)
#     remap[order] = np.arange(k)
#     return remap[labels]


# def segment_image(image_path: str) -> list:
#     log.info(f"Loading image: {image_path}")
#     img  = Image.open(image_path).convert("RGB")
#     w, h = img.size

#     cw  = (w // BASE_GRID) * BASE_GRID
#     ch  = (h // BASE_GRID) * BASE_GRID
#     img = img.crop(((w - cw) // 2, (h - ch) // 2,
#                     (w - cw) // 2 + cw, (h - ch) // 2 + ch))
#     arr = np.array(img)

#     cell_w = cw // BASE_GRID
#     cell_h = ch // BASE_GRID
#     log.info(f"Grid: {BASE_GRID}x{BASE_GRID}, cell {cell_w}x{cell_h} px")

#     tiles     = []
#     entropies = []
#     wscores   = []

#     for ty in range(BASE_GRID):
#         for tx in range(BASE_GRID):
#             x0    = tx * cell_w
#             y0    = ty * cell_h
#             patch = arr[y0:y0+cell_h, x0:x0+cell_w]

#             mc  = patch.mean(axis=(0, 1)).tolist()
#             ent = compute_entropy(patch)
#             ws  = water_score(mc)

#             tiles.append({
#                 "tile_x":      tx,
#                 "tile_y":      ty,
#                 "mean_color":  mc,
#                 "entropy":     ent,
#                 "water_score": ws,
#                 "pixel_bbox":  [x0, y0, x0+cell_w, y0+cell_h],
#             })
#             entropies.append(ent)
#             wscores.append(ws)

#     # ── Stage A: colour gate — detect water tiles ─────────────────
#     ws_arr   = np.array(wscores)
#     is_water = ws_arr >= WATER_SCORE_THRESH
#     log.info(f"Stage A: {is_water.sum()} water tiles "
#              f"(water_score >= {WATER_SCORE_THRESH})")

#     # ── Stage B: entropy k-means on non-water tiles only ─────────
#     land_idx  = np.where(~is_water)[0]
#     land_ents = np.array(entropies)[land_idx]

#     if len(land_idx) >= 2:
#         land_labels = kmeans_1d(land_ents, k=2)   # 0=transition, 1=urban
#     else:
#         land_labels = np.zeros(len(land_idx), dtype=int)

#     final = np.full(len(tiles), 0, dtype=int)
#     final[is_water]     = 0
#     final[land_idx]     = land_labels + 1   # map to class 1 or 2

#     for i, (tile, cls) in enumerate(zip(tiles, final)):
#         tile["class"]      = int(cls)
#         tile["order"]      = ORDER_MAP[int(cls)]
#         tile["class_name"] = CLASS_NAMES[int(cls)]

#     log.info("Segmentation complete:")
#     for c in range(3):
#         n = int((final == c).sum())
#         log.info(f"  Class {c} ({CLASS_NAMES[c]}, order={ORDER_MAP[c]}): {n} tiles")

#     with open(OUTPUT_JSON, "w") as f:
#         json.dump({
#             "grid_size":  BASE_GRID,
#             "image_size": [cw, ch],
#             "cell_size":  [cell_w, cell_h],
#             "tiles":      tiles,
#         }, f, indent=2)
#     log.info(f"Saved: {OUTPUT_JSON}")

#     _visualize(img, tiles)
#     return tiles


# def _visualize(img: Image.Image, tiles: list):
#     canvas  = img.copy().convert("RGBA")
#     overlay = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
#     draw    = ImageDraw.Draw(overlay)

#     try:
#         font    = ImageFont.truetype(
#             "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 13)
#         font_sm = ImageFont.truetype(
#             "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 10)
#     except Exception:
#         font = font_sm = ImageFont.load_default()

#     for tile in tiles:
#         cls             = tile["class"]
#         order           = tile["order"]
#         ent             = tile["entropy"]
#         ws              = tile["water_score"]
#         x0, y0, x1, y1 = tile["pixel_bbox"]
#         r, g, b         = CLASS_COLORS[cls]

#         draw.rectangle([x0, y0, x1, y1],
#                        fill=(r, g, b, 70),
#                        outline=(r, g, b, 220), width=2)
#         draw.text((x0+4, y0+4),  f"ord={order}",
#                   fill=(255, 255, 255, 255), font=font)
#         draw.text((x0+4, y0+20), f"H={ent:.2f}  ws={ws:.2f}",
#                   fill=(220, 220, 220, 220), font=font_sm)

#     # Legend
#     lx, ly = 10, img.height - 80
#     for cls, name in CLASS_NAMES.items():
#         r, g, b = CLASS_COLORS[cls]
#         draw.rectangle([lx, ly, lx+14, ly+14], fill=(r, g, b, 230))
#         draw.text((lx+18, ly),
#                   f"Class {cls}: {name}  (Hilbert order {ORDER_MAP[cls]})",
#                   fill=(255, 255, 255, 255), font=font_sm)
#         ly += 18

#     Image.alpha_composite(canvas, overlay).convert("RGB").save(OUTPUT_VIS)
#     log.info(f"Saved: {OUTPUT_VIS}")


# if __name__ == "__main__":
#     import sys
#     path = sys.argv[1] if len(sys.argv) > 1 else "test1.jpg"
#     segment_image(path)

"""
region_segmenter.py  —  Coastline-aware Adaptive Quadtree Segmentation
Stage 1 for adaptive Hilbert indexing.

Architecture (from Sun et al. 2024 + Hilbert papers):

  Step A — Binary water/land mask
    water_score = (B - R) / (R+G+B)  >= WATER_THRESH → water pixel
    Result: per-pixel boolean mask, same size as image.

  Step B — Quadtree decomposition, criterion = mask composition
    For each tile:
      - ALL water pixels   → WATER leaf     (order 2, big blue tile)
      - ALL land pixels    → LAND subtree   (split by entropy: order 3 or 4)
      - MIXED (boundary)   → TRANSITION leaf at depth=1 (order 3, green)
        This is the key: coastline tiles are defined geometrically
        (mask straddles water+land), NOT by entropy.

  Step C — Land-only entropy split
    Pure-land tiles at depth 0 → split once
    At depth 1: entropy >= ENTROPY_URBAN_THRESH → split again (order 4)
               entropy <  ENTROPY_URBAN_THRESH → transition leaf (order 3)
    depth 2 always → urban leaf (order 4)

Output:
  segmentation_map.json
  segmentation_vis.png
  water_mask.png           ← binary mask for inspection
"""

import json, logging
import numpy as np
from PIL import Image, ImageDraw, ImageFont

logging.basicConfig(level=logging.INFO, format="%(asctime)s  %(message)s")
log = logging.getLogger("QuadtreeSegmenter")

BASE_GRID            = 4       # starting coarse grid
WATER_THRESH         = 0.04    # pixel-level water gate: (B-R)/(R+G+B)
MIXED_THRESH         = 0.12    # fraction of tile that must be water to call it "mixed"
ENTROPY_URBAN_THRESH = 2.80    # depth-1 land tile: above this → urban (split again)

ORDER_MAP    = {0: 2, 1: 3, 2: 4}
CLASS_NAMES  = {0: "water/flat", 1: "transition/coastline", 2: "urban/detail"}
CLASS_COLORS = {
    0: (30,  120, 210),
    1: (60,  170, 80),
    2: (210, 55,  55),
}
OUTPUT_JSON  = "segmentation_map.json"
OUTPUT_VIS   = "segmentation_vis.png"
OUTPUT_MASK  = "water_mask.png"


# ── Step A: build pixel-level water mask ──────────────────────────
def build_water_mask(arr: np.ndarray) -> np.ndarray:
    """Returns boolean array (H, W): True = water pixel."""
    r = arr[:,:,0].astype(np.float32)
    g = arr[:,:,1].astype(np.float32)
    b = arr[:,:,2].astype(np.float32)
    score = (b - r) / (r + g + b + 1e-6)
    return score >= WATER_THRESH


# ── Entropy of gradient ───────────────────────────────────────────
def compute_entropy(patch: np.ndarray) -> float:
    gray = patch.mean(axis=2).astype(np.float32)
    dx   = np.diff(gray, axis=1)
    dy   = np.diff(gray, axis=0)
    mag  = np.sqrt(dx[:-1,:]**2 + dy[:,:-1]**2).ravel()
    if mag.max() == 0: return 0.0
    hist, _ = np.histogram(mag, bins=32, range=(0, mag.max()+1e-6))
    hist = hist.astype(np.float64); hist /= hist.sum()
    mask = hist > 0
    return float(-np.sum(hist[mask] * np.log2(hist[mask])))


# ── Step B+C: recursive quadtree ─────────────────────────────────
def subdivide(arr, wmask, x0, y0, w, h, depth, tiles):
    """
    wmask : full-image boolean water mask (H, W)
    Tile mask region: wmask[y0:y0+h, x0:x0+w]
    """
    tile_mask  = wmask[y0:y0+h, x0:x0+w]
    water_frac = tile_mask.mean()          # fraction of water pixels

    # ── Classify tile by mask composition ────────────────────────
    if water_frac >= (1.0 - MIXED_THRESH):
        # Predominantly water → water leaf (any depth)
        _leaf(tiles, 0, 2, depth, arr, wmask, x0, y0, w, h)

    elif water_frac >= MIXED_THRESH:
        # Mixed tile → coastline/transition
        if depth < 1 and w >= 16 and h >= 16:
            # Split once to localise the boundary more precisely
            _split(arr, wmask, x0, y0, w, h, depth+1, tiles)
        else:
            # At depth≥1 a mixed tile is the transition leaf
            _leaf(tiles, 1, 3, depth, arr, wmask, x0, y0, w, h)

    else:
        # Predominantly land → decide by entropy and depth
        if depth == 0:
            # Always split base land tiles
            _split(arr, wmask, x0, y0, w, h, depth+1, tiles)
        elif depth == 1:
            ent = compute_entropy(arr[y0:y0+h, x0:x0+w])
            if ent >= ENTROPY_URBAN_THRESH and w >= 16 and h >= 16:
                _split(arr, wmask, x0, y0, w, h, depth+1, tiles)
            else:
                _leaf(tiles, 1, 3, depth, arr, wmask, x0, y0, w, h)
        else:
            # depth == 2: urban leaf
            _leaf(tiles, 2, 4, depth, arr, wmask, x0, y0, w, h)


def _split(arr, wmask, x0, y0, w, h, depth, tiles):
    hw, hh = w//2, h//2
    subdivide(arr, wmask, x0,    y0,    hw, hh, depth, tiles)
    subdivide(arr, wmask, x0+hw, y0,    hw, hh, depth, tiles)
    subdivide(arr, wmask, x0,    y0+hh, hw, hh, depth, tiles)
    subdivide(arr, wmask, x0+hw, y0+hh, hw, hh, depth, tiles)


def _leaf(tiles, cls, order, depth, arr, wmask, x0, y0, w, h):
    patch      = arr[y0:y0+h, x0:x0+w]
    mean_color = patch.mean(axis=(0,1)).tolist()
    ent        = compute_entropy(patch)
    tile_mask  = wmask[y0:y0+h, x0:x0+w]
    tiles.append({
        "tile_x":      x0,
        "tile_y":      y0,
        "width":       w,
        "height":      h,
        "depth":       depth,
        "class":       cls,
        "order":       order,
        "class_name":  CLASS_NAMES[cls],
        "mean_color":  mean_color,
        "entropy":     ent,
        "water_frac":  float(tile_mask.mean()),
        "pixel_bbox":  [x0, y0, x0+w, y0+h],
    })


# ── Main ──────────────────────────────────────────────────────────
def segment_image(image_path: str) -> list:
    log.info(f"Loading: {image_path}")
    img  = Image.open(image_path).convert("RGB")
    w, h = img.size

    cw = (w // BASE_GRID) * BASE_GRID
    ch = (h // BASE_GRID) * BASE_GRID
    img = img.crop(((w-cw)//2, (h-ch)//2, (w-cw)//2+cw, (h-ch)//2+ch))
    arr = np.array(img)
    log.info(f"Cropped to {cw}×{ch}")

    # Step A: pixel-level mask
    wmask = build_water_mask(arr)
    log.info(f"Water mask: {wmask.mean()*100:.1f}% of pixels are water")
    _save_mask(wmask)

    # Step B+C: quadtree
    cell_w = cw // BASE_GRID
    cell_h = ch // BASE_GRID
    tiles  = []
    for ty in range(BASE_GRID):
        for tx in range(BASE_GRID):
            subdivide(arr, wmask,
                      tx*cell_w, ty*cell_h, cell_w, cell_h,
                      depth=0, tiles=tiles)

    from collections import Counter
    by_cls   = Counter(t["class"]  for t in tiles)
    by_depth = Counter(t["depth"]  for t in tiles)
    log.info(f"Quadtree → {len(tiles)} leaf tiles:")
    for c in range(3):
        log.info(f"  Class {c} ({CLASS_NAMES[c]}, order={ORDER_MAP[c]}): {by_cls[c]} tiles")
    log.info(f"  By depth: {dict(sorted(by_depth.items()))}")

    with open(OUTPUT_JSON, "w") as f:
        json.dump({
            "grid_size":  BASE_GRID,
            "image_size": [cw, ch],
            "cell_size":  [cell_w, cell_h],
            "max_depth":  2,
            "tiles":      tiles,
        }, f, indent=2)
    log.info(f"Saved: {OUTPUT_JSON}")

    _visualize(img, tiles, wmask)
    return tiles


def _save_mask(wmask: np.ndarray):
    vis = (wmask.astype(np.uint8) * 255)
    Image.fromarray(vis).save(OUTPUT_MASK)
    log.info(f"Saved: {OUTPUT_MASK}")


def _visualize(img: Image.Image, tiles: list, wmask: np.ndarray):
    # Blend a subtle blue tint over water pixels for context
    canvas  = img.copy().convert("RGBA")

    # Water tint overlay from mask
    tint = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
    tint_arr = np.array(tint)
    tint_arr[wmask, 0] = 30
    tint_arr[wmask, 1] = 100
    tint_arr[wmask, 2] = 200
    tint_arr[wmask, 3] = 40
    canvas = Image.alpha_composite(canvas, Image.fromarray(tint_arr, "RGBA"))

    overlay = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
    draw    = ImageDraw.Draw(overlay)

    try:
        font    = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 11)
        font_sm = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 9)
    except Exception:
        font = font_sm = ImageFont.load_default()

    for tile in tiles:
        cls             = tile["class"]
        order           = tile["order"]
        ent             = tile["entropy"]
        wf              = tile["water_frac"]
        x0, y0, x1, y1 = tile["pixel_bbox"]
        r, g, b         = CLASS_COLORS[cls]
        tile_w          = x1 - x0

        draw.rectangle([x0, y0, x1-1, y1-1],
                       fill=(r, g, b, 50),
                       outline=(r, g, b, 230), width=2)
        if tile_w >= 28:
            draw.text((x0+3, y0+2),  f"ord={order}",
                      fill=(255,255,255,255), font=font)
        if tile_w >= 55:
            draw.text((x0+3, y0+15), f"H={ent:.2f} wf={wf:.2f}",
                      fill=(220,220,220,210), font=font_sm)

    # Legend
    lx, ly = 8, img.height - 65
    for cls, name in CLASS_NAMES.items():
        r, g, b = CLASS_COLORS[cls]
        draw.rectangle([lx, ly, lx+12, ly+12], fill=(r, g, b, 230))
        draw.text((lx+16, ly), f"Class {cls}: {name}  (order {ORDER_MAP[cls]})",
                  fill=(255,255,255,255), font=font_sm)
        ly += 18

    Image.alpha_composite(canvas, overlay).convert("RGB").save(OUTPUT_VIS)
    log.info(f"Saved: {OUTPUT_VIS}")


if __name__ == "__main__":
    import sys
    path = sys.argv[1] if len(sys.argv) > 1 else "test1.jpg"
    segment_image(path)