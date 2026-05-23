"""
DataParser Module - AgM
Extracts and validates numeric data from sensor blocks delimited by $ markers.
Handles sample measurement (/*...*/) protocol.
"""

import re
from typing import List, Optional, Tuple

class DataParser:
    def __init__(self):
        """Initialize parser with regex for number extraction."""
        self.num_regex = re.compile(r'\d+')
    
    def detect_mode(self, line: str) -> Optional[str]:
        """
        Detect if line contains start of sample measurement.
        Returns: 'calibration' (for compatibility, but it's now sample measurement), or None
        """
        if '/*' in line:
            return 'calibration'
        return None
    
    def extract_reading_block(self, line: str) -> Optional[List[str]]:
        """
        Extract numeric values from $,v1,...,v18,$ frame.
        Handles float values (e.g. 5.6721, 0.0000) and trailing comma before $.
        Returns list of 18 numeric strings, or None if invalid.
        """
        if '$,' not in line:
            return None

        # Find opening $, and closing $ (last occurrence)
        start_idx = line.find('$,')
        end_idx   = line.rfind('$')   # last $ in line

        if start_idx == -1 or end_idx <= start_idx:
            return None

        # Content between the two $ markers, strip the leading comma
        content = line[start_idx + 2 : end_idx]

        # Split and keep only parseable numbers (int or float)
        values = []
        for v in content.split(','):
            v = v.strip()
            if not v:
                continue
            try:
                float(v)   # validate it is a number
                values.append(v)
            except ValueError:
                continue

        if len(values) != 18:
            return None

        return values

    def validate(self, vals: List[str]) -> List[float]:
        """
        Convert strings to floats. Allows zero values (valid when lamp is off
        or channel reads nothing). Rejects non-finite values only.
        """
        result = []
        for v in vals:
            try:
                f = float(v)
                if abs(f) != float('inf') and f == f:  # finite, not NaN
                    result.append(f)
            except (ValueError, TypeError):
                continue
        return result
    
    def is_end_marker(self, line: str, mode: str = 'calibration') -> bool:
        """
        Check if line contains end marker for sample measurement.
        mode: unused but kept for compatibility
        """
        if '*/' in line:
            return True
        return False

    # ── Inference Feature (PY-03 / PY-04 / PY-05) ────────────────────

    def parse_inference_frame(self, raw: str) -> Optional[List[float]]:
        """
        Extract and return R[18] float list from a $,v1,...,v18,$ frame.
        Returns list of 18 floats or None if frame is invalid.
        Ref: AgM_SRS_Inference_V0.4.1 §3.3 PY-03
        """
        values = self.extract_reading_block(raw)
        if values is None:
            return None
        validated = self.validate(values)
        if len(validated) != 18:
            return None
        return validated

    def detect_error(self, line: str) -> bool:
        """
        Return True if line is an ERR,CALIB_MISSING frame.
        Ref: AgM_SRS_Inference_V0.4.1 §3.3 PY-04
        """
        return line.strip().startswith("ERR,")

    def detect_warning(self, line: str) -> bool:
        """
        Return True if line is a WARN,LAMP_COLD frame.
        Ref: AgM_SRS_Inference_V0.4.1 §3.3 PY-05
        """
        return line.strip().startswith("WARN,")