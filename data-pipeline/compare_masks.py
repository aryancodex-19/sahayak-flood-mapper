"""
SAHAYAK — Compare Otsu mask vs High-confidence mask
"""
import rasterio
import numpy as np

# Original Otsu mask
with rasterio.open('sar_data/flood_mask_20220620_filtered.tif') as src:
    otsu_mask = src.read(1)

# High-confidence mask (agreement >= 0.8)
with rasterio.open('sar_data/multi_threshold_agreement.tif') as src:
    agreement = src.read(1)

high_conf = (agreement >= 0.8).astype(np.uint8)

# Compare
otsu_count = otsu_mask.sum()
hc_count = high_conf.sum()
overlap = np.sum((otsu_mask == 1) & (high_conf == 1))

print(f"Otsu mask (filtered):       {otsu_count} pixels")
print(f"High-confidence mask:       {hc_count} pixels")
print(f"Overlap:                    {overlap} pixels")
print(f"Otsu pixels in HC zone:     {overlap/otsu_count*100:.2f}%")
print(f"HC pixels in Otsu:          {overlap/hc_count*100:.2f}%")

# Extra stats
otsu_only = np.sum((otsu_mask == 1) & (high_conf == 0))
hc_only = np.sum((otsu_mask == 0) & (high_conf == 1))

print(f"\nOtsu only (borderline):     {otsu_only} pixels")
print(f"HC only (missed by Otsu):   {hc_only} pixels")