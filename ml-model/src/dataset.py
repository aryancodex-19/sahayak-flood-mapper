"""
Dataset and Preprocessing Module for SAHAYAK Flood Segmentation.

This module provides:
1. Sentinel-1 SAR normalization from decibels (dB) to [0, 1].
2. Patch extraction (256x256) with coordinate tracking and edge padding.
3. Strict spatial separation between Training and Validation zones with a guard band.
4. Validity mask creation so padded/invalid pixels never contribute to loss or metrics.
5. Handling of slope-filtered flood masks as pseudo-labels (not verified ground truth).
"""

from typing import Tuple, Dict, List, Optional
from pathlib import Path
import numpy as np
import torch
from torch.utils.data import Dataset
import rasterio


def normalize_sar_db(
    arr: np.ndarray,
    min_db: float = -30.0,
    max_db: float = 0.0,
) -> Tuple[np.ndarray, Dict[str, float]]:
    """
    Normalizes Sentinel-1 SAR backscatter from decibels (dB) to [0.0, 1.0].

    Formula:
        norm = np.clip((arr - min_db) / (max_db - min_db), 0.0, 1.0)

    Args:
        arr: Input backscatter array in dB (float32 or float64).
        min_db: Lower bound clip limit in dB (default: -30.0 dB).
        max_db: Upper bound clip limit in dB (default: 0.0 dB).

    Returns:
        norm_arr: Float32 array normalized to [0.0, 1.0].
        stats: Dictionary containing percentage of pixels clipped and invalid counts.
    """
    if min_db >= max_db:
        raise ValueError(f"min_db ({min_db}) must be strictly less than max_db ({max_db})")

    # Detect invalid values (NaN or Inf)
    invalid_mask = np.isnan(arr) | np.isinf(arr)
    total_pixels = arr.size
    invalid_count = int(np.sum(invalid_mask))

    clean_arr = np.where(invalid_mask, min_db, arr)

    below_mask = clean_arr < min_db
    above_mask = clean_arr > max_db

    pct_clipped_below = float(np.sum(below_mask) / total_pixels * 100.0) if total_pixels > 0 else 0.0
    pct_clipped_above = float(np.sum(above_mask) / total_pixels * 100.0) if total_pixels > 0 else 0.0
    pct_invalid = float(invalid_count / total_pixels * 100.0) if total_pixels > 0 else 0.0

    norm_arr = np.clip((clean_arr - min_db) / (max_db - min_db), 0.0, 1.0).astype(np.float32)

    # Set invalid pixels strictly to 0.0
    if invalid_count > 0:
        norm_arr[invalid_mask] = 0.0

    stats = {
        "min_db": min_db,
        "max_db": max_db,
        "total_pixels": total_pixels,
        "invalid_count": invalid_count,
        "pct_invalid": pct_invalid,
        "pct_clipped_below": pct_clipped_below,
        "pct_clipped_above": pct_clipped_above,
    }

    return norm_arr, stats


def generate_patch_coordinates(
    height: int,
    width: int,
    patch_size: int = 256,
    stride: Optional[int] = None,
    col_min: int = 0,
    col_max: Optional[int] = None,
    row_min: int = 0,
    row_max: Optional[int] = None,
) -> List[Dict[str, int]]:
    """
    Generates deterministic patch window coordinates confined strictly within spatial bounds.

    Args:
        height: Total raster height.
        width: Total raster width.
        patch_size: Square tile dimension (default: 256).
        stride: Step between tiles (default: patch_size for non-overlapping).
        col_min: Minimum column boundary (inclusive).
        col_max: Maximum column boundary (exclusive). Default is width.
        row_min: Minimum row boundary (inclusive).
        row_max: Maximum row boundary (exclusive). Default is height.

    Returns:
        List of coordinate dicts: [{'r_start', 'r_end', 'c_start', 'c_end'}, ...]
    """
    if stride is None:
        stride = patch_size

    if col_max is None:
        col_max = width
    if row_max is None:
        row_max = height

    if col_min >= col_max or row_min >= row_max:
        return []

    coords = []
    # Generate rows
    r = row_min
    while r < row_max:
        r_start = r
        r_end = r_start + patch_size
        # Generate columns
        c = col_min
        while c < col_max:
            c_start = c
            c_end = c_start + patch_size

            coords.append({
                "r_start": r_start,
                "r_end": r_end,
                "c_start": c_start,
                "c_end": c_end,
                "src_r_end": min(r_end, row_max),
                "src_c_end": min(c_end, col_max),
            })
            c += stride
        r += stride

    return coords


class SARPatchDataset(Dataset):
    """
    Dataset for Sentinel-1 Pre/Post Flood SAR and Pseudo-Label Masks.

    Inputs:
        Channel 0: Pre-flood VV (normalized [0, 1])
        Channel 1: Post-flood VV (normalized [0, 1])
    Target:
        Filtered flood mask (0 = dry, 1 = flood)
    Validity:
        Boolean mask (True = real satellite pixel, False = padded edge or invalid)
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
    ):
        """
        Initializes the dataset with in-memory arrays.

        Args:
            pre_flood: 2D array of pre-flood VV SAR (in dB).
            post_flood: 2D array of post-flood VV SAR (in dB).
            target_mask: 2D array of binary pseudo-labels (0 or 1).
            split: 'train', 'val', or 'all'.
            patch_size: Dimension of square patches (default: 256).
            stride: Stride between patches (default: patch_size).
            train_col_boundary: Column dividing train from guard band.
            guard_band_pixels: Pixel buffer between train and val zones.
            min_db: Minimum dB for normalization.
            max_db: Maximum dB for normalization.
        """
        if pre_flood.shape != post_flood.shape or pre_flood.shape != target_mask.shape:
            raise ValueError(
                f"Array shape mismatch: pre {pre_flood.shape}, "
                f"post {post_flood.shape}, target {target_mask.shape}"
            )

        self.height, self.width = pre_flood.shape
        self.patch_size = patch_size
        self.split = split.lower()
        self.min_db = min_db
        self.max_db = max_db

        # Normalize SAR imagery and record stats
        self.pre_norm, self.pre_stats = normalize_sar_db(pre_flood, min_db=min_db, max_db=max_db)
        self.post_norm, self.post_stats = normalize_sar_db(post_flood, min_db=min_db, max_db=max_db)

        # Ensure target is uint8 binary (0 or 1)
        self.target = (target_mask == 1).astype(np.float32)

        # Compute validity map for source arrays (False if either SAR is invalid)
        self.src_valid = ~(np.isnan(pre_flood) | np.isinf(pre_flood) |
                           np.isnan(post_flood) | np.isinf(post_flood))

        # Spatial splitting boundaries
        # Train: cols [0, train_col_boundary)
        # Guard band: cols [train_col_boundary, train_col_boundary + guard_band_pixels)
        # Val: cols [train_col_boundary + guard_band_pixels, width)
        val_col_start = train_col_boundary + guard_band_pixels

        self.train_bounds = {"col_min": 0, "col_max": train_col_boundary}
        self.guard_bounds = {"col_min": train_col_boundary, "col_max": val_col_start}
        self.val_bounds = {"col_min": val_col_start, "col_max": self.width}

        if self.split == "train":
            self.patch_coords = generate_patch_coordinates(
                height=self.height,
                width=self.width,
                patch_size=patch_size,
                stride=stride,
                col_min=self.train_bounds["col_min"],
                col_max=self.train_bounds["col_max"],
            )
        elif self.split == "val":
            self.patch_coords = generate_patch_coordinates(
                height=self.height,
                width=self.width,
                patch_size=patch_size,
                stride=stride,
                col_min=self.val_bounds["col_min"],
                col_max=self.val_bounds["col_max"],
            )
        elif self.split == "all":
            self.patch_coords = generate_patch_coordinates(
                height=self.height,
                width=self.width,
                patch_size=patch_size,
                stride=stride,
                col_min=0,
                col_max=self.width,
            )
        else:
            raise ValueError(f"Unknown split: {split}. Expected 'train', 'val', or 'all'.")

    def __len__(self) -> int:
        return len(self.patch_coords)

    def __getitem__(self, idx: int) -> Dict[str, torch.Tensor]:
        coord = self.patch_coords[idx]
        r_start, r_end = coord["r_start"], coord["r_end"]
        c_start, c_end = coord["c_start"], coord["c_end"]

        # Valid source slice bounds
        src_r_end = min(r_end, self.height)
        src_c_end = min(c_end, self.width)

        h_valid = src_r_end - r_start
        w_valid = src_c_end - c_start

        # Allocate padded patch buffers [channels, patch_size, patch_size]
        image_patch = np.zeros((2, self.patch_size, self.patch_size), dtype=np.float32)
        target_patch = np.zeros((1, self.patch_size, self.patch_size), dtype=np.float32)
        valid_patch = np.zeros((1, self.patch_size, self.patch_size), dtype=bool)

        if h_valid > 0 and w_valid > 0:
            # Channel 0: Pre-flood VV
            image_patch[0, :h_valid, :w_valid] = self.pre_norm[r_start:src_r_end, c_start:src_c_end]
            # Channel 1: Post-flood VV
            image_patch[1, :h_valid, :w_valid] = self.post_norm[r_start:src_r_end, c_start:src_c_end]
            # Target mask
            target_patch[0, :h_valid, :w_valid] = self.target[r_start:src_r_end, c_start:src_c_end]
            # Validity (only real, unpadded, non-NaN pixels are valid)
            valid_patch[0, :h_valid, :w_valid] = self.src_valid[r_start:src_r_end, c_start:src_c_end]

        return {
            "image": torch.from_numpy(image_patch),           # [2, 256, 256]
            "target": torch.from_numpy(target_patch),         # [1, 256, 256]
            "valid_mask": torch.from_numpy(valid_patch),     # [1, 256, 256]
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
    ) -> "SARPatchDataset":
        """Factory constructor that loads and aligns GeoTIFF files from disk."""
        for p, name in [(pre_flood_path, "pre-flood"), (post_flood_path, "post-flood"), (mask_path, "mask")]:
            if not p.exists():
                raise FileNotFoundError(f"Missing {name} GeoTIFF file at: {p}")

        with rasterio.open(pre_flood_path) as s_pre:
            pre_arr = s_pre.read(1)
            pre_crs = s_pre.crs
            pre_shape = s_pre.shape

        with rasterio.open(post_flood_path) as s_post:
            post_arr = s_post.read(1)
            post_crs = s_post.crs
            post_shape = s_post.shape

        with rasterio.open(mask_path) as s_mask:
            mask_arr = s_mask.read(1)
            mask_crs = s_mask.crs
            mask_shape = s_mask.shape

        if pre_shape != post_shape or pre_shape != mask_shape:
            raise ValueError(
                f"Raster shape mismatch: pre {pre_shape}, post {post_shape}, mask {mask_shape}"
            )
        if pre_crs != post_crs or pre_crs != mask_crs:
            raise ValueError(
                f"CRS mismatch: pre {pre_crs}, post {post_crs}, mask {mask_crs}"
            )

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
        )
