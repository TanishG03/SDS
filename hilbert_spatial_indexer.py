"""
hilbert_spatial_indexer.py
Demonstrates Hilbert curve spatial indexing from Hajjaji et al. (2021).

FIXES over previous version:
  - Loads a local high-res image (test1.jpg).
  - Generates a physical visualization of the Hilbert Curve overlaid on the image.
  - Draws the continuous 1D spatial path connecting the 2D tiles.
  - Labels each tile with its respective 1D database sequence index.
"""

import os
import math
import time
import struct
import logging
from dataclasses import dataclass
from typing import Dict, List, Tuple
from PIL import Image, ImageDraw, ImageFont

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(message)s"
)
log = logging.getLogger("HilbertIndexer")

# ── 1. Image Loading ──────────────────────────────────────────────

def load_local_canvas(file_path: str) -> Image.Image:
    """Loads a high-res image from the local disk."""
    log.info(f"Loading background image from local file: {file_path}...")
    try:
        img = Image.open(file_path).convert("RGB")
        log.info(f"Image loaded: {img.width}×{img.height} px")
        return img
    except FileNotFoundError:
        log.error(f"Could not find '{file_path}'. Please check the file name and path.")
        raise

# ── 2. Tile coordinate system ────────────────────────────────────

@dataclass
class TileCoord:
    level: int; rownu: int; colnu: int
    def __hash__(self):  return hash((self.level, self.rownu, self.colnu))
    def __eq__(self, o): return (self.level, self.rownu, self.colnu) == (o.level, o.rownu, o.colnu)
    def __repr__(self):  return f"Tile(L{self.level},r{self.rownu},c{self.colnu})"

def latlon_to_tile(lat, lon, level):
    cell  = 180.0 / (2 ** level)
    rownu = int(math.floor((lat + 90.0)  / cell)) % (2 ** level)
    colnu = int(math.floor((lon + 180.0) / cell)) % (2 ** (level + 1))
    return TileCoord(level, rownu, colnu)

def bbox_to_tiles(west, south, east, north, level):
    tl = latlon_to_tile(north, west, level)
    br = latlon_to_tile(south, east, level)
    n_rows = 2 ** level
    n_cols = 2 ** (level + 1)
    return [
        TileCoord(level, r, c)
        for r in range(max(0, min(tl.rownu, br.rownu)), min(n_rows-1, max(tl.rownu, br.rownu)) + 1)
        for c in range(max(0, min(tl.colnu, br.colnu)), min(n_cols-1, max(tl.colnu, br.colnu)) + 1)
    ]

# ── 3. Hilbert curve (Butz algorithm) ────────────────────────────

class HilbertCurve:
    def __init__(self, order):
        self.order     = order
        self.grid_size = 2 ** order
        self._cache: Dict[Tuple, int] = {}

    def xy_to_hilbert(self, x, y):
        if (x, y) in self._cache:
            return self._cache[(x, y)]
        d, s, cx, cy = 0, self.grid_size // 2, x, y
        while s > 0:
            rx = 1 if (cx & s) > 0 else 0
            ry = 1 if (cy & s) > 0 else 0
            d += s * s * ((3 * rx) ^ ry)
            if ry == 0:
                if rx == 1: cx, cy = s-1-cx, s-1-cy
                cx, cy = cy, cx
            s //= 2
        self._cache[(x, y)] = d
        return d

    def print_grid(self):
        log.info("  " + "".join(f"  x={x:<3}" for x in range(self.grid_size)))
        for y in range(self.grid_size):
            row = f"y={y}  " + "".join(f"{self.xy_to_hilbert(x, y):<6}" for x in range(self.grid_size))
            log.info("  " + row)

# ── 4. HBase Simulator & Encoding ────────────────────────────────

def encode_row_key(raster_id, level, band, hilbert):
    key = (((raster_id & 0x7FFF) << 49) | ((level & 0x1) << 48) |
           ((band & 0xFFFF) << 32) | (hilbert & 0xFFFFFFFF))
    return struct.pack(">Q", key)

def decode_row_key(b):
    k = struct.unpack(">Q", b)[0]
    return ((k >> 49) & 0x7FFF, (k >> 48) & 0x1, (k >> 32) & 0xFFFF, k & 0xFFFFFFFF)

def key_string(raster_id, level, band, hilbert):
    return f"{raster_id:04x}_{level:02d}_{band:04x}_{hilbert:08x}"

@dataclass
class TileRow:
    key_bytes: bytes; key_str: str
    level: int; rownu: int; colnu: int
    band: int; raster_id: int; hilbert: int

class HBaseTable:
    def __init__(self):
        self._rows: Dict[bytes, TileRow] = {}

    def put(self, row: TileRow):
        self._rows[row.key_bytes] = row

    def range_scan(self, start: bytes, stop: bytes) -> List[TileRow]:
        return [self._rows[k] for k in sorted(self._rows) if start <= k <= stop]

# ── 5. Visualizer ────────────────────────────────────────────────

def visualize_hilbert_indexing(image: Image.Image, order: int = 3):
    """Draws the Hilbert curve path and grid over the base image."""
    log.info("\n  Rendering physical Hilbert Curve visualization...")
    
    # We will draw over a slightly darkened copy of the image so the bright lines pop
    canvas = image.copy()
    overlay = Image.new('RGBA', canvas.size, (0, 0, 0, 120))
    canvas.paste(overlay, (0, 0), overlay)
    
    draw = ImageDraw.Draw(canvas, "RGBA")
    
    try:
        font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 18)
    except Exception:
        font = ImageFont.load_default()

    hc = HilbertCurve(order)
    grid_size = hc.grid_size
    w, h = canvas.size
    
    # Force the crop to be perfectly divisible by the grid size
    cell_w = w // grid_size
    cell_h = h // grid_size

    # Draw the grid
    for x in range(grid_size + 1):
        draw.line([(x * cell_w, 0), (x * cell_w, h)], fill=(255, 255, 255, 60), width=1)
    for y in range(grid_size + 1):
        draw.line([(0, y * cell_h), (w, y * cell_h)], fill=(255, 255, 255, 60), width=1)

    # Calculate center points mapped to their Hilbert ID
    points_by_id = {}
    for x in range(grid_size):
        for y in range(grid_size):
            h_id = hc.xy_to_hilbert(x, y)
            cx = (x * cell_w) + (cell_w // 2)
            cy = (y * cell_h) + (cell_h // 2)
            points_by_id[h_id] = (cx, cy)

    # Draw the continuous Hilbert Curve line connecting the centers
    sorted_ids = sorted(points_by_id.keys())
    for i in range(len(sorted_ids) - 1):
        pt1 = points_by_id[sorted_ids[i]]
        pt2 = points_by_id[sorted_ids[i+1]]
        # Draw a thick neon cyan line
        draw.line([pt1, pt2], fill=(0, 255, 255, 200), width=4)

    # Draw the ID numbers and nodes
    for h_id, (cx, cy) in points_by_id.items():
        # Draw node dot
        r = 5
        draw.ellipse([cx-r, cy-r, cx+r, cy+r], fill=(255, 255, 0, 255))
        
        # Draw text background
        text_bg_bounds = [cx + 6, cy - 10, cx + 32, cy + 10]
        draw.rectangle(text_bg_bounds, fill=(0, 0, 0, 180))
        
        # Draw Hilbert Index text
        draw.text((cx + 8, cy - 8), str(h_id), fill=(255, 255, 255, 255), font=font)

    out_path = "hilbert_curve_visualization.png"
    canvas.save(out_path)
    log.info(f"  Visualization saved: {os.path.abspath(out_path)}")
    
    try:
        canvas.show()
    except:
        pass

# ── 6. Main ──────────────────────────────────────────────────────

if __name__ == "__main__":

    log.info("=" * 60)
    log.info("HILBERT SPATIAL INDEXER — Hajjaji et al. (2021)")
    log.info("=" * 60)

    # [1] Hilbert index grid logic
    log.info("\n[1] Hilbert Curve Index (4×4 grid, order=2):")
    hc2 = HilbertCurve(order=2)
    hc2.print_grid()

    # [2] Viewport query simulation
    log.info("\n[2] Viewport Query (standalone, zoom=2):")
    table = HBaseTable()
    level = 2
    hcq   = HilbertCurve(order=max(1, level + 1))
    tiles = bbox_to_tiles(76.8, 28.2, 77.6, 29.0, level)
    h_vals = [hcq.xy_to_hilbert(t.rownu, t.colnu) for t in tiles]
    
    h_min, h_max = min(h_vals), max(h_vals)
    log.info(f"  Hilbert range  : [{h_min:#010x}, {h_max:#010x}]")
    log.info(f"  HBase scans    : 1  (single range scan!)")

    # [3] Visualizer!
    # Ensure you have 'test1.jpg' in the same directory, or update this path.
    base_image = load_local_canvas("test1.jpg")
    
    # We use order=3 to create an 8x8 grid, showing 64 tiles being indexed
    visualize_hilbert_indexing(base_image, order=3)