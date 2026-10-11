"""
Download road network using OSMnx and export to GraphML and GeoPackage formats.
"""

import sys
import argparse
from pathlib import Path
import osmnx as ox


def download_and_save_network(place_name: str = "Kamrup, Assam, India", output_dir: Path = None):
    """
    Downloads driveable road network for a given place, saves it as GraphML
    and GeoPackage, and prints network statistics.
    """
    if output_dir is None:
        output_dir = Path(__file__).resolve().parent
    else:
        output_dir = Path(output_dir).resolve()

    output_dir.mkdir(parents=True, exist_ok=True)
    graphml_path = output_dir / "network.graphml"
    gpkg_path = output_dir / "road_edges.gpkg"

    print(f"Downloading driveable road network for: '{place_name}'...")
    # OSMnx 2.1+ graph download
    graph = ox.graph_from_place(place_name, network_type="drive")
    print("Download completed successfully.")

    # Save graph as GraphML
    print(f"Saving graph to GraphML: {graphml_path.name}...")
    ox.save_graphml(graph, filepath=graphml_path)
    print(f"Saved: {graphml_path}")

    # Convert graph to GeoDataFrames
    print("Converting graph to GeoDataFrames...")
    gdf_nodes, gdf_edges = ox.graph_to_gdfs(graph)

    # Handle list-type attributes in edges for GeoPackage compatibility
    edges_to_save = gdf_edges.copy()
    for col in edges_to_save.columns:
        if edges_to_save[col].apply(lambda val: isinstance(val, list)).any():
            edges_to_save[col] = edges_to_save[col].apply(
                lambda val: ", ".join(map(str, val)) if isinstance(val, list) else val
            )

    # Save edges as GeoPackage
    print(f"Saving edges to GeoPackage: {gpkg_path.name}...")
    edges_to_save.to_file(gpkg_path, driver="GPKG")
    print(f"Saved: {gpkg_path}")

    # Calculate statistics
    num_nodes = len(gdf_nodes)
    num_edges = len(gdf_edges)
    total_length_km = gdf_edges["length"].sum() / 1000.0 if "length" in gdf_edges.columns else 0.0

    print("\n" + "=" * 40)
    print("ROAD NETWORK STATISTICS")
    print("=" * 40)
    print(f"Place: {place_name}")
    print(f"Total Nodes: {num_nodes:,}")
    print(f"Total Edges: {num_edges:,}")
    print(f"Total Road Length: {total_length_km:,.2f} km")
    print("=" * 40)

    return {
        "nodes": num_nodes,
        "edges": num_edges,
        "total_length_km": total_length_km,
        "graphml_path": graphml_path,
        "gpkg_path": gpkg_path,
    }


def main():
    parser = argparse.ArgumentParser(
        description="Download OSM driveable road network for a specified place and save outputs."
    )
    parser.add_argument(
        "place",
        nargs="?",
        default="Kamrup, Assam, India",
        help="Target place name (default: 'Kamrup, Assam, India')",
    )

    args = parser.parse_args()

    try:
        download_and_save_network(place_name=args.place)
    except KeyboardInterrupt:
        print("\nOperation cancelled by user.", file=sys.stderr)
        sys.exit(130)
    except Exception as exc:
        print(f"\n[ERROR] Failed to download or process network for '{args.place}': {exc}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
