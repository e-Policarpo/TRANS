================================================================================
ANÁLISE ESTRUTURAL COMPLETA DO PROJETO T.R.A.N.S.
================================================================================

📊 ESTATÍSTICAS GERAIS
--------------------------------------------------------------------------------
Total de módulos analisados: 14
Total de classes: 16
Total de métodos: 156
Total de funções: 5

================================================================================
📦 MÓDULO: base_loader.py
================================================================================

Descrição:
  Base Data Loader
Abstract base class for all data loaders...

🏛️ CLASSES:

  class BaseDataLoader
    Herda de: ABC
    Doc: Abstract base class for hyperspectral data loaders.

Each specific loader must i...
    
    Métodos (12):
      🔒 __init__(self) 🟢 C=1
         └─ Initialize base loader...
      🔓 load_from_directory(self, directory) 🟢 C=1
         └─ Load data from a directory containing measurement files....
      🔓 load_single_file(self, filepath) 🟢 C=1
         └─ Load data from a single file....
      🔓 validate_directory(self, directory) 🟡 C=6
         └─ Validate that directory exists and contains supported files....
      🔓 find_files(self, directory, pattern) 🟢 C=2
         └─ Find files matching pattern in directory....
      🔓 create_metadata(self, dimensions, scan_mode, units) 🟢 C=2
         └─ Create metadata object with common parameters....
      🔓 concatenate_spectra(self, spectra_list, independent_var, column_names) 🟢 C=5
         └─ Concatenate multiple spectra into a DataFrame....
      🔓 apply_preprocessing(self, data, smooth, window_length, polyorder) 🟢 C=3
         └─ Apply common preprocessing steps to spectral data....
      🔓 detect_data_type(filepath, sample_lines) 🔴 C=11
         └─ Detect data type from filename and content....
      🔓 get_data_type_display_name(data_type) 🟢 C=1
         └─ Get display name for data type....
      🔓 get_info(self) 🟢 C=1
         └─ Get information about the loader....
      🔒 __repr__(self) 🟢 C=1

📥 DEPENDÊNCIAS:
  - abc
  - logging
  - models.spectral_data
  - models.topography_data
  - numpy
  - pandas
  - pathlib
  - scipy.signal
  - typing

================================================================================
📦 MÓDULO: derivatives.py
================================================================================

Descrição:
  Derivatives Processing Module
Handles calculation and correction of derivatives for spectral data...

🏛️ CLASSES:

  class DerivativesProcessor
    Doc: Processor for calculating and correcting spectral derivatives.

Supports first a...
    
    Métodos (7):
      🔒 __init__(self, smooth_window, smooth_polyorder) 🟢 C=1
         └─ Initialize derivatives processor....
      🔓 calculate_first_derivative(self, spectral_data, smooth_before, smooth_after) 🟢 C=5
         └─ Calculate first derivative (dI/dV or equivalent)....
      🔓 calculate_second_derivative(self, spectral_data, from_first, smooth_before, smooth_after) 🟡 C=7
         └─ Calculate second derivative (d²I/dV² or equivalent)....
      🔓 polynomial_baseline_correction(self, spectral_data, poly_degree) 🟢 C=2
         └─ Apply polynomial baseline correction to spectra....
      🔓 correct_derivatives_with_polynomials(self, first_deriv, second_deriv, first_poly_degree, second_poly_degree) 🟢 C=1
         └─ Apply polynomial baseline correction to both derivatives....
      🔒 _smooth_data(self, data) 🟢 C=3
         └─ Apply Savitzky-Golay smoothing to data....
      🔓 calculate_derivatives_batch(self, spectral_data, calculate_second, apply_correction) 🟢 C=4
         └─ Calculate and optionally correct both derivatives in one bat...

📥 DEPENDÊNCIAS:
  - logging
  - models.spectral_data
  - numpy
  - pandas
  - scipy.signal
  - typing

================================================================================
📦 MÓDULO: discretization.py
================================================================================

Descrição:
  Discretization Module
Handles spatial discretization of hyperspectral data with block averaging...

🏛️ CLASSES:

  class Discretizer
    Doc: Handles discretization of hyperspectral data into blocks.

This module correctly...
    
    Métodos (10):
      🔒 __init__(self) 🟢 C=1
         └─ Initialize discretizer....
      🔓 discretize_spectral_data(self, spectral_data, block_h, block_v, topography, selected_blocks, ignore_empty_blocks, data_type) 🟡 C=6
         └─ Discretize spectral data into blocks with proper edge handli...
      🔒 _horizontal_averaging(self, cube, dim_h, dim_v, block_h, num_groups_h, var_name, ignore_empty, data_type) 🟡 C=9
         └─ Perform horizontal averaging stage....
      🔒 _vertical_averaging(self, cube, dim_h, dim_v, block_h, block_v, num_groups_h, num_groups_v, var_name, ignore_empty, data_type) 🟡 C=9
         └─ Perform vertical averaging stage to create final blocks....
      🔒 _create_selection_mask(self, dim_h, dim_v, block_h, block_v, selected_blocks) 🟢 C=2
         └─ Create 2D boolean mask from selected blocks....
      🔒 _create_discretized_metadata(self, original_metadata, stage, block_size, num_blocks, data_type) 🟢 C=1
         └─ Create metadata for discretized data....
      🔓 validate_block_selection(self, spectral_data, block_h, block_v, selected_blocks) 🟢 C=4
         └─ Validate that selected blocks are within bounds....
      🔓 get_block_info(self, spectral_data, block_h, block_v) 🟡 C=9
         └─ Get information about discretization blocks....
      🔓 export_discretized_data(self, spectral_data, block_h, block_v, output_directory, data_type, use_selection, selected_blocks, ignore_empty_blocks) 🟢 C=4
         └─ Export discretized data to CSV files with specialized naming...
      🔓 batch_discretize_multiple_types(self, data_dict, block_h, block_v, output_directory, use_selection, selected_blocks, ignore_empty_blocks) 🟢 C=3
         └─ Discretize multiple data types in batch....

📥 DEPENDÊNCIAS:
  - logging
  - math
  - models.spectral_data
  - models.topography_data
  - numpy
  - os
  - pandas
  - pathlib
  - typing

================================================================================
📦 MÓDULO: integration.py
================================================================================

Descrição:
  Integration Processing Module
Handles integration of spectral data over specified intervals...

🏛️ CLASSES:

  class IntegrationProcessor
    Doc: Processes spectral data integration over voltage intervals....
    
    Métodos (3):
      🔒 __init__(self) 🟢 C=1
      🔓 set_intervals(self, intervals) 🟢 C=1
         └─ Set integration intervals....
      🔓 integrate_spectral_data(self, spectral_data) 🟢 C=3
         └─ Integrate spectral data over all configured intervals....

📥 DEPENDÊNCIAS:
  - logging
  - models.spectral_data
  - numpy
  - typing

================================================================================
📦 MÓDULO: iv_processor.py
================================================================================

Descrição:
  I-V Data Processor
Handles raw I-V curve processing and conversion to derivatives...

🏛️ CLASSES:

  class IVDataProcessor
    Doc: Processor for raw I-V data with derivative calculation....
    
    Métodos (6):
      🔒 __init__(self, smooth_window, smooth_polyorder) 🟢 C=1
         └─ Initialize I-V processor....
      🔓 process_raw_iv_data(self, spectral_data) 🟢 C=1
         └─ Process raw I-V data with smoothing....
      🔓 calculate_derivatives_from_iv(self, iv_data, smooth_before, smooth_after) 🟢 C=4
         └─ Calculate first and second derivatives from I-V data....
      🔒 _create_derivative_dataframe(self, derivative_data, V, original_data, prefix) 🟢 C=1
         └─ Create DataFrame for derivative data....
      🔒 _create_derivative_metadata(self, original_metadata, derivative_order, smooth_before, smooth_after) 🟢 C=5
         └─ Create metadata for derivative data....
      🔒 _smooth_data(self, data) 🟢 C=3
         └─ Apply Savitzky-Golay smoothing to data....

📥 DEPENDÊNCIAS:
  - logging
  - models.spectral_data
  - numpy
  - pandas
  - scipy.signal
  - typing

================================================================================
📦 MÓDULO: main.py
================================================================================

Descrição:
  HyperSpec Analyzer - Main Entry Point
Advanced tool for hyperspectral data analysis...

⚙️ FUNÇÕES:

  def setup_application_style(app) 🟢 C=2
    └─ Setup application style and theme....
  def setup_application_icon(app) 🔴 C=11
    └─ Setup application icon with macOS-specific fixes....
  def create_fallback_icon(app) 🟢 C=2
    └─ Create a simple programmatic fallback icon....
  def setup_macos_specific_settings() 🟢 C=2
    └─ Setup macOS-specific environment settings....
  def main() 🟡 C=7
    └─ Main application entry point....

📥 DEPENDÊNCIAS:
  - AppKit
  - PySide6.QtCore
  - PySide6.QtGui
  - PySide6.QtWidgets
  - logging
  - os
  - pathlib
  - src.ui.main_window
  - sys
  - traceback

================================================================================
📦 MÓDULO: main_window.py
================================================================================

Descrição:
  Main Application Window - IMPROVED VERSION
PySide6-based GUI for hyperspectral data analysis

CHANGES IN THIS VERSION:
1. Fixed hard-coded paths
2. Added UI for polynomial correction
3. Added UI for I...

🏛️ CLASSES:

  class MainWindow
    Herda de: QMainWindow
    Doc: Main application window for hyperspectral data analysis....
    
    Métodos (35):
      🔒 __init__(self) 🟢 C=1
         └─ Initialize main window....
      🔓 setup_window_icon(self) 🟡 C=6
         └─ Setup window icon with RELATIVE paths only....
      🔓 create_fallback_icon(self) 🟢 C=2
         └─ Create a simple fallback icon programmatically....
      🔓 setup_ui(self) 🟢 C=1
         └─ Setup user interface....
      🔓 create_menu_bar(self) 🟢 C=1
         └─ Create menu bar with actions....
      🔓 create_control_panel(self) 🟢 C=1
         └─ Create left control panel with enhanced controls....
      🔓 create_visualization_panel(self) 🟢 C=1
         └─ Create center visualization panel....
      🔓 setup_spectrum_viewer(self) 🟢 C=1
         └─ Setup spectrum viewer tab - IMPROVED with matplotlib placeho...
      🔓 create_info_panel(self) 🟢 C=1
         └─ Create right info/log panel with IMPROVED statistics....
      🔓 setup_logging(self) 🟢 C=1
         └─ Setup logging to text widget....
      🔓 process_iv_data(self) 🟢 C=5
         └─ Process raw I-V data with USER-CONFIGURABLE smoothing....
      🔓 calculate_derivatives(self) 🟢 C=5
         └─ Calculate derivatives with POLYNOMIAL CORRECTION option....
      🔓 calculate_derivatives_from_iv(self) 🟢 C=5
         └─ Calculate derivatives from I-V data using IV processor....
      🔓 apply_discretization(self) 🟡 C=6
         └─ Apply spatial discretization with IMPROVED statistics displa...
      🔓 export_topography_csv(self) 🟢 C=5
         └─ IMPROVEMENT: Export topography data as CSV....
      🔓 update_spectrum_plot(self) 🔴 C=12
         └─ IMPROVEMENT: Basic implementation of spectrum plotting....
      🔓 update_statistics(self) 🟢 C=4
         └─ IMPROVED: Update statistics with discretization info....
      🔓 load_from_directory(self) 🟡 C=7
         └─ Load data from directory of measurement files....
      🔓 load_single_file(self) 🟡 C=6
         └─ Load data from single file....
      🔓 load_csv_file(self, filepath) 🟢 C=2
         └─ Load spectral data from CSV file....
      🔓 export_to_csv(self) 🟡 C=6
         └─ Export current spectral data to CSV....
      🔓 export_selection(self) 🟡 C=6
         └─ Export only selected blocks....
      🔓 generate_maps(self) 🟡 C=6
         └─ Generate spatial maps from integrated data....
      🔓 on_selection_changed(self) 🟢 C=2
         └─ Handle topography selection changes....
      🔓 log_message(self, message) 🟢 C=2
         └─ Add message to processing log....
      🔓 update_ui_with_data(self) 🟢 C=3
         └─ Update UI after loading data....
      🔓 update_data_table(self) 🟢 C=5
         └─ Update data table with current spectral data....
      🔓 update_info_display(self) 🔴 C=11
         └─ Update information display with current data details....
      🔓 update_spectrum_selector(self) 🟢 C=4
         └─ Update spectrum selection combo box....
      🔓 update_derivatives_display(self) 🟢 C=4
         └─ Update display after calculating derivatives....
      🔓 update_discretization_display(self) 🟡 C=6
         └─ Update display after discretization....
      🔓 show_progress(self, message) 🟢 C=2
         └─ Show progress indicator with message....
      🔓 hide_progress(self) 🟢 C=2
         └─ Hide progress indicator....
      🔓 reset_view(self) 🟡 C=6
         └─ Reset all views to default state....
      🔓 show_about(self) 🟢 C=1
         └─ Show about dialog....

  class GuiLogHandler
    Herda de: logging.Handler
    
    Métodos (2):
      🔒 __init__(self, text_widget) 🟢 C=1
      🔓 emit(self, record) 🟢 C=1

📥 DEPENDÊNCIAS:
  - PySide6.QtCore
  - PySide6.QtGui
  - PySide6.QtWidgets
  - data_loaders.base_loader
  - data_loaders.nanosurf_sts_loader
  - data_loaders.neaspec_snom_loader
  - logging
  - map_dialog
  - matplotlib.backends.backend_qt5agg
  - matplotlib.pyplot
  ... e mais 13

================================================================================
📦 MÓDULO: map_dialog.py
================================================================================

Descrição:
  Map Generation Dialog
UI for configuring and generating spatial maps...

🏛️ CLASSES:

  class MapDialog
    Herda de: QDialog
    Doc: Dialog for configuring map generation parameters....
    
    Métodos (6):
      🔒 __init__(self, parent) 🟢 C=1
      🔓 setup_ui(self) 🟢 C=1
         └─ Setup the dialog UI....
      🔓 add_interval(self) 🟢 C=3
         └─ Add integration interval....
      🔓 remove_interval(self) 🟢 C=2
         └─ Remove selected interval....
      🔓 clear_intervals(self) 🟢 C=1
         └─ Clear all intervals....
      🔓 get_intervals(self) 🟢 C=1
         └─ Get the configured integration intervals....

📥 DEPENDÊNCIAS:
  - PySide6.QtCore
  - PySide6.QtWidgets
  - logging
  - typing

================================================================================
📦 MÓDULO: map_generator.py
================================================================================

Descrição:
  Map Generation Module
Generates spatial maps from integrated spectral data...

🏛️ CLASSES:

  class MapGenerator
    Doc: Generates spatial maps from integrated spectral data....
    
    Métodos (8):
      🔒 __init__(self) 🟢 C=1
      🔓 set_integration_intervals(self, intervals) 🟢 C=1
         └─ Set integration intervals for map generation....
      🔓 integrate_over_intervals(self, spectral_data) 🟢 C=4
         └─ Integrate spectral data over specified intervals....
      🔓 create_spatial_map(self, integrated_data, dimensions, output_path) 🟢 C=4
         └─ Create spatial map from integrated data and save as image....
      🔒 _save_map_as_image(self, map_data, output_path) 🟢 C=2
         └─ Save map data as image file (TIFF and PNG)....
      🔒 _save_colormap_image(self, map_data, output_path) 🟢 C=3
         └─ Save map with color map for better visualization....
      🔓 generate_maps_for_dataset(self, spectral_data, output_directory, data_type) 🟢 C=5
         └─ Generate maps for all integration intervals with specialized...
      🔓 generate_topography_map(self, topography_data, output_directory) 🟢 C=2
         └─ Generate topography map image....

📥 DEPENDÊNCIAS:
  - PIL
  - logging
  - matplotlib.pyplot
  - models.spectral_data
  - models.topography_data
  - numpy
  - pandas
  - pathlib
  - tifffile
  - typing

================================================================================
📦 MÓDULO: nanosurf_sts_loader.py
================================================================================

Descrição:
  Nanosurf STS Data Loader
Loader for Scanning Tunneling Spectroscopy data from Nanosurf microscopes...

🏛️ CLASSES:

  class NanosurfSTSLoader
    Herda de: BaseDataLoader
    Doc: Loader for Nanosurf STS (Scanning Tunneling Spectroscopy) data.

This loader han...
    
    Métodos (5):
      🔒 __init__(self, patch_nsfopen) 🟢 C=3
         └─ Initialize Nanosurf STS loader....
      🔒 _apply_nsfopen_patches(self) 🟢 C=4
         └─ Apply runtime patches to NSFopen for STM compatibility...
      🔓 load_from_directory(self, directory) 🔴 C=19
         └─ Load STS data from directory of .nid files....
      🔓 load_single_file(self, filepath) 🟡 C=8
         └─ Load data from a single .nid file....
      🔓 extract_dimensions_from_params(self, stm_nid) 🟡 C=10
         └─ Try to extract grid dimensions from .nid file parameters....

📥 DEPENDÊNCIAS:
  - NSFopen.read
  - base_loader
  - logging
  - models.spectral_data
  - models.topography_data
  - numpy
  - pandas
  - pathlib
  - typing

================================================================================
📦 MÓDULO: neaspec_snom_loader.py
================================================================================

Descrição:
  NeaSpec SNOM Data Loader
Loader for Scanning Near-field Optical Microscopy data from NeaSpec...

🏛️ CLASSES:

  class NeaSpecSNOMLoader
    Herda de: BaseDataLoader
    Doc: Loader for NeaSpec SNOM (Scanning Near-field Optical Microscopy) data.

This loa...
    
    Métodos (6):
      🔒 __init__(self) 🟢 C=1
         └─ Initialize NeaSpec SNOM loader....
      🔓 parse_header(self, lines) 🔴 C=14
         └─ Parse NeaSpec file header to extract metadata....
      🔓 parse_data_columns(self, header_line) 🟢 C=1
         └─ Parse column names from data header line....
      🔓 load_single_file(self, filepath) 🔴 C=18
         └─ Load SNOM data from a single text file....
      🔓 load_from_directory(self, directory) 🟡 C=7
         └─ Load SNOM data from directory....
      🔓 extract_all_harmonics(self, spectral_data) 🟢 C=3
         └─ Extract all harmonic channels as separate SpectralData objec...

📥 DEPENDÊNCIAS:
  - base_loader
  - logging
  - models.spectral_data
  - models.topography_data
  - numpy
  - pandas
  - pathlib
  - re
  - typing

================================================================================
📦 MÓDULO: spectral_data.py
================================================================================

Descrição:
  Spectral Data Model
Core data structure for hyperspectral data analysis...

🏛️ CLASSES:

  class SpectralMetadata
    Doc: Metadata for spectral datasets...
    
    Métodos (1):
      🔒 __post_init__(self) 🟢 C=2

  class SpectralData
    Doc: Core spectral data container with standardized structure.

The data is stored as...
    
    Métodos (11):
      🔒 __init__(self, data, metadata, topography) 🟢 C=1
         └─ Initialize SpectralData object....
      🔓 validate_data(data) 🟢 C=4
         └─ Validate data structure...
      🔓 correct_meander(self, force) 🟡 C=8
         └─ Correct meander scan pattern by reversing odd rows....
      🔓 to_3d_cube(self) 🟢 C=2
         └─ Reshape data to 3D cube (n_points, dim_v, dim_h)....
      🔓 apply_mask(self, mask) 🟢 C=5
         └─ Apply a 2D boolean mask to the spectral data....
      🔓 get_spectrum_at(self, row, col) 🟡 C=6
         └─ Get spectrum at specific grid position....
      🔓 truncate_range(self, min_val, max_val) 🟢 C=1
         └─ Truncate data to specified range of independent variable....
      🔓 save(self, filepath) 🟢 C=1
         └─ Save spectral data to CSV file...
      🔓 load(cls, filepath, metadata, topography) 🟢 C=1
         └─ Load spectral data from CSV file...
      🔓 copy(self) 🟢 C=1
         └─ Create a deep copy of the SpectralData object...
      🔒 __repr__(self) 🟢 C=1
    
    Propriedades (6):
      @property data
      @property independent_var
      @property independent_var_name
      @property spectra
      @property num_spectra
      @property num_points

📥 DEPENDÊNCIAS:
  - copy
  - dataclasses
  - logging
  - numpy
  - pandas
  - typing

================================================================================
📦 MÓDULO: topography_data.py
================================================================================

Descrição:
  Topography Data Model
Structure for handling topography/height data...

🏛️ CLASSES:

  class TopographyMetadata
    Doc: Metadata for topography data...
    
    Propriedades (1):
      @property pixel_size

  class TopographyData
    Doc: Container for topography/height data with discretization support....
    
    Métodos (14):
      🔒 __init__(self, data, metadata) 🟢 C=3
         └─ Initialize TopographyData object....
      🔓 normalize(self, vmin, vmax) 🟢 C=2
         └─ Normalize topography data to [0, 1] range....
      🔓 to_image(self, colormap) 🟢 C=2
         └─ Convert topography to PIL Image....
      🔓 discretize(self, block_v, block_h, resize_to_fit) 🟡 C=6
         └─ Discretize topography into blocks....
      🔓 get_selection_mask(self) 🟢 C=4
         └─ Get boolean mask for selected blocks....
      🔓 add_selected_block(self, block_i, block_j) 🟢 C=2
         └─ Add a block to selection...
      🔓 remove_selected_block(self, block_i, block_j) 🟢 C=2
         └─ Remove a block from selection...
      🔓 toggle_block_selection(self, block_i, block_j) 🟢 C=2
         └─ Toggle block selection state...
      🔓 clear_selection(self) 🟢 C=1
         └─ Clear all selected blocks...
      🔓 get_block_value(self, block_i, block_j) 🟢 C=4
         └─ Get average value of a discretized block...
      🔓 save(self, filepath, format) 🟢 C=3
         └─ Save topography data....
      🔓 load(cls, filepath) 🟢 C=3
         └─ Load topography from file....
      🔓 from_forward_backward(cls, forward, backward, flip_vertical) 🟢 C=2
         └─ Create topography from forward and backward scans....
      🔒 __repr__(self) 🟢 C=1
    
    Propriedades (3):
      @property shape
      @property height
      @property width

📥 DEPENDÊNCIAS:
  - PIL
  - dataclasses
  - logging
  - matplotlib.cm
  - numpy
  - typing

================================================================================
📦 MÓDULO: topography_widget.py
================================================================================

Descrição:
  Topography Widget - COM SELEÇÃO INTERATIVA AVANÇADA
Interactive widget for topography display and block selection...

🏛️ CLASSES:

  class TopographyWidget
    Herda de: QWidget
    Doc: Widget for displaying topography and allowing interactive block selection....
    
    Métodos (20):
      🔒 __init__(self, parent) 🟢 C=1
         └─ Initialize topography widget....
      🔓 setup_ui(self) 🟢 C=1
         └─ Setup the widget UI....
      🔓 set_topography(self, topography) 🟢 C=1
         └─ Set topography data to display....
      🔓 create_pixmap(self) 🟢 C=3
         └─ Create QPixmap from topography data with block overlay....
      🔓 create_block_overlay(self) 🟡 C=10
         └─ Create overlay showing discretized blocks and selection....
      🔓 on_mouse_press(self, event) 🟢 C=5
         └─ Handle mouse click for block selection....
      🔓 on_mouse_move(self, event) 🟢 C=5
         └─ Handle mouse movement for hover effects....
      🔓 on_mouse_leave(self, event) 🟢 C=1
         └─ Handle mouse leaving the widget....
      🔓 get_image_pos(self, widget_pos) 🟢 C=4
         └─ Convert widget position to image coordinates....
      🔓 get_block_at_pos(self, pos) 🟢 C=3
         └─ Get block indices at given position....
      🔓 toggle_block(self, block) 🟢 C=3
         └─ Toggle selection state of a block....
      🔓 toggle_select_mode(self) 🟢 C=2
         └─ Toggle selection mode on/off....
      🔓 clear_selection(self) 🟢 C=2
         └─ Clear all selected blocks....
      🔓 zoom_in(self) 🟢 C=1
         └─ Zoom in the display....
      🔓 zoom_out(self) 🟢 C=1
         └─ Zoom out the display....
      🔓 reset_view(self) 🟢 C=1
         └─ Reset view to fit window....
      🔓 update_display(self) 🟢 C=4
         └─ Update the display with current pixmap and scale....
      🔓 update_info(self) 🟢 C=3
         └─ Update information labels....
      🔓 set_colormap(self, colormap) 🟢 C=2
         └─ Change colormap for topography display....
      🔓 get_selected_blocks(self) 🟢 C=1
         └─ Get currently selected blocks....

📥 DEPENDÊNCIAS:
  - PySide6.QtCore
  - PySide6.QtGui
  - PySide6.QtWidgets
  - logging
  - models.topography_data
  - numpy
  - typing
