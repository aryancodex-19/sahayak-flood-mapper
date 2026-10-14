"""
Unit tests for Experiment 01 (3-channel input, difference normalization, and augmentation).
"""

import unittest
from pathlib import Path
import numpy as np
import torch

# Ensure ml-model directory is in sys.path
TEST_DIR = Path(__file__).resolve().parent
REPO_ML_DIR = TEST_DIR.parent
import sys
if str(REPO_ML_DIR) not in sys.path:
    sys.path.insert(0, str(REPO_ML_DIR))

from scripts.train_exp01 import normalize_sar_diff_db, SAR3ChannelPatchDataset
from src.model import build_unet_model


class TestExperiment01(unittest.TestCase):
    def test_normalize_sar_diff_db(self):
        """Verify that difference channel normalization correctly scales and clips dB differences."""
        diff = np.array([-30.0, -20.0, -5.0, 10.0, 25.0, np.nan])
        invalid = np.isnan(diff)
        diff_clean = np.where(invalid, 0.0, diff)

        norm, stats = normalize_sar_diff_db(diff_clean, invalid, min_diff_db=-20.0, max_diff_db=10.0)

        # -30 should clip to 0.0
        self.assertAlmostEqual(norm[0], 0.0, places=4)
        # -20 should map to 0.0
        self.assertAlmostEqual(norm[1], 0.0, places=4)
        # -5 should map to (-5 - (-20)) / 30 = 15 / 30 = 0.5
        self.assertAlmostEqual(norm[2], 0.5, places=4)
        # 10 should map to 1.0
        self.assertAlmostEqual(norm[3], 1.0, places=4)
        # 25 should clip to 1.0
        self.assertAlmostEqual(norm[4], 1.0, places=4)
        # NaN pixel should be strictly 0.0
        self.assertAlmostEqual(norm[5], 0.0, places=4)

    def test_3channel_dataset_dimensions_and_channels(self):
        """Verify 3-channel dataset outputs [3, H, W] images and expected channel contracts."""
        H, W = 670, 1114
        pre = np.random.uniform(-25.0, -5.0, size=(H, W)).astype(np.float32)
        post = np.random.uniform(-25.0, -5.0, size=(H, W)).astype(np.float32)
        mask = np.random.binomial(1, 0.05, size=(H, W)).astype(np.uint8)

        # Train dataset with stride 128 (6 rows x 6 cols = 36 patches)
        ds_train = SAR3ChannelPatchDataset(
            pre_flood=pre,
            post_flood=post,
            target_mask=mask,
            split="train",
            patch_size=256,
            stride=128,
            augment=True,
        )
        self.assertEqual(len(ds_train), 36)

        item = ds_train[0]
        self.assertEqual(item["image"].shape, torch.Size([3, 256, 256]))
        self.assertEqual(item["target"].shape, torch.Size([1, 256, 256]))
        self.assertEqual(item["valid_mask"].shape, torch.Size([1, 256, 256]))

        # Validation dataset with stride 256 (6 patches)
        ds_val = SAR3ChannelPatchDataset(
            pre_flood=pre,
            post_flood=post,
            target_mask=mask,
            split="val",
            patch_size=256,
            stride=256,
            augment=False,
        )
        self.assertEqual(len(ds_val), 6)
        val_item = ds_val[0]
        self.assertEqual(val_item["image"].shape, torch.Size([3, 256, 256]))

    def test_3channel_model_forward(self):
        """Verify FloodUNet forward pass with in_channels=3."""
        model = build_unet_model(in_channels=3, classes=1, encoder_weights=None)
        x = torch.randn(2, 3, 256, 256)
        out = model(x)
        self.assertEqual(out.shape, torch.Size([2, 1, 256, 256]))
        self.assertTrue(torch.isfinite(out).all().item())


if __name__ == "__main__":
    unittest.main()
