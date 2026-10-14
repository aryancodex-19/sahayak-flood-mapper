"""
SAHAYAK Flood Mapper — Experiment 01: Controlled ML Improvement Runner

Experimental Configuration:
- Inputs: 3 channels [pre_flood_VV, post_flood_VV, post_minus_pre_diff_dB]
- Difference Channel Normalization: np.clip((diff - (-20.0)) / (10.0 - (-20.0)), 0.0, 1.0)
- Training Stride: 128 (yielding 25 training patches within cols [0, 768))
- Validation Stride: 256 (yielding identical 6 held-out patches within cols [832, 1114))
- Augmentation: Random horizontal & vertical flips (training only)
- Architecture: U-Net with ResNet34 backbone, in_channels=3, classes=1, random weights
- Epochs: 20
- Optimizer: AdamW (lr=2e-4, weight_decay=1e-2) with CosineAnnealingLR (eta_min=1e-6)
- Loss: Combined BCE + Dice loss with pos_weight=3.0
- Checkpoint Selection: Highest validation F1 at threshold 0.50

All artifacts are saved strictly into ml-model/outputs/experiments/exp01_diff_channel/.
Baseline model weights (outputs/baseline_run_01/model_best.pth) and frontend artifacts
are completely untouched.
"""

import sys
import os
import argparse
import json
import time
import random
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple
import numpy as np
import torch
import torch.nn as nn
from torch.utils.data import Dataset, DataLoader
import rasterio

# Ensure UTF-8 output encoding on Windows console
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

# Ensure ml-model directory is in sys.path
SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ML_DIR = SCRIPT_DIR.parent
if str(REPO_ML_DIR) not in sys.path:
    sys.path.insert(0, str(REPO_ML_DIR))

from src.dataset import normalize_sar_db, generate_patch_coordinates
from src.model import build_unet_model, FloodUNet
from src.losses import CombinedFloodLoss, compute_valid_metrics


def normalize_sar_diff_db(
    diff_arr: np.ndarray,
    invalid_mask: np.ndarray,
    min_diff_db: float = -20.0,
    max_diff_db: float = 10.0,
) -> Tuple[np.ndarray, Dict[str, float]]:
    """
    Normalizes physical SAR dB difference (post - pre) to [0.0, 1.0].

    Formula:
        diff_norm = np.clip((clean_diff - min_diff_db) / (max_diff_db - min_diff_db), 0.0, 1.0)
    """
    clean_diff = np.where(invalid_mask, min_diff_db, diff_arr)
    diff_norm = np.clip((clean_diff - min_diff_db) / (max_diff_db - min_diff_db), 0.0, 1.0).astype(np.float32)
    diff_norm[invalid_mask] = 0.0

    stats = {
        "min_diff_db": min_diff_db,
        "max_diff_db": max_diff_db,
        "total_pixels": int(diff_arr.size),
        "invalid_count": int(np.sum(invalid_mask)),
        "clipped_below_pct": float(np.sum(clean_diff < min_diff_db) / diff_arr.size * 100.0),
        "clipped_above_pct": float(np.sum(clean_diff > max_diff_db) / diff_arr.size * 100.0),
    }
    return diff_norm, stats


class SAR3ChannelPatchDataset(Dataset):
    """
    3-Channel Dataset for Sentinel-1 Pre-flood, Post-flood, and Difference imagery.

    Channels:
        0: Pre-flood VV (normalized [0, 1])
        1: Post-flood VV (normalized [0, 1])
        2: Difference (Post - Pre in dB, normalized [0, 1])
    """

    def __init__(
        self,
        pre_flood: np.ndarray,
        post_flood: np.ndarray,
        target_mask: np.ndarray,
        split: str = "train",
        patch_size: int = 256,
        stride: Optional[int] = None,
        train_col_boundary: int = 768,
        guard_band_pixels: int = 64,
        min_db: float = -30.0,
        max_db: float = 0.0,
        min_diff_db: float = -20.0,
        max_diff_db: float = 10.0,
        augment: bool = False,
        seed: int = 42,
    ):
        if pre_flood.shape != post_flood.shape or pre_flood.shape != target_mask.shape:
            raise ValueError(f"Shape mismatch: {pre_flood.shape}, {post_flood.shape}, {target_mask.shape}")

        self.height, self.width = pre_flood.shape
        self.patch_size = patch_size
        self.split = split.lower()
        self.augment = augment and (self.split == "train")
        self.seed = seed

        # Detect invalid pixels
        self.invalid_mask = np.isnan(pre_flood) | np.isinf(pre_flood) | np.isnan(post_flood) | np.isinf(post_flood)
        self.src_valid = ~self.invalid_mask

        # Normalize Channel 0 & Channel 1
        self.pre_norm, _ = normalize_sar_db(pre_flood, min_db=min_db, max_db=max_db)
        self.post_norm, _ = normalize_sar_db(post_flood, min_db=min_db, max_db=max_db)

        # Compute Channel 2: Physical dB Difference (post - pre)
        raw_diff = post_flood - pre_flood
        self.diff_norm, self.diff_stats = normalize_sar_diff_db(
            raw_diff, self.invalid_mask, min_diff_db=min_diff_db, max_diff_db=max_diff_db
        )

        # Target mask (0 = dry, 1 = flood)
        self.target = (target_mask == 1).astype(np.float32)

        # Spatial splitting
        val_col_start = train_col_boundary + guard_band_pixels
        self.train_bounds = {"col_min": 0, "col_max": train_col_boundary}
        self.guard_bounds = {"col_min": train_col_boundary, "col_max": val_col_start}
        self.val_bounds = {"col_min": val_col_start, "col_max": self.width}

        if self.split == "train":
            train_stride = stride if stride is not None else patch_size
            self.patch_coords = generate_patch_coordinates(
                height=self.height,
                width=self.width,
                patch_size=patch_size,
                stride=train_stride,
                col_min=self.train_bounds["col_min"],
                col_max=self.train_bounds["col_max"],
            )
        elif self.split == "val":
            val_stride = patch_size  # Strictly non-overlapping for validation
            self.patch_coords = generate_patch_coordinates(
                height=self.height,
                width=self.width,
                patch_size=patch_size,
                stride=val_stride,
                col_min=self.val_bounds["col_min"],
                col_max=self.val_bounds["col_max"],
            )
        else:
            raise ValueError(f"Unknown split: {split}")

    def __len__(self) -> int:
        return len(self.patch_coords)

    def __getitem__(self, idx: int) -> Dict[str, torch.Tensor]:
        coord = self.patch_coords[idx]
        r_start, r_end = coord["r_start"], coord["r_end"]
        c_start, c_end = coord["c_start"], coord["c_end"]

        src_r_end = min(r_end, self.height)
        src_c_end = min(c_end, self.width)
        h_valid = src_r_end - r_start
        w_valid = src_c_end - c_start

        image_patch = np.zeros((3, self.patch_size, self.patch_size), dtype=np.float32)
        target_patch = np.zeros((1, self.patch_size, self.patch_size), dtype=np.float32)
        valid_patch = np.zeros((1, self.patch_size, self.patch_size), dtype=bool)

        if h_valid > 0 and w_valid > 0:
            image_patch[0, :h_valid, :w_valid] = self.pre_norm[r_start:src_r_end, c_start:src_c_end]
            image_patch[1, :h_valid, :w_valid] = self.post_norm[r_start:src_r_end, c_start:src_c_end]
            image_patch[2, :h_valid, :w_valid] = self.diff_norm[r_start:src_r_end, c_start:src_c_end]
            target_patch[0, :h_valid, :w_valid] = self.target[r_start:src_r_end, c_start:src_c_end]
            valid_patch[0, :h_valid, :w_valid] = self.src_valid[r_start:src_r_end, c_start:src_c_end]

        # Augmentation (Training only)
        if self.augment:
            # Random horizontal flip
            if random.random() < 0.5:
                image_patch = np.flip(image_patch, axis=-1).copy()
                target_patch = np.flip(target_patch, axis=-1).copy()
                valid_patch = np.flip(valid_patch, axis=-1).copy()
            # Random vertical flip
            if random.random() < 0.5:
                image_patch = np.flip(image_patch, axis=-2).copy()
                target_patch = np.flip(target_patch, axis=-2).copy()
                valid_patch = np.flip(valid_patch, axis=-2).copy()

        return {
            "image": torch.from_numpy(image_patch),
            "target": torch.from_numpy(target_patch),
            "valid_mask": torch.from_numpy(valid_patch),
            "r_start": torch.tensor(r_start, dtype=torch.int32),
            "r_end": torch.tensor(r_end, dtype=torch.int32),
            "c_start": torch.tensor(c_start, dtype=torch.int32),
            "c_end": torch.tensor(c_end, dtype=torch.int32),
        }

    @classmethod
    def from_geotiffs(
        cls,
        pre_flood_path: Path,
        post_flood_path: Path,
        mask_path: Path,
        split: str = "train",
        patch_size: int = 256,
        stride: Optional[int] = None,
        train_col_boundary: int = 768,
        guard_band_pixels: int = 64,
        min_db: float = -30.0,
        max_db: float = 0.0,
        min_diff_db: float = -20.0,
        max_diff_db: float = 10.0,
        augment: bool = False,
        seed: int = 42,
    ) -> "SAR3ChannelPatchDataset":
        with rasterio.open(pre_flood_path) as s_pre:
            pre_arr = s_pre.read(1)
        with rasterio.open(post_flood_path) as s_post:
            post_arr = s_post.read(1)
        with rasterio.open(mask_path) as s_mask:
            mask_arr = s_mask.read(1)

        return cls(
            pre_flood=pre_arr,
            post_flood=post_arr,
            target_mask=mask_arr,
            split=split,
            patch_size=patch_size,
            stride=stride,
            train_col_boundary=train_col_boundary,
            guard_band_pixels=guard_band_pixels,
            min_db=min_db,
            max_db=max_db,
            min_diff_db=min_diff_db,
            max_diff_db=max_diff_db,
            augment=augment,
            seed=seed,
        )


def evaluate_val_set(
    model: nn.Module,
    val_loader: DataLoader,
    criterion: nn.Module,
    device: torch.device,
    threshold: float = 0.50,
) -> Dict[str, Any]:
    """Evaluates the validation set and returns loss, metrics, and probabilities."""
    model.eval()
    val_loss_total = 0.0
    val_steps = 0
    val_tp, val_fp, val_fn, val_tn = 0, 0, 0, 0
    total_valid = 0

    val_probs_list = []
    val_targets_list = []

    with torch.no_grad():
        for batch in val_loader:
            images = batch["image"].to(device)
            targets = batch["target"].to(device)
            valid_mask = batch["valid_mask"].to(device)

            logits = model(images)
            loss, loss_dict = criterion(logits, targets, valid_mask)

            val_loss_total += loss_dict["loss_total"]
            val_steps += 1

            m = compute_valid_metrics(logits, targets, valid_mask, threshold=threshold)
            val_tp += m["tp"]
            val_fp += m["fp"]
            val_fn += m["fn"]
            val_tn += m["tn"]
            total_valid += m["valid_pixels"]

            # Store for detailed threshold analysis
            mask_bool = valid_mask.bool()
            probs = torch.sigmoid(logits)[mask_bool].cpu().numpy()
            targs = targets[mask_bool].cpu().numpy()
            val_probs_list.append(probs)
            val_targets_list.append(targs)

    avg_val_loss = val_loss_total / max(1, val_steps)
    eps = 1e-7
    prec = (val_tp + eps) / (val_tp + val_fp + eps)
    rec = (val_tp + eps) / (val_tp + val_fn + eps)
    f1 = (2.0 * prec * rec) / (prec + rec + eps)
    iou = (val_tp + eps) / (val_tp + val_fp + val_fn + eps)

    all_probs = np.concatenate(val_probs_list) if val_probs_list else np.array([])
    all_targets = np.concatenate(val_targets_list) if val_targets_list else np.array([])

    pred_pos_pct = (val_tp + val_fp) / max(1, total_valid) * 100.0
    ref_pos_pct = (val_tp + val_fn) / max(1, total_valid) * 100.0

    return {
        "val_loss": round(float(avg_val_loss), 4),
        "precision": round(float(prec), 4),
        "recall": round(float(rec), 4),
        "f1": round(float(f1), 4),
        "iou": round(float(iou), 4),
        "tp": int(val_tp),
        "fp": int(val_fp),
        "fn": int(val_fn),
        "tn": int(val_tn),
        "valid_pixels": int(total_valid),
        "pred_positive_pct": round(float(pred_pos_pct), 2),
        "ref_positive_pct": round(float(ref_pos_pct), 2),
        "all_probs": all_probs,
        "all_targets": all_targets,
    }


def run_experiment(
    data_dir: Path,
    output_dir: Path,
    epochs: int = 20,
    batch_size: int = 4,
    lr: float = 2e-4,
    pos_weight: float = 3.0,
    train_stride: int = 128,
    seed: int = 42,
) -> Dict[str, Any]:
    """Runs Experiment 01 with 3 channels and validation F1 checkpoint selection."""
    output_dir.mkdir(parents=True, exist_ok=True)
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(seed)

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")

    print("=" * 80)
    print(" SAHAYAK ML EXPERIMENT 01 — 3-CHANNEL DIFF + F1 SELECTION")
    print("=" * 80)
    print(f"Device:           {device}")
    if device.type == "cuda":
        print(f"GPU Name:         {torch.cuda.get_device_name(0)}")
    print(f"Epochs:           {epochs}")
    print(f"Batch Size:       {batch_size}")
    print(f"Learning Rate:    {lr} (Cosine Annealing to 1e-6)")
    print(f"Pos Weight:       {pos_weight}")
    print(f"Train Stride:     {train_stride} (Stride 128)")
    print(f"Random Seed:      {seed}")
    print(f"Output Directory: {output_dir}")
    print("=" * 80)

    pre_path = data_dir / "pre_flood_VV.tif"
    post_path = data_dir / "post_flood_VV.tif"
    mask_path = data_dir / "flood_mask_20220620_filtered.tif"

    # Datasets
    train_ds = SAR3ChannelPatchDataset.from_geotiffs(
        pre_flood_path=pre_path,
        post_flood_path=post_path,
        mask_path=mask_path,
        split="train",
        patch_size=256,
        stride=train_stride,
        augment=True,
        seed=seed,
    )
    val_ds = SAR3ChannelPatchDataset.from_geotiffs(
        pre_flood_path=pre_path,
        post_flood_path=post_path,
        mask_path=mask_path,
        split="val",
        patch_size=256,
        stride=256,
        augment=False,
        seed=seed,
    )

    print(f"Training Patches:   {len(train_ds)} (West Kamrup, Stride {train_stride}, Augment=True)")
    print(f"Validation Patches: {len(val_ds)} (East Kamrup, Stride 256, Augment=False)")

    train_loader = DataLoader(train_ds, batch_size=batch_size, shuffle=True)
    val_loader = DataLoader(val_ds, batch_size=batch_size, shuffle=False)

    # Build 3-channel U-Net model
    model = build_unet_model(in_channels=3, classes=1, encoder_weights=None)
    model.to(device)

    optimizer = torch.optim.AdamW(model.parameters(), lr=lr, weight_decay=1e-2)
    scheduler = torch.optim.lr_scheduler.CosineAnnealingLR(optimizer, T_max=epochs, eta_min=1e-6)
    criterion = CombinedFloodLoss(bce_weight=1.0, dice_weight=1.0, pos_weight=pos_weight)

    best_val_f1 = -1.0
    best_epoch = 1
    best_val_metrics = {}
    best_model_state = None
    history = []

    start_time = time.time()

    print("\n" + "=" * 90)
    print(f"{'Epoch':<6} | {'TrainLoss':<10} | {'ValLoss':<8} | {'ValPrec':<8} | {'ValRec':<8} | {'ValF1':<8} | {'ValIoU':<8} | {'Pred%':<6} | {'LR'}")
    print("-" * 90)

    for epoch in range(1, epochs + 1):
        model.train()
        train_loss_total = 0.0
        train_bce_total = 0.0
        train_dice_total = 0.0
        steps = 0

        for batch in train_loader:
            images = batch["image"].to(device)
            targets = batch["target"].to(device)
            valid_mask = batch["valid_mask"].to(device)

            optimizer.zero_grad()
            logits = model(images)
            loss, loss_dict = criterion(logits, targets, valid_mask)
            loss.backward()

            for name, param in model.named_parameters():
                if param.grad is not None and not torch.isfinite(param.grad).all():
                    raise RuntimeError(f"Non-finite gradient in {name}")

            optimizer.step()
            train_loss_total += loss_dict["loss_total"]
            train_bce_total += loss_dict["loss_bce"]
            train_dice_total += loss_dict["loss_dice"]
            steps += 1

        avg_train_loss = train_loss_total / max(1, steps)
        current_lr = scheduler.get_last_lr()[0]
        scheduler.step()

        # Validation evaluation
        val_res = evaluate_val_set(model, val_loader, criterion, device, threshold=0.50)

        # Checkpoint selection strictly by highest validation F1
        is_best = val_res["f1"] > best_val_f1
        if is_best:
            best_val_f1 = val_res["f1"]
            best_epoch = epoch
            best_val_metrics = {k: v for k, v in val_res.items() if k not in ("all_probs", "all_targets")}
            best_model_state = {k: v.cpu().clone() for k, v in model.state_dict().items()}

        epoch_record = {
            "epoch": epoch,
            "train_loss": round(float(avg_train_loss), 4),
            "train_bce": round(float(train_bce_total / max(1, steps)), 4),
            "train_dice": round(float(train_dice_total / max(1, steps)), 4),
            "val_loss": val_res["val_loss"],
            "val_precision": val_res["precision"],
            "val_recall": val_res["recall"],
            "val_f1": val_res["f1"],
            "val_iou": val_res["iou"],
            "val_tp": val_res["tp"],
            "val_fp": val_res["fp"],
            "val_fn": val_res["fn"],
            "val_tn": val_res["tn"],
            "pred_positive_pct": val_res["pred_positive_pct"],
            "ref_positive_pct": val_res["ref_positive_pct"],
            "lr": round(float(current_lr), 7),
            "is_best": is_best,
        }
        history.append(epoch_record)

        mark = " * [BEST F1]" if is_best else ""
        print(f"{epoch:<6} | {avg_train_loss:<10.4f} | {val_res['val_loss']:<8.4f} | "
              f"{val_res['precision']:<8.4f} | {val_res['recall']:<8.4f} | {val_res['f1']:<8.4f} | "
              f"{val_res['iou']:<8.4f} | {val_res['pred_positive_pct']:<5.1f}% | {current_lr:.1e}{mark}")

    total_training_time = time.time() - start_time
    print("=" * 90)
    print(f"Training completed in {total_training_time:.2f} seconds.")
    print(f"Best Checkpoint at Epoch {best_epoch} with Val F1 = {best_val_f1:.4f} (IoU = {best_val_metrics.get('iou', 0):.4f})")

    # Save best checkpoint
    checkpoint_data = {
        "epoch": best_epoch,
        "best_epoch": best_epoch,
        "best_criterion": "highest_val_f1_threshold_0_5",
        "best_val_f1": best_val_f1,
        "best_val_metrics": best_val_metrics,
        "model_state_dict": best_model_state,
        "optimizer_state_dict": optimizer.state_dict(),
        "history": history,
        "config": {
            "in_channels": 3,
            "classes": 1,
            "encoder_name": "resnet34",
            "pos_weight": pos_weight,
            "train_stride": train_stride,
            "epochs": epochs,
            "lr": lr,
            "seed": seed,
            "min_diff_db": -20.0,
            "max_diff_db": 10.0,
        },
    }
    ckpt_path = output_dir / "model_best.pth"
    torch.save(checkpoint_data, ckpt_path)
    print(f"[CHECKPOINT SAVED] {ckpt_path}")

    # Reload best model to run comprehensive threshold evaluation
    model.load_state_dict(best_model_state)
    best_eval = evaluate_val_set(model, val_loader, criterion, device, threshold=0.50)
    best_probs = best_eval["all_probs"]
    best_targets = best_eval["all_targets"]

    # Sweep thresholds on best model
    threshold_sweep = []
    for t in [round(x, 2) for x in np.arange(0.10, 0.91, 0.05)]:
        pred_pos = best_probs >= t
        tp = int(np.sum(pred_pos & (best_targets == 1)))
        fp = int(np.sum(pred_pos & (best_targets == 0)))
        fn = int(np.sum((~pred_pos) & (best_targets == 1)))
        tn = int(np.sum((~pred_pos) & (best_targets == 0)))
        eps = 1e-7
        prec = (tp + eps) / (tp + fp + eps)
        rec = (tp + eps) / (tp + fn + eps)
        f1 = (2 * prec * rec) / (prec + rec + eps)
        iou = (tp + eps) / (tp + fp + fn + eps)
        threshold_sweep.append({
            "threshold": t,
            "tp": tp, "fp": fp, "fn": fn, "tn": tn,
            "precision": round(float(prec), 4),
            "recall": round(float(rec), 4),
            "f1": round(float(f1), 4),
            "iou": round(float(iou), 4),
            "pred_positive_pct": round(float((tp + fp) / len(best_probs) * 100.0), 2),
        })

    # Save metrics JSON
    metrics_path = output_dir / "training_metrics.json"
    with open(metrics_path, "w", encoding="utf-8") as f:
        json.dump({
            "duration_sec": round(total_training_time, 2),
            "best_epoch": best_epoch,
            "best_val_f1": best_val_f1,
            "best_val_metrics": best_val_metrics,
            "history": history,
            "threshold_sweep_at_best_epoch": threshold_sweep,
        }, f, indent=2)
    print(f"[METRICS SAVED] {metrics_path}")

    # Save configuration JSON
    config_path = output_dir / "experiment_config.json"
    with open(config_path, "w", encoding="utf-8") as f:
        json.dump(checkpoint_data["config"], f, indent=2)

    # Save Markdown Summary
    summary_path = output_dir / "experiment_summary.md"
    with open(summary_path, "w", encoding="utf-8") as f:
        f.write("# SAHAYAK Flood Mapper — Experiment 01 Report\n\n")
        f.write("## Overview\n")
        f.write("- **Experiment**: 3-Channel Input (Pre, Post, Post-Pre Diff dB) + Stride 128 + Flip Augmentation + F1 Selection\n")
        f.write(f"- **Runtime**: {total_training_time:.2f} seconds\n")
        f.write(f"- **Best Epoch**: {best_epoch} (Selected by highest validation F1 at threshold 0.50)\n\n")
        f.write("## Baseline vs Experiment 01 Comparison (Validation Set at Threshold 0.50)\n\n")
        f.write("| Metric | Baseline (`baseline_run_01`) | Experiment 01 (`exp01_diff_channel`) | Delta |\n")
        f.write("| :--- | :---: | :---: | :---: |\n")
        f.write(f"| **Validation F1** | 0.1515 | **{best_val_metrics['f1']:.4f}** | {'+' if best_val_metrics['f1'] >= 0.1515 else ''}{best_val_metrics['f1'] - 0.1515:.4f} |\n")
        f.write(f"| **Validation IoU** | 0.0820 | **{best_val_metrics['iou']:.4f}** | {'+' if best_val_metrics['iou'] >= 0.0820 else ''}{best_val_metrics['iou'] - 0.0820:.4f} |\n")
        f.write(f"| **Validation Precision** | 0.0915 | **{best_val_metrics['precision']:.4f}** | {'+' if best_val_metrics['precision'] >= 0.0915 else ''}{best_val_metrics['precision'] - 0.0915:.4f} |\n")
        f.write(f"| **Validation Recall** | 0.4417 | **{best_val_metrics['recall']:.4f}** | {'+' if best_val_metrics['recall'] >= 0.4417 else ''}{best_val_metrics['recall'] - 0.4417:.4f} |\n")
        f.write(f"| **Predicted Flood Area %** | 22.33% | **{best_val_metrics['pred_positive_pct']:.2f}%** | {best_val_metrics['pred_positive_pct'] - 22.33:.2f}% |\n")
        f.write(f"| **True Positives** | 3,858 | **{best_val_metrics['tp']:,}** | {'+' if best_val_metrics['tp'] >= 3858 else ''}{best_val_metrics['tp'] - 3858} |\n")
        f.write(f"| **False Positives** | 38,328 | **{best_val_metrics['fp']:,}** | {best_val_metrics['fp'] - 38328} |\n\n")
        f.write("## Threshold Sweep on Best Model (Validation Set)\n\n")
        f.write("| Threshold | TP | FP | FN | TN | Precision | Recall | F1 Score | IoU | Pred Flood % |\n")
        f.write("| :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |\n")
        for r in threshold_sweep:
            f.write(f"| {r['threshold']:.2f} | {r['tp']:,} | {r['fp']:,} | {r['fn']:,} | {r['tn']:,} | "
                    f"{r['precision']:.4f} | {r['recall']:.4f} | {r['f1']:.4f} | {r['iou']:.4f} | {r['pred_positive_pct']:.2f}% |\n")

    print(f"[SUMMARY SAVED] {summary_path}")
    return {
        "best_epoch": best_epoch,
        "best_val_f1": best_val_f1,
        "best_val_metrics": best_val_metrics,
        "duration_sec": total_training_time,
    }


def main():
    parser = argparse.ArgumentParser(description="SAHAYAK Experiment 01 Runner")
    parser.add_argument("--data-dir", type=str, default="Data/raw", help="Raw SAR GeoTIFF directory")
    parser.add_argument("--output-dir", type=str, default="outputs/experiments/exp01_diff_channel", help="Experiment output dir")
    parser.add_argument("--epochs", type=int, default=20, help="Number of training epochs")
    parser.add_argument("--batch-size", type=int, default=4, help="Batch size")
    parser.add_argument("--lr", type=float, default=2e-4, help="Initial learning rate")
    parser.add_argument("--pos-weight", type=float, default=3.0, help="Positive class weight in BCE loss")
    parser.add_argument("--train-stride", type=int, default=128, help="Training patch stride")
    parser.add_argument("--seed", type=int, default=42, help="Random seed")

    args = parser.parse_args()

    data_dir = (REPO_ML_DIR / args.data_dir).resolve()
    output_dir = (REPO_ML_DIR / args.output_dir).resolve()

    run_experiment(
        data_dir=data_dir,
        output_dir=output_dir,
        epochs=args.epochs,
        batch_size=args.batch_size,
        lr=args.lr,
        pos_weight=args.pos_weight,
        train_stride=args.train_stride,
        seed=args.seed,
    )


if __name__ == "__main__":
    main()
