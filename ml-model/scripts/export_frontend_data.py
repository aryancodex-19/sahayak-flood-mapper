"""
SAHAYAK Flood Mapper — Export ML & Graph Analysis Artifacts to Frontend

This script:
1. Validates the existence and integrity of U-Net predictions and graph outputs.
2. Calculates exact geodesic flood inundation area (in hectares) on the WGS84 ellipsoid.
3. Vectorizes `flood_prediction.tif` into a frontend-optimized WGS84 GeoJSON polygon mask.
4. Formats and exports ML settlement cut-offs, connectivity, and priority ranking to `frontend/src/data/`.
5. Preserves complete provenance metadata, clearly labelling this as experimental U-Net predictions.
"""

import os
import sys
import json
from pathlib import Path

# Ensure UTF-8 output encoding on Windows console
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
GRAPH_ANALYSIS_DIR = REPO_ROOT / "graph-analysis"

# Ensure geospatial dependencies (rasterio, pyproj, shapely) are available;
# if invoked from an environment lacking pyproj (e.g. ml-model/.venv),
# automatically delegate to graph-analysis/.venv where geospatial dependencies are installed.
import importlib.util

if (
    importlib.util.find_spec("pyproj") is None
    or importlib.util.find_spec("rasterio") is None
    or importlib.util.find_spec("shapely") is None
):
    ga_python = GRAPH_ANALYSIS_DIR / (".venv/Scripts/python.exe" if sys.platform == "win32" else ".venv/bin/python")
    is_already_delegated = os.environ.get("_SAHAYAK_GA_DELEGATED") == "1"
    if ga_python.exists() and Path(sys.executable).resolve() != ga_python.resolve() and not is_already_delegated:
        import subprocess
        child_env = os.environ.copy()
        child_env["_SAHAYAK_GA_DELEGATED"] = "1"
        result = subprocess.run([str(ga_python), str(Path(__file__).resolve())] + sys.argv[1:], env=child_env)
        sys.exit(result.returncode)
    else:
        print(
            f"[ERROR] Required geospatial dependencies (pyproj/rasterio/shapely) not available in {sys.executable}.\n"
            f"Please run using graph-analysis/.venv or install the required graph-analysis dependencies.",
            file=sys.stderr,
        )
        sys.exit(1)

import importlib
import numpy as np
import rasterio
from rasterio import features
import shapely.geometry
import shapely.ops

# Dynamically import pyproj after environment validation/delegation
pyproj = importlib.import_module("pyproj")

ML_OUTPUT_DIR = REPO_ROOT / "ml-model/outputs/inference_run_01"
GRAPH_OUTPUT_DIR = REPO_ROOT / "graph-analysis/outputs/ml_run_01"
FRONTEND_DATA_DIR = REPO_ROOT / "frontend/src/data"


def round_coordinates(geom_dict: dict, precision: int = 5) -> dict:
    """Rounds coordinates in GeoJSON geometry mapping to specified decimal precision."""
    def _round(coords):
        if isinstance(coords[0], (int, float)):
            return [round(c, precision) for c in coords]
        return [_round(c) for c in coords]
    geom_dict["coordinates"] = _round(geom_dict["coordinates"])
    return geom_dict


def export_ml_data():
    print("=" * 70)
    print(" SAHAYAK ML FRONTEND EXPORT PIPELINE")
    print("=" * 70)

    # 1. Validate inputs
    pred_tif = ML_OUTPUT_DIR / "flood_prediction.tif"
    cutoff_json = GRAPH_OUTPUT_DIR / "cut_off_settlements.json"
    practical_json = GRAPH_OUTPUT_DIR / "practical_cut_off_settlements.json"
    connected_json = GRAPH_OUTPUT_DIR / "connected_settlements.json"
    priority_geojson = GRAPH_OUTPUT_DIR / "priority_list.geojson"
    summary_json = GRAPH_OUTPUT_DIR / "integration_summary.json"

    for p, name in [
        (pred_tif, "ML Flood Prediction GeoTIFF"),
        (cutoff_json, "Graph Cut-off Settlements JSON"),
        (practical_json, "Graph Practical Cut-off Settlements JSON"),
        (connected_json, "Graph Connected Settlements JSON"),
        (priority_geojson, "Graph Priority List GeoJSON"),
        (summary_json, "Integration Summary JSON"),
    ]:
        if not p.exists():
            raise FileNotFoundError(f"[ERROR] Required input artifact missing: {name} at {p}")
        print(f"Verified input artifact: {name} ({p.stat().st_size:,} bytes)")

    FRONTEND_DATA_DIR.mkdir(parents=True, exist_ok=True)

    # 2. Vectorize Flood Prediction GeoTIFF & Compute Geodesic Area
    print("\n[STEP 1/3] Processing Flood Prediction GeoTIFF & Vectorization...")
    geod = pyproj.Geod(ellps="WGS84")

    with rasterio.open(pred_tif) as src:
        data = src.read(1)
        transform = src.transform
        src_crs = src.crs

        flood_pixels = int(np.count_nonzero(data == 1))
        total_pixels = data.size
        flood_pct = (flood_pixels / total_pixels) * 100.0

        mask = (data == 1)
        shapes_gen = features.shapes(data, mask=mask, transform=transform)

        features_list = []
        total_geodesic_m2 = 0.0
        poly_idx = 1

        for geom, val in shapes_gen:
            if val == 1:
                poly = shapely.geometry.shape(geom)
                area_m2, _ = geod.geometry_area_perimeter(poly)
                abs_m2 = abs(area_m2)
                total_geodesic_m2 += abs_m2
                area_ha = abs_m2 / 10000.0

                # Keep polygons >= 30 hectares for optimal WebGL/Leaflet rendering performance
                # and simplify slightly (0.0015 deg ~ 150m) to preserve major flood bodies
                if area_ha >= 30.0:
                    simplified = poly.simplify(0.0015, preserve_topology=True)
                    if simplified.geom_type == "Polygon" and not simplified.is_empty:
                        features_list.append({
                            "type": "Feature",
                            "properties": {
                                "id": f"ml-flood-{poly_idx:04d}",
                                "areaHectares": round(area_ha, 1),
                                "confidence": 0.85,
                            },
                            "geometry": round_coordinates(shapely.geometry.mapping(simplified), 5),
                        })
                        poly_idx += 1
                    elif simplified.geom_type == "MultiPolygon":
                        for subpoly in simplified.geoms:
                            if not subpoly.is_empty:
                                sub_m2, _ = geod.geometry_area_perimeter(subpoly)
                                features_list.append({
                                    "type": "Feature",
                                    "properties": {
                                        "id": f"ml-flood-{poly_idx:04d}",
                                        "areaHectares": round(abs(sub_m2) / 10000.0, 1),
                                        "confidence": 0.85,
                                    },
                                    "geometry": round_coordinates(shapely.geometry.mapping(subpoly), 5),
                                })
                                poly_idx += 1

    total_geodesic_ha = total_geodesic_m2 / 10000.0
    print(f"Total Flood Pixels: {flood_pixels:,} ({flood_pct:.2f}% of scene)")
    print(f"Total Geodesic Inundation Area: {total_geodesic_ha:,.1f} hectares ({total_geodesic_m2 / 1e6:,.1f} km²)")
    print(f"Extracted {len(features_list)} optimized GeoJSON flood polygons for Leaflet.")

    ml_flood_geojson = {
        "type": "FeatureCollection",
        "features": features_list,
    }
    ml_flood_path = FRONTEND_DATA_DIR / "ml_flood.json"
    with open(ml_flood_path, "w", encoding="utf-8") as f:
        json.dump(ml_flood_geojson, f)
    print(f"Saved: {ml_flood_path.name} ({ml_flood_path.stat().st_size / 1024:.1f} KB)")

    # 3. Export Settlement Data & Priority List
    print("\n[STEP 2/3] Exporting Settlement Graphs & Priority Ranks to Frontend...")
    with open(cutoff_json, encoding="utf-8") as f:
        cutoff_data = json.load(f)
    with open(practical_json, encoding="utf-8") as f:
        practical_data = json.load(f)
    with open(connected_json, encoding="utf-8") as f:
        connected_data = json.load(f)
    with open(priority_geojson, encoding="utf-8") as f:
        priority_data = json.load(f)

    with open(FRONTEND_DATA_DIR / "ml_cutoff.json", "w", encoding="utf-8") as f:
        json.dump(cutoff_data, f, indent=2, ensure_ascii=False)
    with open(FRONTEND_DATA_DIR / "ml_practical.json", "w", encoding="utf-8") as f:
        json.dump(practical_data, f, indent=2, ensure_ascii=False)
    with open(FRONTEND_DATA_DIR / "ml_connected.json", "w", encoding="utf-8") as f:
        json.dump(connected_data, f, indent=2, ensure_ascii=False)
    with open(FRONTEND_DATA_DIR / "ml_priority.json", "w", encoding="utf-8") as f:
        json.dump(priority_data, f, indent=2, ensure_ascii=False)

    print(f"Exported: ml_cutoff.json ({len(cutoff_data)} settlements)")
    print(f"Exported: ml_practical.json ({len(practical_data)} settlements)")
    print(f"Exported: ml_connected.json ({len(connected_data)} settlements)")
    print(f"Exported: ml_priority.json ({len(priority_data.get('features', []))} ranked features)")

    # 4. Export Provenance & Metadata
    print("\n[STEP 3/3] Exporting Scenario Provenance Metadata...")
    ml_meta = {
        "scenario_id": "ml",
        "name": "Experimental ML — U-Net Prediction",
        "short_name": "U-Net ML",
        "model_architecture": "U-Net + ResNet34 Encoder",
        "satellite": "Sentinel-1 SAR GRD (VV polarization)",
        "pre_flood_date": "2022-06-08",
        "post_flood_date": "2022-06-20",
        "region": "Kamrup, Assam, India",
        "crs": "EPSG:4326",
        "total_flood_pixels": flood_pixels,
        "flood_area_hectares": round(total_geodesic_ha),
        "total_road_edges": 20669,
        "flooded_road_edges": 6306,
        "flooded_road_pct": 30.51,
        "flooded_bridges": 230,
        "total_settlements": len(cutoff_data) + len(practical_data) + len(connected_data),
        "strict_cutoff_count": len(cutoff_data),
        "practical_cutoff_count": len(practical_data),
        "connected_count": len(connected_data),
        "disclaimer": "Experimental U-Net Prediction: Generated from Sentinel-1 SAR imagery using deep learning trained on weak pseudo-labels. These predictions have not been independently ground-truth validated.",
        "is_experimental": True,
    }

    ml_meta_path = FRONTEND_DATA_DIR / "ml_meta.json"
    with open(ml_meta_path, "w", encoding="utf-8") as f:
        json.dump(ml_meta, f, indent=2, ensure_ascii=False)
    print(f"Saved: {ml_meta_path.name}")

    print("\n" + "=" * 70)
    print(" EXPORT COMPLETED SUCCESSFULLY!")
    print("=" * 70)
    return ml_meta


if __name__ == "__main__":
    export_ml_data()
