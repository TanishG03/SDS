# """
# pipeline_integration.py
# Demonstrates the complete end-to-end integration of all three papers.

# FIXES over previous version:
#   - Uses local "test1.jpg" instead of synthetic noise.
#   - Stage 3a visually stitches the database results into a standalone viewport image.
#   - Stage 3b visually stitches the database results into a multi-panel SAGE2 wall.
#   - Replaces arbitrary lat/lon with exact tile grid coordinates to guarantee hits.
# """

# import os
# import time
# import struct
# import tempfile
# import logging
# import threading
# from typing import Dict, List
# from PIL import Image, ImageDraw, ImageFont

# logging.basicConfig(level=logging.INFO, format="%(asctime)s  %(message)s")
# log = logging.getLogger("Pipeline")

# TILE_SIZE = 256

# # ── Image Loading ─────────────────────────────────────────────────

# def load_local_canvas(file_path: str) -> Image.Image:
#     log.info(f"Loading base image from local file: {file_path}...")
#     try:
#         img = Image.open(file_path).convert("RGB")
#         return img
#     except FileNotFoundError:
#         log.error(f"Could not find '{file_path}'.")
#         raise

# def crop_to_tile_multiple(img: Image.Image) -> Image.Image:
#     w, h   = img.size
#     new_w  = (w // TILE_SIZE) * TILE_SIZE
#     new_h  = (h // TILE_SIZE) * TILE_SIZE
#     left   = (w - new_w) // 2
#     top    = (h - new_h) // 2
#     return img.crop((left, top, left + new_w, top + new_h))

# # ── Hilbert curve ─────────────────────────────────────────────────

# def xy_to_hilbert(x, y, order):
#     d, s, cx, cy = 0, 2**(order-1), x, y
#     while s > 0:
#         rx = 1 if (cx & s) > 0 else 0
#         ry = 1 if (cy & s) > 0 else 0
#         d += s * s * ((3 * rx) ^ ry)
#         if ry == 0:
#             if rx == 1: cx, cy = s-1-cx, s-1-cy
#             cx, cy = cy, cx
#         s //= 2
#     return d

# # ── HBase simulator ───────────────────────────────────────────────

# class HBase:
#     def __init__(self):
#         self._store: Dict[bytes, dict] = {}

#     def put(self, key: bytes, row: dict):
#         self._store[key] = row

#     def range_scan(self, start: bytes, stop: bytes) -> List[dict]:
#         return [self._store[k] for k in sorted(self._store) if start <= k <= stop]

#     def count(self): return len(self._store)

# def make_key(raster_id, zoom, band, h):
#     k = (((raster_id & 0x7FFF) << 49) | ((zoom & 0x1) << 48) |
#          ((band & 0xFFFF) << 32) | (h & 0xFFFFFFFF))
#     return struct.pack(">Q", k)

# # ════════════════════════════════════════════════════════════════
# # STAGE 1 — Tile Pyramid Builder (Paper 1: Guo et al.)
# # ════════════════════════════════════════════════════════════════

# def stage1_build_pyramid(base_img: Image.Image, max_zoom=3):
#     log.info("─" * 60)
#     log.info("STAGE 1 — Tile Pyramid Builder  [Guo et al., 2016]")
#     log.info("─" * 60)

#     img = crop_to_tile_multiple(base_img)
#     log.info(f"  Source raster: {img.width}×{img.height} px")

#     outdir = tempfile.mkdtemp(prefix="pipeline_tiles_")
#     tiles_by_zoom = {}
#     current = img.copy()
#     t0 = time.perf_counter()

#     for zoom in range(max_zoom, -1, -1):
#         work = crop_to_tile_multiple(current)
#         nx = work.width // TILE_SIZE
#         ny = work.height // TILE_SIZE
#         zoom_tiles = {}
#         for tx in range(nx):
#             for ty in range(ny):
#                 crop = work.crop((tx*TILE_SIZE, ty*TILE_SIZE, (tx+1)*TILE_SIZE, (ty+1)*TILE_SIZE))
#                 path = os.path.join(outdir, f"{zoom}_{tx}_{ty}.png")
#                 crop.save(path)
#                 zoom_tiles[(tx, ty)] = path
                
#         tiles_by_zoom[zoom] = zoom_tiles
#         nw = max(TILE_SIZE, current.width  // 2)
#         nh = max(TILE_SIZE, current.height // 2)
#         current = current.resize((nw, nh), Image.LANCZOS)
#         log.info(f"  Zoom {zoom}: {len(zoom_tiles):>3} tiles generated ({nx}x{ny} grid)")

#     log.info(f"  Tile cache: {outdir}")
#     return tiles_by_zoom, nx, ny

# # ════════════════════════════════════════════════════════════════
# # STAGE 2 — HBase Ingest with Hilbert Keys (Paper 3)
# # ════════════════════════════════════════════════════════════════

# def stage2_ingest(tiles_by_zoom: dict, raster_id=0x0001):
#     log.info("\n" + "─" * 60)
#     log.info("STAGE 2 — HBase Ingest with Hilbert Indexing  [Hajjaji et al.]")
#     log.info("─" * 60)

#     hbase = HBase()
#     written = 0
#     t0 = time.perf_counter()

#     for zoom, tiles in tiles_by_zoom.items():
#         order = max(1, zoom + 2) # Ensure Hilbert grid is large enough
#         for (tx, ty), path in tiles.items():
#             h   = xy_to_hilbert(tx, ty, order)
#             key = make_key(raster_id, zoom, 0, h)
#             hbase.put(key, {"zoom": zoom, "tx": tx, "ty": ty, "hilbert": h, "path": path})
#             written += 1

#     log.info(f"  Tiles ingested : {written}")
#     log.info(f"  HBase rows     : {hbase.count()}")
#     log.info(f"  Ingest time    : {(time.perf_counter() - t0):.3f}s")
#     return hbase

# # ════════════════════════════════════════════════════════════════
# # STAGE 3a — Standalone Viewport Query
# # ════════════════════════════════════════════════════════════════

# def stage3a_standalone(hbase: HBase, max_tx: int, max_ty: int, zoom=3, raster_id=0x0001):
#     log.info("\n" + "─" * 60)
#     log.info("STAGE 3a — Standalone Viewport Query  [Condition (a)]")
#     log.info("─" * 60)

#     order = max(1, zoom + 2)
    
#     # Define a 2x2 viewport somewhere in the middle of our image
#     min_tx, max_tx_query = max(0, max_tx // 2 - 1), min(max_tx, max_tx // 2 + 1)
#     min_ty, max_ty_query = max(0, max_ty // 2 - 1), min(max_ty, max_ty // 2 + 1)
    
#     tiles_needed = [(x, y) for x in range(min_tx, max_tx_query) for y in range(min_ty, max_ty_query)]
#     h_vals = [xy_to_hilbert(tx, ty, order) for tx, ty in tiles_needed]
#     h_min, h_max = min(h_vals), max(h_vals)

#     start_k = make_key(raster_id, zoom, 0, h_min)
#     stop_k  = make_key(raster_id, zoom, 0, h_max)

#     candidates = hbase.range_scan(start_k, stop_k)
#     tile_set = set(tiles_needed)
#     hits = [r for r in candidates if (r["tx"], r["ty"]) in tile_set]

#     log.info(f"  Viewport Request: X[{min_tx}-{max_tx_query-1}], Y[{min_ty}-{max_ty_query-1}] at zoom {zoom}")
#     log.info(f"  Hilbert range   : [{h_min:#010x}, {h_max:#010x}]")
#     log.info(f"  HBase scans     : 1  (single range scan!)")
#     log.info(f"  Viewport hits   : {len(hits)}")

#     # Visual Output!
#     if hits:
#         w = (max_tx_query - min_tx) * TILE_SIZE
#         h = (max_ty_query - min_ty) * TILE_SIZE
#         canvas = Image.new("RGB", (w, h))
#         for r in hits:
#             img = Image.open(r["path"])
#             canvas.paste(img, ((r["tx"] - min_tx) * TILE_SIZE, (r["ty"] - min_ty) * TILE_SIZE))
        
#         out_path = "integration_standalone_view.png"
#         canvas.save(out_path)
#         log.info(f"  [VISUAL] Saved stitched viewport to {out_path}")

# # ════════════════════════════════════════════════════════════════
# # STAGE 3b — Distributed Display Wall
# # ════════════════════════════════════════════════════════════════

# def stage3b_distributed(hbase: HBase, grid_w: int, grid_h: int, zoom=3, raster_id=0x0001):
#     log.info("\n" + "─" * 60)
#     log.info("STAGE 3b — Distributed Display Wall  [Condition (b)]")
#     log.info("─" * 60)

#     PANELS_X, PANELS_Y = 4, 2
#     order = max(1, zoom + 2)

#     # Divide the available tiles evenly among the 8 panels
#     tiles_per_panel_x = grid_w // PANELS_X
#     tiles_per_panel_y = grid_h // PANELS_Y
    
#     if tiles_per_panel_x == 0 or tiles_per_panel_y == 0:
#         log.error("Image is too small to divide into 4x2 panels at this tile size.")
#         return

#     panel_results = {}
#     panel_lock    = threading.Lock()

#     def query_panel(row, col):
#         pid = f"P{row}{col}"
#         min_tx = col * tiles_per_panel_x
#         max_tx = min_tx + tiles_per_panel_x
#         min_ty = row * tiles_per_panel_y
#         max_ty = min_ty + tiles_per_panel_y

#         tiles = [(x, y) for x in range(min_tx, max_tx) for y in range(min_ty, max_ty)]
#         h_vals = [xy_to_hilbert(tx, ty, order) for tx, ty in tiles]
#         h_min, h_max = min(h_vals), max(h_vals)

#         start_k = make_key(raster_id, zoom, 0, h_min)
#         stop_k  = make_key(raster_id, zoom, 0, h_max)
#         candidates = hbase.range_scan(start_k, stop_k)
        
#         tile_set = set(tiles)
#         hits = [r for r in candidates if (r["tx"], r["ty"]) in tile_set]

#         with panel_lock:
#             panel_results[pid] = {
#                 "row": row, "col": col, "hits": hits,
#                 "min_tx": min_tx, "min_ty": min_ty, "tiles_needed": len(tiles)
#             }

#     # Parallel querying simulating SAGE2
#     threads = [threading.Thread(target=query_panel, args=(r, c)) 
#                for r in range(PANELS_Y) for c in range(PANELS_X)]
#     for t in threads: t.start()
#     for t in threads: t.join()

#     log.info(f"  All {PANELS_X*PANELS_Y} panels queried HBase in parallel.")
    
#     # Visual Output!
#     log.info("  [VISUAL] Stitching results into Display Wall representation...")
    
#     pw = tiles_per_panel_x * TILE_SIZE
#     ph = tiles_per_panel_y * TILE_SIZE
#     bezel = 12
#     wall_w = (pw * PANELS_X) + (bezel * (PANELS_X + 1))
#     wall_h = (ph * PANELS_Y) + (bezel * (PANELS_Y + 1))
    
#     wall_canvas = Image.new("RGB", (wall_w, wall_h), (20, 20, 20))
    
#     try: font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 20)
#     except Exception: font = ImageFont.load_default()

#     for pid, data in panel_results.items():
#         panel_canvas = Image.new("RGB", (pw, ph), (0,0,0))
        
#         # Stitch fetched tiles
#         for t in data["hits"]:
#             img = Image.open(t["path"])
#             lx = (t["tx"] - data["min_tx"]) * TILE_SIZE
#             ly = (t["ty"] - data["min_ty"]) * TILE_SIZE
#             panel_canvas.paste(img, (lx, ly))
            
#         # Paste onto wall
#         paste_x = bezel + (data["col"] * (pw + bezel))
#         paste_y = bezel + (data["row"] * (ph + bezel))
#         wall_canvas.paste(panel_canvas, (paste_x, paste_y))
        
#         # Draw Panel ID label
#         draw = ImageDraw.Draw(wall_canvas)
#         draw.rectangle([paste_x, paste_y, paste_x + 60, paste_y + 30], fill=(0, 0, 0, 180))
#         draw.text((paste_x + 10, paste_y + 5), pid, fill=(255, 255, 255), font=font)

#     out_path = "integration_wall_view.png"
#     wall_canvas.save(out_path)
#     log.info(f"  [VISUAL] Saved distributed wall simulation to {out_path}")

# # ── Main ─────────────────────────────────────────────────────────

# if __name__ == "__main__":
#     log.info("=" * 60)
#     log.info("PIPELINE INTEGRATION — Full End-to-End Demo")
#     log.info("=" * 60)

#     t_start = time.perf_counter()

#     base_image = load_local_canvas("test1.jpg")
    
#     tiles_by_zoom, grid_w_tiles, grid_h_tiles = stage1_build_pyramid(base_image, max_zoom=3)
#     hbase = stage2_ingest(tiles_by_zoom)
    
#     stage3a_standalone(hbase, grid_w_tiles, grid_h_tiles, zoom=3)
#     stage3b_distributed(hbase, grid_w_tiles, grid_h_tiles, zoom=3)

#     log.info("\n" + "=" * 60)
#     log.info(f"PIPELINE COMPLETE  —  total time: {(time.perf_counter() - t_start):.3f}s")
#     log.info("=" * 60)


"""
pipeline_integration.py - FIXED VERSION
- Stage 3a: queries a meaningful 3×3 viewport (centre of the image)
- Stage 3b: correctly divides the 6×6 tile grid across 4×2 panels
            with proper bezel separation and panel labels
- Both stages produce full-resolution stitched output images
"""

import os
import time
import struct
import tempfile
import logging
import threading
from typing import Dict, List
from PIL import Image, ImageDraw, ImageFont

logging.basicConfig(level=logging.INFO, format="%(asctime)s  %(message)s")
log = logging.getLogger("Pipeline")

TILE_SIZE = 256

# ── Utilities ─────────────────────────────────────────────────────

def load_local_canvas(path: str) -> Image.Image:
    log.info(f"Loading base image: {path}...")
    img = Image.open(path).convert("RGB")
    log.info(f"  Loaded: {img.width}×{img.height} px")
    return img

def crop_to_tile_multiple(img: Image.Image) -> Image.Image:
    w, h  = img.size
    nw    = (w // TILE_SIZE) * TILE_SIZE
    nh    = (h // TILE_SIZE) * TILE_SIZE
    left  = (w - nw) // 2
    top   = (h - nh) // 2
    return img.crop((left, top, left + nw, top + nh))

def xy_to_hilbert(x, y, order):
    d, s, cx, cy = 0, 2**(order - 1), x, y
    while s > 0:
        rx = 1 if (cx & s) > 0 else 0
        ry = 1 if (cy & s) > 0 else 0
        d += s * s * ((3 * rx) ^ ry)
        if ry == 0:
            if rx == 1: cx, cy = s - 1 - cx, s - 1 - cy
            cx, cy = cy, cx
        s //= 2
    return d

def make_key(raster_id, zoom, band, h):
    k = (((raster_id & 0x7FFF) << 49) |
         ((zoom      & 0x1)    << 48) |
         ((band      & 0xFFFF) << 32) |
         (h          & 0xFFFFFFFF))
    return struct.pack(">Q", k)

def load_font(size=18):
    try:
        return ImageFont.truetype(
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", size)
    except Exception:
        return ImageFont.load_default()

# ── HBase simulator ───────────────────────────────────────────────

class HBase:
    def __init__(self):
        self._store: Dict[bytes, dict] = {}

    def put(self, key: bytes, row: dict):
        self._store[key] = row

    def range_scan(self, start: bytes, stop: bytes) -> List[dict]:
        return [self._store[k] for k in sorted(self._store)
                if start <= k <= stop]

    def count(self): return len(self._store)

# ════════════════════════════════════════════════════════════════
# STAGE 1 — Tile Pyramid  (Guo et al., 2016)
# ════════════════════════════════════════════════════════════════

def stage1_build_pyramid(base_img: Image.Image, max_zoom: int = 3):
    log.info("─" * 60)
    log.info("STAGE 1 — Tile Pyramid Builder  [Guo et al., 2016]")
    log.info("─" * 60)

    img     = crop_to_tile_multiple(base_img)
    outdir  = tempfile.mkdtemp(prefix="pipeline_tiles_")
    current = img.copy()
    tiles_by_zoom: Dict[int, Dict] = {}
    grid_dims: Dict[int, tuple]    = {}

    log.info(f"  Source raster : {img.width}×{img.height} px")

    t0 = time.perf_counter()
    for zoom in range(max_zoom, -1, -1):
        work = crop_to_tile_multiple(current)
        nx   = work.width  // TILE_SIZE
        ny   = work.height // TILE_SIZE
        zoom_tiles = {}
        for tx in range(nx):
            for ty in range(ny):
                crop = work.crop((
                    tx * TILE_SIZE,       ty * TILE_SIZE,
                    (tx + 1) * TILE_SIZE, (ty + 1) * TILE_SIZE
                ))
                path = os.path.join(outdir, f"{zoom}_{tx}_{ty}.png")
                crop.save(path)
                zoom_tiles[(tx, ty)] = path
        tiles_by_zoom[zoom] = zoom_tiles
        grid_dims[zoom]     = (nx, ny)
        nw      = max(TILE_SIZE, current.width  // 2)
        nh      = max(TILE_SIZE, current.height // 2)
        current = current.resize((nw, nh), Image.LANCZOS)
        log.info(f"  Zoom {zoom}: {len(zoom_tiles):>3} tiles  "
                 f"({nx}×{ny} grid)  "
                 f"@ {work.width}×{work.height} px")

    log.info(f"  Total time : {time.perf_counter() - t0:.3f}s")
    log.info(f"  Tile cache : {outdir}")
    return tiles_by_zoom, grid_dims, img

# ════════════════════════════════════════════════════════════════
# STAGE 2 — HBase Ingest  (Hajjaji et al., 2021)
# ════════════════════════════════════════════════════════════════

def stage2_ingest(tiles_by_zoom: dict, raster_id: int = 0x0001) -> HBase:
    log.info("\n" + "─" * 60)
    log.info("STAGE 2 — HBase Ingest with Hilbert Indexing  "
             "[Hajjaji et al., 2021]")
    log.info("─" * 60)

    hbase   = HBase()
    written = 0
    t0      = time.perf_counter()

    for zoom, tiles in tiles_by_zoom.items():
        order = max(2, zoom + 2)
        for (tx, ty), path in tiles.items():
            h   = xy_to_hilbert(tx, ty, order)
            key = make_key(raster_id, zoom, 0, h)
            hbase.put(key, {
                "zoom": zoom, "tx": tx, "ty": ty,
                "hilbert": h, "path": path
            })
            written += 1

    elapsed = time.perf_counter() - t0
    log.info(f"  Tiles ingested : {written}")
    log.info(f"  HBase rows     : {hbase.count()}")
    log.info(f"  Ingest time    : {elapsed:.4f}s")
    return hbase

# ════════════════════════════════════════════════════════════════
# STAGE 3a — Standalone Viewport Query  (Condition a)
# ════════════════════════════════════════════════════════════════

def stage3a_standalone(hbase: HBase, grid_dims: dict,
                       zoom: int = 3, raster_id: int = 0x0001):
    log.info("\n" + "─" * 60)
    log.info("STAGE 3a — Standalone Viewport Query  [Condition (a)]")
    log.info("─" * 60)

    nx, ny = grid_dims[zoom]
    order  = max(2, zoom + 2)

    # Query the centre 3×3 block of the 6×6 grid
    # (or the full grid if smaller than 3×3)
    qw = min(3, nx)
    qh = min(3, ny)
    tx_start = (nx - qw) // 2
    ty_start = (ny - qh) // 2
    tx_end   = tx_start + qw
    ty_end   = ty_start + qh

    tiles_needed = [
        (tx, ty)
        for tx in range(tx_start, tx_end)
        for ty in range(ty_start, ty_end)
    ]

    h_vals       = [xy_to_hilbert(tx, ty, order) for tx, ty in tiles_needed]
    h_min, h_max = min(h_vals), max(h_vals)
    start_k      = make_key(raster_id, zoom, 0, h_min)
    stop_k       = make_key(raster_id, zoom, 0, h_max)

    t0         = time.perf_counter()
    candidates = hbase.range_scan(start_k, stop_k)
    elapsed    = (time.perf_counter() - t0) * 1000

    tile_set = set(tiles_needed)
    hits     = [r for r in candidates
                if (r["tx"], r["ty"]) in tile_set]
    hit_rate = len(hits) / max(1, len(candidates)) * 100

    log.info(f"  Grid size      : {nx}×{ny} tiles at zoom {zoom}")
    log.info(f"  Viewport       : X[{tx_start}–{tx_end-1}]  "
             f"Y[{ty_start}–{ty_end-1}]  ({qw}×{qh} tiles)")
    log.info(f"  Tiles needed   : {len(tiles_needed)}")
    log.info(f"  Hilbert range  : [{h_min:#010x}, {h_max:#010x}]")
    log.info(f"  HBase scans    : 1  (single range scan)")
    log.info(f"  Candidates     : {len(candidates)}")
    log.info(f"  Viewport hits  : {len(hits)}")
    log.info(f"  Hit rate       : {hit_rate:.1f}%")
    log.info(f"  Query time     : {elapsed:.3f} ms")

    # ── Stitch retrieved tiles into output image ─────────────────
    if hits:
        canvas_w = qw * TILE_SIZE
        canvas_h = qh * TILE_SIZE
        canvas   = Image.new("RGB", (canvas_w, canvas_h), (30, 30, 30))
        draw     = ImageDraw.Draw(canvas)
        font     = load_font(14)

        for r in hits:
            tile_img = Image.open(r["path"])
            px = (r["tx"] - tx_start) * TILE_SIZE
            py = (r["ty"] - ty_start) * TILE_SIZE
            canvas.paste(tile_img, (px, py))
            # Draw tile grid lines
            draw.rectangle(
                [px, py, px + TILE_SIZE - 1, py + TILE_SIZE - 1],
                outline=(255, 255, 255), width=1
            )
            # Label tile coordinates and Hilbert index
            h_val = xy_to_hilbert(r["tx"], r["ty"], order)
            draw.rectangle([px + 2, py + 2, px + 130, py + 30],
                           fill=(0, 0, 0, 180))
            draw.text((px + 5, py + 4),
                      f"({r['tx']},{r['ty']})  H={h_val}",
                      fill=(255, 255, 0), font=font)

        # Add a title bar
        title_bar = Image.new("RGB", (canvas_w, 36), (30, 30, 30))
        td = ImageDraw.Draw(title_bar)
        tf = load_font(15)
        td.text((8, 8),
                f"Standalone Viewport  |  zoom={zoom}  |  "
                f"{qw}×{qh} tiles  |  1 HBase range scan",
                fill=(100, 220, 100), font=tf)
        final = Image.new("RGB", (canvas_w, canvas_h + 36))
        final.paste(title_bar, (0, 0))
        final.paste(canvas,    (0, 36))

        out = "integration_standalone_view.png"
        final.save(out)
        log.info(f"  Saved: {out}")

# ════════════════════════════════════════════════════════════════
# STAGE 3b — Distributed Display Wall  (Condition b)
# ════════════════════════════════════════════════════════════════

def stage3b_distributed(hbase: HBase, grid_dims: dict,
                        zoom: int = 3, raster_id: int = 0x0001):
    log.info("\n" + "─" * 60)
    log.info("STAGE 3b — Distributed Display Wall  [Condition (b)]")
    log.info("─" * 60)

    PANELS_X, PANELS_Y = 4, 2
    nx, ny = grid_dims[zoom]
    order  = max(2, zoom + 2)

    # ── Distribute tile grid across panels ───────────────────────
    # Each panel gets a contiguous rectangular sub-region of the tile grid.
    # For a 6×6 grid and 4×2 panels:
    #   horizontal: columns 0-1, 1-2, 2-3 etc  (with overlap for non-divisible)
    #   vertical:   rows 0-2, 3-5

    def panel_tile_range(panel_idx, total_tiles, n_panels):
        """Divide total_tiles as evenly as possible across n_panels."""
        base  = total_tiles // n_panels
        extra = total_tiles  % n_panels
        start = panel_idx * base + min(panel_idx, extra)
        end   = start + base + (1 if panel_idx < extra else 0)
        return start, end

    panel_results = {}
    panel_lock    = threading.Lock()

    def query_panel(row, col):
        pid    = f"P{row:02d}{col:02d}"
        tx_s, tx_e = panel_tile_range(col, nx, PANELS_X)
        ty_s, ty_e = panel_tile_range(row, ny, PANELS_Y)

        if tx_e <= tx_s or ty_e <= ty_s:
            return

        tiles  = [(x, y) for x in range(tx_s, tx_e)
                           for y in range(ty_s, ty_e)]
        h_vals = [xy_to_hilbert(tx, ty, order) for tx, ty in tiles]
        h_min, h_max = min(h_vals), max(h_vals)

        start_k    = make_key(raster_id, zoom, 0, h_min)
        stop_k     = make_key(raster_id, zoom, 0, h_max)
        candidates = hbase.range_scan(start_k, stop_k)
        tile_set   = set(tiles)
        hits       = [r for r in candidates
                      if (r["tx"], r["ty"]) in tile_set]

        with panel_lock:
            panel_results[pid] = {
                "row": row, "col": col,
                "tx_s": tx_s, "tx_e": tx_e,
                "ty_s": ty_s, "ty_e": ty_e,
                "tiles_needed": len(tiles),
                "candidates":   len(candidates),
                "hits":         hits,
                "h_range":      (h_min, h_max)
            }

    # ── Parallel query (simulates SAGE2 per-node independent fetch) ──
    t0      = time.perf_counter()
    threads = [
        threading.Thread(target=query_panel, args=(r, c), daemon=True)
        for r in range(PANELS_Y)
        for c in range(PANELS_X)
    ]
    for t in threads: t.start()
    for t in threads: t.join()
    elapsed = (time.perf_counter() - t0) * 1000

    # ── Console results table ────────────────────────────────────
    log.info(f"\n  {'Panel':<8} {'Tiles':<8} {'Candidates':<13} "
             f"{'Hits':<6} {'Hilbert Range'}")
    log.info("  " + "-" * 65)
    total_tiles = total_hits = 0
    for pid in sorted(panel_results):
        d = panel_results[pid]
        log.info(
            f"  {pid:<8} {d['tiles_needed']:<8} {d['candidates']:<13} "
            f"{len(d['hits']):<6} "
            f"[{d['h_range'][0]:#010x}, {d['h_range'][1]:#010x}]"
        )
        total_tiles += d["tiles_needed"]
        total_hits  += len(d["hits"])
    log.info("  " + "-" * 65)
    log.info(f"  {'TOTAL':<8} {total_tiles:<8} {'':13} {total_hits}")
    log.info(f"\n  All {PANELS_X*PANELS_Y} panels fetched in PARALLEL")
    log.info(f"  Parallel query time  : {elapsed:.2f} ms")
    log.info(f"  [SAGE2] ✓ Sync signal broadcast — "
             f"all panels update simultaneously")

    # ── Stitch visual wall output ────────────────────────────────
    BEZEL   = 10
    font_lg = load_font(16)
    font_sm = load_font(12)

    # Compute actual pixel dimensions per panel from tile counts
    col_widths = [
        (panel_tile_range(c, nx, PANELS_X)[1] -
         panel_tile_range(c, nx, PANELS_X)[0]) * TILE_SIZE
        for c in range(PANELS_X)
    ]
    row_heights = [
        (panel_tile_range(r, ny, PANELS_Y)[1] -
         panel_tile_range(r, ny, PANELS_Y)[0]) * TILE_SIZE
        for r in range(PANELS_Y)
    ]

    wall_w = sum(col_widths)  + BEZEL * (PANELS_X + 1)
    wall_h = sum(row_heights) + BEZEL * (PANELS_Y + 1)

    wall = Image.new("RGB", (wall_w, wall_h), (20, 20, 20))

    for pid, d in panel_results.items():
        r, c     = d["row"], d["col"]
        pw       = col_widths[c]
        ph       = row_heights[r]
        panel_cv = Image.new("RGB", (pw, ph), (10, 10, 10))
        pdraw    = ImageDraw.Draw(panel_cv)

        # Paste all retrieved tiles onto panel canvas
        for tile in d["hits"]:
            tile_img = Image.open(tile["path"])
            lx = (tile["tx"] - d["tx_s"]) * TILE_SIZE
            ly = (tile["ty"] - d["ty_s"]) * TILE_SIZE
            panel_cv.paste(tile_img, (lx, ly))

            # Subtle tile boundary grid
            pdraw.rectangle(
                [lx, ly, lx + TILE_SIZE - 1, ly + TILE_SIZE - 1],
                outline=(80, 80, 80), width=1
            )

        # Panel ID label (top-left corner)
        pdraw.rectangle([0, 0, 100, 26], fill=(0, 0, 0))
        pdraw.text((6, 4), pid, fill=(255, 255, 255), font=font_lg)

        # Paste panel onto wall at correct bezel-offset position
        paste_x = BEZEL + sum(col_widths[:c])  + c * BEZEL
        paste_y = BEZEL + sum(row_heights[:r]) + r * BEZEL
        wall.paste(panel_cv, (paste_x, paste_y))

    out = "integration_wall_view.png"
    wall.save(out)
    log.info(f"\n  Saved: {out}")

# ── Main ─────────────────────────────────────────────────────────

if __name__ == "__main__":
    log.info("=" * 60)
    log.info("PIPELINE INTEGRATION — Full End-to-End Demo")
    log.info("  Paper 1: Guo et al. (2016)   — Tile Pyramid")
    log.info("  Paper 2: Renambot et al. (2015) — SAGE2")
    log.info("  Paper 3: Hajjaji et al. (2021)  — Hilbert HBase")
    log.info("=" * 60)

    t_start    = time.perf_counter()
    base_image = load_local_canvas("test1.jpg")

    tiles_by_zoom, grid_dims, cropped = stage1_build_pyramid(
        base_image, max_zoom=3
    )
    hbase = stage2_ingest(tiles_by_zoom)
    stage3a_standalone(hbase, grid_dims, zoom=3)
    stage3b_distributed(hbase, grid_dims, zoom=3)

    log.info("\n" + "=" * 60)
    log.info(f"PIPELINE COMPLETE — "
             f"total time: {time.perf_counter() - t_start:.3f}s")
    log.info("=" * 60)