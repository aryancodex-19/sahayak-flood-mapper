"""
Unit tests for the SAHAYAK Dataset and Preprocessing module.
"""

import unittest
from pathlib import Path
import numpy as np
import torch

from src.dataset import (
    normalize_sar_db,
    generate_patch_coordinates,
    SARPatchDataset,
)


class TestSARPatchDataset(unittest.TestCase):
    """Test suite for SAR dataset, preprocessing, normalization, and patch tiling."""

    def setUp(self):
        # Create reproducible synthetic arrays mimicking Kamrup raster shape (670, 1114)
        np.random.seed(42)
        self.height = 670
        self.width = 1114

        # Synthetic SAR backscatter in typical dB range [-35 dB, +15 dB]
        self.pre_flood = np.random.uniform(-35.0, 15.0, size=(self.height, self.width)).astype(np.float32)
        self.post_flood = np.random.uniform(-35.0, 15.0, size=(self.height, self.width)).astype(np.float32)

        # Synthetic binary mask (mostly 0 with ~5% flood)
        self.target_mask = (np.random.rand(self.height, self.width) < 0.05).astype(np.uint8)

    def test_normalization_and_clipping(self):
        """Verify dB normalization to [0, 1] and clipping statistics."""
        test_arr = np.array([-40.0, -30.0, -15.0, 0.0, 10.0], dtype=np.float32)
        norm, stats = normalize_sar_db(test_arr, min_db=-30.0, max_db=0.0)

        # Expected: -40 -> 0.0, -30 -> 0.0, -15 -> 0.5, 0.0 -> 1.0, 10.0 -> 1.0
        expected = np.array([0.0, 0.0, 0.5, 1.0, 1.0], dtype=np.float32)
        np.testing.assert_allclose(norm, expected, atol=1e-5)

        self.assertGreater(stats["pct_clipped_below"], 0.0)
        self.assertGreater(stats["pct_clipped_above"], 0.0)
        self.assertEqual(stats["invalid_count"], 0)

    def test_invalid_pixels_handling(self):
        """Verify that NaN and Inf values are safely clamped to 0.0 and reported."""
        test_arr = np.array([-20.0, np.nan, -10.0, np.inf], dtype=np.float32)
        norm, stats = normalize_sar_db(test_arr, min_db=-30.0, max_db=0.0)

        self.assertEqual(stats["invalid_count"], 2)
        self.assertTrue(np.isfinite(norm).all())
        self.assertEqual(norm[1], 0.0)
        self.assertEqual(norm[3], 0.0)

    def test_shapes_and_types(self):
        """Verify patch tensor shapes and datatypes."""
        ds = SARPatchDataset(
            pre_flood=self.pre_flood,
            post_flood=self.post_flood,
            target_mask=self.target_mask,
            split="train",
            patch_size=256,
        )

        self.assertGreater(len(ds), 0)
        sample = ds[0]

        # Expected shapes: image [2, 256, 256], target [1, 256, 256], valid_mask [1, 256, 256]
        self.assertEqual(sample["image"].shape, (2, 256, 256))
        self.assertEqual(sample["target"].shape, (1, 256, 256))
        self.assertEqual(sample["valid_mask"].shape, (1, 256, 256))

        self.assertEqual(sample["image"].dtype, torch.float32)
        self.assertEqual(sample["target"].dtype, torch.float32)
        self.assertEqual(sample["valid_mask"].dtype, torch.bool)

    def test_channel_order(self):
        """Verify channel 0 corresponds to pre-flood and channel 1 to post-flood."""
        pre = np.full((670, 1114), -15.0, dtype=np.float32)  # -15 dB maps to 0.5
        post = np.full((670, 1114), 0.0, dtype=np.float32)    # 0 dB maps to 1.0
        mask = np.zeros((670, 1114), dtype=np.uint8)

        ds = SARPatchDataset(pre, post, mask, split="train", patch_size=256)
        sample = ds[0]

        np.testing.assert_allclose(sample["image"][0, :100, :100].numpy(), 0.5, atol=1e-5)
        np.testing.assert_allclose(sample["image"][1, :100, :100].numpy(), 1.0, atol=1e-5)

    def test_binary_labels(self):
        """Verify target mask contains strictly 0.0 and 1.0 values."""
        ds = SARPatchDataset(
            self.pre_flood, self.post_flood, self.target_mask,
            split="train", patch_size=256
        )
        sample = ds[0]
        unique_vals = torch.unique(sample["target"])
        for v in unique_vals:
            self.assertIn(v.item(), [0.0, 1.0])

    def test_edge_padding_validity_mask(self):
        """Verify that padded boundary regions have valid_mask set to False."""
        ds = SARPatchDataset(
            self.pre_flood, self.post_flood, self.target_mask,
            split="train", patch_size=256
        )

        # Find a patch that touches the bottom edge (row_end > 670)
        found_edge = False
        for i in range(len(ds)):
            sample = ds[i]
            r_start = sample["r_start"].item()
            r_end = sample["r_end"].item()
            if r_end > self.height:
                found_edge = True
                valid_rows = self.height - r_start
                # Real pixels up to valid_rows should be True
                self.assertTrue(sample["valid_mask"][0, :valid_rows, :256].all())
                # Padded pixels past valid_rows must be False
                self.assertFalse(sample["valid_mask"][0, valid_rows:, :256].any())
                # Padded image pixels must be 0.0
                self.assertEqual(sample["image"][:, valid_rows:, :].sum().item(), 0.0)
                break

        self.assertTrue(found_edge, "Did not find a bottom-edge patch to test padding validity.")

    def test_spatial_separation_no_overlap(self):
        """Verify that Train and Validation spatial regions are strictly disjoint with guard band."""
        train_boundary = 768
        guard_band = 64

        ds_train = SARPatchDataset(
            self.pre_flood, self.post_flood, self.target_mask,
            split="train", patch_size=256,
            train_col_boundary=train_boundary,
            guard_band_pixels=guard_band,
        )
        ds_val = SARPatchDataset(
            self.pre_flood, self.post_flood, self.target_mask,
            split="val", patch_size=256,
            train_col_boundary=train_boundary,
            guard_band_pixels=guard_band,
        )

        self.assertGreater(len(ds_train), 0)
        self.assertGreater(len(ds_val), 0)

        # Check all train patches stay strictly <= train_boundary
        for i in range(len(ds_train)):
            c_end = ds_train[i]["c_end"].item()
            self.assertLessEqual(c_end, train_boundary)

        # Check all val patches start strictly >= train_boundary + guard_band
        min_val_start = train_boundary + guard_band
        for i in range(len(ds_val)):
            c_start = ds_val[i]["c_start"].item()
            self.assertGreaterEqual(c_start, min_val_start)

    def test_deterministic_behavior(self):
        """Verify that accessing the same patch index repeatedly returns identical values."""
        ds = SARPatchDataset(
            self.pre_flood, self.post_flood, self.target_mask,
            split="train", patch_size=256
        )
        sample1 = ds[0]
        sample2 = ds[0]
        self.assertTrue(torch.equal(sample1["image"], sample2["image"]))
        self.assertTrue(torch.equal(sample1["target"], sample2["target"]))
        self.assertTrue(torch.equal(sample1["valid_mask"], sample2["valid_mask"]))

    def test_mismatched_dimensions(self):
        """Verify that mismatched input shapes raise ValueError."""
        wrong_pre = np.zeros((100, 100), dtype=np.float32)
        wrong_post = np.zeros((200, 200), dtype=np.float32)
        mask = np.zeros((100, 100), dtype=np.uint8)

        with self.assertRaises(ValueError):
            SARPatchDataset(wrong_pre, wrong_post, mask)

    def test_real_geotiffs_integration(self):
        """Integration check with real GeoTIFF files if they exist in data/raw."""
        base_dir = Path(__file__).resolve().parent.parent
        raw_dir = base_dir / "data" / "raw"

        pre_path = raw_dir / "pre_flood_VV.tif"
        post_path = raw_dir / "post_flood_VV.tif"
        mask_path = raw_dir / "flood_mask_20220620_filtered.tif"

        if not (pre_path.exists() and post_path.exists() and mask_path.exists()):
            self.skipTest("Real GeoTIFF files not found in data/raw; skipping integration test.")

        # Load train dataset from real GeoTIFFs
        ds_train = SARPatchDataset.from_geotiffs(
            pre_flood_path=pre_path,
            post_flood_path=post_path,
            mask_path=mask_path,
            split="train",
            patch_size=256,
        )
        ds_val = SARPatchDataset.from_geotiffs(
            pre_flood_path=pre_path,
            post_flood_path=post_path,
            mask_path=mask_path,
            split="val",
            patch_size=256,
        )

        print(f"\n[Real Rasters Integration] Train patches: {len(ds_train)} | Val patches: {len(ds_val)}")
        print(f"[Real Rasters Stats] Pre-flood clipped below: {ds_train.pre_stats['pct_clipped_below']:.2f}% | above: {ds_train.pre_stats['pct_clipped_above']:.2f}%")
        print(f"[Real Rasters Stats] Post-flood clipped below: {ds_train.post_stats['pct_clipped_below']:.2f}% | above: {ds_train.post_stats['pct_clipped_above']:.2f}%")

        self.assertGreater(len(ds_train), 0)
        self.assertGreater(len(ds_val), 0)

        # Check sample
        s = ds_train[0]
        self.assertEqual(s["image"].shape, (2, 256, 256))
        self.assertEqual(s["target"].shape, (1, 256, 256))
        self.assertEqual(s["valid_mask"].shape, (1, 256, 256))


if __name__ == "__main__":
    unittest.main()
