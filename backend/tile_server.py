
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
from rtree import index as rtree_mod
from adaptive_hilbert_indexer import xy_to_hilbert

# ── Pre-computed Hilbert lookup table (order 2-7) ─────────────────
# Avoids recomputing xy_to_hilbert() inside hot loops.
HILBERT_CACHE: dict = {}
for _ord in range(2, 8):
    _g = 2 ** _ord
    HILBERT_CACHE[_ord] = {(_x, _y): xy_to_hilbert(_x, _y, _ord)
                           for _x in range(_g) for _y in range(_g)}

logging.basicConfig(level=logging.INFO, format="%(asctime)s  %(message)s")
log = logging.getLogger("TileServer")

VECTOR_SEG_MAP = "vector_segmentation_map.json"
VECTOR_INDEX_FILE = "vector_index.json"

app = Flask(__name__)
CORS(app)  # allow React dev server

# ── Startup: load all data into memory ───────────────────────────
def _load_seg(filename):
    if not os.path.exists(filename):
        log.warning(f"{filename} missing")
        return None
    with open(filename) as f:
        return json.load(f)

def _load_index(filename, seg):
    if not seg: return {}
    index = []
    if os.path.exists(filename):
        with open(filename) as f: index = json.load(f)
    else:
        log.warning(f"Index file {filename} not found.")

    base_lookup = defaultdict(list)
    for rec in index:
        base_lookup[(rec["base_tx"], rec["base_ty"])].append(rec)

    base_keys = {}
    for k in base_lookup:
        base_lookup[k].sort(key=lambda r: r["hilbert_code"])
        base_keys[k] = [r["hilbert_code"] for r in base_lookup[k]]

    tile_meta = {(t["tile_x"], t["tile_y"]): t for t in seg["tiles"]}

    sorted_index = sorted(index, key=lambda r: (
        r["region_class"], r["hilbert_order"], r["hilbert_code"]
    ))

    # ── R-tree index over base tile bboxes ──────────────────────────
    # Allows O(log B + K) viewport intersection instead of O(B) scan.
    rt = rtree_mod.Index()
    rt_id_map: dict = {}          # integer id → (tx, ty)
    for i, ((tx, ty), _) in enumerate(base_lookup.items()):
        tm = tile_meta.get((tx, ty))
        if tm:
            x0, y0, x1, y1 = tm["pixel_bbox"]
            rt.insert(i, (x0, y0, x1, y1))
            rt_id_map[i] = (tx, ty)

    log.info(f"Loaded {len(index)} features across {len(base_lookup)} base tiles from {filename} "
             f"(R-tree: {len(rt_id_map)} entries)")
    return {
        "index": index,
        "base_lookup": dict(base_lookup),
        "base_keys": base_keys,
        "tile_meta": tile_meta,
        "sorted_index": sorted_index,
        "base_rtree": rt,
        "rtree_id_map": rt_id_map,
    }

try:
    SEG_DATA = {
        "test1": _load_seg("segmentation_map_test1.json"),
        "test2": _load_seg("segmentation_map_test2.json"),
        "vector": _load_seg(VECTOR_SEG_MAP)
    }
    
    INDEX_DATA = {
        "test1": _load_index("tile_index_test1.json", SEG_DATA["test1"]),
        "test2": _load_index("tile_index_test2.json", SEG_DATA["test2"]),
        "vector": _load_index(VECTOR_INDEX_FILE, SEG_DATA["vector"])
    }
    DATA_OK = True
except Exception as e:
    log.warning(f"Data not ready: {e}")
    DATA_OK = False
    SEG_DATA = {"test1": None, "test2": None, "vector": None}
    INDEX_DATA = {"test1": {}, "test2": {}, "vector": {}}

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
def _hilbert_range_scan(index_data, vp, zoom):
    """
    O(log B + log N + K) Hilbert range scan.

    Step 0: R-tree intersection → only candidate base tiles (O(log B + K_b))
    Step 1: collect Hilbert code ranges from matching sub-tiles (O(K_b * S))
    Step 2: merge overlapping ranges per (class, order) key
    Step 3: bisect into sorted per-(class,order) array  (O(log N + K))
    """
    BASE_LOOKUP       = index_data.get("base_lookup", {})
    BASE_KEYS         = index_data.get("base_keys", {})
    TILE_META         = index_data.get("tile_meta", {})
    base_rtree        = index_data.get("base_rtree")
    rtree_id_map      = index_data.get("rtree_id_map", {})

    # Step 0: R-tree query → candidate (tx, ty) pairs that overlap viewport
    if base_rtree is not None and rtree_id_map:
        candidate_keys = [rtree_id_map[rid]
                          for rid in base_rtree.intersection((vp[0], vp[1], vp[2], vp[3]))]
    else:
        candidate_keys = list(BASE_LOOKUP.keys())

    results  = []
    examined = 0

    # Step 1: For each candidate tile, project viewport mathematically and bisect locally
    for (btx, bty) in candidate_keys:
        tm = TILE_META.get((btx, bty))
        if not tm:
            continue

        order = tm["order"]
        sub_grid = 2 ** order
        x0, y0, x1, y1 = tm["pixel_bbox"]

        arr  = BASE_LOOKUP.get((btx, bty), [])
        keys = BASE_KEYS.get((btx, bty), [])
        if not arr: continue

        # Local viewport boundaries relative to base tile
        lx0 = max(0, vp[0] - x0)
        ly0 = max(0, vp[1] - y0)
        lx1 = min(x1 - x0, vp[2] - x0)
        ly1 = min(y1 - y0, vp[3] - y0)

        if lx0 >= lx1 or ly0 >= ly1:
            continue

        sub_w = (x1 - x0) // sub_grid
        sub_h = (y1 - y0) // sub_grid

        sx_min = max(0, min(sub_grid - 1, int(lx0 / max(1, sub_w))))
        sy_min = max(0, min(sub_grid - 1, int(ly0 / max(1, sub_h))))
        sx_max = max(0, min(sub_grid - 1, int(lx1 / max(1, sub_w))))
        sy_max = max(0, min(sub_grid - 1, int(ly1 / max(1, sub_h))))

        h_lut = HILBERT_CACHE.get(order, {})
        codes = []
        for sy in range(sy_min, sy_max + 1):
            for sx in range(sx_min, sx_max + 1):
                # Only include cell if its centre is in viewport (matching the naive logic)
                cx_ = x0 + (sx + 0.5) * sub_w
                cy_ = y0 + (sy + 0.5) * sub_h
                if vp[0] <= cx_ <= vp[2] and vp[1] <= cy_ <= vp[3]:
                    code = h_lut.get((sx, sy), -1)
                    if code != -1:
                        codes.append(code)

        if not codes:
            continue

        # Group contiguous codes into precise ranges
        codes.sort()
        ranges = []
        start_c = codes[0]
        end_c = codes[0]
        for c in codes[1:]:
            if c == end_c + 1:
                end_c = c
            else:
                ranges.append((start_c, end_c))
                start_c = c
                end_c = c
        ranges.append((start_c, end_c))

        # Bisect these exact ranges within the base tile's local records
        for h_min, h_max in ranges:
            lo = bisect.bisect_left(keys,  h_min)
            hi = bisect.bisect_right(keys, h_max)
            examined += hi - lo

            for i in range(lo, hi):
                r = arr[i]
                bb = r.get("abs_bbox", r.get("pixel_bbox", []))
                if len(bb) < 4: continue
                
                cx_ = (bb[0] + bb[2]) / 2
                cy_ = (bb[1] + bb[3]) / 2
                if vp[0] <= cx_ <= vp[2] and vp[1] <= cy_ <= vp[3]:
                    results.append(r)

    return results, examined


def _naive_scan(index_data, vp):
    """
    Simulate naive full-table scan: iterate ALL records, check bbox.
    """
    INDEX = index_data.get("index", [])
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
    dataset = request.args.get("dataset", request.args.get("mode", "test1"))
    if dataset == "raster": dataset = "test1"
    seg = SEG_DATA.get(dataset)
    if not seg: abort(404, f"Segmentation for {dataset} not found")
    return jsonify(seg)

@app.route("/image")
def serve_image():
    """Serve the source satellite image for the React canvas background."""
    dataset = request.args.get("dataset", request.args.get("mode", "test1"))
    if dataset == "raster": dataset = "test1"
    
    # Simple mapping
    img_map = {"test1": "test1.jpg", "test2": "test2.jpg"}
    fname = img_map.get(dataset, "test1.jpg")
    
    if os.path.exists(fname):
        return send_file(fname, mimetype="image/jpeg")
    abort(404, "Source image not found")

@app.route("/index_stats")
def index_stats():
    if not DATA_OK: abort(503)
    dataset = request.args.get("dataset", request.args.get("mode", "test1"))
    if dataset == "raster": dataset = "test1"
    idx = INDEX_DATA.get(dataset, {}).get("index", [])
    base = INDEX_DATA.get(dataset, {}).get("base_lookup", {})
    from collections import Counter
    return jsonify({
        "total_sub_tiles": len(idx),
        "base_tiles":      len(base),
        "by_class":        dict(Counter(r["region_class"]   for r in idx)),
        "by_order":        dict(Counter(r["hilbert_order"]  for r in idx)),
    })

@app.route("/lod")
def get_lod():
    if not DATA_OK: abort(503)
    zoom = int(request.args.get("zoom", 2))
    dataset = request.args.get("dataset", request.args.get("mode", "test1"))
    if dataset == "raster": dataset = "test1"
    base = INDEX_DATA.get(dataset, {}).get("base_lookup", {})

    result = []
    seg = SEG_DATA.get(dataset)
    if not seg: return jsonify({"lod_stats": {}, "tiles": []})

    for tile in seg["tiles"]:
        tx, ty  = tile["tile_x"], tile["tile_y"]
        order   = tile["order"]
        cls     = tile["class"]
        recs    = base.get((tx, ty), [])
        mean_c  = (np.array([r.get("mean_color", [128,128,128]) for r in recs]).mean(axis=0).tolist()
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
    GET /query?cx=<float>&cy=<float>&zoom=<int>&mode=<string>
    """
    if not DATA_OK:
        abort(503, "Run the pipeline first.")

    dataset = request.args.get("dataset", request.args.get("mode", "test1"))
    if dataset == "raster": dataset = "test1"
    index_data = INDEX_DATA.get(dataset, {})
    if not index_data.get("index"):
        abort(503, f"{dataset} index is empty. Run indexer first.")

    try:
        cx   = float(request.args["cx"])
        cy   = float(request.args["cy"])
        zoom = int(request.args.get("zoom", 2))
    except (KeyError, ValueError):
        abort(400, "Required: cx, cy (floats), zoom (int)")

    img_w, img_h = SEG_DATA[dataset]["image_size"] if SEG_DATA.get(dataset) else (1600, 1600)
    vp = _viewport(cx, cy, zoom, img_w, img_h)

    # ── Hilbert range scan ─────────────────────────────────────────
    t0 = time.perf_counter()
    h_recs, h_examined = _hilbert_range_scan(index_data, vp, zoom)
    hilbert_ms = (time.perf_counter() - t0) * 1000

    # ── Naive full scan ────────────────────────────────────────────
    t0 = time.perf_counter()
    n_recs, n_examined = _naive_scan(index_data, vp)
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
            "features":      r.get("features", [])
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

    dataset = request.args.get("dataset", request.args.get("mode", "test1"))
    if dataset == "raster": dataset = "test1"
    base = INDEX_DATA.get(dataset, {}).get("base_lookup", {})

    img_w, img_h = SEG_DATA[dataset]["image_size"] if SEG_DATA.get(dataset) else (1600, 1600)
    vp = _viewport(cx, cy, depth, img_w, img_h)

    # Hilbert order shown at each depth per class
    # depth 0: show base order; each depth adds 1 to the visible sub-grid
    def visible_order(base_order, depth):
        return min(base_order + depth, 6)   # cap at 64x64

    result = []
    seg = SEG_DATA.get(dataset)
    if not seg: return jsonify({"depth": depth, "viewport": vp, "tiles": [], "tile_count": 0})

    index_data = INDEX_DATA.get(dataset, {})

    # ── Use R-tree to find only tiles that intersect the viewport ───
    # Falls back to iterating seg["tiles"] linearly if no R-tree.
    seg_rtree   = index_data.get("base_rtree")
    seg_id_map  = index_data.get("rtree_id_map", {})
    tile_meta   = index_data.get("tile_meta", {})

    if seg_rtree is not None and seg_id_map:
        # R-tree gives us only the overlapping (tx, ty) pairs directly.
        candidate_tkeys = set(seg_id_map[rid]
                              for rid in seg_rtree.intersection((vp[0], vp[1], vp[2], vp[3])))
        candidate_tiles = [t for t in seg["tiles"]
                           if (t["tile_x"], t["tile_y"]) in candidate_tkeys]
    else:
        # Fallback: linear scan with manual bbox check
        candidate_tiles = [t for t in seg["tiles"] if _tile_in_viewport(t["pixel_bbox"], vp)]

    for tile in candidate_tiles:
        tx, ty = tile["tile_x"], tile["tile_y"]
        bb     = tile["pixel_bbox"]

        cls     = tile["class"]
        order   = tile["order"]
        recs    = base.get((tx, ty), [])
        mean_c  = (np.array([r.get("mean_color", [128,128,128]) for r in recs]).mean(axis=0).tolist()
                   if recs else [128, 128, 128])

        # At this depth, what Hilbert sub-grid do we show?
        vis_order = visible_order(order, depth)
        vis_grid  = 2 ** vis_order

        # Clip pixel_bbox to viewport
        cx0 = max(bb[0], vp[0]); cy0 = max(bb[1], vp[1])
        cx1 = min(bb[2], vp[2]); cy1 = min(bb[3], vp[3])

        # Which sub-tile Hilbert codes fall in the visible clip?
        # Uses pre-computed HILBERT_CACHE — no recomputation per request.
        tile_w = bb[2] - bb[0]; tile_h = bb[3] - bb[1]
        sw = tile_w / vis_grid;  sh = tile_h / vis_grid
        h_lut = HILBERT_CACHE.get(vis_order, {})

        visible_codes = []
        for sy in range(vis_grid):
            sub_y0 = bb[1] + sy * sh
            sub_y1 = sub_y0 + sh
            if sub_y0 >= cy1 or sub_y1 <= cy0:
                continue                          # entire row outside viewport
            for sx in range(vis_grid):
                sub_x0 = bb[0] + sx * sw
                sub_x1 = sub_x0 + sw
                if sub_x0 >= cx1 or sub_x1 <= cx0:
                    continue                      # this cell outside viewport
                visible_codes.append({
                    "code": h_lut.get((sx, sy), xy_to_hilbert(sx, sy, vis_order)),
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

