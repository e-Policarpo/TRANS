"""
Spectral Data Model
Core data structure for hyperspectral data analysis
"""

import numpy as np
import pandas as pd
from dataclasses import dataclass
from typing import Optional, Tuple, Dict, Any, List
import logging

logger = logging.getLogger(__name__)


@dataclass
class SpectralMetadata:
    """Metadata for spectral datasets"""
    source_type: str  # 'nanosurf_sts', 'neaspec_snom', etc.
    dimensions: Tuple[int, int]  # (horizontal, vertical)
    scan_mode: str  # 'meander', 'raster', etc.
    units: Dict[str, str]  # {'x': 'nm', 'y': 'nm', 'independent': 'V', 'dependent': 'A'}
    acquisition_date: Optional[str] = None
    additional_info: Dict[str, Any] = None
    
    def __post_init__(self):
        if self.additional_info is None:
            self.additional_info = {}


class SpectralData:
    """
    Core spectral data container with standardized structure.
    
    The data is stored as a pandas DataFrame where:
    - First column is the independent variable (e.g., voltage, wavenumber)
    - Subsequent columns are spectral data from different spatial positions
    - Column names encode spatial information
    """
    
    def __init__(self, 
                 data: pd.DataFrame,
                 metadata: SpectralMetadata,
                 topography: Optional[np.ndarray] = None):
        """
        Initialize SpectralData object.
        
        Parameters:
        -----------
        data : pd.DataFrame
            DataFrame with independent variable in first column
        metadata : SpectralMetadata
            Metadata about the spectral dataset
        topography : np.ndarray, optional
            Associated topography data
        """
        self.validate_data(data)
        self._data = data
        self.metadata = metadata
        self.topography = topography
        self._corrected_meander = False
        
    @staticmethod
    def validate_data(data: pd.DataFrame):
        """Validate data structure"""
        if not isinstance(data, pd.DataFrame):
            raise TypeError("Data must be a pandas DataFrame")
        
        if len(data.columns) < 2:
            raise ValueError("DataFrame must have at least 2 columns (independent var + 1 spectrum)")
            
        # First column should be numeric (independent variable)
        if not pd.api.types.is_numeric_dtype(data.iloc[:, 0]):
            raise ValueError("First column must be numeric (independent variable)")
    
    @property
    def data(self) -> pd.DataFrame:
        """Get the spectral data DataFrame"""
        return self._data
    
    @property
    def independent_var(self) -> np.ndarray:
        """Get the independent variable (first column)"""
        return self._data.iloc[:, 0].values
    
    @property
    def independent_var_name(self) -> str:
        """Get the name of the independent variable"""
        return self._data.columns[0]
    
    @property
    def spectra(self) -> pd.DataFrame:
        """Get all spectra (excluding independent variable)"""
        return self._data.iloc[:, 1:]
    
    @property
    def num_spectra(self) -> int:
        """Get number of spectra"""
        return len(self._data.columns) - 1
    
    @property
    def num_points(self) -> int:
        """Get number of points per spectrum"""
        return len(self._data)
    
    def correct_meander(self, force: bool = False) -> 'SpectralData':
        """
        Correct meander scan pattern by reversing odd rows.
        
        Parameters:
        -----------
        force : bool
            Force correction even if already corrected
            
        Returns:
        --------
        self : SpectralData
            Returns self for method chaining
        """
        if self._corrected_meander and not force:
            logger.info("Meander already corrected, skipping...")
            return self
        
        if self.metadata.scan_mode != 'meander':
            logger.warning(f"Scan mode is '{self.metadata.scan_mode}', not 'meander'. Skipping correction.")
            return self
        
        dim_h, dim_v = self.metadata.dimensions
        expected_spectra = dim_h * dim_v
        
        if self.num_spectra != expected_spectra:
            logger.warning(f"Number of spectra ({self.num_spectra}) doesn't match "
                          f"dimensions ({dim_h}x{dim_v}={expected_spectra})")
            
            # Try to adjust dimensions if possible
            if self.num_spectra < expected_spectra:
                dim_v = self.num_spectra // dim_h
                self.metadata.dimensions = (dim_h, dim_v)
                logger.info(f"Adjusted vertical dimension to {dim_v}")
        
        # Create new column order
        new_order = [self.independent_var_name]
        col_idx = 1
        
        for row in range(dim_v):
            row_cols = list(range(col_idx, col_idx + dim_h))
            if row % 2 == 1:  # Reverse odd rows
                row_cols = row_cols[::-1]
            new_order.extend([self._data.columns[i] for i in row_cols])
            col_idx += dim_h
        
        # Reorder columns
        self._data = self._data[new_order]
        self._corrected_meander = True
        
        logger.info("Meander correction applied successfully")
        return self
    
    def to_3d_cube(self) -> np.ndarray:
        """
        Reshape data to 3D cube (n_points, dim_v, dim_h).
        
        Returns:
        --------
        cube : np.ndarray
            3D array with shape (n_points, dim_v, dim_h)
        """
        dim_h, dim_v = self.metadata.dimensions
        n_pts = self.num_points
        
        # Get spectral data as numpy array
        spectra_array = self.spectra.values
        
        # Reshape to 3D
        try:
            cube = spectra_array.T.reshape(dim_v, dim_h, n_pts)
            cube = cube.transpose(2, 0, 1)  # (n_pts, dim_v, dim_h)
        except ValueError as e:
            logger.error(f"Cannot reshape data to cube: {e}")
            raise ValueError(f"Cannot reshape {spectra_array.shape} to "
                           f"({n_pts}, {dim_v}, {dim_h})")
        
        return cube
    
    def apply_mask(self, mask: np.ndarray) -> 'SpectralData':
        """
        Apply a 2D boolean mask to the spectral data.
        
        Parameters:
        -----------
        mask : np.ndarray
            2D boolean array with shape matching metadata.dimensions
            
        Returns:
        --------
        masked_data : SpectralData
            New SpectralData object with masked spectra
        """
        dim_h, dim_v = self.metadata.dimensions
        
        if mask.shape != (dim_v, dim_h):
            raise ValueError(f"Mask shape {mask.shape} doesn't match "
                           f"dimensions ({dim_v}, {dim_h})")
        
        # Flatten mask and select corresponding columns
        flat_mask = mask.flatten()
        
        # Keep independent variable and masked spectra
        selected_cols = [self.independent_var_name]
        spectrum_cols = list(self.spectra.columns)
        
        for i, keep in enumerate(flat_mask):
            if keep and i < len(spectrum_cols):
                selected_cols.append(spectrum_cols[i])
        
        masked_df = self._data[selected_cols].copy()
        
        # Update metadata
        new_metadata = SpectralMetadata(
            source_type=self.metadata.source_type,
            dimensions=(np.sum(mask), 1),  # Flattened dimensions
            scan_mode='masked',
            units=self.metadata.units.copy(),
            acquisition_date=self.metadata.acquisition_date,
            additional_info={'original_dimensions': self.metadata.dimensions,
                           'mask_applied': True}
        )
        
        return SpectralData(masked_df, new_metadata, self.topography)
    
    def get_spectrum_at(self, row: int, col: int) -> pd.Series:
        """
        Get spectrum at specific grid position.
        
        Parameters:
        -----------
        row : int
            Row index (0-based)
        col : int
            Column index (0-based)
            
        Returns:
        --------
        spectrum : pd.Series
            Spectrum at the specified position
        """
        dim_h, dim_v = self.metadata.dimensions
        
        if not (0 <= row < dim_v and 0 <= col < dim_h):
            raise IndexError(f"Position ({row}, {col}) out of bounds "
                           f"for dimensions ({dim_v}, {dim_h})")
        
        # Calculate linear index
        if self._corrected_meander or self.metadata.scan_mode != 'meander':
            idx = row * dim_h + col
        else:
            # Account for meander pattern if not corrected
            if row % 2 == 0:
                idx = row * dim_h + col
            else:
                idx = row * dim_h + (dim_h - 1 - col)
        
        # Return spectrum with independent variable as index
        spectrum_col = self.spectra.columns[idx]
        return pd.Series(self._data[spectrum_col].values, 
                        index=self.independent_var,
                        name=f"Spectrum_r{row}_c{col}")
    
    def truncate_range(self, min_val: float, max_val: float) -> 'SpectralData':
        """
        Truncate data to specified range of independent variable.
        
        Parameters:
        -----------
        min_val : float
            Minimum value of independent variable
        max_val : float
            Maximum value of independent variable
            
        Returns:
        --------
        truncated : SpectralData
            New SpectralData object with truncated range
        """
        mask = (self.independent_var >= min_val) & (self.independent_var <= max_val)
        truncated_df = self._data[mask].copy()
        truncated_df.reset_index(drop=True, inplace=True)
        
        # Update metadata
        new_metadata = SpectralMetadata(
            source_type=self.metadata.source_type,
            dimensions=self.metadata.dimensions,
            scan_mode=self.metadata.scan_mode,
            units=self.metadata.units.copy(),
            acquisition_date=self.metadata.acquisition_date,
            additional_info={**self.metadata.additional_info,
                           'truncated': True,
                           'truncation_range': (min_val, max_val)}
        )
        
        return SpectralData(truncated_df, new_metadata, self.topography)
    
    def save(self, filepath: str):
        """Save spectral data to CSV file"""
        self._data.to_csv(filepath, index=False)
        logger.info(f"Spectral data saved to {filepath}")
    
    @classmethod
    def load(cls, filepath: str, metadata: SpectralMetadata, 
             topography: Optional[np.ndarray] = None) -> 'SpectralData':
        """Load spectral data from CSV file"""
        data = pd.read_csv(filepath)
        return cls(data, metadata, topography)
    
    def copy(self) -> 'SpectralData':
        """Create a deep copy of the SpectralData object"""
        import copy
        return SpectralData(
            self._data.copy(),
            copy.deepcopy(self.metadata),
            self.topography.copy() if self.topography is not None else None
        )
    
    def __repr__(self) -> str:
        return (f"SpectralData(type='{self.metadata.source_type}', "
                f"dimensions={self.metadata.dimensions}, "
                f"spectra={self.num_spectra}, "
                f"points={self.num_points})")
