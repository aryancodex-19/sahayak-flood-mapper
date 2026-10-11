"""
Rank cut-off settlements by rescue priority after flood road network disruptions.
"""

import sys
import json
import math
import argparse
from pathlib import Path
from typing import Dict, Any, List, Tuple
import pandas as pd
import geopandas as gpd
from shapely.geometry import Point
import networkx as nx
import osmnx as ox


# Population estimates based on settlement classification
POPULATION_MAP = {
    "town": 5000,
    "suburb": 3000,
    "neighbourhood": 1500,
    "village": 800,
    "locality": 1000,
    "hamlet": 200,
}


def haversine_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Calculates great-circle distance between two points in kilometers."""
    r = 6371.0  # Earth's radius in km
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    delta_phi = math.radians(lat2 - lat1)
    delta_lambda = math.radians(lon2 - lon1)

    a = (
        math.sin(delta_phi / 2.0) ** 2
        + math.cos(phi1) * math.cos(phi2) * math.sin(delta_lambda / 2.0) ** 2
    )
    c = 2.0 * math.atan2(math.sqrt(a), math.sqrt(1.0 - a))
    return r * c


def get_population_estimate(item: Dict[str, Any]) -> int:
    """Extracts or estimates population for a settlement."""
    pop = item.get("population")
    if pop is not None:
        try:
            val = int(pop)
            if val > 0:
                return val
        except (ValueError, TypeError):
            pass

    place_type = str(item.get("place_type") or item.get("type", "village")).lower().strip()
    return POPULATION_MAP.get(place_type, 800)


def compute_settlement_distance_to_service_center(
    settlement: Dict[str, Any],
    G: nx.MultiDiGraph = None,
    service_node_ids: set = None,
    service_center_coords: List[Tuple[float, float]] = None,
) -> float:
    """
    Computes distance in km from cut-off settlement to nearest service center.
    Uses pre-flood graph distance if path exists; otherwise Haversine straight-line distance.
    """
    st_node = settlement.get("nearest_graph_node")
    lat = settlement.get("latitude")
    lon = settlement.get("longitude")

    # 1. Try pre-flood road distance via network graph if available
    if G is not None and st_node is not None and service_node_ids and st_node in G:
        try:
            lengths = nx.single_source_dijkstra_path_length(G, st_node, weight="length")
            valid_dists = [lengths[sc] for sc in service_node_ids if sc in lengths]
            if valid_dists:
                return min(valid_dists) / 1000.0  # Convert meters to km
        except Exception:
            pass

    # 2. Straight-line geodesic distance fallback
    if service_center_coords and lat is not None and lon is not None:
        min_line_dist = min(
            haversine_distance(lat, lon, sc_lat, sc_lon)
            for sc_lat, sc_lon in service_center_coords
        )
        return min_line_dist

    # Default fallback distance
    return settlement.get("shortest_distance_km", 5.0)


def rank_cutoff_settlements(
    cutoff_file: Path = None,
    connected_file: Path = None,
    graph_file: Path = None,
    service_centers_file: Path = None,
    output_dir: Path = None,
) -> Dict[str, Any]:
    """
    Ranks cut-off settlements based on estimated population and distance to service centers.
    """
    base_dir = Path(__file__).resolve().parent

    cutoff_file = Path(cutoff_file or base_dir / "cut_off_settlements.json").resolve()
    connected_file = Path(connected_file or base_dir / "connected_settlements.json").resolve()
    graph_file = Path(graph_file or base_dir / "network.graphml").resolve()
    service_centers_file = Path(service_centers_file or base_dir / "service_centers.geojson").resolve()
    output_dir = Path(output_dir or base_dir).resolve()

    output_dir.mkdir(parents=True, exist_ok=True)
    csv_output_path = output_dir / "priority_list.csv"
    geojson_output_path = output_dir / "priority_list.geojson"

    # 1. Load cut-off settlements
    if not cutoff_file.exists():
        raise FileNotFoundError(f"Cut-off settlements file not found: {cutoff_file}")

    print(f"Loading cut-off settlements from: {cutoff_file.name}...")
    with open(cutoff_file, "r", encoding="utf-8") as f:
        cutoff_data = json.load(f)
    print(f"Loaded {len(cutoff_data)} cut-off settlements.")

    # 2. Load connected settlements (context for distance scaling)
    connected_data = []
    connected_distances = []
    if connected_file.exists():
        print(f"Loading connected settlements from: {connected_file.name}...")
        try:
            with open(connected_file, "r", encoding="utf-8") as f:
                connected_data = json.load(f)
            connected_distances = [
                c.get("shortest_distance_km", 0.0)
                for c in connected_data
                if c.get("shortest_distance_km") is not None
            ]
            print(f"Loaded {len(connected_data)} connected settlements (context reference).")
        except Exception as e:
            print(f"Notice: Failed to parse connected settlements: {e}")

    # Handle empty cut-off settlements edge case
    if not cutoff_data:
        print("[INFO] No cut-off settlements found. Outputting empty priority files.")
        empty_df = pd.DataFrame(columns=[
            "rank", "name", "type", "population_est", "lat", "lon", "score", "category", "reason"
        ])
        empty_df.to_csv(csv_output_path, index=False)
        empty_gdf = gpd.GeoDataFrame(columns=[
            "rank", "name", "type", "population_est", "lat", "lon", "score", "category", "reason", "geometry"
        ], crs="EPSG:4326")
        empty_gdf.to_file(geojson_output_path, driver="GeoJSON")
        return {"total_ranked": 0, "csv_path": csv_output_path, "geojson_path": geojson_output_path}

    # 3. Load pre-flood graph & service centers if available
    G = None
    if graph_file.exists():
        try:
            G = ox.load_graphml(graph_file)
        except Exception:
            pass

    service_node_ids = set()
    service_center_coords = []

    # Extract service centers from connected settlements or service_centers.geojson
    if service_centers_file.exists():
        try:
            sc_gdf = gpd.read_file(service_centers_file)
            for geom in sc_gdf.geometry:
                p = geom.centroid
                service_center_coords.append((p.y, p.x))
        except Exception:
            pass

    for c in connected_data:
        sc_info = c.get("nearest_service_center", {})
        if "node" in sc_info:
            service_node_ids.add(sc_info["node"])

    # 4. Compute metrics for cut-off settlements
    processed = []
    for item in cutoff_data:
        name = item.get("name", "Unknown")
        p_type = item.get("place_type") or item.get("type", "village")
        lat = float(item.get("latitude", 0.0))
        lon = float(item.get("longitude", 0.0))
        pop_est = get_population_estimate(item)

        dist_km = compute_settlement_distance_to_service_center(
            item,
            G=G,
            service_node_ids=service_node_ids,
            service_center_coords=service_center_coords,
        )

        processed.append({
            "id": item.get("id"),
            "name": name,
            "type": p_type,
            "population_est": pop_est,
            "lat": lat,
            "lon": lon,
            "distance_km": dist_km,
        })

    # 5. Normalization (0-100 scale)
    # Population bounds: standard range [200, 5000]
    pop_values = [p["population_est"] for p in processed]
    min_pop = min(200, min(pop_values))
    max_pop = max(5000, max(pop_values))

    # Distance bounds: based on regional context from connected and cutoff settlements
    all_dists = [p["distance_km"] for p in processed] + connected_distances
    min_dist = 0.0
    max_dist = max(all_dists) if all_dists and max(all_dists) > 0 else 10.0

    for p in processed:
        # Normalize population (0 - 100)
        if max_pop > min_pop:
            norm_pop = ((p["population_est"] - min_pop) / (max_pop - min_pop)) * 100.0
        else:
            norm_pop = 50.0

        # Normalize distance (0 - 100)
        if max_dist > min_dist:
            norm_dist = ((p["distance_km"] - min_dist) / (max_dist - min_dist)) * 100.0
        else:
            norm_dist = 50.0

        # Score formula: 40 + (0.4 * normalized_population) + (0.2 * normalized_distance)
        # Ensures cut-off settlements score between 40-100
        score = 40.0 + (0.4 * norm_pop) + (0.2 * norm_dist)
        score_clamped = max(40.0, min(100.0, score))
        score_rounded = round(score_clamped, 2)

        # Categorize cut-off settlements:
        # Critical (>80), High (60-80), Medium (40-60)
        if score_rounded > 80.0:
            category = "Critical"
        elif score_rounded >= 60.0:
            category = "High"
        else:
            category = "Medium"

        reason = (
            f"Cut off from all service centers; "
            f"estimated population {p['population_est']}; "
            f"nearest service center {p['distance_km']:.2f}km away"
        )

        p["score"] = score_rounded
        p["category"] = category
        p["reason"] = reason

    # 6. Rank settlements (highest priority first)
    processed.sort(key=lambda x: -x["score"])
    for rank_idx, item in enumerate(processed, 1):
        item["rank"] = rank_idx

    # 7. Save priority_list.csv
    csv_rows = [
        {
            "rank": item["rank"],
            "name": item["name"],
            "type": item["type"],
            "population_est": item["population_est"],
            "lat": item["lat"],
            "lon": item["lon"],
            "score": item["score"],
            "category": item["category"],
            "reason": item["reason"],
        }
        for item in processed
    ]
    df = pd.DataFrame(csv_rows)
    df.to_csv(csv_output_path, index=False, encoding="utf-8")
    print(f"\nSaved priority list CSV ({len(df)} records): {csv_output_path.name}")

    # Save priority_list.geojson
    gdf_features = []
    for item in processed:
        gdf_features.append({
            "rank": item["rank"],
            "name": item["name"],
            "type": item["type"],
            "population_est": item["population_est"],
            "distance_km": round(item["distance_km"], 2),
            "lat": item["lat"],
            "lon": item["lon"],
            "score": item["score"],
            "category": item["category"],
            "reason": item["reason"],
            "geometry": Point(item["lon"], item["lat"]),
        })
    gdf = gpd.GeoDataFrame(gdf_features, crs="EPSG:4326")
    gdf.to_file(geojson_output_path, driver="GeoJSON")
    print(f"Saved priority list GeoJSON: {geojson_output_path.name}")

    # 8. Print top 5 priority settlements
    print("\n" + "=" * 75)
    print("TOP PRIORITY CUT-OFF SETTLEMENTS (RESCUE RANKING)")
    print("=" * 75)
    header = f"{'Rank':<5} | {'Settlement':<16} | {'Type':<9} | {'Pop Est':<7} | {'Score':<6} | {'Category':<8} | Reason"
    print(header)
    print("-" * 75)
    for item in processed[:5]:
        row_str = (
            f"{item['rank']:<5} | "
            f"{item['name'][:16]:<16} | "
            f"{item['type'][:9]:<9} | "
            f"{item['population_est']:<7} | "
            f"{item['score']:<6.2f} | "
            f"{item['category']:<8} | "
            f"{item['reason']}"
        )
        print(row_str)
    print("=" * 75)

    return {
        "total_ranked": len(processed),
        "csv_path": csv_output_path,
        "geojson_path": geojson_output_path,
        "top_5": processed[:5],
    }


def main():
    parser = argparse.ArgumentParser(
        description="Rank cut-off settlements by rescue priority based on population and service distance."
    )
    parser.add_argument(
        "--cutoff",
        type=str,
        default=None,
        help="Path to cut_off_settlements.json (default: cut_off_settlements.json in script folder)",
    )
    parser.add_argument(
        "--connected",
        type=str,
        default=None,
        help="Path to connected_settlements.json (default: connected_settlements.json in script folder)",
    )
    parser.add_argument(
        "--graph",
        type=str,
        default=None,
        help="Path to network.graphml (default: network.graphml in script folder)",
    )
    parser.add_argument(
        "--service-centers",
        type=str,
        default=None,
        help="Path to service_centers.geojson (default: service_centers.geojson in script folder)",
    )
    parser.add_argument(
        "--output-dir",
        type=str,
        default=None,
        help="Output folder for CSV and GeoJSON results (default: script folder)",
    )

    args = parser.parse_args()

    try:
        rank_cutoff_settlements(
            cutoff_file=args.cutoff,
            connected_file=args.connected,
            graph_file=args.graph,
            service_centers_file=args.service_centers,
            output_dir=args.output_dir,
        )
    except KeyboardInterrupt:
        print("\nOperation cancelled by user.", file=sys.stderr)
        sys.exit(130)
    except Exception as exc:
        print(f"\n[ERROR] Priority ranking failed: {exc}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
