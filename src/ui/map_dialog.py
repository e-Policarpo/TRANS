"""
Map Generation Dialog
UI for configuring and generating spatial maps
"""

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, 
    QLineEdit, QPushButton, QListWidget, QListWidgetItem,
    QGroupBox, QGridLayout, QDoubleSpinBox, QMessageBox, 
    QComboBox, QCheckBox
)
from PySide6.QtCore import Qt
import logging
from typing import List, Tuple


logger = logging.getLogger(__name__)


class MapDialog(QDialog):
    """
    Dialog for configuring map generation parameters.
    """
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Generate Spatial Maps")
        self.setModal(True)
        self.setMinimumWidth(500)
        
        self.intervals: List[Tuple[float, float]] = []
        
        self.setup_ui()
    
    def setup_ui(self):
        """Setup the dialog UI."""
        layout = QVBoxLayout(self)
        
        # Integration intervals group
        intervals_group = QGroupBox("Integration Intervals")
        intervals_layout = QVBoxLayout()
        
        # Interval input
        input_layout = QHBoxLayout()
        input_layout.addWidget(QLabel("Interval (V min, V max):"))
        
        self.v_min_spin = QDoubleSpinBox()
        self.v_min_spin.setRange(-10, 10)
        self.v_min_spin.setValue(-1.0)
        self.v_min_spin.setSingleStep(0.1)
        input_layout.addWidget(self.v_min_spin)
        
        self.v_max_spin = QDoubleSpinBox()
        self.v_max_spin.setRange(-10, 10)
        self.v_max_spin.setValue(1.0)
        self.v_max_spin.setSingleStep(0.1)
        input_layout.addWidget(self.v_max_spin)
        
        
        output_group = QGroupBox("Output Options")
        output_layout = QGridLayout()

        output_layout.addWidget(QLabel("Image Format:"), 0, 0)
        self.format_combo = QComboBox()
        self.format_combo.addItems(["TIFF + PNG", "TIFF only", "PNG only", "All formats"])
        output_layout.addWidget(self.format_combo, 0, 1)

        self.save_csv_check = QCheckBox("Save numerical data (CSV)")
        self.save_csv_check.setChecked(True)
        output_layout.addWidget(self.save_csv_check, 1, 0, 1, 2)

        self.generate_topography_check = QCheckBox("Generate topography map")
        self.generate_topography_check.setChecked(True)
        output_layout.addWidget(self.generate_topography_check, 2, 0, 1, 2)

        output_group.setLayout(output_layout)
        layout.addWidget(output_group)
        self.add_interval_btn = QPushButton("Add Interval")
        self.add_interval_btn.clicked.connect(self.add_interval)
        input_layout.addWidget(self.add_interval_btn)
        
        intervals_layout.addLayout(input_layout)
        
        # Interval list
        self.intervals_list = QListWidget()
        intervals_layout.addWidget(self.intervals_list)
        
        # Interval controls
        interval_controls = QHBoxLayout()
        self.remove_interval_btn = QPushButton("Remove Selected")
        self.remove_interval_btn.clicked.connect(self.remove_interval)
        interval_controls.addWidget(self.remove_interval_btn)
        
        self.clear_intervals_btn = QPushButton("Clear All")
        self.clear_intervals_btn.clicked.connect(self.clear_intervals)
        interval_controls.addWidget(self.clear_intervals_btn)
        
        intervals_layout.addLayout(interval_controls)
        intervals_group.setLayout(intervals_layout)
        layout.addWidget(intervals_group)
        
        # Buttons
        button_layout = QHBoxLayout()
        self.generate_btn = QPushButton("Generate Maps")
        self.generate_btn.clicked.connect(self.accept)
        button_layout.addWidget(self.generate_btn)
        
        self.cancel_btn = QPushButton("Cancel")
        self.cancel_btn.clicked.connect(self.reject)
        button_layout.addWidget(self.cancel_btn)
        
        layout.addLayout(button_layout)
    
    def add_interval(self):
        """Add integration interval."""
        v_min = self.v_min_spin.value()
        v_max = self.v_max_spin.value()
        
        if v_min >= v_max:
            QMessageBox.warning(self, "Invalid Interval", "V min must be less than V max")
            return
        
        interval = (v_min, v_max)
        if interval not in self.intervals:
            self.intervals.append(interval)
            item_text = f"[{v_min:.3f}, {v_max:.3f}]"
            self.intervals_list.addItem(item_text)
            logger.info(f"Added interval: {item_text}")
    
    def remove_interval(self):
        """Remove selected interval."""
        current_row = self.intervals_list.currentRow()
        if current_row >= 0:
            self.intervals.pop(current_row)
            self.intervals_list.takeItem(current_row)
    
    def clear_intervals(self):
        """Clear all intervals."""
        self.intervals.clear()
        self.intervals_list.clear()
    
    def get_intervals(self) -> List[Tuple[float, float]]:
        """Get the configured integration intervals."""
        return self.intervals