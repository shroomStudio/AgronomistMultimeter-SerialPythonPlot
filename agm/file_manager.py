"""
FileManager Module - AgM
Manages file creation, directory structure, and data persistence.
"""

import os
from pathlib import Path
from datetime import datetime
from typing import List, Optional

class FileManager:
    def __init__(self, base_path: Optional[str] = None):
        """Initialize file manager with base directory."""
        if base_path is None:
            base_path = "/Users/jorgecortes/Documents/maestriaSistemasEmbebidosInfotec/multimetroAgronomo/ClaudeProject/AgM_Readings_2026/AgM_CalibrationReads"
        self.base_path = Path(base_path)
        self.ensure_dir()
    
    def ensure_dir(self) -> bool:
        """Create directory if it doesn't exist."""
        try:
            self.base_path.mkdir(parents=True, exist_ok=True)
            print(f"[INFO] Ensured directory: {self.base_path}")
            return True
        except Exception as e:
            print(f"[ERROR] Failed to create directory: {e}")
            return False
    
    def get_timestamp_formatted(self) -> str:
        """Generate timestamp in format Date_Day-MM-YR_Time_HR-MIN (valid for filenames)"""
        now = datetime.now()
        date_part = now.strftime("%d-%m-%y")
        time_part = now.strftime("%H-%M")
        return f"Date_{date_part}_Time_{time_part}"
    
    def write_txt(self, sample_name: str, data: str) -> Optional[str]:
        """
        Write sample measurement data to .txt file with format:
        AgM_SampleName_Reads_Date:Day/MM/YR_Time:HR:MIN.txt
        Returns file path on success, None on failure.
        """
        try:
            timestamp = self.get_timestamp_formatted()
            filename = f"AgM_{sample_name}_Reads_{timestamp}.txt"
            filepath = self.base_path / filename
            
            with open(filepath, 'w') as f:
                f.write(data)
            
            print(f"[INFO] Saved: {filepath}")
            return str(filepath)
        except Exception as e:
            print(f"[ERROR] Failed to write txt file: {e}")
            return None
    
    def write_png(self, sample_name: str, fig) -> Optional[str]:
        """
        Save matplotlib figure as PNG with format:
        AgM_SampleName_Plot_Date:Day/MM/YR_Time:HR:MIN.png
        Returns file path on success, None on failure.
        """
        try:
            timestamp = self.get_timestamp_formatted()
            filename = f"AgM_{sample_name}_Plot_{timestamp}.png"
            filepath = self.base_path / filename
            
            fig.savefig(filepath, dpi=100, bbox_inches='tight')
            print(f"[INFO] Saved: {filepath}")
            return str(filepath)
        except Exception as e:
            print(f"[ERROR] Failed to write PNG file: {e}")
            return None
    
    def find_latest_calibration(self) -> Optional[List[float]]:
        """
        Find and load the latest sample measurement file to use as reference.
        Returns calibration data or None if not found.
        """
        try:
            calib_files = sorted(self.base_path.glob("AgM_*_Reads_*.txt"))
            if not calib_files:
                print("[WARN] No previous sample measurement found")
                return None
            
            latest_file = calib_files[-1]
            print(f"[INFO] Loading reference from: {latest_file}")
            
            with open(latest_file, 'r') as f:
                content = f.read()
            
            # Parse measurement data (format: "Wavelength: value")
            calib_data = []
            for line in content.split('\n'):
                if ': ' in line and 'Raw=' in line:
                    try:
                        # Extract raw value from "Wavelength: Raw=X.XX, Normalized=Y.YY%"
                        parts = line.split('Raw=')[1].split(',')[0]
                        val = float(parts.strip())
                        calib_data.append(val)
                    except (ValueError, IndexError):
                        continue
            
            if len(calib_data) == 18:
                return calib_data
            else:
                print(f"[WARN] Measurement has {len(calib_data)} values, expected 18")
                return None
        except Exception as e:
            print(f"[ERROR] Failed to load reference data: {e}")
            return None
