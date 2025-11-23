"""
Map Generation Module
Generates spatial maps from integrated spectral data
"""

import numpy as np
import pandas as pd
import logging
from typing import List, Tuple, Dict, Optional
from pathlib import Path
from PIL import Image
import tifffile

from ..models.spectral_data import SpectralData
from ..models.topography_data import TopographyData

logger = logging.getLogger(__name__)


class MapGenerator:
    """
    Generates spatial maps from integrated spectral data.
    """
    
    def __init__(self):
        self.intervals: List[Tuple[float, float]] = []
    
    def set_integration_intervals(self, intervals: List[Tuple[float, float]]):
        """Set integration intervals for map generation."""
        self.intervals = intervals
        logger.info(f"Set integration intervals: {intervals}")
    
    def integrate_over_intervals(self, spectral_data: SpectralData) -> Dict[str, np.ndarray]:
        """
        Integrate spectral data over specified intervals.
        
        Parameters:
        -----------
        spectral_data : SpectralData
            Spectral data to integrate
            
        Returns:
        --------
        integration_results : Dict[str, np.ndarray]
            Dictionary with integration results for each interval
        """
        if not self.intervals:
            raise ValueError("No integration intervals set")
        
        voltage_data = spectral_data.independent_var
        spectral_values = spectral_data.spectra.values
        
        results = {}
        
        for i, (start_v, end_v) in enumerate(self.intervals):
            # Create mask for integration interval
            voltage_mask = (voltage_data >= start_v) & (voltage_data <= end_v)
            
            if not np.any(voltage_mask):
                logger.warning(f"No data in interval [{start_v}, {end_v}]")
                continue
            
            # Extract data in interval
            interval_voltages = voltage_data[voltage_mask]
            interval_spectra = spectral_values[voltage_mask, :]
            
            # Integrate using trapezoidal rule
            integrated_values = np.trapz(interval_spectra, x=interval_voltages, axis=0)
            
            # Store results
            interval_key = f"{start_v:.3f}_{end_v:.3f}"
            results[interval_key] = integrated_values
        
        logger.info(f"Integrated over {len(results)} intervals")
        return results
    
    def create_spatial_map(self, 
                          integrated_data: np.ndarray,
                          dimensions: Tuple[int, int],
                          output_path: Path) -> np.ndarray:
        """
        Create spatial map from integrated data and save as image.
        
        CRITICAL: Input data is assumed to be ALREADY MEANDER-CORRECTED.
        The discretizer outputs blocks in H→V order (column-by-column).
        This method reshapes that 1D array back to 2D using Fortran order.
        
        Parameters:
        -----------
        integrated_data : np.ndarray
            Flattened integrated data (ALREADY meander-corrected)
        dimensions : Tuple[int, int]
            Spatial dimensions (width, height) = (num_groups_h, num_groups_v)
        output_path : Path
            Base path to save the map images (without extension)
            
        Returns:
        --------
        map_data : np.ndarray
            2D spatial map with shape (height, width)
        """
        width, height = dimensions  # width = num_groups_h, height = num_groups_v
        
        if len(integrated_data) != width * height:
            raise ValueError(f"Data length {len(integrated_data)} doesn't match "
                           f"dimensions {width}x{height}={width*height}")
        
        # Reshape using Fortran order (column-major) to match H→V discretization order
        # Block_0 is at (row=0, col=0), Block_1 at (row=1, col=0), etc.
        # This is equivalent to: reshape and then transpose
        map_data = integrated_data.reshape(height, width, order='F')
        
        # NO meander correction here - data is already corrected by discretizer!
        
        # Flip vertically for proper display orientation (origin at top-left)
        map_data = np.flipud(map_data)
        
        # CORREÇÃO: Garantir que output_path seja o caminho base sem extensão
        base_output_path = output_path.parent / output_path.stem
        
        # Save as image files
        self._save_map_as_image(map_data, base_output_path)
        
        # Also save numerical data as CSV for analysis
        csv_path = base_output_path.with_suffix('.csv')
        pd.DataFrame(map_data).to_csv(csv_path, index=False)
        
        logger.info(f"Map created with shape {map_data.shape} using Fortran order (H→V)")
        logger.info(f"Images saved with base name: {base_output_path}")
        logger.info(f"Numerical data saved to: {csv_path}")
        
        return map_data
    
    def _save_map_as_image(self, map_data: np.ndarray, output_path: Path):
        """
        Save map data as image file (TIFF and PNG).
        
        Parameters:
        -----------
        map_data : np.ndarray
            2D array with map data
        output_path : Path
            Base path for output files (without extension)
        """
        # Normalize data for visualization
        if np.ptp(map_data) > 0:
            normalized_map = 255 * (map_data - np.min(map_data)) / np.ptp(map_data)
        else:
            normalized_map = np.zeros_like(map_data)
        
        # Convert to 8-bit
        image_data = normalized_map.astype(np.uint8)
        
        # Save as TIFF (preserves data better)
        tiff_path = output_path.with_suffix('.tiff')
        tifffile.imwrite(str(tiff_path), image_data)
        
        # Save as PNG for quick viewing
        png_path = output_path.with_suffix('.png')
        image = Image.fromarray(image_data)
        image.save(png_path, 'PNG')
        
        # Save high-quality visualization with color map
        self._save_colormap_image(map_data, output_path)
    
    def _save_colormap_image(self, map_data: np.ndarray, output_path: Path):
        """
        Save map with color map for better visualization.
        
        Parameters:
        -----------
        map_data : np.ndarray
            2D array with map data
        output_path : Path
            Base path for output image (without extension)
        """
        try:
            import matplotlib.pyplot as plt
            
            # Create figure
            fig, ax = plt.subplots(figsize=(8, 6))
            
            # Create heatmap
            im = ax.imshow(map_data, cmap='viridis', aspect='auto')
            
            # Add colorbar
            plt.colorbar(im, ax=ax, label='Integrated Intensity')
            
            # Remove axes for cleaner look
            ax.set_xticks([])
            ax.set_yticks([])
            ax.set_title('Spatial Map - Integrated Spectral Data')
            
            # Save high quality image
            plt.tight_layout()
            
            # CORREÇÃO: Criar caminho correto para colormap
            colormap_path = output_path.with_name(f"{output_path.name}_colormap.png")
            plt.savefig(colormap_path, dpi=300, bbox_inches='tight', 
                       facecolor='white', transparent=False)
            plt.close(fig)
            
            logger.info(f"Colormap visualization saved to: {colormap_path}")
            
        except ImportError:
            logger.warning("Matplotlib not available, skipping colormap visualization")
        except Exception as e:
            logger.error(f"Error saving colormap image: {e}")
    
    
    def generate_maps_for_dataset(self,
                                 spectral_data: SpectralData,
                                 output_directory: Path,
                                 data_type: str = "unknown") -> Dict[str, np.ndarray]:
        """
        Generate maps for all integration intervals with specialized naming.
        """
        output_directory.mkdir(exist_ok=True)
        
        # Integrate over intervals
        integration_results = self.integrate_over_intervals(spectral_data)
        
        # Get spatial dimensions
        width, height = spectral_data.metadata.dimensions
        
        all_maps = {}
        
        for interval_key, integrated_values in integration_results.items():
            # Create map filename base with data type prefix
            if data_type == 'iv':
                map_basename = f"IV_map_{interval_key}"
            elif data_type == 'didv':
                map_basename = f"dIdV_map_{interval_key}"
            elif data_type == 'd2idv2':
                map_basename = f"d2IdV2_map_{interval_key}"
            else:
                map_basename = f"map_{interval_key}"
                
            map_path = output_directory / map_basename
            
            # Generate spatial map (will save TIFF, PNG, and CSV)
            map_data = self.create_spatial_map(
                integrated_values, 
                (width, height), 
                map_path
            )
            
            all_maps[interval_key] = map_data
            
            logger.info(f"Generated {data_type} map for interval {interval_key}")
        
        return all_maps
        
    def generate_topography_map(self,
                              topography_data: TopographyData,
                              output_directory: Path) -> Path:
        """
        Generate topography map image.
        
        Parameters:
        -----------
        topography_data : TopographyData
            Topography data to visualize
        output_directory : Path
            Directory to save the map
            
        Returns:
        --------
        image_path : Path
            Path to saved topography image
        """
        output_directory.mkdir(exist_ok=True)
        
        # Get topography array
        topo_array = topography_data.data
        
        # Create output path base (sem extensão)
        output_base = output_directory / "topography_map"
        
        # Normalize for visualization
        if np.ptp(topo_array) > 0:
            normalized_topo = 255 * (topo_array - np.min(topo_array)) / np.ptp(topo_array)
        else:
            normalized_topo = np.zeros_like(topo_array)
        
        # Convert to 8-bit and save
        image_data = normalized_topo.astype(np.uint8)
        
        # Save TIFF
        tiff_path = output_base.with_suffix('.tiff')
        tifffile.imwrite(str(tiff_path), image_data)
        
        # Save PNG
        png_path = output_base.with_suffix('.png')
        image = Image.fromarray(image_data)
        image.save(png_path, 'PNG')
        
        logger.info(f"Topography map saved to: {tiff_path}")
        
        return tiff_path