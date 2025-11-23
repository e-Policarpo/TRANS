"""
I-V Data Processor
Handles raw I-V curve processing and conversion to derivatives
"""

import numpy as np
import pandas as pd
from scipy.signal import savgol_filter
from typing import Optional, Tuple
import logging

from ..models.spectral_data import SpectralData, SpectralMetadata

logger = logging.getLogger(__name__)


class IVDataProcessor:
    """
    Processor for raw I-V data with derivative calculation.
    """
    
    def __init__(self, 
                 smooth_window: int = 11,
                 smooth_polyorder: int = 3):
        """
        Initialize I-V processor.
        
        Parameters:
        -----------
        smooth_window : int
            Window length for Savitzky-Golay smoothing
        smooth_polyorder : int
            Polynomial order for smoothing
        """
        self.smooth_window = smooth_window
        self.smooth_polyorder = smooth_polyorder
    
    def process_raw_iv_data(self, spectral_data: SpectralData) -> SpectralData:
        """
        Process raw I-V data with smoothing.
        
        Parameters:
        -----------
        spectral_data : SpectralData
            Raw I-V spectral data
            
        Returns:
        --------
        processed : SpectralData
            Smoothed I-V data
        """
        logger.info("Processing raw I-V data")
        
        # Get independent variable and spectra
        V = spectral_data.independent_var
        spectra = spectral_data.spectra.values
        
        # Apply smoothing
        smoothed_spectra = self._smooth_data(spectra)
        
        # Create DataFrame
        df_columns = [f"I_{col}" for col in spectral_data.spectra.columns]
        df = pd.DataFrame(smoothed_spectra, columns=df_columns)
        df.insert(0, spectral_data.independent_var_name, V)
        
        # Create metadata
        new_metadata = SpectralMetadata(
            source_type=spectral_data.metadata.source_type,
            dimensions=spectral_data.metadata.dimensions,
            scan_mode=spectral_data.metadata.scan_mode,
            units=spectral_data.metadata.units.copy(),
            acquisition_date=spectral_data.metadata.acquisition_date,
            additional_info={
                **spectral_data.metadata.additional_info,
                'data_type': 'iv_processed',
                'smoothed': True,
                'smooth_window': self.smooth_window,
                'smooth_polyorder': self.smooth_polyorder
            }
        )
        
        return SpectralData(df, new_metadata, spectral_data.topography)
    
    def calculate_derivatives_from_iv(self, 
                                    iv_data: SpectralData,
                                    smooth_before: bool = True,
                                    smooth_after: bool = True) -> Tuple[SpectralData, SpectralData]:
        """
        Calculate first and second derivatives from I-V data.
        
        Parameters:
        -----------
        iv_data : SpectralData
            Processed I-V data
        smooth_before : bool
            Apply smoothing before differentiation
        smooth_after : bool
            Apply smoothing after differentiation
            
        Returns:
        --------
        first_deriv : SpectralData
            First derivative (dI/dV)
        second_deriv : SpectralData
            Second derivative (d²I/dV²)
        """
        logger.info("Calculating derivatives from I-V data")
        
        # Get data
        V = iv_data.independent_var
        spectra = iv_data.spectra.values
        
        # Apply pre-smoothing if requested
        if smooth_before:
            spectra = self._smooth_data(spectra)
        
        # Calculate first derivative using central differences
        V_diff = np.diff(V)
        
        first_derivative = np.zeros_like(spectra)
        first_derivative[1:-1, :] = (spectra[2:, :] - spectra[:-2, :]) / \
                                  (V_diff[1:] + V_diff[:-1])[:, None]
        
        # Use forward/backward differences for endpoints
        first_derivative[0, :] = (spectra[1, :] - spectra[0, :]) / V_diff[0]
        first_derivative[-1, :] = (spectra[-1, :] - spectra[-2, :]) / V_diff[-1]
        
        # Apply post-smoothing if requested
        if smooth_after:
            first_derivative = self._smooth_data(first_derivative)
        
        # Calculate second derivative
        second_derivative = np.zeros_like(first_derivative)
        second_derivative[1:-1, :] = (first_derivative[2:, :] - first_derivative[:-2, :]) / \
                                   (V_diff[1:] + V_diff[:-1])[:, None]
        
        # Endpoints
        second_derivative[0, :] = (first_derivative[1, :] - first_derivative[0, :]) / V_diff[0]
        second_derivative[-1, :] = (first_derivative[-1, :] - first_derivative[-2, :]) / V_diff[-1]
        
        # Apply post-smoothing if requested
        if smooth_after:
            second_derivative = self._smooth_data(second_derivative)
        
        # Create DataFrames
        df_first = self._create_derivative_dataframe(first_derivative, V, iv_data, "dIdV")
        df_second = self._create_derivative_dataframe(second_derivative, V, iv_data, "d2IdV2")
        
        # Create metadata
        first_metadata = self._create_derivative_metadata(iv_data.metadata, 1, smooth_before, smooth_after)
        second_metadata = self._create_derivative_metadata(iv_data.metadata, 2, smooth_before, smooth_after)
        
        first_deriv = SpectralData(df_first, first_metadata, iv_data.topography)
        second_deriv = SpectralData(df_second, second_metadata, iv_data.topography)
        
        return first_deriv, second_deriv
    
    def _create_derivative_dataframe(self, derivative_data: np.ndarray, 
                                   V: np.ndarray, 
                                   original_data: SpectralData,
                                   prefix: str) -> pd.DataFrame:
        """Create DataFrame for derivative data."""
        df_columns = [f"{prefix}_{col}" for col in original_data.spectra.columns]
        df = pd.DataFrame(derivative_data, columns=df_columns)
        df.insert(0, original_data.independent_var_name, V)
        return df
    
    def _create_derivative_metadata(self, 
                                  original_metadata: SpectralMetadata,
                                  derivative_order: int,
                                  smooth_before: bool,
                                  smooth_after: bool) -> SpectralMetadata:
        """Create metadata for derivative data."""
        units = original_metadata.units.copy()
        if 'independent' in units and 'dependent' in units:
            dep_unit = units['dependent']
            ind_unit = units['independent']
            if derivative_order == 1:
                units['dependent'] = f"{dep_unit}/{ind_unit}"
            elif derivative_order == 2:
                units['dependent'] = f"{dep_unit}/{ind_unit}²"
        
        return SpectralMetadata(
            source_type=original_metadata.source_type,
            dimensions=original_metadata.dimensions,
            scan_mode=original_metadata.scan_mode,
            units=units,
            acquisition_date=original_metadata.acquisition_date,
            additional_info={
                **original_metadata.additional_info,
                'derivative_order': derivative_order,
                'smoothed_before': smooth_before,
                'smoothed_after': smooth_after,
                'data_type': f'derivative_{derivative_order}'
            }
        )
    
    def _smooth_data(self, data: np.ndarray) -> np.ndarray:
        """Apply Savitzky-Golay smoothing to data."""
        if data.shape[0] < self.smooth_window:
            logger.warning(f"Data length ({data.shape[0]}) < window ({self.smooth_window}), reducing window size")
            window = data.shape[0] if data.shape[0] % 2 == 1 else data.shape[0] - 1
        else:
            window = self.smooth_window
        
        smoothed = np.zeros_like(data)
        for i in range(data.shape[1]):
            smoothed[:, i] = savgol_filter(
                data[:, i],
                window_length=window,
                polyorder=min(self.smooth_polyorder, window - 1)
            )
        
        return smoothed