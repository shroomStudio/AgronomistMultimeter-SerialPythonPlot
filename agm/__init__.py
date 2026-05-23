"""
AgM - Agronomist Multimeter
Modular soil spectrophotometry analysis system
"""

from .serial_port import SerialPort
from .data_parser import DataParser
from .measurement import Measurement
from .file_manager import FileManager
from .calibration_manager import CalibrationManager
from .plot_manager import PlotManager
from .knn_inference import knn_predict, confidence_label, load_centroids, load_fira_labels

__version__ = "1.0.0"
__all__ = [
    'SerialPort',
    'DataParser',
    'Measurement',
    'FileManager',
    'CalibrationManager',
    'PlotManager',
    'knn_predict',
    'confidence_label',
    'load_centroids',
    'load_fira_labels',
]
