"""
DataParser Module - AgM
Extracts and validates numeric data from sensor blocks delimited by $ markers.
Handles calibration (/*...*/) and measurement (@...@/) protocols.
"""

import re
from typing import List, Optional, Tuple

class DataParser:
    def __init__(self):
        """Initialize parser with regex for number extraction."""
        self.num_regex = re.compile(r'\d+')
    
    def detect_mode(self, line: str) -> Optional[str]:
        """
        Detect if line contains start of calibration or measurement.
        Returns: 'calibration', 'measurement', or None
        """
        if '/*' in line:
            return 'calibration'
        elif '@' in line and '@/' not in line:
            return 'measurement'
        return None
    
    def extract_reading_block(self, line: str) -> Optional[List[str]]:
        """
        Extract numeric values from a line containing $,value1,value2,...,value18,$.
        Returns list of 18 numeric strings, or None if invalid.
        """
        # Look for pattern: $,numbers,$
        if '$,' not in line or ',$' not in line:
            return None
        
        # Extract content between $, and ,$
        start_idx = line.find('$,')
        end_idx = line.find(',$', start_idx)
        
        if start_idx == -1 or end_idx == -1:
            return None
        
        # Extract the numeric part
        content = line[start_idx + 2:end_idx]
        
        # Split by comma and extract numbers
        values = [v.strip() for v in content.split(',')]
        values = [v for v in values if v.isdigit()]
        
        # Must have exactly 18 values
        if len(values) != 18:
            return None
        
        return values
    
    def validate(self, vals: List[str]) -> List[float]:
        """Convert strings to floats, return only positive finite values."""
        result = []
        for v in vals:
            try:
                f = float(v)
                if f > 0 and abs(f) != float('inf'):
                    result.append(f)
            except (ValueError, TypeError):
                continue
        return result
    
    def is_end_marker(self, line: str, mode: str) -> bool:
        """
        Check if line contains end marker for current mode.
        mode: 'calibration' or 'measurement'
        """
        if mode == 'calibration' and '*/' in line:
            return True
        elif mode == 'measurement' and '@/' in line:
            return True
        return False