
# """
# tile_server.py — Adaptive Hilbert LOD Tile Server

# Endpoints:
#   GET /segmentation          segmentation_map.json
#   GET /index_stats           tile count summary
#   GET /lod?zoom=<z>          which tiles are live vs collapsed at zoom z
#   GET /image                 the base satellite image (for canvas background)
#   GET /tile?z=&x=&y=         PNG tile
#   GET /query?cx=&cy=&zoom=   THE KEY ENDPOINT:
#       Given a click point (cx, cy in image pixels) and zoom level,
#       returns:
#         - hilbert_result:   tiles found via Hilbert range scan (fast path)
#         - naive_result:     tiles found via full linear scan (baseline)
#         - hilbert_ms:       time taken for Hilbert scan
#         - naive_ms:         time taken for naive scan
#         - speedup:          naive_ms / hilbert_ms
#         - scanned_hilbert:  how many index entries were examined
#         - scanned_naive:    how many index entries were examined (all)
#         - viewport_bbox:    [x0,y0,x1,y1] of the zoom viewport
# """

# import os, io, json, time, logging, math, bisect
# from collections import defaultdict
# from flask import Flask, jsonify, request, send_file, abort
# from flask_cors import CORS
# import numpy as np
# from PIL import Image

# logging.basicConfig(level=logging.INFO, format="%(asctime)s  %(message)s")
# log = logging.getLogger("TileServer")

# SEG_MAP    = "segmentation_map.json"
# INDEX_FILE = "tile_index.json"
# IMAGE_FILE = "test1.jpg"   # or whatever your source image is called

# app = Flask(__name__)
# CORS(app)  # allow React dev server

# # ── Startup: load all data into memory ───────────────────────────
# def _load():
#     if not os.path.exists(SEG_MAP):
#         raise FileNotFoundError(f"Run region_segmenter.py first — {SEG_MAP} missing")

#     with open(SEG_MAP) as f:  seg   = json.load(f)

#     index = []
#     if os.path.exists(INDEX_FILE):
#         with open(INDEX_FILE) as f: index = json.load(f)

#     base_lookup = defaultdict(list)
#     for rec in index:
#         base_lookup[(rec["base_tx"], rec["base_ty"])].append(rec)

#     tile_meta = {(t["tile_x"], t["tile_y"]): t for t in seg["tiles"]}

#     # Per-(class,order) sorted arrays for O(log N) bisect range scan.
#     from collections import defaultdict as _dd
#     coi = _dd(list)
#     for rec in index:
#         coi[(rec["region_class"], rec["hilbert_order"])].append(rec)
#     for k in coi:
#         coi[k].sort(key=lambda r: r["hilbert_code"])
#     cok = {k: [r["hilbert_code"] for r in v] for k, v in coi.items()}

#     sorted_index = sorted(index, key=lambda r: (
#         r["region_class"], r["hilbert_order"], r["hilbert_code"]
#     ))
#     log.info(f"Loaded {len(index)} sub-tiles across {len(base_lookup)} base tiles")
#     return seg, index, base_lookup, tile_meta, sorted_index, dict(coi), cok

# try:
#     SEG, INDEX, BASE_LOOKUP, TILE_META, SORTED_INDEX, CLASS_ORDER_INDEX, CLASS_ORDER_KEYS = _load()
#     IMG_W, IMG_H = SEG["image_size"]
#     DATA_OK = True
# except Exception as e:
#     log.warning(f"Data not ready: {e}")
#     DATA_OK = False
#     SEG = INDEX = BASE_LOOKUP = TILE_META = SORTED_INDEX = CLASS_ORDER_INDEX = CLASS_ORDER_KEYS = None
#     IMG_W = IMG_H = 0

# # ── LOD collapse logic ────────────────────────────────────────────
# def _collapsed(order: int, zoom: int) -> bool:
#     # order 2 (water)    → collapse at zoom <= 1
#     # order 3 (shore)    → collapse at zoom <= 0
#     # order 4 (urban)    → never collapse
#     return zoom <= {2: 1, 3: 0, 4: -1}.get(order, -1)

# # ── Viewport around a click point ────────────────────────────────
# def _viewport(cx: float, cy: float, zoom: int, img_w: int, img_h: int):
#     """
#     Returns pixel bbox [x0, y0, x1, y1] for the viewport centred on (cx, cy).
#     At zoom=0 → full image. Each zoom level halves the viewport size.
#     """
#     frac  = 1.0 / (2 ** zoom)   # fraction of image covered
#     half_w = (img_w * frac) / 2
#     half_h = (img_h * frac) / 2
#     x0 = max(0,     cx - half_w)
#     y0 = max(0,     cy - half_h)
#     x1 = min(img_w, cx + half_w)
#     y1 = min(img_h, cy + half_h)
#     return [x0, y0, x1, y1]

# def _tile_in_viewport(tile_bbox, vp):
#     """True if tile_bbox [x0,y0,x1,y1] overlaps viewport vp."""
#     tx0, ty0, tx1, ty1 = tile_bbox
#     vx0, vy0, vx1, vy1 = vp
#     return tx0 < vx1 and tx1 > vx0 and ty0 < vy1 and ty1 > vy0

# # ── Hilbert range scan ────────────────────────────────────────────
# def _hilbert_range_scan(vp, zoom):
#     """
#     Correct O(log N + K) Hilbert range scan using bisect.

#     Algorithm:
#       1. For each base tile overlapping the viewport, record
#          (class, order, h_min, h_max) of the sub-tiles inside the viewport.
#       2. Merge overlapping ranges per (class, order) key so we never
#          scan the same segment twice.
#       3. For each merged range, use bisect_left/bisect_right to jump
#          directly to the start position in the per-(class,order) sorted
#          array — O(log N) per range, O(K) to collect results.

#     Total entries examined = sum of range widths, NOT O(N).
#     """
#     if not CLASS_ORDER_INDEX:
#         return [], 0

#     # Step 1: collect ranges per (class, order)
#     from collections import defaultdict
#     ranges = defaultdict(list)   # (cls, order) -> [(h_min, h_max), ...]

#     for (btx, bty), recs in BASE_LOOKUP.items():
#         if not recs: continue
#         # Check base tile bbox against viewport
#         tm = TILE_META.get((btx, bty))
#         if not tm: continue
#         if not _tile_in_viewport(tm["pixel_bbox"], vp):
#             continue

#         # Find sub-tiles whose centre is inside the viewport
#         in_vp = []
#         for r in recs:
#             bb = r.get("abs_bbox", r.get("pixel_bbox", []))
#             if len(bb) < 4: continue
#             cx_ = (bb[0] + bb[2]) / 2
#             cy_ = (bb[1] + bb[3]) / 2
#             if vp[0] <= cx_ <= vp[2] and vp[1] <= cy_ <= vp[3]:
#                 in_vp.append(r)

#         if not in_vp: continue
#         cls   = in_vp[0]["region_class"]
#         order = in_vp[0]["hilbert_order"]
#         h_min = min(r["hilbert_code"] for r in in_vp)
#         h_max = max(r["hilbert_code"] for r in in_vp)
#         ranges[(cls, order)].append((h_min, h_max))

#     if not ranges:
#         return [], 0

#     # Step 2: merge overlapping ranges per key
#     def merge_ranges(rl):
#         rl = sorted(rl)
#         merged = [rl[0]]
#         for lo, hi in rl[1:]:
#             if lo <= merged[-1][1] + 1:
#                 merged[-1] = (merged[-1][0], max(merged[-1][1], hi))
#             else:
#                 merged.append((lo, hi))
#         return merged

#     # Step 3: bisect into per-(class,order) arrays
#     results  = []
#     examined = 0

#     for (cls, order), raw_ranges in ranges.items():
#         arr  = CLASS_ORDER_INDEX.get((cls, order), [])
#         keys = CLASS_ORDER_KEYS.get((cls, order), [])
#         if not arr: continue

#         for h_min, h_max in merge_ranges(raw_ranges):
#             lo = bisect.bisect_left(keys,  h_min)
#             hi = bisect.bisect_right(keys, h_max)
#             segment = arr[lo:hi]
#             examined += (hi - lo)

#             for r in segment:
#                 bb = r.get("abs_bbox", r.get("pixel_bbox", []))
#                 if len(bb) < 4: continue
#                 cx_ = (bb[0] + bb[2]) / 2
#                 cy_ = (bb[1] + bb[3]) / 2
#                 if vp[0] <= cx_ <= vp[2] and vp[1] <= cy_ <= vp[3]:
#                     results.append(r)

#     return results, examined


# def _naive_scan(vp):
#     """
#     Simulate naive full-table scan: iterate ALL records, check bbox.
#     Returns (matching_records, n_examined = len(INDEX)).
#     """
#     results = []
#     for r in INDEX:
#         bb = r.get("abs_bbox", r.get("pixel_bbox", []))
#         if len(bb) < 4: continue
#         cx_ = (bb[0] + bb[2]) / 2
#         cy_ = (bb[1] + bb[3]) / 2
#         if (vp[0] <= cx_ <= vp[2]) and (vp[1] <= cy_ <= vp[3]):
#             results.append(r)
#     return results, len(INDEX)


# # ── Routes ────────────────────────────────────────────────────────
# @app.after_request
# def _cors(resp):
#     resp.headers["Access-Control-Allow-Origin"] = "*"
#     return resp

# @app.route("/")
# def index_page():
#     return jsonify({"status": "ok", "data_loaded": DATA_OK,
#                     "endpoints": ["/segmentation", "/index_stats", "/lod", "/image", "/tile", "/query"]})

# @app.route("/segmentation")
# def segmentation():
#     if not DATA_OK: abort(503)
#     return jsonify(SEG)

# @app.route("/image")
# def serve_image():
#     """Serve the source satellite image for the React canvas background."""
#     for fname in [IMAGE_FILE, "test1.jpg", "test1.png"]:
#         if os.path.exists(fname):
#             return send_file(fname, mimetype="image/jpeg")
#     abort(404, "Source image not found — set IMAGE_FILE in tile_server.py")

# @app.route("/index_stats")
# def index_stats():
#     if not DATA_OK: abort(503)
#     from collections import Counter
#     return jsonify({
#         "total_sub_tiles": len(INDEX),
#         "base_tiles":      len(BASE_LOOKUP),
#         "by_class":        dict(Counter(r["region_class"]   for r in INDEX)),
#         "by_order":        dict(Counter(r["hilbert_order"]  for r in INDEX)),
#     })

# @app.route("/lod")
# def get_lod():
#     if not DATA_OK: abort(503)
#     zoom = int(request.args.get("zoom", 2))

#     result = []
#     for tile in SEG["tiles"]:
#         tx, ty  = tile["tile_x"], tile["tile_y"]
#         order   = tile["order"]
#         cls     = tile["class"]
#         recs    = BASE_LOOKUP.get((tx, ty), [])
#         mean_c  = (np.array([r["mean_color"] for r in recs]).mean(axis=0).tolist()
#                    if recs else [128, 128, 128])
#         collapsed = _collapsed(order, zoom)

#         result.append({
#             "base_tx":        tx,
#             "base_ty":        ty,
#             "region_class":   cls,
#             "class_name":     tile["class_name"],
#             "hilbert_order":  order,
#             "sub_tile_count": len(recs),
#             "status":         "collapsed" if collapsed else "live",
#             "mean_color":     [round(v, 1) for v in mean_c],
#             "entropy":        tile["entropy"],
#             "pixel_bbox":     tile["pixel_bbox"],
#         })

#     stats = {
#         "zoom":      zoom,
#         "total":     len(result),
#         "live":      sum(1 for r in result if r["status"] == "live"),
#         "collapsed": sum(1 for r in result if r["status"] == "collapsed"),
#     }
#     return jsonify({"lod_stats": stats, "tiles": result})


# @app.route("/query")
# def query():
#     """
#     GET /query?cx=<float>&cy=<float>&zoom=<int>

#     cx, cy: click point in image pixel coordinates
#     zoom:   current zoom level (0–4)

#     Returns timing comparison between Hilbert range scan and naive scan.
#     """
#     if not DATA_OK:
#         abort(503, "Run the pipeline first.")
#     if not INDEX:
#         abort(503, "tile_index.json is empty — run hilbert_spatial_indexer.py first.")

#     try:
#         cx   = float(request.args["cx"])
#         cy   = float(request.args["cy"])
#         zoom = int(request.args.get("zoom", 2))
#     except (KeyError, ValueError):
#         abort(400, "Required: cx, cy (floats), zoom (int)")

#     vp = _viewport(cx, cy, zoom, IMG_W, IMG_H)

#     # ── Hilbert range scan ─────────────────────────────────────────
#     t0 = time.perf_counter()
#     h_recs, h_examined = _hilbert_range_scan(vp, zoom)
#     hilbert_ms = (time.perf_counter() - t0) * 1000

#     # ── Naive full scan ────────────────────────────────────────────
#     t0 = time.perf_counter()
#     n_recs, n_examined = _naive_scan(vp)
#     naive_ms = (time.perf_counter() - t0) * 1000

#     speedup = naive_ms / hilbert_ms if hilbert_ms > 0 else 0

#     # Summarise matched tiles (don't send full record, just metadata)
#     def _summarise(recs):
#         return [{
#             "region_class":  r["region_class"],
#             "hilbert_order": r["hilbert_order"],
#             "hilbert_code":  r["hilbert_code"],
#             "abs_bbox":      r.get("abs_bbox", r.get("pixel_bbox", [])),
#             "mean_color":    [round(v) for v in r.get("mean_color", [128,128,128])],
#         } for r in recs]

#     log.info(f"Query ({cx:.0f},{cy:.0f}) zoom={zoom}: "
#              f"Hilbert {hilbert_ms:.2f}ms/{h_examined} examined → {len(h_recs)} hits | "
#              f"Naive {naive_ms:.2f}ms/{n_examined} examined → {len(n_recs)} hits | "
#              f"speedup {speedup:.1f}×")

#     return jsonify({
#         "viewport_bbox":    vp,
#         "zoom":             zoom,
#         "click_point":      [cx, cy],
#         "hilbert_result": {
#             "tiles":           _summarise(h_recs),
#             "count":           len(h_recs),
#             "examined":        h_examined,
#             "time_ms":         round(hilbert_ms, 3),
#             "method":          "hilbert range scan",
#         },
#         "naive_result": {
#             "tiles":           _summarise(n_recs),
#             "count":           len(n_recs),
#             "examined":        n_examined,
#             "time_ms":         round(naive_ms, 3),
#             "method":          "full linear scan",
#         },
#         "speedup":            round(speedup, 2),
#         "tiles_saved":        n_examined - h_examined,
#         "pct_skipped":        round((1 - h_examined / max(n_examined, 1)) * 100, 1),
#     })


# if __name__ == "__main__":
#     log.info("Starting on http://localhost:5000")
#     app.run(host="0.0.0.0", port=5000, debug=True)

"""
tile_server.py — Adaptive Hilbert LOD Tile Server

Endpoints:
  GET /segmentation          segmentation_map.json
  GET /index_stats           tile count summary
  GET /lod?zoom=<z>          which tiles are live vs collapsed at zoom z
  GET /image                 the base satellite image (for canvas background)
  GET /tile?z=&x=&y=         PNG tile
  GET /query?cx=&cy=&zoom=   THE KEY ENDPOINT:
      Given a click point (cx, cy in image pixels) and zoom level,
      returns:
        - hilbert_result:   tiles found via Hilbert range scan (fast path)
        - naive_result:     tiles found via full linear scan (baseline)
        - hilbert_ms:       time taken for Hilbert scan
        - naive_ms:         time taken for naive scan
        - speedup:          naive_ms / hilbert_ms
        - scanned_hilbert:  how many index entries were examined
        - scanned_naive:    how many index entries were examined (all)
        - viewport_bbox:    [x0,y0,x1,y1] of the zoom viewport
"""

import os, io, json, time, logging, math, bisect
from collections import defaultdict
from flask import Flask, jsonify, request, send_file, abort
from flask_cors import CORS
import numpy as np
from PIL import Image

logging.basicConfig(level=logging.INFO, format="%(asctime)s  %(message)s")
log = logging.getLogger("TileServer")

SEG_MAP    = "segmentation_map.json"
INDEX_FILE = "tile_index.json"
IMAGE_FILE = "test1.jpg"   # or whatever your source image is called

app = Flask(__name__)
CORS(app)  # allow React dev server

# ── Startup: load all data into memory ───────────────────────────
def _load():
    if not os.path.exists(SEG_MAP):
        raise FileNotFoundError(f"Run region_segmenter.py first — {SEG_MAP} missing")

    with open(SEG_MAP) as f:  seg   = json.load(f)

    index = []
    if os.path.exists(INDEX_FILE):
        with open(INDEX_FILE) as f: index = json.load(f)

    base_lookup = defaultdict(list)
    for rec in index:
        base_lookup[(rec["base_tx"], rec["base_ty"])].append(rec)

    tile_meta = {(t["tile_x"], t["tile_y"]): t for t in seg["tiles"]}

    # Per-(class,order) sorted arrays for O(log N) bisect range scan.
    from collections import defaultdict as _dd
    coi = _dd(list)
    for rec in index:
        coi[(rec["region_class"], rec["hilbert_order"])].append(rec)
    for k in coi:
        coi[k].sort(key=lambda r: r["hilbert_code"])
    cok = {k: [r["hilbert_code"] for r in v] for k, v in coi.items()}

    sorted_index = sorted(index, key=lambda r: (
        r["region_class"], r["hilbert_order"], r["hilbert_code"]
    ))
    log.info(f"Loaded {len(index)} sub-tiles across {len(base_lookup)} base tiles")
    return seg, index, base_lookup, tile_meta, sorted_index, dict(coi), cok

try:
    SEG, INDEX, BASE_LOOKUP, TILE_META, SORTED_INDEX, CLASS_ORDER_INDEX, CLASS_ORDER_KEYS = _load()
    IMG_W, IMG_H = SEG["image_size"]
    DATA_OK = True
except Exception as e:
    log.warning(f"Data not ready: {e}")
    DATA_OK = False
    SEG = INDEX = BASE_LOOKUP = TILE_META = SORTED_INDEX = CLASS_ORDER_INDEX = CLASS_ORDER_KEYS = None
    IMG_W = IMG_H = 0

# ── LOD collapse logic ────────────────────────────────────────────
def _collapsed(order: int, zoom: int) -> bool:
    # order 2 (water)    → collapse at zoom <= 1
    # order 3 (shore)    → collapse at zoom <= 0
    # order 4 (urban)    → never collapse
    return zoom <= {2: 1, 3: 0, 4: -1}.get(order, -1)

# ── Viewport around a click point ────────────────────────────────
def _viewport(cx: float, cy: float, zoom: int, img_w: int, img_h: int):
    """
    Returns pixel bbox [x0, y0, x1, y1] for the viewport centred on (cx, cy).
    At zoom=0 → full image. Each zoom level halves the viewport size.
    """
    frac  = 1.0 / (2 ** zoom)   # fraction of image covered
    half_w = (img_w * frac) / 2
    half_h = (img_h * frac) / 2
    x0 = max(0,     cx - half_w)
    y0 = max(0,     cy - half_h)
    x1 = min(img_w, cx + half_w)
    y1 = min(img_h, cy + half_h)
    return [x0, y0, x1, y1]

def _tile_in_viewport(tile_bbox, vp):
    """True if tile_bbox [x0,y0,x1,y1] overlaps viewport vp."""
    tx0, ty0, tx1, ty1 = tile_bbox
    vx0, vy0, vx1, vy1 = vp
    return tx0 < vx1 and tx1 > vx0 and ty0 < vy1 and ty1 > vy0

# ── Hilbert range scan ────────────────────────────────────────────
def _hilbert_range_scan(vp, zoom):
    """
    Correct O(log N + K) Hilbert range scan using bisect.

    Algorithm:
      1. For each base tile overlapping the viewport, record
         (class, order, h_min, h_max) of the sub-tiles inside the viewport.
      2. Merge overlapping ranges per (class, order) key so we never
         scan the same segment twice.
      3. For each merged range, use bisect_left/bisect_right to jump
         directly to the start position in the per-(class,order) sorted
         array — O(log N) per range, O(K) to collect results.

    Total entries examined = sum of range widths, NOT O(N).
    """
    if not CLASS_ORDER_INDEX:
        return [], 0

    # Step 1: collect ranges per (class, order)
    from collections import defaultdict
    ranges = defaultdict(list)   # (cls, order) -> [(h_min, h_max), ...]

    for (btx, bty), recs in BASE_LOOKUP.items():
        if not recs: continue
        # Check base tile bbox against viewport
        tm = TILE_META.get((btx, bty))
        if not tm: continue
        if not _tile_in_viewport(tm["pixel_bbox"], vp):
            continue

        # Find sub-tiles whose centre is inside the viewport
        in_vp = []
        for r in recs:
            bb = r.get("abs_bbox", r.get("pixel_bbox", []))
            if len(bb) < 4: continue
            cx_ = (bb[0] + bb[2]) / 2
            cy_ = (bb[1] + bb[3]) / 2
            if vp[0] <= cx_ <= vp[2] and vp[1] <= cy_ <= vp[3]:
                in_vp.append(r)

        if not in_vp: continue
        cls   = in_vp[0]["region_class"]
        order = in_vp[0]["hilbert_order"]
        h_min = min(r["hilbert_code"] for r in in_vp)
        h_max = max(r["hilbert_code"] for r in in_vp)
        ranges[(cls, order)].append((h_min, h_max))

    if not ranges:
        return [], 0

    # Step 2: merge overlapping ranges per key
    def merge_ranges(rl):
        rl = sorted(rl)
        merged = [rl[0]]
        for lo, hi in rl[1:]:
            if lo <= merged[-1][1] + 1:
                merged[-1] = (merged[-1][0], max(merged[-1][1], hi))
            else:
                merged.append((lo, hi))
        return merged

    # Step 3: bisect into per-(class,order) arrays
    results  = []
    examined = 0

    for (cls, order), raw_ranges in ranges.items():
        arr  = CLASS_ORDER_INDEX.get((cls, order), [])
        keys = CLASS_ORDER_KEYS.get((cls, order), [])
        if not arr: continue

        for h_min, h_max in merge_ranges(raw_ranges):
            lo = bisect.bisect_left(keys,  h_min)
            hi = bisect.bisect_right(keys, h_max)
            segment = arr[lo:hi]
            examined += (hi - lo)

            for r in segment:
                bb = r.get("abs_bbox", r.get("pixel_bbox", []))
                if len(bb) < 4: continue
                cx_ = (bb[0] + bb[2]) / 2
                cy_ = (bb[1] + bb[3]) / 2
                if vp[0] <= cx_ <= vp[2] and vp[1] <= cy_ <= vp[3]:
                    results.append(r)

    return results, examined


def _naive_scan(vp):
    """
    Simulate naive full-table scan: iterate ALL records, check bbox.
    Returns (matching_records, n_examined = len(INDEX)).
    """
    results = []
    for r in INDEX:
        bb = r.get("abs_bbox", r.get("pixel_bbox", []))
        if len(bb) < 4: continue
        cx_ = (bb[0] + bb[2]) / 2
        cy_ = (bb[1] + bb[3]) / 2
        if (vp[0] <= cx_ <= vp[2]) and (vp[1] <= cy_ <= vp[3]):
            results.append(r)
    return results, len(INDEX)


# ── Routes ────────────────────────────────────────────────────────
@app.after_request
def _cors(resp):
    resp.headers["Access-Control-Allow-Origin"] = "*"
    return resp

@app.route("/")
def index_page():
    return jsonify({"status": "ok", "data_loaded": DATA_OK,
                    "endpoints": ["/segmentation", "/index_stats", "/lod", "/image", "/tile", "/query"]})

@app.route("/segmentation")
def segmentation():
    if not DATA_OK: abort(503)
    return jsonify(SEG)

@app.route("/image")
def serve_image():
    """Serve the source satellite image for the React canvas background."""
    for fname in [IMAGE_FILE, "test1.jpg", "test1.png"]:
        if os.path.exists(fname):
            return send_file(fname, mimetype="image/jpeg")
    abort(404, "Source image not found — set IMAGE_FILE in tile_server.py")

@app.route("/index_stats")
def index_stats():
    if not DATA_OK: abort(503)
    from collections import Counter
    return jsonify({
        "total_sub_tiles": len(INDEX),
        "base_tiles":      len(BASE_LOOKUP),
        "by_class":        dict(Counter(r["region_class"]   for r in INDEX)),
        "by_order":        dict(Counter(r["hilbert_order"]  for r in INDEX)),
    })

@app.route("/lod")
def get_lod():
    if not DATA_OK: abort(503)
    zoom = int(request.args.get("zoom", 2))

    result = []
    for tile in SEG["tiles"]:
        tx, ty  = tile["tile_x"], tile["tile_y"]
        order   = tile["order"]
        cls     = tile["class"]
        recs    = BASE_LOOKUP.get((tx, ty), [])
        mean_c  = (np.array([r["mean_color"] for r in recs]).mean(axis=0).tolist()
                   if recs else [128, 128, 128])
        collapsed = _collapsed(order, zoom)

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
            "pixel_bbox":     tile["pixel_bbox"],
        })

    stats = {
        "zoom":      zoom,
        "total":     len(result),
        "live":      sum(1 for r in result if r["status"] == "live"),
        "collapsed": sum(1 for r in result if r["status"] == "collapsed"),
    }
    return jsonify({"lod_stats": stats, "tiles": result})


@app.route("/query")
def query():
    """
    GET /query?cx=<float>&cy=<float>&zoom=<int>

    cx, cy: click point in image pixel coordinates
    zoom:   current zoom level (0–4)

    Returns timing comparison between Hilbert range scan and naive scan.
    """
    if not DATA_OK:
        abort(503, "Run the pipeline first.")
    if not INDEX:
        abort(503, "tile_index.json is empty — run hilbert_spatial_indexer.py first.")

    try:
        cx   = float(request.args["cx"])
        cy   = float(request.args["cy"])
        zoom = int(request.args.get("zoom", 2))
    except (KeyError, ValueError):
        abort(400, "Required: cx, cy (floats), zoom (int)")

    vp = _viewport(cx, cy, zoom, IMG_W, IMG_H)

    # ── Hilbert range scan ─────────────────────────────────────────
    t0 = time.perf_counter()
    h_recs, h_examined = _hilbert_range_scan(vp, zoom)
    hilbert_ms = (time.perf_counter() - t0) * 1000

    # ── Naive full scan ────────────────────────────────────────────
    t0 = time.perf_counter()
    n_recs, n_examined = _naive_scan(vp)
    naive_ms = (time.perf_counter() - t0) * 1000

    speedup = naive_ms / hilbert_ms if hilbert_ms > 0 else 0

    # Summarise matched tiles (don't send full record, just metadata)
    def _summarise(recs):
        return [{
            "region_class":  r["region_class"],
            "hilbert_order": r["hilbert_order"],
            "hilbert_code":  r["hilbert_code"],
            "abs_bbox":      r.get("abs_bbox", r.get("pixel_bbox", [])),
            "mean_color":    [round(v) for v in r.get("mean_color", [128,128,128])],
        } for r in recs]

    log.info(f"Query ({cx:.0f},{cy:.0f}) zoom={zoom}: "
             f"Hilbert {hilbert_ms:.2f}ms/{h_examined} examined → {len(h_recs)} hits | "
             f"Naive {naive_ms:.2f}ms/{n_examined} examined → {len(n_recs)} hits | "
             f"speedup {speedup:.1f}×")

    return jsonify({
        "viewport_bbox":    vp,
        "zoom":             zoom,
        "click_point":      [cx, cy],
        "hilbert_result": {
            "tiles":           _summarise(h_recs),
            "count":           len(h_recs),
            "examined":        h_examined,
            "time_ms":         round(hilbert_ms, 3),
            "method":          "hilbert range scan",
        },
        "naive_result": {
            "tiles":           _summarise(n_recs),
            "count":           len(n_recs),
            "examined":        n_examined,
            "time_ms":         round(naive_ms, 3),
            "method":          "full linear scan",
        },
        "speedup":            round(speedup, 2),
        "tiles_saved":        n_examined - h_examined,
        "pct_skipped":        round((1 - h_examined / max(n_examined, 1)) * 100, 1),
    })

# ── /zoom_lod — viewport-aware LOD with increasing Hilbert density ──
@app.route("/zoom_lod")
def zoom_lod():
    """
    GET /zoom_lod?cx=<float>&cy=<float>&depth=<int>

    Returns the tiles visible inside a viewport centred on (cx,cy) at
    the given click-depth (0 = full image, 1 = first zoom, 2 = second…).

    Key difference from /lod:
      - Only returns tiles that intersect the viewport
      - Each tile's 'sub_grid' field = 2^(order + extra) where extra
        increases with depth, so the drawn Hilbert grid gets denser
        as you zoom in — showing the curve at finer resolution
      - Tiles fully outside the viewport are omitted entirely (this is
        what the Hilbert scan is optimising for)
      - Returns collapse/live status AND the visible hilbert_codes
        within the viewport for that tile
    """
    if not DATA_OK: abort(503)
    try:
        cx    = float(request.args["cx"])
        cy    = float(request.args["cy"])
        depth = int(request.args.get("depth", 0))
    except (KeyError, ValueError):
        abort(400, "Required: cx, cy; optional: depth")

    vp = _viewport(cx, cy, depth, IMG_W, IMG_H)

    # Hilbert order shown at each depth per class
    # depth 0: show base order; each depth adds 1 to the visible sub-grid
    def visible_order(base_order, depth):
        return min(base_order + depth, 6)   # cap at 64x64

    result = []
    for tile in SEG["tiles"]:
        tx, ty = tile["tile_x"], tile["tile_y"]
        bb     = tile["pixel_bbox"]
        if not _tile_in_viewport(bb, vp):
            continue

        cls     = tile["class"]
        order   = tile["order"]
        recs    = BASE_LOOKUP.get((tx, ty), [])
        mean_c  = (np.array([r["mean_color"] for r in recs]).mean(axis=0).tolist()
                   if recs else [128, 128, 128])

        # At this depth, what Hilbert sub-grid do we show?
        vis_order  = visible_order(order, depth)
        vis_grid   = 2 ** vis_order

        # Clip pixel_bbox to viewport
        cx0 = max(bb[0], vp[0]); cy0 = max(bb[1], vp[1])
        cx1 = min(bb[2], vp[2]); cy1 = min(bb[3], vp[3])

        # Which sub-tile hilbert codes fall in the visible clip?
        tile_w = bb[2] - bb[0]; tile_h = bb[3] - bb[1]
        sw = tile_w / vis_grid;  sh = tile_h / vis_grid

        visible_codes = []
        for sy in range(vis_grid):
            for sx in range(vis_grid):
                sub_x0 = bb[0] + sx * sw;  sub_y0 = bb[1] + sy * sh
                sub_x1 = sub_x0 + sw;      sub_y1 = sub_y0 + sh
                if sub_x0 < cx1 and sub_x1 > cx0 and sub_y0 < cy1 and sub_y1 > cy0:
                    from adaptive_hilbert_indexer import xy_to_hilbert
                    visible_codes.append({
                        "code": xy_to_hilbert(sx, sy, vis_order),
                        "sx": sx, "sy": sy,
                        "bbox": [sub_x0, sub_y0, sub_x1, sub_y1]
                    })

        collapsed = _collapsed(order, depth)

        result.append({
            "base_tx":       tx, "base_ty":       ty,
            "region_class":  cls, "class_name":   tile["class_name"],
            "base_order":    order,
            "visible_order": vis_order,
            "vis_grid":      vis_grid,
            "status":        "collapsed" if collapsed else "live",
            "mean_color":    [round(v,1) for v in mean_c],
            "entropy":       tile["entropy"],
            "pixel_bbox":    bb,
            "clip_bbox":     [cx0, cy0, cx1, cy1],
            "visible_codes": visible_codes,
        })

    return jsonify({
        "depth":        depth,
        "viewport":     vp,
        "click_point":  [cx, cy],
        "tile_count":   len(result),
        "tiles":        result,
    })


if __name__ == "__main__":
    log.info("Starting on http://localhost:5000")
    app.run(host="0.0.0.0", port=5000, debug=True)

