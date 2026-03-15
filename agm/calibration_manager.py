"""
CalibrationManager Module - AgM
Manages calibration reference data storage and retrieval.
"""

from typing import List, Optional
from agm.file_manager import FileManager

class CalibrationManager:
    def __init__(self, file_manager: FileManager):
        """Initialize calibration manager with file manager."""
        self.file_manager = file_manager
        self.channel_labels = [
            "410nm", "435nm", "460nm", "485nm", "510nm", "535nm",
            "560nm", "585nm", "610nm", "645nm", "680nm", "705nm",
            "730nm", "760nm", "810nm", "860nm", "900nm", "940nm"
        ]
    
    def save_calibration(self, values: List[float]) -> Optional[str]:
        """
        Save calibration data to .txt file in readable format.
        Returns file path on success.
        """
        if len(values) != 18:
            print(f"[ERROR] Expected 18 channels, got {len(values)}")
            return None
        
        # Format calibration data
        lines = ["CALIBRATION REFERENCE DATA", "=" * 50, ""]
        for i, (label, val) in enumerate(zip(self.channel_labels, values)):
            lines.append(f"{label}: {val:.2f}")
        
        lines.append("")
        lines.append("=" * 50)
        lines.append("Use this calibration for measurement normalization")
        
        data = "\n".join(lines)
        return self.file_manager.write_txt("AgM_CalibMeasurements", data)
    
    def load_latest_calibration(self) -> Optional[List[float]]:
        """
        Load the latest calibration file.
        Returns calibration data (18 values) or None if not found.
        """
        return self.file_manager.find_latest_calibration()
