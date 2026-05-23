"""
SerialPort Module - AgM
Handles USB serial communication with the spectrometer sensor.
"""

import serial
import time
from typing import Optional

class SerialPort:
    def __init__(self, port: str, baud: int, timeout: float = 1.0):
        """Initialize serial connection."""
        self.port = port
        self.baud = baud
        self.timeout = timeout
        self.ser = None
        
    def open(self) -> bool:
        """Open serial port."""
        try:
            self.ser = serial.Serial(self.port, self.baud, timeout=self.timeout)
            print(f"[INFO] Opened serial port {self.port} at {self.baud} baud")
            return True
        except Exception as e:
            print(f"[ERROR] Could not open serial port {self.port}: {e}")
            return False
    
    def readline(self) -> Optional[str]:
        """Read a line from serial port, return decoded string or None."""
        try:
            raw = self.ser.readline()
            if not raw:
                return None
            return raw.decode(errors="ignore").strip()
        except Exception as e:
            print(f"[ERROR] Serial read failed: {e}")
            return None
    
    def close(self) -> None:
        """Close serial port."""
        try:
            if self.ser and self.ser.is_open:
                self.ser.close()
                print("[INFO] Serial port closed")
        except Exception as e:
            print(f"[ERROR] Error closing serial port: {e}")
