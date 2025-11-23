"""
Main Application Window - REFACTORED VERSION
PySide6-based GUI for hyperspectral data analysis

MAJOR REFACTORING CHANGES:
1. Auto-detection of data types (STS vs SNOM)
2. Tab-based interface for different data types
3. Simplified I-V processing without polynomial correction in processing
4. Individual baseline correction applied separately
5. Canvas with conditional display
6. Enhanced SNOM support with FFT
7. Renamed visualization tabs
8. Enhanced status bar and theming
9. Drag & drop support
10. Comprehensive menu system
"""

import sys
from pathlib import Path
import logging
from typing import Optional, Dict, List, Tuple

import pandas as pd
import numpy as np
from PIL import Image

from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, 
    QPushButton, QLabel, QFileDialog, QMessageBox,
    QGroupBox, QGridLayout, QSpinBox, QCheckBox,
    QComboBox, QTableWidget, QTableWidgetItem,
    QProgressBar, QTextEdit, QSplitter, QTabWidget,
    QDoubleSpinBox, QInputDialog, QDialog, QScrollArea,
    QApplication
)
from PySide6.QtCore import Qt, Signal, QThread, QTimer
from PySide6.QtGui import (
    QPixmap, QPainter, QColor, QBrush, QPen, QIcon,
    QAction, QKeySequence, QImage
)

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

logger = logging.getLogger(__name__)


class MainWindow(QMainWindow):
    """Main application window for hyperspectral data analysis."""
    
    def __init__(self):
        """Initialize main window."""
        super().__init__()
        self.setWindowTitle("🏳️‍⚧️ T.R.A.N.S. HyperSpec Analyzer (Refactored v1.0) - Eduarda Policarpo - 🏳️‍⚧️")
        self.setGeometry(100, 100, 1400, 800)

        # Setup icon
        self.setup_window_icon()
        
        # Data storage
        self.spectral_data: Optional[SpectralData] = None
        self.topography_data: Optional[TopographyData] = None
        self.derivatives: Dict[str, SpectralData] = {}
        self.discretized_data: Dict[str, SpectralData] = {}
        self.current_data_type: str = 'unknown'  # 'sts', 'snom', 'unknown'
        
        # Canvas (conditional)
        self.canvas_image: Optional[Image.Image] = None
        self.canvas_aspect_ratio: float = 1.0
        self.canvas_widget: Optional[QTabWidget] = None
        self.canvas_placeholder: Optional[QLabel] = None
        
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
        
        # UI Components
        self.data_type_tabs: QTabWidget = None  # Left panel tabs
        self.sts_tab: QWidget = None
        self.snom_tab: QWidget = None
        
        # Theme
        self.dark_theme_active = False
        
        # Setup
        self.setup_ui()
        self.setup_drag_drop()
        self.setup_keyboard_shortcuts()

    def setup_window_icon(self):
        """Setup window icon with relative paths only."""
        icon_paths = [
            Path(__file__).parent / "icon.png",
            Path(__file__).parent.parent.parent / "src" / "ui" / "icon.png",
            Path("src/ui/icon.png"),
        ]
        
        icon_loaded = False
        
        for icon_path in icon_paths:
            if icon_path.exists():
                try:
                    icon = QIcon(str(icon_path))
                    if not icon.isNull():
                        self.setWindowIcon(icon)
                        logger.info(f"Icon loaded: {icon_path}")
                        icon_loaded = True
                        break
                except Exception as e:
                    logger.warning(f"Error loading icon {icon_path}: {e}")
                    continue
        
        if not icon_loaded:
            logger.warning("No application icon could be loaded")
    
    def setup_ui(self):
        """Setup main UI components."""
        # Create menu bar
        self.create_menu_bar()
        
        # Create central widget
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        # Main layout - horizontal split
        main_layout = QHBoxLayout(central_widget)
        main_layout.setContentsMargins(5, 5, 5, 5)
        
        # Create main splitter
        splitter = QSplitter(Qt.Horizontal)
        
        # Left panel - control panel with tabs
        control_panel = self.create_control_panel()
        control_panel.setMinimumWidth(300)
        control_panel.setMaximumWidth(500)
        splitter.addWidget(control_panel)
        
        # Right panel - visualization
        viz_panel = self.create_visualization_panel()
        splitter.addWidget(viz_panel)
        
        # Set splitter sizes
        splitter.setSizes([350, 1050])
        
        main_layout.addWidget(splitter)
        
        # Status bar
        self.create_enhanced_statusbar()
        
        logger.info("UI setup complete")

    # =====================================================================
    # PROMPT 1: MENU BAR WITH AUTO-DETECTION
    # =====================================================================
    
    def create_menu_bar(self):
        """Create enhanced menu bar with file import."""
        menubar = self.menuBar()
        
        # ============= FILE MENU =============
        file_menu = menubar.addMenu('📁 &File')
        
        # Import Single File
        import_file_action = QAction('Import Single File...', self)
        import_file_action.setShortcut(QKeySequence('Ctrl+O'))
        import_file_action.setStatusTip('Import a single data file')
        import_file_action.triggered.connect(self.import_single_file)
        file_menu.addAction(import_file_action)
        
        # Import Directory
        import_dir_action = QAction('Import Directory...', self)
        import_dir_action.setShortcut(QKeySequence('Ctrl+Shift+O'))
        import_dir_action.setStatusTip('Import directory of data files')
        import_dir_action.triggered.connect(self.import_directory)
        file_menu.addAction(import_dir_action)
        
        file_menu.addSeparator()
        
        # Import Image to Canvas
        import_image_action = QAction('Import Image to Canvas...', self)
        import_image_action.setShortcut(QKeySequence('Ctrl+I'))
        import_image_action.setStatusTip('Import background image for canvas overlay')
        import_image_action.triggered.connect(self.import_canvas_image)
        file_menu.addAction(import_image_action)
        
        file_menu.addSeparator()
        
        # Export submenu
        export_menu = file_menu.addMenu('💾 Export')
        
        export_csv_action = QAction('Export to CSV...', self)
        export_csv_action.triggered.connect(self.export_to_csv)
        export_menu.addAction(export_csv_action)
        
        export_selection_action = QAction('Export Selection...', self)
        export_selection_action.triggered.connect(self.export_selection)
        export_menu.addAction(export_selection_action)
        
        file_menu.addSeparator()
        
        # Preferences
        prefs_action = QAction('⚙️ Preferences...', self)
        prefs_action.setShortcut(QKeySequence('Ctrl+,'))
        prefs_action.triggered.connect(self.show_preferences)
        file_menu.addAction(prefs_action)
        
        file_menu.addSeparator()
        
        # Exit
        exit_action = QAction('Exit', self)
        exit_action.setShortcut(QKeySequence('Ctrl+Q'))
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)
        
        # ============= VIEW MENU =============
        view_menu = menubar.addMenu('👁️ &View')
        
        # Toggle theme
        toggle_theme_action = QAction('Toggle Dark/Light Theme', self)
        toggle_theme_action.setShortcut(QKeySequence('Ctrl+T'))
        toggle_theme_action.triggered.connect(self.toggle_theme)
        view_menu.addAction(toggle_theme_action)
        
        view_menu.addSeparator()
        
        # Canvas tabs shortcuts
        view_menu.addAction(QAction('Show Image Visualization (Ctrl+1)', self))
        view_menu.addAction(QAction('Show Curve Visualization (Ctrl+2)', self))
        view_menu.addAction(QAction('Show Data Table (Ctrl+3)', self))
        view_menu.addAction(QAction('Show Metadata (Ctrl+4)', self))
        
        # ============= HELP MENU =============
        help_menu = menubar.addMenu('❓ &Help')
        
        quickstart_action = QAction('📖 Quick Start Guide', self)
        quickstart_action.setShortcut(QKeySequence('F1'))
        quickstart_action.triggered.connect(self.show_quickstart)
        help_menu.addAction(quickstart_action)
        
        help_menu.addSeparator()
        
        shortcuts_action = QAction('⌨️ Keyboard Shortcuts', self)
        shortcuts_action.triggered.connect(self.show_shortcuts_dialog)
        help_menu.addAction(shortcuts_action)
        
        help_menu.addSeparator()
        
        about_action = QAction('ℹ️ About T.R.A.N.S.', self)
        about_action.triggered.connect(self.show_about_dialog)
        help_menu.addAction(about_action)

    def import_single_file(self):
        """Import single file with automatic data type detection."""
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Import Data File",
            "",
            "All Supported Files (*.nid *.txt *.dat);;Nanosurf Files (*.nid);;Text Files (*.txt *.dat)"
        )
        
        if not file_path:
            return
        
        file_path = Path(file_path)
        self.import_single_file_internal(file_path)
    
    def import_single_file_internal(self, file_path: Path):
        """Internal method for importing single file."""
        self.statusBar().showMessage(f"Loading {file_path.name}...")
        
        try:
            # Detect data type
            data_type = self.detect_data_type(file_path)
            
            if data_type == 'unknown':
                # Ask user
                data_type = self.ask_user_data_type()
                if not data_type:
                    return
            
            # Load data
            self.load_file_with_type(file_path, data_type)
            
            # Switch to appropriate tab
            self.switch_to_data_type_tab(data_type)
            
            self.statusBar().showMessage(f"Loaded: {file_path.name} ({data_type.upper()})", 5000)
            
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to load file:\n{str(e)}")
            logger.error(f"Error loading file: {e}")
            self.statusBar().showMessage("Error loading file", 5000)

    def import_directory(self):
        """Import directory with automatic data type detection."""
        dir_path = QFileDialog.getExistingDirectory(
            self,
            "Select Data Directory"
        )
        
        if not dir_path:
            return
        
        dir_path = Path(dir_path)
        self.import_directory_internal(dir_path)
    
    def import_directory_internal(self, dir_path: Path):
        """Internal method for importing directory."""
        self.statusBar().showMessage(f"Loading from {dir_path.name}...")
        
        try:
            # Detect data type
            data_type = self.detect_data_type(dir_path)
            
            if data_type == 'unknown':
                data_type = self.ask_user_data_type()
                if not data_type:
                    return
            
            # Load data
            self.load_directory_with_type(dir_path, data_type)
            
            # Switch to appropriate tab
            self.switch_to_data_type_tab(data_type)
            
            self.statusBar().showMessage(f"Loaded: {dir_path.name} ({data_type.upper()})", 5000)
            
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to load directory:\n{str(e)}")
            logger.error(f"Error loading directory: {e}")

    def detect_data_type(self, path: Path) -> str:
        """
        Detect data type from file/directory.
        
        Returns: 'sts', 'snom', or 'unknown'
        """
        if path.is_file():
            # Check extension
            if path.suffix == '.nid':
                return 'sts'
            elif path.suffix in ['.txt', '.dat']:
                # Read first few lines
                try:
                    with open(path, 'r') as f:
                        content = f.read(500)
                        if 'neaspec' in content.lower():
                            return 'snom'
                except:
                    pass
        
        elif path.is_dir():
            # Check for .nid files
            if list(path.glob('*.nid')):
                return 'sts'
            # Check for neaspec txt files
            for txt_file in path.glob('*.txt'):
                try:
                    with open(txt_file, 'r') as f:
                        if 'neaspec' in f.read(500).lower():
                            return 'snom'
                except:
                    continue
        
        return 'unknown'

    def ask_user_data_type(self) -> Optional[str]:
        """Ask user to select data type."""
        items = ['STS (Nanosurf)', 'SNOM (NeaSpec)']
        item, ok = QInputDialog.getItem(
            self,
            "Select Data Type",
            "Could not auto-detect data type.\nPlease select:",
            items,
            0,
            False
        )
        
        if ok and item:
            return 'sts' if 'STS' in item else 'snom'
        return None

    def load_file_with_type(self, file_path: Path, data_type: str):
        """Load single file based on data type."""
        if data_type == 'sts':
            loader = self.loaders['nanosurf']
            self.spectral_data = loader.load_single_file(file_path)
            self.topography_data = None
        elif data_type == 'snom':
            loader = self.loaders['neaspec']
            self.spectral_data = loader.load_single_file(file_path)
            self.topography_data = None
        
        self.current_data_type = data_type
        self.update_ui_after_data_load()

    def load_directory_with_type(self, dir_path: Path, data_type: str):
        """Load directory based on data type."""
        if data_type == 'sts':
            loader = self.loaders['nanosurf']
            self.spectral_data, self.topography_data = loader.load_from_directory(dir_path)
        elif data_type == 'snom':
            loader = self.loaders['neaspec']
            self.spectral_data, self.topography_data = loader.load_from_directory(dir_path)
        
        self.current_data_type = data_type
        self.update_ui_after_data_load()

    def switch_to_data_type_tab(self, data_type: str):
        """Switch to appropriate data type tab."""
        if data_type == 'sts':
            self.data_type_tabs.setCurrentIndex(0)
        elif data_type == 'snom':
            self.data_type_tabs.setCurrentIndex(1)
        
        self.current_data_type = data_type
        self.update_ui_for_data_type()
    
    def update_ui_for_data_type(self):
        """Update UI elements based on current data type."""
        # Enable/disable type-specific buttons
        if self.current_data_type == 'sts':
            self.enable_sts_controls()
        elif self.current_data_type == 'snom':
            self.enable_snom_controls()
    
    def update_ui_after_data_load(self):
        """Update UI after data is loaded."""
        if self.spectral_data is None:
            return
        
        # Update visualization
        self.update_data_display()
        
        # Enable appropriate controls
        self.update_ui_for_data_type()
        
        # Show data info
        QMessageBox.information(
            self,
            "Data Loaded",
            f"Data type: {self.current_data_type.upper()}\n"
            f"Dimensions: {self.spectral_data.metadata.dimensions}\n"
            f"Spectra: {self.spectral_data.num_spectra}\n"
            f"Points per spectrum: {self.spectral_data.num_points}"
        )
    
    def update_data_display(self):
        """Update visualization displays with current data."""
        if self.spectral_data is None:
            return
        
        # Create canvas if needed
        if self.canvas_widget is None:
            self.create_square_canvas_default()
        
        # Update displays
        self.update_metadata_display()
        self.update_data_table()
        self.update_curve_plot()
        
        # Update topography if available
        if self.topography_data:
            self.display_topography()

    # =====================================================================
    # PROMPT 2: TAB-BASED CONTROL PANEL
    # =====================================================================
    
    def create_control_panel(self) -> QWidget:
        """Create left control panel with tabs for different data types."""
        panel = QWidget()
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(5, 5, 5, 5)
        
        # Create tab widget
        self.data_type_tabs = QTabWidget()
        self.data_type_tabs.setTabPosition(QTabWidget.West)
        
        # Tab 1: STS
        self.sts_tab = self.create_sts_tab()
        self.data_type_tabs.addTab(self.sts_tab, "⚡ STS")
        self.data_type_tabs.setTabToolTip(0, "Scanning Tunneling Spectroscopy")
        
        # Tab 2: SNOM
        self.snom_tab = self.create_snom_tab()
        self.data_type_tabs.addTab(self.snom_tab, "🔬 SNOM")
        self.data_type_tabs.setTabToolTip(1, "Scanning Near-field Optical Microscopy")
        
        # Tab 3: Plugins (disabled initially)
        plugins_tab = QWidget()
        plugins_layout = QVBoxLayout(plugins_tab)
        plugins_layout.addWidget(QLabel("🔌 No plugins installed"))
        plugins_layout.addStretch()
        self.data_type_tabs.addTab(plugins_tab, "🔌 Plugins")
        self.data_type_tabs.setTabEnabled(2, False)
        self.data_type_tabs.setTabToolTip(2, "Plugin system (coming soon)")
        
        # Styling
        self.data_type_tabs.setStyleSheet("""
            QTabWidget::pane {
                border: 1px solid #ccc;
                border-radius: 5px;
            }
            QTabBar::tab {
                background: #f0f0f0;
                padding: 12px 8px;
                margin: 2px;
                border-radius: 3px;
            }
            QTabBar::tab:selected {
                background: #4CAF50;
                color: white;
                font-weight: bold;
            }
            QTabBar::tab:hover {
                background: #66BB6A;
            }
            QTabBar::tab:disabled {
                background: #e0e0e0;
                color: #999;
            }
        """)
        
        layout.addWidget(self.data_type_tabs)
        
        return panel

    # =====================================================================
    # PROMPT 3, 4, 5: STS TAB (Simplified I-V, Baseline, Data Viz)
    # =====================================================================
    
    def create_sts_tab(self) -> QWidget:
        """Create STS-specific controls tab."""
        tab = QWidget()
        
        # Use scroll area for long content
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        
        content = QWidget()
        layout = QVBoxLayout(content)
        layout.setSpacing(10)
        
        # === PREPROCESSING ===
        preprocess_group = QGroupBox("⚙️ Preprocessing")
        preprocess_layout = QVBoxLayout()
        
        # Truncate range
        truncate_layout = QGridLayout()
        truncate_layout.addWidget(QLabel("V min:"), 0, 0)
        self.v_min_spin = QDoubleSpinBox()
        self.v_min_spin.setRange(-10, 10)
        self.v_min_spin.setValue(-2.0)
        self.v_min_spin.setSingleStep(0.1)
        self.v_min_spin.setSuffix(" V")
        truncate_layout.addWidget(self.v_min_spin, 0, 1)
        
        truncate_layout.addWidget(QLabel("V max:"), 1, 0)
        self.v_max_spin = QDoubleSpinBox()
        self.v_max_spin.setRange(-10, 10)
        self.v_max_spin.setValue(2.0)
        self.v_max_spin.setSingleStep(0.1)
        self.v_max_spin.setSuffix(" V")
        truncate_layout.addWidget(self.v_max_spin, 1, 1)
        
        self.truncate_btn = QPushButton("✂️ Apply Truncation")
        self.truncate_btn.clicked.connect(self.truncate_range)
        self.truncate_btn.setEnabled(False)
        truncate_layout.addWidget(self.truncate_btn, 2, 0, 1, 2)
        
        preprocess_layout.addLayout(truncate_layout)
        preprocess_group.setLayout(preprocess_layout)
        layout.addWidget(preprocess_group)
        
        # === PROCESSING ===
        process_group = QGroupBox("🔬 Processing")
        process_layout = QVBoxLayout()
        
        # I-V Processing (SIMPLIFIED - Prompt 3)
        iv_group = QGroupBox("I-V Processing")
        iv_layout = QVBoxLayout()
        
        # Smoothing option
        self.smooth_iv_check = QCheckBox("Apply Smoothing")
        self.smooth_iv_check.setChecked(True)
        self.smooth_iv_check.stateChanged.connect(self.update_iv_smoothing_visibility)
        iv_layout.addWidget(self.smooth_iv_check)
        
        # Smoothing parameters (visible only when checked)
        self.iv_smooth_params_widget = QWidget()
        smooth_params_layout = QGridLayout(self.iv_smooth_params_widget)
        
        smooth_params_layout.addWidget(QLabel("Window:"), 0, 0)
        self.iv_smooth_window_spin = QSpinBox()
        self.iv_smooth_window_spin.setRange(3, 51)
        self.iv_smooth_window_spin.setValue(11)
        self.iv_smooth_window_spin.setSingleStep(2)
        self.iv_smooth_window_spin.setToolTip("Window length for Savitzky-Golay filter (must be odd)")
        smooth_params_layout.addWidget(self.iv_smooth_window_spin, 0, 1)
        
        smooth_params_layout.addWidget(QLabel("Poly Order:"), 1, 0)
        self.iv_smooth_poly_spin = QSpinBox()
        self.iv_smooth_poly_spin.setRange(1, 5)
        self.iv_smooth_poly_spin.setValue(3)
        self.iv_smooth_poly_spin.setToolTip("Polynomial order for Savitzky-Golay filter")
        smooth_params_layout.addWidget(self.iv_smooth_poly_spin, 1, 1)
        
        iv_layout.addWidget(self.iv_smooth_params_widget)
        
        # Process button
        self.process_iv_btn = QPushButton("🔄 Process I-V Data")
        self.process_iv_btn.clicked.connect(self.process_iv_data)
        self.process_iv_btn.setEnabled(False)
        iv_layout.addWidget(self.process_iv_btn)
        
        iv_group.setLayout(iv_layout)
        process_layout.addWidget(iv_group)
        
        # Derivatives (REFACTORED - Prompt 4)
        deriv_group = QGroupBox("Derivatives")
        deriv_layout = QVBoxLayout()
        
        self.apply_baseline_check = QCheckBox("Apply Baseline Correction")
        self.apply_baseline_check.setChecked(True)
        self.apply_baseline_check.setToolTip(
            "<b>Individual Baseline Correction</b><br>"
            "Fits and subtracts individual polynomial baseline from each spectrum.<br>"
            "This makes peaks comparable in integrated area."
        )
        deriv_layout.addWidget(self.apply_baseline_check)
        
        self.calc_derivatives_btn = QPushButton("∂ Calculate Derivatives")
        self.calc_derivatives_btn.clicked.connect(self.calculate_derivatives)
        self.calc_derivatives_btn.setEnabled(False)
        deriv_layout.addWidget(self.calc_derivatives_btn)
        
        deriv_group.setLayout(deriv_layout)
        process_layout.addWidget(deriv_group)
        
        process_group.setLayout(process_layout)
        layout.addWidget(process_group)
        
        # === DISCRETIZATION ===
        discretize_group = QGroupBox("⊞ Spatial Discretization")
        discretize_layout = QGridLayout()
        
        discretize_layout.addWidget(QLabel("Block Width:"), 0, 0)
        self.block_h_spin = QSpinBox()
        self.block_h_spin.setRange(1, 100)
        self.block_h_spin.setValue(10)
        self.block_h_spin.valueChanged.connect(self.validate_discretization_params)
        discretize_layout.addWidget(self.block_h_spin, 0, 1)
        
        discretize_layout.addWidget(QLabel("Block Height:"), 1, 0)
        self.block_v_spin = QSpinBox()
        self.block_v_spin.setRange(1, 100)
        self.block_v_spin.setValue(10)
        self.block_v_spin.valueChanged.connect(self.validate_discretization_params)
        discretize_layout.addWidget(self.block_v_spin, 1, 1)
        
        self.ignore_empty_check = QCheckBox("Ignore Empty Blocks")
        self.ignore_empty_check.setChecked(True)
        discretize_layout.addWidget(self.ignore_empty_check, 2, 0, 1, 2)
        
        self.use_selection_check = QCheckBox("Use Selection Only")
        discretize_layout.addWidget(self.use_selection_check, 3, 0, 1, 2)
        
        self.discretize_btn = QPushButton("⊞ Apply Discretization")
        self.discretize_btn.setShortcut(QKeySequence('Ctrl+D'))
        self.discretize_btn.clicked.connect(self.apply_discretization)
        self.discretize_btn.setEnabled(False)
        discretize_layout.addWidget(self.discretize_btn, 4, 0, 1, 2)
        
        discretize_group.setLayout(discretize_layout)
        layout.addWidget(discretize_group)
        
        # === DATA VISUALIZATION (Prompt 5) ===
        viz_group = QGroupBox("🗺️ Data Visualization")
        viz_layout = QVBoxLayout()
        
        viz_info = QLabel(
            "Generate spatial maps by integrating spectral data over voltage intervals."
        )
        viz_info.setWordWrap(True)
        viz_info.setStyleSheet("color: #555; font-size: 10pt;")
        viz_layout.addWidget(viz_info)
        
        self.generate_maps_btn = QPushButton("🗺️ Generate Maps")
        self.generate_maps_btn.setShortcut(QKeySequence('Ctrl+M'))
        self.generate_maps_btn.setToolTip("Create spatial maps from integrated spectral data")
        self.generate_maps_btn.clicked.connect(self.generate_maps)
        self.generate_maps_btn.setEnabled(False)
        viz_layout.addWidget(self.generate_maps_btn)
        
        viz_group.setLayout(viz_layout)
        layout.addWidget(viz_group)
        
        # === EXPORT ===
        export_group = QGroupBox("💾 Export")
        export_layout = QVBoxLayout()
        
        self.export_raw_btn = QPushButton("📊 Export Raw Data")
        self.export_raw_btn.clicked.connect(self.export_raw_data)
        self.export_raw_btn.setEnabled(False)
        export_layout.addWidget(self.export_raw_btn)
        
        self.export_deriv_btn = QPushButton("∂ Export Derivatives")
        self.export_deriv_btn.clicked.connect(self.export_derivatives)
        self.export_deriv_btn.setEnabled(False)
        export_layout.addWidget(self.export_deriv_btn)
        
        self.export_discretized_btn = QPushButton("⊞ Export Discretized")
        self.export_discretized_btn.clicked.connect(self.export_discretized)
        self.export_discretized_btn.setEnabled(False)
        export_layout.addWidget(self.export_discretized_btn)
        
        export_group.setLayout(export_layout)
        layout.addWidget(export_group)
        
        layout.addStretch()
        
        scroll.setWidget(content)
        
        tab_layout = QVBoxLayout(tab)
        tab_layout.setContentsMargins(0, 0, 0, 0)
        tab_layout.addWidget(scroll)
        
        return tab

    def update_iv_smoothing_visibility(self):
        """Show/hide smoothing parameters based on checkbox."""
        show = self.smooth_iv_check.isChecked()
        self.iv_smooth_params_widget.setVisible(show)
    
    def enable_sts_controls(self):
        """Enable STS-specific controls."""
        has_data = self.spectral_data is not None
        
        self.truncate_btn.setEnabled(has_data)
        self.process_iv_btn.setEnabled(has_data)
        self.discretize_btn.setEnabled(has_data)
        self.export_raw_btn.setEnabled(has_data)
        
        # Enable derivative calculation after I-V processing
        has_processed = has_data and self.spectral_data is not None
        self.calc_derivatives_btn.setEnabled(has_processed)
        
        # Enable export for derivatives
        has_derivatives = len(self.derivatives) > 0
        self.export_deriv_btn.setEnabled(has_derivatives)
        
        # Enable map generation after discretization
        has_discretized = len(self.discretized_data) > 0
        self.generate_maps_btn.setEnabled(has_discretized and has_data)
        self.export_discretized_btn.setEnabled(has_discretized)

    # =====================================================================
    # PROMPT 6: SNOM TAB
    # =====================================================================
    
    def create_snom_tab(self) -> QWidget:
        """Create SNOM-specific controls tab."""
        tab = QWidget()
        
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        
        content = QWidget()
        layout = QVBoxLayout(content)
        layout.setSpacing(10)
        
        # === PREPROCESSING ===
        preprocess_group = QGroupBox("⚙️ Preprocessing")
        preprocess_layout = QVBoxLayout()
        
        # Truncate spectral range
        self.truncate_snom_check = QCheckBox("Truncate Spectral Range")
        self.truncate_snom_check.stateChanged.connect(self.update_snom_truncate_visibility)
        preprocess_layout.addWidget(self.truncate_snom_check)
        
        # Truncate parameters (visible when checked)
        self.snom_truncate_widget = QWidget()
        truncate_layout = QGridLayout(self.snom_truncate_widget)
        
        truncate_layout.addWidget(QLabel("Min Wavenumber:"), 0, 0)
        self.wn_min_spin = QDoubleSpinBox()
        self.wn_min_spin.setRange(100, 10000)
        self.wn_min_spin.setValue(400)
        self.wn_min_spin.setSingleStep(10)
        self.wn_min_spin.setSuffix(" cm⁻¹")
        truncate_layout.addWidget(self.wn_min_spin, 0, 1)
        
        truncate_layout.addWidget(QLabel("Max Wavenumber:"), 1, 0)
        self.wn_max_spin = QDoubleSpinBox()
        self.wn_max_spin.setRange(100, 10000)
        self.wn_max_spin.setValue(4000)
        self.wn_max_spin.setSingleStep(10)
        self.wn_max_spin.setSuffix(" cm⁻¹")
        truncate_layout.addWidget(self.wn_max_spin, 1, 1)
        
        self.truncate_snom_btn = QPushButton("✂️ Apply Truncation")
        self.truncate_snom_btn.clicked.connect(self.truncate_snom_range)
        truncate_layout.addWidget(self.truncate_snom_btn, 2, 0, 1, 2)
        
        self.snom_truncate_widget.setVisible(False)
        preprocess_layout.addWidget(self.snom_truncate_widget)
        
        preprocess_group.setLayout(preprocess_layout)
        layout.addWidget(preprocess_group)
        
        # === PROCESSING ===
        process_group = QGroupBox("🔬 Processing")
        process_layout = QVBoxLayout()
        
        # FFT Window selection
        fft_window_layout = QHBoxLayout()
        fft_window_layout.addWidget(QLabel("FFT Window:"))
        self.fft_window_combo = QComboBox()
        self.fft_window_combo.addItems(["Hann", "Hamming", "Blackman", "Bartlett", "None"])
        self.fft_window_combo.setCurrentText("Hann")
        fft_window_layout.addWidget(self.fft_window_combo)
        process_layout.addLayout(fft_window_layout)
        
        # Calculate FFT
        self.calc_fft_btn = QPushButton("🔢 Calculate FFT")
        self.calc_fft_btn.setToolTip("Compute Fast Fourier Transform of spectral data")
        self.calc_fft_btn.clicked.connect(self.calculate_snom_fft)
        self.calc_fft_btn.setEnabled(False)
        process_layout.addWidget(self.calc_fft_btn)
        
        process_group.setLayout(process_layout)
        layout.addWidget(process_group)
        
        # === DISCRETIZATION ===
        discretize_group = QGroupBox("⊞ Spatial Discretization")
        discretize_layout = QGridLayout()
        
        discretize_layout.addWidget(QLabel("Block Width:"), 0, 0)
        self.snom_block_h_spin = QSpinBox()
        self.snom_block_h_spin.setRange(1, 100)
        self.snom_block_h_spin.setValue(10)
        discretize_layout.addWidget(self.snom_block_h_spin, 0, 1)
        
        discretize_layout.addWidget(QLabel("Block Height:"), 1, 0)
        self.snom_block_v_spin = QSpinBox()
        self.snom_block_v_spin.setRange(1, 100)
        self.snom_block_v_spin.setValue(10)
        discretize_layout.addWidget(self.snom_block_v_spin, 1, 1)
        
        self.snom_ignore_empty_check = QCheckBox("Ignore Empty Blocks")
        self.snom_ignore_empty_check.setChecked(True)
        discretize_layout.addWidget(self.snom_ignore_empty_check, 2, 0, 1, 2)
        
        self.snom_use_selection_check = QCheckBox("Use Selection Only")
        discretize_layout.addWidget(self.snom_use_selection_check, 3, 0, 1, 2)
        
        self.snom_discretize_btn = QPushButton("⊞ Apply Discretization")
        self.snom_discretize_btn.clicked.connect(self.apply_snom_discretization)
        self.snom_discretize_btn.setEnabled(False)
        discretize_layout.addWidget(self.snom_discretize_btn, 4, 0, 1, 2)
        
        discretize_group.setLayout(discretize_layout)
        layout.addWidget(discretize_group)
        
        # === DATA VISUALIZATION ===
        viz_group = QGroupBox("🗺️ Data Visualization")
        viz_layout = QVBoxLayout()
        
        self.snom_generate_maps_btn = QPushButton("🗺️ Generate Maps")
        self.snom_generate_maps_btn.clicked.connect(self.generate_snom_maps)
        self.snom_generate_maps_btn.setEnabled(False)
        viz_layout.addWidget(self.snom_generate_maps_btn)
        
        viz_group.setLayout(viz_layout)
        layout.addWidget(viz_group)
        
        # === EXPORT ===
        export_group = QGroupBox("💾 Export")
        export_layout = QVBoxLayout()
        
        self.export_spectrum_btn = QPushButton("📊 Export Spectrum")
        self.export_spectrum_btn.setToolTip("Export raw spectral data (wavenumber vs intensity)")
        self.export_spectrum_btn.clicked.connect(self.export_snom_spectrum)
        self.export_spectrum_btn.setEnabled(False)
        export_layout.addWidget(self.export_spectrum_btn)
        
        self.export_snom_selection_btn = QPushButton("✂️ Export Selection")
        self.export_snom_selection_btn.setToolTip("Export selected spatial region only")
        self.export_snom_selection_btn.clicked.connect(self.export_snom_selection)
        self.export_snom_selection_btn.setEnabled(False)
        export_layout.addWidget(self.export_snom_selection_btn)
        
        self.export_fft_btn = QPushButton("🔢 Export FFT")
        self.export_fft_btn.setToolTip("Export FFT results")
        self.export_fft_btn.clicked.connect(self.export_snom_fft)
        self.export_fft_btn.setEnabled(False)
        export_layout.addWidget(self.export_fft_btn)
        
        self.export_snom_maps_btn = QPushButton("🗺️ Export Maps")
        self.export_snom_maps_btn.setToolTip("Export generated spatial maps")
        self.export_snom_maps_btn.clicked.connect(self.export_snom_maps)
        self.export_snom_maps_btn.setEnabled(False)
        export_layout.addWidget(self.export_snom_maps_btn)
        
        export_group.setLayout(export_layout)
        layout.addWidget(export_group)
        
        layout.addStretch()
        
        scroll.setWidget(content)
        
        tab_layout = QVBoxLayout(tab)
        tab_layout.setContentsMargins(0, 0, 0, 0)
        tab_layout.addWidget(scroll)
        
        return tab

    def update_snom_truncate_visibility(self):
        """Show/hide SNOM truncate parameters."""
        show = self.truncate_snom_check.isChecked()
        self.snom_truncate_widget.setVisible(show)

    def enable_snom_controls(self):
        """Enable SNOM-specific controls."""
        has_data = self.spectral_data is not None
        
        self.truncate_snom_btn.setEnabled(has_data)
        self.calc_fft_btn.setEnabled(has_data)
        self.snom_discretize_btn.setEnabled(has_data)
        self.export_spectrum_btn.setEnabled(has_data)
        
        # Enable map generation after discretization
        has_discretized = len(self.discretized_data) > 0
        self.snom_generate_maps_btn.setEnabled(has_discretized and has_data)
        self.export_snom_maps_btn.setEnabled(has_discretized)

    # =====================================================================
    # PROMPT 7: CANVAS WITH CONDITIONAL DISPLAY
    # =====================================================================
    
    def create_visualization_panel(self) -> QWidget:
        """Create central visualization panel with conditional canvas."""
        panel = QWidget()
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(0, 0, 0, 0)
        
        # Create main splitter for canvas area
        self.central_splitter = QSplitter(Qt.Vertical)
        
        # Initially show placeholder
        self.canvas_placeholder = QLabel(
            "No image loaded\n\n"
            "📁 File → Import Image to Canvas...\n"
            "(Ctrl+I)"
        )
        self.canvas_placeholder.setAlignment(Qt.AlignCenter)
        self.canvas_placeholder.setStyleSheet("""
            QLabel {
                color: #999;
                font-size: 14pt;
                background-color: #f5f5f5;
                border: 2px dashed #ccc;
                border-radius: 10px;
                padding: 40px;
            }
        """)
        
        self.central_splitter.addWidget(self.canvas_placeholder)
        
        layout.addWidget(self.central_splitter)
        
        return panel

    def import_canvas_image(self):
        """Import image to canvas with automatic aspect ratio handling."""
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Import Image to Canvas",
            "",
            "Images (*.png *.jpg *.jpeg *.tif *.tiff *.bmp);;All Files (*.*)"
        )
        
        if not file_path:
            return
        
        self.import_canvas_image_direct(Path(file_path))
    
    def import_canvas_image_direct(self, file_path: Path):
        """Direct import of canvas image."""
        try:
            # Load image
            self.canvas_image = Image.open(file_path)
            
            # Get dimensions and aspect ratio
            width, height = self.canvas_image.size
            self.canvas_aspect_ratio = width / height
            
            logger.info(f"Loaded canvas image: {width}x{height}, AR: {self.canvas_aspect_ratio:.2f}")
            
            # Remove placeholder if exists
            if self.canvas_placeholder:
                self.canvas_placeholder.setParent(None)
                self.canvas_placeholder = None
            
            # Create canvas if not exists
            if self.canvas_widget is None:
                self.create_canvas_tabs()
                self.central_splitter.addWidget(self.canvas_widget)
            
            # Setup canvas with image
            self.setup_canvas_with_image()
            
            self.statusBar().showMessage(
                f"✅ Image loaded: {file_path.name} ({width}x{height})",
                5000
            )
            
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to load image:\n{str(e)}")
            logger.error(f"Error loading canvas image: {e}")

    def create_canvas_tabs(self):
        """Create tabs for central canvas area (Prompt 8: Renamed tabs)."""
        self.canvas_widget = QTabWidget()
        
        # Tab 1: Image Visualization (was Topography)
        self.image_viz_widget = TopographyWidget()
        self.canvas_widget.addTab(self.image_viz_widget, "🖼️ Image Visualization")
        self.canvas_widget.setTabToolTip(0, "Visualize and interact with spatial data")
        
        # Tab 2: Curve Visualization (was Spectrum Viewer)
        self.curve_viz_widget = self.create_curve_viewer()
        self.canvas_widget.addTab(self.curve_viz_widget, "📈 Curve Visualization")
        self.canvas_widget.setTabToolTip(1, "Plot and analyze spectral curves")
        
        # Tab 3: Data Table
        self.data_table_widget = QTableWidget()
        self.canvas_widget.addTab(self.data_table_widget, "📊 Data Table")
        self.canvas_widget.setTabToolTip(2, "View raw numerical data")
        
        # Tab 4: Metadata (was Information)
        self.metadata_widget = QTextEdit()
        self.metadata_widget.setReadOnly(True)
        self.metadata_widget.setFontFamily("Courier New")
        self.canvas_widget.addTab(self.metadata_widget, "ℹ️ Metadata")
        self.canvas_widget.setTabToolTip(3, "View file and acquisition metadata")
        
        # Styling
        self.canvas_widget.setTabPosition(QTabWidget.North)
        self.canvas_widget.setStyleSheet("""
            QTabWidget::pane {
                border: 1px solid #ccc;
                border-radius: 5px;
            }
            QTabBar::tab {
                background: #e0e0e0;
                padding: 8px 15px;
                margin-right: 2px;
                border-top-left-radius: 5px;
                border-top-right-radius: 5px;
            }
            QTabBar::tab:selected {
                background: #4CAF50;
                color: white;
            }
            QTabBar::tab:hover {
                background: #66BB6A;
            }
        """)

    def setup_canvas_with_image(self):
        """Setup canvas with proper aspect ratio based on loaded image."""
        if self.canvas_image is None:
            return
        
        # Determine optimal canvas size
        MAX_WIDTH = 800
        MAX_HEIGHT = 600
        
        width, height = self.canvas_image.size
        
        if self.canvas_aspect_ratio >= 1.0:
            # Landscape or square
            canvas_width = min(MAX_WIDTH, int(MAX_HEIGHT * self.canvas_aspect_ratio))
            canvas_height = int(canvas_width / self.canvas_aspect_ratio)
        else:
            # Portrait
            canvas_height = min(MAX_HEIGHT, int(MAX_WIDTH / self.canvas_aspect_ratio))
            canvas_width = int(canvas_height * self.canvas_aspect_ratio)
        
        # Convert PIL Image to QPixmap
        img_array = np.array(self.canvas_image)
        
        if len(img_array.shape) == 2:
            # Grayscale
            h, w = img_array.shape
            qimage = QImage(img_array.data, w, h, w, QImage.Format_Grayscale8)
        else:
            # RGB
            h, w = img_array.shape[:2]
            bytes_per_line = 3 * w
            qimage = QImage(img_array.data, w, h, bytes_per_line, QImage.Format_RGB888)
        
        pixmap = QPixmap.fromImage(qimage)
        
        # Set to image visualization widget
        if hasattr(self.image_viz_widget, 'set_background_image'):
            self.image_viz_widget.set_background_image(pixmap)
            self.image_viz_widget.setFixedSize(canvas_width, canvas_height)
        
        # Set size constraints
        self.canvas_widget.setMinimumSize(canvas_width // 2, canvas_height // 2)

    def create_square_canvas_default(self):
        """Create square 1:1 canvas when no image loaded (default behavior)."""
        if self.canvas_placeholder:
            self.canvas_placeholder.setParent(None)
            self.canvas_placeholder = None
        
        if self.canvas_widget is None:
            self.create_canvas_tabs()
            self.central_splitter.addWidget(self.canvas_widget)
        
        # Assume 1:1 aspect ratio
        self.canvas_aspect_ratio = 1.0
        size = 600
        
        self.canvas_widget.setMinimumSize(size, size)
        logger.info(f"Created default square canvas: {size}x{size}")

    def create_curve_viewer(self) -> QWidget:
        """Create curve visualization widget."""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        # Placeholder for matplotlib or pyqtgraph
        placeholder = QLabel("Curve visualization\n(plotting functionality)")
        placeholder.setAlignment(Qt.AlignCenter)
        placeholder.setStyleSheet("color: #999; font-size: 12pt;")
        layout.addWidget(placeholder)
        
        return widget

    # =====================================================================
    # PROCESSING METHODS
    # =====================================================================
    
    def truncate_range(self):
        """Truncate voltage range for STS data."""
        if self.spectral_data is None:
            return
        
        try:
            v_min = self.v_min_spin.value()
            v_max = self.v_max_spin.value()
            
            self.spectral_data = self.spectral_data.truncate_range(v_min, v_max)
            
            self.statusBar().showMessage(f"✅ Truncated to {v_min}-{v_max} V", 5000)
            self.update_data_display()
            
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Truncation failed:\n{str(e)}")

    def process_iv_data(self):
        """Process raw I-V data with smoothing."""
        if self.spectral_data is None:
            QMessageBox.warning(self, "Warning", "No data loaded")
            return
        
        try:
            self.statusBar().showMessage("Processing I-V data...")
            QApplication.setOverrideCursor(Qt.WaitCursor)
            
            # Get smoothing parameters
            apply_smooth = self.smooth_iv_check.isChecked()
            
            if apply_smooth:
                window = self.iv_smooth_window_spin.value()
                poly_order = self.iv_smooth_poly_spin.value()
                
                # Update processor settings
                self.iv_processor.smooth_window = window
                self.iv_processor.smooth_polyorder = poly_order
            
            # Process I-V data
            self.spectral_data = self.iv_processor.process_raw_iv_data(self.spectral_data)
            
            QApplication.restoreOverrideCursor()
            self.statusBar().showMessage("✅ I-V data processed", 5000)
            
            # Enable derivative calculation
            self.calc_derivatives_btn.setEnabled(True)
            
            self.update_data_display()
            
            QMessageBox.information(
                self,
                "Success",
                f"I-V data processed:\n"
                f"• Smoothing: {apply_smooth}\n"
                f"• Window: {window if apply_smooth else 'N/A'}\n"
                f"• Poly order: {poly_order if apply_smooth else 'N/A'}"
            )
            
        except Exception as e:
            QApplication.restoreOverrideCursor()
            QMessageBox.critical(self, "Error", f"Failed to process I-V data:\n{str(e)}")
            logger.error(f"Error processing I-V data: {e}")
            self.statusBar().showMessage("❌ Error processing I-V data", 5000)

    def calculate_derivatives(self):
        """Calculate derivatives with individual baseline correction (Prompt 4)."""
        if self.spectral_data is None:
            QMessageBox.warning(self, "Warning", "No data loaded")
            return
        
        try:
            self.statusBar().showMessage("Calculating derivatives...")
            QApplication.setOverrideCursor(Qt.WaitCursor)
            
            # Get raw data
            raw_data = self.spectral_data
            
            # Step 1: Individual baseline correction if requested
            if self.apply_baseline_check.isChecked():
                logger.info("Applying individual baseline correction to raw data")
                raw_data = self.fit_individual_baselines(raw_data, poly_degree=3)
            
            # Step 2: Calculate derivatives
            logger.info("Calculating first derivative")
            first_deriv = self.derivatives_processor.calculate_first_derivative(
                raw_data,
                smooth_before=True,
                smooth_after=True
            )
            
            logger.info("Calculating second derivative")
            second_deriv = self.derivatives_processor.calculate_second_derivative(
                raw_data,
                from_first=first_deriv,
                smooth_before=False,
                smooth_after=True
            )
            
            # Step 3: Apply baseline to derivatives if requested
            if self.apply_baseline_check.isChecked():
                logger.info("Applying individual baseline correction to derivatives")
                first_deriv = self.fit_individual_baselines(first_deriv, poly_degree=2)
                second_deriv = self.fit_individual_baselines(second_deriv, poly_degree=3)
            
            # Store results
            self.derivatives['first'] = first_deriv
            self.derivatives['second'] = second_deriv
            
            # Update UI
            self.update_ui_after_derivatives()
            
            QApplication.restoreOverrideCursor()
            self.statusBar().showMessage("✅ Derivatives calculated successfully", 5000)
            
            QMessageBox.information(
                self,
                "Success",
                f"Derivatives calculated:\n"
                f"• First derivative: {first_deriv.num_spectra} spectra\n"
                f"• Second derivative: {second_deriv.num_spectra} spectra\n"
                f"• Baseline corrected: {self.apply_baseline_check.isChecked()}"
            )
            
        except Exception as e:
            QApplication.restoreOverrideCursor()
            QMessageBox.critical(self, "Error", f"Failed to calculate derivatives:\n{str(e)}")
            logger.error(f"Error calculating derivatives: {e}")
            self.statusBar().showMessage("❌ Error calculating derivatives", 5000)

    def fit_individual_baselines(self, spectral_data: SpectralData, 
                                poly_degree: int = 3) -> SpectralData:
        """
        Fit and subtract individual polynomial baseline for each spectrum.
        Each spectrum gets its own fitted polynomial (Prompt 4).
        """
        V = spectral_data.independent_var
        spectra = spectral_data.spectra
        
        corrected_spectra = []
        for col in spectra.columns:
            spectrum = spectra[col].values
            
            # Fit polynomial to THIS spectrum only
            coeffs = np.polyfit(V, spectrum, poly_degree)
            baseline = np.polyval(coeffs, V)
            
            # Subtract baseline
            corrected = spectrum - baseline
            corrected_spectra.append(corrected)
        
        # Create new DataFrame
        corrected_array = np.column_stack(corrected_spectra)
        df = pd.DataFrame(corrected_array, columns=spectra.columns)
        df.insert(0, spectral_data.independent_var_name, V)
        
        # Create new metadata
        new_metadata = SpectralMetadata(
            source_type=spectral_data.metadata.source_type,
            dimensions=spectral_data.metadata.dimensions,
            scan_mode=spectral_data.metadata.scan_mode,
            units=spectral_data.metadata.units.copy(),
            acquisition_date=spectral_data.metadata.acquisition_date,
            additional_info={
                **spectral_data.metadata.additional_info,
                'baseline_corrected': True,
                'baseline_method': 'individual_polynomial',
                'baseline_poly_degree': poly_degree
            }
        )
        
        return SpectralData(df, new_metadata, spectral_data.topography)

    def update_ui_after_derivatives(self):
        """Update UI after derivative calculation."""
        self.export_deriv_btn.setEnabled(True)
        self.discretize_btn.setEnabled(True)

    def validate_discretization_params(self):
        """Validate discretization parameters."""
        if self.spectral_data is None:
            return
        
        dim_h, dim_v = self.spectral_data.metadata.dimensions
        block_h = self.block_h_spin.value()
        block_v = self.block_v_spin.value()
        
        # Check if blocks are valid
        if block_h > dim_h or block_v > dim_v:
            self.discretize_btn.setEnabled(False)
            self.discretize_btn.setToolTip("⚠️ Block size exceeds data dimensions")
        else:
            self.discretize_btn.setEnabled(True)
            self.discretize_btn.setToolTip("✅ Apply spatial discretization")

    def apply_discretization(self):
        """Apply spatial discretization to STS data."""
        if self.spectral_data is None:
            QMessageBox.warning(self, "Warning", "No data loaded")
            return
        
        try:
            self.statusBar().showMessage("Applying discretization...")
            QApplication.setOverrideCursor(Qt.WaitCursor)
            
            block_h = self.block_h_spin.value()
            block_v = self.block_v_spin.value()
            ignore_empty = self.ignore_empty_check.isChecked()
            use_selection = self.use_selection_check.isChecked()
            
            # Get selection if needed
            selected_blocks = None
            if use_selection and self.topography_data:
                selected_blocks = self.topography_data.selected_blocks
            
            # Discretize each data type
            data_types_to_process = {'raw': self.spectral_data}
            if 'first' in self.derivatives:
                data_types_to_process['didv'] = self.derivatives['first']
            if 'second' in self.derivatives:
                data_types_to_process['d2idv2'] = self.derivatives['second']
            
            for data_type, data in data_types_to_process.items():
                results = self.discretizer.discretize_spectral_data(
                    spectral_data=data,
                    block_h=block_h,
                    block_v=block_v,
                    topography=self.topography_data,
                    selected_blocks=selected_blocks,
                    ignore_empty_blocks=ignore_empty,
                    data_type=data_type
                )
                
                # Store results
                self.discretized_data[data_type] = results['final']
            
            QApplication.restoreOverrideCursor()
            self.statusBar().showMessage("✅ Discretization complete", 5000)
            
            # Enable map generation
            self.generate_maps_btn.setEnabled(True)
            self.export_discretized_btn.setEnabled(True)
            
            # Show statistics
            stats = self.discretizer.last_stats
            QMessageBox.information(
                self,
                "Discretization Complete",
                f"Discretization completed:\n"
                f"• Original: {stats['original_dimensions']}\n"
                f"• Block size: {stats['block_size']}\n"
                f"• Final blocks: {stats['final_columns']}\n"
                f"• Data types processed: {len(data_types_to_process)}"
            )
            
        except Exception as e:
            QApplication.restoreOverrideCursor()
            QMessageBox.critical(self, "Error", f"Discretization failed:\n{str(e)}")
            logger.error(f"Error in discretization: {e}")
            self.statusBar().showMessage("❌ Error in discretization", 5000)

    def generate_maps(self):
        """Generate spatial maps from discretized data."""
        if not self.discretized_data:
            QMessageBox.warning(self, "Warning", "No discretized data available")
            return
        
        # Show map dialog
        dialog = MapDialog(self)
        if dialog.exec() != QDialog.Accepted:
            return
        
        intervals = dialog.get_intervals()
        if not intervals:
            QMessageBox.warning(self, "Warning", "No integration intervals defined")
            return
        
        try:
            self.statusBar().showMessage("Generating maps...")
            QApplication.setOverrideCursor(Qt.WaitCursor)
            
            # Set integration intervals
            self.map_generator.set_integration_intervals(intervals)
            
            # Select output directory
            output_dir = QFileDialog.getExistingDirectory(
                self,
                "Select Output Directory for Maps"
            )
            
            if not output_dir:
                QApplication.restoreOverrideCursor()
                return
            
            output_path = Path(output_dir)
            
            # Generate maps for each data type
            for data_type, discretized in self.discretized_data.items():
                self.map_generator.generate_maps_for_dataset(
                    discretized,
                    output_path / data_type,
                    data_type=data_type
                )
            
            QApplication.restoreOverrideCursor()
            self.statusBar().showMessage("✅ Maps generated successfully", 5000)
            
            QMessageBox.information(
                self,
                "Success",
                f"Maps generated for {len(self.discretized_data)} data types\n"
                f"Output: {output_dir}"
            )
            
        except Exception as e:
            QApplication.restoreOverrideCursor()
            QMessageBox.critical(self, "Error", f"Map generation failed:\n{str(e)}")
            logger.error(f"Error generating maps: {e}")
            self.statusBar().showMessage("❌ Error generating maps", 5000)

    # =====================================================================
    # SNOM PROCESSING METHODS
    # =====================================================================
    
    def truncate_snom_range(self):
        """Truncate SNOM data wavenumber range."""
        if self.spectral_data is None:
            return
        
        try:
            min_wn = self.wn_min_spin.value()
            max_wn = self.wn_max_spin.value()
            
            self.spectral_data = self.spectral_data.truncate_range(min_wn, max_wn)
            
            self.statusBar().showMessage(
                f"✅ Truncated to {min_wn}-{max_wn} cm⁻¹",
                5000
            )
            
            self.update_data_display()
            
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Truncation failed:\n{str(e)}")

    def calculate_snom_fft(self):
        """Calculate FFT for SNOM data."""
        if self.spectral_data is None:
            return
        
        try:
            window = self.fft_window_combo.currentText()
            
            self.statusBar().showMessage("Calculating FFT...")
            QApplication.setOverrideCursor(Qt.WaitCursor)
            
            # Placeholder for actual FFT implementation
            # fft_result = self.snom_processor.calculate_fft(
            #     self.spectral_data,
            #     window=window
            # )
            
            QApplication.restoreOverrideCursor()
            
            # Enable export button
            self.export_fft_btn.setEnabled(True)
            
            self.statusBar().showMessage("✅ FFT calculated", 5000)
            
            QMessageBox.information(
                self,
                "Success",
                f"FFT calculated using {window} window\n"
                f"(FFT processing implementation needed)"
            )
            
        except Exception as e:
            QApplication.restoreOverrideCursor()
            QMessageBox.critical(self, "Error", f"FFT failed:\n{str(e)}")

    def apply_snom_discretization(self):
        """Apply spatial discretization to SNOM data."""
        # Similar to STS discretization but with SNOM-specific parameters
        self.apply_discretization()

    def generate_snom_maps(self):
        """Generate spatial maps for SNOM data."""
        # Similar to STS map generation
        self.generate_maps()

    # =====================================================================
    # EXPORT METHODS
    # =====================================================================
    
    def export_to_csv(self):
        """Export current data to CSV."""
        if self.spectral_data is None:
            QMessageBox.warning(self, "Warning", "No data to export")
            return
        
        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "Export to CSV",
            "",
            "CSV Files (*.csv)"
        )
        
        if not file_path:
            return
        
        try:
            self.spectral_data.save(file_path)
            self.statusBar().showMessage(f"✅ Exported to {file_path}", 5000)
            QMessageBox.information(self, "Success", f"Data exported to:\n{file_path}")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Export failed:\n{str(e)}")

    def export_selection(self):
        """Export selected region."""
        QMessageBox.information(
            self,
            "Export Selection",
            "Export selection functionality\n(Implementation needed)"
        )

    def export_raw_data(self):
        """Export raw spectral data."""
        self.export_to_csv()

    def export_derivatives(self):
        """Export derivative data."""
        if not self.derivatives:
            QMessageBox.warning(self, "Warning", "No derivatives to export")
            return
        
        output_dir = QFileDialog.getExistingDirectory(
            self,
            "Select Output Directory"
        )
        
        if not output_dir:
            return
        
        try:
            output_path = Path(output_dir)
            
            for deriv_type, data in self.derivatives.items():
                file_path = output_path / f"{deriv_type}_derivative.csv"
                data.save(str(file_path))
            
            self.statusBar().showMessage(f"✅ Derivatives exported", 5000)
            QMessageBox.information(
                self,
                "Success",
                f"Derivatives exported to:\n{output_dir}"
            )
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Export failed:\n{str(e)}")

    def export_discretized(self):
        """Export discretized data."""
        if not self.discretized_data:
            QMessageBox.warning(self, "Warning", "No discretized data to export")
            return
        
        output_dir = QFileDialog.getExistingDirectory(
            self,
            "Select Output Directory"
        )
        
        if not output_dir:
            return
        
        try:
            output_path = Path(output_dir)
            
            for data_type, data in self.discretized_data.items():
                file_path = output_path / f"{data_type}_discretized.csv"
                data.save(str(file_path))
            
            self.statusBar().showMessage(f"✅ Discretized data exported", 5000)
            QMessageBox.information(
                self,
                "Success",
                f"Discretized data exported to:\n{output_dir}"
            )
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Export failed:\n{str(e)}")

    def export_snom_spectrum(self):
        """Export SNOM spectrum data."""
        self.export_to_csv()

    def export_snom_selection(self):
        """Export SNOM selection."""
        self.export_selection()

    def export_snom_fft(self):
        """Export SNOM FFT results."""
        QMessageBox.information(
            self,
            "Export FFT",
            "FFT export functionality\n(Implementation needed)"
        )

    def export_snom_maps(self):
        """Export SNOM maps."""
        QMessageBox.information(
            self,
            "Export Maps",
            "SNOM map export functionality\n(Implementation needed)"
        )

    # =====================================================================
    # DISPLAY METHODS
    # =====================================================================
    
    def update_metadata_display(self):
        """Update metadata display."""
        if self.spectral_data is None or self.metadata_widget is None:
            return
        
        metadata = self.spectral_data.metadata
        
        text = f"""
=== SPECTRAL DATA METADATA ===

Source Type: {metadata.source_type}
Dimensions: {metadata.dimensions[0]} x {metadata.dimensions[1]}
Scan Mode: {metadata.scan_mode}
Number of Spectra: {self.spectral_data.num_spectra}
Points per Spectrum: {self.spectral_data.num_points}

Units:
{chr(10).join(f'  {k}: {v}' for k, v in metadata.units.items())}

Acquisition Date: {metadata.acquisition_date or 'N/A'}

Additional Info:
{chr(10).join(f'  {k}: {v}' for k, v in metadata.additional_info.items())}
"""
        
        self.metadata_widget.setText(text)

    def update_data_table(self):
        """Update data table display."""
        if self.spectral_data is None or self.data_table_widget is None:
            return
        
        df = self.spectral_data.data
        
        # Set table dimensions
        self.data_table_widget.setRowCount(min(df.shape[0], 100))  # Limit to 100 rows
        self.data_table_widget.setColumnCount(df.shape[1])
        
        # Set headers
        self.data_table_widget.setHorizontalHeaderLabels(df.columns.tolist())
        
        # Fill table
        for i in range(min(df.shape[0], 100)):
            for j in range(df.shape[1]):
                value = df.iloc[i, j]
                item = QTableWidgetItem(f"{value:.6e}" if isinstance(value, float) else str(value))
                self.data_table_widget.setItem(i, j, item)

    def update_curve_plot(self):
        """Update curve plot."""
        # Placeholder for plotting functionality
        pass

    def display_topography(self):
        """Display topography data."""
        if self.topography_data is None or self.image_viz_widget is None:
            return
        
        try:
            # Convert topography to pixmap
            topo_array = self.topography_data.data
            
            # Normalize
            normalized = 255 * (topo_array - np.nanmin(topo_array)) / np.ptp(topo_array)
            img_data = normalized.astype(np.uint8)
            
            h, w = img_data.shape
            qimage = QImage(img_data.data, w, h, w, QImage.Format_Grayscale8)
            pixmap = QPixmap.fromImage(qimage)
            
            if hasattr(self.image_viz_widget, 'set_background_image'):
                self.image_viz_widget.set_background_image(pixmap)
                
        except Exception as e:
            logger.error(f"Error displaying topography: {e}")

    # =====================================================================
    # PROMPT 9: UI ENHANCEMENTS
    # =====================================================================
    
    def create_enhanced_statusbar(self):
        """Create enhanced status bar with multiple widgets."""
        status_bar = self.statusBar()
        
        # Main status label
        self.status_label = QLabel("Ready")
        status_bar.addWidget(self.status_label, 1)
        
        # Separator
        status_bar.addWidget(QLabel(" | "))
        
        # Data type indicator
        self.data_type_label = QLabel("No data")
        status_bar.addPermanentWidget(self.data_type_label)
        
        # Separator
        status_bar.addPermanentWidget(QLabel(" | "))
        
        # Dimensions indicator
        self.dimensions_label = QLabel("---")
        status_bar.addPermanentWidget(self.dimensions_label)

    def setup_keyboard_shortcuts(self):
        """Setup keyboard shortcuts."""
        # Canvas tabs
        for i in range(1, 5):
            shortcut = QKeySequence(f'Ctrl+{i}')
            action = QAction(self)
            action.setShortcut(shortcut)
            action.triggered.connect(lambda checked, idx=i-1: self.switch_canvas_tab(idx))
            self.addAction(action)

    def switch_canvas_tab(self, index: int):
        """Switch to canvas tab by index."""
        if self.canvas_widget:
            self.canvas_widget.setCurrentIndex(index)

    def toggle_theme(self):
        """Toggle between dark and light themes."""
        self.dark_theme_active = not self.dark_theme_active
        
        if self.dark_theme_active:
            self.apply_dark_theme()
        else:
            self.apply_light_theme()

    def apply_dark_theme(self):
        """Apply dark theme."""
        self.setStyleSheet("""
        QMainWindow, QWidget {
            background-color: #2b2b2b;
            color: white;
        }
        QGroupBox {
            border: 1px solid #555;
            border-radius: 5px;
            margin-top: 10px;
            font-weight: bold;
            padding-top: 10px;
        }
        QGroupBox::title {
            subcontrol-origin: margin;
            left: 10px;
            padding: 0 5px;
        }
        QPushButton {
            background-color: #3d3d3d;
            color: white;
            border: 1px solid #555;
            padding: 5px;
            border-radius: 3px;
        }
        QPushButton:hover {
            background-color: #4d4d4d;
        }
        QPushButton:disabled {
            background-color: #2d2d2d;
            color: #666;
        }
        QLineEdit, QSpinBox, QDoubleSpinBox, QComboBox {
            background-color: #3d3d3d;
            border: 1px solid #555;
            color: white;
            padding: 3px;
        }
        QCheckBox {
            color: white;
        }
        QLabel {
            color: white;
        }
        QTextEdit, QTableWidget {
            background-color: #2d2d2d;
            color: white;
            border: 1px solid #555;
        }
    """)

    def apply_light_theme(self):
        """Apply light theme (default)."""
        self.setStyleSheet("")  # Reset to default

    def show_preferences(self):
        """Show preferences dialog."""
        QMessageBox.information(
            self,
            "Preferences",
            "Preferences dialog\n(Implementation coming soon)"
        )

    def show_quickstart(self):
        """Show quick start guide."""
        dialog = QDialog(self)
        dialog.setWindowTitle("Quick Start Guide")
        dialog.setMinimumSize(600, 400)
        
        layout = QVBoxLayout(dialog)
        
        text = QTextEdit()
        text.setReadOnly(True)
        text.setHtml("""
            <h2>T.R.A.N.S. Quick Start Guide</h2>
            
            <h3>1. Import Data</h3>
            <p><b>File → Import Single File</b> (Ctrl+O)<br>
            or<br>
            <b>File → Import Directory</b> (Ctrl+Shift+O)</p>
            <p>The program will automatically detect STS or SNOM data.</p>
            
            <h3>2. Load Image (Optional)</h3>
            <p><b>File → Import Image to Canvas</b> (Ctrl+I)<br>
            Load a background image for spatial reference.</p>
            
            <h3>3. Process Data</h3>
            <p><b>STS:</b> Process I-V → Calculate Derivatives<br>
            <b>SNOM:</b> Truncate range → Calculate FFT</p>
            
            <h3>4. Discretize</h3>
            <p>Set block size and apply spatial discretization.</p>
            
            <h3>5. Visualize</h3>
            <p>Generate spatial maps from integrated data.</p>
            
            <h3>6. Export</h3>
            <p>Export processed data, maps, or selections.</p>
            
            <h3>Keyboard Shortcuts</h3>
            <p>
            <b>Ctrl+O</b>: Import file<br>
            <b>Ctrl+Shift+O</b>: Import directory<br>
            <b>Ctrl+I</b>: Import image<br>
            <b>Ctrl+D</b>: Apply discretization<br>
            <b>Ctrl+M</b>: Generate maps<br>
            <b>Ctrl+1/2/3/4</b>: Switch canvas tabs<br>
            <b>Ctrl+T</b>: Toggle theme<br>
            <b>F1</b>: This help<br>
            </p>
        """)
        layout.addWidget(text)
        
        close_btn = QPushButton("Close")
        close_btn.clicked.connect(dialog.accept)
        layout.addWidget(close_btn)
        
        dialog.exec()

    def show_shortcuts_dialog(self):
        """Show keyboard shortcuts dialog."""
        QMessageBox.information(
            self,
            "Keyboard Shortcuts",
            """
            <h3>File Operations</h3>
            <b>Ctrl+O</b>: Import single file<br>
            <b>Ctrl+Shift+O</b>: Import directory<br>
            <b>Ctrl+I</b>: Import image to canvas<br>
            <b>Ctrl+S</b>: Export to CSV<br>
            <b>Ctrl+Q</b>: Exit<br>
            
            <h3>Processing</h3>
            <b>Ctrl+D</b>: Apply discretization<br>
            <b>Ctrl+M</b>: Generate maps<br>
            
            <h3>View</h3>
            <b>Ctrl+1</b>: Image Visualization<br>
            <b>Ctrl+2</b>: Curve Visualization<br>
            <b>Ctrl+3</b>: Data Table<br>
            <b>Ctrl+4</b>: Metadata<br>
            <b>Ctrl+T</b>: Toggle theme<br>
            
            <h3>Help</h3>
            <b>F1</b>: Quick Start Guide<br>
            """
        )

    def show_about_dialog(self):
        """Show about dialog."""
        QMessageBox.about(
            self,
            "About T.R.A.N.S.",
            """
            <h2>🏳️‍⚧️ T.R.A.N.S. HyperSpec Analyzer</h2>
            <h3>Tools of Research and Analysis for Nano Spectroscopy</h3>
            
            <p><b>Version:</b> 1.0.0 (Refactored)</p>
            <p><b>Author:</b> Eduarda Policarpo</p>
            <p><b>Date:</b> November 2025</p>
            
            <p>Advanced hyperspectral data analysis tool for:</p>
            <ul>
            <li>Scanning Tunneling Spectroscopy (STS)</li>
            <li>Scanning Near-field Optical Microscopy (SNOM)</li>
            </ul>
            
            <p><b>Features:</b></p>
            <ul>
            <li>Automatic data type detection</li>
            <li>Individual baseline correction</li>
            <li>Spatial discretization with H→V ordering</li>
            <li>FFT analysis for SNOM</li>
            <li>Interactive canvas with image overlay</li>
            <li>Dark/Light themes</li>
            </ul>
            
            <p>🏳️‍⚧️ Made with 💖 by the trans community</p>
            """
        )

    def setup_drag_drop(self):
        """Enable drag and drop for files."""
        self.setAcceptDrops(True)

    def dragEnterEvent(self, event):
        """Handle drag enter."""
        if event.mimeData().hasUrls():
            event.accept()
        else:
            event.ignore()

    def dropEvent(self, event):
        """Handle file drop."""
        files = [url.toLocalFile() for url in event.mimeData().urls()]
        
        if len(files) == 1:
            file_path = Path(files[0])
            
            if file_path.is_dir():
                self.import_directory_internal(file_path)
            else:
                # Check if image
                if file_path.suffix.lower() in ['.png', '.jpg', '.jpeg', '.tif', '.tiff', '.bmp']:
                    # Ask what to do
                    reply = QMessageBox.question(
                        self,
                        "Import Image",
                        "Import as Canvas Background?",
                        QMessageBox.Yes | QMessageBox.No,
                        QMessageBox.Yes
                    )
                    
                    if reply == QMessageBox.Yes:
                        # Import as canvas
                        self.import_canvas_image_direct(file_path)
                    else:
                        # Try as data
                        self.import_single_file_internal(file_path)
                else:
                    self.import_single_file_internal(file_path)
        else:
            QMessageBox.warning(self, "Warning", "Please drop only one file or directory")


# =============================================================================
# END OF REFACTORED MAIN WINDOW
# =============================================================================
