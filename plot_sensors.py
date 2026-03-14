import serial
import matplotlib.pyplot as plt
from matplotlib.animation import FuncAnimation
import numpy as np
import sys
import time
import math
import threading
import queue
import re
from pathlib import Path
from collections import deque
from dataclasses import dataclass
from typing import List, Optional

# === CONFIG ===
PORT = '/dev/tty.usbmodem14701'
BAUD = 115200
QUEUE_MAXSIZE = 5
UPDATE_INTERVAL_MS = 200
Y_AXIS_MAX = 30000
DEBUG_MODE = True

# === AS7265x CHANNEL LABELS (enum order) ===
AS7265X_LABELS = [
    "410nm", "435nm", "460nm", "485nm", "510nm", "535nm",
    "560nm", "585nm", "610nm", "645nm", "680nm", "705nm",
    "730nm", "760nm", "810nm", "860nm", "900nm", "940nm"
]

# X positions and colors
X_POS = np.arange(len(AS7265X_LABELS))
COLORS = plt.cm.nipy_spectral(np.linspace(0, 1, len(AS7265X_LABELS)))

# Regex to extract numbers
NUM_REGEX = re.compile(r'[-+]?\d+(?:\.\d+)?')

# === STATISTICS TRACKING ===
@dataclass
class SerialStats:
    blocks_received: int = 0
    blocks_valid: int = 0
    blocks_invalid: int = 0
    parse_errors: int = 0
    queue_drops: int = 0

serial_stats = SerialStats()

# === THREAD COMMUNICATION ===
queue_7265x = queue.Queue(maxsize=QUEUE_MAXSIZE)
shutdown_event = threading.Event()

# === UTILITY FUNCTIONS ===
def parse_block_numbers(block: str, expected_count: int) -> List[str]:
    """Extract numeric tokens from block, preserve order, return up to expected_count as strings."""
    if not block:
        return []
    nums = NUM_REGEX.findall(block)
    return nums[:expected_count]

def drain_queue(q: queue.Queue) -> None:
    """Remove all items from queue q (non-blocking)."""
    try:
        while True:
            q.get_nowait()
    except queue.Empty:
        pass

def safe_float_or_zero(s: str) -> float:
    """Convert string to float, return 0 if invalid or non-positive."""
    try:
        f = float(s)
        return f if math.isfinite(f) and f > 0 else 0.0
    except (ValueError, TypeError):
        return 0.0

def log_debug(msg: str) -> None:
    """Print debug message if DEBUG_MODE is True."""
    if DEBUG_MODE:
        print(f"[DEBUG] {msg}")

def log_info(msg: str) -> None:
    """Print info message."""
    print(f"[INFO] {msg}")

def log_warn(msg: str) -> None:
    """Print warning message."""
    print(f"[WARN] {msg}")

def log_error(msg: str) -> None:
    """Print error message."""
    print(f"[ERROR] {msg}")

# === SERIAL READER THREAD ===
def serial_reader() -> None:
    """
    Blocking reader thread:
    - Idle until a line contains '$'
    - When symbol seen, collect until same symbol seen again
    - Push parsed numeric tokens into queue_7265x
    - Ignore unrelated text
    """
    log_info("Serial reader started, waiting for $ blocks...")
    
    while not shutdown_event.is_set():
        try:
            raw = ser.readline()
        except Exception as e:
            log_error(f"Serial read failed: {e}")
            time.sleep(0.5)
            continue
        
        if not raw:
            continue
        
        try:
            line = raw.decode(errors="ignore").strip()
        except Exception as e:
            log_debug(f"Decode error: {e}")
            serial_stats.parse_errors += 1
            continue

        if '$' not in line:
            continue  # Skip lines without delimiters

        serial_stats.blocks_received += 1

        # Extract block between $ delimiters
        block = extract_block(line)
        
        if not block:
            serial_stats.blocks_invalid += 1
            continue

        log_debug(f"AS7265x raw block:\n{block}")

        # Parse and validate
        vals = parse_block_numbers(block, len(AS7265X_LABELS))
        vals_pos = [v for v in vals if safe_float_or_zero(v) > 0]

        if vals_pos:
            drain_queue(queue_7265x)
            try:
                queue_7265x.put_nowait(vals_pos)
                serial_stats.blocks_valid += 1
                log_debug(f"AS7265x block queued ({len(vals_pos)} values)")
            except queue.Full:
                log_warn("Queue full, dropping block")
                serial_stats.queue_drops += 1
        else:
            serial_stats.blocks_invalid += 1
            log_debug("AS7265x block received but no positive values")

def extract_block(line: str) -> Optional[str]:
    """
    Extract block content between $ delimiters.
    Handles both single-line and multi-line cases.
    """
    if line.count('$') >= 2:
        # Both delimiters on same line
        sidx = line.find('$') + 1
        eidx = line.find('$', sidx)
        return line[sidx:eidx]
    
    # Collect remainder after first $
    parts = []
    after = line[line.find('$') + 1:]
    if after:
        parts.append(after)
    
    # Read until closing $ found
    max_attempts = 50  # Prevent infinite loops
    attempts = 0
    
    while attempts < max_attempts:
        attempts += 1
        try:
            raw2 = ser.readline()
        except Exception:
            continue
        
        if not raw2:
            continue
        
        try:
            l2 = raw2.decode(errors="ignore").strip()
        except Exception:
            continue
        
        if '$' in l2:
            before = l2[:l2.find('$')]
            if before:
                parts.append(before)
            return "\n".join(parts)
        else:
            if l2:
                parts.append(l2)
    
    log_warn("Timeout waiting for closing $")
    return None

# === INITIALIZATION ===
try:
    ser = serial.Serial(PORT, BAUD, timeout=1)
    log_info(f"Opened serial port {PORT} at {BAUD} baud")
except Exception as e:
    log_error(f"Could not open serial port {PORT}: {e}")
    sys.exit(1)

# === PLOT SETUP ===
fig, ax = plt.subplots(1, 1, figsize=(14, 6))
fig.suptitle("AS7265x Spectrometer Real-Time Monitor", fontsize=14, fontweight='bold')

bars = ax.bar(X_POS, [0] * len(AS7265X_LABELS), color=COLORS, edgecolor='black', linewidth=0.5)
ax.set_ylabel("Intensity", fontsize=11, fontweight='bold')
ax.set_xlabel("Wavelength / Channel", fontsize=11, fontweight='bold')
ax.set_xticks(X_POS)
ax.set_xticklabels(AS7265X_LABELS, rotation=45, ha='right', fontsize=9)
ax.set_ylim(0, Y_AXIS_MAX)
ax.grid(axis='y', alpha=0.3, linestyle='--')

# Keep last displayed values
last_vals = [0.0] * len(AS7265X_LABELS)

# Start reader thread
reader_thread = threading.Thread(target=serial_reader, daemon=True)
reader_thread.start()

# Performance tracking
frame_count = [0]
fps_counter = deque(maxlen=30)

def update(frame: int) -> tuple:
    """
    Animation update: check queue for newest AS7265x block and update bars.
    Script remains idle until thread puts a block into queue.
    """
    frame_count[0] += 1
    start_time = time.perf_counter()
    
    try:
        vals = queue_7265x.get_nowait()
    except queue.Empty:
        vals = None

    if vals:
        # Map values to floats, pad/trim to 18 channels
        arr = [safe_float_or_zero(v) for v in vals]
        arr = (arr + [0.0] * len(AS7265X_LABELS))[:len(AS7265X_LABELS)]
        last_vals[:] = arr
        
        positives = [v for v in arr if v > 0]
        if positives:
            log_debug(f"Plotting {len(positives)} positive values (max={max(positives):.0f})")
    else:
        arr = last_vals

    # Update bars
    for bar, height in zip(bars, arr):
        bar.set_height(height)

    # Track FPS
    elapsed = time.perf_counter() - start_time
    fps_counter.append(elapsed)
    
    # Print stats every 50 frames
    if frame_count[0] % 50 == 0:
        avg_frame_time = np.mean(fps_counter) * 1000  # ms
        log_info(f"Frame {frame_count[0]} | Avg frame time: {avg_frame_time:.2f}ms | "
                f"Blocks RX: {serial_stats.blocks_received} | Valid: {serial_stats.blocks_valid}")

    return tuple(bars)

# Create animation with optimized settings
ani = FuncAnimation(fig, update, interval=UPDATE_INTERVAL_MS, blit=True, cache_frame_data=False)

plt.tight_layout()

try:
    plt.show()
except KeyboardInterrupt:
    log_info("Interrupted by user")
finally:
    # Cleanup
    shutdown_event.set()
    try:
        ser.close()
        log_info("Serial port closed")
    except Exception as e:
        log_error(f"Error closing serial port: {e}")
    
    # Print final stats
    print("\n" + "="*60)
    print("FINAL STATISTICS")
    print("="*60)
    print(f"Blocks Received:  {serial_stats.blocks_received}")
    print(f"Blocks Valid:     {serial_stats.blocks_valid}")
    print(f"Blocks Invalid:   {serial_stats.blocks_invalid}")
    print(f"Parse Errors:     {serial_stats.parse_errors}")
    print(f"Queue Drops:      {serial_stats.queue_drops}")
    print(f"Total Frames:     {frame_count[0]}")
    print("="*60)