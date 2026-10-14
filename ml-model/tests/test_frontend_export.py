"""
Unit Tests for Frontend ML Integration Data Artifacts and Contracts.
Validates:
1. Completeness and validity of all exported JSON/GeoJSON files.
2. Reconciliation of cut-off and connected settlement counts (20 + 0 + 84 = 104).
3. Coordinate bounds and geometric validity of flood prediction polygons.
4. Correctness of geodesic inundation area and provenance metadata.
5. Ranking consistency (top priority settlements match graph-analysis results).
"""

import unittest
import json
from pathlib import Path


class TestFrontendMLExport(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.repo_root = Path(__file__).resolve().parent.parent.parent
        cls.frontend_data_dir = cls.repo_root / "frontend/src/data"

        cls.files = {
            "cutoff": cls.frontend_data_dir / "ml_cutoff.json",
            "practical": cls.frontend_data_dir / "ml_practical.json",
            "connected": cls.frontend_data_dir / "ml_connected.json",
            "priority": cls.frontend_data_dir / "ml_priority.json",
            "flood": cls.frontend_data_dir / "ml_flood.json",
            "meta": cls.frontend_data_dir / "ml_meta.json",
        }

    def test_all_frontend_ml_files_exist(self):
        """Ensure all required ML data files exist and are non-empty."""
        for name, path in self.files.items():
            self.assertTrue(path.exists(), f"Missing exported frontend file: {name} at {path}")
            self.assertGreater(path.stat().st_size, 0, f"File is empty: {name}")

    def test_settlement_counts_and_reconciliation(self):
        """Ensure 20 strict cutoffs + 0 practical + 84 connected = 104 settlements total."""
        with open(self.files["cutoff"], encoding="utf-8") as f:
            cutoff_data = json.load(f)
        with open(self.files["practical"], encoding="utf-8") as f:
            practical_data = json.load(f)
        with open(self.files["connected"], encoding="utf-8") as f:
            connected_data = json.load(f)

        self.assertEqual(len(cutoff_data), 20, "Expected exactly 20 strict cut-offs")
        self.assertEqual(len(practical_data), 0, "Expected exactly 0 practical cut-offs")
        self.assertEqual(len(connected_data), 84, "Expected exactly 84 connected settlements")
        self.assertEqual(len(cutoff_data) + len(practical_data) + len(connected_data), 104, "Total settlements must reconcile to 104")

    def test_settlement_coordinate_bounds(self):
        """Ensure all settlement coordinates fall within Kamrup geographical bounds."""
        with open(self.files["cutoff"], encoding="utf-8") as f:
            cutoff_data = json.load(f)
        with open(self.files["connected"], encoding="utf-8") as f:
            connected_data = json.load(f)

        for item in cutoff_data + connected_data:
            lat = item.get("latitude")
            lon = item.get("longitude")
            self.assertIsNotNone(lat, f"Missing latitude for {item.get('name')}")
            self.assertIsNotNone(lon, f"Missing longitude for {item.get('name')}")
            self.assertTrue(25.5 <= lat <= 27.0, f"Latitude {lat} out of Kamrup bounds for {item.get('name')}")
            self.assertTrue(90.5 <= lon <= 92.5, f"Longitude {lon} out of Kamrup bounds for {item.get('name')}")

    def test_priority_ranking_consistency(self):
        """Verify priority list features match graph analysis ranking."""
        with open(self.files["priority"], encoding="utf-8") as f:
            priority_geojson = json.load(f)

        features = priority_geojson.get("features", [])
        self.assertEqual(len(features), 20, "Expected 20 ranked priority features")

        top_names = [f["properties"]["name"] for f in features[:3]]
        self.assertEqual(top_names, ["Amingaon", "Jalukbari", "Pandu"])
        for f in features[:3]:
            self.assertEqual(f["properties"]["score"], 76.32)
            self.assertEqual(f["properties"]["category"], "High")

    def test_flood_geojson_geometry(self):
        """Ensure flood GeoJSON contains valid polygons with positive areas."""
        with open(self.files["flood"], encoding="utf-8") as f:
            flood_geojson = json.load(f)

        self.assertEqual(flood_geojson.get("type"), "FeatureCollection")
        features = flood_geojson.get("features", [])
        self.assertGreater(len(features), 0, "Flood GeoJSON must contain features")

        for f in features:
            self.assertEqual(f.get("type"), "Feature")
            self.assertEqual(f["geometry"]["type"], "Polygon")
            self.assertGreater(len(f["geometry"]["coordinates"]), 0)
            self.assertGreater(f["properties"]["areaHectares"], 0)

    def test_provenance_metadata(self):
        """Ensure metadata clearly identifies experimental U-Net predictions."""
        with open(self.files["meta"], encoding="utf-8") as f:
            meta = json.load(f)

        self.assertEqual(meta.get("scenario_id"), "ml")
        self.assertTrue(meta.get("is_experimental"), "Must be explicitly marked experimental")
        self.assertEqual(meta.get("total_road_edges"), 20669)
        self.assertEqual(meta.get("flooded_road_edges"), 6306)
        self.assertEqual(meta.get("flooded_road_pct"), 30.51)
        self.assertEqual(meta.get("total_settlements"), 104)
        self.assertEqual(meta.get("strict_cutoff_count"), 20)
        self.assertIn("not been independently ground-truth validated", meta.get("disclaimer", ""))


if __name__ == "__main__":
    unittest.main()
