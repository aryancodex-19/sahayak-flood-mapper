"""
Detect which settlements are cut off from service centers after road network flooding.
"""

import sys
import json
import argparse
from pathlib import Path
from collections import Counter
from typing import Dict, Any, List
import requests
import geopandas as gpd
import pandas as pd
import networkx as nx
import osmnx as ox
from shapely.geometry import Point

# Ensure UTF-8 output encoding on Windows console
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass


# Configure OSMnx settings
ox.settings.use_cache = True
ox.settings.requests_timeout = 180
ox.settings.http_user_agent = "SahayakFloodMapper/1.0 (flood-analysis-tool; contact@sahayak.org)"

OVERPASS_ENDPOINTS = [
    "https://lz4.overpass-api.de/api/interpreter",
    "https://overpass-api.de/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter",
    "https://overpass.private.coffee/api/interpreter",
]

EXPANDED_PLACE_TYPES = [
    "village",
    "hamlet",
    "town",
    "suburb",
    "neighbourhood",
    "locality",
]


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
    sc_gdf = gpd.GeoDataFrame()

    nodes_gdf = ox.graph_to_gdfs(G, edges=False)
    minx, miny, maxx, maxy = nodes_gdf.total_bounds

    for endpoint in OVERPASS_ENDPOINTS:
        try:
            ox.settings.overpass_url = endpoint.replace("/interpreter", "")
            sc_gdf = ox.features_from_bbox((minx, miny, maxx, maxy), tags=tags)
            if not sc_gdf.empty:
                break
        except Exception:
            continue

    if sc_gdf.empty:
        try:
            sc_gdf = ox.features_from_place(place_name, tags=tags)
        except Exception as e2:
            print(f"Warning: OSM service center query failed: {e2}")
            sc_gdf = gpd.GeoDataFrame(columns=["name", "amenity", "place", "geometry"], crs="EPSG:4326")

    # Cache if found
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


def _query_overpass_elements(s: float, w: float, n: float, e: float) -> List[Dict[str, Any]]:
    """Helper to query Overpass for expanded settlement place tags."""
    headers = {"User-Agent": "SahayakFloodMapper/1.0 (contact@sahayak.org)"}
    lines = [f'  node["place"="{p}"]({s},{w},{n},{e});' for p in EXPANDED_PLACE_TYPES]
    body = "\n".join(lines)
    query = f"""[out:json][timeout:180];
(
{body}
);
out body;"""

    for ep in OVERPASS_ENDPOINTS:
        try:
            print(f"Querying {ep} (timeout=30s)...", flush=True)
            resp = requests.post(ep, data={"data": query}, headers=headers, timeout=30)
            if resp.status_code == 200:
                data = resp.json()
                elements = data.get("elements", [])
                if elements:
                    print(f" -> Success from {ep}: {len(elements)} elements", flush=True)
                    return elements
            else:
                print(f" -> {ep} returned status {resp.status_code}", flush=True)
        except Exception as exc:
            print(f" -> {ep} request failed: {exc}", flush=True)
            continue
    return []


def _query_overpass_chunked(s: float, w: float, n: float, e: float) -> List[Dict[str, Any]]:
    """Splits bounding box into 4 spatial quadrants to prevent server timeouts."""
    lat_mid = (s + n) / 2.0
    lon_mid = (w + e) / 2.0
    quadrants = [
        ("SW", s, w, lat_mid, lon_mid),
        ("SE", s, lon_mid, lat_mid, e),
        ("NW", lat_mid, w, n, lon_mid),
        ("NE", lat_mid, lon_mid, n, e),
    ]

    all_elements = []
    seen_ids = set()

    for name, qs, qw, qn, qe in quadrants:
        print(f"Querying quadrant {name}...", flush=True)
        elements = _query_overpass_elements(qs, qw, qn, qe)
        for el in elements:
            el_id = el.get("id")
            if el_id not in seen_ids:
                seen_ids.add(el_id)
                all_elements.append(el)

    return all_elements


def load_or_fetch_settlements(
    G: nx.MultiDiGraph,
    place_name: str = "Kamrup, Assam, India",
    cache_path: Path = None,
    buffer_deg: float = 0.07,
    force_refresh: bool = False,
) -> gpd.GeoDataFrame:
    """
    Loads settlements from local cache or queries OSM Overpass with expanded place tags,
    buffered bounding box, chunking, and OSMnx fallback to ensure 100+ settlements.
    """
    if cache_path and cache_path.exists() and not force_refresh:
        gdf = gpd.read_file(cache_path)
        if len(gdf) >= 100:
            print(f"Loading settlements from local file ({len(gdf)} settlements): {cache_path.name}...")
            _print_settlement_breakdown(gdf)
            return gdf
        else:
            print(f"Cached settlements file has only {len(gdf)} entries (< 100). Refreshing from OSM...")

    # Calculate buffered bounding box (at least 0.05 to 0.07 degree buffer)
    nodes_gdf = ox.graph_to_gdfs(G, edges=False)
    minx, miny, maxx, maxy = nodes_gdf.total_bounds
    s = miny - buffer_deg
    w = minx - buffer_deg
    n = maxy + buffer_deg
    e = maxx + buffer_deg

    print(f"\nExpanded search bounds (buffer={buffer_deg}°):")
    print(f" South: {s:.4f}, West: {w:.4f}, North: {n:.4f}, East: {e:.4f}")
    print(f"Target place types: {', '.join(EXPANDED_PLACE_TYPES)}")

    elements = []
    # Attempt 1: Overpass API direct query with buffer
    print("1. Querying Overpass API for all expanded place types...")
    elements = _query_overpass_elements(s, w, n, e)

    # Attempt 2: If < 50, try chunked queries
    if len(elements) < 50:
        print(f"Direct query returned {len(elements)} elements (< 50). Trying spatial quadrant chunking...")
        elements = _query_overpass_chunked(s, w, n, e)

    # Attempt 3: Fallback using OSMnx features_from_bbox() if < 50
    st_gdf = gpd.GeoDataFrame()
    if len(elements) < 50:
        print(f"Overpass returned {len(elements)} settlements. Triggering OSMnx features_from_bbox fallback...")
        fallback_tags = {"place": ["village", "hamlet", "town", "suburb"]}
        try:
            st_gdf = ox.features_from_bbox((w, s, e, n), tags=fallback_tags)
            print(f"OSMnx features_from_bbox fallback retrieved {len(st_gdf)} features.")
        except Exception as ox_err:
            print(f"OSMnx fallback query error: {ox_err}")

    # Convert Overpass elements to GeoDataFrame if available
    if elements:
        rows = []
        for el in elements:
            tags = el.get("tags", {})
            lat = el.get("lat") or el.get("center", {}).get("lat")
            lon = el.get("lon") or el.get("center", {}).get("lon")
            if lat is not None and lon is not None:
                rows.append({
                    "osmid": el.get("id"),
                    "name": tags.get("name", f"Settlement_{el.get('id')}"),
                    "place": tags.get("place", "village"),
                    "geometry": Point(lon, lat),
                })
        overpass_gdf = gpd.GeoDataFrame(rows, crs="EPSG:4326")
        if len(overpass_gdf) > len(st_gdf):
            st_gdf = overpass_gdf

    if st_gdf.empty:
        print("[WARNING] Could not retrieve settlements. Creating empty dataset.")
        return gpd.GeoDataFrame(columns=["name", "place", "geometry"], crs="EPSG:4326")

    # Display stats breakdown
    _print_settlement_breakdown(st_gdf)

    # Cache results to settlements.geojson so re-runs don't re-query
    if cache_path:
        try:
            to_save = st_gdf.copy()
            for col in to_save.columns:
                if col != "geometry" and to_save[col].apply(lambda x: isinstance(x, list)).any():
                    to_save[col] = to_save[col].astype(str)
            to_save.to_file(cache_path, driver="GeoJSON")
            print(f"Cached {len(st_gdf)} settlements to: {cache_path.name}")
        except Exception as save_err:
            print(f"Warning: Failed to cache settlements: {save_err}")

    return st_gdf


def _print_settlement_breakdown(gdf: gpd.GeoDataFrame):
    """Prints statistics of settlement place types."""
    print("\n" + "-" * 40)
    print("SETTLEMENT TYPES BREAKDOWN")
    print("-" * 40)
    print(f"Total Settlements: {len(gdf):,}")
    if "place" in gdf.columns:
        counts = gdf["place"].value_counts()
        for p_type, count in counts.items():
            print(f" - {p_type.capitalize():15s}: {count:,}")
    print("-" * 40)


def analyze_flood_connectivity(
    graph_path: Path = None,
    flooded_edges_path: Path = None,
    service_centers_path: Path = None,
    settlements_path: Path = None,
    output_dir: Path = None,
    place_name: str = "Kamrup, Assam, India",
    force_refresh_settlements: bool = False,
    detour_threshold: float = 3.0,
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
    practical_output_file = output_dir / "practical_cut_off_settlements.json"

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
                    G_flood.remove_edge(u, v)
                    removed_count += 1

    print(f"Submerged edges removed from network: {removed_count:,} (remaining edges: {len(G_flood.edges):,})")

    # 4. Service centers
    sc_gdf = load_or_fetch_service_centers(G, place_name=place_name, cache_path=service_centers_path)
    if sc_gdf.empty:
        print("[WARNING] No service centers identified! All settlements will be marked cut-off.")
    else:
        print(f"Loaded {len(sc_gdf)} service center facilities.")

    # 5. Settlements (with 0.05+ degree buffer, expanded place tags, fallback & caching)
    st_gdf = load_or_fetch_settlements(
        G,
        place_name=place_name,
        cache_path=settlements_path,
        buffer_deg=0.07,
        force_refresh=force_refresh_settlements,
    )

    if st_gdf.empty:
        print("No settlements to evaluate.")
        with open(connected_output_file, "w", encoding="utf-8") as f:
            json.dump([], f, indent=2)
        with open(cutoff_output_file, "w", encoding="utf-8") as f:
            json.dump([], f, indent=2)
        with open(practical_output_file, "w", encoding="utf-8") as f:
            json.dump([], f, indent=2)

        return {
            "total_settlements": 0,
            "connected_count": 0,
            "strict_cutoff_count": 0,
            "practical_cutoff_count": 0,
            "connected_file": connected_output_file,
            "cutoff_file": cutoff_output_file,
            "practical_cutoff_file": practical_output_file,
        }

    # Extract centroids
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

    # 6. Evaluate connectivity (Strict vs Practical vs Connected)
    print("Evaluating pre-flood vs post-flood reachability to service centers...")
    connected_settlements = []
    strict_cutoff_settlements = []
    practical_cutoff_settlements = []
    skipped_settlements = []

    service_node_list = list(sc_node_map.keys())
    detour_threshold = float(detour_threshold if detour_threshold is not None else 3.0)

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

        # Step A: Evaluate pre-flood shortest path on original G
        if st_node not in G or not service_node_list:
            skipped_settlements.append(st_name)
            continue

        try:
            orig_lengths, orig_paths = nx.single_source_dijkstra(G, source=st_node, weight="length")
            valid_sc_orig = [sc for sc in service_node_list if sc in orig_lengths]
            if not valid_sc_orig:
                # No path even before flood, skip settlement
                skipped_settlements.append(st_name)
                continue
            best_orig_sc = min(valid_sc_orig, key=lambda sc: orig_lengths[sc])
            pre_flood_dist = orig_lengths[best_orig_sc]
        except (nx.NetworkXNoPath, nx.NodeNotFound):
            skipped_settlements.append(st_name)
            continue

        # Step B: Evaluate post-flood shortest path on G_flood
        if st_node not in G_flood:
            # Node completely removed or isolated
            settlement_entry["reason"] = "Strict cut-off: settlement node isolated by flood"
            settlement_entry["pre_flood_distance_km"] = round(pre_flood_dist / 1000.0, 2)
            strict_cutoff_settlements.append(settlement_entry)
            continue

        try:
            flood_lengths, flood_paths = nx.single_source_dijkstra(G_flood, source=st_node, weight="length")
            valid_sc_flood = [sc for sc in service_node_list if sc in flood_lengths]
            if not valid_sc_flood:
                # Strict cut-off: no path exists to ANY service center
                settlement_entry["reason"] = "Strict cut-off: all road routes to service centers submerged"
                settlement_entry["pre_flood_distance_km"] = round(pre_flood_dist / 1000.0, 2)
                strict_cutoff_settlements.append(settlement_entry)
                continue

            best_flood_sc = min(valid_sc_flood, key=lambda sc: flood_lengths[sc])
            post_flood_dist = flood_lengths[best_flood_sc]
            post_flood_path = flood_paths[best_flood_sc]
        except (nx.NetworkXNoPath, nx.NodeNotFound):
            settlement_entry["reason"] = "Strict cut-off: all road routes to service centers submerged"
            settlement_entry["pre_flood_distance_km"] = round(pre_flood_dist / 1000.0, 2)
            strict_cutoff_settlements.append(settlement_entry)
            continue

        # Step C: Compare post-flood distance vs pre-flood distance
        if pre_flood_dist == 0.0:
            detour_ratio = 1.0 if post_flood_dist == 0.0 else 999.0
        else:
            detour_ratio = post_flood_dist / pre_flood_dist

        extra_km = max(0.0, (post_flood_dist - pre_flood_dist) / 1000.0)
        nearest_sc_info = {
            "node": int(best_flood_sc),
            "name": sc_node_map[best_flood_sc]["name"],
            "type": sc_node_map[best_flood_sc]["type"],
            "path_nodes_count": len(post_flood_path),
        }

        settlement_entry["pre_flood_distance_km"] = round(pre_flood_dist / 1000.0, 2)
        settlement_entry["post_flood_distance_km"] = round(post_flood_dist / 1000.0, 2)
        settlement_entry["shortest_distance_km"] = round(post_flood_dist / 1000.0, 2)
        settlement_entry["shortest_distance_meters"] = round(post_flood_dist, 1)
        settlement_entry["detour_ratio"] = round(detour_ratio, 2)
        settlement_entry["extra_distance_km"] = round(extra_km, 2)
        settlement_entry["nearest_service_center"] = nearest_sc_info

        # Step D: Classify
        if detour_ratio >= detour_threshold:
            # Practical cut-off: distance at least tripled
            settlement_entry["reason"] = (
                f"Practical cut-off: road distance increased by {detour_ratio:.2f}x "
                f"(+{extra_km:.2f}km detour to {nearest_sc_info['name']})"
            )
            practical_cutoff_settlements.append(settlement_entry)
        else:
            # Connected: distance did not triple
            connected_settlements.append(settlement_entry)

    # 7. Output results to JSON files
    with open(cutoff_output_file, "w", encoding="utf-8") as f:
        json.dump(strict_cutoff_settlements, f, indent=2, ensure_ascii=False)
    print(f"\nSaved strict cut-off settlements ({len(strict_cutoff_settlements):,}): {cutoff_output_file.name}")

    with open(practical_output_file, "w", encoding="utf-8") as f:
        json.dump(practical_cutoff_settlements, f, indent=2, ensure_ascii=False)
    print(f"Saved practical cut-off settlements ({len(practical_cutoff_settlements):,}): {practical_output_file.name}")

    with open(connected_output_file, "w", encoding="utf-8") as f:
        json.dump(connected_settlements, f, indent=2, ensure_ascii=False)
    print(f"Saved connected settlements ({len(connected_settlements):,}): {connected_output_file.name}")

    # 8. Print statistics breakdown
    total_st = len(st_gdf)
    evaluated_count = len(strict_cutoff_settlements) + len(practical_cutoff_settlements) + len(connected_settlements)
    strict_count = len(strict_cutoff_settlements)
    practical_count = len(practical_cutoff_settlements)
    conn_count = len(connected_settlements)

    print("\n" + "=" * 55)
    print("SETTLEMENT CONNECTIVITY ANALYSIS BREAKDOWN")
    print("=" * 55)
    print(f"Total Settlements:       {total_st:,}")
    print(f"Evaluated Settlements:   {evaluated_count:,} (skipped: {len(skipped_settlements)})")
    print(f" - Strict Cut-offs:      {strict_count:,} (no road path exists)")
    print(f" - Practical Cut-offs:   {practical_count:,} (detour >= {detour_threshold:.1f}x)")
    print(f" - Connected:            {conn_count:,} (detour < {detour_threshold:.1f}x)")
    print("=" * 55)

    if strict_cutoff_settlements:
        print(f"\nSTRICT CUT-OFF SETTLEMENTS ({strict_count}):")
        for idx, item in enumerate(strict_cutoff_settlements[:10], 1):
            print(f" {idx:2d}. {item['name']} ({item['place_type']}) - Lat: {item['latitude']:.4f}, Lon: {item['longitude']:.4f}")

    if practical_cutoff_settlements:
        print(f"\nPRACTICAL CUT-OFF SETTLEMENTS (Detour >= {detour_threshold:.1f}x) ({practical_count}):")
        for idx, item in enumerate(practical_cutoff_settlements[:10], 1):
            pre_d = item.get("pre_flood_distance_km", 0.0)
            post_d = item.get("post_flood_distance_km", 0.0)
            ratio = item.get("detour_ratio", 1.0)
            print(f" {idx:2d}. {item['name']} ({item['place_type']}) - {pre_d:.2f}km -> {post_d:.2f}km ({ratio:.2f}x detour)")

    return {
        "total_settlements": total_st,
        "evaluated_settlements": evaluated_count,
        "strict_cutoff_count": strict_count,
        "practical_cutoff_count": practical_count,
        "connected_count": conn_count,
        "cutoff_file": cutoff_output_file,
        "practical_cutoff_file": practical_output_file,
        "connected_file": connected_output_file,
    }


def main():
    parser = argparse.ArgumentParser(
        description="Detect strict and practical cut-off settlements from service centers after floods."
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
    parser.add_argument(
        "--detour-threshold",
        type=float,
        default=3.0,
        help="Detour ratio threshold for practical cut-off (default: 3.0)",
    )
    parser.add_argument(
        "--refresh-settlements",
        action="store_true",
        help="Force re-querying settlements from OSM instead of using cached settlements.geojson",
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
            force_refresh_settlements=args.refresh_settlements,
            detour_threshold=args.detour_threshold,
        )
    except KeyboardInterrupt:
        print("\nOperation cancelled by user.", file=sys.stderr)
        sys.exit(130)
    except Exception as exc:
        print(f"\n[ERROR] Connectivity analysis failed: {exc}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
