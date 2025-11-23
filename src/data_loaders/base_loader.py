"""
Base Data Loader
Abstract base class for all data loaders
"""

from abc import ABC, abstractmethod
from typing import Optional, List, Dict, Any, Tuple, Callable
from pathlib import Path
import logging
import pandas as pd
import numpy as np

from ..models.spectral_data import SpectralData, SpectralMetadata
from ..models.topography_data import TopographyData, TopographyMetadata

logger = logging.getLogger(__name__)

# Type alias for progress callback: (current, total, message) -> None
ProgressCallback = Optional[Callable[[int, int, str], None]]


class BaseDataLoader(ABC):
    """
    Abstract base class for hyperspectral data loaders.
    
    Each specific loader must implement the load_from_directory method
    to handle its specific file format and data structure.
    """
    
    def __init__(self):
        """Initialize base loader"""
        self.supported_extensions: List[str] = []
        self.loader_type: str = "base"
        self.last_loaded_path: Optional[Path] = None
        
    @abstractmethod
    def load_from_directory(self, directory: Path) -> Tuple[SpectralData, Optional[TopographyData]]:
        """
        Load data from a directory containing measurement files.
        
        Parameters:
        -----------
        directory : Path
            Directory containing data files
            
        Returns:
        --------
        spectral_data : SpectralData
            Loaded and processed spectral data
        topography : TopographyData or None
            Associated topography data if available
        """
        pass
    
    @abstractmethod
    def load_single_file(self, filepath: Path) -> SpectralData:
        """
        Load data from a single file.
        
        Parameters:
        -----------
        filepath : Path
            Path to data file
            
        Returns:
        --------
        spectral_data : SpectralData
            Loaded spectral data
        """
        pass
    
    def validate_directory(self, directory: Path) -> bool:
        """
        Validate that directory exists and contains supported files.
        
        Parameters:
        -----------
        directory : Path
            Directory to validate
            
        Returns:
        --------
        valid : bool
            True if directory is valid
        """
        if not directory.exists():
            logger.error(f"Directory does not exist: {directory}")
            return False
        
        if not directory.is_dir():
            logger.error(f"Path is not a directory: {directory}")
            return False
        
        # Check for supported files
        has_files = False
        for ext in self.supported_extensions:
            if list(directory.glob(f"*{ext}")):
                has_files = True
                break
        
        if not has_files:
            logger.warning(f"No supported files ({self.supported_extensions}) found in {directory}")
            return False
        
        return True
    
    def find_files(self, directory: Path, pattern: str = "*") -> List[Path]:
        """
        Find files matching pattern in directory.
        
        Parameters:
        -----------
        directory : Path
            Directory to search
        pattern : str
            Glob pattern for files
            
        Returns:
        --------
        files : List[Path]
            Sorted list of matching files
        """
        files = []
        for ext in self.supported_extensions:
            files.extend(directory.glob(f"{pattern}{ext}"))
        
        # Sort files for consistent ordering
        files = sorted(files, key=lambda x: x.name)
        
        logger.info(f"Found {len(files)} files matching pattern '{pattern}' in {directory}")
        return files
    
    def create_metadata(self, 
                       dimensions: Tuple[int, int],
                       scan_mode: str = "meander",
                       units: Optional[Dict[str, str]] = None,
                       **kwargs) -> SpectralMetadata:
        """
        Create metadata object with common parameters.
        
        Parameters:
        -----------
        dimensions : Tuple[int, int]
            (horizontal, vertical) dimensions
        scan_mode : str
            Scanning mode
        units : Dict[str, str]
            Units dictionary
        **kwargs : Any
            Additional metadata fields
            
        Returns:
        --------
        metadata : SpectralMetadata
            Metadata object
        """
        if units is None:
            units = {}
        
        return SpectralMetadata(
            source_type=self.loader_type,
            dimensions=dimensions,
            scan_mode=scan_mode,
            units=units,
            additional_info=kwargs
        )
    
    def concatenate_spectra(self, 
                           spectra_list: List[np.ndarray],
                           independent_var: np.ndarray,
                           column_names: Optional[List[str]] = None) -> pd.DataFrame:
        """
        Concatenate multiple spectra into a DataFrame.
        
        Parameters:
        -----------
        spectra_list : List[np.ndarray]
            List of 1D spectra arrays
        independent_var : np.ndarray
            Independent variable (e.g., voltage, wavenumber)
        column_names : List[str], optional
            Names for spectrum columns
            
        Returns:
        --------
        df : pd.DataFrame
            DataFrame with concatenated spectra
        """
        # Stack spectra
        if len(spectra_list) == 0:
            raise ValueError("No spectra to concatenate")
        
        # Ensure all spectra have same length
        spec_len = len(spectra_list[0])
        for i, spec in enumerate(spectra_list):
            if len(spec) != spec_len:
                logger.warning(f"Spectrum {i} has different length ({len(spec)} vs {spec_len})")
        
        # Create DataFrame
        data_array = np.column_stack(spectra_list)
        
        if column_names is None:
            column_names = [f"Spectrum_{i+1}" for i in range(len(spectra_list))]
        
        df = pd.DataFrame(data_array, columns=column_names)
        
        # Insert independent variable as first column
        df.insert(0, "Variable", independent_var)
        
        logger.info(f"Concatenated {len(spectra_list)} spectra into DataFrame")
        return df
    
    def apply_preprocessing(self, 
                           data: pd.DataFrame,
                           smooth: bool = False,
                           window_length: int = 11,
                           polyorder: int = 3) -> pd.DataFrame:
        """
        Apply common preprocessing steps to spectral data.
        
        Parameters:
        -----------
        data : pd.DataFrame
            Input data with spectra
        smooth : bool
            Whether to apply Savitzky-Golay smoothing
        window_length : int
            Window length for smoothing
        polyorder : int
            Polynomial order for smoothing
            
        Returns:
        --------
        processed : pd.DataFrame
            Processed data
        """
        processed = data.copy()
        
        if smooth:
            from scipy.signal import savgol_filter
            
            # Apply smoothing to each spectrum column (skip first column which is independent var)
            for col in processed.columns[1:]:
                processed[col] = savgol_filter(processed[col].values, 
                                              window_length=window_length,
                                              polyorder=polyorder)
            
            logger.info(f"Applied Savitzky-Golay smoothing (window={window_length}, order={polyorder})")
        
        return processed
    
    @staticmethod
    def detect_data_type(filepath: Path, sample_lines: int = 10) -> str:
        """
        Detect data type from filename and content.
        
        Parameters:
        -----------
        filepath : Path
            Path to data file
        sample_lines : int
            Number of lines to sample for content analysis
            
        Returns:
        --------
        data_type : str
            Detected data type: 'iv', 'didv', 'd2idv2', or 'unknown'
        """
        filename = filepath.name.lower()
        
        # Check filename patterns first (most reliable)
        if any(pattern in filename for pattern in ['iv', 'raw', 'current', 'concatenated']):
            return 'iv'
        elif any(pattern in filename for pattern in ['didv', 'first_derivative', 'primeira_derivada']):
            return 'didv'
        elif any(pattern in filename for pattern in ['d2idv2', 'second_derivative', 'segunda_derivada']):
            return 'd2idv2'
        
        # If filename doesn't help, analyze content
        try:
            df = pd.read_csv(filepath, nrows=sample_lines)
            
            # Check for required columns
            if 'V' not in df.columns:
                return 'unknown'
            
            # Get first data column (excluding V)
            data_columns = [col for col in df.columns if col != 'V']
            if not data_columns:
                return 'unknown'
            
            first_data_col = data_columns[0]
            data_values = df[first_data_col].values
            
            # Analyze data characteristics
            abs_mean = np.abs(data_values).mean()
            std_dev = np.std(data_values)
            
            # I-V data typically has larger absolute values and variation
            # Derivatives are smaller and more noisy
            if abs_mean > 1e-9 and std_dev > 1e-10:
                return 'iv'
            elif abs_mean < 1e-9 and std_dev < 1e-10:
                return 'didv'
            else:
                return 'unknown'
                
        except Exception as e:
            logger.warning(f"Could not detect data type for {filepath}: {e}")
            return 'unknown'

    @staticmethod
    def get_data_type_display_name(data_type: str) -> str:
        """Get display name for data type."""
        type_map = {
            'iv': 'I-V Curves',
            'didv': 'First Derivative (dI/dV)',
            'd2idv2': 'Second Derivative (d²I/dV²)',
            'unknown': 'Unknown Data Type'
        }
        return type_map.get(data_type, 'Unknown Data Type')
    
    def get_info(self) -> Dict[str, Any]:
        """
        Get information about the loader.
        
        Returns:
        --------
        info : Dict[str, Any]
            Loader information
        """
        return {
            'type': self.loader_type,
            'supported_extensions': self.supported_extensions,
            'last_loaded': str(self.last_loaded_path) if self.last_loaded_path else None
        }
    
    def __repr__(self) -> str:
        return (f"{self.__class__.__name__}(type='{self.loader_type}', "
                f"extensions={self.supported_extensions})")
