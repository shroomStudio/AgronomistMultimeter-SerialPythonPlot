"""
Measurement Module - AgM
Buffers 5 readings and computes averages with optional normalization.
"""

import numpy as np
from collections import deque
from typing import List, Optional

class Measurement:
    def __init__(self, buffer_size: int = 5, num_channels: int = 18):
        """Initialize measurement buffer."""
        self.buffer_size = buffer_size
        self.num_channels = num_channels
        self.buffer = deque(maxlen=buffer_size)
        self.white_reference = None
    
    def add_reading(self, values: List[float]) -> Optional[List[float]]:
        """
        Add a reading to buffer. Returns averaged values when buffer is full.
        """
        # Pad/trim to expected channel count
        padded = (values + [0.0] * self.num_channels)[:self.num_channels]
        self.buffer.append(padded)
        
        if len(self.buffer) == self.buffer_size:
            return self.compute_average()
        return None
    
    def compute_average(self) -> List[float]:
        """Calculate arithmetic mean across buffered readings."""
        if not self.buffer:
            return [0.0] * self.num_channels
        
        arr = np.array(list(self.buffer))
        avg = np.mean(arr, axis=0)
        return avg.tolist()
    
    def set_white_reference(self, white_ref: List[float]) -> None:
        """Store white reference for normalization."""
        self.white_reference = white_ref
    
    def normalize(self, measurement: List[float]) -> List[float]:
        """
        Normalize measurement by white reference.
        R(λᵢ) = I_avg(i) / I_white(i) × 100%
        """
        if not self.white_reference:
            print("[WARN] No white reference set, returning raw values")
            return measurement
        
        normalized = []
        for i, val in enumerate(measurement):
            if i < len(self.white_reference) and self.white_reference[i] > 0:
                norm_val = (val / self.white_reference[i]) * 100
                normalized.append(norm_val)
            else:
                normalized.append(0.0)
        
        return normalized
    
    def clear_buffer(self) -> None:
        """Clear the buffer for next measurement cycle."""
        self.buffer.clear()
