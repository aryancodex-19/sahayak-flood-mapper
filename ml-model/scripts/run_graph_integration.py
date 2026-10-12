"""
SAHAYAK Flood Mapper — Step 6, Phase 3: Graph Analysis ML Integration Runner

Runs the full graph-analysis pipeline (Flood Overlay -> Connectivity Analysis -> Priority Ranking)
using the preliminary U-Net binary prediction raster (flood_prediction.tif) without overwriting
any teammate files or downloading road networks.
"""

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

# Add graph-analysis directory to sys.path
repo_root = Path(__file__).resolve().parent.parent.parent
graph_analysis_dir = repo_root / "graph-analysis"
if str(graph_analysis_dir) not in sys.path:
    sys.path.insert(0, str(graph_analysis_dir))

from flood_overlay import overlay_flood_on_network
from connectivity import analyze_flood_connectivity
from priority_ranking import rank_cutoff_settlements


def run_integration():
    print("=" * 70)
    print(" SAHAYAK ML GRAPH INTEGRATION RUNNER (Phase 3)")
    print("=" * 70)

    # 1. Inputs validation
    flood_pred_path = repo_root / "ml-model/outputs/inference_run_01/flood_prediction.tif"
    road_edges_path = graph_analysis_dir / "road_edges.gpkg"
    network_graphml_path = graph_analysis_dir / "network.graphml"
    service_centers_path = graph_analysis_dir / "service_centers.geojson"
    settlements_path = graph_analysis_dir / "settlements.geojson"

    output_dir = graph_analysis_dir / "outputs/ml_run_01"
    output_dir.mkdir(parents=True, exist_ok=True)

    for p, name in [
        (flood_pred_path, "ML Flood Prediction GeoTIFF"),
        (road_edges_path, "Road Edges GeoPackage"),
        (network_graphml_path, "Road Network GraphML"),
        (service_centers_path, "Service Centers GeoJSON"),
        (settlements_path, "Settlements GeoJSON"),
    ]:
        if not p.exists():
            raise FileNotFoundError(f"Missing required input asset: {name} at {p}")
        print(f"Verified input: {name} -> {p.name}")

    print(f"Isolated Output Directory: {output_dir}")
    print("=" * 70)

    # Output paths
    flooded_gpkg = output_dir / "flooded_edges.gpkg"
    flooded_geojson = output_dir / "flooded_edges.geojson"
    cutoff_json = output_dir / "cut_off_settlements.json"
    practical_cutoff_json = output_dir / "practical_cut_off_settlements.json"
    connected_json = output_dir / "connected_settlements.json"
    priority_csv = output_dir / "priority_list.csv"
    priority_geojson = output_dir / "priority_list.geojson"

    # Step 1: Flood Overlay
    print("\n[STEP 1/3] Executing Flood Overlay on Road Network...")
    overlay_stats = overlay_flood_on_network(
        edges_path=road_edges_path,
        flood_mask_path=flood_pred_path,
        output_gpkg_path=flooded_gpkg,
        output_geojson_path=flooded_geojson,
    )

    # Step 2: Connectivity Analysis
    print("\n[STEP 2/3] Executing Connectivity & Cut-Off Analysis...")
    connectivity_stats = analyze_flood_connectivity(
        graph_path=network_graphml_path,
        flooded_edges_path=flooded_geojson,
        service_centers_path=service_centers_path,
        settlements_path=settlements_path,
        output_dir=output_dir,
        place_name="Kamrup, Assam, India",
        detour_threshold=3.0,
    )

    # Step 3: Priority Ranking
    print("\n[STEP 3/3] Executing Rescue Priority Ranking...")
    ranking_stats = rank_cutoff_settlements(
        cutoff_file=cutoff_json,
        connected_file=connected_json,
        graph_file=network_graphml_path,
        service_centers_file=service_centers_path,
        output_dir=output_dir,
    )

    # Save integration metadata JSON
    summary = {
        "scenario": "Experimental U-Net Prediction (June 2022 Kamrup Baseline)",
        "disclaimer": "Preliminary model predictions trained against pseudo-labels; not verified ground-truth flood extent.",
        "input_flood_raster": str(flood_pred_path),
        "total_edges": overlay_stats.get("total_edges"),
        "flooded_edges": overlay_stats.get("flooded_edges"),
        "flooded_bridges": overlay_stats.get("flooded_bridges"),
        "flooded_tunnels": overlay_stats.get("flooded_tunnels"),
        "pct_flooded_edges": overlay_stats.get("pct_flooded"),
        "total_settlements": connectivity_stats.get("total_settlements"),
        "strict_cutoff_count": connectivity_stats.get("strict_cutoff_count"),
        "practical_cutoff_count": connectivity_stats.get("practical_cutoff_count"),
        "connected_count": connectivity_stats.get("connected_count"),
        "total_ranked_settlements": ranking_stats.get("total_ranked"),
        "top_priority_settlements": ranking_stats.get("top_5", []),
        "outputs": {
            "flooded_edges_gpkg": str(flooded_gpkg),
            "flooded_edges_geojson": str(flooded_geojson),
            "cut_off_settlements_json": str(cutoff_json),
            "practical_cut_off_settlements_json": str(practical_cutoff_json),
            "connected_settlements_json": str(connected_json),
            "priority_list_csv": str(priority_csv),
            "priority_list_geojson": str(priority_geojson),
        },
    }

    summary_path = output_dir / "integration_summary.json"
    with open(summary_path, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2)

    print("\n" + "=" * 70)
    print(" INTEGRATION RUN SUCCESSFUL!")
    print(f" Summary saved to: {summary_path}")
    print("=" * 70)

    return summary


if __name__ == "__main__":
    run_integration()
