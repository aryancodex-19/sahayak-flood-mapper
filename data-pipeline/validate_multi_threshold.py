"""
SAHAYAK — Multi-threshold validation (SAR-based)
Different Otsu thresholds pe mask stable hai ya nahi check karo
"""
import rasterio
import numpy as np
from rasterio.features import shapes

# Load pre/post SAR
with rasterio.open('sar_data/pre_flood_VV.tif') as src:
    pre = src.read(1).astype(np.float32)
    transform = src.transform
    crs = src.crs

with rasterio.open('sar_data/post_flood_VV.tif') as src:
    post = src.read(1).astype(np.float32)

# Log-ratio
lr = post - pre

# Multiple thresholds
thresholds = [-2.5, -3.0, -3.34, -3.5, -4.0]

masks = []
for t in thresholds:
    m = (lr < t).astype(np.uint8)
    masks.append(m)
    print(f"Threshold {t} dB: {m.sum()} pixels ({m.sum()/m.size*100:.2f}%)")

# Agreement matrix
masks_arr = np.stack(masks, axis=0)  # (5, H, W)
agreement = masks_arr.mean(axis=0)   # 0.0 to 1.0

# Confidence stats
print(f"\nAgreement distribution:")
print(f"  Mean:   {agreement.mean():.3f}")
print(f"  Median: {np.median(agreement):.3f}")
print(f"  >0.8:   {(agreement > 0.8).sum()} pixels ({((agreement > 0.8).sum()/agreement.size*100):.2f}%)")
print(f"  >0.6:   {(agreement > 0.6).sum()} pixels")

# High-confidence flood = at least 4/5 thresholds agree
high_conf_flood = (agreement >= 0.8).astype(np.uint8)
print(f"\nHigh-confidence flood: {high_conf_flood.sum()} pixels ({high_conf_flood.sum()/high_conf_flood.size*100:.2f}%)")

# Save
profile = {
    'driver': 'GTiff', 'dtype': 'float32', 'count': 1,
    'width': lr.shape[1], 'height': lr.shape[0],
    'crs': crs, 'transform': transform, 'compress': 'lzw'
}
with rasterio.open('sar_data/multi_threshold_agreement.tif', 'w', **profile) as dst:
    dst.write(agreement, 1)
print("✅ Saved: multi_threshold_agreement.tif")

# Save metrics
import json
results = {
    "method": "Multi-threshold consistency",
    "thresholds": thresholds,
    "mean_agreement": round(float(agreement.mean()), 3),
    "high_conf_pixels": int((agreement > 0.8).sum()),
    "high_conf_pct": round(float((agreement > 0.8).sum() / agreement.size * 100), 2),
    "note": "Optical validation failed due to 51% cloud cover — SAR-based consistency validation"
}
with open('sar_data/validation_multi_threshold.json', 'w') as f:
    json.dump(results, f, indent=2)
print("✅ Metrics saved: validation_multi_threshold.json")