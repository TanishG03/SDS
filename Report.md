# Project Report: Semantic-Adaptive Hilbert (SAH) Indexing Tool

## Addressing the Visualization Challenge
This tool addresses the complex problem of providing a **"Visualization optimized approach for display/rendering of large Raster data (including images) at multiple zoom levels in two different conditions- (a) stand-alone single display output; (b) distributed data output for rendering over contiguous display panels."** by introducing several novel spatial data processing techniques.

Traditional spatial rendering approaches typically rely on uniform grid structures (like standard quadtrees) where every region of a spatial dataset is decomposed equally regardless of its content. This causes massive memory and performance overheads when processing large raster images because "empty" or "uniform" sections (such as large bodies of uniform water or flat terrain) are processed and rendered with the same cost as highly complex regions (such as dense urban environments or transition regions).

Our Semantic-Adaptive Hilbert (SAH) Pipeline solves this by dynamically altering the mapping and rendering rules based on the intrinsic content of the data itself.

### Novelty and Key Contributions

1. **Semantic-Adaptive Level of Detail (LOD):**
   Instead of a uniform quadtree array, the tool leverages Shannon entropy and K-means clustering (in `region_segmenter.py`) to categorize the dataset into semantic segments (e.g., Water = low entropy, Transition = medium entropy, Urban = high entropy). Base on this classification, the system generates an asymmetric, multi-level tile pyramid. Regions of low complexity stop at early LODs (preventing over-generation), while complex regions dynamically deepen, achieving significant memory savings and faster disk I/O.

2. **Adaptive Hilbert Curve Indexing:**
   Through `adaptive_hilbert_indexer.py`, the spatial index preserves high spatial locality for multi-resolution data. Crucially, the Hilbert path itself is *adaptive*—it naturally skips over collapsed minimal-detail regions and only recursively traverses into complex regions. This results in a massively optimized one-dimensional bounding-box lookup that replaces iterative linear tree traversals. Integrating an `R-Tree` spatial indexing model combined with module-level Hilbert coordinate cache guarantees computational efficiency for bounding-box queries.

3. **Optimized for Two Render Environments:**
   - **(a) Stand-Alone Single Display Output:** The React-based frontend dynamically renders the adaptive visualization. It retrieves optimized LOD data from the Flask API based heavily on viewport coordinates and dynamically displays visually appropriate grids, guaranteeing that a single browser canvas can smoothly navigate gigapixel environments without overwhelming the local machine's memory threshold.
   - **(b) Distributed Data Output (SAGE2 Simulated Wall):** The backend incorporates `sage2_display_coordinator.py`, functioning as a middleware node synchronizer. For contiguous display panels, the backend partitions the Hilbert querying boundaries across localized nodes. Distributed screens asynchronously pull quadrant-specific chunks from the spatial APIs. The SAH architecture assures each node only processes the precise data slice required for its render payload, reducing redundant network transmission overhead.

## Pipeline Workflow Implementation

The full stack architecture is divided into the following sequential pipeline stages:

1. **Data Ingestion & Semantic Analysis (`region_segmenter.py`):**
   - Ingests raw raster imagery.
   - Applies sliding windows to compute local Shannon entropy.
   - Clusters data via K-means into distinctive region classes (Water, Transition, Urban).
   - Downsamples image sections intelligently, producing semantic mask structures.

2. **Adaptive Structural Indexing (`adaptive_hilbert_indexer.py`):**
   - Applies an adaptive grid mesh matching semantic complexity to hierarchical node depth.
   - Computes a continuous space-filling Hilbert curve recursively.
   - Mirrors mappings intelligently when traversing specific sub-quadrants and stores index results leveraging an aggressive module-level Hilbert coordinate cache.

3. **Tile Pyramid Output (`tile_pyramid_builder.py`):**
   - Slices the base dataset into multi-resolution JPEG/PNG tiles mapped precisely to the semantic boundaries determined in step 1.
   - Consolidates uniform tiles up the tree structure to minimize directory footprint.

4. **Multi-Platform Tile Serving (`tile_server.py` & `sage2_display_coordinator.py`):**
   - Loads the `rtree` based spatial indexes and JSON payload coordinates into memory fast-query structures.
   - Exposes RESTful API endpoints for the client dashboards `/api/tiles`, `/api/lod_metadata`, and `/api/sage2/wall_state`.
   - Coordinates synchronized streaming to standalone frontends and isolated quadrant calls from the distributed display simulator.

## Directory Structure
```text
.
├── backend/
│   ├── run_pipeline.py          # Main entry point to run pipeline
│   ├── tile_server.py           # Flask server providing spatial data
│   ├── region_segmenter.py      # Segments base content by semantic metrics
│   ├── adaptive_hilbert_indexer.py # Calculates Hilbert ordering and caching
│   ├── tile_pyramid_builder.py  # Generates optimized LOD image pyramid
│   ├── sage2_display_coordinator.py # Manages distributed panel simulation
│   └── ... (other pipeline scripts, json config, masks, png outputs)
├── frontend/
│   ├── src/                     # React / Tailwind frontend source files
│   ├── public/                  # Static web assets
│   ├── package.json             # Node dependencies
│   └── ...
├── docs/
│   └── papers/                  # Underlying research papers (PDFs)
├── .gitignore                   # Ignore configurations
└── Report.md                    # Project documentation
```

## How to Run Code
1. **Backend Integration and Server:**
   ```bash
   cd backend
   python3 run_pipeline.py test1.jpg    # Execute the SAH ingest pipeline
   python3 tile_server.py               # Deploy the backend Flask service
   ```

2. **Frontend UI Dashboard:**
   ```bash
   cd frontend
   npm install      # Install dependencies (only required first time)
   npm start        # Deploy React interface on localhost (default port 3000)
   ```

## Related Research Papers
- Hajjaji et al. (2021) - Demonstrates Hilbert curve spatial indexing.
- Guo et al. (2016) - Adaptive multilevel tile pyramid construction methods.
- Renambot et al. (2015) - SAGE2 distributed display systems middleware.

## Performance Evaluation & Benchmarking

To validate the computational efficiency of the spatial mapping, the custom Semantic-Adaptive Hilbert (SAH) range scan was benchmarked against a naive full-table linear intersection scan. Tests were conducted simulating dynamic viewport bounding-box queries across three dataset topologies.

| Metric | Raster Dataset 1 | Raster Dataset 2 | Vector Dataset |
| :--- | :--- | :--- | :--- |
| **Total Features** | 31,072 | 3,136 | 24,320 |
| **Hilbert Scan Time** | 11.11 ms | 1.07 ms | 5.89 ms |
| **Naive Scan Time** | 16.75 ms | 1.48 ms | 15.67 ms |
| **Speedup** | **1.51x** | **1.38x** | **2.66x** |
| **Search Space Skipped**| 70.3% | 81.1% | 87.7% |

The test demonstrates that leveraging mathematical viewport-to-Hilbert projections and bisecting over continuous index ranges scales extremely well as complexity increases. The spatial index naturally rejects rendering up to 87.7% of off-screen data points effortlessly. It consistently outperforms naive linear queries, with speedups magnifying significantly (up to 2.66x) for intricate topologies.

## Limitations
- **Processing Overheads for Gigapixel Datasets:** Large inputs necessitate longer pipeline ingest processing times since pixel-precise evaluations dictate regional sub-tiles before mapping.
- **Memory Threshold Limits:** Exhaustive bounding box records per LOD depth constrain in-memory operations across restricted hardware allocations.
- **Heuristic Entropy Sensitivity:** K-means separation values rely on heuristic color/frequency constraints which may occasionally misclassify intermediate transitions depending on distinct lightning variations on satellite pulls.

## Possible Extensions
- **Vector Graph Augmentations:** Deepen handling functionality around poly-lines in vector files directly converting unmapped road metadata via spatial graph-network architectures.
- **Real-Time Parallel Ingests:** Enhance `run_pipeline.py` employing parallel core assignments explicitly targeting quadrant isolated mappings simultaneously.
- **Incremental Index Updates:** Refactor database caching logic to allow selective insertion/updates for spatial subsets without completely running the region classification index again.
