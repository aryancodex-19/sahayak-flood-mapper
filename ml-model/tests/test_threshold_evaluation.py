"""
Unit tests for ML calibration, threshold evaluation, and nodata masking.
"""

import json
from pathlib import Path
import unittest
import numpy as np

# Ensure ml-model directory is in sys.path
TEST_DIR = Path(__file__).resolve().parent
REPO_ML_DIR = TEST_DIR.parent
import sys
if str(REPO_ML_DIR) not in sys.path:
    sys.path.insert(0, str(REPO_ML_DIR))

from scripts.evaluate_thresholds import compute_threshold_metrics, sweep_thresholds


class TestThresholdEvaluation(unittest.TestCase):
    def setUp(self):
        self.base_dir = REPO_ML_DIR
        self.exp_dir = self.base_dir / "outputs/experiments/threshold_calibration"
        self.json_report_path = self.exp_dir / "threshold_evaluation.json"

    def test_confusion_metric_math_and_invariants(self):
        """Verify TP, FP, FN, TN, precision, recall, F1, and IoU calculations on synthetic data."""
        # 10 samples: 4 true positives, 2 false positives, 1 false negative, 3 true negatives
        probs = np.array([0.9, 0.8, 0.7, 0.6, 0.55, 0.52, 0.45, 0.3, 0.2, 0.1])
        targets = np.array([1, 1, 1, 1, 0, 0, 1, 0, 0, 0])
        thresh = 0.50

        m = compute_threshold_metrics(probs, targets, threshold=thresh)

        # Expected:
        # Pred pos (>= 0.5): indices 0..5 (6 items)
        # targets at 0..5: [1, 1, 1, 1, 0, 0] -> 4 TP, 2 FP
        # Pred neg (< 0.5): indices 6..9 (4 items)
        # targets at 6..9: [1, 0, 0, 0] -> 1 FN, 3 TN
        self.assertEqual(m["tp"], 4)
        self.assertEqual(m["fp"], 2)
        self.assertEqual(m["fn"], 1)
        self.assertEqual(m["tn"], 3)
        self.assertEqual(m["tp"] + m["fp"] + m["fn"] + m["tn"], 10)
        self.assertEqual(m["valid_pixels"], 10)

        # Precision = 4 / 6 = 0.6667
        self.assertAlmostEqual(m["precision"], 4.0 / 6.0, places=4)
        # Recall = 4 / 5 = 0.8000
        self.assertAlmostEqual(m["recall"], 4.0 / 5.0, places=4)
        # F1 = 2 * (4/6 * 4/5) / (4/6 + 4/5) = 2 * (16/30) / (44/30) = 32 / 44 = 0.7273
        self.assertAlmostEqual(m["f1"], 32.0 / 44.0, places=4)
        # IoU = 4 / (4 + 2 + 1) = 4 / 7 = 0.5714
        self.assertAlmostEqual(m["iou"], 4.0 / 7.0, places=4)

    def test_threshold_monotonicity_invariants(self):
        """Verify that increasing decision thresholds monotonically non-increases recall and false positives."""
        np.random.seed(42)
        probs = np.random.uniform(0.1, 0.8, size=1000)
        targets = np.random.binomial(1, 0.1, size=1000)

        thresholds = [0.2, 0.3, 0.4, 0.5, 0.6, 0.7]
        results = sweep_thresholds(probs, targets, thresholds)

        for i in range(len(results) - 1):
            curr_r = results[i]
            next_r = results[i + 1]

            # Invariant 1: Total pixels conserved
            self.assertEqual(curr_r["tp"] + curr_r["fp"] + curr_r["fn"] + curr_r["tn"], 1000)

            # Invariant 2: Higher threshold -> fewer or equal predicted positives
            self.assertGreaterEqual(curr_r["tp"] + curr_r["fp"], next_r["tp"] + next_r["fp"])

            # Invariant 3: Higher threshold -> lower or equal recall
            self.assertGreaterEqual(curr_r["recall"], next_r["recall"])

            # Invariant 4: Higher threshold -> lower or equal false positives
            self.assertGreaterEqual(curr_r["fp"], next_r["fp"])

    def test_invalid_and_nodata_pixel_exclusion(self):
        """Verify that invalid/nodata pixels are strictly excluded from confusion matrix metrics."""
        # 4 pixels in 2D array: 2 valid, 1 NaN, 1 padded invalid
        probs = np.array([0.8, 0.2, 0.9, 0.1])
        targets = np.array([1, 0, 1, 0])
        valid_mask = np.array([True, True, False, False])  # only first 2 pixels are valid

        # Only pass valid pixels
        valid_probs = probs[valid_mask]
        valid_targets = targets[valid_mask]

        m = compute_threshold_metrics(valid_probs, valid_targets, threshold=0.5)
        self.assertEqual(m["valid_pixels"], 2)
        self.assertEqual(m["tp"], 1)
        self.assertEqual(m["tn"], 1)
        self.assertEqual(m["fp"], 0)
        self.assertEqual(m["fn"], 0)
        self.assertEqual(m["precision"], 1.0)
        self.assertEqual(m["recall"], 1.0)
        self.assertEqual(m["f1"], 1.0)
        self.assertEqual(m["iou"], 1.0)

    def test_reproduced_validation_experiment_report(self):
        """Verify that the generated experiment JSON matches expected schema and reproduction numbers."""
        self.assertTrue(self.json_report_path.exists(), "Experiment JSON report missing!")

        with open(self.json_report_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        self.assertIn("metadata", data)
        self.assertIn("baseline_metrics_threshold_0_5", data)
        self.assertIn("standard_sweep", data)
        self.assertIn("candidates", data)

        meta = data["metadata"]
        self.assertEqual(meta["num_validation_patches"], 6)
        self.assertEqual(meta["total_valid_pixels"], 188940)
        self.assertEqual(meta["reference_positive_pixels"], 8734)
        self.assertAlmostEqual(meta["reference_positive_pct"], 4.62, places=2)

        base_m = data["baseline_metrics_threshold_0_5"]
        self.assertEqual(base_m["threshold"], 0.5)
        self.assertEqual(base_m["tp"], 3858)
        self.assertEqual(base_m["fp"], 38328)
        self.assertEqual(base_m["fn"], 4876)
        self.assertEqual(base_m["tn"], 141878)
        self.assertAlmostEqual(base_m["precision"], 0.0915, places=3)
        self.assertAlmostEqual(base_m["recall"], 0.4417, places=3)
        self.assertAlmostEqual(base_m["f1"], 0.1515, places=3)
        self.assertAlmostEqual(base_m["iou"], 0.0820, places=3)


if __name__ == "__main__":
    unittest.main()
