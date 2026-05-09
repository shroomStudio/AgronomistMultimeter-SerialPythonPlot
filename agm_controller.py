"""
AgM Main Controller
Orchestrates the modular system with state machine for Sample Measurement
(IDLE → SAMPLE_MEASUREMENT → IDLE)
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
    SAMPLE_MEASUREMENT = "sample_measurement"

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
        self.sample_name = None
        
        # Statistics
        self.blocks_received = 0
        self.blocks_processed = 0
    
    def run(self) -> None:
        """Main event loop."""
        if not self.serial.open():
            sys.exit(1)
        
        print("[INFO] AgM Controller started")
        print()
        
        # Ask for sample name before starting
        self.sample_name = self._prompt_sample_name()
        if not self.sample_name:
            print("[ERROR] Sample name required to start. Exiting.")
            self._cleanup()
            sys.exit(1)
        
        print()
        print("[INFO] Send /* to start a sample measurement")
        
        try:
            while True:
                line = self.serial.readline()
                if not line:
                    continue
                
                # Check for sample measurement marker
                mode = self.parser.detect_mode(line)
                if mode and self.state == State.IDLE:
                    self._start_measurement_cycle(line)
        
        except KeyboardInterrupt:
            print("\n[INFO] Interrupted by user")
        finally:
            self._cleanup()
    
    def _start_measurement_cycle(self, start_line: str) -> None:
        """Start measurement cycle after sample name has been set."""
        print("\n[INFO] === SAMPLE MEASUREMENT MODE ===")
        print(f"[INFO] Sample: {self.sample_name}")
        print()
        
        self.state = State.SAMPLE_MEASUREMENT
        self._run_measurement_cycle(start_line)
    
    def _prompt_sample_name(self) -> Optional[str]:
        """Prompt user for sample name."""
        try:
            sample_name = input("\nEnter sample name: ").strip()
            if sample_name:
                return sample_name
            else:
                print("[ERROR] Sample name cannot be empty")
                return None
        except Exception as e:
            print(f"[ERROR] Failed to read sample name: {e}")
            return None
    
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
            if self.parser.is_end_marker(line):
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
        print("[INFO] Returning to IDLE - ready for next measurement")
    
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
        """Save and store the averaged measurement."""
        if not avg_values:
            print("[ERROR] No valid measurements")
            return
        
        print("\n[INFO] Processing sample measurement data...")
        
        # Save measurement data
        calib_path = self.calib_manager.save_calibration(self.sample_name, avg_values)
        
        # Generate and save plot
        self.plot_manager.plot_spectrum(avg_values, f"AS7265x Sample: {self.sample_name}")
        self.plot_manager.update_y_axis(avg_values)
        
        # Save plot as PNG
        plot_filepath = self.file_manager.base_path / f"AgM_{self.sample_name}_Plot_{self.file_manager.get_timestamp_formatted()}.png"
        self.plot_manager.save_figure(str(plot_filepath))
        
        # Close plot without displaying
        self.plot_manager.close()
        
        print("[INFO] Sample measurement complete - files saved")
        print(f"  - Text file: {calib_path}")
        print(f"  - Plot file: {plot_filepath}")
    
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