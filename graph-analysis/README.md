# Graph Analysis Module

Owner: Aryan
Purpose: Detect cut-off settlements using OSM road network + flood mask

## Files
- `download_network.py` — OSMnx se road network download
- `flood_overlay.py` — Flood mask overlay on roads
- `connectivity.py` — Cut-off detection
- `priority_ranking.py` — Priority scoring
- `main.py` — Integration script

## Output
- `cut_off_settlements.json`
- `priority_list.csv`
- `priority_list.geojson`