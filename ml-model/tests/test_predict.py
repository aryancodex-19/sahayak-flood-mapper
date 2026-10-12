"""
Unit tests for full-scene inference and georeferenced prediction pipeline.
"""

import unittest
from pathlib import Path
import numpy as np
import torch
import rasterio

from src.model import build_unet_model
from scripts.predict import predict_full_raster


class TestPredictPipeline(unittest.TestCase):
    """Test suite for full-scene tiled inference and export logic."""

    def setUp(self):
        torch.manual_seed(42)
        np.random.seed(42)

        # Synthetic non-divisible dimensions (e.g. 300 x 400)
        self.height = 300
        self.width = 400

        self.pre_arr = np.random.uniform(-30.0, 5.0, size=(self.height, self.width)).astype(np.float32)
        self.post_arr = np.random.uniform(-30.0, 5.0, size=(self.height, self.width)).astype(np.float32)

        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        self.model = build_unet_model(in_channels=2, classes=1, encoder_weights=None)
        self.model.to(self.device)
        self.model.eval()

    def test_predict_full_raster_dimensions(self):
        """Verify output shapes match non-divisible input dimensions exactly."""
        prob_map, pred_map, stats = predict_full_raster(
            model=self.model,
            pre_arr=self.pre_arr,
            post_arr=self.post_arr,
            device=self.device,
            patch_size=256,
            batch_size=2,
            threshold=0.5,
        )

        self.assertEqual(prob_map.shape, (self.height, self.width))
        self.assertEqual(pred_map.shape, (self.height, self.width))
        self.assertEqual(stats["uncovered_pixels"], 0)
        self.assertEqual(stats["duplicate_pixels"], 0)

    def test_predict_probability_bounds(self):
        """Verify all predicted probabilities are finite and strictly in [0.0, 1.0]."""
        prob_map, _, _ = predict_full_raster(
            model=self.model,
            pre_arr=self.pre_arr,
            post_arr=self.post_arr,
            device=self.device,
            patch_size=256,
        )

        self.assertTrue(np.isfinite(prob_map).all())
        self.assertGreaterEqual(float(np.min(prob_map)), 0.0)
        self.assertLessEqual(float(np.max(prob_map)), 1.0)

    def test_predict_binary_values(self):
        """Verify binary prediction map contains only 0 and 1."""
        _, pred_map, _ = predict_full_raster(
            model=self.model,
            pre_arr=self.pre_arr,
            post_arr=self.post_arr,
            device=self.device,
            patch_size=256,
        )

        unique_vals = np.unique(pred_map)
        for u in unique_vals:
            self.assertIn(u, [0, 1])

    def test_threshold_monotonicity(self):
        """Verify that increasing threshold decreases or maintains predicted flood pixels."""
        _, pred_low, _ = predict_full_raster(
            model=self.model,
            pre_arr=self.pre_arr,
            post_arr=self.post_arr,
            device=self.device,
            threshold=0.2,
        )
        _, pred_high, _ = predict_full_raster(
            model=self.model,
            pre_arr=self.pre_arr,
            post_arr=self.post_arr,
            device=self.device,
            threshold=0.8,
        )

        count_low = np.sum(pred_low == 1)
        count_high = np.sum(pred_high == 1)
        self.assertGreaterEqual(count_low, count_high)

    def test_shape_mismatch_rejection(self):
        """Verify that mismatched pre and post raster dimensions raise ValueError."""
        wrong_post = np.zeros((200, 200), dtype=np.float32)
        with self.assertRaises(ValueError):
            predict_full_raster(
                model=self.model,
                pre_arr=self.pre_arr,
                post_arr=wrong_post,
                device=self.device,
            )


if __name__ == "__main__":
    unittest.main()
