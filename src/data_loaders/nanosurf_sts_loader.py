"""
Nanosurf STS Data Loader
Loader for Scanning Tunneling Spectroscopy data from Nanosurf microscopes
"""

import numpy as np
import pandas as pd
from pathlib import Path
from typing import Optional, Tuple, List
import logging

from .base_loader import BaseDataLoader
from ..models.spectral_data import SpectralData, SpectralMetadata
from ..models.topography_data import TopographyData

try:
    from NSFopen.read import read as nid_read
    NSFOPEN_AVAILABLE = True
except ImportError:
    NSFOPEN_AVAILABLE = False
    logging.warning("NSFopen library not available. Install it to use Nanosurf loader.")

logger = logging.getLogger(__name__)


class NanosurfSTSLoader(BaseDataLoader):
    """
    Loader for Nanosurf STS (Scanning Tunneling Spectroscopy) data.
    
    This loader handles .nid files from Nanosurf STM systems and creates
    standardized SpectralData objects with proper meander correction.
    """
    
    def __init__(self, patch_nsfopen: bool = True):
        """
        Initialize Nanosurf STS loader.
        
        Parameters:
        -----------
        patch_nsfopen : bool
            Whether to apply patches for STM compatibility (no cantilever data)
        """
        super().__init__()
        self.supported_extensions = ['.nid']
        self.loader_type = 'nanosurf_sts'
        self.patch_nsfopen = patch_nsfopen
        
        if not NSFOPEN_AVAILABLE:
            raise ImportError("NSFopen library is required for Nanosurf loader")
        
        if self.patch_nsfopen:
            self._apply_nsfopen_patches()
    
    def _apply_nsfopen_patches(self):
        """Apply runtime patches to NSFopen for STM compatibility"""
        try:
            import NSFopen.read
            # Monkey-patch to ignore cantilever errors
            original_read = NSFopen.read.read.__init__
            
            def patched_init(self, *args, **kwargs):
                try:
                    original_read(self, *args, **kwargs)
                except KeyError as e:
                    if 'cantilever' in str(e).lower():
                        logger.debug("Ignoring cantilever-related error (STM mode)")
                    else:
                        raise
            
            NSFopen.read.read.__init__ = patched_init
            logger.debug("Applied NSFopen patches for STM compatibility")
        except Exception as e:
            logger.warning(f"Could not apply NSFopen patches: {e}")
    
    def load_from_directory(self, directory: Path, progress_callback=None) -> Tuple[SpectralData, Optional[TopographyData]]:
        """
        Load STS data from directory of .nid files.

        Parameters:
        -----------
        directory : Path
            Directory containing .nid files
        progress_callback : callable, optional
            Callback function(current, total, message) for progress updates

        Returns:
        --------
        spectral_data : SpectralData
            Concatenated spectral data from all files
        topography : TopographyData or None
            Average topography from first file
        """
        directory = Path(directory)
        
        if not self.validate_directory(directory):
            raise ValueError(f"Invalid directory: {directory}")
        
        # Find all .nid files
        nid_files = self.find_files(directory)
        
        if not nid_files:
            raise ValueError(f"No .nid files found in {directory}")
        
        logger.info(f"Loading {len(nid_files)} .nid files from {directory}")
        
        # Storage for concatenated data
        concatenated_spectra = []
        V_common = None
        topography = None
        dimensions = None
        
        # Process each file
        for i, filepath in enumerate(nid_files):
            try:
                # Update progress
                if progress_callback:
                    progress_callback(i, len(nid_files), f"Loading {filepath.name}")

                logger.debug(f"Processing file {i+1}/{len(nid_files)}: {filepath.name}")
                
                # Read .nid file
                stm_nid = nid_read(str(filepath))
                
                # Extract spectroscopy data
                if hasattr(stm_nid.data, 'Spec'):
                    # Forward and backward I-V curves
                    I_forward = np.array(stm_nid.data.Spec.Forward.get("Tip Current", 
                                                                      stm_nid.data.Spec.Forward.get("Current")))
                    I_backward = np.array(stm_nid.data.Spec.Backward.get("Tip Current",
                                                                        stm_nid.data.Spec.Backward.get("Current")))
                    
                    # Average forward and backward, then average over repetitions
                    I_mean_forward = np.mean(I_forward, axis=0)
                    I_mean_backward = np.mean(I_backward, axis=0)
                    I_mean = (I_mean_forward + I_mean_backward) / 2
                    
                    concatenated_spectra.append(I_mean)
                    
                    # Get voltage array from metadata
                    try:
                        V = np.array(stm_nid.data.Spec.Forward.get("Tip voltage",
                                                                  stm_nid.data.Spec.Forward.get("Voltage")))[0, :]
                    except (IndexError, TypeError, AttributeError) as e:
                        # Fallback: generate voltage array from metadata range
                        logger.warning(f"Could not extract voltage array directly, generating from metadata: {e}")
                        V = self._generate_voltage_array_from_metadata(stm_nid)

                    # Verify voltage consistency
                    if V_common is None:
                        V_common = V
                        logger.info(f"Voltage range: [{V_common.min():.3f}, {V_common.max():.3f}] V ({len(V_common)} points)")
                    elif not np.allclose(V_common, V, rtol=1e-5):
                        logger.warning(f"Voltage array in {filepath.name} differs from others")
                
                # Extract topography from first file
                if topography is None and hasattr(stm_nid.data, 'Image'):
                    try:
                        # Get forward and backward topography
                        z_forward = np.array(stm_nid.data.Image.Forward.get("Z-Axis",
                                                                           stm_nid.data.Image.Forward.get("Height")))
                        z_backward = np.array(stm_nid.data.Image.Backward.get("Z-Axis",
                                                                             stm_nid.data.Image.Backward.get("Height")))
                        
                        # Create topography object
                        topography = TopographyData.from_forward_backward(
                            z_forward, z_backward, flip_vertical=True
                        )
                        
                        # Get dimensions from topography
                        dimensions = (topography.width, topography.height)
                        
                        logger.info(f"Extracted topography with dimensions {dimensions}")
                    except Exception as e:
                        logger.warning(f"Could not extract topography: {e}")
                
            except Exception as e:
                logger.error(f"Error processing {filepath.name}: {e}")
                continue
        
        if not concatenated_spectra:
            raise ValueError("No spectral data could be extracted")
        
        # Infer dimensions if not from topography
        if dimensions is None:
            # Try to infer from number of spectra (assume square grid as fallback)
            n_spectra = len(concatenated_spectra)
            dim_guess = int(np.sqrt(n_spectra))
            if dim_guess * dim_guess == n_spectra:
                dimensions = (dim_guess, dim_guess)
                logger.info(f"Inferred square grid dimensions: {dimensions}")
            else:
                # Try common aspect ratios
                for aspect in [(2, 1), (3, 2), (4, 3), (5, 4)]:
                    for base in range(10, 100):
                        test_dims = (base * aspect[0], base * aspect[1])
                        if test_dims[0] * test_dims[1] == n_spectra:
                            dimensions = test_dims
                            logger.info(f"Inferred dimensions: {dimensions}")
                            break
                    if dimensions:
                        break
                
                if dimensions is None:
                    # Default to single row
                    dimensions = (n_spectra, 1)
                    logger.warning(f"Could not infer grid dimensions, using single row: {dimensions}")
        
        # Create DataFrame
        df = self.concatenate_spectra(
            concatenated_spectra,
            V_common,
            column_names=[f"Point_{i+1}" for i in range(len(concatenated_spectra))]
        )
        
        # Rename voltage column
        df = df.rename(columns={"Variable": "V"})
        
        # Create metadata
        metadata = self.create_metadata(
            dimensions=dimensions,
            scan_mode="meander",
            units={"independent": "V", "dependent": "A", "x": "nm", "y": "nm"},
            n_files=len(nid_files),
            source_directory=str(directory)
        )
        
        # Create SpectralData object
        spectral_data = SpectralData(df, metadata, topography.data if topography else None)
        
        # Apply meander correction
        if progress_callback:
            progress_callback(len(nid_files), len(nid_files), "Applying meander correction...")
        spectral_data.correct_meander()

        # Final progress update
        if progress_callback:
            progress_callback(len(nid_files), len(nid_files), "Complete!")

        self.last_loaded_path = directory
        logger.info(f"Successfully loaded STS data: {spectral_data}")

        return spectral_data, topography
    
    def load_single_file(self, filepath: Path) -> SpectralData:
        """
        Load data from a single .nid file.
        
        Parameters:
        -----------
        filepath : Path
            Path to .nid file
            
        Returns:
        --------
        spectral_data : SpectralData
            Spectral data from the file
        """
        filepath = Path(filepath)
        
        if not filepath.exists():
            raise FileNotFoundError(f"File not found: {filepath}")
        
        if filepath.suffix != '.nid':
            raise ValueError(f"Expected .nid file, got {filepath.suffix}")
        
        logger.info(f"Loading single file: {filepath}")
        
        # Read file
        stm_nid = nid_read(str(filepath))
        
        # Extract spectroscopy data
        if not hasattr(stm_nid.data, 'Spec'):
            raise ValueError(f"No spectroscopy data found in {filepath}")
        
        # Get I-V curves
        I_forward = np.array(stm_nid.data.Spec.Forward.get("Tip Current",
                                                          stm_nid.data.Spec.Forward.get("Current")))
        I_backward = np.array(stm_nid.data.Spec.Backward.get("Tip Current",
                                                            stm_nid.data.Spec.Backward.get("Current")))
        
        # Get voltage
        V = np.array(stm_nid.data.Spec.Forward.get("Tip voltage",
                                                  stm_nid.data.Spec.Forward.get("Voltage")))[0, :]
        
        # Process based on data shape
        if I_forward.ndim == 3:
            # Multiple spatial points
            n_points = I_forward.shape[0]
            spectra = []
            
            for i in range(n_points):
                I_mean_fw = np.mean(I_forward[i], axis=0)
                I_mean_bw = np.mean(I_backward[i], axis=0)
                I_mean = (I_mean_fw + I_mean_bw) / 2
                spectra.append(I_mean)
            
            # Create DataFrame
            df = self.concatenate_spectra(
                spectra, V,
                column_names=[f"Point_{i+1}" for i in range(n_points)]
            )
            
            # Guess dimensions
            dim_guess = int(np.sqrt(n_points))
            if dim_guess * dim_guess == n_points:
                dimensions = (dim_guess, dim_guess)
            else:
                dimensions = (n_points, 1)
        else:
            # Single point
            I_mean_fw = np.mean(I_forward, axis=0)
            I_mean_bw = np.mean(I_backward, axis=0)
            I_mean = (I_mean_fw + I_mean_bw) / 2
            
            df = pd.DataFrame({"V": V, "Current": I_mean})
            dimensions = (1, 1)
        
        # Rename voltage column if needed
        if "Variable" in df.columns:
            df = df.rename(columns={"Variable": "V"})
        
        # Create metadata
        metadata = self.create_metadata(
            dimensions=dimensions,
            scan_mode="single" if dimensions == (1, 1) else "meander",
            units={"independent": "V", "dependent": "A"},
            source_file=str(filepath)
        )
        
        # Create SpectralData
        spectral_data = SpectralData(df, metadata)
        
        self.last_loaded_path = filepath
        logger.info(f"Successfully loaded single file: {spectral_data}")
        
        return spectral_data
    
    def extract_dimensions_from_params(self, stm_nid) -> Optional[Tuple[int, int]]:
        """
        Try to extract grid dimensions from .nid file parameters.
        
        Parameters:
        -----------
        stm_nid : NSFopen object
            Loaded .nid file object
            
        Returns:
        --------
        dimensions : Tuple[int, int] or None
            (horizontal, vertical) dimensions if found
        """
        try:
            # Try different possible parameter locations
            if hasattr(stm_nid, 'param'):
                params = stm_nid.param
                
                # Look for grid dimensions
                for key in ['GridDim', 'GridSize', 'Dimension', 'Resolution']:
                    if key in params:
                        val = params[key]
                        if isinstance(val, (list, tuple)) and len(val) == 2:
                            return tuple(map(int, val))
                
                # Look for X and Y separately
                x_keys = ['GridDimX', 'GridSizeX', 'DimensionX', 'ResolutionX', 'PointsX']
                y_keys = ['GridDimY', 'GridSizeY', 'DimensionY', 'ResolutionY', 'PointsY']
                
                for x_key, y_key in zip(x_keys, y_keys):
                    if x_key in params and y_key in params:
                        return (int(params[x_key]), int(params[y_key]))
        
        except Exception as e:
            logger.debug(f"Could not extract dimensions from parameters: {e}")

        return None

    def _generate_voltage_array_from_metadata(self, stm_nid) -> np.ndarray:
        """
        Generate voltage array by arithmetic progression from metadata.

        This is a fallback method when the voltage array cannot be extracted directly.
        It generates a linearly spaced array based on V_min, V_max, and number of points.

        Parameters:
        -----------
        stm_nid : NSFopen object
            Loaded .nid file object

        Returns:
        --------
        V : np.ndarray
            Generated voltage array
        """
        try:
            # Try to get voltage range from Spec parameters
            if hasattr(stm_nid.data, 'Spec') and hasattr(stm_nid.data.Spec, 'Forward'):
                # Get current data to determine number of points
                I_data = np.array(stm_nid.data.Spec.Forward.get("Tip Current",
                                                                stm_nid.data.Spec.Forward.get("Current")))
                n_points = I_data.shape[-1]  # Last dimension is voltage points

                # Try to extract voltage range from parameters
                if hasattr(stm_nid, 'param'):
                    params = stm_nid.param

                    # Look for voltage range parameters
                    v_min = None
                    v_max = None

                    for min_key in ['V_min', 'Vmin', 'VoltageMin', 'StartVoltage', 'Spec_V_min']:
                        if min_key in params:
                            v_min = float(params[min_key])
                            break

                    for max_key in ['V_max', 'Vmax', 'VoltageMax', 'EndVoltage', 'Spec_V_max']:
                        if max_key in params:
                            v_max = float(params[max_key])
                            break

                    if v_min is not None and v_max is not None:
                        # Generate linearly spaced voltage array
                        V = np.linspace(v_min, v_max, n_points)
                        logger.info(f"Generated voltage array: [{v_min}, {v_max}] V ({n_points} points)")
                        return V

            # If all else fails, create a generic array
            logger.warning("Could not find voltage range in metadata, using generic array")
            return np.arange(n_points) if 'n_points' in locals() else np.arange(100)

        except Exception as e:
            logger.error(f"Error generating voltage array from metadata: {e}")
            # Last resort: return a generic array
            return np.arange(100)
