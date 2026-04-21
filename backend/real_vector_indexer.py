import os
import json
import logging
import math

logging.basicConfig(level=logging.INFO, format="%(asctime)s  %(message)s")
log = logging.getLogger("RealVectorIndexer")

SEG_MAP = "vector_segmentation_map.json"
NYC_DATA = "varied_roads.json"
INDEX_OUT = "vector_index.json"

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

def encode_key(region_class: int, order: int,
               base_tx: int, base_ty: int,
               sub_x: int, sub_y: int, hilbert: int) -> str:
    return (f"{region_class}_{order}_"
            f"{base_tx:02d}{base_ty:02d}_"
            f"{sub_x:02d}{sub_y:02d}_"
            f"{hilbert:08x}")

def build_real_index():
    if not os.path.exists(SEG_MAP):
        log.error(f"{SEG_MAP} missing")
        return
    if not os.path.exists(NYC_DATA):
        log.error(f"{NYC_DATA} missing")
        return

    with open(SEG_MAP) as f: seg = json.load(f)
    img_w, img_h = seg["image_size"]
    
    with open(NYC_DATA) as f: raw_data = json.load(f)
    ways = raw_data.get('elements', [])
    
    log.info(f"Loaded {len(ways)} features from {NYC_DATA}")

    # 1. Find the min/max coordinates
    min_lon, min_lat = float('inf'), float('inf')
    max_lon, max_lat = float('-inf'), float('-inf')
    
    valid_ways = []
    for w in ways:
        geom = w.get("geometry", [])
        if len(geom) < 2: continue
        pts = []
        for pt in geom:
            lon, lat = pt["lon"], pt["lat"]
            min_lon, min_lat = min(min_lon, lon), min(min_lat, lat)
            max_lon, max_lat = max(max_lon, lon), max(max_lat, lat)
            pts.append((lon, lat))
        valid_ways.append(pts)

    log.info(f"Geo bounds: Lon[{min_lon}, {max_lon}] Lat[{min_lat}, {max_lat}]")

    # 2. Normalize and project into Pixel space
    lon_range = max_lon - min_lon
    lat_range = max_lat - min_lat
    if lon_range == 0 or lat_range == 0:
        log.error("Invalid geometry range")
        return

    def to_pixel(lon, lat):
        # x: lon -> [0, img_w]
        x = ((lon - min_lon) / lon_range) * img_w
        # y: lat -> [0, img_h] BUT inverted since lat increases North, image Y increases down
        y = ((max_lat - lat) / lat_range) * img_h
        return [x, y]

    # Map each base tile's pixel bbox for lookup
    tile_grid = {} # (tx, ty) -> tile_meta
    for t in seg["tiles"]:
        tile_grid[(t["tile_x"], t["tile_y"])] = t
    
    tile_w = seg["tiles"][0]["pixel_bbox"][2] - seg["tiles"][0]["pixel_bbox"][0]
    tile_h = seg["tiles"][0]["pixel_bbox"][3] - seg["tiles"][0]["pixel_bbox"][1]

    # Sub-grid grouping
    # sub_grid_map[(tx, ty, sx, sy)] = list of features
    sub_grid_map = {}

    log.info("Mapping features into Hilbert sub-grids...")
    for pts in valid_ways:
        pix_pts = [to_pixel(lon, lat) for lon, lat in pts]
        
        # Calculate centroid in pixel space
        sum_x = sum(p[0] for p in pix_pts)
        sum_y = sum(p[1] for p in pix_pts)
        cx = sum_x / len(pix_pts)
        cy = sum_y / len(pix_pts)
        
        tile = None
        for t in seg["tiles"]:
            x0, y0, x1, y1 = t["pixel_bbox"]
            if x0 <= cx < x1 and y0 <= cy < y1:
                tile = t
                break
        
        if not tile:
            continue # out of bounds somehow
            
        cls = tile["class"]
        order = tile["order"]
        tx, ty = tile["tile_x"], tile["tile_y"]
        x0, y0, x1, y1 = tile["pixel_bbox"]
        
        # Which sub-grid within the tile?
        grid_dim = 2 ** order
        sub_w = (x1 - x0) / grid_dim
        sub_h = (y1 - y0) / grid_dim
        
        sx = int(max(0, min((cx - x0) // sub_w, grid_dim - 1)))
        sy = int(max(0, min((cy - y0) // sub_h, grid_dim - 1)))
        
        key = (tx, ty, sx, sy)
        if key not in sub_grid_map:
            sub_grid_map[key] = {
                "tile": tile,
                "features": []
            }
        
        sub_grid_map[key]["features"].append({
            "type": "LineString",
            "coordinates": pix_pts
        })

    # 3. Create Index Records
    index_records = []
    for (tx, ty, sx, sy), data in sub_grid_map.items():
        tile = data["tile"]
        cls = tile["class"]
        order = tile["order"]
        x0, y0, x1, y1 = tile["pixel_bbox"]
        
        h_code = xy_to_hilbert(sx, sy, order)
        row_key = encode_key(cls, order, tx, ty, sx, sy, h_code)
        
        grid_dim = 2 ** order
        sub_w = (x1 - x0) / grid_dim
        sub_h = (y1 - y0) / grid_dim
        abs_x0 = x0 + sx * sub_w
        abs_y0 = y0 + sy * sub_h
        abs_x1 = abs_x0 + sub_w
        abs_y1 = abs_y0 + sub_h
        bbox = [int(abs_x0), int(abs_y0), int(abs_x1), int(abs_y1)]
        
        record = {
            "key": row_key,
            "region_class": cls,
            "class_name": tile["class_name"],
            "hilbert_order": order,
            "base_tx": tx,
            "base_ty": ty,
            "sub_x": sx,
            "sub_y": sy,
            "hilbert_code": h_code,
            "abs_bbox": bbox,
            "features": data["features"]
        }
        index_records.append(record)

    index_records.sort(key=lambda r: r["key"])

    with open(INDEX_OUT, "w") as f:
        json.dump(index_records, f)

    log.info(f"Indexed {len(valid_ways)} vectors into {len(index_records)} Hilbert sub-grids -> {INDEX_OUT}")

if __name__ == "__main__":
    build_real_index()
