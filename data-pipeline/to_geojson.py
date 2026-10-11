"""
SAHAYAK — Step 12: GeoTIFF → GeoJSON + CSV
Team integration ke liye
"""
import rasterio
from rasterio.features import shapes
from shapely.geometry import shape
import geopandas as gpd
import json
import os
import numpy as np

OUT_DIR = 'sar_data'
MASK = os.path.join(OUT_DIR, 'flood_mask_20220620.tif')
CONF = os.path.join(OUT_DIR, 'flood_confidence_20220620.tif')

# ── 1. Read flood mask ───────────────────────────────
with rasterio.open(MASK) as src:
    mask = src.read(1)
    transform = src.transform
    crs = src.crs

print(f"Mask shape: {mask.shape}")
print(f"CRS: {crs}")
print(f"Flood pixels: {mask.sum()}")

# ── 2. Extract polygons ──────────────────────────────
geoms = [
    shape(s) for s, v in shapes(mask, mask=(mask == 1), transform=transform)
]
print(f"Polygons extracted: {len(geoms)}")

# ── 3. GeoDataFrame ──────────────────────────────────
gdf = gpd.GeoDataFrame(
    {'flood': [1] * len(geoms)},
    geometry=geoms,
    crs=crs
)
gdf = gdf.to_crs('EPSG:4326')

geojson_path = os.path.join(OUT_DIR, 'flood_mask_20220620.geojson')
gdf.to_file(geojson_path, driver='GeoJSON')
print(f"✅ GeoJSON saved: {geojson_path}")

# ── 4. Confidence stats ──────────────────────────────
with rasterio.open(CONF) as src:
    confidence = src.read(1)
    valid_conf = confidence[confidence > 0]
    if len(valid_conf) > 0:
        print(f"Confidence mean: {valid_conf.mean():.3f}")
        print(f"Confidence max: {valid_conf.max():.3f}")

# ── 5. Metadata ──────────────────────────────────────
meta = {
    "event": "Kamrup, Assam Flood 2022",
    "date": "2022-06-20",
    "satellite": "Sentinel-1 GRD",
    "polarization": "VV",
    "orbit": "DESCENDING",
    "crs": "EPSG:4326",
    "shape": list(mask.shape),
    "flood_pixels": int(mask.sum()),
    "flood_percentage": round(float(mask.sum() / mask.size * 100), 2),
    "flood_polygons": len(gdf),
    "bounds": {
        "min_lon": 90.99,
        "min_lat": 25.79,
        "max_lon": 92.00,
        "max_lat": 26.40
    },
    "source": "Copernicus Sentinel-1 via Google Earth Engine"
}
meta_path = os.path.join(OUT_DIR, 'metadata.json')
with open(meta_path, 'w') as f:
    json.dump(meta, f, indent=2)
print(f"✅ Metadata saved: {meta_path}")

print("\n✅ STEP 12 COMPLETE — Team ke liye output ready!")