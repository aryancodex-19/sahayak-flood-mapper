"""
Sahayak Flood Mapper - Graph Analysis Pipeline Runner
Orchestrates end-to-end network extraction, flood overlay, connectivity analysis, and rescue priority ranking.
"""

import sys
import argparse
from pathlib import Path
from typing import Dict, Any, Optional

# Ensure UTF-8 output encoding on Windows console
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

# Import pipeline modular functions
try:
    from download_network import download_and_save_network
    from flood_overlay import overlay_flood_on_network
    from connectivity import analyze_flood_connectivity
    from priority_ranking import rank_cutoff_settlements
except ImportError:
    # Support running when script's parent folder is not in sys.path
    current_dir = Path(__file__).resolve().parent
    if str(current_dir) not in sys.path:
        sys.path.insert(0, str(current_dir))
    from download_network import download_and_save_network
    from flood_overlay import overlay_flood_on_network
    from connectivity import analyze_flood_connectivity
    from priority_ranking import rank_cutoff_settlements


def run_pipeline(
    flood_mask_path: str,
    region: str = "Kamrup, Assam, India",
    detour_threshold: float = 3.0,
    skip_download: bool = False,
    use_ml: bool = False,
    output_dir: str = ".",
) -> Dict[str, Any]:
    """
    Executes the end-to-end graph analysis pipeline.
    
    Args:
        flood_mask_path: Path to flood mask (.geojson or .tif)
        region: OSM place name for road network
        detour_threshold: Detour multiplier threshold for practical cut-offs
        skip_download: If True, skips OSM download if network.graphml exists
        use_ml: Placeholder flag for ML refinement models
        output_dir: Directory to save generated artifacts
    """
    base_output_dir = Path(output_dir).resolve()
    base_output_dir.mkdir(parents=True, exist_ok=True)

    flood_mask = Path(flood_mask_path).resolve()
    if not flood_mask.exists():
        print(f"\n[ERROR] Flood mask file not found: {flood_mask}", file=sys.stderr)
        sys.exit(1)

    print("\n" + "=" * 60)
    print("STARTING SAHAYAK GRAPH ANALYSIS PIPELINE")
    print("=" * 60)
    print(f"Region:           {region}")
    print(f"Flood Mask:       {flood_mask}")
    print(f"Detour Threshold: {detour_threshold:.1f}x")
    print(f"Output Directory: {base_output_dir}")
    if use_ml:
        print("ML Refinement:    Enabled (heuristic model baseline)")
    print("=" * 60)

    # File paths
    graphml_path = base_output_dir / "network.graphml"
    road_edges_gpkg = base_output_dir / "road_edges.gpkg"
    flooded_gpkg = base_output_dir / "flooded_edges.gpkg"
    flooded_geojson = base_output_dir / "flooded_edges.geojson"
    service_centers_geojson = base_output_dir / "service_centers.geojson"
    settlements_geojson = base_output_dir / "settlements.geojson"
    cutoff_json = base_output_dir / "cut_off_settlements.json"
    practical_cutoff_json = base_output_dir / "practical_cut_off_settlements.json"
    connected_json = base_output_dir / "connected_settlements.json"
    priority_csv = base_output_dir / "priority_list.csv"
    priority_geojson = base_output_dir / "priority_list.geojson"

    # Step 1: Road Network
    print("\n[STEP 1/4] Preparing Road Network...")
    try:
        if skip_download and graphml_path.exists():
            print(f"Found existing road network at: {graphml_path.name} (--skip-download enabled). Skipping OSM download.")
        else:
            download_and_save_network(place_name=region, output_dir=base_output_dir)
    except Exception as exc:
        print(f"\n[FATAL ERROR] Step 1 (Road Network Download) failed: {exc}", file=sys.stderr)
        sys.exit(1)

    # Step 2: Flood Overlay
    print("\n[STEP 2/4] Performing Flood Network Overlay...")
    try:
        overlay_stats = overlay_flood_on_network(
            edges_path=road_edges_gpkg,
            flood_mask_path=flood_mask,
            output_gpkg_path=flooded_gpkg,
            output_geojson_path=flooded_geojson,
        )
    except Exception as exc:
        print(f"\n[FATAL ERROR] Step 2 (Flood Overlay) failed: {exc}", file=sys.stderr)
        sys.exit(1)

    # Step 3: Connectivity Analysis
    print("\n[STEP 3/4] Evaluating Settlement Connectivity & Cut-Offs...")
    try:
        connectivity_stats = analyze_flood_connectivity(
            graph_path=graphml_path,
            flooded_edges_path=flooded_geojson,
            service_centers_path=service_centers_geojson,
            settlements_path=settlements_geojson,
            output_dir=base_output_dir,
            place_name=region,
            detour_threshold=detour_threshold,
        )
    except Exception as exc:
        print(f"\n[FATAL ERROR] Step 3 (Connectivity Analysis) failed: {exc}", file=sys.stderr)
        sys.exit(1)

    # Step 4: Priority Ranking
    print("\n[STEP 4/4] Ranking Rescue Priorities...")
    try:
        ranking_stats = rank_cutoff_settlements(
            cutoff_file=cutoff_json,
            connected_file=connected_json,
            graph_file=graphml_path,
            service_centers_file=service_centers_geojson,
            output_dir=base_output_dir,
        )
    except Exception as exc:
        print(f"\n[FATAL ERROR] Step 4 (Priority Ranking) failed: {exc}", file=sys.stderr)
        sys.exit(1)

    # Step 5: Formatted Pipeline Summary
    total_edges = overlay_stats.get("total_edges", 0)
    flooded_edges = overlay_stats.get("flooded_edges", 0)
    pct_flooded = overlay_stats.get("pct_flooded", 0.0)

    total_settlements = connectivity_stats.get("total_settlements", 0)
    strict_cutoff_count = connectivity_stats.get("strict_cutoff_count", 0)
    practical_cutoff_count = connectivity_stats.get("practical_cutoff_count", 0)
    connected_count = connectivity_stats.get("connected_count", 0)

    top_settlements = ranking_stats.get("top_5", [])[:3]

    print("\n" + "=" * 40)
    print("SAHAYAK PIPELINE COMPLETE")
    print("=" * 40)
    print(f"Flood Mask:        {flood_mask}")
    print(f"Flooded Edges:     {flooded_edges:,} ({pct_flooded:.2f}% of total)")
    print(f"Settlements:       {total_settlements:,}")
    print(f"- Strict Cut-offs: {strict_cutoff_count:,}")
    print(f"- Practical:       {practical_cutoff_count:,}")
    print(f"- Connected:       {connected_count:,}")
    print("")
    print("TOP PRIORITY SETTLEMENTS:")
    if top_settlements:
        for idx, item in enumerate(top_settlements, 1):
            s_name = item.get("name", "Unknown")
            s_type = item.get("type", "settlement")
            s_pop = item.get("population_est", 0)
            s_score = item.get("score", 0.0)
            s_cat = str(item.get("category", "HIGH")).upper()
            print(f"{idx}. {s_name} ({s_type}) — Pop: {s_pop} — Score: {s_score:.2f} — {s_cat}")
    else:
        print("No cut-off settlements identified (all settlements remain accessible).")

    print("")
    print(f"Outputs saved to: {base_output_dir}")
    print("=" * 40 + "\n")

    return {
        "overlay_stats": overlay_stats,
        "connectivity_stats": connectivity_stats,
        "ranking_stats": ranking_stats,
        "output_dir": base_output_dir,
    }


def main():
    parser = argparse.ArgumentParser(
        description="Sahayak Flood Mapper: End-to-end Graph Analysis Pipeline Runner"
    )
    parser.add_argument(
        "--flood-mask",
        required=True,
        type=str,
        help="Path to flood mask file (.geojson or .tif)",
    )
    parser.add_argument(
        "--region",
        type=str,
        default="Kamrup, Assam, India",
        help="Region name for road network download (default: 'Kamrup, Assam, India')",
    )
    parser.add_argument(
        "--detour-threshold",
        type=float,
        default=3.0,
        help="Detour ratio threshold for practical cut-off (default: 3.0)",
    )
    parser.add_argument(
        "--skip-download",
        action="store_true",
        help="Skip OSM network download if network.graphml already exists",
    )
    parser.add_argument(
        "--use-ml",
        action="store_true",
        help="Placeholder flag for future ML refinement integration",
    )
    parser.add_argument(
        "--output-dir",
        type=str,
        default=".",
        help="Directory to save generated outputs (default: current directory)",
    )

    args = parser.parse_args()

    try:
        run_pipeline(
            flood_mask_path=args.flood_mask,
            region=args.region,
            detour_threshold=args.detour_threshold,
            skip_download=args.skip_download,
            use_ml=args.use_ml,
            output_dir=args.output_dir,
        )
    except KeyboardInterrupt:
        print("\nPipeline execution cancelled by user.", file=sys.stderr)
        sys.exit(130)


if __name__ == "__main__":
    main()
