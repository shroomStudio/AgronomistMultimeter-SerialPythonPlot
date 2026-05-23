"""
PlotManager Module - AgM
Handles spectrum plotting and figure generation. Does NOT display plots.
"""

import matplotlib.pyplot as plt
import matplotlib
matplotlib.use('Agg')  # Use non-interactive backend
import numpy as np
from typing import List, Optional

class PlotManager:
    def __init__(self, figsize: tuple = (14, 6)):
        """Initialize plot with channel labels."""
        self.channel_labels = [
            "410nm", "435nm", "460nm", "485nm", "510nm", "535nm",
            "560nm", "585nm", "610nm", "645nm", "680nm", "705nm",
            "730nm", "760nm", "810nm", "860nm", "900nm", "940nm"
        ]
        self.x_pos = np.arange(len(self.channel_labels))
        self.colors = plt.cm.nipy_spectral(np.linspace(0, 1, len(self.channel_labels)))
        
        self.fig = None
        self.ax = None
        self.bars = None
        self.y_max = 30000
    
    def create_figure(self, title: str = "AS7265x Spectrometer") -> None:
        """Create matplotlib figure and axes."""
        self.fig, self.ax = plt.subplots(1, 1, figsize=(14, 6))
        self.fig.suptitle(title, fontsize=14, fontweight='bold')
        
        self.bars = self.ax.bar(self.x_pos, [0] * len(self.channel_labels), 
                                color=self.colors, edgecolor='black', linewidth=0.5)
        
        self.ax.set_ylabel("Intensity", fontsize=11, fontweight='bold')
        self.ax.set_xlabel("Wavelength / Channel", fontsize=11, fontweight='bold')
        self.ax.set_xticks(self.x_pos)
        self.ax.set_xticklabels(self.channel_labels, rotation=45, ha='right', fontsize=9)
        self.ax.set_ylim(0, self.y_max)
        self.ax.grid(axis='y', alpha=0.3, linestyle='--')
        
        plt.tight_layout()
    
    def update_y_axis(self, values: List[float]) -> None:
        """Auto-adjust Y-axis based on max value in data."""
        if values:
            max_val = max(values)
            # Round up to nearest 1000
            new_max = int(np.ceil(max_val / 1000) * 1000)
            self.y_max = max(new_max, 1000)  # Minimum 1000
            self.ax.set_ylim(0, self.y_max)
            print(f"[INFO] Y-axis updated to: {self.y_max}")
    
    def update_bars(self, values: List[float]) -> None:
        """Update bar heights with new values."""
        if not self.bars:
            return
        
        for bar, height in zip(self.bars, values):
            bar.set_height(height)
    
    def plot_spectrum(self, values: List[float], title: str = "AS7265x Spectrometer") -> None:
        """Create a spectrum plot."""
        self.create_figure(title)
        self.update_y_axis(values)
        self.update_bars(values)
    
    def show(self) -> None:
        """Plot display is disabled - plots are saved to file only."""
        print("[INFO] Plot display disabled - plot will be saved to file")
    
    def save_figure(self, filepath: str) -> bool:
        """Save the current figure to file."""
        try:
            if self.fig:
                self.fig.savefig(filepath, dpi=100, bbox_inches='tight')
                print(f"[INFO] Plot saved to: {filepath}")
                return True
        except Exception as e:
            print(f"[ERROR] Failed to save plot: {e}")
            return False
    
    def close(self) -> None:
        """Close the figure."""
        if self.fig:
            plt.close(self.fig)

    # ── Inference Feature (PY-09) ─────────────────────────────────────

    def plot_inference(self, r_new: list, centroid: list, sample_id: str) -> None:
        """
        Overlay measured spectrum (r_new) and matched centroid on the same axes.
        Non-blocking — saves to file only (Agg backend).
        Ref: AgM_SRS_Inference_V0.4.1 §3.3 PY-09
        """
        fig, ax = plt.subplots(1, 1, figsize=(14, 6))
        fig.suptitle(f"AgM Inference — Matched: {sample_id}", fontsize=14, fontweight='bold')

        x = np.arange(len(self.channel_labels))
        width = 0.4

        ax.bar(x - width/2, r_new,   width, label="Measured R[18]",
               color=self.colors, edgecolor='black', linewidth=0.5, alpha=0.85)
        ax.bar(x + width/2, centroid, width, label=f"Centroid {sample_id}",
               color=self.colors, edgecolor='grey',  linewidth=0.5, alpha=0.45)

        ax.set_ylabel("Reflectance (%)", fontsize=11, fontweight='bold')
        ax.set_xlabel("Wavelength / Channel", fontsize=11, fontweight='bold')
        ax.set_xticks(x)
        ax.set_xticklabels(self.channel_labels, rotation=45, ha='right', fontsize=9)
        ax.legend(fontsize=10)
        ax.grid(axis='y', alpha=0.3, linestyle='--')
        plt.tight_layout()

        self.fig = fig
        self.ax  = ax
