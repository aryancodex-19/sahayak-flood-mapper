"""
Overlay flood mask (GeoJSON or GeoTIFF) on road network to detect submerged roads, bridges, and tunnels.
"""

import sys
import argparse
from pathlib import Path
import geopandas as gpd
import pandas as pd
import numpy as np
import rasterio
from rasterio.mask import mask
from scipy.ndimage import label, find_objects
from shapely.geometry import box
import shapely


def is_osm_flag_active(val) -> bool:
    """Helper to determine if an OSM tag like 'bridge' or 'tunnel' is active."""
    if val is None or pd.isna(val):
        return False
    val_str = str(val).strip().lower()
    return val_str not in ("no", "false", "0", "none", "")


def load_flood_from_geojson(path: Path) -> gpd.GeoDataFrame:
    """
    Loads flood mask polygons from a GeoJSON file using geopandas.read_file().
    Ensures valid geometries and CRS alignment to EPSG:4326.
    """
    path = Path(path).resolve()
    if not path.exists():
        raise FileNotFoundError(f"Flood GeoJSON mask not found at: {path}")

    print(f"Loading flood mask from GeoJSON: {path.name}...")
    flood_gdf = gpd.read_file(path)

    # Validate and standardize CRS to EPSG:4326
    if flood_gdf.crs is None:
        print("Notice: Flood GeoJSON CRS undefined, defaulting to EPSG:4326.")
        flood_gdf.set_crs(epsg=4326, inplace=True)
    elif flood_gdf.crs.to_epsg() != 4326:
        print(f"Reprojecting flood GeoJSON from {flood_gdf.crs} to EPSG:4326...")
        flood_gdf = flood_gdf.to_crs(epsg=4326)

    # Remove empty or invalid geometries
    flood_gdf = flood_gdf[~flood_gdf.is_empty & flood_gdf.geometry.notna()].copy()
    print(f"Loaded {len(flood_gdf):,} flood polygons (EPSG:4326).")
    return flood_gdf


def overlay_flood_geojson(edges: gpd.GeoDataFrame, flood_gdf: gpd.GeoDataFrame) -> np.ndarray:
    """
    Identifies edges that intersect with flood polygons using spatial index (sindex)
    and GeoPandas .intersects() for high performance.
    """
    if flood_gdf.empty or edges.empty:
        return np.array([], dtype=int)

    print("Querying spatial index for road edge-polygon candidate intersections...")
    # sindex.query(flood_gdf.geometry) returns (flood_indices, edge_indices)
    candidate_flood_idx, candidate_edge_idx = edges.sindex.query(flood_gdf.geometry)
    print(f"Candidate intersection pairs identified: {len(candidate_edge_idx):,}")

    if len(candidate_edge_idx) == 0:
        return np.array([], dtype=int)

    print("Evaluating exact .intersects() on candidate pairs...")
    edge_geoms = edges.geometry.iloc[candidate_edge_idx].reset_index(drop=True)
    flood_geoms = flood_gdf.geometry.iloc[candidate_flood_idx].reset_index(drop=True)

    intersect_mask = edge_geoms.intersects(flood_geoms)
    flooded_edge_indices = np.unique(candidate_edge_idx[intersect_mask])
    return flooded_edge_indices


def overlay_flood_geotiff(edges: gpd.GeoDataFrame, tif_path: Path) -> np.ndarray:
    """
    Identifies edges that intersect with flooded pixels (value=1) in a GeoTIFF raster.
    """
    print(f"Loading flood raster mask from: {tif_path.name}...")
    with rasterio.open(tif_path) as src:
        raster_crs = src.crs
        raster_data = src.read(1)
        raster_transform = src.transform

        # Align edges CRS if needed
        if raster_crs is not None and edges.crs != raster_crs:
            print(f"Reprojecting edges from {edges.crs} to raster CRS ({raster_crs})...")
            edges = edges.to_crs(raster_crs)

        flooded_pixel_count = int(np.count_nonzero(raster_data == 1))
        print(f"Flooded pixels detected in raster: {flooded_pixel_count:,}")

        if flooded_pixel_count == 0:
            return np.array([], dtype=int)

        # Build bounding boxes of flooded regions
        labeled_mask, _ = label(raster_data == 1)
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

        candidate_matches = edges.sindex.query(combined_flood_bounds, predicate="intersects")
        candidate_indices = np.unique(candidate_matches)
        print(f"Candidate edges in flood zones: {len(candidate_indices):,} (out of {len(edges):,})")

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
                continue

        return np.array(flooded_indices, dtype=int)


def overlay_flood_on_network(
    edges_path: Path = None,
    flood_mask_path: Path = None,
    output_gpkg_path: Path = None,
    output_geojson_path: Path = None,
):
    """
    Overlays flood mask (GeoJSON polygons or GeoTIFF raster) on road network edges.

    :param edges_path: Path to road_edges.gpkg
    :param flood_mask_path: Path to flood mask file (.geojson or .tif)
    :param output_gpkg_path: Destination path for flooded_edges.gpkg
    :param output_geojson_path: Destination path for flooded_edges.geojson
    """
    base_dir = Path(__file__).resolve().parent

    edges_path = Path(edges_path or base_dir / "road_edges.gpkg").resolve()
    if flood_mask_path is None:
        flood_mask_path = base_dir / "dummy_flood_mask.tif"
    else:
        flood_mask_path = Path(flood_mask_path).resolve()

    output_gpkg_path = Path(output_gpkg_path or base_dir / "flooded_edges.gpkg").resolve()
    output_geojson_path = Path(output_geojson_path or base_dir / "flooded_edges.geojson").resolve()

    if not edges_path.exists():
        raise FileNotFoundError(f"Road network file not found at: {edges_path}")

    if not flood_mask_path.exists():
        raise FileNotFoundError(f"Flood mask file not found at: {flood_mask_path}")

    print(f"Loading road edges from: {edges_path}...")
    edges = gpd.read_file(edges_path)
    total_edges = len(edges)
    print(f"Total road edges loaded: {total_edges:,}")

    # Standardize CRS of edges to EPSG:4326
    if edges.crs is None:
        print("Notice: road_edges CRS undefined, defaulting to EPSG:4326.")
        edges.set_crs(epsg=4326, inplace=True)
    elif edges.crs.to_epsg() != 4326:
        print(f"Reprojecting edges from {edges.crs} to EPSG:4326...")
        edges = edges.to_crs(epsg=4326)

    # Initialize flooded column
    edges["flooded"] = False

    # Determine input type by file extension
    ext = flood_mask_path.suffix.lower()
    print(f"Flood mask input format: '{ext}' ({flood_mask_path.name})")

    if ext in (".geojson", ".json"):
        # GeoJSON input
        flood_gdf = load_flood_from_geojson(flood_mask_path)
        if edges.crs != flood_gdf.crs:
            edges = edges.to_crs(flood_gdf.crs)
        flooded_indices = overlay_flood_geojson(edges, flood_gdf)
    elif ext in (".tif", ".tiff"):
        # GeoTIFF input
        flooded_indices = overlay_flood_geotiff(edges, flood_mask_path)
    else:
        # Fallback: try GeoJSON first, then GeoTIFF
        try:
            flood_gdf = load_flood_from_geojson(flood_mask_path)
            flooded_indices = overlay_flood_geojson(edges, flood_gdf)
        except Exception:
            flooded_indices = overlay_flood_geotiff(edges, flood_mask_path)

    # Mark flooded edges
    if len(flooded_indices) > 0:
        edges.loc[edges.index[flooded_indices], "flooded"] = True

    # Check bridge and tunnel status using OSM tags
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
        description="Overlay flood mask (GeoJSON or GeoTIFF) on road network to find submerged roads, bridges, and tunnels."
    )
    parser.add_argument(
        "--input",
        "--flood-mask",
        dest="input_mask",
        type=str,
        default=None,
        help="Path to flood mask file (.geojson or .tif). Default: dummy_flood_mask.tif in script folder.",
    )
    parser.add_argument(
        "--edges",
        type=str,
        default=None,
        help="Path to road_edges.gpkg (default: road_edges.gpkg in script folder)",
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
            flood_mask_path=args.input_mask,
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
