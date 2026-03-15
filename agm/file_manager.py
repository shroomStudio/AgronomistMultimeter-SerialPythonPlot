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
            base_path = os.path.expanduser("~/Documents/AgMReadings")
        
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
    
    def get_filename_timestamp(self, prefix: str) -> str:
        """Generate filename with date and time."""
        now = datetime.now()
        timestamp = now.strftime("%Y%m%d_%H%M%S")
        return f"{prefix}_{timestamp}"
    
    def write_txt(self, prefix: str, data: str) -> Optional[str]:
        """
        Write measurement/calibration data to .txt file.
        Returns file path on success, None on failure.
        """
        try:
            filename = self.get_filename_timestamp(prefix) + ".txt"
            filepath = self.base_path / filename
            
            with open(filepath, 'w') as f:
                f.write(data)
            
            print(f"[INFO] Saved: {filepath}")
            return str(filepath)
        except Exception as e:
            print(f"[ERROR] Failed to write txt file: {e}")
            return None
    
    def write_png(self, prefix: str, fig) -> Optional[str]:
        """
        Save matplotlib figure as PNG.
        Returns file path on success, None on failure.
        """
        try:
            filename = self.get_filename_timestamp(prefix) + ".png"
            filepath = self.base_path / filename
            
            fig.savefig(filepath, dpi=100, bbox_inches='tight')
            print(f"[INFO] Saved: {filepath}")
            return str(filepath)
        except Exception as e:
            print(f"[ERROR] Failed to write PNG file: {e}")
            return None
    
    def find_latest_calibration(self) -> Optional[List[float]]:
        """
        Find and load the latest calibration file.
        Returns calibration data or None if not found.
        """
        try:
            calib_files = sorted(self.base_path.glob("AgM_CalibMeasurements_*.txt"))
            if not calib_files:
                print("[WARN] No calibration file found")
                return None
            
            latest_file = calib_files[-1]
            print(f"[INFO] Loading calibration from: {latest_file}")
            
            with open(latest_file, 'r') as f:
                content = f.read()
            
            # Parse calibration data (format: "Wavelength: value")
            calib_data = []
            for line in content.split('\n'):
                if ': ' in line:
                    try:
                        val = float(line.split(': ')[1].strip())
                        calib_data.append(val)
                    except ValueError:
                        continue
            
            if len(calib_data) == 18:
                return calib_data
            else:
                print(f"[WARN] Calibration has {len(calib_data)} values, expected 18")
                return None
        except Exception as e:
            print(f"[ERROR] Failed to load calibration: {e}")
            return None
