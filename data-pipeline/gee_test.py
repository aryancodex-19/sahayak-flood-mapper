import ee

# Project ID — Ravi ke screenshot se (b9, NOT h9)
PROJECT_ID = 'snappy-nomad-465705-b9'
ee.Initialize(project=PROJECT_ID)

# Kamrup, Assam
kamrup = ee.Geometry.Rectangle([91.0, 25.8, 92.0, 26.4])

# Sentinel-1 collection
s1 = (ee.ImageCollection('COPERNICUS/S1_GRD')
      .filterBounds(kamrup)
      .filterDate('2022-06-01', '2022-06-30')
      .filter(ee.Filter.eq('instrumentMode', 'IW'))
      .filter(ee.Filter.listContains('transmitterReceiverPolarisation', 'VV'))
      .filter(ee.Filter.eq('orbitProperties_pass', 'DESCENDING'))
      .select('VV'))

count = s1.size().getInfo()
first_id = s1.first().get('system:index').getInfo()

print(f"Project: {PROJECT_ID}")
print(f"Total images: {count}")
print(f"First image: {first_id}")
print("✅ Python GEE authentication SUCCESS!")