"""
agm_orchestrator.py — AgM Terminal Orchestrator
Entry point for the Agronomist Multimeter Python host application.
All device interaction is via serial console.

Menu structure:
  Main Menu:
    1. Calibration Procedure
    2. Measurement Procedure  ->  Measurement Menu:
                                    1. Warm-up Lamp (cmd L, 10 min countdown)
                                    2. Sensing Process (cmd M, full inference)
                                    3. Return to Main Menu
    3. General Settings
    0. Exit

Ref: AgM_SRS_Inference_V0.5 §3.7
"""

import sys
import time
import threading
from datetime import datetime
from enum import Enum
from typing import Optional, List

from agm.serial_port import SerialPort
from agm.data_parser import DataParser
from agm.measurement import Measurement
from agm.file_manager import FileManager
from agm.calibration_manager import CalibrationManager
from agm.plot_manager import PlotManager
from agm.knn_inference import knn_predict, confidence_label, load_centroids

DIVIDER = "-" * 31
WARMUP_SECONDS = 600  # 10 minutes


class State(Enum):
    IDLE               = "idle"
    SAMPLE_MEASUREMENT = "sample_measurement"
    INFERENCE          = "inference"


# ── Helpers ───────────────────────────────────────────────────────────

def _header(subtitle: str = "Main Menu"):
    print()
    print("Agronomist Multimeter.")
    print(DIVIDER)
    print(subtitle)
    print(DIVIDER)
    print()

def _auto_sample_name() -> str:
    """Generate sample name: AgM_Measurement_DDMMYY_HHMM"""
    return datetime.now().strftime("AgM_Measurement_%d%m%y_%H%M")

def _warmup_countdown(stop_event: threading.Event):
    """Display a live countdown timer for WARMUP_SECONDS. Runs in a thread."""
    start = time.time()
    while not stop_event.is_set():
        elapsed  = int(time.time() - start)
        remaining = WARMUP_SECONDS - elapsed
        if remaining <= 0:
            print("\r  Warm-up complete!                        ")
            break
        mins = remaining // 60
        secs = remaining % 60
        print(f"\r  Warm-up time remaining: {mins:02d}:{secs:02d}  ", end="", flush=True)
        time.sleep(1)


# ── Orchestrator ──────────────────────────────────────────────────────

class AgMOrchestrator:
    def __init__(self, port: str = '/dev/tty.usbmodem14701', baud: int = 115200):
        self.port  = port
        self.baud  = baud

        self.serial        = SerialPort(port, baud)
        self.parser        = DataParser()
        self.measurement   = Measurement(buffer_size=5, num_channels=18)
        self.file_manager  = FileManager()
        self.calib_manager = CalibrationManager(self.file_manager)
        self.plot_manager  = PlotManager()

        self.state            = State.IDLE
        self.blocks_received  = 0
        self.blocks_processed = 0

    # ── Entry point ───────────────────────────────────────────────────

    def run(self) -> None:
        if not self.serial.open():
            sys.exit(1)
        try:
            while True:
                choice = self._main_menu()
                if choice == "1":
                    self._menu_calibration()
                elif choice == "2":
                    self._menu_measurement()
                elif choice == "3":
                    self._menu_settings()
                elif choice == "0":
                    self._exit()
                    break
                else:
                    print("  [WARN] Invalid option.")
                    time.sleep(1)
        except KeyboardInterrupt:
            print("\n  [INFO] Interrupted by user.")
        finally:
            self._cleanup()

    # ── Main menu ─────────────────────────────────────────────────────

    def _main_menu(self) -> str:
        _header("Main Menu")
        print("  1. Calibration Procedure")
        print("  2. Measurement Procedure")
        print("  3. General Settings")
        print("  0. Exit")
        print()
        return input("Option: ").strip()

    # ── Option 1: Calibration ─────────────────────────────────────────

    def _menu_calibration(self) -> None:
        _header("Calibration Procedure")
        print("  The calibration process is already done.")
        print("  Measures are stored in device.")
        print()
        time.sleep(2)

    # ── Option 2: Measurement — submenu ──────────────────────────────

    def _menu_measurement(self) -> None:
        while True:
            _header("Measurement Menu")
            print("  1. Warm-up Lamp")
            print("  2. Sensing Process")
            print("  3. Return to Main Menu")
            print()
            choice = input("Option: ").strip()

            if choice == "1":
                self._warmup_lamp()
            elif choice == "2":
                self._sensing_process()
            elif choice == "3":
                return
            else:
                print("  [WARN] Invalid option.")
                time.sleep(1)

    def _warmup_lamp(self) -> None:
        """Send L to Arduino, show 10-min countdown, then thermal stabilisation notice."""
        _header("Warm-up Lamp")
        print("  Sending lamp ON command to Arduino...")

        try:
            self.serial.ser.write(b'L')
        except Exception as e:
            print(f"  [ERROR] Failed to send cmd L: {e}")
            time.sleep(2)
            return

        # Wait for ACK 'L' from Arduino
        ack_received = False
        for _ in range(20):
            line = self.serial.readline()
            if line and line.strip() == "L":
                ack_received = True
                break

        if not ack_received:
            print("  [WARN] No ACK from Arduino — lamp may still be on.")
        else:
            print("  [INFO] Lamp ON confirmed by Arduino.")

        print()
        print("  10-minute warm-up countdown started.")
        print("  Press Ctrl+C to return to menu before countdown ends.")
        print()

        stop_event = threading.Event()
        timer_thread = threading.Thread(target=_warmup_countdown, args=(stop_event,), daemon=True)
        timer_thread.start()

        try:
            timer_thread.join(timeout=WARMUP_SECONDS + 2)
        except KeyboardInterrupt:
            stop_event.set()
            print("\n  [INFO] Warm-up interrupted — returning to menu.")
            time.sleep(1)
            return

        stop_event.set()
        print()
        print("  ┌─────────────────────────────────────────┐")
        print("  │  Lamp warm-up complete.                 │")
        print("  │  Time for thermal stabilisation.        │")
        print("  │  Press Ctrl+C to return to menu.        │")
        print("  └─────────────────────────────────────────┘")

        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            print("\n  [INFO] Returning to Measurement Menu.")
            time.sleep(0.5)

    def _sensing_process(self) -> None:
        """Confirm with user then send M to Arduino and run full inference."""
        _header("Sensing Process")

        sample_name = _auto_sample_name()
        print(f"  Sample ID: {sample_name}")
        print()
        print("  Press M to start measurement or 0 to return to menu.")
        print()
        choice = input("  [user input]: ").strip().upper()

        if choice == "0":
            return

        if choice != "M":
            print("  [WARN] Invalid input.")
            time.sleep(1)
            return

        print()
        print("  Sending measurement command to Arduino...")
        self.run_inference(sample_name)

    # ── Option 3: Settings ────────────────────────────────────────────

    def _menu_settings(self) -> None:
        _header("General Settings")
        print("  Implementation to be done.")
        print()
        time.sleep(1)

    # ── Option 0: Exit ────────────────────────────────────────────────

    def _exit(self) -> None:
        print()
        print("  Closing serial connection and exiting...")
        time.sleep(0.5)

    # ── Inference workflow (PY-02 to PY-09) ──────────────────────────

    def run_inference(self, sample_name: str) -> None:
        """
        Full KNN inference workflow.
        Ref: AgM_SRS_Inference_V0.5 §3.4

        Flow:
          1. Send cmd M → Arduino responds: ACK,M + [WARN,LAMP_COLD] + $,...,$
          2. Read all serial lines until $...$ frame is found or timeout
          3. On WARN: drain remaining buffer first, then show warning + user prompt
          4. KNN predict → display → save → plot
        """
        self.state = State.INFERENCE

        # Send trigger cmd M
        try:
            self.serial.ser.write(b'M')
            self.serial.ser.flush()
        except Exception as e:
            print(f"  [ERROR] Failed to send cmd M: {e}")
            self.state = State.IDLE
            return

        # ── Phase 1: collect ALL lines Arduino sends (ACK + WARN + $frame$) ──
        # Arduino sends everything in one burst — read with generous timeout
        raw_lines = []
        empties   = 0
        max_empties = 12  # ~12 s total wait at 1 s timeout

        while empties < max_empties:
            line = self.serial.readline()
            if not line:
                empties += 1
                # Stop early if we already have a data frame
                if any(l.startswith("$,") for l in raw_lines):
                    break
                continue
            empties = 0  # reset on any real data
            raw_lines.append(line)
            if line.startswith("$,"):
                break  # data frame received — stop reading

        # ── Phase 2: process collected lines ──────────────────────────
        r_values         = None
        lamp_cold_warned = False

        for line in raw_lines:
            if line.strip() == "M":
                continue  # ignore serial echo

            if line.startswith("ACK"):
                print(f"  [INFO] {line}")
                continue

            if self.parser.detect_error(line):
                print(f"  [ERROR] Arduino: {line} — calibration missing, aborting.")
                self.state = State.IDLE
                return

            if self.parser.detect_warning(line) and not lamp_cold_warned:
                lamp_cold_warned = True
                print(f"  [WARN] Arduino: {line} — lamp may be cold.")
                continue

            parsed = self.parser.parse_inference_frame(line)
            if parsed:
                r_values = parsed
                print(f"  [INFO] R[18] frame received ({len(r_values)} channels)")

        # ── Phase 3: if WARN was received, show confirmation prompt ───
        if lamp_cold_warned:
            print()
            time.sleep(1)
            print("  Continue? Press M to proceed or 0 to return to menu.")
            print()
            user = input("  [user input]: ").strip().upper()
            if user == "0":
                self.state = State.IDLE
                return
            # User confirmed — proceed with data already in r_values

        if not r_values:
            print("  [ERROR] No valid inference frame received.")
            self.state = State.IDLE
            return

        # KNN prediction
        prediction             = knn_predict(r_values)
        confidence             = confidence_label(prediction["distance"])
        prediction["confidence"] = confidence
        prediction["r_values"]   = r_values
        prediction["sample_name"] = sample_name

        print()
        print("  " + "=" * 46)
        print("  INFERENCE RESULT")
        print("  " + "=" * 46)
        print(f"  Sample ID      : {sample_name}")
        print(f"  Matched        : {prediction['sample']}")
        print(f"  Distance       : {prediction['distance']:.4f}")
        print(f"  Confidence     : {confidence}")
        print("  " + "-" * 46)
        print(f"  N (Nitrogen)   : {prediction['N']:<8} ({prediction['N_mg_kg']:.2f} mg/kg)")
        print(f"  P (Phosphorus) : {prediction['P']:<8} ({prediction['P_mg_kg']:.2f} mg/kg)")
        print(f"  K (Potassium)  : {prediction['K']:<8} ({prediction['K_mg_kg']:.2f} mg/kg)")
        print("  " + "=" * 46)

        # Save result file using auto-generated sample name
        result_path = self.file_manager.save_inference_result(prediction)
        if result_path:
            print(f"  [INFO] Result saved: {result_path}")

        # Plot overlay
        centroids = load_centroids()
        centroid  = centroids.get(prediction["sample"], [])
        if centroid:
            self.plot_manager.plot_inference(r_values, centroid, prediction["sample"])
            plot_path = str(
                self.file_manager.base_path /
                f"{sample_name}_Plot_{self.file_manager.get_timestamp_formatted()}.png"
            )
            self.plot_manager.save_figure(plot_path)
            self.plot_manager.close()
            print(f"  [INFO] Plot saved: {plot_path}")

        self.state = State.IDLE
        print()
        print("  [INFO] Measurement complete — returning to menu.")
        time.sleep(2)

    # ── Cleanup ───────────────────────────────────────────────────────

    def _cleanup(self) -> None:
        self.serial.close()
        print()
        print("=" * 40)
        print("SESSION STATISTICS")
        print("=" * 40)
        print(f"Blocks Received:  {self.blocks_received}")
        print(f"Blocks Processed: {self.blocks_processed}")
        print("=" * 40)
        print("Goodbye.")


if __name__ == "__main__":
    orchestrator = AgMOrchestrator()
    orchestrator.run()
