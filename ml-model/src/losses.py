"""
Loss Functions and Valid-Pixel-Aware Evaluation Metrics for SAHAYAK Flood Mapping.

This module provides:
1. Masked BCEWithLogitsLoss: Applied strictly to valid pixels (ignoring padding/invalid).
2. Masked DiceLoss: Measures overlap strictly on valid pixels with smoothing.
3. CombinedFloodLoss: Weighted sum of Masked BCE and Masked Dice loss.
4. Valid-pixel evaluation metrics: Precision, Recall, F1/Dice, and IoU (Jaccard Index).
"""

from typing import Dict, Optional, Tuple
import torch
import torch.nn as nn
import torch.nn.functional as F


class MaskedBCEWithLogitsLoss(nn.Module):
    """
    Binary Cross-Entropy with Logits applied strictly to valid pixels.
    """

    def __init__(self, pos_weight: Optional[float] = None):
        super().__init__()
        self.pos_weight_val = pos_weight

    def forward(self, logits: torch.Tensor, targets: torch.Tensor, valid_mask: torch.Tensor) -> torch.Tensor:
        """
        Args:
            logits: Unnormalized model predictions [B, 1, H, W]
            targets: Binary ground truth / pseudo-labels [B, 1, H, W] (0.0 or 1.0)
            valid_mask: Boolean tensor [B, 1, H, W] (True for valid pixels, False for padding/invalid)

        Returns:
            Scalar loss tensor.
        """
        # Ensure valid_mask is boolean
        mask_bool = valid_mask.bool()

        if not mask_bool.any():
            return torch.tensor(0.0, device=logits.device, requires_grad=True)

        valid_logits = logits[mask_bool]
        valid_targets = targets[mask_bool]

        if self.pos_weight_val is not None:
            pw_tensor = torch.tensor([self.pos_weight_val], device=logits.device, dtype=logits.dtype)
            return F.binary_cross_entropy_with_logits(valid_logits, valid_targets, pos_weight=pw_tensor)
        else:
            return F.binary_cross_entropy_with_logits(valid_logits, valid_targets)


class MaskedDiceLoss(nn.Module):
    """
    Dice Loss computed exclusively on valid pixels.
    """

    def __init__(self, smooth: float = 1e-6):
        super().__init__()
        self.smooth = smooth

    def forward(self, logits: torch.Tensor, targets: torch.Tensor, valid_mask: torch.Tensor) -> torch.Tensor:
        """
        Args:
            logits: Raw logits [B, 1, H, W]
            targets: Binary targets [B, 1, H, W]
            valid_mask: Boolean valid mask [B, 1, H, W]

        Returns:
            Scalar Dice loss (1.0 - Dice coefficient).
        """
        mask_bool = valid_mask.bool()

        if not mask_bool.any():
            return torch.tensor(0.0, device=logits.device, requires_grad=True)

        probs = torch.sigmoid(logits)
        valid_probs = probs[mask_bool]
        valid_targets = targets[mask_bool]

        intersection = torch.sum(valid_probs * valid_targets)
        cardinality = torch.sum(valid_probs) + torch.sum(valid_targets)

        dice_score = (2.0 * intersection + self.smooth) / (cardinality + self.smooth)
        return 1.0 - dice_score


class CombinedFloodLoss(nn.Module):
    """
    Weighted combination of Masked BCEWithLogitsLoss and Masked DiceLoss.
    """

    def __init__(
        self,
        bce_weight: float = 1.0,
        dice_weight: float = 1.0,
        pos_weight: Optional[float] = None,
        smooth: float = 1e-6,
    ):
        super().__init__()
        self.bce_weight = bce_weight
        self.dice_weight = dice_weight
        self.bce_loss = MaskedBCEWithLogitsLoss(pos_weight=pos_weight)
        self.dice_loss = MaskedDiceLoss(smooth=smooth)

    def forward(
        self,
        logits: torch.Tensor,
        targets: torch.Tensor,
        valid_mask: torch.Tensor,
    ) -> Tuple[torch.Tensor, Dict[str, float]]:
        """
        Computes the combined loss and component dictionary.
        """
        bce = self.bce_loss(logits, targets, valid_mask)
        dice = self.dice_loss(logits, targets, valid_mask)

        total_loss = self.bce_weight * bce + self.dice_weight * dice
        metrics = {
            "loss_total": float(total_loss.detach().item()),
            "loss_bce": float(bce.detach().item()),
            "loss_dice": float(dice.detach().item()),
        }

        return total_loss, metrics


def compute_valid_metrics(
    logits: torch.Tensor,
    targets: torch.Tensor,
    valid_mask: torch.Tensor,
    threshold: float = 0.5,
    eps: float = 1e-7,
) -> Dict[str, float]:
    """
    Computes Precision, Recall, F1/Dice, and IoU exclusively on valid pixels.

    Args:
        logits: Model output logits [B, 1, H, W]
        targets: Target masks [B, 1, H, W]
        valid_mask: Valid pixel mask [B, 1, H, W]
        threshold: Probability threshold for positive classification (default: 0.5)
        eps: Epsilon for numerical stability

    Returns:
        Dictionary of computed metrics and pixel counts.
    """
    with torch.no_grad():
        mask_bool = valid_mask.bool()

        if not mask_bool.any():
            return {
                "precision": 0.0,
                "recall": 0.0,
                "f1": 0.0,
                "iou": 0.0,
                "tp": 0,
                "fp": 0,
                "fn": 0,
                "tn": 0,
                "valid_pixels": 0,
            }

        probs = torch.sigmoid(logits)[mask_bool]
        y_true = (targets[mask_bool] >= 0.5).float()
        y_pred = (probs >= threshold).float()

        tp = float(torch.sum(y_pred * y_true).item())
        fp = float(torch.sum(y_pred * (1.0 - y_true)).item())
        fn = float(torch.sum((1.0 - y_pred) * y_true).item())
        tn = float(torch.sum((1.0 - y_pred) * (1.0 - y_true)).item())

        precision = (tp + eps) / (tp + fp + eps)
        recall = (tp + eps) / (tp + fn + eps)
        f1 = (2.0 * precision * recall) / (precision + recall + eps)
        iou = (tp + eps) / (tp + fp + fn + eps)

        # If there are no positive predictions and no positive targets, IoU is 1.0 (perfect background agreement)
        if (tp + fp + fn) == 0:
            iou = 1.0
            f1 = 1.0
            precision = 1.0
            recall = 1.0

        return {
            "precision": float(precision),
            "recall": float(recall),
            "f1": float(f1),
            "iou": float(iou),
            "tp": int(tp),
            "fp": int(fp),
            "fn": int(fn),
            "tn": int(tn),
            "valid_pixels": int(mask_bool.sum().item()),
        }
