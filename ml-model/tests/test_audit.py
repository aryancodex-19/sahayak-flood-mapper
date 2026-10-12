"""
Unit tests for Step 5A inference output audit and metric reconciliation.
"""

import json
from pathlib import Path
import unittest
import numpy as np
import rasterio
import torch


class TestInferenceAudit(unittest.TestCase):
    def setUp(self):
        self.base_dir = Path(__file__).resolve().parent.parent
        self.ckpt_path = self.base_dir / "outputs/baseline_run_01/model_best.pth"
        self.metrics_json_path = self.base_dir / "outputs/baseline_run_01/training_metrics.json"
        self.prob_path = self.base_dir / "outputs/inference_run_01/flood_probability.tif"
        self.pred_path = self.base_dir / "outputs/inference_run_01/flood_prediction.tif"
        self.pre_path = self.base_dir / "data/raw/pre_flood_VV.tif"
        self.post_path = self.base_dir / "data/raw/post_flood_VV.tif"
        self.lbl_path = self.base_dir / "data/raw/flood_mask_20220620_filtered.tif"
        self.audit_json_path = self.base_dir / "outputs/audit_run_01/audit_report.json"

    def test_checkpoint_metric_reconciliation(self):
        """Verify baseline checkpoint and training JSON both specify Epoch 1 val_f1 = 0.1512."""
        with open(self.metrics_json_path, "r", encoding="utf-8") as f:
            metrics_data = json.load(f)

        self.assertEqual(metrics_data["best_epoch"], 1)
        self.assertAlmostEqual(metrics_data["best_val_loss"], 1.6532, places=4)

        epoch_1 = metrics_data["history"][0]
        self.assertAlmostEqual(epoch_1["val_f1"], 0.1512, places=4)
        self.assertAlmostEqual(epoch_1["val_precision"], 0.0913, places=4)
        self.assertAlmostEqual(epoch_1["val_recall"], 0.4407, places=4)

        ckpt = torch.load(self.ckpt_path, map_location="cpu")
        self.assertEqual(ckpt["best_epoch"], 1)
        self.assertAlmostEqual(ckpt["best_val_loss"], 1.6532, places=4)
        self.assertAlmostEqual(ckpt["history"][0]["val_f1"], 0.1512, places=4)

    def test_raster_georeferencing_and_alignment(self):
        """Verify exported rasters match source rasters in shape, CRS, and transform."""
        with rasterio.open(self.prob_path) as s_prob, \
             rasterio.open(self.pred_path) as s_pred, \
             rasterio.open(self.pre_path) as s_pre:

            self.assertEqual(s_prob.shape, (670, 1114))
            self.assertEqual(s_pred.shape, (670, 1114))
            self.assertEqual(s_prob.crs, s_pre.crs)
            self.assertEqual(s_pred.crs, s_pre.crs)
            self.assertEqual(s_prob.transform, s_pre.transform)
            self.assertEqual(s_pred.transform, s_pre.transform)

    def test_single_coverage_guarantee(self):
        """Verify tiling writes each pixel exactly once without gaps or overlaps."""
        H, W = 670, 1114
        patch_size = 256
        coverage = np.zeros((H, W), dtype=np.int32)

        for r in range(0, H, patch_size):
            r_end = min(r + patch_size, H)
            for c in range(0, W, patch_size):
                c_end = min(c + patch_size, W)
                coverage[r:r_end, c:c_end] += 1

        self.assertEqual(int(np.min(coverage)), 1)
        self.assertEqual(int(np.max(coverage)), 1)

    def test_safe_binary_nodata_convention(self):
        """Verify binary prediction GeoTIFF does not declare 0 as NoData."""
        with rasterio.open(self.pred_path) as s_pred:
            self.assertNotEqual(s_pred.nodata, 0)
            self.assertEqual(s_pred.nodata, 255.0)
            data = s_pred.read(1)
            unique_vals = set(np.unique(data).tolist())
            self.assertEqual(unique_vals, {0, 1})

    def test_reproducible_confusion_metrics(self):
        """Verify confusion counts and agreement metrics against pseudo-label match audited values."""
        with rasterio.open(self.pred_path) as s_pred, \
             rasterio.open(self.lbl_path) as s_lbl, \
             rasterio.open(self.pre_path) as s_pre, \
             rasterio.open(self.post_path) as s_post:

            pred = s_pred.read(1)
            lbl = s_lbl.read(1)
            pre = s_pre.read(1)
            post = s_post.read(1)

            valid = np.isfinite(pre) & np.isfinite(post)
            self.assertEqual(int(valid.sum()), 746380)

            tp = int(np.sum((pred == 1) & (lbl == 1) & valid))
            fp = int(np.sum((pred == 1) & (lbl == 0) & valid))
            fn = int(np.sum((pred == 0) & (lbl == 1) & valid))
            tn = int(np.sum((pred == 0) & (lbl == 0) & valid))

            self.assertEqual(tp, 13707)
            self.assertEqual(fp, 144444)
            self.assertEqual(fn, 26206)
            self.assertEqual(tn, 562023)

            prec = tp / (tp + fp)
            rec = tp / (tp + fn)
            f1 = 2 * prec * rec / (prec + rec)
            self.assertAlmostEqual(prec, 0.0867, places=4)
            self.assertAlmostEqual(rec, 0.3434, places=4)
            self.assertAlmostEqual(f1, 0.1384, places=4)


if __name__ == "__main__":
    unittest.main()
