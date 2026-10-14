# SAHAYAK Flood Mapper — Unified End-to-End Pipeline

This document describes the unified, reproducible end-to-end pipeline orchestrator for **SAHAYAK Flood Mapper**.

The pipeline executes the complete workflow in a single repository-root command:
1. **Pre-flight Verification**: Validates input SAR GeoTIFFs, trained U-Net checkpoint, OSM graph assets, and virtual environments.
2. **U-Net Full-Scene Inference**: Runs sliding-window tiled prediction with georeferencing on local Sentinel-1 SAR VV rasters.
3. **Road Graph Overlay & Routing**: Overlays predicted flood masks on the road network, runs Dijkstra reachability analysis, and computes rescue priority rankings.
4. **Frontend Data Export**: Computes WGS84 ellipsoidal geodesic inundation area, vectorizes flood masks into GeoJSON, and exports structured data artifacts to the frontend.
5. **Data Contract Validation & Unit Tests**: Enforces cross-file settlement reconciliation, coordinate validity bounds, positive flood area invariants, and executes the 32-test regression suite.
6. **Frontend Production Build**: Compiles TypeScript (`tsc -b`) and bundles production assets via Vite.

---

## Architecture & Important System Boundaries

### Static Artifact Model (Not a Live Inference API)
The SAHAYAK Flood Mapper frontend (React + Vite + Leaflet) loads pre-computed, schema-validated static JSON and GeoJSON artifacts from `frontend/src/data/`.
This pipeline is an **offline batch orchestration tool** designed for reproducible disaster analysis and static deployment. It is not an online server or live streaming inference endpoint.

### Google Earth Engine (GEE) Credentials
- SAR data acquisition (`data-acquisition/`) requires authenticated Google Earth Engine credentials managed by teammate Ravi.
- The end-to-end pipeline intentionally **does not trigger automatic satellite downloads**. It operates exclusively on existing local SAR GeoTIFFs (`ml-model/Data/raw/`) to ensure full offline reproducibility without risking API rate limits, authentication failures, or accidental raw data overwrites.

### Model Weights & Retraining
- The orchestrator **never retrains the U-Net model**. It executes inference using the validated model checkpoint (`ml-model/outputs/baseline_run_01/model_best.pth`).

---

## Prerequisites & Setup

### 1. Python Virtual Environments
The repository uses two isolated Python environments to prevent C-extension conflicts between PyTorch (CUDA) and GDAL/GeoPandas:

1. **ML Environment (`ml-model/.venv`)**:
   - Python: 3.11+
   - Packages: PyTorch, torchvision, `segmentation-models-pytorch`, rasterio, numpy
   - Setup:
     ```powershell
     cd ml-model
     python -m venv .venv
     .venv\Scripts\pip install -r requirements.txt
     cd ..
     ```

2. **Graph Analysis Environment (`graph-analysis/.venv`)**:
   - Python: 3.11+
   - Packages: geopandas, osmnx, networkx, shapely, pyproj, rasterio
   - Setup:
     ```powershell
     cd graph-analysis
     python -m venv .venv
     .venv\Scripts\pip install -r requirements.txt
     cd ..
     ```

### 2. Node.js & Frontend Environment
- Node.js (v18+ recommended)
- Dependencies installed in `frontend/`:
  ```powershell
  cd frontend
  npm install
  cd ..
  ```

### 3. Required Local Input Files
Before running the pipeline, ensure the following local assets exist:

| Asset Description | Path |
| :--- | :--- |
| Pre-flood Sentinel-1 SAR VV GeoTIFF | `ml-model/Data/raw/pre_flood_VV.tif` |
| Post-flood Sentinel-1 SAR VV GeoTIFF | `ml-model/Data/raw/post_flood_VV.tif` |
| Trained U-Net Model Checkpoint | `ml-model/outputs/baseline_run_01/model_best.pth` |
| Road Network GeoPackage | `graph-analysis/road_edges.gpkg` |
| OpenStreetMap GraphML Network | `graph-analysis/network.graphml` |
| Service Centers GeoJSON | `graph-analysis/service_centers.geojson` |
| Settlements GeoJSON | `graph-analysis/settlements.geojson` |

---

## Execution Guide

### One-Command Full Pipeline

From the repository root, run:

**Windows PowerShell:**
```powershell
& "ml-model/.venv/Scripts/python.exe" ml-model/scripts/run_e2e_pipeline.py --threshold 0.5
```

**Linux / macOS:**
```bash
./ml-model/.venv/bin/python ml-model/scripts/run_e2e_pipeline.py --threshold 0.5
```

### Command-Line Arguments

The orchestrator supports standard CLI options:

| Flag | Type | Default | Description |
| :--- | :--- | :--- | :--- |
| `--threshold` | `float` | `0.5` | Decision threshold for U-Net binary flood segmentation (0.0 – 1.0). Passed directly to `predict.py`. |
| `--dry-run` | `flag` | `False` | Validates prerequisites, input files, and virtual environments without running inference or builds. |
| `--skip-tests` | `flag` | `False` | Skips running the automated 32-test unit test suite during Stage 5. |
| `--skip-build` | `flag` | `False` | Skips the frontend production build (`tsc -b && vite build`) in Stage 6. |
| `--help` | `flag` | — | Displays the help text and argument summary. |

#### Dry-Run Example
```powershell
& "ml-model/.venv/Scripts/python.exe" ml-model/scripts/run_e2e_pipeline.py --dry-run
```

---

## Stage Breakdown & Output Artifacts

| Stage | Script / Action | Virtual Environment | Output Artifacts |
| :--- | :--- | :--- | :--- |
| **Stage 1: Pre-flight Verification** | Built-in check in `run_e2e_pipeline.py` | Host | Console status report |
| **Stage 2: U-Net Inference** | `ml-model/scripts/predict.py` | `ml-model/.venv` | `ml-model/outputs/inference_run_01/flood_prediction.tif`<br>`ml-model/outputs/inference_run_01/flood_probability.tif` |
| **Stage 3: Graph Overlay & Routing** | `ml-model/scripts/run_graph_integration.py` | `graph-analysis/.venv` | `graph-analysis/outputs/ml_run_01/cut_off_settlements.geojson`<br>`graph-analysis/outputs/ml_run_01/connected_settlements.geojson`<br>`graph-analysis/outputs/ml_run_01/flooded_roads.geojson`<br>`graph-analysis/outputs/ml_run_01/priority_rankings.geojson`<br>`graph-analysis/outputs/ml_run_01/summary_metrics.json` |
| **Stage 4: Frontend Data Export** | `ml-model/scripts/export_frontend_data.py` | `graph-analysis/.venv` | `frontend/src/data/ml_flood.json`<br>`frontend/src/data/ml_cutoff.json`<br>`frontend/src/data/ml_practical.json`<br>`frontend/src/data/ml_connected.json`<br>`frontend/src/data/ml_priority.json`<br>`frontend/src/data/ml_meta.json` |
| **Stage 5: Data Contract & Tests** | `validate_data_contracts()` + `unittest discover` | `ml-model/.venv` | 32 passed unit tests & schema invariant validation |
| **Stage 6: Frontend Build** | `npm run build` (`tsc -b && vite build`) | Node.js system PATH | `frontend/dist/` production bundle |

---

## Data Contract & Invariant Validation

Stage 5 validates critical invariants across all generated artifacts:
1. **Dynamic Cross-File Reconciliation**:
   $$\text{len(ml\_cutoff)} + \text{len(ml\_practical)} + \text{len(ml\_connected)} \equiv \text{meta.total\_settlements}$$
   Settlement numbers are verified relationally across files rather than hardcoding static snapshot counts.
2. **Priority Ranking Consistency**:
   The count of ranked priority features equals the total number of cut-off settlements ($\text{cutoff} + \text{practical}$).
3. **Geographic Coordinate Bounds**:
   All settlement centroids are verified to possess valid numeric latitudes $\in [-90, 90]$ and longitudes $\in [-180, 180]$.
4. **Geodesic Inundation Area**:
   Flood area is computed using `pyproj.Geod(ellps="WGS84")` for accurate ellipsoidal surface measurement and asserted to be positive ($> 0$).
5. **Experimental Provenance Metadata**:
   `ml_meta.json` is asserted to contain `is_experimental: true` and an explicit disclaimer distinguishing experimental U-Net predictions from official agency ground truth.

---

## Troubleshooting & Diagnostics

The orchestrator adheres to fail-fast principles with descriptive exit codes:

| Exit Code | Stage | Failure Cause & Remediation |
| :---: | :--- | :--- |
| **`1`** | Pre-flight Verification | Missing raw GeoTIFF, model checkpoint, graph asset, or virtual environment. Check the printed list of missing files and create required venvs. |
| **`2`** | U-Net Inference | CUDA out-of-memory or corrupt GeoTIFF. Verify GPU VRAM or run with CPU fallback if necessary. |
| **`3`** | Graph Analysis | Spatial mismatch or corrupt network graph. Verify `graph-analysis/road_edges.gpkg` CRS matches EPSG:4326. |
| **`4`** | Frontend Export | Geodesic area calculation or polygon vectorization failure. Verify `pyproj` and `shapely` are intact in `graph-analysis/.venv`. |
| **`5`** | Data Contract Violation | Discrepancy between exported settlement categories and metadata, out-of-bounds coordinates, or missing files. |
| **`6`** | Unit Test Failure | One or more tests in `ml-model/tests/` failed. Inspect test stack trace in terminal output. |
| **`7`** | Frontend Build Failure | TypeScript type errors or Vite bundling issues. Run `cd frontend && npm run build` to see detailed compiler diagnostics. |

---

## Safe Rerunning & Idempotency

The orchestrator is completely idempotent and safe to rerun repeatedly:
- It overwrites only generated output folders (`ml-model/outputs/inference_run_01/`, `graph-analysis/outputs/ml_run_01/`, `frontend/src/data/ml_*.json`, and `frontend/dist/`).
- It **never deletes, resets, or modifies** source code, model weights, or raw satellite imagery.
- Existing frontend scenarios ("Severe Scenario" and "Real Event") remain untouched.
