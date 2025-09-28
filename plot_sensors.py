# plot_sensors.py
import serial
import matplotlib.pyplot as plt
from matplotlib.animation import FuncAnimation
import numpy as np
import sys
import time

# === CONFIG ===
PORT = '/dev/tty.usbmodem14701'   # change to your Arduino port
BAUD = 115200

# === SERIAL ===
try:
    ser = serial.Serial(PORT, BAUD, timeout=1)
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
as7263_labels = ["Violet", "Blue", "Green", "Yellow", "Orange", "Red"]

# X positions (just 0..N-1 for plotting, with labels)
x7341 = np.arange(len(as7341_labels))
x7263 = np.arange(len(as7263_labels))

# Assign a unique color for each wavelength/channel
as7341_colors = plt.cm.viridis(np.linspace(0, 1, len(as7341_labels)))
as7263_colors = plt.cm.plasma(np.linspace(0, 1, len(as7263_labels)))

# === PLOT SETUP ===
fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(10, 8))

bars1 = ax1.bar(x7341, [0]*len(x7341), color=as7341_colors)
bars2 = ax2.bar(x7263, [0]*len(x7263), color=as7263_colors)

# Axis formatting
ax1.set_title("AS7341 Spectrometer")
ax1.set_ylabel("Intensity")
ax1.set_xticks(x7341)
ax1.set_xticklabels(as7341_labels, rotation=45)
ax1.set_ylim(0, 5000)

ax2.set_title("AS7263 Spectrometer")
ax2.set_ylabel("Intensity")
ax2.set_xticks(x7263)
ax2.set_xticklabels(as7263_labels, rotation=45)
ax2.set_ylim(0, 5000)
ax2.set_xlabel("Wavelength / Channel")

# === READ SENSOR BLOCK ===
def read_sensor_block(symbol, expected_count):
    """
    Collects lines between a line containing only the start symbol and a line ending with the end symbol.
    Returns a list of strings (numbers as strings).
    """
    buffer = []
    collecting = False
    while True:
        line = ser.readline().decode(errors="ignore").strip()
        if not line:
            continue
        print(f"[SERIAL] {line}")
        # Start collecting after a line with only the symbol (e.g. "&,")
        if not collecting:
            if line.replace(",", "") == symbol:
                collecting = True
            continue
        if collecting:
            # If this is the end line (ends with symbol), remove symbol and finish
            if line.endswith(symbol):
                # Remove the symbol and any trailing comma, then append
                value_part = line[:-len(symbol)]
                if value_part.endswith(","):
                    value_part = value_part[:-1]
                if value_part:
                    buffer.append(value_part)
                break
            else:
                buffer.append(line)
    # Join all collected lines, split by comma, and clean up
    joined = ",".join(buffer)
    values = [v.strip() for v in joined.split(",") if v.strip()]
    return values[:expected_count]

# === UPDATE FUNCTION ===
def update(frame):
    print("\n--- New Frame ---")
    vals_7341 = read_sensor_block("&", len(as7341_labels))
    print(f"[AS7341] Block: {vals_7341}")
    vals_7263 = read_sensor_block("$", len(as7263_labels))
    print(f"[AS7263] Block: {vals_7263}")

    def safe_float(val):
        try:
            f = float(val)
            return f if f > 0 else np.nan
        except Exception:
            return np.nan

    vals_7341_f = [safe_float(v) for v in vals_7341]
    vals_7263_f = [safe_float(v) for v in vals_7263]

    vals_7341_plot = (vals_7341_f + [np.nan]*len(as7341_labels))[:len(as7341_labels)]
    vals_7263_plot = (vals_7263_f + [np.nan]*len(as7263_labels))[:len(as7263_labels)]

    print(f"[AS7341] Plot values: {vals_7341_plot}")
    print(f"[AS7263] Plot values: {vals_7263_plot}")

    # Update bar heights
    for bar, h in zip(bars1, vals_7341_plot):
        bar.set_height(h if not np.isnan(h) else 0)
    for bar, h in zip(bars2, vals_7263_plot):
        bar.set_height(h if not np.isnan(h) else 0)

    return (*bars1, *bars2)

ani = FuncAnimation(fig, update, interval=100, blit=True)  # Faster update, blit for speed
plt.tight_layout()
plt.show()