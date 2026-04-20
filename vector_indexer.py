import os
import json
import random
import logging

logging.basicConfig(level=logging.INFO, format="%(asctime)s  %(message)s")
log = logging.getLogger("VectorIndexer")

SEG_MAP = "segmentation_map.json"
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

def generate_vector_features(cls: int, x0: float, y0: float, x1: float, y1: float):
    """
    Generate synthetic vector data (LineStrings) based on class complexity.
    cls 0 (Water): 1 simple line
    cls 1 (Transition): 2 lines
    cls 2 (Urban): 4 intersecting lines
    """
    features = []
    w = x1 - x0
    h = y1 - y0
    
    if cls == 0:
        # 1 straight line
        y_pos = y0 + h * random.uniform(0.2, 0.8)
        features.append({
            "type": "LineString",
            "coordinates": [[x0, y_pos], [x1, y_pos]]
        })
    elif cls == 1:
        # 2 intersecting lines
        cx = x0 + w * 0.5 + random.uniform(-w*0.1, w*0.1)
        cy = y0 + h * 0.5 + random.uniform(-h*0.1, h*0.1)
        features.append({
            "type": "LineString",
            "coordinates": [[x0, y0 + h * random.uniform(0, 1)], [cx, cy], [x1, y0 + h * random.uniform(0, 1)]]
        })
        features.append({
            "type": "LineString",
            "coordinates": [[x0 + w * random.uniform(0, 1), y0], [cx, cy], [x0 + w * random.uniform(0, 1), y1]]
        })
    else:
        # Dense mini grid
        num_v = random.randint(3, 5)
        num_h = random.randint(3, 5)
        for i in range(num_v):
            vx = x0 + (w / num_v) * i + random.uniform(0, w*0.05)
            features.append({
                "type": "LineString",
                "coordinates": [[vx, y0], [vx + random.uniform(-2, 2), y0 + h/2], [vx, y1]]
            })
        for i in range(num_h):
            vy = y0 + (h / num_h) * i + random.uniform(0, h*0.05)
            features.append({
                "type": "LineString",
                "coordinates": [[x0, vy], [x0 + w/2, vy + random.uniform(-2, 2)], [x1, vy]]
            })
            
    return features

def build_vector_index():
    if not os.path.exists(SEG_MAP):
        log.error(f"{SEG_MAP} not found.")
        return

    with open(SEG_MAP) as f:
        seg = json.load(f)

    index_records = []
    class_stats = {0: 0, 1: 0, 2: 0}

    for tile_info in seg["tiles"]:
        base_tx = tile_info["tile_x"]
        base_ty = tile_info["tile_y"]
        cls     = tile_info["class"]
        order   = tile_info["order"]
        x0, y0, x1, y1 = tile_info["pixel_bbox"]

        sub_grid = 2 ** order
        sub_w = (x1 - x0) / sub_grid
        sub_h = (y1 - y0) / sub_grid

        for sy in range(sub_grid):
            for sx in range(sub_grid):
                h_code = xy_to_hilbert(sx, sy, order)

                abs_x0 = x0 + sx * sub_w
                abs_y0 = y0 + sy * sub_h
                abs_x1 = abs_x0 + sub_w
                abs_y1 = abs_y0 + sub_h
                
                # Bbox integer precision slightly expanded
                bbox = [int(abs_x0), int(abs_y0), int(abs_x1), int(abs_y1)]

                features = generate_vector_features(cls, abs_x0, abs_y0, abs_x1, abs_y1)

                row_key = encode_key(cls, order, base_tx, base_ty, sx, sy, h_code)

                record = {
                    "key": row_key,
                    "region_class": cls,
                    "class_name": tile_info["class_name"],
                    "hilbert_order": order,
                    "base_tx": base_tx,
                    "base_ty": base_ty,
                    "sub_x": sx,
                    "sub_y": sy,
                    "hilbert_code": h_code,
                    "abs_bbox": bbox,
                    "features": features
                }
                index_records.append(record)
                class_stats[cls] += 1

    index_records.sort(key=lambda r: r["key"])

    with open(INDEX_OUT, "w") as f:
        json.dump(index_records, f, indent=2)

    log.info(f"Indexed {len(index_records)} vector features -> {INDEX_OUT}")
    for c, n in class_stats.items():
        log.info(f"  Class {c}: {n} sub-grids")

if __name__ == "__main__":
    log.info("Generating Semantic-Adaptive Vector Index...")
    random.seed(42) # For reproducibility
    build_vector_index()
