"""
Integration Processing Module
Handles integration of spectral data over specified intervals
"""

import numpy as np
import logging
from typing import List, Tuple, Dict

from ..models.spectral_data import SpectralData

logger = logging.getLogger(__name__)


class IntegrationProcessor:
    """
    Processes spectral data integration over voltage intervals.
    """
    
    def __init__(self):
        self.intervals: List[Tuple[float, float]] = []
    
    def set_intervals(self, intervals: List[Tuple[float, float]]):
        """Set integration intervals."""
        self.intervals = intervals
    
    def integrate_spectral_data(self, spectral_data: SpectralData) -> Dict[str, np.ndarray]:
        """
        Integrate spectral data over all configured intervals.
        
        Parameters:
        -----------
        spectral_data : SpectralData
            Spectral data to integrate
            
        Returns:
        --------
        results : Dict[str, np.ndarray]
            Integration results for each interval
        """
        voltage = spectral_data.independent_var
        spectra = spectral_data.spectra.values
        
        results = {}
        
        for start_v, end_v in self.intervals:
            # Create mask for interval
            mask = (voltage >= start_v) & (voltage <= end_v)
            
            if not np.any(mask):
                logger.warning(f"No data in interval [{start_v}, {end_v}]")
                continue
            
            # Extract data in interval
            interval_voltage = voltage[mask]
            interval_spectra = spectra[mask, :]
            
            # Perform integration
            integrated = np.trapz(interval_spectra, x=interval_voltage, axis=0)
            
            # Store result
            interval_key = f"{start_v:.3f}_{end_v:.3f}"
            results[interval_key] = integrated
        
        logger.info(f"Integrated over {len(results)} intervals")
        return results