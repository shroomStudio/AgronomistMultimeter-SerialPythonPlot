#!/usr/bin/env python3
"""
AgM - Agronomist Multimeter
Sample Measurement System
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
    print("Sample Measurement System")
    print("=" * 60)
    print()
    print("Features:")
    print("  - Takes sample measurements via serial port")
    print("  - Saves readings in: /Users/jorgecortes/Documents/maestriaSistemasEmbebidosInfotec/multimetroAgronomo/ClaudeProject/AgM_Readings_2026/AgM_CalibrationReads")
    print("  - Generates .txt files with raw data")
    print("  - Generates .png files with spectrum plots")
    print()
    print("Usage:")
    print("  1. Send /* marker to start a new sample measurement")
    print("  2. Enter the sample name when prompted")
    print("  3. Send 5 readings (each line with $,value1,...,value18,$)")
    print("  4. Send */ marker to end measurement")
    print("  5. Files will be automatically saved")
    print()
    print("=" * 60)
    print()
    
    # Configuration
    PORT = '/dev/tty.usbmodem14701'
    BAUD = 115200
    
    # Run controller
    controller = AgMController(port=PORT, baud=BAUD)
    controller.run()
