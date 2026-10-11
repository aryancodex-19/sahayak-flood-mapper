"""
Generate a dummy flood mask GeoTIFF based on road network bounding box.
"""

import sys
import argparse
from pathlib import Path
import geopandas as gpd
import numpy as np
import rasterio
from rasterio.transform import from_bounds


def generate_dummy_flood_mask(
    edges_gpkg_path: Path = None,
    output_tif_path: Path = None,
    resolution: float = 0.001,
    num_patches: int = 4,
    random_seed: int = 42,
):
    """
    Creates a binary dummy flood mask GeoTIFF covering the bounding box of edges_gpkg.

    :param edges_gpkg_path: Path to road_edges.gpkg
    :param output_tif_path: Destination path for dummy_flood_mask.tif
    :param resolution: Grid cell resolution in degrees (default: 0.001 ~ 100m)
    :param num_patches: Number of flooded rectangular patches (default: 3-4)
    :param random_seed: Seed for reproducible patch placement
    """
    base_dir = Path(__file__).resolve().parent

    if edges_gpkg_path is None:
        edges_gpkg_path = base_dir / "road_edges.gpkg"
    else:
        edges_gpkg_path = Path(edges_gpkg_path).resolve()

    if output_tif_path is None:
        output_tif_path = base_dir / "dummy_flood_mask.tif"
    else:
        output_tif_path = Path(output_tif_path).resolve()

    if not edges_gpkg_path.exists():
        raise FileNotFoundError(f"Road edges file not found at: {edges_gpkg_path}")

    print(f"Loading road edges from: {edges_gpkg_path}...")
    edges = gpd.read_file(edges_gpkg_path)

    # Ensure CRS is EPSG:4326
    if edges.crs is None:
        edges.set_crs(epsg=4326, inplace=True)
    elif edges.crs.to_epsg() != 4326:
        print(f"Reprojecting edges from {edges.crs} to EPSG:4326...")
        edges = edges.to_crs(epsg=4326)

    # Compute bounding box
    minx, miny, maxx, maxy = edges.total_bounds
    print(f"Bounding Box (EPSG:4326): West={minx:.5f}, South={miny:.5f}, East={maxx:.5f}, North={maxy:.5f}")

    # Compute dimensions based on resolution
    width = int(np.ceil((maxx - minx) / resolution))
    height = int(np.ceil((maxy - miny) / resolution))

    # Recalculate east and south to match exact grid steps
    east = minx + width * resolution
    south = maxy - height * resolution

    print(f"Raster dimensions: {width} x {height} pixels (resolution: {resolution} deg)")

    # Georeferencing transform
    transform = from_bounds(minx, south, east, maxy, width, height)

    # Initialize raster with 0 (no flood)
    raster = np.zeros((height, width), dtype=np.uint8)

    # Place random rectangular patches
    rng = np.random.default_rng(random_seed)
    actual_patches = rng.integers(3, num_patches + 1) if num_patches >= 3 else num_patches
    print(f"Generating {actual_patches} flooded rectangular patches...")

    for i in range(actual_patches):
        # Patch dimensions between 8% and 20% of raster size
        patch_h = rng.integers(max(5, int(height * 0.08)), max(10, int(height * 0.20)))
        patch_w = rng.integers(max(5, int(width * 0.08)), max(10, int(width * 0.20)))

        # Random top-left corner
        row_start = rng.integers(0, max(1, height - patch_h))
        col_start = rng.integers(0, max(1, width - patch_w))

        row_end = min(height, row_start + patch_h)
        col_end = min(width, col_start + patch_w)

        raster[row_start:row_end, col_start:col_end] = 1
        print(f" - Patch {i+1}: rows [{row_start}:{row_end}], cols [{col_start}:{col_end}] ({row_end - row_start}x{col_end - col_start} px)")

    flooded_pixels = int(np.sum(raster == 1))
    total_pixels = height * width
    flood_percentage = (flooded_pixels / total_pixels) * 100

    # Save to GeoTIFF using rasterio
    output_tif_path.parent.mkdir(parents=True, exist_ok=True)
    print(f"Saving GeoTIFF to: {output_tif_path}...")
    with rasterio.open(
        output_tif_path,
        "w",
        driver="GTiff",
        height=height,
        width=width,
        count=1,
        dtype=raster.dtype,
        crs="EPSG:4326",
        transform=transform,
        nodata=255,
        compress="lzw",
    ) as dst:
        dst.write(raster, 1)

    print("\n" + "=" * 40)
    print("DUMMY FLOOD MASK GENERATED")
    print("=" * 40)
    print(f"File: {output_tif_path}")
    print(f"Resolution: {resolution} deg (~100m)")
    print(f"Flooded Pixels: {flooded_pixels:,} / {total_pixels:,} ({flood_percentage:.2f}%)")
    print("=" * 40)

    return output_tif_path


def main():
    parser = argparse.ArgumentParser(
        description="Generate a dummy flood mask GeoTIFF for testing flood overlay logic."
    )
    parser.add_argument(
        "--edges",
        type=str,
        default=None,
        help="Path to road_edges.gpkg (defaults to road_edges.gpkg in script folder)",
    )
    parser.add_argument(
        "--output",
        type=str,
        default=None,
        help="Output GeoTIFF path (defaults to dummy_flood_mask.tif in script folder)",
    )
    parser.add_argument(
        "--res",
        type=float,
        default=0.001,
        help="Grid resolution in degrees (default: 0.001)",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=42,
        help="Random seed for patch generation (default: 42)",
    )

    args = parser.parse_args()

    try:
        generate_dummy_flood_mask(
            edges_gpkg_path=args.edges,
            output_tif_path=args.output,
            resolution=args.res,
            random_seed=args.seed,
        )
    except KeyboardInterrupt:
        print("\nOperation cancelled by user.", file=sys.stderr)
        sys.exit(130)
    except Exception as exc:
        print(f"\n[ERROR] Failed to generate dummy flood mask: {exc}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
