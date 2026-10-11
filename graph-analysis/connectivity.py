"""
Detect which settlements are cut off from service centers after road network flooding.
"""

import sys
import json
import argparse
from pathlib import Path
from typing import Dict, Any, List, Tuple
import geopandas as gpd
import pandas as pd
import networkx as nx
import osmnx as ox
from shapely.geometry import Point


# Configure OSMnx settings
ox.settings.use_cache = True
ox.settings.requests_timeout = 60
ox.settings.http_user_agent = "SahayakFloodMapper/1.0 (flood-analysis-tool; contact@sahayak.org)"


def load_or_fetch_service_centers(
    G: nx.MultiDiGraph,
    place_name: str = "Kamrup, Assam, India",
    cache_path: Path = None,
) -> gpd.GeoDataFrame:
    """
    Loads service centers (hospitals and towns) from local cache or queries OSM.
    """
    if cache_path and cache_path.exists():
        print(f"Loading service centers from local file: {cache_path.name}...")
        gdf = gpd.read_file(cache_path)
        if not gdf.empty:
            return gdf

    print("Querying OSM for service centers (amenity=hospital, place=town)...")
    tags = {"amenity": "hospital", "place": "town"}
    try:
        # Get bounding box from graph nodes
        nodes_gdf = ox.graph_to_gdfs(G, edges=False)
        minx, miny, maxx, maxy = nodes_gdf.total_bounds
        sc_gdf = ox.features_from_bbox((minx, miny, maxx, maxy), tags=tags)
    except Exception as exc:
        print(f"Bbox query failed ({exc}), attempting query by place name...")
        try:
            sc_gdf = ox.features_from_place(place_name, tags=tags)
        except Exception as e2:
            print(f"Warning: OSM service center query failed: {e2}")
            sc_gdf = gpd.GeoDataFrame(columns=["name", "amenity", "place", "geometry"], crs="EPSG:4326")

    # If successfully fetched, cache it
    if cache_path and not sc_gdf.empty:
        try:
            to_save = sc_gdf.copy()
            for col in to_save.columns:
                if col != "geometry" and to_save[col].apply(lambda x: isinstance(x, list)).any():
                    to_save[col] = to_save[col].astype(str)
            to_save.to_file(cache_path, driver="GeoJSON")
            print(f"Cached service centers to: {cache_path.name}")
        except Exception as save_err:
            print(f"Warning: Failed to cache service centers: {save_err}")

    return sc_gdf


def load_or_fetch_settlements(
    G: nx.MultiDiGraph,
    place_name: str = "Kamrup, Assam, India",
    cache_path: Path = None,
) -> gpd.GeoDataFrame:
    """
    Loads settlements (villages, hamlets, towns) from local cache or queries OSM.
    """
    if cache_path and cache_path.exists():
        print(f"Loading settlements from local file: {cache_path.name}...")
        gdf = gpd.read_file(cache_path)
        if not gdf.empty:
            return gdf

    print("Querying OSM for settlements (place=village, hamlet, town)...")
    tags = {"place": ["village", "hamlet", "town"]}
    try:
        nodes_gdf = ox.graph_to_gdfs(G, edges=False)
        minx, miny, maxx, maxy = nodes_gdf.total_bounds
        st_gdf = ox.features_from_bbox((minx, miny, maxx, maxy), tags=tags)
    except Exception as exc:
        print(f"Bbox query failed ({exc}), attempting query by place name...")
        try:
            st_gdf = ox.features_from_place(place_name, tags=tags)
        except Exception as e2:
            print(f"Warning: OSM settlement query failed: {e2}")
            st_gdf = gpd.GeoDataFrame(columns=["name", "place", "geometry"], crs="EPSG:4326")

    # If successfully fetched, cache it
    if cache_path and not st_gdf.empty:
        try:
            to_save = st_gdf.copy()
            for col in to_save.columns:
                if col != "geometry" and to_save[col].apply(lambda x: isinstance(x, list)).any():
                    to_save[col] = to_save[col].astype(str)
            to_save.to_file(cache_path, driver="GeoJSON")
            print(f"Cached settlements to: {cache_path.name}")
        except Exception as save_err:
            print(f"Warning: Failed to cache settlements: {save_err}")

    return st_gdf


def analyze_flood_connectivity(
    graph_path: Path = None,
    flooded_edges_path: Path = None,
    service_centers_path: Path = None,
    settlements_path: Path = None,
    output_dir: Path = None,
    place_name: str = "Kamrup, Assam, India",
) -> Dict[str, Any]:
    """
    Removes flooded road edges from the road graph and analyzes path reachability
    from settlements to service centers.
    """
    base_dir = Path(__file__).resolve().parent

    graph_path = Path(graph_path or base_dir / "network.graphml").resolve()
    flooded_edges_path = Path(flooded_edges_path or base_dir / "flooded_edges.geojson").resolve()
    service_centers_path = Path(service_centers_path or base_dir / "service_centers.geojson").resolve()
    settlements_path = Path(settlements_path or base_dir / "settlements.geojson").resolve()
    output_dir = Path(output_dir or base_dir).resolve()

    output_dir.mkdir(parents=True, exist_ok=True)
    connected_output_file = output_dir / "connected_settlements.json"
    cutoff_output_file = output_dir / "cut_off_settlements.json"

    # 1. Load road network
    if not graph_path.exists():
        raise FileNotFoundError(f"Road network GraphML not found at: {graph_path}")
    print(f"Loading road network from: {graph_path.name}...")
    G = ox.load_graphml(graph_path)
    total_nodes = len(G.nodes)
    total_edges = len(G.edges)
    print(f"Network loaded: {total_nodes:,} nodes, {total_edges:,} edges.")

    # 2. Load flooded edges
    flooded_edges_gdf = gpd.GeoDataFrame()
    if flooded_edges_path.exists():
        print(f"Loading flooded edges from: {flooded_edges_path.name}...")
        flooded_edges_gdf = gpd.read_file(flooded_edges_path)
        print(f"Flooded edges recorded: {len(flooded_edges_gdf):,}")
    else:
        print(f"Notice: Flooded edges file not found at {flooded_edges_path}. Assuming no edges flooded.")

    # 3. Create graph copy and remove flooded edges
    print("Creating graph copy and removing submerged road edges...")
    G_flood = G.copy()
    removed_count = 0

    if not flooded_edges_gdf.empty:
        has_uv = "u" in flooded_edges_gdf.columns and "v" in flooded_edges_gdf.columns
        for _, row in flooded_edges_gdf.iterrows():
            if has_uv and pd.notna(row["u"]) and pd.notna(row["v"]):
                u = int(row["u"])
                v = int(row["v"])
                key = int(row["key"]) if ("key" in row and pd.notna(row["key"])) else 0

                if G_flood.has_edge(u, v, key):
                    G_flood.remove_edge(u, v, key)
                    removed_count += 1
                elif G_flood.has_edge(u, v):
                    # In case key differs, remove any existing edge between u and v
                    G_flood.remove_edge(u, v)
                    removed_count += 1

    print(f"Submerged edges removed from network: {removed_count:,} (remaining edges: {len(G_flood.edges):,})")

    # 4. Service centers
    sc_gdf = load_or_fetch_service_centers(G, place_name=place_name, cache_path=service_centers_path)
    if sc_gdf.empty:
        print("[WARNING] No service centers identified! All settlements will be marked cut-off.")
    else:
        print(f"Loaded {len(sc_gdf)} service center facilities.")

    # 5. Settlements
    st_gdf = load_or_fetch_settlements(G, place_name=place_name, cache_path=settlements_path)
    if st_gdf.empty:
        print("[WARNING] No settlements identified in target region!")
    else:
        print(f"Loaded {len(st_gdf)} settlements.")

    # Handle edge case: empty settlements
    if st_gdf.empty:
        print("No settlements to evaluate.")
        with open(connected_output_file, "w", encoding="utf-8") as f:
            json.dump([], f, indent=2)
        with open(cutoff_output_file, "w", encoding="utf-8") as f:
            json.dump([], f, indent=2)

        return {
            "total_settlements": 0,
            "connected_count": 0,
            "cutoff_count": 0,
            "pct_cutoff": 0.0,
            "connected_file": connected_output_file,
            "cutoff_file": cutoff_output_file,
        }

    # Extract centroids for coordinate lookups
    sc_points = [geom.centroid for geom in sc_gdf.geometry] if not sc_gdf.empty else []
    st_points = [geom.centroid for geom in st_gdf.geometry]

    # Map facilities to nearest graph nodes
    sc_node_map: Dict[int, Dict[str, Any]] = {}
    if sc_points:
        sc_node_ids = ox.nearest_nodes(G, [p.x for p in sc_points], [p.y for p in sc_points])
        for idx, (node_id, row) in enumerate(zip(sc_node_ids, sc_gdf.itertuples())):
            name = getattr(row, "name", None) or f"ServiceCenter_{getattr(row, 'osmid', idx)}"
            facility_type = getattr(row, "amenity", None) or getattr(row, "place", "facility")
            sc_node_map[node_id] = {
                "name": str(name),
                "type": str(facility_type),
                "x": sc_points[idx].x,
                "y": sc_points[idx].y,
            }
        print(f"Mapped service centers to {len(sc_node_map)} unique network nodes.")

    # Map settlements to nearest graph nodes
    st_node_ids = ox.nearest_nodes(G, [p.x for p in st_points], [p.y for p in st_points])

    # 6. Evaluate connectivity using networkx.has_path & shortest_path
    print("Evaluating path connectivity to service centers for each settlement...")
    connected_settlements = []
    cutoff_settlements = []

    service_node_list = list(sc_node_map.keys())

    for idx, (st_node, row) in enumerate(zip(st_node_ids, st_gdf.itertuples())):
        st_id = getattr(row, "osmid", idx)
        st_name = getattr(row, "name", None) or f"Settlement_{st_id}"
        place_type = getattr(row, "place", "settlement")
        coord_x = st_points[idx].x
        coord_y = st_points[idx].y

        settlement_entry = {
            "id": int(st_id) if str(st_id).isdigit() else str(st_id),
            "name": str(st_name),
            "place_type": str(place_type),
            "latitude": float(coord_y),
            "longitude": float(coord_x),
            "nearest_graph_node": int(st_node),
        }

        # Check if settlement node still exists in post-flood network
        if st_node not in G_flood or not service_node_list:
            settlement_entry["reason"] = "Node isolated or no service centers"
            cutoff_settlements.append(settlement_entry)
            continue

        best_distance = float("inf")
        nearest_sc_info = None

        # Check path reachability to any service center
        for sc_node in service_node_list:
            if sc_node not in G_flood:
                continue

            try:
                # Check path existence
                if nx.has_path(G_flood, st_node, sc_node):
                    # Compute shortest path with weight='length'
                    path_length = nx.shortest_path_length(
                        G_flood, source=st_node, target=sc_node, weight="length"
                    )
                    if path_length < best_distance:
                        best_distance = path_length
                        path = nx.shortest_path(
                            G_flood, source=st_node, target=sc_node, weight="length"
                        )
                        nearest_sc_info = {
                            "node": int(sc_node),
                            "name": sc_node_map[sc_node]["name"],
                            "type": sc_node_map[sc_node]["type"],
                            "path_nodes_count": len(path),
                        }
            except (nx.NetworkXNoPath, nx.NodeNotFound):
                continue
            except Exception as path_err:
                # Fallback for unexpected path error
                continue

        if nearest_sc_info is not None:
            dist_km = round(best_distance / 1000.0, 2)
            settlement_entry["nearest_service_center"] = nearest_sc_info
            settlement_entry["shortest_distance_km"] = dist_km
            settlement_entry["shortest_distance_meters"] = round(best_distance, 1)
            connected_settlements.append(settlement_entry)
        else:
            settlement_entry["reason"] = "All road routes to service centers submerged"
            cutoff_settlements.append(settlement_entry)

    # 7. Output results to JSON
    with open(connected_output_file, "w", encoding="utf-8") as f:
        json.dump(connected_settlements, f, indent=2, ensure_ascii=False)
    print(f"\nSaved connected settlements ({len(connected_settlements)}): {connected_output_file.name}")

    with open(cutoff_output_file, "w", encoding="utf-8") as f:
        json.dump(cutoff_settlements, f, indent=2, ensure_ascii=False)
    print(f"Saved cut-off settlements ({len(cutoff_settlements)}): {cutoff_output_file.name}")

    # 8. Print statistics
    total_st = len(st_gdf)
    conn_count = len(connected_settlements)
    cutoff_count = len(cutoff_settlements)
    pct_cutoff = (cutoff_count / total_st * 100.0) if total_st > 0 else 0.0

    print("\n" + "=" * 45)
    print("SETTLEMENT CONNECTIVITY ANALYSIS")
    print("=" * 45)
    print(f"Total Settlements:    {total_st:,}")
    print(f"Connected:            {conn_count:,}")
    print(f"Cut-off (Critical!):  {cutoff_count:,}")
    print(f"Cut-off Percentage:   {pct_cutoff:.2f}%")
    print("=" * 45)

    if cutoff_settlements:
        print("\nCRITICAL: Submerged / Cut-off Settlements List:")
        for idx, item in enumerate(cutoff_settlements, 1):
            print(f" {idx}. {item['name']} ({item['place_type']}) - Lat: {item['latitude']:.4f}, Lon: {item['longitude']:.4f}")

    return {
        "total_settlements": total_st,
        "connected_count": conn_count,
        "cutoff_count": cutoff_count,
        "pct_cutoff": pct_cutoff,
        "connected_file": connected_output_file,
        "cutoff_file": cutoff_output_file,
    }


def main():
    parser = argparse.ArgumentParser(
        description="Detect which settlements are cut off from service centers after flood events."
    )
    parser.add_argument(
        "--graph",
        type=str,
        default=None,
        help="Path to network.graphml (default: network.graphml in script folder)",
    )
    parser.add_argument(
        "--flooded-edges",
        type=str,
        default=None,
        help="Path to flooded_edges.geojson (default: flooded_edges.geojson in script folder)",
    )
    parser.add_argument(
        "--service-centers",
        type=str,
        default=None,
        help="Path to service_centers.geojson (default: service_centers.geojson in script folder)",
    )
    parser.add_argument(
        "--settlements",
        type=str,
        default=None,
        help="Path to settlements.geojson (default: settlements.geojson in script folder)",
    )
    parser.add_argument(
        "--output-dir",
        type=str,
        default=None,
        help="Output folder for JSON files (default: script folder)",
    )
    parser.add_argument(
        "--place",
        type=str,
        default="Kamrup, Assam, India",
        help="Target region place name (default: 'Kamrup, Assam, India')",
    )

    args = parser.parse_args()

    try:
        analyze_flood_connectivity(
            graph_path=args.graph,
            flooded_edges_path=args.flooded_edges,
            service_centers_path=args.service_centers,
            settlements_path=args.settlements,
            output_dir=args.output_dir,
            place_name=args.place,
        )
    except KeyboardInterrupt:
        print("\nOperation cancelled by user.", file=sys.stderr)
        sys.exit(130)
    except Exception as exc:
        print(f"\n[ERROR] Connectivity analysis failed: {exc}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
