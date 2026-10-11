"""
Minimal reproducible test for the SAHAYAK U-Net segmentation model.
"""

import unittest
import torch

from src.model import build_unet_model, FloodUNet


class TestFloodUNet(unittest.TestCase):
    """Test suite for initial FloodUNet model instantiation and forward pass."""

    def setUp(self):
        # Select CUDA when available, otherwise CPU
        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")

    def test_forward_pass_dummy_input(self):
        """Verify model forward pass with dummy 2-channel input tensor."""
        # Print selected device and hardware info
        print(f"\n[Test Setup] Selected device: {self.device}")
        if self.device.type == "cuda":
            print(f"[Test Setup] GPU Device Name: {torch.cuda.get_device_name(0)}")

        # 1. Construct model with 2 input channels, 1 output class, no pretrained weights
        model = build_unet_model(in_channels=2, classes=1, encoder_weights=None)
        self.assertIsInstance(model, FloodUNet)
        model.to(self.device)
        model.eval()

        # 2. Dummy input with shape [1, 2, 128, 128]
        # Low memory footprint: 1 * 2 * 128 * 128 * 4 bytes ~ 131 KB
        dummy_input = torch.randn(1, 2, 128, 128, device=self.device, dtype=torch.float32)

        # 3. Forward pass in eval mode with torch.no_grad()
        with torch.no_grad():
            output = model(dummy_input)

        # 4. Check that output shape matches [1, 1, 128, 128]
        expected_shape = (1, 1, 128, 128)
        self.assertEqual(
            output.shape,
            expected_shape,
            f"Expected output shape {expected_shape}, but got {output.shape}",
        )

        # 5. Check that all output values are finite (no NaNs or Infs)
        is_finite = torch.isfinite(output).all().item()
        self.assertTrue(
            is_finite,
            "Model output contains non-finite values (NaN or Inf).",
        )

        # 6. Print clear pass message
        print(
            f"[Test PASS] Device: {self.device} | "
            f"Input Shape: {list(dummy_input.shape)} | "
            f"Output Shape: {list(output.shape)} | "
            f"All values finite: {is_finite}"
        )


if __name__ == "__main__":
    unittest.main()
