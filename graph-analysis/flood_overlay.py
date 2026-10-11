"""
Overlay flood raster mask on road network to detect submerged roads, bridges, and tunnels.
"""

import sys
import argparse
from pathlib import Path
import geopandas as gpd
import pandas as pd
import numpy as np
import rasterio
from rasterio.mask import mask
from rasterio.features import geometry_mask
from scipy.ndimage import label, find_objects
from shapely.geometry import box
import shapely


def is_osm_flag_active(val) -> bool:
    """Helper to determine if an OSM tag like 'bridge' or 'tunnel' is active."""
    if val is None or pd.isna(val):
        return False
    val_str = str(val).strip().lower()
    return val_str not in ("no", "false", "0", "none", "")


def overlay_flood_on_network(
    edges_path: Path = None,
    flood_mask_path: Path = None,
    output_gpkg_path: Path = None,
    output_geojson_path: Path = None,
):
    """
    Overlays a flood raster mask on road network edges using spatial indexing.

    :param edges_path: Path to road_edges.gpkg
    :param flood_mask_path: Path to flood raster (dummy_flood_mask.tif)
    :param output_gpkg_path: Path for flooded_edges.gpkg
    :param output_geojson_path: Path for flooded_edges.geojson
    """
    base_dir = Path(__file__).resolve().parent

    if edges_path is None:
        edges_path = base_dir / "road_edges.gpkg"
    else:
        edges_path = Path(edges_path).resolve()

    if flood_mask_path is None:
        flood_mask_path = base_dir / "dummy_flood_mask.tif"
    else:
        flood_mask_path = Path(flood_mask_path).resolve()

    if output_gpkg_path is None:
        output_gpkg_path = base_dir / "flooded_edges.gpkg"
    else:
        output_gpkg_path = Path(output_gpkg_path).resolve()

    if output_geojson_path is None:
        output_geojson_path = base_dir / "flooded_edges.geojson"
    else:
        output_geojson_path = Path(output_geojson_path).resolve()

    if not edges_path.exists():
        raise FileNotFoundError(f"Road network file not found at: {edges_path}")

    if not flood_mask_path.exists():
        raise FileNotFoundError(f"Flood mask raster not found at: {flood_mask_path}")

    print(f"Loading road edges from: {edges_path}...")
    edges = gpd.read_file(edges_path)
    total_edges = len(edges)
    print(f"Total road edges loaded: {total_edges:,}")

    # Initialize flooded column
    edges["flooded"] = False

    # Open raster and check CRS
    print(f"Loading flood raster mask from: {flood_mask_path}...")
    with rasterio.open(flood_mask_path) as src:
        raster_crs = src.crs
        raster_data = src.read(1)
        raster_transform = src.transform

        # CRS Alignment
        if edges.crs is None:
            print("Notice: road_edges CRS undefined, setting to EPSG:4326.")
            edges.set_crs(epsg=4326, inplace=True)

        if raster_crs is not None and edges.crs != raster_crs:
            print(f"Reprojecting edges from {edges.crs} to raster CRS ({raster_crs})...")
            edges = edges.to_crs(raster_crs)

        # Check for flooded pixels
        flooded_pixel_count = int(np.count_nonzero(raster_data == 1))
        print(f"Flooded pixels detected in raster: {flooded_pixel_count:,}")

        # Edge case: Empty flood mask
        if flooded_pixel_count == 0:
            print("[INFO] Flood mask has no flooded pixels (value=1). No edges flooded.")
            candidate_indices = np.array([], dtype=int)
        else:
            # Spatial indexing: Find bounding boxes of flooded connected patches
            print("Building spatial bounding boxes for flooded regions...")
            labeled_mask, num_features = label(raster_data == 1)
            slices = find_objects(labeled_mask)

            patch_boxes = []
            for r_slice, c_slice in slices:
                xs, ys = rasterio.transform.xy(
                    raster_transform,
                    [r_slice.start, r_slice.stop],
                    [c_slice.start, c_slice.stop],
                )
                patch_boxes.append(box(min(xs), min(ys), max(xs), max(ys)))

            combined_flood_bounds = shapely.unary_union(patch_boxes)

            # Query spatial index of road edges to find only candidates
            print("Querying spatial index for candidate intersecting road edges...")
            candidate_matches = edges.sindex.query(combined_flood_bounds, predicate="intersects")
            candidate_indices = np.unique(candidate_matches)
            print(f"Candidate edges in flood zones: {len(candidate_indices):,} (out of {total_edges:,})")

            # Verify intersection for candidate edges using rasterio mask / geometry_mask
            print("Verifying precise edge-raster intersections...")
            flooded_indices = []
            for idx in candidate_indices:
                geom = edges.geometry.iloc[idx]
                if geom is None or geom.is_empty:
                    continue
                try:
                    out_img, _ = mask(src, [geom], crop=True, all_touched=True, filled=False)
                    if np.any(out_img == 1):
                        flooded_indices.append(idx)
                except Exception:
                    # In case geometry is slightly outside bounds or degenerated
                    continue

            if flooded_indices:
                edges.loc[edges.index[flooded_indices], "flooded"] = True

    # Check bridge and tunnel status
    has_bridge_col = "bridge" in edges.columns
    has_tunnel_col = "tunnel" in edges.columns

    if has_bridge_col:
        is_bridge_series = edges["bridge"].apply(is_osm_flag_active)
    else:
        print("Notice: 'bridge' column not present in road network. Defaulting to False.")
        is_bridge_series = pd.Series(False, index=edges.index)

    if has_tunnel_col:
        is_tunnel_series = edges["tunnel"].apply(is_osm_flag_active)
    else:
        print("Notice: 'tunnel' column not present in road network. Defaulting to False.")
        is_tunnel_series = pd.Series(False, index=edges.index)

    edges["is_bridge"] = is_bridge_series
    edges["is_tunnel"] = is_tunnel_series

    # Filter flooded edges
    flooded_edges = edges[edges["flooded"]].copy()
    num_flooded = len(flooded_edges)
    num_flooded_bridges = int((flooded_edges["is_bridge"]).sum())
    num_flooded_tunnels = int((flooded_edges["is_tunnel"]).sum())
    pct_flooded = (num_flooded / total_edges * 100.0) if total_edges > 0 else 0.0

    # Ensure list columns in flooded_edges are formatted as string for GPKG / GeoJSON export
    for col in flooded_edges.columns:
        if col != "geometry" and flooded_edges[col].apply(lambda x: isinstance(x, list)).any():
            flooded_edges[col] = flooded_edges[col].apply(
                lambda x: ", ".join(map(str, x)) if isinstance(x, list) else x
            )

    # Save outputs
    output_gpkg_path.parent.mkdir(parents=True, exist_ok=True)
    output_geojson_path.parent.mkdir(parents=True, exist_ok=True)

    print(f"\nSaving flooded edges to GeoPackage: {output_gpkg_path.name}...")
    flooded_edges.to_file(output_gpkg_path, driver="GPKG")
    print(f"Saved: {output_gpkg_path}")

    print(f"Saving flooded edges to GeoJSON: {output_geojson_path.name}...")
    flooded_edges.to_file(output_geojson_path, driver="GeoJSON")
    print(f"Saved: {output_geojson_path}")

    # Summary Statistics
    print("\n" + "=" * 45)
    print("FLOOD NETWORK OVERLAY STATISTICS")
    print("=" * 45)
    print(f"Total Edges:         {total_edges:,}")
    print(f"Flooded Edges:       {num_flooded:,}")
    print(f"Flooded Bridges:     {num_flooded_bridges:,}")
    print(f"Flooded Tunnels:     {num_flooded_tunnels:,}")
    print(f"Flooded Road Ratio:  {pct_flooded:.2f}%")
    print("=" * 45)

    return {
        "total_edges": total_edges,
        "flooded_edges": num_flooded,
        "flooded_bridges": num_flooded_bridges,
        "flooded_tunnels": num_flooded_tunnels,
        "pct_flooded": pct_flooded,
        "output_gpkg": output_gpkg_path,
        "output_geojson": output_geojson_path,
    }


def main():
    parser = argparse.ArgumentParser(
        description="Overlay flood mask on road network to find submerged roads, bridges, and tunnels."
    )
    parser.add_argument(
        "--edges",
        type=str,
        default=None,
        help="Path to road_edges.gpkg (default: road_edges.gpkg in script folder)",
    )
    parser.add_argument(
        "--flood-mask",
        type=str,
        default=None,
        help="Path to dummy_flood_mask.tif (default: dummy_flood_mask.tif in script folder)",
    )
    parser.add_argument(
        "--output-gpkg",
        type=str,
        default=None,
        help="Path for flooded_edges.gpkg (default: flooded_edges.gpkg in script folder)",
    )
    parser.add_argument(
        "--output-geojson",
        type=str,
        default=None,
        help="Path for flooded_edges.geojson (default: flooded_edges.geojson in script folder)",
    )

    args = parser.parse_args()

    try:
        overlay_flood_on_network(
            edges_path=args.edges,
            flood_mask_path=args.flood_mask,
            output_gpkg_path=args.output_gpkg,
            output_geojson_path=args.output_geojson,
        )
    except KeyboardInterrupt:
        print("\nOperation cancelled by user.", file=sys.stderr)
        sys.exit(130)
    except Exception as exc:
        print(f"\n[ERROR] Failed to execute flood overlay: {exc}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
