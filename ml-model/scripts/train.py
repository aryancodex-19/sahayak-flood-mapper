"""
Training and Smoke-Test Script for SAHAYAK U-Net Flood Segmentation.

This script orchestrates:
1. Loading SARPatchDataset from local raw GeoTIFFs (with spatial train/val split).
2. Initializing FloodUNet with ResNet34 backbone.
3. Training with CombinedFloodLoss (Masked BCE + Masked Dice) and AdamW.
4. Computing valid-pixel-aware metrics (Precision, Recall, F1/Dice, IoU).
5. Checkpoint saving and reloading validation.
6. A lightweight --smoke-test mode for rapid GPU verification without long runs.
"""

import sys
import os
import argparse
import json
import time
from pathlib import Path
import torch
from torch.utils.data import DataLoader, Subset

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

from src.model import build_unet_model
from src.dataset import SARPatchDataset
from src.losses import CombinedFloodLoss, compute_valid_metrics


def run_training(
    data_dir: Path,
    output_dir: Path,
    epochs: int = 5,
    batch_size: int = 2,
    lr: float = 1e-4,
    pos_weight: float = 5.0,
    seed: int = 42,
    smoke_test: bool = False,
) -> dict:
    """
    Executes training or a rapid smoke test.
    """
    torch.manual_seed(seed)
    output_dir.mkdir(parents=True, exist_ok=True)

    # 1. Device selection
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print("\n" + "=" * 70)
    print(" SAHAYAK ML TRAINING & VERIFICATION PIPELINE")
    print("=" * 70)
    print(f"Device:           {device}")
    if device.type == "cuda":
        print(f"GPU Name:         {torch.cuda.get_device_name(0)}")
        print(f"Initial VRAM:     {torch.cuda.memory_allocated(0) / (1024**2):.2f} MB")
    print(f"Smoke Test Mode:  {smoke_test}")
    print(f"Batch Size:       {batch_size}")
    print(f"Learning Rate:    {lr}")
    print(f"Positive Weight:  {pos_weight} (balancing ~5.35% flood pixels)")
    print(f"Output Directory: {output_dir}")
    print("=" * 70)

    # 2. Check source GeoTIFFs
    pre_path = data_dir / "pre_flood_VV.tif"
    post_path = data_dir / "post_flood_VV.tif"
    mask_path = data_dir / "flood_mask_20220620_filtered.tif"

    for p, name in [(pre_path, "pre-flood"), (post_path, "post-flood"), (mask_path, "mask")]:
        if not p.exists():
            raise FileNotFoundError(f"Missing {name} GeoTIFF at: {p}")

    # 3. Load datasets
    train_ds = SARPatchDataset.from_geotiffs(
        pre_flood_path=pre_path,
        post_flood_path=post_path,
        mask_path=mask_path,
        split="train",
        patch_size=256,
    )
    val_ds = SARPatchDataset.from_geotiffs(
        pre_flood_path=pre_path,
        post_flood_path=post_path,
        mask_path=mask_path,
        split="val",
        patch_size=256,
    )

    print(f"Total Train Patches: {len(train_ds)} (West Kamrup)")
    print(f"Total Val Patches:   {len(val_ds)} (East Kamrup, guarded separation)")

    # In smoke test mode, restrict to 2 patches and 1 epoch
    if smoke_test:
        train_ds = Subset(train_ds, [0, 1])
        val_ds = Subset(val_ds, [0])
        epochs = 1
        print("[SMOKE TEST] Restricting to 2 train patches and 1 val patch.")

    train_loader = DataLoader(train_ds, batch_size=batch_size, shuffle=False)
    val_loader = DataLoader(val_ds, batch_size=batch_size, shuffle=False)

    # 4. Build Model & Optimizer
    model = build_unet_model(in_channels=2, classes=1, encoder_weights=None)
    model.to(device)

    optimizer = torch.optim.AdamW(model.parameters(), lr=lr, weight_decay=1e-2)
    criterion = CombinedFloodLoss(bce_weight=1.0, dice_weight=1.0, pos_weight=pos_weight)

    # Track initial weights norm to prove weights change during training
    initial_param_norm = torch.norm(torch.stack([torch.norm(p.detach()) for p in model.parameters()])).item()

    history = []
    best_val_loss = float("inf")
    best_epoch = 1
    best_model_state = None
    start_time = time.time()

    for epoch in range(1, epochs + 1):
        model.train()
        train_loss_total = 0.0
        train_loss_bce = 0.0
        train_loss_dice = 0.0
        train_steps = 0

        for batch in train_loader:
            images = batch["image"].to(device)
            targets = batch["target"].to(device)
            valid_mask = batch["valid_mask"].to(device)

            optimizer.zero_grad()
            logits = model(images)

            loss, loss_dict = criterion(logits, targets, valid_mask)
            loss.backward()

            # Verify gradient sanity
            for name, param in model.named_parameters():
                if param.grad is not None:
                    if not torch.isfinite(param.grad).all():
                        raise RuntimeError(f"Non-finite gradient detected in {name}!")

            optimizer.step()

            train_loss_total += loss_dict["loss_total"]
            train_loss_bce += loss_dict["loss_bce"]
            train_loss_dice += loss_dict["loss_dice"]
            train_steps += 1

        avg_train_loss = train_loss_total / max(1, train_steps)
        avg_train_bce = train_loss_bce / max(1, train_steps)
        avg_train_dice = train_loss_dice / max(1, train_steps)

        # 5. Validation Step
        model.eval()
        val_loss_total = 0.0
        val_steps = 0
        val_tp, val_fp, val_fn, val_tn = 0, 0, 0, 0
        total_valid_pixels = 0

        with torch.no_grad():
            for batch in val_loader:
                images = batch["image"].to(device)
                targets = batch["target"].to(device)
                valid_mask = batch["valid_mask"].to(device)

                logits = model(images)
                loss, loss_dict = criterion(logits, targets, valid_mask)

                val_loss_total += loss_dict["loss_total"]
                val_steps += 1

                m = compute_valid_metrics(logits, targets, valid_mask, threshold=0.5)
                val_tp += m["tp"]
                val_fp += m["fp"]
                val_fn += m["fn"]
                val_tn += m["tn"]
                total_valid_pixels += m["valid_pixels"]

        avg_val_loss = val_loss_total / max(1, val_steps)
        eps = 1e-7
        val_prec = (val_tp + eps) / (val_tp + val_fp + eps)
        val_rec = (val_tp + eps) / (val_tp + val_fn + eps)
        val_f1 = (2.0 * val_prec * val_rec) / (val_prec + val_rec + eps)
        val_iou = (val_tp + eps) / (val_tp + val_fp + val_fn + eps)

        is_best = avg_val_loss < best_val_loss
        if is_best:
            best_val_loss = avg_val_loss
            best_epoch = epoch
            best_model_state = {k: v.cpu().clone() for k, v in model.state_dict().items()}

        epoch_record = {
            "epoch": epoch,
            "train_loss": round(avg_train_loss, 4),
            "train_bce": round(avg_train_bce, 4),
            "train_dice": round(avg_train_dice, 4),
            "val_loss": round(avg_val_loss, 4),
            "val_precision": round(float(val_prec), 4),
            "val_recall": round(float(val_rec), 4),
            "val_f1": round(float(val_f1), 4),
            "val_iou": round(float(val_iou), 4),
            "valid_pixels_evaluated": total_valid_pixels,
            "is_best": is_best,
        }
        history.append(epoch_record)

        print(
            f"Epoch {epoch:02d}/{epochs:02d} | "
            f"Train Loss: {avg_train_loss:.4f} (BCE: {avg_train_bce:.4f}, Dice: {avg_train_dice:.4f}) | "
            f"Val Loss: {avg_val_loss:.4f} | "
            f"Val IoU: {val_iou:.4f} | Val F1: {val_f1:.4f}"
            f"{' [BEST]' if is_best else ''}"
        )

    duration = time.time() - start_time
    peak_vram = 0.0
    if device.type == "cuda":
        peak_vram = torch.cuda.max_memory_allocated(0) / (1024**2)
        print(f"\n[GPU Memory] Peak VRAM Allocated: {peak_vram:.2f} MB")

    # Check weights norm change
    final_param_norm = torch.norm(torch.stack([torch.norm(p.detach()) for p in model.parameters()])).item()
    weights_changed = abs(final_param_norm - initial_param_norm) > 1e-6
    print(f"[Model Weights] Initial norm: {initial_param_norm:.4f}, Final norm: {final_param_norm:.4f}, Weights changed: {weights_changed}")

    # 6. Checkpoint saving & reload verification
    ckpt_path = output_dir / ("smoke_test_model.pth" if smoke_test else "model_best.pth")
    checkpoint_data = {
        "epoch": epochs,
        "best_epoch": best_epoch,
        "best_criterion": "lowest_val_loss",
        "best_val_loss": round(best_val_loss, 4),
        "model_state_dict": best_model_state if best_model_state is not None else model.state_dict(),
        "optimizer_state_dict": optimizer.state_dict(),
        "history": history,
        "config": {
            "in_channels": 2,
            "classes": 1,
            "encoder": "resnet34",
            "pos_weight": pos_weight,
            "lr": lr,
            "seed": seed,
            "smoke_test": smoke_test,
        },
    }
    torch.save(checkpoint_data, ckpt_path)
    print(f"[SUCCESS] Checkpoint saved successfully at: {ckpt_path} (Best Epoch: {best_epoch})")

    # Reload check
    loaded_ckpt = torch.load(ckpt_path, map_location=device, weights_only=False)
    test_model = build_unet_model(in_channels=2, classes=1, encoder_weights=None)
    test_model.load_state_dict(loaded_ckpt["model_state_dict"])
    test_model.to(device)
    test_model.eval()
    print("[SUCCESS] Checkpoint reloaded and verified successfully!")

    # Save metrics JSON
    metrics_path = output_dir / ("smoke_metrics.json" if smoke_test else "training_metrics.json")
    with open(metrics_path, "w") as f:
        json.dump({
            "duration_sec": round(duration, 2),
            "peak_vram_mb": round(peak_vram, 2),
            "device": str(device),
            "best_epoch": best_epoch,
            "best_val_loss": round(best_val_loss, 4),
            "weights_changed": weights_changed,
            "history": history,
        }, f, indent=2)
    print(f"[SUCCESS] Metrics saved at: {metrics_path}")

    return {
        "checkpoint_path": str(ckpt_path),
        "metrics_path": str(metrics_path),
        "duration": duration,
        "peak_vram_mb": peak_vram,
        "history": history,
    }


def main():
    parser = argparse.ArgumentParser(description="Train SAHAYAK U-Net on Sentinel-1 SAR patches")
    parser.add_argument("--data-dir", type=str, default="data/raw", help="Path to raw GeoTIFFs")
    parser.add_argument("--output-dir", type=str, default="outputs", help="Directory for checkpoints/metrics")
    parser.add_argument("--epochs", type=int, default=5, help="Number of training epochs")
    parser.add_argument("--batch-size", type=int, default=2, help="Batch size")
    parser.add_argument("--lr", type=float, default=1e-4, help="Learning rate")
    parser.add_argument("--pos-weight", type=float, default=5.0, help="Positive class weight in BCE")
    parser.add_argument("--seed", type=int, default=42, help="Random seed")
    parser.add_argument("--smoke-test", action="store_true", help="Run 1-epoch GPU smoke test on tiny subset")

    args = parser.parse_args()

    data_dir = (REPO_ML_DIR / args.data_dir).resolve()
    output_dir = (REPO_ML_DIR / args.output_dir).resolve()

    run_training(
        data_dir=data_dir,
        output_dir=output_dir,
        epochs=args.epochs,
        batch_size=args.batch_size,
        lr=args.lr,
        pos_weight=args.pos_weight,
        seed=args.seed,
        smoke_test=args.smoke_test,
    )


if __name__ == "__main__":
    main()
