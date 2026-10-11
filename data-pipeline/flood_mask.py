"""
SAHAYAK — Step 11: Log-Ratio + Otsu Threshold
Input: sar_data/pre_flood_VV.tif, sar_data/post_flood_VV.tif
Output: flood_mask_20220620.tif (binary), confidence_map.tif
"""
import rasterio
import numpy as np
import cv2
import os

OUT_DIR = 'sar_data'
PRE = os.path.join(OUT_DIR, 'pre_flood_VV.tif')
POST = os.path.join(OUT_DIR, 'post_flood_VV.tif')

# ── 1. Read both images ──────────────────────────────
with rasterio.open(PRE) as src:
    pre = src.read(1).astype(np.float32)
    profile = src.profile.copy()
    transform = src.transform
    crs = src.crs

with rasterio.open(POST) as src:
    post = src.read(1).astype(np.float32)

print(f"Pre shape: {pre.shape}, range: [{np.nanmin(pre):.2f}, {np.nanmax(pre):.2f}]")
print(f"Post shape: {post.shape}, range: [{np.nanmin(post):.2f}, {np.nanmax(post):.2f}]")

# ── 2. Log-Ratio ─────────────────────────────────────
# LR = post_dB - pre_dB  (GEE S1_GRD already in dB)
# Flooded → post backscatter LOW → LR negative
lr = post - pre
print(f"\nLog-Ratio range: [{np.nanmin(lr):.2f}, {np.nanmax(lr):.2f}]")

# ── 3. Otsu Threshold ────────────────────────────────
# Normalize LR to 0-255 for OpenCV
lr_valid = lr[~np.isnan(lr)]
lr_norm = ((lr - lr_valid.min()) / (lr_valid.max() - lr_valid.min()) * 255).astype(np.uint8)
lr_norm = np.nan_to_num(lr_norm, nan=0)

otsu_thresh, _ = cv2.threshold(lr_norm, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
print(f"Otsu threshold (normalized): {otsu_thresh}")

# Convert back to dB
otsu_db = lr_valid.min() + (otsu_thresh / 255) * (lr_valid.max() - lr_valid.min())
print(f"Otsu threshold (dB): {otsu_db:.2f}")

# Flood = LR below Otsu (low backscatter = water)
flood_mask = (lr < otsu_db).astype(np.uint8)

# ── 4. Morphological cleanup ─────────────────────────
kernel = np.ones((3, 3), np.uint8)
flood_mask = cv2.morphologyEx(flood_mask, cv2.MORPH_OPEN, kernel)
flood_mask = cv2.morphologyEx(flood_mask, cv2.MORPH_CLOSE, kernel)

flood_pct = flood_mask.sum() / flood_mask.size * 100
print(f"\nFlooded pixels: {flood_mask.sum()} ({flood_pct:.2f}% of area)")

# ── 5. Save flood mask (GeoTIFF, EPSG:4326) ──────────
profile.update(dtype=rasterio.uint8, count=1, compress='lzw', nodata=0)
mask_path = os.path.join(OUT_DIR, 'flood_mask_20220620.tif')
with rasterio.open(mask_path, 'w', **profile) as dst:
    dst.write(flood_mask, 1)
print(f"✅ Saved: {mask_path}")

# ── 6. Confidence map (multi-threshold agreement) ────
m1 = (lr < otsu_db - 1.0).astype(np.float32)  # aggressive
m2 = (lr < otsu_db).astype(np.float32)         # standard
m3 = (lr < otsu_db + 1.0).astype(np.float32)   # conservative
confidence = (m1 + m2 + m3) / 3.0              # 0.0, 0.33, 0.67, 1.0

profile.update(dtype=rasterio.float32, count=1, nodata=0.0)
conf_path = os.path.join(OUT_DIR, 'flood_confidence_20220620.tif')
with rasterio.open(conf_path, 'w', **profile) as dst:
    dst.write(confidence, 1)
print(f"✅ Saved: {conf_path}")

print("\n✅ STEP 11 COMPLETE — Flood mask + Confidence map ready!")