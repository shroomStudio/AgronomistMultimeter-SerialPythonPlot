"""
SampleMeasurementManager Module - AgM
Manages sample measurement data storage and retrieval.
"""

from typing import List, Optional
from agm.file_manager import FileManager

class CalibrationManager:
    """Manager for sample measurements (renamed from CalibrationManager)."""
    def __init__(self, file_manager: FileManager):
        """Initialize sample measurement manager with file manager."""
        self.file_manager = file_manager
        self.channel_labels = [
            "410nm", "435nm", "460nm", "485nm", "510nm", "535nm",
            "560nm", "585nm", "610nm", "645nm", "680nm", "705nm",
            "730nm", "760nm", "810nm", "860nm", "900nm", "940nm"
        ]
    
    def save_calibration(self, sample_name: str, values: List[float]) -> Optional[str]:
        """
        Save sample measurement data to .txt file in readable format.
        Args:
            sample_name: Name of the sample
            values: Raw measurement values (18 channels)
        Returns file path on success.
        """
        if len(values) != 18:
            print(f"[ERROR] Expected 18 channels, got {len(values)}")
            return None
        
        # Format sample measurement data
        lines = ["SAMPLE MEASUREMENT DATA", "=" * 50, ""]
        lines.append(f"Sample: {sample_name}")
        lines.append("")
        
        for label, val in zip(self.channel_labels, values):
            lines.append(f"{label}: {val:.2f}")
        
        lines.append("")
        lines.append("=" * 50)
        
        data = "\n".join(lines)
        return self.file_manager.write_txt(sample_name, data)
    
    def load_latest_calibration(self) -> Optional[List[float]]:
        """
        Load the latest sample measurement file as reference.
        Returns measurement data (18 values) or None if not found.
        """
        return self.file_manager.find_latest_calibration()
