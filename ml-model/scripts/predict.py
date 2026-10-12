"""
Full-Scene Inference and Georeferenced Export Script for SAHAYAK Flood Mapping.

This script:
1. Loads the best trained U-Net checkpoint.
2. Reads Sentinel-1 pre-flood and post-flood SAR GeoTIFFs.
3. Applies consistent dB normalization ([-30, 0] dB -> [0, 1]).
4. Runs sliding-window patch inference (256x256) covering the full scene without gaps.
5. Reconstructs exact unpadded dimensions, preserving source CRS and Affine transform.
6. Exports georeferenced GeoTIFFs:
   - flood_probability.tif (Float32 in [0, 1])
   - flood_prediction.tif (Uint8: 1 = flood, 0 = non-flood, nodata = 255)
7. Reopens and validates exported GeoTIFF metadata.
"""

import sys
import os
import argparse
import time
from pathlib import Path
from typing import Tuple, Dict, Any, Optional
import numpy as np
import torch
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

from src.model import build_unet_model, FloodUNet
from src.dataset import normalize_sar_db


def predict_full_raster(
    model: FloodUNet,
    pre_arr: np.ndarray,
    post_arr: np.ndarray,
    device: torch.device,
    patch_size: int = 256,
    batch_size: int = 4,
    threshold: float = 0.5,
    min_db: float = -30.0,
    max_db: float = 0.0,
) -> Tuple[np.ndarray, np.ndarray, Dict[str, Any]]:
    """
    Performs full-scene tiled inference over arbitrary raster dimensions without gaps.

    Args:
        model: Loaded PyTorch FloodUNet in eval mode.
        pre_arr: 2D array of pre-flood VV SAR (in dB).
        post_arr: 2D array of post-flood VV SAR (in dB).
        device: Computation device (cuda or cpu).
        patch_size: Square tile dimension (default: 256).
        batch_size: Tile batch size for forward pass (default: 4).
        threshold: Decision threshold for binary flood prediction (default: 0.5).
        min_db: Minimum dB for normalization.
        max_db: Maximum dB for normalization.

    Returns:
        prob_map: 2D float32 array in [0.0, 1.0].
        pred_map: 2D uint8 array with 1 = flood, 0 = non-flood.
        stats: Dictionary of coverage, tile counts, and predicted pixels.
    """
    if pre_arr.shape != post_arr.shape:
        raise ValueError(f"Shape mismatch: pre {pre_arr.shape} vs post {post_arr.shape}")

    height, width = pre_arr.shape

    # Normalize SAR channels
    pre_norm, _ = normalize_sar_db(pre_arr, min_db=min_db, max_db=max_db)
    post_norm, _ = normalize_sar_db(post_arr, min_db=min_db, max_db=max_db)

    # Allocate full-scene output buffer on CPU
    prob_map = np.zeros((height, width), dtype=np.float32)
    coverage_tracker = np.zeros((height, width), dtype=np.uint8)

    # Generate non-overlapping grid tile coordinates
    r_steps = list(range(0, height, patch_size))
    c_steps = list(range(0, width, patch_size))

    tiles_info = []
    for r in r_steps:
        r_start = r
        r_end = min(r_start + patch_size, height)
        for c in c_steps:
            c_start = c
            c_end = min(c_start + patch_size, width)
            tiles_info.append({
                "r_start": r_start,
                "r_end": r_end,
                "c_start": c_start,
                "c_end": c_end,
                "h_valid": r_end - r_start,
                "w_valid": c_end - c_start,
            })

    total_tiles = len(tiles_info)
    model.eval()

    # Process in batches
    for i in range(0, total_tiles, batch_size):
        batch_slice = tiles_info[i:i + batch_size]
        actual_bs = len(batch_slice)

        # Allocate padded GPU batch buffer [B, 2, patch_size, patch_size]
        batch_tensor = np.zeros((actual_bs, 2, patch_size, patch_size), dtype=np.float32)

        for b_idx, t in enumerate(batch_slice):
            hv, wv = t["h_valid"], t["w_valid"]
            rs, re = t["r_start"], t["r_end"]
            cs, ce = t["c_start"], t["c_end"]
            batch_tensor[b_idx, 0, :hv, :wv] = pre_norm[rs:re, cs:ce]
            batch_tensor[b_idx, 1, :hv, :wv] = post_norm[rs:re, cs:ce]

        with torch.no_grad():
            inp = torch.from_numpy(batch_tensor).to(device)
            logits = model(inp)
            probs = torch.sigmoid(logits).cpu().numpy()  # [B, 1, patch_size, patch_size]

        # Place predictions back into full raster
        for b_idx, t in enumerate(batch_slice):
            hv, wv = t["h_valid"], t["w_valid"]
            rs, re = t["r_start"], t["r_end"]
            cs, ce = t["c_start"], t["c_end"]

            prob_map[rs:re, cs:ce] = probs[b_idx, 0, :hv, :wv]
            coverage_tracker[rs:re, cs:ce] += 1

    # Verify coverage integrity (every pixel covered exactly once)
    uncovered_count = int(np.count_nonzero(coverage_tracker == 0))
    duplicate_count = int(np.count_nonzero(coverage_tracker > 1))
    if uncovered_count > 0 or duplicate_count > 0:
        raise RuntimeError(
            f"Coverage anomaly detected: {uncovered_count} uncovered pixels, "
            f"{duplicate_count} multiply-covered pixels."
        )

    # Compute binary prediction
    pred_map = (prob_map >= threshold).astype(np.uint8)

    flood_pixels = int(np.sum(pred_map == 1))
    total_pixels = height * width
    flood_pct = (flood_pixels / total_pixels) * 100.0 if total_pixels > 0 else 0.0

    stats = {
        "height": height,
        "width": width,
        "total_pixels": total_pixels,
        "total_tiles": total_tiles,
        "patch_size": patch_size,
        "threshold": threshold,
        "flood_pixels": flood_pixels,
        "flood_pct": round(flood_pct, 2),
        "prob_min": float(np.min(prob_map)),
        "prob_max": float(np.max(prob_map)),
        "prob_mean": float(np.mean(prob_map)),
        "uncovered_pixels": uncovered_count,
        "duplicate_pixels": duplicate_count,
    }

    return prob_map, pred_map, stats


def run_inference(
    checkpoint_path: Path,
    pre_flood_path: Path,
    post_flood_path: Path,
    output_dir: Path,
    patch_size: int = 256,
    batch_size: int = 4,
    threshold: float = 0.5,
) -> Dict[str, Any]:
    """
    Executes full pipeline: verifies rasters, runs prediction, and exports georeferenced GeoTIFFs.
    """
    checkpoint_path = Path(checkpoint_path)
    pre_flood_path = Path(pre_flood_path)
    post_flood_path = Path(post_flood_path)
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")

    print("\n" + "=" * 70)
    print(" SAHAYAK FULL-SCENE INFERENCE & GEOTIFF EXPORT")
    print("=" * 70)
    print(f"Device:           {device}")
    if device.type == "cuda":
        print(f"GPU Device:       {torch.cuda.get_device_name(0)}")
        print(f"Initial VRAM:     {torch.cuda.memory_allocated(0) / (1024**2):.2f} MB")
    print(f"Checkpoint:       {checkpoint_path}")
    print(f"Pre-flood Raster: {pre_flood_path}")
    print(f"Post-flood Raster:{post_flood_path}")
    print(f"Output Directory: {output_dir}")
    print(f"Patch Size:       {patch_size} x {patch_size}")
    print(f"Decision Thresh:  {threshold}")
    print("=" * 70)

    # 1. Load and verify input rasters
    for p, name in [(pre_flood_path, "pre-flood"), (post_flood_path, "post-flood")]:
        if not p.exists():
            raise FileNotFoundError(f"Missing {name} GeoTIFF at: {p}")

    with rasterio.open(pre_flood_path) as s_pre:
        pre_arr = s_pre.read(1)
        pre_profile = s_pre.profile.copy()
        pre_crs = s_pre.crs
        pre_transform = s_pre.transform
        pre_shape = s_pre.shape

    with rasterio.open(post_flood_path) as s_post:
        post_arr = s_post.read(1)
        post_crs = s_post.crs
        post_transform = s_post.transform
        post_shape = s_post.shape

    # Spatial alignment verification
    if pre_shape != post_shape:
        raise ValueError(f"Input raster dimension mismatch: pre {pre_shape} vs post {post_shape}")
    if pre_crs != post_crs:
        raise ValueError(f"Input raster CRS mismatch: pre {pre_crs} vs post {post_crs}")
    if pre_transform != post_transform:
        raise ValueError(f"Input raster transform mismatch: pre {pre_transform} vs post {post_transform}")

    print(f"Input Rasters Validated: Shape {pre_shape}, CRS {pre_crs}, Alignment PERFECT.")

    # 2. Load model from checkpoint
    if not checkpoint_path.exists():
        raise FileNotFoundError(f"Checkpoint not found at: {checkpoint_path}")

    ckpt = torch.load(checkpoint_path, map_location=device, weights_only=False)
    config = ckpt.get("config", {})
    in_channels = config.get("in_channels", 2)
    classes = config.get("classes", 1)
    encoder = config.get("encoder", "resnet34")

    model = build_unet_model(in_channels=in_channels, classes=classes, encoder_name=encoder, encoder_weights=None)
    model.load_state_dict(ckpt["model_state_dict"])
    model.to(device)
    model.eval()
    print(f"Loaded Checkpoint successfully (Epoch {ckpt.get('best_epoch', ckpt.get('epoch', '?'))}).")

    # 3. Execute tiled inference
    start_time = time.time()
    prob_map, pred_map, stats = predict_full_raster(
        model=model,
        pre_arr=pre_arr,
        post_arr=post_arr,
        device=device,
        patch_size=patch_size,
        batch_size=batch_size,
        threshold=threshold,
    )
    inference_duration = time.time() - start_time

    peak_vram = 0.0
    if device.type == "cuda":
        peak_vram = torch.cuda.max_memory_allocated(0) / (1024**2)

    # 4. Export Probability GeoTIFF
    prob_tif_path = output_dir / "flood_probability.tif"
    prob_profile = pre_profile.copy()
    prob_profile.update(
        dtype=rasterio.float32,
        count=1,
        compress="lzw",
        nodata=-9999.0,
    )
    with rasterio.open(prob_tif_path, "w", **prob_profile) as dst:
        dst.write(prob_map, 1)
    print(f"[SUCCESS] Exported Probability GeoTIFF: {prob_tif_path}")

    # 5. Export Binary Prediction GeoTIFF (Graph Analysis Drop-in Input)
    # Convention: 1 = flood, 0 = dry/non-flood.
    # Note: nodata is explicitly NOT set to 0 because 0 is the valid non-flood class!
    pred_tif_path = output_dir / "flood_prediction.tif"
    pred_profile = pre_profile.copy()
    pred_profile.update(
        dtype=rasterio.uint8,
        count=1,
        compress="lzw",
        nodata=255,  # 255 reserved for nodata; 0 = dry land, 1 = flood
    )
    with rasterio.open(pred_tif_path, "w", **pred_profile) as dst:
        dst.write(pred_map, 1)
    print(f"[SUCCESS] Exported Binary Prediction GeoTIFF: {pred_tif_path}")

    # 6. Reopen & Validate Exported GeoTIFFs
    print("\n" + "=" * 70)
    print(" VALIDATING EXPORTED GEOTIFFS (RE-OPEN CHECK)")
    print("=" * 70)

    # Validate probability raster
    with rasterio.open(prob_tif_path) as p_src:
        p_data = p_src.read(1)
        print(f"Probability GeoTIFF: Shape={p_src.shape}, Dtype={p_src.dtypes[0]}, CRS={p_src.crs}, NoData={p_src.nodata}")
        print(f"  Range: Min={np.nanmin(p_data):.4f}, Max={np.nanmax(p_data):.4f}, Mean={np.nanmean(p_data):.4f}")
        print(f"  Finite count: {np.count_nonzero(np.isfinite(p_data)):,} / {p_data.size:,}")
        assert p_src.shape == pre_shape, "Probability shape mismatch!"
        assert p_src.crs == pre_crs, "Probability CRS mismatch!"
        assert p_src.transform == pre_transform, "Probability Transform mismatch!"

    # Validate binary prediction raster
    with rasterio.open(pred_tif_path) as b_src:
        b_data = b_src.read(1)
        unique_vals, counts = np.unique(b_data, return_counts=True)
        print(f"Binary Prediction GeoTIFF: Shape={b_src.shape}, Dtype={b_src.dtypes[0]}, CRS={b_src.crs}, NoData={b_src.nodata}")
        print(f"  Unique values & counts: {dict(zip(unique_vals.tolist(), counts.tolist()))}")
        print(f"  Predicted Flood Pixels (val=1): {stats['flood_pixels']:,} ({stats['flood_pct']}%)")
        assert b_src.shape == pre_shape, "Prediction shape mismatch!"
        assert b_src.crs == pre_crs, "Prediction CRS mismatch!"
        assert b_src.transform == pre_transform, "Prediction Transform mismatch!"
        for u in unique_vals:
            assert u in [0, 1], f"Unexpected binary value: {u}"

    print("[SUCCESS] All exported GeoTIFFs validated and spatial alignment confirmed!")

    return {
        "prob_path": str(prob_tif_path),
        "pred_path": str(pred_tif_path),
        "stats": stats,
        "runtime_sec": round(inference_duration, 2),
        "peak_vram_mb": round(peak_vram, 2),
    }


def main():
    parser = argparse.ArgumentParser(description="Full-Scene Inference for SAHAYAK U-Net")
    parser.add_argument("--checkpoint", type=str, default="outputs/baseline_run_01/model_best.pth", help="Checkpoint path")
    parser.add_argument("--pre-flood", type=str, default="data/raw/pre_flood_VV.tif", help="Pre-flood GeoTIFF path")
    parser.add_argument("--post-flood", type=str, default="data/raw/post_flood_VV.tif", help="Post-flood GeoTIFF path")
    parser.add_argument("--output-dir", type=str, default="outputs/inference_run_01", help="Output directory")
    parser.add_argument("--patch-size", type=int, default=256, help="Tile size")
    parser.add_argument("--batch-size", type=int, default=4, help="Inference batch size")
    parser.add_argument("--threshold", type=float, default=0.5, help="Decision threshold")

    args = parser.parse_args()

    checkpoint_path = (REPO_ML_DIR / args.checkpoint).resolve()
    pre_path = (REPO_ML_DIR / args.pre_flood).resolve()
    post_path = (REPO_ML_DIR / args.post_flood).resolve()
    output_dir = (REPO_ML_DIR / args.output_dir).resolve()

    run_inference(
        checkpoint_path=checkpoint_path,
        pre_flood_path=pre_path,
        post_flood_path=post_path,
        output_dir=output_dir,
        patch_size=args.patch_size,
        batch_size=args.batch_size,
        threshold=args.threshold,
    )


if __name__ == "__main__":
    main()
