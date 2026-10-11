"""
U-Net Segmentation Model for SAHAYAK Flood Mapping.

This module defines a U-Net architecture with a ResNet34 encoder for binary
flood extent mapping from satellite imagery (Sentinel-1 SAR).

Provisional Input Contract:
- Shape: [batch_size, 2, height, width]
  - Channel 0: Pre-flood SAR VV imagery
  - Channel 1: Post-flood SAR VV imagery
  (Provisional assumption pending data-pipeline confirmation from Ravi)

Output Contract:
- Shape: [batch_size, 1, height, width]
  - Raw unnormalized logits for binary segmentation (Flood vs. Non-Flood).
  - Note: Sigmoid is NOT applied internally so that numerical stability
    is maintained when training with torch.nn.BCEWithLogitsLoss.
  - To obtain probability masks during inference: probs = torch.sigmoid(logits).

Status:
- Untrained architecture initialized with random weights (encoder_weights=None).
- Does not claim to detect floods accurately until trained on ground truth.
"""

from typing import Optional
import torch
import torch.nn as nn
import segmentation_models_pytorch as smp


class FloodUNet(nn.Module):
    """
    U-Net segmentation model wrapper with ResNet34 encoder.

    Args:
        in_channels: Number of input raster channels (default: 2, e.g. pre- & post-flood VV).
        classes: Number of target segmentation classes (default: 1 for binary flood logit map).
        encoder_name: Backbone encoder name (default: "resnet34").
        encoder_weights: Pretrained weights to load (default: None, prevents automatic download).
    """

    def __init__(
        self,
        in_channels: int = 2,
        classes: int = 1,
        encoder_name: str = "resnet34",
        encoder_weights: Optional[str] = None,
    ):
        super().__init__()
        if in_channels <= 0:
            raise ValueError(f"in_channels must be positive, got {in_channels}")
        if classes <= 0:
            raise ValueError(f"classes must be positive, got {classes}")

        self.in_channels = in_channels
        self.classes = classes
        self.encoder_name = encoder_name

        # Construct U-Net architecture using segmentation_models_pytorch.
        # activation=None ensures raw logits are returned (crucial for BCEWithLogitsLoss).
        self.model = smp.Unet(
            encoder_name=encoder_name,
            encoder_weights=encoder_weights,
            in_channels=in_channels,
            classes=classes,
            activation=None,
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        """
        Forward pass of the segmentation model.

        Args:
            x: Input tensor of shape [batch, in_channels, height, width].

        Returns:
            Logits tensor of shape [batch, classes, height, width].
        """
        if x.dim() != 4:
            raise ValueError(
                f"Expected 4D input tensor [batch, channels, height, width], "
                f"got {x.dim()}D tensor of shape {list(x.shape)}"
            )
        if x.shape[1] != self.in_channels:
            raise ValueError(
                f"Expected {self.in_channels} input channels, "
                f"got {x.shape[1]} channels in tensor of shape {list(x.shape)}"
            )

        return self.model(x)


def build_unet_model(
    in_channels: int = 2,
    classes: int = 1,
    encoder_name: str = "resnet34",
    encoder_weights: Optional[str] = None,
) -> FloodUNet:
    """
    Factory function to construct the SAHAYAK Flood U-Net model.

    Args:
        in_channels: Number of input image channels (default: 2 for [pre_flood_VV, post_flood_VV]).
        classes: Number of output segmentation classes (default: 1 for binary logits).
        encoder_name: Name of encoder backbone (default: "resnet34").
        encoder_weights: Pretrained weights identifier (default: None to prevent downloads).

    Returns:
        Instantiated FloodUNet model.
    """
    return FloodUNet(
        in_channels=in_channels,
        classes=classes,
        encoder_name=encoder_name,
        encoder_weights=encoder_weights,
    )
