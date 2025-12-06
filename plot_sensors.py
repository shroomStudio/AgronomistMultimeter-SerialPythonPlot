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

# === CONFIG ===
PORT = '/dev/tty.usbmodem14701'
BAUD = 115200

# === SERIAL ===
try:
    ser = serial.Serial(PORT, BAUD, timeout=None)  # blocking reads in thread
    print(f"[INFO] Opened serial port {PORT} at {BAUD} baud.")
except Exception as e:
    print(f"[ERROR] Could not open serial port {PORT}: {e}")
    sys.exit(1)

# === AS7265x CHANNEL LABELS (enum order) ===
as7265x_labels = [
    "410nm", "435nm", "460nm", "485nm", "510nm", "535nm",
    "560nm", "585nm", "610nm", "645nm", "680nm", "705nm",
    "730nm", "760nm", "810nm", "860nm", "900nm", "940nm"
]

# X positions
x7265x = np.arange(len(as7265x_labels))

# Color per wavelength (spectral colormap)
as7265x_colors = plt.cm.nipy_spectral(np.linspace(0, 1, len(as7265x_labels)))

# === THREAD COMMUNICATION QUEUE ===
queue_7265x = queue.Queue(maxsize=5)

# regex to extract integers/floats
_num_re = re.compile(r'[-+]?\d+(?:\.\d+)?')

def parse_block_numbers(block, expected_count):
    """Extract numeric tokens from block, preserve order, return up to expected_count as strings."""
    if not block:
        return []
    nums = _num_re.findall(block)
    return nums[:expected_count]

def drain_queue(q):
    """Remove all items from queue q (non-blocking)."""
    try:
        while True:
            q.get_nowait()
    except queue.Empty:
        return

def serial_reader():
    """
    Blocking reader thread:
    - Idle until a line contains '$'
    - When symbol seen, collect until same symbol seen again
    - Push parsed numeric tokens into queue_7265x
    - Ignore unrelated text
    """
    print("[THREAD] Serial reader started, waiting for $ blocks...")
    while True:
        try:
            raw = ser.readline()
        except Exception as e:
            print(f"[THREAD ERROR] serial read failed: {e}")
            time.sleep(0.5)
            continue
        if not raw:
            continue
        try:
            line = raw.decode(errors="ignore").strip()
        except Exception:
            continue

        if '$' in line:
            # Case: both start and end on same line
            if line.count('$') >= 2:
                sidx = line.find('$') + 1
                eidx = line.find('$', sidx)
                block = line[sidx:eidx]
            else:
                # collect remainder after first $
                parts = []
                after = line[line.find('$')+1:]
                if after:
                    parts.append(after)
                # read until we find a line containing the closing $
                while True:
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
                        break
                    else:
                        if l2:
                            parts.append(l2)
                block = "\n".join(parts)

            # DEBUG: show raw block briefly (comment out to reduce output)
            print(f"[THREAD DEBUG] AS7265x raw block:\n{block}")

            vals = parse_block_numbers(block, len(as7265x_labels))
            # keep only positive numeric values
            vals_pos = []
            for v in vals:
                try:
                    f = float(v)
                    if math.isfinite(f) and f > 0:
                        vals_pos.append(v)
                except Exception:
                    continue

            if vals_pos:
                # keep newest only
                drain_queue(queue_7265x)
                try:
                    queue_7265x.put_nowait(vals_pos)
                    print(f"[THREAD] AS7265x block queued ({len(vals_pos)} positive values)")
                except queue.Full:
                    print("[THREAD WARN] AS7265x queue full, dropping block")
            else:
                print("[THREAD] AS7265x block received but no positive values, ignored")
            continue

        # ignore unrelated text silently

def safe_float_or_zero(s):
    try:
        f = float(s)
        if math.isfinite(f) and f > 0:
            return f
        return 0.0
    except Exception:
        return 0.0

# === PLOT SETUP ===
fig, ax = plt.subplots(1, 1, figsize=(14, 6))

bars = ax.bar(x7265x, [0] * len(x7265x), color=as7265x_colors)
ax.set_title("AS7265x Spectrometer")
ax.set_ylabel("Intensity")
ax.set_xticks(x7265x)
ax.set_xticklabels(as7265x_labels, rotation=45)
ax.set_ylim(0, 250)  # requested Y-axis maximum
ax.set_xlabel("Wavelength / Channel")

# Start reader thread
reader_thread = threading.Thread(target=serial_reader, daemon=True)
reader_thread.start()

# keep last displayed
last_vals = [0.0] * len(as7265x_labels)

def update(frame):
    """
    Animation update: check queue for newest AS7265x block and update bars.
    Script remains idle until thread puts a block into queue.
    """
    try:
        vals = queue_7265x.get_nowait()
    except queue.Empty:
        vals = None

    if vals:
        # Map values to floats, pad/trim to 18 channels
        arr = [safe_float_or_zero(v) for v in vals]
        arr = (arr + [0.0] * len(as7265x_labels))[:len(as7265x_labels)]
        last_vals[:] = arr
        # print only positive values for historic view
        positives = [v for v in arr if v > 0]
        if positives:
            print(f"[AS7265x] Plotting positive values: {positives}")
    else:
        arr = last_vals

    # update bars
    for bar, h in zip(bars, arr):
        bar.set_height(h)

    return bars

ani = FuncAnimation(fig, update, interval=200, blit=True)
plt.tight_layout()
plt.show()