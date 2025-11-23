"""
NeaSpec SNOM Data Loader
Loader for Scanning Near-field Optical Microscopy data from NeaSpec
"""

import numpy as np
import pandas as pd
from pathlib import Path
from typing import Optional, Tuple, List, Dict
import logging
import re

from .base_loader import BaseDataLoader
from ..models.spectral_data import SpectralData, SpectralMetadata
from ..models.topography_data import TopographyData

logger = logging.getLogger(__name__)


class NeaSpecSNOMLoader(BaseDataLoader):
    """
    Loader for NeaSpec SNOM (Scanning Near-field Optical Microscopy) data.
    
    This loader handles text files with hyperspectral SNOM data, extracting
    multiple harmonic channels (O0A, O0P, O1A, etc.) as separate datasets.
    """
    
    def __init__(self):
        """Initialize NeaSpec SNOM loader."""
        super().__init__()
        self.supported_extensions = ['.txt', '.dat']
        self.loader_type = 'neaspec_snom'
        
    def parse_header(self, lines: List[str]) -> Dict[str, any]:
        """
        Parse NeaSpec file header to extract metadata.
        
        Parameters:
        -----------
        lines : List[str]
            Header lines from file
            
        Returns:
        --------
        metadata : Dict
            Parsed metadata
        """
        metadata = {
            'project': '',
            'description': '',
            'date': '',
            'scan_area': None,
            'pixel_area': None,
            'demodulation': 'Fourier',
            'parameters': {}
        }
        
        for line in lines:
            if line.startswith('#'):
                line = line.strip('# \n')
                
                # Skip www.neaspec.com header
                if 'neaspec.com' in line:
                    continue
                
                # Parse key-value pairs
                if ':' in line:
                    parts = line.split(':', 1)
                    if len(parts) == 2:
                        key = parts[0].strip()
                        values = parts[1].strip()
                        
                        # Parse specific fields
                        if 'Project' in key:
                            metadata['project'] = values
                        elif 'Description' in key:
                            metadata['description'] = values
                        elif 'Date' in key:
                            metadata['date'] = values
                        elif 'Scan Area' in key:
                            # Parse scan area: [µm] X Y Z
                            match = re.search(r'\[.*?\]\s*([\d.]+)\s+([\d.]+)\s+([\d.]+)', values)
                            if match:
                                metadata['scan_area'] = (float(match.group(1)), 
                                                        float(match.group(2)), 
                                                        float(match.group(3)))
                        elif 'Pixel Area' in key:
                            # Parse pixel area: [px] X Y Z
                            match = re.search(r'\[.*?\]\s*(\d+)\s+(\d+)\s+(\d+)', values)
                            if match:
                                metadata['pixel_area'] = (int(match.group(1)), 
                                                         int(match.group(2)), 
                                                         int(match.group(3)))
                        elif 'Demodulation Mode' in key:
                            metadata['demodulation'] = values
                        else:
                            # Store other parameters
                            metadata['parameters'][key] = values
        
        return metadata
    
    def parse_data_columns(self, header_line: str) -> List[str]:
        """
        Parse column names from data header line.
        
        Parameters:
        -----------
        header_line : str
            Line containing column headers
            
        Returns:
        --------
        columns : List[str]
            Column names
        """
        # Remove leading/trailing whitespace and split
        columns = header_line.strip().split('\t')
        return [col.strip() for col in columns]
    
    def load_single_file(self, filepath: Path) -> SpectralData:
        """
        Load SNOM data from a single text file.
        
        Parameters:
        -----------
        filepath : Path
            Path to text file
            
        Returns:
        --------
        spectral_data : SpectralData
            Loaded spectral data
        """
        filepath = Path(filepath)
        
        if not filepath.exists():
            raise FileNotFoundError(f"File not found: {filepath}")
        
        logger.info(f"Loading NeaSpec SNOM file: {filepath}")
        
        # Read file
        with open(filepath, 'r') as f:
            lines = f.readlines()
        
        # Separate header and data
        header_lines = []
        data_start_idx = 0
        column_line_idx = None
        
        for i, line in enumerate(lines):
            if line.startswith('#'):
                header_lines.append(line)
            elif not line.strip():
                continue
            else:
                # Check if this is the column header line
                if 'Row' in line and 'Column' in line and 'Wavenumber' in line:
                    column_line_idx = i
                    data_start_idx = i + 1
                    break
        
        if column_line_idx is None:
            raise ValueError("Could not find column header line in file")
        
        # Parse header
        metadata_dict = self.parse_header(header_lines)
        
        # Parse columns
        columns = self.parse_data_columns(lines[column_line_idx])
        
        # Read data
        data_lines = []
        for line in lines[data_start_idx:]:
            if line.strip() and not line.startswith('#'):
                data_lines.append(line.strip().split('\t'))
        
        # Convert to numpy array
        data_array = np.array(data_lines, dtype=float)
        
        # Create DataFrame
        df = pd.DataFrame(data_array, columns=columns)
        
        # Get dimensions from metadata
        if metadata_dict['pixel_area']:
            x_pixels, y_pixels, z_pixels = metadata_dict['pixel_area']
            dimensions = (x_pixels, y_pixels)
            n_wavenumbers = z_pixels
        else:
            # Try to infer from data
            unique_rows = len(df['Row'].unique())
            unique_cols = len(df['Column'].unique())
            dimensions = (unique_cols, unique_rows)
            n_wavenumbers = len(df['Wavenumber'].unique())
        
        logger.info(f"Grid dimensions: {dimensions}, Wavenumber points: {n_wavenumbers}")
        
        # Identify harmonic columns (O0A, O0P, O1A, etc.)
        harmonic_columns = [col for col in columns if re.match(r'O\d+[AP]', col)]
        
        if not harmonic_columns:
            raise ValueError("No harmonic columns (O0A, O0P, etc.) found in data")
        
        logger.info(f"Found harmonic channels: {harmonic_columns}")
        
        # Process first harmonic channel as main dataset
        # We'll restructure data to have wavenumber as independent variable
        # and spatial points as different spectra
        
        # Get unique positions
        positions = df[['Row', 'Column']].drop_duplicates().values
        n_positions = len(positions)
        
        # Get unique wavenumbers
        wavenumbers = df['Wavenumber'].unique()
        wavenumbers = np.sort(wavenumbers)
        
        # For each position, extract spectrum for first harmonic
        main_channel = harmonic_columns[0]  # Use first harmonic as main
        spectra_list = []
        column_names = []
        
        for i, (row, col) in enumerate(positions):
            # Get data for this position
            pos_data = df[(df['Row'] == row) & (df['Column'] == col)]
            
            # Sort by wavenumber
            pos_data = pos_data.sort_values('Wavenumber')
            
            # Extract spectrum
            spectrum = pos_data[main_channel].values
            
            if len(spectrum) != len(wavenumbers):
                logger.warning(f"Position ({row}, {col}) has {len(spectrum)} points, "
                             f"expected {len(wavenumbers)}")
                continue
            
            spectra_list.append(spectrum)
            column_names.append(f"r{int(row)}_c{int(col)}")
        
        # Create DataFrame for main channel
        spectral_df = self.concatenate_spectra(
            spectra_list,
            wavenumbers,
            column_names=column_names
        )
        
        # Rename independent variable
        spectral_df = spectral_df.rename(columns={"Variable": "Wavenumber"})
        
        # Create metadata
        metadata = self.create_metadata(
            dimensions=dimensions,
            scan_mode="raster",  # NeaSpec typically uses raster scanning
            units={"independent": "cm^-1", "dependent": "a.u.", 
                   "x": "µm", "y": "µm"},
            harmonics=harmonic_columns,
            main_channel=main_channel,
            source_file=str(filepath),
            **metadata_dict
        )
        
        # Create SpectralData
        spectral_data = SpectralData(spectral_df, metadata)
        
        # Store additional harmonic channels in metadata
        additional_channels = {}
        for channel in harmonic_columns[1:]:
            channel_spectra = []
            for row, col in positions:
                pos_data = df[(df['Row'] == row) & (df['Column'] == col)]
                pos_data = pos_data.sort_values('Wavenumber')
                channel_spectra.append(pos_data[channel].values)
            
            channel_df = self.concatenate_spectra(
                channel_spectra,
                wavenumbers,
                column_names=column_names
            )
            channel_df = channel_df.rename(columns={"Variable": "Wavenumber"})
            additional_channels[channel] = channel_df
        
        spectral_data.metadata.additional_info['harmonic_channels'] = additional_channels
        
        self.last_loaded_path = filepath
        logger.info(f"Successfully loaded NeaSpec SNOM data: {spectral_data}")
        
        return spectral_data
    
    def load_from_directory(self, directory: Path, progress_callback=None) -> Tuple[SpectralData, Optional[TopographyData]]:
        """
        Load SNOM data from directory.

        For NeaSpec SNOM, typically there's one file per measurement,
        so this method just loads the first suitable file found.

        Parameters:
        -----------
        directory : Path
            Directory containing data files
        progress_callback : callable, optional
            Callback function(current, total, message) for progress updates

        Returns:
        --------
        spectral_data : SpectralData
            Loaded spectral data
        topography : None
            NeaSpec SNOM files don't typically include topography
        """
        directory = Path(directory)
        
        if not self.validate_directory(directory):
            raise ValueError(f"Invalid directory: {directory}")
        
        # Find suitable files
        data_files = self.find_files(directory)
        
        if not data_files:
            raise ValueError(f"No suitable files found in {directory}")
        
        # Filter for NeaSpec files (contain header marker)
        neaspec_files = []
        for filepath in data_files:
            try:
                with open(filepath, 'r') as f:
                    first_line = f.readline()
                    if 'neaspec' in first_line.lower():
                        neaspec_files.append(filepath)
            except Exception:
                continue
        
        if not neaspec_files:
            logger.warning("No NeaSpec formatted files found, trying first file")
            neaspec_files = [data_files[0]]

        # Update progress
        if progress_callback:
            progress_callback(0, 1, f"Loading {neaspec_files[0].name}")

        # Load first file
        spectral_data = self.load_single_file(neaspec_files[0])

        # Final progress update
        if progress_callback:
            progress_callback(1, 1, "Complete!")

        # No topography data in NeaSpec files
        topography = None

        return spectral_data, topography
    
    def extract_all_harmonics(self, spectral_data: SpectralData) -> Dict[str, SpectralData]:
        """
        Extract all harmonic channels as separate SpectralData objects.
        
        Parameters:
        -----------
        spectral_data : SpectralData
            Loaded SNOM data with harmonics in metadata
            
        Returns:
        --------
        harmonics : Dict[str, SpectralData]
            Dictionary mapping channel names to SpectralData objects
        """
        harmonics = {}
        
        # Add main channel
        main_channel = spectral_data.metadata.additional_info.get('main_channel', 'main')
        harmonics[main_channel] = spectral_data
        
        # Extract additional channels
        if 'harmonic_channels' in spectral_data.metadata.additional_info:
            for channel_name, channel_df in spectral_data.metadata.additional_info['harmonic_channels'].items():
                # Create new metadata for this channel
                channel_metadata = SpectralMetadata(
                    source_type=spectral_data.metadata.source_type,
                    dimensions=spectral_data.metadata.dimensions,
                    scan_mode=spectral_data.metadata.scan_mode,
                    units=spectral_data.metadata.units.copy(),
                    acquisition_date=spectral_data.metadata.acquisition_date,
                    additional_info={'channel': channel_name}
                )
                
                # Create SpectralData for this channel
                channel_data = SpectralData(channel_df, channel_metadata, 
                                           spectral_data.topography)
                harmonics[channel_name] = channel_data
        
        return harmonics
