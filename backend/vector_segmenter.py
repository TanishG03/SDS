import os
import json
import logging

logging.basicConfig(level=logging.INFO, format="%(asctime)s  %(message)s")
log = logging.getLogger("VectorSegmenter")

NYC_DATA = "varied_roads.json"
SEG_OUT = "vector_segmentation_map.json"
IMG_W, IMG_H = 1600, 1600
MAX_DEPTH = 5

def build_vector_segmentation():
    if not os.path.exists(NYC_DATA):
        log.error(f"{NYC_DATA} missing")
        return

    with open(NYC_DATA) as f: raw_data = json.load(f)
    ways = raw_data.get('elements', [])
    log.info(f"Loaded {len(ways)} features from {NYC_DATA}")

    # 1. Geo Bounds
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

    lon_range = max_lon - min_lon
    lat_range = max_lat - min_lat

    def to_pixel(lon, lat):
        x = ((lon - min_lon) / lon_range) * IMG_W
        y = ((max_lat - lat) / lat_range) * IMG_H
        return x, y

    # Convert all ways to pixel bounding boxes for fast intersection checks
    way_bboxes = []
    for pts in valid_ways:
        pix_pts = [to_pixel(lon, lat) for lon, lat in pts]
        xs = [p[0] for p in pix_pts]
        ys = [p[1] for p in pix_pts]
        way_bboxes.append((min(xs), min(ys), max(xs), max(ys)))

    def count_intersecting(x0, y0, x1, y1):
        count = 0
        for wx0, wy0, wx1, wy1 in way_bboxes:
            # Check overlap
            if wx0 < x1 and wx1 > x0 and wy0 < y1 and wy1 > y0:
                count += 1
        return count

    tiles = []
    
    def quadtree(x0, y0, width, height, depth, tx, ty):
        count = count_intersecting(x0, y0, x0 + width, y0 + height)
        
        # Split condition: > 200 roads and not at max depth
        if count > 200 and depth < MAX_DEPTH:
            hw = width / 2
            hh = height / 2
            quadtree(x0, y0, hw, hh, depth + 1, tx * 2, ty * 2)
            quadtree(x0 + hw, y0, hw, hh, depth + 1, tx * 2 + 1, ty * 2)
            quadtree(x0, y0 + hh, hw, hh, depth + 1, tx * 2, ty * 2 + 1)
            quadtree(x0 + hw, y0 + hh, hw, hh, depth + 1, tx * 2 + 1, ty * 2 + 1)
        else:
            # Leaf node classification
            if count < 50:
                cls = 0; order = 2; cname = "water"
            elif count < 200:
                cls = 1; order = 3; cname = "transition"
            else:
                cls = 2; order = 4; cname = "urban"
                
            tiles.append({
                "tile_x": tx,
                "tile_y": ty,
                "width": int(width),
                "height": int(height),
                "depth": depth,
                "class": cls,
                "order": order,
                "class_name": cname,
                "entropy": count, # store count as "entropy" for debugging
                "pixel_bbox": [int(x0), int(y0), int(x0 + width), int(y0 + height)]
            })

    log.info("Building QuadTree segmentation based on road density...")
    quadtree(0, 0, IMG_W, IMG_H, 0, 0, 0)
    
    out_data = {
        "grid_size": 2 ** MAX_DEPTH,
        "image_size": [IMG_W, IMG_H],
        "cell_size": [int(IMG_W / (2 ** MAX_DEPTH)), int(IMG_H / (2 ** MAX_DEPTH))],
        "max_depth": MAX_DEPTH,
        "tiles": tiles
    }
    
    with open(SEG_OUT, "w") as f:
        json.dump(out_data, f, indent=2)
        
    log.info(f"Generated {len(tiles)} base tiles -> {SEG_OUT}")

if __name__ == "__main__":
    build_vector_segmentation()
