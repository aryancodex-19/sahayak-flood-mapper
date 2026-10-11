"""
SAHAYAK — Step 10: Sentinel-1 SAR Download
Region: Kamrup, Assam
Event: June 2022 Floods
"""
import ee
import geemap
import os

# ── Config ───────────────────────────────────────────
PROJECT_ID = 'snappy-nomad-465705-b9'
ee.Initialize(project=PROJECT_ID)

# Kamrup, Assam bounding box
KAMRUP = ee.Geometry.Rectangle([91.0, 25.8, 92.0, 26.4])

# Date windows
PRE_START  = '2022-05-15'
PRE_END    = '2022-06-10'
POST_START = '2022-06-20'
POST_END   = '2022-07-05'

# Output folder
OUT_DIR = 'sar_data'
os.makedirs(OUT_DIR, exist_ok=True)

# ── Helper: Get S1 collection ────────────────────────
def get_s1(aoi, start, end):
    return (ee.ImageCollection('COPERNICUS/S1_GRD')
            .filterBounds(aoi)
            .filterDate(start, end)
            .filter(ee.Filter.eq('instrumentMode', 'IW'))
            .filter(ee.Filter.listContains('transmitterReceiverPolarisation', 'VV'))
            .filter(ee.Filter.eq('orbitProperties_pass', 'DESCENDING'))
            .select('VV'))

# ── Download pre-flood ───────────────────────────────
print("Downloading PRE-flood SAR...")
pre_col = get_s1(KAMRUP, PRE_START, PRE_END)
print(f"  Pre-flood images found: {pre_col.size().getInfo()}")

pre_median = pre_col.median().clip(KAMRUP)
pre_path = os.path.join(OUT_DIR, 'pre_flood_VV.tif')

geemap.ee_export_image(
    pre_median,
    filename=pre_path,
    scale=100,
    region=KAMRUP,
    file_per_band=False,
    crs='EPSG:4326'
)
print(f"  ✅ Saved: {pre_path}")

# ── Download post-flood ──────────────────────────────
print("\nDownloading POST-flood SAR...")
post_col = get_s1(KAMRUP, POST_START, POST_END)
print(f"  Post-flood images found: {post_col.size().getInfo()}")

post_median = post_col.median().clip(KAMRUP)
post_path = os.path.join(OUT_DIR, 'post_flood_VV.tif')

geemap.ee_export_image(
    post_median,
    filename=post_path,
    scale=100,
    region=KAMRUP,
    file_per_band=False,
    crs='EPSG:4326'
)
print(f"  ✅ Saved: {post_path}")

print("\n✅ STEP 10 COMPLETE — Pre + Post SAR downloaded!")