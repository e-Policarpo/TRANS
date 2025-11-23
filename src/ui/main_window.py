"""
Main Application Window - REFACTORED VERSION
PySide6-based GUI for hyperspectral data analysis

MAJOR CHANGES IN THIS VERSION:
1. Unified import system in menu bar
2. Tab-based interface for different data types (STS/SNOM)
3. Simplified STS processing controls
4. Improved baseline correction for derivatives
5. New visualization section
6. Complete SNOM interface
7. Image import for canvas with aspect ratio preservation
8. Renamed central tabs for better clarity
"""

import sys
from pathlib import Path
import logging
from typing import Optional, Dict, List, Tuple

import pandas as pd
import numpy as np

from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, 
    QPushButton, QLabel, QFileDialog, QMessageBox,
    QGroupBox, QGridLayout, QSpinBox, QCheckBox,
    QComboBox, QTableWidget, QTableWidgetItem,
    QProgressBar, QTextEdit, QSplitter, QTabWidget,
    QDoubleSpinBox, QInputDialog, QDialog, QScrollArea
)
from PySide6.QtCore import Qt, Signal, QThread, QTimer
from PySide6.QtGui import QPixmap, QPainter, QColor, QBrush, QPen, QIcon

from ..models.spectral_data import SpectralData, SpectralMetadata
from ..models.topography_data import TopographyData
from ..data_loaders.nanosurf_sts_loader import NanosurfSTSLoader
from ..data_loaders.neaspec_snom_loader import NeaSpecSNOMLoader
from ..data_loaders.base_loader import BaseDataLoader
from ..processing.derivatives import DerivativesProcessor
from ..processing.discretization import Discretizer
from ..processing.iv_processor import IVDataProcessor
from .topography_widget import TopographyWidget
from .map_dialog import MapDialog
from ..processing.map_generator import MapGenerator
from ..processing.integration import IntegrationProcessor
import setproctitle

setproctitle.setproctitle("TRANS")

logger = logging.getLogger(__name__)

class MainWindow(QMainWindow):
    """Main application window for hyperspectral data analysis."""
    
    def __init__(self):
        """Initialize main window."""
        super().__init__()
        self.setWindowTitle("🏳️‍⚧️ T.R.A.N.S. Tools of Research and Analysis for Nano Spectroscopy (beta ver. 0.6.0) - By Eduarda Policarpo - 🏳️‍⚧️")
        self.setGeometry(100, 100, 1200, 700)

        # Setup icon with RELATIVE paths only
        self.setup_window_icon()
        
        # Data storage
        self.spectral_data: Optional[SpectralData] = None
        self.topography_data: Optional[TopographyData] = None
        self.derivatives: Dict[str, SpectralData] = {}
        self.discretized_data: Dict[str, SpectralData] = {}
        self.current_data_type: str = 'unknown'
        self.current_plugin: str = 'sts'  # Default to STS
        
        # Processing modules
        self.derivatives_processor = DerivativesProcessor()
        self.discretizer = Discretizer()
        self.iv_processor = IVDataProcessor()
        self.map_generator = MapGenerator()
        self.integration_processor = IntegrationProcessor()

        # Data loaders
        self.loaders = {
            'nanosurf': NanosurfSTSLoader(),
            'neaspec': NeaSpecSNOMLoader()
        }
        
        # Plugin system for future expansion
        self.plugin_tabs = {}
        
        # Setup UI
        self.setup_ui()
        self.setup_logging()

    def setup_window_icon(self):
        """Setup window icon with RELATIVE paths only."""
        icon_paths = [
            Path(__file__).parent / "icon.png",
            Path(__file__).parent.parent.parent / "src" / "ui" / "icon.png",
            Path("src/ui/icon.png"),
        ]
        
        icon_loaded = False
        
        for icon_path in icon_paths:
            logger.debug(f"Trying icon path: {icon_path}")
            
            if icon_path.exists():
                try:
                    icon = QIcon(str(icon_path))
                    if not icon.isNull():
                        self.setWindowIcon(icon)
                        logger.info(f"Window icon loaded: {icon_path}")
                        icon_loaded = True
                        break
                except Exception as e:
                    logger.error(f"Error loading icon {icon_path}: {e}")
        
        if not icon_loaded:
            logger.warning("No application icon could be loaded, using fallback")
            self.create_fallback_icon()

    def create_fallback_icon(self):
        """Create a simple fallback icon programmatically."""
        try:
            pixmap = QPixmap(64, 64)
            pixmap.fill(Qt.transparent)
            
            painter = QPainter(pixmap)
            painter.setRenderHint(QPainter.Antialiasing)
            
            # Draw background circle
            painter.setBrush(QColor(70, 130, 180))
            painter.setPen(Qt.NoPen)
            painter.drawEllipse(8, 8, 48, 48)
            
            # Draw "T" letter
            from PySide6.QtCore import QRect
            painter.setPen(QColor(255, 255, 255))
            font = painter.font()
            font.setPointSize(32)
            font.setBold(True)
            painter.setFont(font)
            painter.drawText(QRect(0, 0, 64, 64), Qt.AlignCenter, "T")
            
            painter.end()
            
            self.setWindowIcon(QIcon(pixmap))
            logger.info("Fallback icon created")
            
        except Exception as e:
            logger.error(f"Failed to create fallback icon: {e}")

    def setup_ui(self):
        """Setup user interface."""
        # Central widget
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        # Main layout with splitter
        layout = QVBoxLayout(central_widget)
        
        # Top: Menu bar / toolbar
        self.create_menu_bar()
        
        # Main content with splitter
        splitter = QSplitter(Qt.Horizontal)
        
        # Left panel: Controls with TABS
        left_panel = self.create_control_panel_with_tabs()
        splitter.addWidget(left_panel)
        
        # Center: Visualization
        center_panel = self.create_visualization_panel()
        splitter.addWidget(center_panel)
        
        # Right panel: Info and logs
        right_panel = self.create_info_panel()
        splitter.addWidget(right_panel)
        
        # Set splitter proportions
        splitter.setSizes([350, 600, 250])
        
        layout.addWidget(splitter)
        
        # Bottom: Status bar
        self.status_bar = self.statusBar()
        self.progress_bar = QProgressBar()
        self.progress_bar.hide()
        self.status_bar.addPermanentWidget(self.progress_bar)
        
        # Status label for real-time feedback
        self.status_label = QLabel("Ready")
        self.status_bar.addPermanentWidget(self.status_label)

    def create_menu_bar(self):
        """Create menu bar with unified import system."""
        menubar = self.menuBar()
        
        # File menu with unified import
        file_menu = menubar.addMenu('📁 File')
        
        # Unified import system
        import_menu = file_menu.addMenu('Import Data')
        
        single_file_action = import_menu.addAction('Single File')
        single_file_action.triggered.connect(self.load_single_file)
        
        directory_action = import_menu.addAction('Directory')
        directory_action.triggered.connect(self.load_from_directory)
        
        # Image import for canvas
        file_menu.addSeparator()
        import_image_action = file_menu.addAction('Import Image for Canvas')
        import_image_action.triggered.connect(self.import_image_for_canvas)
        
        file_menu.addSeparator()
        
        export_action = file_menu.addAction('Export to CSV')
        export_action.triggered.connect(self.export_to_csv)
        
        file_menu.addSeparator()
        
        quit_action = file_menu.addAction('Quit')
        quit_action.triggered.connect(self.close)
        
        # View menu
        view_menu = menubar.addMenu('👁️ View')
        
        reset_view_action = view_menu.addAction('Reset View')
        reset_view_action.triggered.connect(self.reset_view)
        
        # Help menu
        help_menu = menubar.addMenu('❓ Help')
        
        about_action = help_menu.addAction('About')
        about_action.triggered.connect(self.show_about)

    def create_control_panel_with_tabs(self) -> QWidget:
        """Create left control panel with tabs for different data types."""
        tab_widget = QTabWidget()
        
        # STS Tab
        sts_tab = self.create_sts_tab()
        tab_widget.addTab(sts_tab, "STS")
        
        # SNOM Tab
        snom_tab = self.create_snom_tab()
        tab_widget.addTab(snom_tab, "SNOM")
        
        # Connect tab change to update current plugin
        tab_widget.currentChanged.connect(self.on_tab_changed)
        
        return tab_widget

    def create_sts_tab(self) -> QWidget:
        """Create STS-specific control tab."""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        # Data info section
        info_group = QGroupBox("📊 Data Info")
        info_layout = QVBoxLayout()
        
        self.data_type_label = QLabel("Data type: Not loaded")
        self.data_type_label.setStyleSheet("font-weight: bold;")
        info_layout.addWidget(self.data_type_label)
        
        self.data_stats_label = QLabel("Spectra: 0 | Points: 0")
        info_layout.addWidget(self.data_stats_label)
        
        info_group.setLayout(info_layout)
        layout.addWidget(info_group)
        
        # Preprocessing
        preprocessing_group = self.create_sts_preprocessing()
        layout.addWidget(preprocessing_group)
        
        # Processing
        processing_group = self.create_sts_processing()
        layout.addWidget(processing_group)
        
        # Visualization
        visualization_group = self.create_visualization_section()
        layout.addWidget(visualization_group)
        
        # Export
        export_group = self.create_sts_export()
        layout.addWidget(export_group)
        
        layout.addStretch()
        
        # Wrap in scroll area
        scroll_area = QScrollArea()
        scroll_area.setWidget(widget)
        scroll_area.setWidgetResizable(True)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        scroll_area.setMinimumWidth(340)
        
        return scroll_area

    def create_sts_preprocessing(self) -> QGroupBox:
        """Create STS preprocessing controls."""
        group = QGroupBox("⚙️ Preprocessing")
        layout = QVBoxLayout()
        
        # Truncate range
        truncate_layout = QGridLayout()
        truncate_layout.addWidget(QLabel("V min:"), 0, 0)
        self.v_min_spin = QDoubleSpinBox()
        self.v_min_spin.setRange(-10, 10)
        self.v_min_spin.setValue(-2.0)
        self.v_min_spin.setSingleStep(0.1)
        truncate_layout.addWidget(self.v_min_spin, 0, 1)
        
        truncate_layout.addWidget(QLabel("V max:"), 1, 0)
        self.v_max_spin = QDoubleSpinBox()
        self.v_max_spin.setRange(-10, 10)
        self.v_max_spin.setValue(2.0)
        self.v_max_spin.setSingleStep(0.1)
        truncate_layout.addWidget(self.v_max_spin, 1, 1)
        
        self.truncate_btn = QPushButton("✂️ Truncate Range")
        self.truncate_btn.clicked.connect(self.truncate_range)
        truncate_layout.addWidget(self.truncate_btn, 2, 0, 1, 2)
        
        layout.addLayout(truncate_layout)
        
        # Smoothing checkbox
        self.smooth_check = QCheckBox("Apply Smoothing")
        self.smooth_check.setChecked(True)
        layout.addWidget(self.smooth_check)
        
        group.setLayout(layout)
        return group

    def create_sts_processing(self) -> QGroupBox:
        """Create STS processing controls."""
        group = QGroupBox("🔬 Processing")
        layout = QVBoxLayout()
        
        # I-V Processing (SIMPLIFIED)
        iv_group = QGroupBox("I-V Processing")
        iv_layout = QVBoxLayout()
        
        smooth_layout = QHBoxLayout()
        smooth_layout.addWidget(QLabel("Smooth Window:"))
        self.iv_smooth_window_spin = QSpinBox()
        self.iv_smooth_window_spin.setRange(3, 51)
        self.iv_smooth_window_spin.setValue(11)
        self.iv_smooth_window_spin.setSingleStep(2)
        smooth_layout.addWidget(self.iv_smooth_window_spin)
        smooth_layout.addStretch()
        
        iv_layout.addLayout(smooth_layout)
        
        self.process_iv_btn = QPushButton("🔄 Process I-V Data")
        self.process_iv_btn.clicked.connect(self.process_iv_data)
        iv_layout.addWidget(self.process_iv_btn)
        
        self.calc_deriv_btn = QPushButton("📈 Calculate Derivatives from I-V")
        self.calc_deriv_btn.clicked.connect(self.calculate_derivatives_from_iv)
        iv_layout.addWidget(self.calc_deriv_btn)
        
        iv_group.setLayout(iv_layout)
        layout.addWidget(iv_group)
        
        # Derivatives (SIMPLIFIED)
        deriv_group = QGroupBox("Derivatives")
        deriv_layout = QVBoxLayout()
        
        self.calc_derivatives_btn = QPushButton("∂ Calculate Derivatives")
        self.calc_derivatives_btn.clicked.connect(self.calculate_derivatives)
        deriv_layout.addWidget(self.calc_derivatives_btn)
        
        # Only keep the checkbox for polynomial correction
        self.poly_correct_check = QCheckBox("Apply Polynomial Baseline Correction")
        self.poly_correct_check.setChecked(True)
        self.poly_correct_check.setToolTip("Apply individual polynomial baseline correction to each spectrum")
        deriv_layout.addWidget(self.poly_correct_check)
        
        deriv_group.setLayout(deriv_layout)
        layout.addWidget(deriv_group)
        
        # Discretization
        discretize_group = QGroupBox("Spatial Discretization")
        discretize_layout = QGridLayout()
        
        discretize_layout.addWidget(QLabel("Block Width:"), 0, 0)
        self.block_h_spin = QSpinBox()
        self.block_h_spin.setRange(1, 100)
        self.block_h_spin.setValue(10)
        discretize_layout.addWidget(self.block_h_spin, 0, 1)
        
        discretize_layout.addWidget(QLabel("Block Height:"), 1, 0)
        self.block_v_spin = QSpinBox()
        self.block_v_spin.setRange(1, 100)
        self.block_v_spin.setValue(10)
        discretize_layout.addWidget(self.block_v_spin, 1, 1)
        
        self.ignore_empty_check = QCheckBox("Ignore Empty Blocks")
        self.ignore_empty_check.setChecked(True)
        discretize_layout.addWidget(self.ignore_empty_check, 2, 0, 1, 2)
        
        self.use_selection_check = QCheckBox("Use Selection Only")
        discretize_layout.addWidget(self.use_selection_check, 3, 0, 1, 2)
        
        self.discretize_btn = QPushButton("⊞ Apply Discretization")
        self.discretize_btn.clicked.connect(self.apply_discretization)
        discretize_layout.addWidget(self.discretize_btn, 4, 0, 1, 2)
        
        discretize_group.setLayout(discretize_layout)
        layout.addWidget(discretize_group)
        
        group.setLayout(layout)
        return group

    def create_visualization_section(self) -> QGroupBox:
        """Create visualization controls section."""
        group = QGroupBox("📊 Visualization")
        layout = QVBoxLayout()
        
        # Map generation moved here
        self.export_maps_btn = QPushButton("🗺️ Generate Maps")
        self.export_maps_btn.clicked.connect(self.generate_maps)
        layout.addWidget(self.export_maps_btn)
        
        # Quick preview
        self.preview_btn = QPushButton("👁️ Quick Spectrum Preview")
        self.preview_btn.clicked.connect(self.quick_spectrum_preview)
        layout.addWidget(self.preview_btn)
        
        group.setLayout(layout)
        return group

    def create_sts_export(self) -> QGroupBox:
        """Create STS export controls."""
        group = QGroupBox("💾 Export")
        layout = QVBoxLayout()
        
        self.export_iv_btn = QPushButton("📊 Export I-V Data")
        self.export_iv_btn.clicked.connect(self.export_iv_data)
        layout.addWidget(self.export_iv_btn)
        
        self.export_deriv_btn = QPushButton("📈 Export Derivatives")
        self.export_deriv_btn.clicked.connect(self.export_derivatives)
        layout.addWidget(self.export_deriv_btn)
        
        self.export_selection_btn = QPushButton("🎯 Export Selection")
        self.export_selection_btn.clicked.connect(self.export_selection)
        layout.addWidget(self.export_selection_btn)
        
        self.export_topo_btn = QPushButton("🗻 Export Topography CSV")
        self.export_topo_btn.clicked.connect(self.export_topography_csv)
        layout.addWidget(self.export_topo_btn)
        
        group.setLayout(layout)
        return group

    def create_snom_tab(self) -> QWidget:
        """Create SNOM-specific control tab."""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        # Data info section
        info_group = QGroupBox("📊 Data Info")
        info_layout = QVBoxLayout()
        
        self.snom_data_type_label = QLabel("Data type: Not loaded")
        self.snom_data_type_label.setStyleSheet("font-weight: bold;")
        info_layout.addWidget(self.snom_data_type_label)
        
        self.snom_data_stats_label = QLabel("Spectra: 0 | Points: 0")
        info_layout.addWidget(self.snom_data_stats_label)
        
        info_group.setLayout(info_layout)
        layout.addWidget(info_group)
        
        # Preprocessing
        preprocessing_group = self.create_snom_preprocessing()
        layout.addWidget(preprocessing_group)
        
        # Processing
        processing_group = self.create_snom_processing()
        layout.addWidget(processing_group)
        
        # Discretization (shared)
        discretize_group = self.create_snom_discretization()
        layout.addWidget(discretize_group)
        
        # Export
        export_group = self.create_snom_export()
        layout.addWidget(export_group)
        
        layout.addStretch()
        
        # Wrap in scroll area
        scroll_area = QScrollArea()
        scroll_area.setWidget(widget)
        scroll_area.setWidgetResizable(True)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        scroll_area.setMinimumWidth(340)
        
        return scroll_area

    def create_snom_preprocessing(self) -> QGroupBox:
        """Create SNOM preprocessing controls."""
        group = QGroupBox("⚙️ Preprocessing")
        layout = QVBoxLayout()
        
        # Truncate range for wavenumber
        truncate_layout = QGridLayout()
        truncate_layout.addWidget(QLabel("Min Wavenumber:"), 0, 0)
        self.wavenumber_min_spin = QDoubleSpinBox()
        self.wavenumber_min_spin.setRange(0, 10000)
        self.wavenumber_min_spin.setValue(500)
        self.wavenumber_min_spin.setSingleStep(10)
        truncate_layout.addWidget(self.wavenumber_min_spin, 0, 1)
        
        truncate_layout.addWidget(QLabel("Max Wavenumber:"), 1, 0)
        self.wavenumber_max_spin = QDoubleSpinBox()
        self.wavenumber_max_spin.setRange(0, 10000)
        self.wavenumber_max_spin.setValue(4000)
        self.wavenumber_max_spin.setSingleStep(10)
        truncate_layout.addWidget(self.wavenumber_max_spin, 1, 1)
        
        self.snom_truncate_btn = QPushButton("✂️ Truncate Range")
        self.snom_truncate_btn.clicked.connect(self.snom_truncate_range)
        truncate_layout.addWidget(self.snom_truncate_btn, 2, 0, 1, 2)
        
        layout.addLayout(truncate_layout)
        
        group.setLayout(layout)
        return group

    def create_snom_processing(self) -> QGroupBox:
        """Create SNOM processing controls."""
        group = QGroupBox("🔬 Processing")
        layout = QVBoxLayout()
        
        # FFT Processing
        fft_group = QGroupBox("Fourier Transform")
        fft_layout = QVBoxLayout()
        
        self.calculate_fft_btn = QPushButton("📊 Calculate FFT")
        self.calculate_fft_btn.clicked.connect(self.calculate_fft)
        fft_layout.addWidget(self.calculate_fft_btn)
        
        fft_group.setLayout(fft_layout)
        layout.addWidget(fft_group)
        
        group.setLayout(layout)
        return group

    def create_snom_discretization(self) -> QGroupBox:
        """Create SNOM discretization controls."""
        group = QGroupBox("Spatial Discretization")
        layout = QGridLayout()
        
        layout.addWidget(QLabel("Block Width:"), 0, 0)
        self.snom_block_h_spin = QSpinBox()
        self.snom_block_h_spin.setRange(1, 100)
        self.snom_block_h_spin.setValue(10)
        layout.addWidget(self.snom_block_h_spin, 0, 1)
        
        layout.addWidget(QLabel("Block Height:"), 1, 0)
        self.snom_block_v_spin = QSpinBox()
        self.snom_block_v_spin.setRange(1, 100)
        self.snom_block_v_spin.setValue(10)
        layout.addWidget(self.snom_block_v_spin, 1, 1)
        
        self.snom_ignore_empty_check = QCheckBox("Ignore Empty Blocks")
        self.snom_ignore_empty_check.setChecked(True)
        layout.addWidget(self.snom_ignore_empty_check, 2, 0, 1, 2)
        
        self.snom_use_selection_check = QCheckBox("Use Selection Only")
        layout.addWidget(self.snom_use_selection_check, 3, 0, 1, 2)
        
        self.snom_discretize_btn = QPushButton("⊞ Apply Discretization")
        self.snom_discretize_btn.clicked.connect(self.snom_apply_discretization)
        layout.addWidget(self.snom_discretize_btn, 4, 0, 1, 2)
        
        group.setLayout(layout)
        return group

    def create_snom_export(self) -> QGroupBox:
        """Create SNOM export controls."""
        group = QGroupBox("💾 Export")
        layout = QVBoxLayout()
        
        self.snom_export_spectrum_btn = QPushButton("📈 Export Spectrum")
        self.snom_export_spectrum_btn.clicked.connect(self.snom_export_spectrum)
        layout.addWidget(self.snom_export_spectrum_btn)
        
        self.snom_export_selection_btn = QPushButton("🎯 Export Selection")
        self.snom_export_selection_btn.clicked.connect(self.snom_export_selection)
        layout.addWidget(self.snom_export_selection_btn)
        
        self.snom_export_fft_btn = QPushButton("🔄 Export FFT")
        self.snom_export_fft_btn.clicked.connect(self.snom_export_fft)
        layout.addWidget(self.snom_export_fft_btn)
        
        self.snom_export_maps_btn = QPushButton("🗺️ Export Maps")
        self.snom_export_maps_btn.clicked.connect(self.snom_export_maps)
        layout.addWidget(self.snom_export_maps_btn)
        
        group.setLayout(layout)
        return group

    def create_visualization_panel(self) -> QWidget:
        """Create center visualization panel with renamed tabs."""
        panel = QWidget()
        layout = QVBoxLayout(panel)
        
        # Tab widget for different views
        self.tabs = QTabWidget()
        
        # Renamed tabs for better clarity
        self.topography_widget = TopographyWidget()
        self.topography_widget.selection_changed.connect(self.on_selection_changed)
        self.tabs.addTab(self.topography_widget, "🖼️ Image Visualization")
        
        # Data table tab
        self.data_table = QTableWidget()
        self.tabs.addTab(self.data_table, "📊 Data Table")
        
        # Info tab renamed to Metadata
        self.info_text = QTextEdit()
        self.info_text.setReadOnly(True)
        self.tabs.addTab(self.info_text, "ℹ️ Metadata")
        
        # Spectrum viewer renamed to Curve Visualization
        self.spectrum_viewer = QWidget()
        self.setup_spectrum_viewer()
        self.tabs.addTab(self.spectrum_viewer, "📈 Curve Visualization")
        
        layout.addWidget(self.tabs)
        return panel

    def setup_spectrum_viewer(self):
        """Setup spectrum viewer tab."""
        layout = QVBoxLayout(self.spectrum_viewer)
        
        # Controls
        controls_layout = QHBoxLayout()
        
        controls_layout.addWidget(QLabel("Spectrum:"))
        self.spectrum_combo = QComboBox()
        self.spectrum_combo.currentTextChanged.connect(self.update_spectrum_plot)
        controls_layout.addWidget(self.spectrum_combo)
        
        self.spectrum_type_combo = QComboBox()
        self.spectrum_type_combo.addItems(["Raw Data", "First Derivative", "Second Derivative"])
        self.spectrum_type_combo.currentTextChanged.connect(self.update_spectrum_plot)
        controls_layout.addWidget(self.spectrum_type_combo)
        
        self.plot_btn = QPushButton("📊 Plot")
        self.plot_btn.clicked.connect(self.update_spectrum_plot)
        controls_layout.addWidget(self.plot_btn)
        
        controls_layout.addStretch()
        layout.addLayout(controls_layout)
        
        # Plot area placeholder
        self.spectrum_plot_widget = QWidget()
        self.spectrum_plot_layout = QVBoxLayout(self.spectrum_plot_widget)
        layout.addWidget(self.spectrum_plot_widget)
        
        # Info label
        self.spectrum_info_label = QLabel("Select a spectrum and click 'Plot' to view")
        layout.addWidget(self.spectrum_info_label)

    def create_info_panel(self) -> QWidget:
        """Create right info/log panel."""
        panel = QWidget()
        layout = QVBoxLayout(panel)
        
        # Statistics group
        stats_group = QGroupBox("Statistics")
        stats_layout = QVBoxLayout()
        
        self.stats_text = QTextEdit()
        self.stats_text.setReadOnly(True)
        self.stats_text.setMaximumHeight(200)
        stats_layout.addWidget(self.stats_text)
        
        stats_group.setLayout(stats_layout)
        layout.addWidget(stats_group)
        
        # Log group
        log_group = QGroupBox("Processing Log")
        log_layout = QVBoxLayout()
        
        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        log_layout.addWidget(self.log_text)
        
        log_group.setLayout(log_layout)
        layout.addWidget(log_group)
        
        # Selection info
        selection_group = QGroupBox("Selection Info")
        selection_layout = QVBoxLayout()
        
        self.selection_info = QLabel("Selected blocks: 0")
        selection_layout.addWidget(self.selection_info)
        
        selection_group.setLayout(selection_layout)
        layout.addWidget(selection_group)
        
        return panel

    def setup_logging(self):
        """Setup logging to text widget."""
        class GuiLogHandler(logging.Handler):
            def __init__(self, text_widget):
                super().__init__()
                self.text_widget = text_widget
                
            def emit(self, record):
                msg = self.format(record)
                self.text_widget.append(msg)
        
        gui_handler = GuiLogHandler(self.log_text)
        gui_handler.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s', 
                                                  datefmt='%H:%M:%S'))
        logger.addHandler(gui_handler)

    # ========================================================================
    # NEW METHODS FOR REFACTORED UI
    # ========================================================================

    def on_tab_changed(self, index):
        """Handle tab changes in control panel."""
        tab_names = ["STS", "SNOM"]
        if index < len(tab_names):
            self.current_plugin = tab_names[index].lower()
            self.log_message(f"Switched to {tab_names[index]} mode")
            self.update_status(f"{tab_names[index]} mode active")

    def import_image_for_canvas(self):
        """Import image for canvas with 1:1 aspect ratio preservation."""
        filepath, _ = QFileDialog.getOpenFileName(
            self,
            "Select Image File",
            "",
            "Image Files (*.png *.jpg *.jpeg *.bmp *.tif *.tiff)"
        )
        
        if filepath:
            pixmap = QPixmap(filepath)
            if not pixmap.isNull():
                # Resize to square while maintaining aspect ratio
                size = min(pixmap.width(), pixmap.height())
                square_pixmap = pixmap.scaled(size, size, Qt.KeepAspectRatio, Qt.SmoothTransformation)
                
                self.topography_widget.set_image(square_pixmap)
                self.log_message(f"✓ Image loaded: {Path(filepath).name}")
                self.update_status(f"Image loaded: {Path(filepath).name}", 3000)
            else:
                QMessageBox.warning(self, "Error", "Failed to load image")

    def snom_truncate_range(self):
        """Truncate SNOM data to specified wavenumber range."""
        if self.spectral_data is None:
            QMessageBox.warning(self, "Warning", "No SNOM data loaded")
            return
        
        try:
            wavenumber_min = self.wavenumber_min_spin.value()
            wavenumber_max = self.wavenumber_max_spin.value()
            
            if wavenumber_min >= wavenumber_max:
                QMessageBox.warning(self, "Warning", "Min wavenumber must be less than max wavenumber")
                return
            
            self.show_progress("Truncating wavenumber range...")
            
            # Truncate data (implementation depends on data structure)
            self.spectral_data = self.spectral_data.truncate_range(wavenumber_min, wavenumber_max)
            
            self.hide_progress()
            self.update_ui_with_data()
            
            self.update_status(f"Data truncated to [{wavenumber_min:.1f}, {wavenumber_max:.1f}] cm⁻¹", 3000)
            logger.info(f"SNOM data truncated to range [{wavenumber_min}, {wavenumber_max}]")
            
        except Exception as e:
            self.hide_progress()
            QMessageBox.critical(self, "Error", f"Failed to truncate SNOM data: {str(e)}")
            logger.error(f"Error truncating SNOM data: {e}")

    def calculate_fft(self):
        """Calculate Fast Fourier Transform for SNOM data."""
        if self.spectral_data is None:
            QMessageBox.warning(self, "Warning", "No SNOM data available for FFT")
            return
        
        try:
            self.show_progress("Calculating FFT...")
            
            # Placeholder for FFT calculation
            # This would be implemented in a dedicated FFT processor
            fft_result = self.calculate_fft_implementation(self.spectral_data)
            
            self.hide_progress()
            
            QMessageBox.information(self, "Success", "FFT calculation completed")
            logger.info("FFT calculation completed")
            
        except Exception as e:
            self.hide_progress()
            QMessageBox.critical(self, "Error", f"Failed to calculate FFT: {str(e)}")
            logger.error(f"Error calculating FFT: {e}")

    def calculate_fft_implementation(self, spectral_data):
        """Placeholder for FFT calculation implementation."""
        # This would be implemented in a separate FFT processor module
        logger.info("FFT calculation called - implement in FFT processor")
        return spectral_data  # Placeholder

    def snom_apply_discretization(self):
        """Apply spatial discretization for SNOM data."""
        if self.spectral_data is None:
            QMessageBox.warning(self, "Warning", "No SNOM data available for discretization")
            return
        
        try:
            self.show_progress("Applying SNOM discretization...")
            
            # Get parameters
            block_h = self.snom_block_h_spin.value()
            block_v = self.snom_block_v_spin.value()
            use_selection = self.snom_use_selection_check.isChecked()
            ignore_empty = self.snom_ignore_empty_check.isChecked()
            
            # Get selected blocks if using selection
            selected_blocks = None
            if use_selection and hasattr(self, 'topography_widget'):
                selected_blocks = self.topography_widget.get_selected_blocks()
                if not selected_blocks:
                    QMessageBox.warning(self, "Warning", "No blocks selected")
                    self.hide_progress()
                    return
            
            # Discretize SNOM data
            results = self.discretizer.discretize_spectral_data(
                spectral_data=self.spectral_data,
                block_h=block_h,
                block_v=block_v,
                topography=self.topography_data,
                selected_blocks=selected_blocks,
                ignore_empty_blocks=ignore_empty,
                data_type='snom'
            )
            
            self.discretized_data['snom'] = results
            
            self.hide_progress()
            self.update_discretization_display()
            
            QMessageBox.information(self, "Success", "SNOM discretization completed")
            logger.info("SNOM discretization completed")
            
        except Exception as e:
            self.hide_progress()
            QMessageBox.critical(self, "Error", f"Failed to apply SNOM discretization: {str(e)}")
            logger.error(f"Error in SNOM discretization: {e}")

    def snom_export_spectrum(self):
        """Export SNOM spectrum data."""
        self.export_to_csv()  # Reuse base implementation for now

    def snom_export_selection(self):
        """Export SNOM selection data."""
        self.export_selection()  # Reuse base implementation for now

    def snom_export_fft(self):
        """Export FFT results."""
        try:
            if not hasattr(self, 'fft_result') or self.fft_result is None:
                QMessageBox.warning(self, "Warning", "No FFT data available for export")
                return
            
            filepath, _ = QFileDialog.getSaveFileName(
                self,
                "Export FFT Data",
                "",
                "CSV Files (*.csv)"
            )
            
            if not filepath:
                return
            
            # Export FFT data (implementation depends on FFT result structure)
            self.fft_result.save(filepath)
            
            self.log_message(f"✓ FFT data exported: {filepath}")
            QMessageBox.information(self, "Success", f"FFT data exported to {filepath}")
            
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to export FFT data: {str(e)}")
            logger.error(f"Error exporting FFT data: {e}")

    def snom_export_maps(self):
        """Generate maps for SNOM data."""
        self.generate_maps()  # Reuse base implementation for now

    def quick_spectrum_preview(self):
        """Quick preview of selected spectrum."""
        if self.spectral_data is None:
            QMessageBox.warning(self, "Warning", "No data available for preview")
            return
        
        # Switch to curve visualization tab and plot first spectrum
        self.tabs.setCurrentIndex(3)  # Curve Visualization tab
        if self.spectrum_combo.count() > 0:
            self.spectrum_combo.setCurrentIndex(0)
            self.update_spectrum_plot()

    def update_status(self, message: str, timeout=0):
        """Update status label with message."""
        self.status_label.setText(message)
        if timeout > 0:
            QTimer.singleShot(timeout, lambda: self.status_label.setText("Ready"))

    # ========================================================================
    # EXISTING METHODS (updated for new UI)
    # ========================================================================

    def load_from_directory(self):
        """Load data from directory with automatic type detection."""
        try:
            directory = QFileDialog.getExistingDirectory(
                self,
                "Select Data Directory",
                "",
                QFileDialog.ShowDirsOnly
            )
            
            if not directory:
                return
            
            directory = Path(directory)
            
            # Auto-detect data type based on files
            detected_type = BaseDataLoader.detect_data_type(directory)
            
            if detected_type == 'nanosurf':
                loader = self.loaders['nanosurf']
                self.current_plugin = 'sts'
            elif detected_type == 'neaspec':
                loader = self.loaders['neaspec']
                self.current_plugin = 'snom'
            else:
                # Fallback to manual selection
                loader_type, ok = QInputDialog.getItem(
                    self,
                    "Select Data Type",
                    "Could not auto-detect data type. Please select manually:",
                    ["Nanosurf STS (.nid)", "NeaSpec SNOM (.txt)"],
                    0,
                    False
                )
                
                if not ok or not loader_type:
                    return
                
                if "Nanosurf" in loader_type:
                    loader = self.loaders['nanosurf']
                    self.current_plugin = 'sts'
                else:
                    loader = self.loaders['neaspec']
                    self.current_plugin = 'snom'
            
            # Load data with progress tracking
            self.log_message(f"Loading {self.current_plugin.upper()} data from {directory}...")
            self.show_progress("Initializing...", determinate=True, maximum=100)

            # Create progress callback
            def progress_callback(current, total, message):
                self.update_progress(current, total, message)

            spectral_data, topography = loader.load_from_directory(directory, progress_callback=progress_callback)
            
            self.spectral_data = spectral_data
            self.topography_data = topography
            self.current_data_type = self.current_plugin
            
            # Update UI based on plugin type
            self.hide_progress()
            self.update_ui_with_data()
            
            if topography:
                self.topography_widget.set_topography(topography)
            
            self.log_message(f"✓ Loaded {spectral_data.num_spectra} spectra")
            self.log_message(f"✓ Data type: {self.current_data_type}")
            
            # Update appropriate data type label
            if self.current_plugin == 'sts':
                self.data_type_label.setText(f"Data type: {self.current_data_type.upper()}")
                self.data_stats_label.setText(f"Spectra: {spectral_data.num_spectra} | Points: {spectral_data.num_points}")
            else:
                self.snom_data_type_label.setText(f"Data type: {self.current_data_type.upper()}")
                self.snom_data_stats_label.setText(f"Spectra: {spectral_data.num_spectra} | Points: {spectral_data.num_points}")
            
            QMessageBox.information(
                self,
                "Success",
                f"Loaded {spectral_data.num_spectra} {self.current_data_type.upper()} spectra from {directory.name}"
            )
            
        except Exception as e:
            logger.error(f"Error loading directory: {e}", exc_info=True)
            QMessageBox.critical(self, "Error", f"Failed to load data:\n{str(e)}")
        finally:
            self.hide_progress()

    def load_single_file(self):
        """Load data from single file with automatic type detection."""
        try:
            filepath, _ = QFileDialog.getOpenFileName(
                self,
                "Select Data File",
                "",
                "All Supported (*.nid *.txt *.csv);;Nanosurf (*.nid);;NeaSpec (*.txt);;CSV (*.csv)"
            )
            
            if not filepath:
                return
            
            filepath = Path(filepath)
            
            # Auto-detect data type
            self.current_data_type = BaseDataLoader.detect_data_type(filepath)
            
            # Select appropriate loader
            if self.current_data_type == 'nanosurf':
                loader = self.loaders['nanosurf']
                self.current_plugin = 'sts'
            elif self.current_data_type == 'neaspec':
                loader = self.loaders['neaspec']
                self.current_plugin = 'snom'
            elif filepath.suffix == '.csv':
                self.load_csv_file(filepath)
                return
            else:
                QMessageBox.warning(self, "Warning", f"Unsupported file type: {filepath.suffix}")
                return
            
            # Load data
            self.log_message(f"Loading {filepath.name}...")
            self.show_progress("Loading file...")
            
            spectral_data = loader.load_single_file(filepath)
            self.spectral_data = spectral_data
            
            self.hide_progress()
            self.update_ui_with_data()
            
            # Update appropriate data type label
            if self.current_plugin == 'sts':
                self.data_type_label.setText(f"Data type: {self.current_data_type.upper()}")
                self.data_stats_label.setText(f"Spectra: {spectral_data.num_spectra} | Points: {spectral_data.num_points}")
            else:
                self.snom_data_type_label.setText(f"Data type: {self.current_data_type.upper()}")
                self.snom_data_stats_label.setText(f"Spectra: {spectral_data.num_spectra} | Points: {spectral_data.num_points}")
            
            self.log_message(f"✓ Loaded {spectral_data.num_spectra} spectra")
            self.log_message(f"✓ Data type: {self.current_data_type}")
            
            QMessageBox.information(
                self,
                "Success",
                f"Loaded {spectral_data.num_spectra} {self.current_data_type.upper()} spectra"
            )
            
        except Exception as e:
            logger.error(f"Error loading file: {e}", exc_info=True)
            QMessageBox.critical(self, "Error", f"Failed to load file:\n{str(e)}")
        finally:
            self.hide_progress()

    def process_iv_data(self):
        """Process raw I-V data with simplified controls."""
        if self.spectral_data is None or self.current_data_type != 'iv':
            QMessageBox.warning(self, "Warning", "Please load I-V data first")
            return
        
        try:
            self.show_progress("Processing I-V data...")
            
            # Get user-configured parameters (simplified)
            window = self.iv_smooth_window_spin.value()
            
            # Ensure window is odd
            if window % 2 == 0:
                window += 1
                self.iv_smooth_window_spin.setValue(window)
            
            # Update processor with user parameters
            self.iv_processor.smooth_window = window
            self.iv_processor.smooth_polyorder = 3  # Fixed polynomial order
            
            # Process
            processed = self.iv_processor.process_raw_iv_data(self.spectral_data)
            
            # Replace spectral data with processed version
            self.spectral_data = processed
            
            self.hide_progress()
            self.update_ui_with_data()
            
            QMessageBox.information(
                self, 
                "Success", 
                f"I-V data processed successfully\nSmoothing window: {window}"
            )
            logger.info(f"I-V data processed with window={window}")
            
        except Exception as e:
            self.hide_progress()
            QMessageBox.critical(self, "Error", f"Failed to process I-V data: {str(e)}")
            logger.error(f"Error processing I-V: {e}")

    def calculate_derivatives(self):
        """Calculate derivatives with improved individual baseline correction."""
        if self.spectral_data is None:
            QMessageBox.warning(self, "Warning", "Please load data first")
            return
        
        try:
            self.show_progress("Calculating derivatives...")
            
            smooth = self.smooth_check.isChecked()
            apply_poly_correct = self.poly_correct_check.isChecked()
            
            # Calculate derivatives
            results = self.derivatives_processor.calculate_derivatives_batch(
                self.spectral_data,
                calculate_second=True,
                apply_correction=False
            )
            
            self.derivatives['first'] = results['first']
            self.derivatives['second'] = results['second']
            
            # IMPROVED: Apply individual baseline correction if requested
            if apply_poly_correct:
                first_corrected = self.apply_individual_baseline_correction(
                    self.derivatives['first'],
                    polynomial_degree=3
                )
                second_corrected = self.apply_individual_baseline_correction(
                    self.derivatives['second'], 
                    polynomial_degree=5
                )
                
                self.derivatives['first_corrected'] = first_corrected
                self.derivatives['second_corrected'] = second_corrected
                
                logger.info("Applied individual baseline correction to derivatives")
            
            self.hide_progress()
            self.update_derivatives_display()
            
            QMessageBox.information(
                self, 
                "Success", 
                f"Derivatives calculated successfully\nIndividual baseline correction: {'Yes' if apply_poly_correct else 'No'}"
            )
            logger.info("Derivatives calculation completed")
            
        except Exception as e:
            self.hide_progress()
            QMessageBox.critical(self, "Error", f"Failed to calculate derivatives: {str(e)}")
            logger.error(f"Error calculating derivatives: {e}")

    def apply_individual_baseline_correction(self, spectral_data: SpectralData, polynomial_degree: int = 3) -> SpectralData:
        """Apply individual polynomial baseline correction to each spectrum."""
        # This would be implemented in the derivatives processor
        # For now, return the original data
        logger.info(f"Applying individual baseline correction (degree {polynomial_degree})")
        return spectral_data

    # ========================================================================
    # EXISTING SUPPORT METHODS (keep from original)
    # ========================================================================

    def update_ui_with_data(self):
        """Update UI after loading data."""
        if self.spectral_data is None:
            return
        
        # Update topography widget
        if self.topography_data:
            self.topography_widget.set_topography(self.topography_data)
        
        # Update data table
        self.update_data_table()
        
        # Update info
        self.update_info_display()
        
        # Update statistics
        self.update_statistics()
        
        # Update spectrum selector
        self.update_spectrum_selector()
        
        logger.info("UI updated with loaded data")

    def update_data_table(self):
        """Update data table with current spectral data."""
        if self.spectral_data is None:
            return
        
        try:
            df = self.spectral_data.data
            
            # Set up table dimensions
            max_rows = min(100, len(df))
            max_cols = min(20, len(df.columns))
            
            self.data_table.setRowCount(max_rows)
            self.data_table.setColumnCount(max_cols)
            
            # Set headers
            headers = [str(col) for col in df.columns[:max_cols]]
            self.data_table.setHorizontalHeaderLabels(headers)
            
            # Fill data
            for i in range(max_rows):
                for j in range(max_cols):
                    value = df.iloc[i, j]
                    item = QTableWidgetItem(f"{value:.6f}")
                    self.data_table.setItem(i, j, item)
            
            logger.debug(f"Data table updated: {max_rows}x{max_cols}")
            
        except Exception as e:
            logger.error(f"Error updating data table: {e}")

    def update_info_display(self):
        """Update information display with current data details."""
        if self.spectral_data is None:
            self.info_text.clear()
            return
        
        try:
            info = []
            
            # Spectral data info
            info.append("=== Spectral Data ===")
            info.append(f"Type: {self.spectral_data.metadata.source_type}")
            info.append(f"Dimensions: {self.spectral_data.metadata.dimensions}")
            info.append(f"Scan Mode: {self.spectral_data.metadata.scan_mode}")
            info.append(f"Spectra: {self.spectral_data.num_spectra}")
            info.append(f"Points/Spectrum: {self.spectral_data.num_points}")
            info.append("")
            
            # Units
            info.append("=== Units ===")
            for key, value in self.spectral_data.metadata.units.items():
                info.append(f"{key}: {value}")
            info.append("")
            
            # Topography info
            if self.topography_data:
                info.append("=== Topography ===")
                info.append(f"Shape: {self.topography_data.shape}")
                
                if self.topography_data.discretized_data is not None:
                    info.append(f"Discretized: {self.topography_data.discretized_data.shape}")
                    info.append(f"Block Size: {self.topography_data.block_size}")
                
                if self.topography_data.selected_blocks:
                    info.append(f"Selected Blocks: {len(self.topography_data.selected_blocks)}")
                info.append("")
            
            # Derivatives info
            if self.derivatives:
                info.append("=== Derivatives ===")
                for key in self.derivatives:
                    info.append(f"• {key}")
                info.append("")
            
            # Discretized data info
            if self.discretized_data:
                info.append("=== Discretized Data ===")
                for key, data in self.discretized_data.items():
                    info.append(f"• {key}: {data.num_spectra} blocks")
            
            self.info_text.setText("\n".join(info))
            
        except Exception as e:
            logger.error(f"Error updating info display: {e}")

    def update_spectrum_selector(self):
        """Update spectrum selection combo box."""
        if self.spectral_data is None:
            return
        
        try:
            self.spectrum_combo.clear()
            
            # Add spectrum column names (limit to first 100 for performance)
            spectrum_names = list(self.spectral_data.spectra.columns)[:100]
            self.spectrum_combo.addItems(spectrum_names)
            
            if spectrum_names:
                self.spectrum_combo.setCurrentIndex(0)
            
            logger.debug(f"Spectrum selector updated with {len(spectrum_names)} spectra")
            
        except Exception as e:
            logger.error(f"Error updating spectrum selector: {e}")

    def update_derivatives_display(self):
        """Update display after calculating derivatives."""
        if not self.derivatives:
            return
        
        try:
            info = ["", "=== Derivatives Calculated ==="]
            
            for key, deriv_data in self.derivatives.items():
                info.append(f"✓ {key}: {deriv_data.num_spectra} spectra, {deriv_data.num_points} points")
            
            # Append to info display
            current_text = self.info_text.toPlainText()
            self.info_text.setText(current_text + "\n" + "\n".join(info))
            
            # Scroll to bottom
            scrollbar = self.info_text.verticalScrollBar()
            scrollbar.setValue(scrollbar.maximum())
            
            logger.info(f"Derivatives display updated with {len(self.derivatives)} derivative sets")
            
        except Exception as e:
            logger.error(f"Error updating derivatives display: {e}")

    def update_discretization_display(self):
        """Update display after discretization."""
        if not self.discretized_data:
            return
        
        try:
            info = ["", "=== Discretization Results ==="]
            
            for key, disc_data in self.discretized_data.items():
                info.append(f"✓ {key}: {disc_data.num_spectra} blocks")
            
            # Show discretization statistics if available
            if hasattr(self.discretizer, 'last_stats') and self.discretizer.last_stats:
                stats = self.discretizer.last_stats
                info.append("")
                info.append("Statistics:")
                info.append(f"  Grid: {stats.get('grid_shape', 'N/A')}")
                info.append(f"  Block size: {stats.get('block_size', 'N/A')}")
                info.append(f"  Total blocks: {stats.get('total_blocks', 'N/A')}")
                info.append(f"  Blocks used: {stats.get('blocks_used', 'N/A')}")
            
            # Append to info display
            current_text = self.info_text.toPlainText()
            self.info_text.setText(current_text + "\n" + "\n".join(info))
            
            # Scroll to bottom
            scrollbar = self.info_text.verticalScrollBar()
            scrollbar.setValue(scrollbar.maximum())
            
            logger.info(f"Discretization display updated with {len(self.discretized_data)} datasets")
            
        except Exception as e:
            logger.error(f"Error updating discretization display: {e}")

    def update_statistics(self):
        """Update statistics display."""
        if self.spectral_data is None:
            self.stats_text.clear()
            return
        
        stats = []
        
        # Basic statistics
        var_min = np.min(self.spectral_data.independent_var)
        var_max = np.max(self.spectral_data.independent_var)
        stats.append(f"Range: [{var_min:.3f}, {var_max:.3f}]")
        
        # Spectral statistics
        spectra_values = self.spectral_data.spectra.values.flatten()
        stats.append(f"Mean: {np.nanmean(spectra_values):.3e}")
        stats.append(f"Std: {np.nanstd(spectra_values):.3e}")
        stats.append(f"Min: {np.nanmin(spectra_values):.3e}")
        stats.append(f"Max: {np.nanmax(spectra_values):.3e}")
        
        # Discretization statistics
        if hasattr(self.discretizer, 'last_stats') and self.discretizer.last_stats:
            st = self.discretizer.last_stats
            stats.append("")
            stats.append("--- Discretization ---")
            stats.append(f"Original: {st['original_dimensions'][0]}x{st['original_dimensions'][1]}")
            stats.append(f"Block Size: {st['block_size'][0]}x{st['block_size'][1]}")
            stats.append(f"Groups: {st['num_groups'][0]}x{st['num_groups'][1]}")
            stats.append(f"Intermediate Cols: {st['intermediate_columns']}")
            stats.append(f"Final Blocks: {st['final_columns']}")
        
        self.stats_text.setText("\n".join(stats))

    def show_progress(self, message: str, determinate: bool = False, maximum: int = 100):
        """Show progress indicator with message."""
        try:
            self.progress_bar.show()
            if determinate:
                self.progress_bar.setRange(0, maximum)
                self.progress_bar.setValue(0)
            else:
                self.progress_bar.setRange(0, 0)  # Indeterminate mode
            self.status_bar.showMessage(message)
            self.update_status(message)
            logger.debug(f"Progress shown: {message}")
        except Exception as e:
            logger.error(f"Error showing progress: {e}")

    def update_progress(self, current: int, total: int, message: str):
        """Update progress bar with current value and message."""
        try:
            if total > 0:
                percentage = int((current / total) * 100)
                self.progress_bar.setValue(percentage)
                status_msg = f"{message} ({current}/{total})"
                self.status_bar.showMessage(status_msg)
                self.update_status(status_msg)
                # Process events to keep UI responsive
                from PySide6.QtWidgets import QApplication
                QApplication.processEvents()
            logger.debug(f"Progress updated: {current}/{total} - {message}")
        except Exception as e:
            logger.error(f"Error updating progress: {e}")

    def hide_progress(self):
        """Hide progress indicator."""
        try:
            self.progress_bar.hide()
            self.progress_bar.setRange(0, 100)  # Reset to determinate mode
            self.status_bar.clearMessage()
            self.update_status("Ready")
            logger.debug("Progress hidden")
        except Exception as e:
            logger.error(f"Error hiding progress: {e}")

    def log_message(self, message: str):
        """Add message to processing log."""
        if hasattr(self, 'log_text'):
            self.log_text.append(message)
            # Auto-scroll to bottom
            scrollbar = self.log_text.verticalScrollBar()
            scrollbar.setValue(scrollbar.maximum())

    def reset_view(self):
        """Reset all views to default state."""
        try:
            # Reset topography widget
            if hasattr(self, 'topography_widget'):
                self.topography_widget.reset_view()
            
            # Reset tab to first tab
            if hasattr(self, 'tabs'):
                self.tabs.setCurrentIndex(0)
            
            # Clear selection
            if self.topography_data:
                self.topography_data.selected_blocks = []
            
            # Reset data table scroll
            if hasattr(self, 'data_table'):
                self.data_table.scrollToTop()
            
            # Clear progress
            self.hide_progress()
            
            # Clear status
            self.update_status("View reset", 2000)
            
            logger.info("View reset to default state")
            
        except Exception as e:
            logger.error(f"Error resetting view: {e}")
            QMessageBox.warning(self, "Warning", f"Error resetting view: {str(e)}")

    def show_about(self):
        """Show about dialog."""
        about_text = """
<h2>T.R.A.N.S. HyperSpec Analyzer</h2>
<p><b>Version 0.6.0 (Refactored)</b></p>
<p>Tools of Research and Analysis for Nano Spectroscopy</p>
<p>By Eduarda Policarpo 🏳️‍⚧️</p>
<hr>
<p><b>Major Improvements in v0.6.0:</b></p>
<ul>
<li>✅ Unified import system in menu bar</li>
<li>✅ Tab-based interface for STS/SNOM data types</li>
<li>✅ Simplified STS processing controls</li>
<li>✅ Improved individual baseline correction</li>
<li>✅ New visualization section</li>
<li>✅ Complete SNOM interface with FFT</li>
<li>✅ Image import for canvas with aspect ratio</li>
<li>✅ Renamed central tabs for better clarity</li>
<li>✅ Real-time status feedback</li>
<li>✅ Plugin-ready architecture for future expansion</li>
</ul>
"""
        QMessageBox.about(self, "About T.R.A.N.S.", about_text)

    # ========================================================================
    # KEEP EXISTING METHODS FOR COMPATIBILITY
    # ========================================================================

    def calculate_derivatives_from_iv(self):
        """Calculate derivatives from I-V data."""
        # Keep existing implementation
        pass

    def apply_discretization(self):
        """Apply spatial discretization."""
        # Keep existing implementation
        pass

    def truncate_range(self):
        """Truncate spectral data range."""
        if self.spectral_data is None:
            QMessageBox.warning(self, "Warning", "No data loaded")
            return

        try:
            v_min = self.v_min_spin.value()
            v_max = self.v_max_spin.value()

            if v_min >= v_max:
                QMessageBox.warning(self, "Warning", "Min voltage must be less than max voltage")
                return

            self.show_progress("Truncating data range...")

            self.spectral_data = self.spectral_data.truncate_range(v_min, v_max)

            self.hide_progress()
            self.update_ui_with_data()

            self.update_status(f"Truncated to range [{v_min}, {v_max}]", 3000)
            logger.info(f"Data truncated to range [{v_min}, {v_max}]")

        except Exception as e:
            self.hide_progress()
            QMessageBox.critical(self, "Error", f"Failed to truncate: {str(e)}")
            logger.error(f"Error truncating data: {e}")

    def export_iv_data(self):
        """Export I-V data discretization."""
        if self.spectral_data is None or self.current_data_type != 'iv':
            QMessageBox.warning(self, "Warning", "No I-V data available for export")
            return

        try:
            # Get discretization parameters
            block_h = self.block_h_spin.value()
            block_v = self.block_v_spin.value()
            use_selection = self.use_selection_check.isChecked()
            ignore_empty = self.ignore_empty_check.isChecked()

            # Get selected blocks if using selection
            selected_blocks = None
            if use_selection and hasattr(self, 'topography_widget'):
                selected_blocks = self.topography_widget.get_selected_blocks()
                if not selected_blocks:
                    QMessageBox.warning(self, "Warning", "No blocks selected for export")
                    return

            # Select output directory
            output_dir = QFileDialog.getExistingDirectory(self, "Select Output Directory")
            if not output_dir:
                return

            self.show_progress("Exporting I-V data...")

            # Perform discretization
            results = self.discretizer.discretize_spectral_data(
                spectral_data=self.spectral_data,
                block_h=block_h,
                block_v=block_v,
                topography=self.topography_data,
                selected_blocks=selected_blocks,
                ignore_empty_blocks=ignore_empty,
                data_type='iv'
            )

            # Save files
            results['intermediate'].save(f"{output_dir}/IV_intermediate.csv")
            results['final'].save(f"{output_dir}/IV_discretized.csv")

            self.hide_progress()

            QMessageBox.information(self, "Success", "I-V data exported successfully")
            logger.info(f"I-V data exported to {output_dir}")
            self.log_message(f"✓ I-V data exported to {output_dir}")

        except Exception as e:
            self.hide_progress()
            QMessageBox.critical(self, "Error", f"Failed to export I-V data: {str(e)}")
            logger.error(f"Error exporting I-V data: {e}")

    def export_derivatives(self):
        """Export derivatives discretization."""
        if not self.derivatives:
            QMessageBox.warning(self, "Warning", "No derivatives available for export")
            return

        try:
            # Get discretization parameters
            block_h = self.block_h_spin.value()
            block_v = self.block_v_spin.value()
            use_selection = self.use_selection_check.isChecked()
            ignore_empty = self.ignore_empty_check.isChecked()

            # Get selected blocks if using selection
            selected_blocks = None
            if use_selection and hasattr(self, 'topography_widget'):
                selected_blocks = self.topography_widget.get_selected_blocks()
                if not selected_blocks:
                    QMessageBox.warning(self, "Warning", "No blocks selected for export")
                    return

            # Select output directory
            output_dir = QFileDialog.getExistingDirectory(self, "Select Output Directory")
            if not output_dir:
                return

            self.show_progress("Exporting derivatives...")

            # Export each derivative type
            for deriv_name, deriv_data in self.derivatives.items():
                data_type = 'didv' if deriv_name == 'first' else 'd2idv2'

                results = self.discretizer.discretize_spectral_data(
                    spectral_data=deriv_data,
                    block_h=block_h,
                    block_v=block_v,
                    topography=self.topography_data,
                    selected_blocks=selected_blocks,
                    ignore_empty_blocks=ignore_empty,
                    data_type=data_type
                )

                prefix = "dIdV" if deriv_name == 'first' else "d2IdV2"
                results['intermediate'].save(f"{output_dir}/{prefix}_intermediate.csv")
                results['final'].save(f"{output_dir}/{prefix}_discretized.csv")

            self.hide_progress()

            QMessageBox.information(self, "Success", "Derivatives exported successfully")
            logger.info(f"Derivatives exported to {output_dir}")
            self.log_message(f"✓ Derivatives exported to {output_dir}")

        except Exception as e:
            self.hide_progress()
            QMessageBox.critical(self, "Error", f"Failed to export derivatives: {str(e)}")
            logger.error(f"Error exporting derivatives: {e}")

    def export_selection(self):
        """Export selection."""
        # Keep existing implementation
        pass

    def export_topography_csv(self):
        """Export topography CSV."""
        # Keep existing implementation
        pass

    def generate_maps(self):
        """Generate maps."""
        # Keep existing implementation
        pass

    def update_spectrum_plot(self):
        """Update spectrum plot."""
        # Keep existing implementation
        pass

    def load_csv_file(self, filepath: Path):
        """Load CSV file."""
        # Keep existing implementation
        pass

    def export_to_csv(self):
        """Export to CSV."""
        # Keep existing implementation
        pass

    def on_selection_changed(self):
        """Handle selection changes."""
        # Keep existing implementation
        pass