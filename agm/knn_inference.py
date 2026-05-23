"""
knn_inference.py — AgM KNN Classifier Module
Implements k=1 nearest-centroid classification for N, P, K saturation levels.
Uses hardcoded protocol centroids (PRESSED / 10MM / FIELD) from
AgM_MasterDataset_25-04-26.xlsx — Norm_Reflactance sheet.

No external ML library required — pure NumPy Euclidean distance.
Ref: AgM_SRS_Inference_V0.4.1 §3.1 / §3.2
"""

import numpy as np
from typing import Dict, List


# ── Channel order (AS7265x 18-channel, 410–940 nm) ───────────────────
CHANNEL_LABELS = [
    "410nm", "435nm", "460nm", "485nm", "510nm", "535nm",
    "560nm", "585nm", "610nm", "645nm", "680nm", "705nm",
    "730nm", "760nm", "810nm", "860nm", "900nm", "940nm"
]


def load_centroids() -> Dict[str, List[float]]:
    """
    Return hardcoded protocol centroids for the 5 FIRA soil samples.
    Source: AgM_MasterDataset_25-04-26.xlsx — Norm_Reflactance sheet
    Protocol: PRESSED / 10MM depth / FIELD moisture (3 replicates averaged)
    """
    return {
        "MS-788": [5.6092, 5.3831, 7.5085, 6.8647, 6.9688, 6.8703,
                   5.6166, 5.3796, 5.6189, 7.5114, 5.3958, 6.8716,
                   7.5200, 6.8737, 6.9776, 6.8787, 6.9708, 6.8830],
        "MS-789": [5.9142, 5.8696, 7.9763, 7.2894, 7.3935, 7.2950,
                   5.9213, 5.8843, 5.9236, 7.9784, 5.9005, 7.2963,
                   7.9847, 7.2984, 7.4023, 7.3034, 7.3955, 7.3077],
        "MS-900": [6.0095, 5.9649, 8.0666, 7.3847, 7.4888, 7.3903,
                   6.0166, 5.9796, 6.0189, 8.0714, 5.9958, 7.3916,
                   8.0800, 7.3937, 7.4976, 7.3987, 7.4908, 7.4030],
        "MS-983": [4.8821, 4.8375, 6.9392, 6.2473, 6.3514, 6.2529,
                   4.8892, 4.8522, 4.8915, 6.9440, 4.8684, 6.2542,
                   6.9526, 6.2563, 6.3602, 6.2613, 6.3534, 6.2656],
        "MS-986": [6.5721, 6.5275, 8.6386, 7.9467, 8.0508, 7.9523,
                   6.5792, 6.5422, 6.5815, 8.6434, 6.5584, 7.9536,
                   8.6520, 7.9557, 8.0596, 7.9607, 8.0528, 7.9650],
    }


def load_fira_labels() -> Dict[str, Dict[str, str]]:
    """
    Return hardcoded FIRA NPK saturation levels for the 5 soil samples.
    Source: FIRA-Banco de Mexico laboratory analysis.
    Ref: AgM_SRS_Inference_V0.4.1 §3.2
    """
    return {
        "MS-788": {"N": "MEDIUM", "P": "LOW",    "K": "MEDIUM",
                   "N_mg_kg": 25.30, "P_mg_kg": 8.45,   "K_mg_kg": 185.50},
        "MS-789": {"N": "HIGH",   "P": "LOW",    "K": "LOW",
                   "N_mg_kg": 42.10, "P_mg_kg": 9.20,   "K_mg_kg": 120.30},
        "MS-900": {"N": "HIGH",   "P": "HIGH",   "K": "LOW",
                   "N_mg_kg": 38.50, "P_mg_kg": 32.55,  "K_mg_kg": 298.08},
        "MS-983": {"N": "LOW",    "P": "LOW",    "K": "LOW",
                   "N_mg_kg": 12.80, "P_mg_kg": 6.30,   "K_mg_kg": 98.40},
        "MS-986": {"N": "HIGH",   "P": "HIGH",   "K": "HIGH",
                   "N_mg_kg": 45.20, "P_mg_kg": 38.90,  "K_mg_kg": 520.70},
    }


def euclidean_distance(a: List[float], b: List[float]) -> float:
    """
    Compute Euclidean distance between two 18-channel reflectance vectors.
    """
    return float(np.sqrt(np.sum((np.array(a) - np.array(b)) ** 2)))


def knn_predict(r_new: List[float]) -> Dict:
    """
    Find the nearest centroid to r_new using k=1 KNN (Euclidean distance).
    Returns dict with keys: sample, N, P, K, N_mg_kg, P_mg_kg, K_mg_kg, distance.
    Ref: AgM_SRS_Inference_V0.4.1 §3.1
    """
    centroids = load_centroids()
    labels    = load_fira_labels()

    best_sample   = None
    best_distance = float("inf")

    for sample, centroid in centroids.items():
        d = euclidean_distance(r_new, centroid)
        if d < best_distance:
            best_distance = d
            best_sample   = sample

    result = {
        "sample":    best_sample,
        "distance":  round(best_distance, 4),
        "N":         labels[best_sample]["N"],
        "P":         labels[best_sample]["P"],
        "K":         labels[best_sample]["K"],
        "N_mg_kg":   labels[best_sample]["N_mg_kg"],
        "P_mg_kg":   labels[best_sample]["P_mg_kg"],
        "K_mg_kg":   labels[best_sample]["K_mg_kg"],
    }
    return result


def confidence_label(distance: float) -> str:
    """
    Map Euclidean distance to confidence level.
    Thresholds from AgM_SRS_Inference_V0.4.1 §3.2:
      HIGH   d < 5.0
      MEDIUM 5.0 <= d <= 20.0
      LOW    d > 20.0
    """
    if distance < 5.0:
        return "HIGH"
    elif distance <= 20.0:
        return "MEDIUM"
    else:
        return "LOW"
