import rasterio
import numpy as np

with rasterio.open('sar_data/flood_mask_20220620.tif') as src:
    mask = src.read(1)
    print(f"Shape: {mask.shape}")
    print(f"CRS: {src.crs}")          # EPSG:4326 hona chahiye
    print(f"Bounds: {src.bounds}")
    print(f"Flood pixels: {mask.sum()}")
    print(f"Flood %: {mask.sum()/mask.size*100:.2f}%")
    print(f"Unique values: {np.unique(mask)}")  # 0 aur 1 hona chahiye