"""
Unit tests for SAHAYAK Loss functions and Valid-pixel Metrics.
"""

import unittest
import torch

from src.losses import (
    MaskedBCEWithLogitsLoss,
    MaskedDiceLoss,
    CombinedFloodLoss,
    compute_valid_metrics,
)


class TestLossesAndMetrics(unittest.TestCase):
    """Test suite for masked losses and valid-pixel metrics."""

    def setUp(self):
        torch.manual_seed(42)
        self.B, self.C, self.H, self.W = 2, 1, 64, 64
        self.logits = torch.randn(self.B, self.C, self.H, self.W, requires_grad=True)
        self.targets = (torch.rand(self.B, self.C, self.H, self.W) > 0.8).float()
        self.valid_mask = torch.ones(self.B, self.C, self.H, self.W, dtype=torch.bool)

    def test_masked_bce_ignores_invalid_pixels(self):
        """Verify that altering invalid pixel logits does not change BCE loss."""
        loss_fn = MaskedBCEWithLogitsLoss()

        # Set lower half to invalid
        mask = self.valid_mask.clone()
        mask[:, :, 32:, :] = False

        loss1 = loss_fn(self.logits, self.targets, mask)

        # Alter logits strictly in the invalid region
        altered_logits = self.logits.clone().detach()
        altered_logits[:, :, 32:, :] += 1000.0
        loss2 = loss_fn(altered_logits, self.targets, mask)

        self.assertAlmostEqual(loss1.item(), loss2.item(), places=5)

    def test_masked_dice_ignores_invalid_pixels(self):
        """Verify that altering invalid pixel logits does not change Dice loss."""
        loss_fn = MaskedDiceLoss()

        mask = self.valid_mask.clone()
        mask[:, :, 32:, :] = False

        loss1 = loss_fn(self.logits, self.targets, mask)

        altered_logits = self.logits.clone().detach()
        altered_logits[:, :, 32:, :] += 500.0
        loss2 = loss_fn(altered_logits, self.targets, mask)

        self.assertAlmostEqual(loss1.item(), loss2.item(), places=5)

    def test_combined_loss_backward_pass(self):
        """Verify combined loss produces finite gradients."""
        loss_fn = CombinedFloodLoss(bce_weight=1.0, dice_weight=1.0, pos_weight=5.0)
        total_loss, metrics = loss_fn(self.logits, self.targets, self.valid_mask)

        self.assertTrue(torch.isfinite(total_loss))
        self.assertGreater(metrics["loss_total"], 0.0)

        total_loss.backward()
        self.assertIsNotNone(self.logits.grad)
        self.assertTrue(torch.isfinite(self.logits.grad).all())

    def test_zero_valid_pixels_safety(self):
        """Verify that a patch with zero valid pixels does not raise ZeroDivisionError."""
        loss_fn = CombinedFloodLoss()
        empty_mask = torch.zeros(self.B, self.C, self.H, self.W, dtype=torch.bool)

        loss, metrics = loss_fn(self.logits, self.targets, empty_mask)
        self.assertEqual(loss.item(), 0.0)

        metrics_dict = compute_valid_metrics(self.logits, self.targets, empty_mask)
        self.assertEqual(metrics_dict["valid_pixels"], 0)
        self.assertEqual(metrics_dict["iou"], 0.0)

    def test_compute_valid_metrics_perfect_prediction(self):
        """Verify metrics give 1.0 on identical predictions."""
        # High positive logits (>10) map to prob ~ 1.0; low negative logits (<-10) map to prob ~ 0.0
        exact_logits = torch.where(self.targets == 1.0, 10.0, -10.0)
        m = compute_valid_metrics(exact_logits, self.targets, self.valid_mask, threshold=0.5)

        self.assertAlmostEqual(m["precision"], 1.0, places=4)
        self.assertAlmostEqual(m["recall"], 1.0, places=4)
        self.assertAlmostEqual(m["f1"], 1.0, places=4)
        self.assertAlmostEqual(m["iou"], 1.0, places=4)


if __name__ == "__main__":
    unittest.main()
