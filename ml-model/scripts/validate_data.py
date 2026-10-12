"""
Raster Data Validation Script for SAHAYAK Flood Mapping.

This script inspects, verifies, and validates raster files:
- Dimensions (Height, Width)
- Band count & data types
- CRS & Affine Transform alignment
- Bounds & NoData handling
- Value distributions (min, max, mean, std), NaNs, and Infs
- Pixel counts for binary masks
"""

import sys
import os
import argparse
from pathlib import Path
import numpy as np
import rasterio


def inspect_raster(filepath: Path) -> dict:
    """Inspects a single GeoTIFF raster and computes spatial & statistical metrics."""
    if not filepath.exists():
        return {"error": f"File not found: {filepath}"}

    file_size_bytes = filepath.stat().st_size

    with rasterio.open(filepath) as src:
        height, width = src.shape
        count = src.count
        dtypes = src.dtypes
        crs = src.crs
        transform = src.transform
        bounds = src.bounds
        nodata = src.nodata

        # Read first band for statistics
        arr = src.read(1)

        # Handle nodata masking
        if nodata is not None:
            if np.isnan(nodata):
                valid_mask = ~np.isnan(arr)
            else:
                valid_mask = (arr != nodata) & (~np.isnan(arr))
        else:
            valid_mask = ~np.isnan(arr)

        nan_count = int(np.isnan(arr).sum())
        inf_count = int(np.isinf(arr).sum())
        valid_count = int(valid_mask.sum())
        total_pixels = height * width

        stats = {
            "path": str(filepath),
            "filename": filepath.name,
            "size_bytes": file_size_bytes,
            "shape": (height, width),
            "bands": count,
            "dtypes": dtypes,
            "crs": str(crs),
            "transform": tuple(transform),
            "bounds": {
                "left": bounds.left,
                "bottom": bounds.bottom,
                "right": bounds.right,
                "top": bounds.top,
            },
            "nodata": nodata,
            "total_pixels": total_pixels,
            "valid_pixels": valid_count,
            "nan_count": nan_count,
            "inf_count": inf_count,
        }

        if valid_count > 0:
            valid_vals = arr[valid_mask]
            stats["min"] = float(valid_vals.min())
            stats["max"] = float(valid_vals.max())
            stats["mean"] = float(valid_vals.mean())
            stats["std"] = float(valid_vals.std())

            # Check for discrete values if integer type or mask
            unique_vals, counts = np.unique(arr, return_counts=True)
            stats["unique_distribution"] = dict(
                zip([float(v) for v in unique_vals], [int(c) for c in counts])
            )
        else:
            stats["min"] = None
            stats["max"] = None
            stats["mean"] = None
            stats["std"] = None
            stats["unique_distribution"] = {}

        return stats


def print_report(results: dict):
    """Prints a clean, formatted validation report."""
    print("=" * 80)
    print(" SAHAYAK RASTER DATA VALIDATION REPORT")
    print("=" * 80)

    for name, res in results.items():
        print(f"\n--- Raster: {name} ---")
        if "error" in res:
            print(f"  [ERROR]: {res['error']}")
            continue

        print(f"  Filename:     {res['filename']} ({res['size_bytes']:,} bytes)")
        print(f"  Dimensions:   Shape {res['shape']} (Height x Width), Bands: {res['bands']}")
        print(f"  Data Type:    {res['dtypes'][0]}")
        print(f"  CRS:          {res['crs']}")
        print(f"  NoData Value: {res['nodata']}")
        print(f"  Total Pixels: {res['total_pixels']:,} | Valid: {res['valid_pixels']:,} | NaNs: {res['nan_count']} | Infs: {res['inf_count']}")
        print(f"  Value Range:  Min: {res['min']:.4f}, Max: {res['max']:.4f}, Mean: {res['mean']:.4f}, Std: {res['std']:.4f}")
        print(f"  Bounds:       Left={res['bounds']['left']:.5f}, Bottom={res['bounds']['bottom']:.5f}, Right={res['bounds']['right']:.5f}, Top={res['bounds']['top']:.5f}")

        if len(res.get("unique_distribution", {})) <= 10:
            print(f"  Unique Values & Counts: {res['unique_distribution']}")

    print("\n" + "=" * 80)
    print(" ALIGNMENT CHECKS")
    print("=" * 80)

    valid_items = {k: v for k, v in results.items() if "error" not in v}
    if not valid_items:
        print("  No valid rasters to check alignment.")
        return

    first_name = list(valid_items.keys())[0]
    base = valid_items[first_name]

    aligned_all = True
    for name, res in valid_items.items():
        if name == first_name:
            continue
        shape_match = (res["shape"] == base["shape"])
        crs_match = (res["crs"] == base["crs"])
        bounds_match = (
            abs(res["bounds"]["left"] - base["bounds"]["left"]) < 1e-5 and
            abs(res["bounds"]["bottom"] - base["bounds"]["bottom"]) < 1e-5 and
            abs(res["bounds"]["right"] - base["bounds"]["right"]) < 1e-5 and
            abs(res["bounds"]["top"] - base["bounds"]["top"]) < 1e-5
        )

        status = "MATCH" if (shape_match and crs_match and bounds_match) else "MISMATCH"
        if status == "MISMATCH":
            aligned_all = False
        print(f"  [{status}] {name} vs {first_name}: Shape Match={shape_match}, CRS Match={crs_match}, Bounds Match={bounds_match}")

    print("=" * 80)
    print(f"  OVERALL ALIGNMENT: {'ALL ALIGNED PERFECTLY' if aligned_all else 'MISALIGNMENTS FOUND'}")
    print("=" * 80)


def main():
    parser = argparse.ArgumentParser(description="Validate SAR and auxiliary rasters")
    parser.add_argument(
        "--data-dir",
        type=str,
        default=None,
        help="Directory containing the GeoTIFF files",
    )
    args = parser.parse_args()

    # Determine files to validate
    # Candidate locations:
    # 1. Specified --data-dir
    # 2. ml-model/data/raw
    # 3. User Downloads folder as verified fallback
    base_script_dir = Path(__file__).resolve().parent
    repo_ml_dir = base_script_dir.parent

    target_files = [
        "pre_flood_VV.tif",
        "post_flood_VV.tif",
        "flood_mask_20220620_filtered.tif",
        "flood_confidence_20220620.tif",
        "slope.tif",
        "flood_mask_20220620.tif",
    ]

    candidate_dirs = []
    if args.data_dir:
        candidate_dirs.append(Path(args.data_dir))
    candidate_dirs.append(repo_ml_dir / "data" / "raw")
    candidate_dirs.append(repo_ml_dir / "Data" / "raw")
    candidate_dirs.append(Path.home() / "Downloads")

    results = {}
    for filename in target_files:
        found_path = None
        for cdir in candidate_dirs:
            p = cdir / filename
            if p.exists():
                found_path = p
                break

        if found_path:
            results[filename] = inspect_raster(found_path)
        else:
            results[filename] = {"error": f"File not found in candidate paths: {[str(d) for d in candidate_dirs]}"}

    print_report(results)


if __name__ == "__main__":
    main()
