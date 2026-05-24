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
            print("\n  [INFO] Warm-up interrupted — turning lamp off.")
            try:
                self.serial.ser.write(b'0')
                self.serial.ser.flush()
            except Exception:
                pass
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
        """Send M to Arduino — Arduino controls the confirmation flow."""
        _header("Sensing Process")

        sample_name = _auto_sample_name()
        print(f"  Sample ID: {sample_name}")
        print()
        print("  Initiating measurement — Arduino will guide the process.")
        print()

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
        Arduino owns the flow — Python displays messages and forwards
        user input as single-byte serial commands.

        Arduino protocol:
          Python sends M  ->  Arduino: ACK,M
          Arduino checks warmup:
            - Cold: WARN,LAMP_COLD   -> waits for M/other
            - Warm: READY,PRESS_M    -> waits for M/other
          Python forwards user input to Arduino
          Arduino: ACK,M_CONFIRMED -> MEASURING,1/10 ... -> $,...,$
                   CANCELLED       -> IDLE

        Ref: AgM_SRS_Inference_V0.5 §3.4
        """
        self.state = State.INFERENCE

        # Increase serial timeout for long measurement phase (~60s max)
        original_timeout = self.serial.ser.timeout
        self.serial.ser.timeout = 30.0

        def _lamp_off():
            """Send lamp-off command to Arduino on interrupt."""
            try:
                self.serial.ser.write(b'0')
                self.serial.ser.flush()
            except Exception:
                pass

        try:
            # Send initial trigger cmd M
            self.serial.ser.write(b'M')
            self.serial.ser.flush()

            r_values = None

            while True:
                line = self.serial.readline()
                if not line:
                    continue

                # Filter serial echo
                if line.strip() in ("M", ""):
                    continue

                # ── Progress update ───────────────────────────────────
                if line.startswith("MEASURING,"):
                    print(f"  [INFO] {line}")
                    continue

                # ── ACK ───────────────────────────────────────────────
                if line.startswith("ACK,M_CONFIRMED"):
                    print(f"  [INFO] {line} — measurement started.")
                    # Switch to long timeout for the read phase
                    self.serial.ser.timeout = 30.0
                    continue

                if line.startswith("ACK"):
                    print(f"  [INFO] {line}")
                    continue

                # ── Error ─────────────────────────────────────────────
                if self.parser.detect_error(line):
                    print(f"  [ERROR] Arduino: {line}")
                    _lamp_off()
                    self.state = State.IDLE
                    return

                # ── CANCELLED ─────────────────────────────────────────
                if line.startswith("CANCELLED"):
                    print()
                    print("  [INFO] Measurement cancelled — returning to menu.")
                    self.state = State.IDLE
                    return

                # ── WARN: lamp cold ───────────────────────────────────
                if self.parser.detect_warning(line):
                    print(f"  [WARN] Arduino: {line} — lamp may be cold.")
                    print()
                    time.sleep(1)
                    print("  Press M to continue measurement or 0 to cancel.")
                    print()
                    user = input("  [user input]: ").strip().upper()
                    cmd  = b'M' if user == "M" else b'0'
                    self.serial.ser.write(cmd)
                    self.serial.ser.flush()
                    continue

                # ── READY: lamp warm ──────────────────────────────────
                if line.startswith("READY,PRESS_M"):
                    print()
                    print("  AgM ready to take reads.")
                    print("  Press M to start or 0 to cancel.")
                    print()
                    user = input("  [user input]: ").strip().upper()
                    cmd  = b'M' if user == "M" else b'0'
                    self.serial.ser.write(cmd)
                    self.serial.ser.flush()
                    continue

                # ── Data frame ────────────────────────────────────────
                r_values = self.parser.parse_inference_frame(line)
                if r_values:
                    print(f"  [INFO] R[18] frame received ({len(r_values)} channels)")
                    break

                # ── Any other line ────────────────────────────────────
                print(f"  [Arduino] {line}")

        except KeyboardInterrupt:
            print()
            print("  [INFO] Measurement interrupted — turning lamp off.")
            _lamp_off()
            self.state = State.IDLE
            return
        finally:
            # Always restore original serial timeout
            self.serial.ser.timeout = original_timeout

        if not r_values:
            print("  [ERROR] No valid inference frame received.")
            _lamp_off()
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
