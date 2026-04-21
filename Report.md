# Project Report: Semantic-Adaptive Hilbert (SAH) Indexing Tool

## Project Description
This project is a full-featured Spatial Data Science tool demonstrating Semantic-Adaptive Hilbert (SAH) Indexing. The system processes spatial datasets (e.g., satellite imagery, vector maps) to segment regions dynamically based on semantic content such as entropy and color composition. It then indexes these generated tiles using an adaptive Hilbert curve ordering that guarantees optimal multi-resolution viewing at different Levels of Detail (LODs).

## Directory Structure
```
.
├── backend/
│   ├── run_pipeline.py          # Main entry point to run pipeline
│   ├── tile_server.py           # Flask server providing spatial data
│   ├── region_segmenter.py      # Segments base content by semantic metrics
│   ├── adaptive_hilbert_indexer.py # Calculates Hilbert ordering and caching
│   ├── ... (other pipeline scripts, json config, masks, png outputs)
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
   python run_pipeline.py test1.jpg    # Execute the SAH ingest pipeline
   python tile_server.py               # Deploy the backend Flask service
   ```

2. **Frontend UI Dashboard:**
   ```bash
   cd frontend
   npm install      # Install dependencies (only required first time)
   npm start        # Deploy React interface on localhost (default port 3000)
   ```

## Usage of this Tool
Through the frontend UI dashboard, users can upload datasets/images, observe real-time dynamic semantic segmentations (categorized into water, transition, and urban clusters), and visualize the overlaying Hilbert Path indexing scheme. Selecting an area generates immediate query performance comparisons natively against full linear map scans, rendering the results on the SAGE2 distributed wall simulation interfaces and single-canvas maps seamlessly.

## Novelty
- **Semantic Data Adaptation:** Instead of maintaining a uniform static grid, this method optimizes scale by assigning diverse index orderings proportional to local node entropy and regional complexity. Flat terrains use minimal nodes, while urban high-frequency areas dynamically utilize deeper multi-level grids.
- **Combined Visualization Workflows:** Blends dynamic background region mapping, adaptive Hilbert generation, and multi-panel LOD adjustments directly within one synchronous full-stack architecture.
- **Immediate Spatial Scanning Advantages:** Incorporates bisection scans optimized by class-ordering dictionaries rather than iterative lookups, offering substantial mathematical reduction in processed query times.

## Related Research Papers
- Hajjaji et al. (2021) - Demonstrates Hilbert curve spatial indexing.
- Guo et al. (2016) - Adaptive multilevel tile pyramid construction methods.
- Renambot et al. (2015) - SAGE2 distributed display systems middleware.

## Limitations
- **Processing Overheads for Gigapixel Datasets:** Large inputs necessitate longer pipeline ingest processing times since pixel-precise evaluations dictate regional sub-tiles before mapping.
- **Memory Threshold Limits:** Exhaustive bounding box records per LOD depth constrain in-memory operations across restricted hardware allocations.
- **Heuristic Entropy Sensitivity:** K-means separation values rely on heuristic color/frequency constraints which may occasionally misclassify intermediate transitions depending on distinct lightning variations on satellite pulls.

## Possible Extensions
- **Vector Graph Augmentations:** Deepen handling functionality around poly-lines in vector files directly converting unmapped road metadata via spatial graph-network architectures.
- **Real-Time Parallel Ingests:** Enhance `run_pipeline.py` employing parallel core assignments explicitly targeting quadrant isolated mappings simultaneously.
- **Incremental Index Updates:** Refactor database caching logic to allow selective insertion/updates for spatial subsets without completely running the region classification index again.
