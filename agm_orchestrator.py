"""
agm_orchestrator.py — AgM Main Orchestrator
Entry point for the Agronomist Multimeter Python host application.
Presents a terminal main menu and orchestrates all AgM modules.

Menu structure:
  1. Calibration Procedure  — informs user calibration is pre-loaded
  2. Measurement Procedure  — triggers Arduino inference via cmd 'M'
  3. General Settings       — placeholder, deferred

Ref: AgM_SRS_Inference_V0.4.1
"""

import sys
import time
from enum import Enum
from typing import Optional, List

from agm.serial_port import SerialPort
from agm.data_parser import DataParser
from agm.measurement import Measurement
from agm.file_manager import FileManager
from agm.calibration_manager import CalibrationManager
from agm.plot_manager import PlotManager
from agm.knn_inference import knn_predict, confidence_label, load_centroids


# ── State machine ─────────────────────────────────────────────────────
class State(Enum):
    IDLE               = "idle"
    SAMPLE_MEASUREMENT = "sample_measurement"
    INFERENCE          = "inference"


# ── UI helpers ────────────────────────────────────────────────────────
DIVIDER = "-" * 31

def _header():
    print()
    print("Agronomist Multimeter.")
    print(DIVIDER)

def _clear_lines(n=1):
    pass  # terminal clarity — keep output readable without clearing screen

def _pause(seconds: float = 2.0):
    time.sleep(seconds)


# ── Orchestrator ──────────────────────────────────────────────────────
class AgMOrchestrator:
    def __init__(self, port: str = '/dev/tty.usbmodem14701', baud: int = 115200):
        """Initialize all AgM modules."""
        self.port = port
        self.baud = baud

        self.serial        = SerialPort(port, baud)
        self.parser        = DataParser()
        self.measurement   = Measurement(buffer_size=5, num_channels=18)
        self.file_manager  = FileManager()
        self.calib_manager = CalibrationManager(self.file_manager)
        self.plot_manager  = PlotManager()

        self.state         = State.IDLE
        self.sample_name   = None
        self.blocks_received  = 0
        self.blocks_processed = 0

    # ── Entry point ───────────────────────────────────────────────────
    def run(self) -> None:
        """Open serial port then show main menu loop."""
        if not self.serial.open():
            sys.exit(1)

        try:
            while True:
                self._main_menu()
        except KeyboardInterrupt:
            print("\n[INFO] Interrupted by user")
        finally:
            self._cleanup()

    # ── Main menu ─────────────────────────────────────────────────────
    def _main_menu(self) -> None:
        _header()
        print("Main Menu")
        print(DIVIDER)
        print()
        print("  1. Calibration Procedure")
        print("  2. Measurement Procedure")
        print("  3. General Settings")
        print()
        choice = input("Option: ").strip()

        if choice == "1":
            self._menu_calibration()
        elif choice == "2":
            self._menu_measurement()
        elif choice == "3":
            self._menu_settings()
        else:
            print("[WARN] Invalid option — please enter 1, 2 or 3.")
            _pause(1.0)

    # ── Option 1: Calibration ─────────────────────────────────────────
    def _menu_calibration(self) -> None:
        _header()
        print("Calibration Procedure")
        print(DIVIDER)
        print()
        print("  The calibration process is already done.")
        print("  Measures are stored in device.")
        print()
        _pause(2.0)
        # returns to main menu automatically

    # ── Option 2: Measurement ─────────────────────────────────────────
    def _menu_measurement(self) -> None:
        _header()
        print("Measurement Procedure")
        print(DIVIDER)
        print()
        print("  Press M to start or 0 to return to main menu.")
        print()
        choice = input("  Start: ").strip().upper()

        if choice == "0":
            return

        if choice == "M":
            self._prompt_sample_name()
            if self.sample_name:
                self.run_inference()
        else:
            print("[WARN] Invalid input — press M to start or 0 to return.")
            _pause(1.0)

    # ── Option 3: Settings ────────────────────────────────────────────
    def _menu_settings(self) -> None:
        _header()
        print("General Settings")
        print(DIVIDER)
        print()
        print("  Implementation to be done.")
        print()
        _pause(1.0)
        # returns to main menu automatically

    # ── Sample name prompt ────────────────────────────────────────────
    def _prompt_sample_name(self) -> None:
        try:
            name = input("  Enter sample name: ").strip()
            if name:
                self.sample_name = name
            else:
                print("[ERROR] Sample name cannot be empty.")
                self.sample_name = None
        except Exception as e:
            print(f"[ERROR] Failed to read sample name: {e}")
            self.sample_name = None

    # ── Inference workflow (PY-02 to PY-09) ──────────────────────────
    def run_inference(self) -> None:
        """
        Full KNN inference workflow.
        Ref: AgM_SRS_Inference_V0.4.1 §3.4
        """
        print()
        print("[INFERENCE] Starting measurement process...")
        self.state = State.INFERENCE

        # Step 1: send trigger command M (PY-02)
        try:
            self.serial.ser.write(b'M')
        except Exception as e:
            print(f"[ERROR] Failed to send cmd M: {e}")
            self.state = State.IDLE
            return

        # Step 2: wait for ACK, ERR, WARN or $...$ frame
        r_values      = None
        timeout_reads = 50

        for _ in range(timeout_reads):
            line = self.serial.readline()
            if not line:
                continue

            if line.startswith("ACK"):
                print(f"[INFERENCE] {line}")
                continue

            # PY-04: ERR — abort
            if self.parser.detect_error(line):
                print(f"[ERROR] Arduino: {line} — calibration missing, aborting.")
                self.state = State.IDLE
                return

            # PY-05: WARN — non-blocking, continue
            if self.parser.detect_warning(line):
                print(f"[WARN] Arduino: {line} — lamp may be cold, continuing.")
                continue

            # Step 3: parse data frame (PY-03)
            r_values = self.parser.parse_inference_frame(line)
            if r_values:
                print(f"[INFERENCE] R[18] frame received ({len(r_values)} channels)")
                break

        if not r_values:
            print("[ERROR] No valid inference frame received.")
            self.state = State.IDLE
            return

        # Step 4: KNN prediction (PY-06)
        prediction             = knn_predict(r_values)
        confidence             = confidence_label(prediction["distance"])
        prediction["confidence"] = confidence
        prediction["r_values"]   = r_values

        print()
        print("=" * 48)
        print("INFERENCE RESULT")
        print("=" * 48)
        print(f"  Matched sample : {prediction['sample']}")
        print(f"  Distance       : {prediction['distance']:.4f}")
        print(f"  Confidence     : {confidence}")
        print("-" * 48)
        print(f"  N (Nitrogen)   : {prediction['N']:<8} ({prediction['N_mg_kg']:.2f} mg/kg)")
        print(f"  P (Phosphorus) : {prediction['P']:<8} ({prediction['P_mg_kg']:.2f} mg/kg)")
        print(f"  K (Potassium)  : {prediction['K']:<8} ({prediction['K_mg_kg']:.2f} mg/kg)")
        print("=" * 48)

        # Step 5: save result file (PY-07 / PY-08)
        result_path = self.file_manager.save_inference_result(prediction)
        if result_path:
            print(f"[INFERENCE] Result saved: {result_path}")

        # Step 6: optional spectrum overlay plot (PY-09)
        centroids = load_centroids()
        centroid  = centroids.get(prediction["sample"], [])
        if centroid:
            self.plot_manager.plot_inference(r_values, centroid, prediction["sample"])
            plot_path = str(
                self.file_manager.base_path /
                f"AgM_Inference_{prediction['sample']}_{self.file_manager.get_timestamp_formatted()}.png"
            )
            self.plot_manager.save_figure(plot_path)
            self.plot_manager.close()
            print(f"[INFERENCE] Plot saved: {plot_path}")

        self.state = State.IDLE
        print("[INFERENCE] Complete — returning to main menu.")
        _pause(2.0)

    # ── Legacy measurement cycle (kept for compatibility) ─────────────
    def _run_measurement_cycle(self, start_line: str) -> None:
        self.measurement.clear_buffer()
        read_count = 0

        values = self.parser.extract_reading_block(start_line)
        if values:
            self._process_reading(values)
            read_count += 1

        while read_count < 5:
            line = self.serial.readline()
            if not line:
                continue
            if self.parser.is_end_marker(line):
                break
            values = self.parser.extract_reading_block(line)
            if values:
                self._process_reading(values)
                read_count += 1

        if read_count > 0:
            avg_values = self.measurement.compute_average()
            self._finalize_measurement(avg_values)
        else:
            print("[ERROR] No valid readings captured")

        self.state = State.IDLE

    def _process_reading(self, values: List[str]) -> None:
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
        if not avg_values:
            print("[ERROR] No valid measurements")
            return
        calib_path   = self.calib_manager.save_calibration(self.sample_name, avg_values)
        self.plot_manager.plot_spectrum(avg_values, f"AS7265x Sample: {self.sample_name}")
        self.plot_manager.update_y_axis(avg_values)
        plot_filepath = (
            self.file_manager.base_path /
            f"AgM_{self.sample_name}_Plot_{self.file_manager.get_timestamp_formatted()}.png"
        )
        self.plot_manager.save_figure(str(plot_filepath))
        self.plot_manager.close()
        print(f"[INFO] Text file: {calib_path}")
        print(f"[INFO] Plot file: {plot_filepath}")

    # ── Cleanup ───────────────────────────────────────────────────────
    def _cleanup(self) -> None:
        self.serial.close()
        print("\n" + "=" * 60)
        print("SESSION STATISTICS")
        print("=" * 60)
        print(f"Blocks Received:  {self.blocks_received}")
        print(f"Blocks Processed: {self.blocks_processed}")
        print("=" * 60)


if __name__ == "__main__":
    orchestrator = AgMOrchestrator()
    orchestrator.run()
