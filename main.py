#!/usr/bin/env python3
"""
AgM - Agronomist Multimeter
Main entry point for running the soil spectroscopy analysis system
"""

import sys
import os

# Add project root to path
project_root = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, project_root)

from agm_controller import AgMController

if __name__ == "__main__":
    print("=" * 60)
    print("AgM - Agronomist Multimeter")
    print("Soil Spectroscopy Analysis System")
    print("=" * 60)
    print()
    
    # Configuration
    PORT = '/dev/tty.usbmodem14701'
    BAUD = 115200
    
    # Run controller
    controller = AgMController(port=PORT, baud=BAUD)
    controller.run()
