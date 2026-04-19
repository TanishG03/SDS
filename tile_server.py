"""
tile_server.py
Stage 2 (server) — Flask API serving adaptive Hilbert-indexed tiles.

Endpoints:
  GET /tile?z=<zoom>&x=<tile_x>&y=<tile_y>
      Returns the PNG tile for a given zoom/x/y.
      At zoom 0 = full base tile (coarsest).
      At zoom 1 = base tile.
      At zoom 2+ = sub-tiles according to per-region Hilbert order.

  GET /lod?viewport=<west,south,east,north>&zoom=<z>
      Returns JSON describing which tiles are "live" (full resolution)
      and which are "collapsed" (averaged parent) for the given viewport
      and zoom level. This is what the React viewer queries on zoom change.

  GET /segmentation
      Returns the raw segmentation_map.json (useful for the React viewer
      to colour-code the region overlay).

  GET /index_stats
      Returns a summary of the tile index.

Run:
  pip install flask pillow numpy
  python tile_server.py

Then open http://localhost:5000/
"""
from flask_cors import CORS
import os
import io
import json
import logging
from collections import defaultdict

import numpy as np
from PIL import Image
from flask import Flask, jsonify, request, send_file, abort

logging.basicConfig(level=logging.INFO, format="%(asctime)s  %(message)s")
log = logging.getLogger("TileServer")

SEG_MAP   = "segmentation_map.json"
INDEX_FILE = "tile_index.json"
TILE_DIR   = "tile_store"

app = Flask(__name__)
CORS(app)

# ── Load data at startup ──────────────────────────────────────────
def _load_data():
    if not os.path.exists(SEG_MAP):
        raise FileNotFoundError(
            f"'{SEG_MAP}' not found. Run region_segmenter.py first.")
    if not os.path.exists(INDEX_FILE):
        raise FileNotFoundError(
            f"'{INDEX_FILE}' not found. Run adaptive_hilbert_indexer.py first.")

    with open(SEG_MAP)   as f: seg   = json.load(f)
    with open(INDEX_FILE) as f: index = json.load(f)

    # Build lookup: (base_tx, base_ty) → list of sub-tile records
    base_lookup = defaultdict(list)
    for rec in index:
        base_lookup[(rec["base_tx"], rec["base_ty"])].append(rec)

    # Build lookup: (base_tx, base_ty, sub_x, sub_y) → record
    sub_lookup = {}
    for rec in index:
        sub_lookup[(rec["base_tx"], rec["base_ty"],
                    rec["sub_x"],  rec["sub_y"])] = rec

    # Base tile info from segmentation
    tile_meta = {(t["tile_x"], t["tile_y"]): t for t in seg["tiles"]}

    log.info(f"Loaded {len(index)} sub-tile records across "
             f"{len(base_lookup)} base tiles.")
    return seg, index, base_lookup, sub_lookup, tile_meta


try:
    SEG, INDEX, BASE_LOOKUP, SUB_LOOKUP, TILE_META = _load_data()
    GRID_SIZE  = SEG["grid_size"]
    IMG_W, IMG_H = SEG["image_size"]
    CELL_W, CELL_H = SEG["cell_size"]
    DATA_OK = True
except FileNotFoundError as e:
    log.warning(f"Data not loaded: {e}")
    DATA_OK = False


# ── Helpers ───────────────────────────────────────────────────────
def _png_response(img: Image.Image):
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)
    return send_file(buf, mimetype="image/png")


def _average_tile_color(records: list[dict]) -> Image.Image:
    """Creates a solid-color tile from the mean color of all sub-records."""
    colors = np.array([r["mean_color"] for r in records])
    avg    = colors.mean(axis=0).astype(np.uint8)
    img    = Image.new("RGB", (CELL_W, CELL_H), tuple(avg.tolist()))
    return img


def _collapse_level(order: int, zoom: int) -> bool:
    """
    Returns True if this region's tiles should be collapsed at this zoom.
    Logic:
      order 2 (water)    → collapse at zoom <= 1
      order 3 (shore)    → collapse at zoom <= 0
      order 4 (urban)    → never collapse (always fine)
    """
    collapse_at = {2: 1, 3: 0, 4: -1}
    return zoom <= collapse_at.get(order, -1)


# ── Routes ────────────────────────────────────────────────────────
@app.route("/")
def index_page():
    return jsonify({
        "status": "ok",
        "endpoints": ["/tile", "/lod", "/segmentation", "/index_stats"],
        "data_loaded": DATA_OK,
    })


@app.route("/segmentation")
def segmentation():
    if not DATA_OK:
        abort(503, "Run region_segmenter.py first.")
    return jsonify(SEG)


@app.route("/index_stats")
def index_stats():
    if not DATA_OK:
        abort(503)
    from collections import Counter
    class_counts = Counter(r["region_class"] for r in INDEX)
    order_counts = Counter(r["hilbert_order"] for r in INDEX)
    return jsonify({
        "total_sub_tiles": len(INDEX),
        "base_tiles":      len(BASE_LOOKUP),
        "by_class":        dict(class_counts),
        "by_order":        dict(order_counts),
    })


@app.route("/image")
def get_image():
    for name in ["test1.jpg", "test1.png", "image.jpg", "image.png"]:
        if os.path.exists(name):
            return send_file(name, mimetype="image/jpeg")
    abort(404, "Source image not found")

@app.route("/tile")
def get_tile():
    """
    GET /tile?z=<int>&x=<int>&y=<int>

    z  = zoom level (0 = coarsest, 3 = finest for order-4 regions)
    x  = base tile column
    y  = base tile row

    Returns a PNG.
    """
    if not DATA_OK:
        abort(503, "Run the preprocessing pipeline first.")

    try:
        z = int(request.args["z"])
        x = int(request.args["x"])
        y = int(request.args["y"])
    except (KeyError, ValueError):
        abort(400, "Required params: z, x, y (integers)")

    if (x, y) not in TILE_META:
        abort(404, f"Base tile ({x},{y}) not found.")

    meta  = TILE_META[(x, y)]
    order = meta["order"]
    recs  = BASE_LOOKUP[(x, y)]

    # Should we collapse at this zoom?
    if _collapse_level(order, z):
        img = _average_tile_color(recs)
        return _png_response(img)

    # For a "full" base tile view (z==1): stitch all sub-tiles together
    if z <= 1:
        sub_grid = 2 ** order
        tile_w   = CELL_W // sub_grid
        tile_h   = CELL_H // sub_grid
        canvas   = Image.new("RGB", (CELL_W, CELL_H))
        for rec in recs:
            sx, sy   = rec["sub_x"], rec["sub_y"]
            tile_img = Image.open(rec["tile_path"])
            canvas.paste(tile_img, (sx * tile_w, sy * tile_h))
        return _png_response(canvas)

    # z >= 2: return individual sub-tile by hilbert_code order slot
    # Treat z offset as a sub-tile selector: we map (z,x,y) as
    # (zoom, base_tx, base_ty) and pick the hilbert-ranked sub-tile
    # closest to the hilbert_code = z * (max_code // max_zoom)
    recs_sorted = sorted(recs, key=lambda r: r["hilbert_code"])
    idx = min(z, len(recs_sorted) - 1)
    rec = recs_sorted[idx]

    tile_img = Image.open(rec["tile_path"])
    return _png_response(tile_img)


@app.route("/lod")
def get_lod():
    """
    GET /lod?viewport=west,south,east,north&zoom=<int>

    Returns JSON list of tile descriptors:
      {base_tx, base_ty, region_class, hilbert_order, status, sub_tile_count, mean_color}

    status = "live"      → rendered at full Hilbert resolution
    status = "collapsed" → averaged to single tile at this zoom
    """
    if not DATA_OK:
        abort(503)

    try:
        zoom = int(request.args.get("zoom", 1))
    except ValueError:
        abort(400, "zoom must be an integer")

    vp_str = request.args.get("viewport", "")
    if vp_str:
        try:
            west, south, east, north = map(float, vp_str.split(","))
        except ValueError:
            abort(400, "viewport must be west,south,east,north floats")
        # Filter tiles by viewport (using pixel bbox approximation)
        # Map lon→x, lat→y linearly over the image
        def in_viewport(tile):
            tx, ty = tile["tile_x"], tile["tile_y"]
            # Just return all tiles for now; a real impl would map lat/lon
            return True
        visible_tiles = [t for t in SEG["tiles"] if in_viewport(t)]
    else:
        visible_tiles = SEG["tiles"]

    result = []
    for tile in visible_tiles:
        tx, ty = tile["tile_x"], tile["tile_y"]
        order  = tile["order"]
        cls    = tile["class"]
        recs   = BASE_LOOKUP[(tx, ty)]

        collapsed = _collapse_level(order, zoom)
        mean_c    = np.array([r["mean_color"] for r in recs]).mean(axis=0).tolist()

        result.append({
            "base_tx":        tx,
            "base_ty":        ty,
            "region_class":   cls,
            "class_name":     tile["class_name"],
            "hilbert_order":  order,
            "sub_tile_count": len(recs),
            "status":         "collapsed" if collapsed else "live",
            "mean_color":     [round(v, 1) for v in mean_c],
            "entropy":        tile["entropy"],
            "pixel_bbox":     tile["pixel_bbox"],   # ← ADD THIS
        })

    stats = {
        "zoom":      zoom,
        "total":     len(result),
        "live":      sum(1 for r in result if r["status"] == "live"),
        "collapsed": sum(1 for r in result if r["status"] == "collapsed"),
    }

    return jsonify({"lod_stats": stats, "tiles": result})


# ── Dev server ────────────────────────────────────────────────────
if __name__ == "__main__":
    log.info("Starting tile server on http://localhost:5000")
    app.run(host="0.0.0.0", port=5000, debug=True)