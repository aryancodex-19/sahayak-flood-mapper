"""
SAHAYAK — Validation via Sentinel-2 Optical
SAR flood mask ko Sentinel-2 NDWI se compare karo
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

# ── 1. Sentinel-2 post-flood (date range wider, no cloud filter) ─
print("Downloading Sentinel-2 optical...")
s2_col = (ee.ImageCollection('COPERNICUS/S2_SR_HARMONIZED')
      .filterBounds(KAMRUP)
      .filterDate('2022-06-15', '2022-07-15'))
print(f"Available S2 images: {s2_col.size().getInfo()}")

# Cloud score+ se least cloudy select karo
s2 = s2_col.sort('CLOUDY_PIXEL_PERCENTAGE').first().clip(KAMRUP)
print(f"Selected image: {s2.get('system:index').getInfo()}")
print(f"Cloud cover: {s2.get('CLOUDY_PIXEL_PERCENTAGE').getInfo()}%")

# NDWI = (Green - NIR) / (Green + NIR) — water detection
ndwi = s2.normalizedDifference(['B3', 'B8']).rename('NDWI')

s2_path = os.path.join(OUT_DIR, 's2_ndwi.tif')
geemap.ee_export_image(
    ndwi, filename=s2_path, scale=100,
    region=KAMRUP, file_per_band=False, crs='EPSG:4326'
)
print(f"✅ S2 NDWI saved: {s2_path}")

# ── 2. Load our SAR mask ─────────────────────────────
with rasterio.open('sar_data/flood_mask_20220620_filtered.tif') as src:
    sar_mask = src.read(1)
    sar_transform = src.transform
    sar_crs = src.crs
    sar_shape = sar_mask.shape

print(f"SAR mask shape: {sar_shape}")

# ── 3. Load S2 NDWI ──────────────────────────────────
with rasterio.open(s2_path) as src:
    ndwi_arr = src.read(1)
    s2_transform = src.transform
    s2_crs = src.crs

# ── 4. Resample if needed ────────────────────────────
if ndwi_arr.shape != sar_shape:
    from rasterio.warp import reproject, Resampling
    ndwi_resampled = np.zeros(sar_shape, dtype=np.float32)
    reproject(
        source=ndwi_arr,
        destination=ndwi_resampled,
        src_transform=s2_transform,
        src_crs=s2_crs,
        dst_transform=sar_transform,
        dst_crs=sar_crs,
        resampling=Resampling.bilinear
    )
    ndwi_arr = ndwi_resampled

# ── 5. Water mask (NDWI > 0) ─────────────────────────
s2_water = (ndwi_arr > 0.0).astype(np.uint8)
sar_water = (sar_mask == 1).astype(np.uint8)

# ── 6. Confusion matrix ──────────────────────────────
TP = np.sum((sar_water == 1) & (s2_water == 1))
TN = np.sum((sar_water == 0) & (s2_water == 0))
FP = np.sum((sar_water == 1) & (s2_water == 0))
FN = np.sum((sar_water == 0) & (s2_water == 1))

print(f"\nConfusion Matrix (SAR vs S2):")
print(f"  TP: {TP}, TN: {TN}, FP: {FP}, FN: {FN}")

# ── 7. Metrics ───────────────────────────────────────
eps = 1e-10
iou = TP / (TP + FP + FN + eps)
precision = TP / (TP + FP + eps)
recall = TP / (TP + FN + eps)
f1 = 2 * precision * recall / (precision + recall + eps)

print(f"\nMetrics (SAR vs S2 Optical):")
print(f"  IoU:       {iou:.4f}")
print(f"  F1 Score:  {f1:.4f}")
print(f"  Precision: {precision:.4f}")
print(f"  Recall:    {recall:.4f}")

# ── 8. Save ──────────────────────────────────────────
import json
results = {
    "iou": round(float(iou), 4),
    "f1": round(float(f1), 4),
    "precision": round(float(precision), 4),
    "recall": round(float(recall), 4),
    "TP": int(TP), "TN": int(TN), "FP": int(FP), "FN": int(FN),
    "reference": "Sentinel-2 NDWI (cross-sensor validation)"
}
with open('sar_data/validation_s2.json', 'w') as f:
    json.dump(results, f, indent=2)
print(f"\n✅ Metrics saved: sar_data/validation_s2.json")