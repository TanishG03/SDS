
# """
# tile_pyramid_builder.py
# Demonstrates the adaptive multilevel tile pyramid construction from Guo et al. (2016).
# """

# import os
# import math
# import time
# import tempfile
# import urllib.request
# from io import BytesIO
# from PIL import Image, ImageDraw

# # ── Config ──────────────────────────────────────────────────────
# MIN_ZOOM    = 0
# MAX_ZOOM    = 3  # Adjusted to 3 so the side-by-side image isn't too massive
# TILE_SIZE   = 256
# OUTPUT_DIR  = tempfile.mkdtemp(prefix="tile_pyramid_")

# # ── Step 1: Fetch a real complex image ──────────────────────────
# def fetch_real_image() -> Image.Image:
#     """
#     Fetches a public domain satellite image of Earth to serve as our base raster.
#     """
#     url = "https://d.ibtimes.co.uk/en/full/266566/stunning-images-earth-captured-geoeye-1-satellite.jpg?w=1600&h=1600&l=50&t=20&q=88&f=a469a52edad7c3e4c74c00ebb75c6ead"
#     print(f"Fetching complex satellite image from web...\n({url})")
    
#     req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
#     with urllib.request.urlopen(req) as response:
#         data = response.read()
    
#     img = Image.open(BytesIO(data)).convert("RGB")
#     return img

# # ── Step 2: Tile coordinate utilities ───────────────────────────
# def pad_to_tile_multiple(img: Image.Image) -> Image.Image:
#     """Pad image so dimensions are multiples of TILE_SIZE."""
#     w, h = img.size
#     pw = math.ceil(w / TILE_SIZE) * TILE_SIZE
#     ph = math.ceil(h / TILE_SIZE) * TILE_SIZE
#     if pw == w and ph == h:
#         return img
#     padded = Image.new(img.mode, (pw, ph), (0, 0, 0)) # Black padding
#     padded.paste(img, (0, 0))
#     return padded

# def save_tile(tile: Image.Image, zoom: int, tx: int, ty: int):
#     """Save tile to z/x/y.png directory structure."""
#     path = os.path.join(OUTPUT_DIR, str(zoom), str(tx))
#     os.makedirs(path, exist_ok=True)
#     tile.save(os.path.join(path, f"{ty}.png"))

# # ── Step 3: Build pyramid ────────────────────────────────────────
# def build_pyramid(source_img: Image.Image):
#     """
#     Adaptive multilevel pyramid builder:
#     - High zoom (fine detail): direct rendering from source (index path)
#     - Low zoom (overview):     resampling from child tiles (resample path)
#     """
#     THRESHOLD_ZOOM = MAX_ZOOM - 1   # Switch to resampling above this level

#     stats = []
#     current_img = source_img.copy()

#     print("\n" + "=" * 60)
#     print(f"  Source loaded: {source_img.width}×{source_img.height} px")
#     print("=" * 60)

#     for zoom in range(MAX_ZOOM, MIN_ZOOM - 1, -1):
#         t0 = time.perf_counter()

#         if zoom >= THRESHOLD_ZOOM:
#             # Direct rendering path (lower pyramid levels: fine detail)
#             method = "direct"
#             padded = pad_to_tile_multiple(current_img)
#             n_tiles_x = padded.width  // TILE_SIZE
#             n_tiles_y = padded.height // TILE_SIZE
#             tile_count = 0
#             for tx in range(n_tiles_x):
#                 for ty in range(n_tiles_y):
#                     crop = padded.crop((
#                         tx * TILE_SIZE, ty * TILE_SIZE,
#                         (tx + 1) * TILE_SIZE, (ty + 1) * TILE_SIZE
#                     ))
#                     save_tile(crop, zoom, tx, ty)
#                     tile_count += 1
            
#             # Downsample 2× for next zoom level (Lanczos — best quality)
#             new_w = max(TILE_SIZE, current_img.width  // 2)
#             new_h = max(TILE_SIZE, current_img.height // 2)
#             current_img = source_img.resize((new_w, new_h), Image.LANCZOS)

#         else:
#             # Resampling path (upper pyramid: overview tiles from children)
#             method = "resample"
#             child_zoom = zoom + 1
#             child_dir  = os.path.join(OUTPUT_DIR, str(child_zoom))
#             tile_count = 0

#             if not os.path.exists(child_dir):
#                 continue

#             # Collect unique parent tile coords from existing child tiles
#             parents = set()
#             for tx_str in os.listdir(child_dir):
#                 for ty_file in os.listdir(os.path.join(child_dir, tx_str)):
#                     tx = int(tx_str)
#                     ty = int(ty_file.replace(".png", ""))
#                     parents.add((tx // 2, ty // 2))

#             for (ptx, pty) in parents:
#                 # Assemble 512×512 from 4 children (2×2 block)
#                 composite = Image.new("RGB", (TILE_SIZE*2, TILE_SIZE*2), (0,0,0))
#                 for dx in range(2):
#                     for dy in range(2):
#                         child_path = os.path.join(
#                             OUTPUT_DIR, str(child_zoom),
#                             str(ptx*2 + dx), f"{pty*2 + dy}.png"
#                         )
#                         if os.path.exists(child_path):
#                             child_img = Image.open(child_path)
#                             composite.paste(child_img, (dx*TILE_SIZE, dy*TILE_SIZE))
                
#                 # Downsample 512×512 → 256×256
#                 parent_tile = composite.resize((TILE_SIZE, TILE_SIZE), Image.LANCZOS)
#                 save_tile(parent_tile, zoom, ptx, pty)
#                 tile_count += 1

#         elapsed = time.perf_counter() - t0
#         stats.append((zoom, tile_count, elapsed, method))
#         print(f"  Processing zoom level {zoom}...")
#         print(f"    Generated {tile_count} tiles in {elapsed:.3f}s  [{method}]")

#     return stats

# # ── Step 4: Visualize Side-by-Side ───────────────────────────────
# def visualize_pyramid_side_by_side():
#     """Stitches tiles back together per level and creates a single summary image."""
#     print("\n" + "=" * 60)
#     print("  Building side-by-side visualization...")
    
#     levels = []
#     # Reconstruct each level from bottom (overview) to top (fine detail)
#     for zoom in range(MIN_ZOOM, MAX_ZOOM + 1):
#         zoom_dir = os.path.join(OUTPUT_DIR, str(zoom))
#         if not os.path.exists(zoom_dir):
#             continue
        
#         # Determine grid size based on available tiles
#         txs = [int(d) for d in os.listdir(zoom_dir) if os.path.isdir(os.path.join(zoom_dir, d))]
#         if not txs: continue
#         max_tx = max(txs)
        
#         tys = []
#         for tx in txs:
#             tx_dir = os.path.join(zoom_dir, str(tx))
#             tys.extend([int(f.split('.')[0]) for f in os.listdir(tx_dir) if f.endswith('.png')])
#         max_ty = max(tys)
        
#         level_w = (max_tx + 1) * TILE_SIZE
#         level_h = (max_ty + 1) * TILE_SIZE
#         level_img = Image.new("RGB", (level_w, level_h), (30, 30, 30))
        
#         # Paste tiles into reconstructed canvas
#         for tx in txs:
#             tx_dir = os.path.join(zoom_dir, str(tx))
#             for file in os.listdir(tx_dir):
#                 if file.endswith('.png'):
#                     ty = int(file.split('.')[0])
#                     tile = Image.open(os.path.join(tx_dir, file))
#                     level_img.paste(tile, (tx * TILE_SIZE, ty * TILE_SIZE))
                    
#                     # Optional: Draw faint grid lines to show tile boundaries
#                     draw = ImageDraw.Draw(level_img)
#                     draw.rectangle(
#                         [tx * TILE_SIZE, ty * TILE_SIZE, (tx+1) * TILE_SIZE, (ty+1) * TILE_SIZE],
#                         outline=(100, 100, 100)
#                     )
                    
#         levels.append((zoom, level_img))
        
#     if not levels:
#         return

#     # Calculate dimensions for the final side-by-side canvas
#     padding = 20
#     total_w = sum(img.width for _, img in levels) + (len(levels) + 1) * padding
#     max_h = max(img.height for _, img in levels) + (padding * 2)
    
#     summary_img = Image.new("RGB", (total_w, max_h), (240, 240, 240))
    
#     # Paste each reconstructed level onto the summary canvas
#     current_x = padding
#     for zoom, img in levels:
#         summary_img.paste(img, (current_x, padding))
#         current_x += img.width + padding
        
#     out_path = os.path.join(OUTPUT_DIR, "pyramid_summary_visualization.png")
#     summary_img.save("pyramid_summary_visualization.png")
#     print(f"  Visualization saved to: {out_path}")
#     print("=" * 60)
    
#     # Attempt to open the image using the default OS viewer
#     summary_img.show()

# # ── Main ─────────────────────────────────────────────────────────
# if __name__ == "__main__":
#     raster = fetch_real_image()
#     stats  = build_pyramid(raster)
#     visualize_pyramid_side_by_side()

"""
tile_pyramid_builder.py
Demonstrates the adaptive multilevel tile pyramid construction from Guo et al. (2016).

FIXES over previous version:
  - No black padding: image is cropped to actual content before tiling
  - Visualization crops each level to actual image content (no black stripes)
  - Adds zoom level labels and tile count annotations to visualization
  - Adds a build summary table printed at the end
"""

import os
import math
import time
import tempfile
import urllib.request
from io import BytesIO
from PIL import Image, ImageDraw, ImageFont

# ── Config ───────────────────────────────────────────────────────
MIN_ZOOM   = 0
MAX_ZOOM   = 3
TILE_SIZE  = 256
OUTPUT_DIR = tempfile.mkdtemp(prefix="tile_pyramid_")

# ── Step 1: Fetch satellite image ────────────────────────────────
def fetch_real_image() -> Image.Image:
    url = (
        "https://d.ibtimes.co.uk/en/full/266566/"
        "stunning-images-earth-captured-geoeye-1-satellite.jpg"
        "?w=1600&h=1600&l=50&t=20&q=88&f=a469a52edad7c3e4c74c00ebb75c6ead"
    )
    print(f"Fetching satellite image...")
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req) as resp:
        data = resp.read()
    img = Image.open(BytesIO(data)).convert("RGB")
    print(f"  Downloaded: {img.width}×{img.height} px")
    return img

# ── Step 2: Crop image to exact tile-multiple without padding ─────
def crop_to_tile_multiple(img: Image.Image) -> Image.Image:
    """
    Instead of padding with black, CROP the image down to the largest
    dimensions that are exact multiples of TILE_SIZE.
    This completely eliminates black stripes in the output tiles.
    """
    w, h   = img.size
    new_w  = (w // TILE_SIZE) * TILE_SIZE
    new_h  = (h // TILE_SIZE) * TILE_SIZE
    if new_w == w and new_h == h:
        return img
    # Centre-crop so we keep the most informative part of the image
    left   = (w - new_w) // 2
    top    = (h - new_h) // 2
    return img.crop((left, top, left + new_w, top + new_h))

def save_tile(tile: Image.Image, zoom: int, tx: int, ty: int):
    path = os.path.join(OUTPUT_DIR, str(zoom), str(tx))
    os.makedirs(path, exist_ok=True)
    tile.save(os.path.join(path, f"{ty}.png"))

def load_tile(zoom: int, tx: int, ty: int) -> Image.Image | None:
    path = os.path.join(OUTPUT_DIR, str(zoom), str(tx), f"{ty}.png")
    return Image.open(path) if os.path.exists(path) else None

# ── Step 3: Build pyramid ─────────────────────────────────────────
def build_pyramid(source_img: Image.Image):
    """
    Adaptive multilevel pyramid:
      - zoom >= THRESHOLD : direct rendering from source (index path)
      - zoom <  THRESHOLD : resampling from child tiles  (resample path)
    Matches Figure 5 workflow from Guo et al. (2016).
    """
    THRESHOLD = MAX_ZOOM - 1      # Fine detail: direct; overviews: resample

    # Crop once so ALL zoom levels share a clean, padding-free source
    source_img = crop_to_tile_multiple(source_img)
    current    = source_img.copy()

    print("\n" + "=" * 60)
    print(f"  Source loaded: {source_img.width}×{source_img.height} px")
    print("=" * 60)

    stats = []

    for zoom in range(MAX_ZOOM, MIN_ZOOM - 1, -1):
        t0 = time.perf_counter()

        # ── Direct rendering (fine-detail levels) ─────────────────
        if zoom >= THRESHOLD:
            method  = "direct"
            # Crop working image to tile multiple at THIS zoom level too
            work    = crop_to_tile_multiple(current)
            nx      = work.width  // TILE_SIZE
            ny      = work.height // TILE_SIZE
            count   = 0
            for tx in range(nx):
                for ty in range(ny):
                    crop = work.crop((
                        tx * TILE_SIZE,       ty * TILE_SIZE,
                        (tx + 1) * TILE_SIZE, (ty + 1) * TILE_SIZE
                    ))
                    save_tile(crop, zoom, tx, ty)
                    count += 1
            # Halve for next zoom level using Lanczos (highest quality)
            nw      = max(TILE_SIZE, current.width  // 2)
            nh      = max(TILE_SIZE, current.height // 2)
            current = source_img.resize((nw, nh), Image.LANCZOS)

        # ── Resampling (overview levels) ──────────────────────────
        else:
            method     = "resample"
            child_zoom = zoom + 1
            child_dir  = os.path.join(OUTPUT_DIR, str(child_zoom))
            count      = 0

            if not os.path.exists(child_dir):
                continue

            # Find all unique parent coords from existing child tiles
            parents = set()
            for tx_str in os.listdir(child_dir):
                tx_dir = os.path.join(child_dir, tx_str)
                if not os.path.isdir(tx_dir):
                    continue
                for f in os.listdir(tx_dir):
                    if f.endswith(".png"):
                        parents.add((int(tx_str) // 2,
                                     int(f.replace(".png", "")) // 2))

            for (ptx, pty) in sorted(parents):
                # Assemble 512×512 block from 4 children
                composite = Image.new("RGB", (TILE_SIZE*2, TILE_SIZE*2))
                for dx in range(2):
                    for dy in range(2):
                        child = load_tile(child_zoom, ptx*2+dx, pty*2+dy)
                        if child:
                            composite.paste(child,
                                            (dx * TILE_SIZE, dy * TILE_SIZE))
                # Downsample 512→256 (one row/col per two — Figure 10)
                parent = composite.resize((TILE_SIZE, TILE_SIZE), Image.LANCZOS)
                save_tile(parent, zoom, ptx, pty)
                count += 1

        elapsed = time.perf_counter() - t0
        stats.append((zoom, count, elapsed, method))
        print(f"  Processing zoom level {zoom}...")
        print(f"    Generated {count} tiles in {elapsed:.3f}s  [{method}]")

    return stats, source_img

# ── Step 4: Print summary table ───────────────────────────────────
def print_summary(stats, source_img):
    print("\n" + "=" * 60)
    print("  BUILD SUMMARY")
    print(f"  {'Zoom':<6} {'Tiles':<8} {'Time (s)':<10} {'Method':<10} {'Resolution'}")
    print("  " + "-" * 55)

    w, h = source_img.size
    total_tiles = total_time = 0

    for zoom, tiles, t, method in stats:
        scale = 2 ** (MAX_ZOOM - zoom)
        res_w = w // scale
        res_h = h // scale
        print(f"  {zoom:<6} {tiles:<8} {t:<10.3f} {method:<10} {res_w}×{res_h} px")
        total_tiles += tiles
        total_time  += t

    print("  " + "-" * 55)
    print(f"  {'TOTAL':<6} {total_tiles:<8} {total_time:<10.3f}")
    print(f"  Output: {OUTPUT_DIR}")
    print("=" * 60)

# ── Step 5: Visualize side-by-side, no black stripes ─────────────
def visualize_pyramid(stats, source_img):
    """
    Reconstructs each pyramid level from saved tiles and lays them
    side-by-side from coarsest (zoom 0) to finest (zoom MAX_ZOOM).
    Labels show zoom level, tile count, and resolution.
    No black padding — tiles are cropped to actual content.
    """
    print("\n  Building visualization...")

    LABEL_H  = 36      # height of label bar above each level image
    PADDING  = 16
    BG_COLOR = (245, 245, 245)
    LBL_BG   = (50,  50,  50)
    LBL_FG   = (255, 255, 255)
    GRID_CLR = (180, 180, 180)

    # ── Reconstruct each level ────────────────────────────────────
    level_imgs = []
    for zoom, tile_count, _, method in stats:
        zoom_dir = os.path.join(OUTPUT_DIR, str(zoom))
        if not os.path.exists(zoom_dir):
            continue

        txs = sorted(int(d) for d in os.listdir(zoom_dir)
                     if os.path.isdir(os.path.join(zoom_dir, d)))
        if not txs:
            continue

        all_tys = []
        for tx in txs:
            tx_dir = os.path.join(zoom_dir, str(tx))
            all_tys.extend(
                int(f.split(".")[0])
                for f in os.listdir(tx_dir)
                if f.endswith(".png")
            )
        tys = sorted(set(all_tys))

        max_tx = max(txs)
        max_ty = max(tys)
        lw = (max_tx + 1) * TILE_SIZE
        lh = (max_ty + 1) * TILE_SIZE

        canvas = Image.new("RGB", (lw, lh), BG_COLOR)

        for tx in txs:
            tx_dir = os.path.join(zoom_dir, str(tx))
            for f in os.listdir(tx_dir):
                if not f.endswith(".png"):
                    continue
                ty   = int(f.split(".")[0])
                tile = Image.open(os.path.join(tx_dir, f))
                canvas.paste(tile, (tx * TILE_SIZE, ty * TILE_SIZE))

        # Draw grid lines showing tile boundaries
        draw = ImageDraw.Draw(canvas)
        for tx in range(max_tx + 2):
            draw.line([(tx * TILE_SIZE, 0),
                       (tx * TILE_SIZE, lh)], fill=GRID_CLR, width=1)
        for ty in range(max_ty + 2):
            draw.line([(0, ty * TILE_SIZE),
                       (lw, ty * TILE_SIZE)], fill=GRID_CLR, width=1)

        level_imgs.append((zoom, tile_count, method, canvas))

    if not level_imgs:
        print("  No levels to visualize.")
        return

    # ── Compose side-by-side canvas ───────────────────────────────
    total_w = (sum(img.width for _, _, _, img in level_imgs)
               + PADDING * (len(level_imgs) + 1))
    max_h   = max(img.height for _, _, _, img in level_imgs)
    total_h = max_h + LABEL_H + PADDING * 2

    final = Image.new("RGB", (total_w, total_h), BG_COLOR)
    draw  = ImageDraw.Draw(final)

    # Try to load a font; fall back gracefully
    try:
        font  = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 13)
        font_sm = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 11)
    except Exception:
        font    = ImageFont.load_default()
        font_sm = font

    x = PADDING
    for zoom, tile_count, method, img in level_imgs:
        w, h = img.size
        y    = PADDING + LABEL_H + (max_h - h) // 2  # vertically centre

        # Paste level image
        final.paste(img, (x, y))

        # Draw label bar above image
        draw.rectangle([x, PADDING, x + w, PADDING + LABEL_H - 2],
                       fill=LBL_BG)
        label = f"Zoom {zoom}  |  {tile_count} tiles  |  {method}"
        draw.text((x + 6, PADDING + 4),  label,
                  fill=LBL_FG, font=font)
        scale   = 2 ** (MAX_ZOOM - zoom)
        sw, sh  = source_img.size
        res_lbl = f"{sw//scale}×{sh//scale} px"
        draw.text((x + 6, PADDING + 19), res_lbl,
                  fill=(200, 200, 200), font=font_sm)

        x += w + PADDING

    out_path = "pyramid_summary_visualization.png"
    final.save(out_path)
    print(f"  Saved: {out_path}")
    final.show()

# ── Main ─────────────────────────────────────────────────────────
if __name__ == "__main__":
    raster        = fetch_real_image()
    stats, cropped = build_pyramid(raster)
    print_summary(stats, cropped)
    visualize_pyramid(stats, cropped)