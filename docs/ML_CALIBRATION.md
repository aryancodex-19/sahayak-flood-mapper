# SAHAYAK Flood Mapper — ML Calibration & Threshold Analysis

This document describes the validation metrics, threshold sweep findings, pseudo-label limitations, and operational rationale behind the decision threshold configuration for the SAHAYAK U-Net flood segmentation model.

---

## 1. Executive Summary & Default Threshold

- **Default Threshold**: $\tau = 0.50$ (retained for production pipeline and frontend export).
- **Peak Validation F1 Score**: $0.1515$ (at $\tau = 0.50$, IoU $= 0.0820$).
- **Validation Dataset**: Held-out East Kamrup patches (columns $832$ to $1114$, $6$ patches, $188,940$ valid pixels).
- **Key Decision**: Although the model over-predicts flood extent at $\tau = 0.50$ ($22.33\%$ predicted area vs. $4.62\%$ reference prevalence), raising the threshold to match prevalence ($\tau = 0.54$) causes recall to collapse from $44.17\%$ down to $10.43\%$ with negligible precision gain ($9.15\% \to 10.29\%$). For humanitarian disaster routing, missing isolated settlements (False Negatives) carries far higher operational risk than precautionary road reconnaissance (False Positives).

---

## 2. Root Cause of Over-Prediction

1. **Uncalibrated Model Logits**:
   The U-Net model's output probabilities are compressed into a narrow band:
   $$\min(p) = 0.2135, \quad \text{median}(p) = 0.4568, \quad \text{mean}(p) = 0.4507, \quad \max(p) = 0.6472$$
   The model never outputs high confidence ($> 0.65$) for any pixel in the scene.
2. **Loss Function Asymmetry**:
   The model was trained with `CombinedFloodLoss(bce_weight=1.0, dice_weight=1.0, pos_weight=5.0)`. The $5\times$ positive weighting penalizes false negatives heavily, shifting uncalibrated logits upward.
3. **Distribution Overlap**:
   The predicted probability distributions for positive and negative pixels overlap heavily between $0.45$ and $0.55$. As a result, shifting the threshold across this range changes the volume of predictions without meaningfully separating true floods from background noise.

---

## 3. Threshold Sweep Metrics (Validation Data Only)

Evaluation performed exclusively on the held-out validation patches (`split="val"`, East Kamrup):
- Total valid pixels: **188,940**
- Reference pseudo-label flood pixels: **8,734 (4.62%)**

### Standard Sweep Table

| Threshold | TP | FP | FN | TN | Precision | Recall | F1 Score | IoU | Pred Flood % | Ref Flood % |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **0.10** | 8,734 | 180,206 | 0 | 0 | 0.0462 | 1.0000 | 0.0884 | 0.0462 | 100.00% | 4.62% |
| **0.20** | 8,734 | 180,206 | 0 | 0 | 0.0462 | 1.0000 | 0.0884 | 0.0462 | 100.00% | 4.62% |
| **0.30** | 8,734 | 178,908 | 0 | 1,298 | 0.0465 | 1.0000 | 0.0890 | 0.0465 | 99.31% | 4.62% |
| **0.40** | 8,547 | 141,211 | 187 | 38,995 | 0.0571 | 0.9786 | 0.1079 | 0.0570 | 79.26% | 4.62% |
| **0.45** | 7,371 | 94,924 | 1,363 | 85,282 | 0.0721 | 0.8439 | 0.1328 | 0.0711 | 54.14% | 4.62% |
| **0.50 (Baseline)** | **3,858** | **38,328** | **4,876** | **141,878** | **0.0915** | **0.4417** | **0.1515** | **0.0820** | **22.33%** | **4.62%** |
| **0.54 (Prevalence)** | **911** | **7,944** | **7,823** | **172,262** | **0.1029** | **0.1043** | **0.1036** | **0.0546** | **4.69%** | **4.62%** |
| **0.55** | 498 | 4,480 | 8,236 | 175,726 | 0.1000 | 0.0570 | 0.0726 | 0.0377 | 2.63% | 4.62% |
| **0.60** | 6 | 75 | 8,728 | 180,131 | 0.0741 | 0.0007 | 0.0014 | 0.0007 | 0.04% | 4.62% |
| **0.65 – 0.90** | 0 | 0 | 8,734 | 180,206 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0.00% | 4.62% |

---

## 4. Candidate Trade-Off Analysis

1. **Baseline Candidate ($\tau = 0.500$)**:
   - Precision: $9.15\%$, Recall: $44.17\%$, F1: $0.1515$, IoU: $0.0820$.
   - Predicted Flood Area: $22.33\%$ ($42,186$ pixels).
   - **Trade-off**: Retains the highest F1 score and captures $44.17\%$ of reference flood pixels, providing adequate sensitivity for downstream road network cutting.
2. **Prevalence-Matched Candidate ($\tau = 0.540$)**:
   - Precision: $10.29\%$, Recall: $10.43\%$, F1: $0.1036$, IoU: $0.0546$.
   - Predicted Flood Area: $4.69\%$ ($8,855$ pixels, matching the $4.62\%$ reference rate).
   - **Trade-off**: Reduces false-positive pixels by $79.3\%$, but misses $89.57\%$ of reference flood pixels ($7,823$ false negatives). Precision remains poor ($10.29\%$).

---

## 5. Pseudo-Label Limitations & Evaluation Integrity

1. **Heuristic Nature of Pseudo-Labels**:
   The reference mask (`flood_mask_20220620_filtered.tif`) is not ground truth from optical imagery or field surveys. It was generated using traditional backscatter change detection thresholding and DEM slope filtering. Many inundated vegetation areas are omitted in the label.
2. **VV Polarization Radar Artifacts**:
   Smooth surfaces (airports, flat highways, bare sandy soil) exhibit low radar backscatter in VV polarization similar to open water, producing natural false positives.
3. **Small Sample Size**:
   The validation split contains only 6 patches from a single scene. Threshold tuning must not be mistaken for model recalibration.

---

## 6. How to Run Threshold Evaluation

The calibration tool can be executed at any time without altering production checkpoints or frontend data:

```powershell
& "ml-model/.venv/Scripts/python.exe" ml-model/scripts/evaluate_thresholds.py
```

Outputs are saved in `ml-model/outputs/experiments/threshold_calibration/`:
- `threshold_evaluation.json`: Full machine-readable confusion matrices and statistics.
- `threshold_summary.md`: Human-readable summary table.
