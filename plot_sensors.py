# ...existing code...
import serial
import matplotlib.pyplot as plt
from matplotlib.animation import FuncAnimation
import numpy as np
import sys
import time
import math
import threading
import queue

# === CONFIG ===
PORT = '/dev/tty.usbmodem14701'
BAUD = 115200

# === SERIAL ===
try:
    # use blocking reads in reader thread (timeout=None)
    ser = serial.Serial(PORT, BAUD, timeout=None)
    print(f"[INFO] Opened serial port {PORT} at {BAUD} baud.")
except Exception as e:
    print(f"[ERROR] Could not open serial port {PORT}: {e}")
    sys.exit(1)

# === CHANNEL LABELS ===
as7341_labels = [
    "415nm", "445nm", "480nm", "515nm",
    "Clear0", "NIR0", "555nm", "590nm",
    "630nm", "680nm", "Clear", "NIR"
]

as7265x_labels = [
    "410nm", "435nm", "460nm", "485nm", "510nm", "535nm",
    "560nm", "585nm", "610nm", "645nm", "680nm", "705nm",
    "730nm", "760nm", "810nm", "860nm", "900nm", "940nm"
]

# X positions
x7341 = np.arange(len(as7341_labels))
x7265x = np.arange(len(as7265x_labels))

# Assign unique colors for each wavelength/channel
as7341_colors = plt.cm.viridis(np.linspace(0, 1, len(as7341_labels)))
as7265x_colors = plt.cm.plasma(np.linspace(0, 1, len(as7265x_labels)))

# === THREAD COMMUNICATION QUEUES ===
queue_7341 = queue.Queue(maxsize=5)
queue_7265x = queue.Queue(maxsize=5)

def parse_block_string(block, expected_count):
    """Normalize block string (may contain newlines), return list of numeric strings up to expected_count."""
    if block is None:
        return []
    normalized = block.replace("\r", "").replace("\n", ",")
    parts = [p.strip() for p in normalized.split(",") if p.strip() != ""]
    vals = []
    for p in parts:
        try:
            # accept numeric tokens only
            float(p)
            vals.append(p)
        except Exception:
            continue
        if len(vals) >= expected_count:
            break
    return vals

def serial_reader():
    """
    Blocking reader thread:
    - Idle until a line contains '&' or '$'
    - When symbol seen, collect until same symbol seen again
    - Push parsed numeric tokens into respective queue
    - Ignore unrelated lines
    """
    print("[THREAD] Serial reader started, waiting for blocks (& or $)...")
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
        # quick check for symbols
        if '&' in line:
            # if both symbols present in same line handle directly
            if line.count('&') >= 2:
                sidx = line.find('&') + 1
                eidx = line.find('&', sidx)
                block = line[sidx:eidx]
            else:
                # start collecting after the first '&'
                block_parts = []
                after = line[line.find('&')+1:]
                if after:
                    block_parts.append(after)
                # collect until a line containing '&'
                while True:
                    raw2 = ser.readline()
                    if not raw2:
                        continue
                    try:
                        l2 = raw2.decode(errors="ignore").strip()
                    except Exception:
                        continue
                    # if end symbol present in this line
                    if '&' in l2:
                        before = l2[:l2.find('&')]
                        if before:
                            block_parts.append(before)
                        break
                    else:
                        if l2:
                            block_parts.append(l2)
                block = ",".join(block_parts)
            vals = parse_block_string(block, len(as7341_labels))
            # filter positive only (>0)
            vals_pos = [v for v in vals if safe_positive(v)]
            if vals_pos:
                try:
                    queue_7341.put_nowait(vals_pos)
                    print(f"[THREAD] AS7341 block queued ({len(vals_pos)} positive values)")
                except queue.Full:
                    print("[THREAD WARN] AS7341 queue full, dropping block")
            else:
                print("[THREAD] AS7341 block received but no positive values, ignored")
            continue

        if '$' in line:
            if line.count('$') >= 2:
                sidx = line.find('$') + 1
                eidx = line.find('$', sidx)
                block = line[sidx:eidx]
            else:
                block_parts = []
                after = line[line.find('$')+1:]
                if after:
                    block_parts.append(after)
                while True:
                    raw2 = ser.readline()
                    if not raw2:
                        continue
                    try:
                        l2 = raw2.decode(errors="ignore").strip()
                    except Exception:
                        continue
                    if '$' in l2:
                        before = l2[:l2.find('$')]
                        if before:
                            block_parts.append(before)
                        break
                    else:
                        if l2:
                            block_parts.append(l2)
                block = ",".join(block_parts)
            vals = parse_block_string(block, len(as7265x_labels))
            vals_pos = [v for v in vals if safe_positive(v)]
            if vals_pos:
                try:
                    queue_7265x.put_nowait(vals_pos)
                    print(f"[THREAD] AS7265x block queued ({len(vals_pos)} positive values)")
                except queue.Full:
                    print("[THREAD WARN] AS7265x queue full, dropping block")
            else:
                print("[THREAD] AS7265x block received but no positive values, ignored")
            continue

        # ignore unrelated text (do not print)
        # if needed for debug, uncomment:
        # print(f"[THREAD IGNORE] {line}")

def safe_positive(s):
    """Return True if s represents numeric > 0."""
    try:
        f = float(s)
        return math.isfinite(f) and (f > 0)
    except Exception:
        return False

# === PLOT SETUP ===
fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(12, 8))

bars1 = ax1.bar(x7341, [0] * len(x7341), color=as7341_colors)
bars2 = ax2.bar(x7265x, [0] * len(x7265x), color=as7265x_colors)

ax1.set_title("AS7341 Spectrometer")
ax1.set_ylabel("Intensity")
ax1.set_xticks(x7341)
ax1.set_xticklabels(as7341_labels, rotation=45)
ax1.set_ylim(0, 15000)

ax2.set_title("AS7265x Spectrometer")
ax2.set_ylabel("Intensity")
ax2.set_xticks(x7265x)
ax2.set_xticklabels(as7265x_labels, rotation=45)
ax2.set_ylim(0, 17000)
ax2.set_xlabel("Wavelength / Channel")

# Start reader thread
reader_thread = threading.Thread(target=serial_reader, daemon=True)
reader_thread.start()

# Keep last displayed arrays so we show something even when no new block arrives
last_7341 = [0.0] * len(as7341_labels)
last_7265x = [0.0] * len(as7265x_labels)

def update(frame):
    """
    Animation update: non-blocking read from queues populated by serial_reader.
    Only update bars when new positive data arrives. Do not print values <= 0.
    """
    updated = False

    # AS7341
    try:
        vals = queue_7341.get_nowait()
        # Convert to floats, keep only positive; pad/trim to expected length
        arr = [float(v) for v in vals]
        arr = [v if v > 0 else 0 for v in arr]
        arr = (arr + [0.0] * len(as7341_labels))[:len(as7341_labels)]
        last_7341[:] = arr
        print(f"[AS7341] Plotting positive values: {[v for v in arr if v>0]}")
        updated = True
    except queue.Empty:
        arr = last_7341

    # AS7265x
    try:
        vals = queue_7265x.get_nowait()
        arr2 = [float(v) for v in vals]
        arr2 = [v if v > 0 else 0 for v in arr2]
        arr2 = (arr2 + [0.0] * len(as7265x_labels))[:len(as7265x_labels)]
        last_7265x[:] = arr2
        print(f"[AS7265x] Plotting positive values: {[v for v in arr2 if v>0]}")
        updated = True
    except queue.Empty:
        arr2 = last_7265x

    # Update bars only if new data or to keep last shown
    for bar, h in zip(bars1, arr):
        bar.set_height(h)
    for bar, h in zip(bars2, arr2):
        bar.set_height(h)

    # return artists for blitting
    return (*bars1, *bars2)

ani = FuncAnimation(fig, update, interval=200, blit=True)
plt.tight_layout()
plt.show()