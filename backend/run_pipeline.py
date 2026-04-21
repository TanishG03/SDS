"""
run_pipeline.py
Runs the full adaptive Hilbert indexing pipeline end-to-end.

Usage:
  python run_pipeline.py [path/to/image.jpg]

Steps:
  1. region_segmenter.py    — segment image into region classes
  2. adaptive_hilbert_indexer.py — build variable-order Hilbert tile index
  3. Print a summary and launch the Flask server (optional)

Requirements:
  pip install pillow numpy flask
"""

import os
import sys
import json
import logging
import subprocess

logging.basicConfig(level=logging.INFO, format="%(asctime)s  %(message)s")
log = logging.getLogger("Pipeline")


def run_step(script: str, image_path: str, label: str):
    log.info(f"\n{'='*60}")
    log.info(f"  STEP: {label}")
    log.info(f"{'='*60}")
    result = subprocess.run(
        [sys.executable, script, image_path],
        capture_output=False
    )
    if result.returncode != 0:
        log.error(f"Step '{label}' failed with exit code {result.returncode}")
        sys.exit(result.returncode)


def print_index_summary():
    if not os.path.exists("tile_index.json"):
        return
    with open("tile_index.json") as f:
        index = json.load(f)

    from collections import Counter
    class_counts = Counter(r["region_class"] for r in index)
    order_counts = Counter(r["hilbert_order"] for r in index)

    log.info("\n" + "="*60)
    log.info("  PIPELINE SUMMARY")
    log.info("="*60)
    log.info(f"  Total sub-tiles indexed : {len(index)}")
    log.info(f"  By region class:")
    class_names = {0: "water/flat", 1: "transition", 2: "urban/detail"}
    order_map   = {0: 2, 1: 3, 2: 4}
    for cls in sorted(class_counts):
        n = class_counts[cls]
        o = order_map[cls]
        log.info(f"    Class {cls} ({class_names[cls]}, order={o}): {n:5d} sub-tiles")
    log.info(f"  By Hilbert order:")
    for order in sorted(order_counts):
        log.info(f"    Order {order} ({2**order}×{2**order} sub-grid): {order_counts[order]:5d} sub-tiles")
    log.info(f"\n  Output files:")
    for fname in ["segmentation_map.json", "segmentation_vis.png",
                  "tile_index.json", "adaptive_hilbert_index_vis.png",
                  "tile_store/"]:
        exists = os.path.exists(fname)
        log.info(f"    {'✓' if exists else '✗'} {fname}")
    log.info("="*60)
    log.info("\n  To start the Flask tile server:")
    log.info("    python tile_server.py")
    log.info("  API endpoints:")
    log.info("    GET http://localhost:5000/lod?zoom=0")
    log.info("    GET http://localhost:5000/lod?zoom=2")
    log.info("    GET http://localhost:5000/tile?z=1&x=3&y=3")
    log.info("    GET http://localhost:5000/segmentation")
    log.info("    GET http://localhost:5000/index_stats\n")


if __name__ == "__main__":
    image_path = sys.argv[1] if len(sys.argv) > 1 else "test1.jpg"

    if not os.path.exists(image_path):
        log.error(f"Image not found: '{image_path}'")
        log.error("Place test1.jpg in this directory, or pass a path as argument.")
        sys.exit(1)

    log.info(f"Using image: {image_path}")

    # Run each stage
    run_step("region_segmenter.py",      image_path, "Stage 1 — Region Segmentation")
    run_step("adaptive_hilbert_indexer.py", image_path, "Stage 2 — Adaptive Hilbert Indexing")

    print_index_summary()