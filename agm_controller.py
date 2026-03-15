"""
AgM Main Controller
Orchestrates the modular system with state machine (IDLE → CALIBRATION/MEASUREMENT → IDLE)
"""

import sys
import time
from enum import Enum
from typing import Optional, List

# Import all modules
from agm.serial_port import SerialPort
from agm.data_parser import DataParser
from agm.measurement import Measurement
from agm.file_manager import FileManager
from agm.calibration_manager import CalibrationManager
from agm.plot_manager import PlotManager

class State(Enum):
    """State machine states."""
    IDLE = "idle"
    CALIBRATION = "calibration"
    MEASUREMENT = "measurement"

class AgMController:
    def __init__(self, port: str = '/dev/tty.usbmodem14701', baud: int = 115200):
        """Initialize AgM controller with all modules."""
        self.port = port
        self.baud = baud
        
        # Initialize modules
        self.serial = SerialPort(port, baud)
        self.parser = DataParser()
        self.measurement = Measurement(buffer_size=5, num_channels=18)
        self.file_manager = FileManager()
        self.calib_manager = CalibrationManager(self.file_manager)
        self.plot_manager = PlotManager()
        
        # State machine
        self.state = State.IDLE
        self.measurement_type = None  # 'calibration' or 'measurement'
        
        # Statistics
        self.blocks_received = 0
        self.blocks_processed = 0
    
    def run(self) -> None:
        """Main event loop."""
        if not self.serial.open():
            sys.exit(1)
        
        print("[INFO] AgM Controller started - Waiting for commands")
        print("[INFO] Send /* for calibration, @ for measurement")
        
        try:
            while True:
                line = self.serial.readline()
                if not line:
                    continue
                
                # Check for mode markers
                mode = self.parser.detect_mode(line)
                if mode:
                    self._start_measurement_cycle(mode, line)
        
        except KeyboardInterrupt:
            print("\n[INFO] Interrupted by user")
        finally:
            self._cleanup()
    
    def _start_measurement_cycle(self, mode: str, start_line: str) -> None:
        """Start a new measurement cycle (calibration or measurement)."""
        if mode == 'calibration':
            print("\n[INFO] === CALIBRATION MODE ===")
            self.measurement_type = 'calibration'
        else:
            print("\n[INFO] === MEASUREMENT MODE ===")
            self.measurement_type = 'measurement'
        
        self._run_measurement_cycle(start_line)
    
    def _run_measurement_cycle(self, start_line: str) -> None:
        """Execute 5-read measurement cycle."""
        self.measurement.clear_buffer()
        read_count = 0
        
        # Try to extract from start line
        values = self.parser.extract_reading_block(start_line)
        if values:
            self._process_reading(values)
            read_count += 1
            print(f"[INFO] Read {read_count}/5 captured")
        
        # Collect remaining reads until end marker
        while read_count < 5:
            line = self.serial.readline()
            if not line:
                continue
            
            # Check for end marker
            if self.parser.is_end_marker(line, self.measurement_type):
                print(f"[INFO] End marker received. Total reads: {read_count}")
                break
            
            # Try to extract reading block
            values = self.parser.extract_reading_block(line)
            if values:
                self._process_reading(values)
                read_count += 1
                print(f"[INFO] Read {read_count}/5 captured")
        
        # Finalize measurement
        if read_count > 0:
            avg_values = self.measurement.compute_average()
            self._finalize_measurement(avg_values)
        else:
            print("[ERROR] No valid readings captured")
        
        self.state = State.IDLE
    
    def _process_reading(self, values: List[str]) -> None:
        """Parse and validate a single reading."""
        try:
            validated = self.parser.validate(values)
            
            if validated and len(validated) == 18:
                self.blocks_received += 1
                self.measurement.add_reading(validated)
                self.blocks_processed += 1
            else:
                print(f"[WARN] Invalid reading: got {len(validated)} values, expected 18")
        except Exception as e:
            print(f"[ERROR] Failed to process reading: {e}")
    
    def _finalize_measurement(self, avg_values: List[float]) -> None:
        """Save and plot the averaged measurement."""
        if not avg_values:
            print("[ERROR] No valid measurements")
            return
        
        if self.measurement_type == 'calibration':
            self._handle_calibration(avg_values)
        else:
            self._handle_measurement(avg_values)
    
    def _handle_calibration(self, avg_values: List[float]) -> None:
        """Process and save calibration reference."""
        print("\n[INFO] Processing calibration data...")
        
        # Save calibration
        calib_path = self.calib_manager.save_calibration(avg_values)
        
        # Store in measurement object
        self.measurement.set_white_reference(avg_values)
        
        # Plot calibration
        self.plot_manager.plot_spectrum(avg_values, "AS7265x Calibration Reference")
        self.plot_manager.show()
        self.plot_manager.close()
        
        print("[INFO] Calibration complete")
    
    def _handle_measurement(self, avg_values: List[float]) -> None:
        """Process, normalize, and save measurement."""
        print("\n[INFO] Processing measurement data...")
        
        # Load calibration
        calib_data = self.calib_manager.load_latest_calibration()
        if not calib_data:
            print("[ERROR] No calibration found - please run calibration first")
            return
        
        self.measurement.set_white_reference(calib_data)
        
        # Normalize
        normalized = self.measurement.normalize(avg_values)
        
        # Format and save measurement
        channel_labels = [
            "410nm", "435nm", "460nm", "485nm", "510nm", "535nm",
            "560nm", "585nm", "610nm", "645nm", "680nm", "705nm",
            "730nm", "760nm", "810nm", "860nm", "900nm", "940nm"
        ]
        
        lines = ["SOIL MEASUREMENT DATA", "=" * 50, ""]
        for label, raw, norm in zip(channel_labels, avg_values, normalized):
            lines.append(f"{label}: Raw={raw:.2f}, Normalized={norm:.2f}%")
        
        lines.append("")
        lines.append("=" * 50)
        lines.append(f"Max raw intensity: {max(avg_values):.2f}")
        lines.append("Normalization applied using latest calibration")
        
        data = "\n".join(lines)
        self.file_manager.write_txt("AgM_Measurements", data)
        
        # Plot
        self.plot_manager.plot_spectrum(normalized, "AS7265x Measurement (Normalized)")
        self.plot_manager.update_y_axis(normalized)
        
        # Save plot as PNG
        plot_path = self.file_manager.base_path / f"{self.file_manager.get_filename_timestamp('AgM_PlotMeasurements')}.png"
        self.plot_manager.save_figure(str(plot_path))
        
        self.plot_manager.show()
        self.plot_manager.close()
        
        print("[INFO] Measurement complete")
    
    def _cleanup(self) -> None:
        """Cleanup before exit."""
        self.serial.close()
        print("\n" + "=" * 60)
        print("FINAL STATISTICS")
        print("=" * 60)
        print(f"Blocks Received:  {self.blocks_received}")
        print(f"Blocks Processed: {self.blocks_processed}")
        print("=" * 60)

if __name__ == "__main__":
    controller = AgMController()
    controller.run()