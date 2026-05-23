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
        """
        Initialize file manager.
        Each day's readings go in ~/AgM_Reads_DDMMYY/ subdirectory.
        Directory is created automatically if it does not exist.
        """
        if base_path is None:
            base_path = str(Path.home() / "AgM_Reads")
        self._root = Path(base_path)
        # Daily subdirectory: AgM_Reads_DDMMYY
        today = datetime.now().strftime("%d%m%y")
        self.base_path = self._root / f"AgM_Reads_{today}"
        self.ensure_dir()

    def ensure_dir(self) -> bool:
        """Create daily directory if it does not exist."""
        try:
            self.base_path.mkdir(parents=True, exist_ok=True)
            print(f"[INFO] Output directory: {self.base_path}")
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

    # ── Inference Feature (PY-07 / PY-08) ────────────────────────────

    def save_inference_result(self, result_dict: dict) -> Optional[str]:
        """
        Write inference result to AgM_Inference_{TIMESTAMP}.txt.
        result_dict keys: sample, N, P, K, N_mg_kg, P_mg_kg, K_mg_kg,
                          distance, confidence, r_values (List[float])
        Ref: AgM_SRS_Inference_V0.4.1 §3.5
        """
        from datetime import datetime
        channel_labels = [
            "410nm", "435nm", "460nm", "485nm", "510nm", "535nm",
            "560nm", "585nm", "610nm", "645nm", "680nm", "705nm",
            "730nm", "760nm", "810nm", "860nm", "900nm", "940nm"
        ]
        try:
            timestamp  = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            r_values   = result_dict.get("r_values", [])
            sample     = result_dict.get("sample", "UNKNOWN")
            distance   = result_dict.get("distance", 0.0)
            confidence = result_dict.get("confidence", "N/A")
            n_level    = result_dict.get("N", "N/A")
            p_level    = result_dict.get("P", "N/A")
            k_level    = result_dict.get("K", "N/A")
            n_mg       = result_dict.get("N_mg_kg", 0.0)
            p_mg       = result_dict.get("P_mg_kg", 0.0)
            k_mg       = result_dict.get("K_mg_kg", 0.0)

            lines = [
                "INFERENCE RESULT",
                "=" * 48,
                f"Timestamp:        {timestamp}",
                f"Matched sample:   {sample}",
                f"Distance:         {distance:.4f}",
                f"Confidence:       {confidence}",
                "-" * 48,
                f"N (Nitrogen):     {n_level:<8} ({n_mg:.2f} mg/kg FIRA ref)",
                f"P (Phosphorus):   {p_level:<8} ({p_mg:.2f} mg/kg FIRA ref)",
                f"K (Potassium):    {k_level:<8} ({k_mg:.2f} mg/kg FIRA ref)",
                "-" * 48,
                "R[18] normalized reflectance (%):",
            ]
            for i, label in enumerate(channel_labels):
                val = r_values[i] if i < len(r_values) else 0.0
                lines.append(f"  {label}:  {val:.4f}")
            lines.append("=" * 48)

            ts_file       = self.get_timestamp_formatted()
            sample_key    = result_dict.get('sample_name', f'AgM_Measurement_{ts_file}')
            filename      = f"{sample_key}.txt"
            filepath = self.base_path / filename
            with open(filepath, 'w') as f:
                f.write("\n".join(lines))
            print(f"[INFO] Inference result saved: {filepath}")
            return str(filepath)
        except Exception as e:
            print(f"[ERROR] Failed to save inference result: {e}")
            return None
