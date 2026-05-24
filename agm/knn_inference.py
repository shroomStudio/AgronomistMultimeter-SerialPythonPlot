"""
knn_inference.py — AgM KNN Classifier Module
Implements k=1 nearest-centroid classification for N, P, K saturation levels.

Source of truth: KNN_ReferenceData skill / AgM_MasterDataset_25-04-26.xlsx
Centroids: PRESSED / 10MM / FIELD protocol, 3 replicates averaged per sample.
Reference calibration: Calibration05.
Normalization: R(λᵢ) = I_sample(λᵢ) / I_white(λᵢ) × 100%

IMPORTANT: All numeric values in this file come directly from
AgM_MasterDataset_25-04-26.xlsx — Norm_Reflactance sheet.
NEVER modify these values without re-extracting from the source dataset.
"""

import numpy as np
from typing import Dict, List


CHANNEL_LABELS = [
    "410nm", "435nm", "460nm", "485nm", "510nm", "535nm",
    "560nm", "585nm", "610nm", "645nm", "680nm", "705nm",
    "730nm", "760nm", "810nm", "860nm", "900nm", "940nm"
]


def load_centroids() -> Dict[str, List[float]]:
    """
    Real protocol centroids — PRESSED / 10MM / FIELD, 3 replicates averaged.
    Source: AgM_MasterDataset_25-04-26.xlsx — Norm_Reflactance sheet.
    Channel order: 410,435,460,485,510,535,560,585,610,645,680,705,730,760,810,860,900,940 nm
    """
    return {
        "MS-788": [ 6.1477,  5.8135,  7.4381,  6.9261,  6.6907,  6.5576,
                    5.6772,  5.9726,  5.6231,  7.4115,  5.9868,  6.9322,
                    7.4444,  6.9350,  7.0359,  6.9397,  7.0308,  6.9430],
        "MS-789": [ 5.1973,  4.4217,  6.1231,  5.4067,  5.4178,  5.0419,
                    4.8282,  4.6395,  4.6448,  6.0750,  4.6400,  5.4201,
                    6.1231,  5.4037,  5.6166,  5.3571,  5.6210,  5.3571],
        "MS-900": [ 6.5238,  6.3643,  7.9723,  7.6319,  7.2659,  7.3694,
                    5.9938,  6.4830,  5.9814,  7.9304,  6.4852,  7.5538,
                    7.9608,  7.6177,  7.6833,  7.8337,  7.6757,  7.8467],
        "MS-983": [11.9803, 11.7741, 14.1816, 13.6038, 13.0337, 13.0429,
                   11.2245, 11.9915, 11.2253, 14.1990, 12.0179, 13.6168,
                   14.2401, 13.6520, 13.6907, 13.6916, 13.6627, 13.6818],
        "MS-986": [24.9624, 26.9437, 30.6673, 30.1042, 27.9438, 28.6710,
                   22.9060, 27.0913, 23.6528, 30.7664, 27.1227, 30.2107,
                   30.6521, 30.0707, 29.6267, 29.5881, 29.6080, 29.5751],
    }


def load_fira_labels() -> Dict[str, Dict]:
    """
    FIRA-Banco de México NPK saturation levels and reference concentrations.
    Source: FIRA laboratory analysis — AgM_MasterDataset_25-04-26.xlsx.
    """
    return {
        "MS-788": {"N": "MEDIUM", "P": "LOW",  "K": "MEDIUM",
                   "N_mg_kg": 25.30, "P_mg_kg":  8.45, "K_mg_kg": 185.50},
        "MS-789": {"N": "HIGH",   "P": "LOW",  "K": "LOW",
                   "N_mg_kg": 42.10, "P_mg_kg":  9.20, "K_mg_kg": 120.30},
        "MS-900": {"N": "HIGH",   "P": "HIGH", "K": "LOW",
                   "N_mg_kg": 38.50, "P_mg_kg": 32.55, "K_mg_kg": 298.08},
        "MS-983": {"N": "LOW",    "P": "LOW",  "K": "LOW",
                   "N_mg_kg": 12.80, "P_mg_kg":  6.30, "K_mg_kg":  98.40},
        "MS-986": {"N": "HIGH",   "P": "HIGH", "K": "HIGH",
                   "N_mg_kg": 45.20, "P_mg_kg": 38.90, "K_mg_kg": 520.70},
    }


def euclidean_distance(a: List[float], b: List[float]) -> float:
    """Euclidean distance between two 18-channel reflectance vectors."""
    return float(np.sqrt(np.sum((np.array(a) - np.array(b)) ** 2)))


def knn_predict(r_new: List[float]) -> Dict:
    """
    k=1 nearest-centroid classification on R[18].
    Returns matched sample, NPK levels, FIRA concentrations, and distance.
    Source of centroids: AgM_MasterDataset_25-04-26.xlsx — Norm_Reflactance.
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
        "sample":   best_sample,
        "distance": round(best_distance, 4),
        "N":        labels[best_sample]["N"],
        "P":        labels[best_sample]["P"],
        "K":        labels[best_sample]["K"],
        "N_mg_kg":  labels[best_sample]["N_mg_kg"],
        "P_mg_kg":  labels[best_sample]["P_mg_kg"],
        "K_mg_kg":  labels[best_sample]["K_mg_kg"],
    }
    return result


def confidence_label(distance: float) -> str:
    """
    Map Euclidean distance to confidence level.
    Thresholds: HIGH d<5.0 / MEDIUM 5.0-20.0 / LOW d>20.0
    """
    if distance < 5.0:
        return "HIGH"
    elif distance <= 20.0:
        return "MEDIUM"
    else:
        return "LOW"
