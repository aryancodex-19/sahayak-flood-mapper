"""
SAHAYAK — Slope Filter (Terrain-Constrained Refinement)
Steep slopes (>5%) pe flood false positives hatao
"""
import ee
import geemap
import rasterio
import numpy as np
import os

PROJECT_ID = 'snappy-nomad-465705-b9'
ee.Initialize(project=PROJECT_ID)

KAMRUP = ee.Geometry.Rectangle([91.0, 25.8, 92.0, 26.4])
OUT_DIR = 'sar_data'

# ── 1. DEM se slope nikaalo ──────────────────────────
print("Downloading slope from Copernicus DEM...")

# ✅ FIX: Naya dataset + ImageCollection ko Image me convert karo
dem = ee.Image('USGS/SRTMGL1_003').clip(KAMRUP)
slope = ee.Terrain.slope(dem).clip(KAMRUP)

slope_path = os.path.join(OUT_DIR, 'slope.tif')
geemap.ee_export_image(
    slope, filename=slope_path, scale=100,
    region=KAMRUP, file_per_band=False, crs='EPSG:4326'
)
print(f"✅ Slope saved: {slope_path}")

# ── 2. Flood mask pe slope filter ────────────────────
print("\nApplying slope filter...")
with rasterio.open('sar_data/flood_mask_20220620.tif') as src:
    mask = src.read(1)
    profile = src.profile.copy()

with rasterio.open(slope_path) as src:
    slope_arr = src.read(1)

print(f"Mask shape: {mask.shape}")
print(f"Slope shape: {slope_arr.shape}")

if slope_arr.shape == mask.shape:
    before = mask.sum()
    mask[slope_arr > 5.0] = 0
    after = mask.sum()
    print(f"Before: {before} flood pixels")
    print(f"After: {after} flood pixels")
    print(f"Removed: {before - after} false positives on steep slopes")

    profile.update(dtype=rasterio.uint8, count=1, compress='lzw')
    output = os.path.join(OUT_DIR, 'flood_mask_20220620_filtered.tif')
    with rasterio.open(output, 'w', **profile) as dst:
        dst.write(mask, 1)
    print(f"✅ Filtered mask saved: {output}")
else:
    print(f"⚠️ Shape mismatch! Slope resampling needed.")
    print(f"   Mask: {mask.shape}, Slope: {slope_arr.shape}")