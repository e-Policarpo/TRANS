"""
Derivatives Processing Module
Handles calculation and correction of derivatives for spectral data
"""

import numpy as np
import pandas as pd
from scipy.signal import savgol_filter
from typing import Optional, Tuple
import logging

from ..models.spectral_data import SpectralData, SpectralMetadata

logger = logging.getLogger(__name__)


class DerivativesProcessor:
    """
    Processor for calculating and correcting spectral derivatives.
    
    Supports first and second derivatives with various correction methods
    including polynomial baseline correction.
    """
    
    def __init__(self, 
                 smooth_window: int = 11,
                 smooth_polyorder: int = 3):
        """
        Initialize derivatives processor.
        
        Parameters:
        -----------
        smooth_window : int
            Window length for Savitzky-Golay smoothing
        smooth_polyorder : int
            Polynomial order for smoothing
        """
        self.smooth_window = smooth_window
        self.smooth_polyorder = smooth_polyorder
        
    def calculate_first_derivative(self, 
                                  spectral_data: SpectralData,
                                  smooth_before: bool = True,
                                  smooth_after: bool = True) -> SpectralData:
        """
        Calculate first derivative (dI/dV or equivalent).
        
        Parameters:
        -----------
        spectral_data : SpectralData
            Input spectral data
        smooth_before : bool
            Apply smoothing before differentiation
        smooth_after : bool
            Apply smoothing after differentiation
            
        Returns:
        --------
        derivative : SpectralData
            First derivative data
        """
        logger.info("Calculating first derivative")
        
        # Get independent variable and spectra
        var = spectral_data.independent_var
        spectra = spectral_data.spectra.values
        
        # Apply pre-smoothing if requested
        if smooth_before:
            spectra = self._smooth_data(spectra)
        
        # Calculate derivative using central differences
        var_diff = np.diff(var)
        
        # Use central differences for interior points
        derivative = np.zeros_like(spectra)
        derivative[1:-1, :] = (spectra[2:, :] - spectra[:-2, :]) / \
                            (var_diff[1:] + var_diff[:-1])[:, None]
        
        # Use forward/backward differences for endpoints
        derivative[0, :] = (spectra[1, :] - spectra[0, :]) / var_diff[0]
        derivative[-1, :] = (spectra[-1, :] - spectra[-2, :]) / var_diff[-1]
        
        # Apply post-smoothing if requested
        if smooth_after:
            derivative = self._smooth_data(derivative)
        
        # Create DataFrame
        df_columns = [f"d{col}/d{spectral_data.independent_var_name}" 
                     for col in spectral_data.spectra.columns]
        df = pd.DataFrame(derivative, columns=df_columns)
        df.insert(0, spectral_data.independent_var_name, var)
        
        # Create metadata
        new_metadata = SpectralMetadata(
            source_type=spectral_data.metadata.source_type,
            dimensions=spectral_data.metadata.dimensions,
            scan_mode=spectral_data.metadata.scan_mode,
            units=spectral_data.metadata.units.copy(),
            acquisition_date=spectral_data.metadata.acquisition_date,
            additional_info={
                **spectral_data.metadata.additional_info,
                'derivative_order': 1,
                'smoothed_before': smooth_before,
                'smoothed_after': smooth_after
            }
        )
        
        # Update units for derivative
        if 'dependent' in new_metadata.units and 'independent' in new_metadata.units:
            dep_unit = new_metadata.units['dependent']
            ind_unit = new_metadata.units['independent']
            new_metadata.units['dependent'] = f"{dep_unit}/{ind_unit}"
        
        return SpectralData(df, new_metadata, spectral_data.topography)
    
    def calculate_second_derivative(self,
                                   spectral_data: SpectralData,
                                   from_first: Optional[SpectralData] = None,
                                   smooth_before: bool = True,
                                   smooth_after: bool = True) -> SpectralData:
        """
        Calculate second derivative (d²I/dV² or equivalent).
        
        Parameters:
        -----------
        spectral_data : SpectralData
            Original spectral data
        from_first : SpectralData, optional
            If provided, calculate from this first derivative
        smooth_before : bool
            Apply smoothing before differentiation
        smooth_after : bool
            Apply smoothing after differentiation
            
        Returns:
        --------
        derivative : SpectralData
            Second derivative data
        """
        logger.info("Calculating second derivative")
        
        # If first derivative provided, use it
        if from_first is not None:
            first_deriv = from_first
        else:
            # Calculate first derivative
            first_deriv = self.calculate_first_derivative(
                spectral_data, 
                smooth_before=smooth_before,
                smooth_after=False
            )
        
        # Get data
        var = first_deriv.independent_var
        first_deriv_data = first_deriv.spectra.values
        
        # Apply smoothing to first derivative if requested
        if smooth_before and from_first is None:
            first_deriv_data = self._smooth_data(first_deriv_data)
        
        # Calculate second derivative
        var_diff = np.diff(var)
        
        second_derivative = np.zeros_like(first_deriv_data)
        second_derivative[1:-1, :] = (first_deriv_data[2:, :] - first_deriv_data[:-2, :]) / \
                                    (var_diff[1:] + var_diff[:-1])[:, None]
        
        # Endpoints
        second_derivative[0, :] = (first_deriv_data[1, :] - first_deriv_data[0, :]) / var_diff[0]
        second_derivative[-1, :] = (first_deriv_data[-1, :] - first_deriv_data[-2, :]) / var_diff[-1]
        
        # Apply post-smoothing if requested
        if smooth_after:
            second_derivative = self._smooth_data(second_derivative)
        
        # Create DataFrame
        df_columns = [f"d²{col}/d{spectral_data.independent_var_name}²" 
                     for col in spectral_data.spectra.columns]
        df = pd.DataFrame(second_derivative, columns=df_columns)
        df.insert(0, spectral_data.independent_var_name, var)
        
        # Create metadata
        new_metadata = SpectralMetadata(
            source_type=spectral_data.metadata.source_type,
            dimensions=spectral_data.metadata.dimensions,
            scan_mode=spectral_data.metadata.scan_mode,
            units=spectral_data.metadata.units.copy(),
            acquisition_date=spectral_data.metadata.acquisition_date,
            additional_info={
                **spectral_data.metadata.additional_info,
                'derivative_order': 2,
                'smoothed_before': smooth_before,
                'smoothed_after': smooth_after
            }
        )
        
        # Update units
        if 'independent' in new_metadata.units:
            ind_unit = new_metadata.units['independent']
            if 'dependent' in spectral_data.metadata.units:
                dep_unit = spectral_data.metadata.units['dependent']
                new_metadata.units['dependent'] = f"{dep_unit}/{ind_unit}²"
        
        return SpectralData(df, new_metadata, spectral_data.topography)
    
    def polynomial_baseline_correction(self,
                                      spectral_data: SpectralData,
                                      poly_degree: int = 2) -> SpectralData:
        """
        Apply polynomial baseline correction to spectra.
        
        Parameters:
        -----------
        spectral_data : SpectralData
            Input spectral data
        poly_degree : int
            Degree of polynomial to fit and subtract
            
        Returns:
        --------
        corrected : SpectralData
            Baseline-corrected data
        """
        logger.info(f"Applying polynomial baseline correction (degree={poly_degree})")
        
        var = spectral_data.independent_var
        spectra = spectral_data.spectra
        
        corrected_data = []
        
        for col in spectra.columns:
            spectrum = spectra[col].values
            
            # Fit polynomial
            coeffs = np.polyfit(var, spectrum, poly_degree)
            baseline = np.polyval(coeffs, var)
            
            # Subtract baseline
            corrected = spectrum - baseline
            corrected_data.append(corrected)
        
        # Create DataFrame
        corrected_array = np.column_stack(corrected_data)
        df = pd.DataFrame(corrected_array, columns=spectra.columns)
        df.insert(0, spectral_data.independent_var_name, var)
        
        # Update metadata
        new_metadata = SpectralMetadata(
            source_type=spectral_data.metadata.source_type,
            dimensions=spectral_data.metadata.dimensions,
            scan_mode=spectral_data.metadata.scan_mode,
            units=spectral_data.metadata.units.copy(),
            acquisition_date=spectral_data.metadata.acquisition_date,
            additional_info={
                **spectral_data.metadata.additional_info,
                'baseline_corrected': True,
                'baseline_poly_degree': poly_degree
            }
        )
        
        return SpectralData(df, new_metadata, spectral_data.topography)
    
    def correct_derivatives_with_polynomials(self,
                                            first_deriv: SpectralData,
                                            second_deriv: SpectralData,
                                            first_poly_degree: int = 2,
                                            second_poly_degree: int = 4) -> Tuple[SpectralData, SpectralData]:
        """
        Apply polynomial baseline correction to both derivatives.
        
        This is commonly used to remove background trends in STS derivatives.
        
        Parameters:
        -----------
        first_deriv : SpectralData
            First derivative data
        second_deriv : SpectralData
            Second derivative data
        first_poly_degree : int
            Polynomial degree for first derivative correction
        second_poly_degree : int
            Polynomial degree for second derivative correction
            
        Returns:
        --------
        corrected : Tuple[SpectralData, SpectralData]
            Corrected first and second derivatives
        """
        logger.info("Correcting derivatives with polynomial baselines")
        
        # Correct first derivative
        first_corrected = self.polynomial_baseline_correction(
            first_deriv, 
            poly_degree=first_poly_degree
        )
        
        # Correct second derivative
        second_corrected = self.polynomial_baseline_correction(
            second_deriv,
            poly_degree=second_poly_degree
        )
        
        return first_corrected, second_corrected
    
    def _smooth_data(self, data: np.ndarray) -> np.ndarray:
        """
        Apply Savitzky-Golay smoothing to data.
        
        Parameters:
        -----------
        data : np.ndarray
            2D array with shape (n_points, n_spectra)
            
        Returns:
        --------
        smoothed : np.ndarray
            Smoothed data
        """
        if data.shape[0] < self.smooth_window:
            logger.warning(f"Data length ({data.shape[0]}) < window ({self.smooth_window}), "
                         "reducing window size")
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
    
    def calculate_derivatives_batch(self,
                                   spectral_data: SpectralData,
                                   calculate_second: bool = True,
                                   apply_correction: bool = True) -> dict:
        """
        Calculate and optionally correct both derivatives in one batch.
        
        Parameters:
        -----------
        spectral_data : SpectralData
            Input spectral data
        calculate_second : bool
            Whether to calculate second derivative
        apply_correction : bool
            Whether to apply polynomial correction
            
        Returns:
        --------
        results : dict
            Dictionary with 'first' and optionally 'second' derivatives
        """
        results = {}
        
        # Calculate first derivative
        first = self.calculate_first_derivative(spectral_data)
        results['first'] = first
        
        # Calculate second derivative if requested
        if calculate_second:
            second = self.calculate_second_derivative(spectral_data, from_first=first)
            results['second'] = second
        
        # Apply corrections if requested
        if apply_correction:
            if calculate_second:
                first_corr, second_corr = self.correct_derivatives_with_polynomials(
                    first, second
                )
                results['first_corrected'] = first_corr
                results['second_corrected'] = second_corr
            else:
                results['first_corrected'] = self.polynomial_baseline_correction(first)
        
        return results
