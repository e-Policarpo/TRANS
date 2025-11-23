"""
Discretization Module
Handles spatial discretization of hyperspectral data with block averaging
"""

import numpy as np
import pandas as pd
from typing import Optional, Tuple, List, Dict
import logging
import math

from ..models.spectral_data import SpectralData, SpectralMetadata
from ..models.topography_data import TopographyData

logger = logging.getLogger(__name__)


class Discretizer:
    """
    Handles discretization of hyperspectral data into blocks.
    
    This module correctly handles edge cases and border blocks,
    fixing the bug in the original implementation.
    """
    
    def __init__(self):
        """Initialize discretizer."""
        self.last_stats: Dict = {}
        
    def discretize_spectral_data(self,
                                spectral_data: SpectralData,
                                block_h: int,
                                block_v: int,
                                topography: Optional[TopographyData] = None,
                                selected_blocks: Optional[List[Tuple[int, int]]] = None,
                                ignore_empty_blocks: bool = True,
                                data_type: str = 'unknown',
                                use_two_stage_averaging: bool = True) -> Dict[str, SpectralData]:
        """
        Discretize spectral data into blocks with proper edge handling.
        
        Parameters:
        -----------
        spectral_data : SpectralData
            Input spectral data
        block_h : int
            Horizontal block size
        block_v : int
            Vertical block size
        topography : TopographyData, optional
            Topography for selection mask
        selected_blocks : List[Tuple[int, int]], optional
            List of (i, j) block indices to include
        ignore_empty_blocks : bool
            Whether to skip blocks with all NaN values
        data_type : str
            Type of data for specialized naming: 'iv', 'didv', 'd2idv2', 'unknown'
        use_two_stage_averaging : bool
            If True, uses two-stage averaging (horizontal then vertical) like original TRANS.
            This ensures exact numerical match with original implementation.
            
        Returns:
        --------
        results : Dict[str, SpectralData]
            Dictionary with 'intermediate' and 'final' discretized data
        """
        logger.info(f"Starting discretization with blocks {block_h}x{block_v}, data type: {data_type}")
        
        # Get dimensions
        dim_h, dim_v = spectral_data.metadata.dimensions
        n_pts = spectral_data.num_points
        
        # Convert to 3D cube for easier processing
        try:
            cube = spectral_data.to_3d_cube()
        except ValueError as e:
            logger.error(f"Cannot create 3D cube: {e}")
            raise
        
        # Apply selection mask if provided
        if selected_blocks is not None and topography is not None:
            mask = self._create_selection_mask(dim_h, dim_v, block_h, block_v, 
                                              selected_blocks)
            # Apply mask (set unselected to NaN)
            for i in range(n_pts):
                cube[i, ~mask] = np.nan
        elif selected_blocks is not None:
            logger.warning("Selected blocks provided but no topography for mask creation")
        
        # Calculate number of block groups (with proper ceiling division)
        num_groups_h = math.ceil(dim_h / block_h)
        num_groups_v = math.ceil(dim_v / block_v)
        
        logger.info(f"Grid: {dim_h}x{dim_v} → {num_groups_h}x{num_groups_v} blocks")
        
        # Stage 1: Horizontal averaging (within rows)
        intermediate_data = self._horizontal_averaging(
            cube, dim_h, dim_v, block_h, num_groups_h, 
            spectral_data.independent_var_name,
            ignore_empty_blocks,
            data_type
        )
        
        # Stage 2: Vertical averaging (across rows within blocks)
        if use_two_stage_averaging:
            # Use two-stage approach like original TRANS for exact match
            final_data = self._vertical_averaging_two_stage(
                cube, dim_h, dim_v, block_h, block_v, 
                num_groups_h, num_groups_v,
                spectral_data.independent_var_name,
                spectral_data.independent_var,
                ignore_empty_blocks,
                data_type
            )
        else:
            # Direct averaging over both dimensions
            final_data = self._vertical_averaging(
                cube, dim_h, dim_v, block_h, block_v, 
                num_groups_h, num_groups_v,
                spectral_data.independent_var_name,
                ignore_empty_blocks,
                data_type
            )
        
        # Create metadata for results
        intermediate_metadata = self._create_discretized_metadata(
            spectral_data.metadata,
            stage='intermediate',
            block_size=(block_h, 1),
            num_blocks=len(intermediate_data.columns) - 1,
            data_type=data_type
        )
        
        final_metadata = self._create_discretized_metadata(
            spectral_data.metadata,
            stage='final',
            block_size=(block_h, block_v),
            num_blocks=len(final_data.columns) - 1,
            data_type=data_type
        )
        
        # Create SpectralData objects
        results = {
            'intermediate': SpectralData(intermediate_data, intermediate_metadata),
            'final': SpectralData(final_data, final_metadata)
        }
        
        # Store statistics
        self.last_stats = {
            'original_dimensions': (dim_h, dim_v),
            'block_size': (block_h, block_v),
            'num_groups': (num_groups_h, num_groups_v),
            'intermediate_columns': len(intermediate_data.columns) - 1,
            'final_columns': len(final_data.columns) - 1,
            'selected_blocks': selected_blocks,
            'ignore_empty': ignore_empty_blocks,
            'data_type': data_type
        }
        
        logger.info(f"Discretization complete: {self.last_stats['final_columns']} final blocks")
        
        return results
    
    def _horizontal_averaging(self,
                            cube: np.ndarray,
                            dim_h: int,
                            dim_v: int,
                            block_h: int,
                            num_groups_h: int,
                            var_name: str,
                            ignore_empty: bool,
                            data_type: str = 'unknown') -> pd.DataFrame:
        """
        Perform horizontal averaging stage.
        
        Parameters:
        -----------
        cube : np.ndarray
            3D data cube (n_pts, dim_v, dim_h)
        dim_h : int
            Horizontal dimension
        dim_v : int
            Vertical dimension
        block_h : int
            Horizontal block size
        num_groups_h : int
            Number of horizontal groups
        var_name : str
            Independent variable name
        ignore_empty : bool
            Whether to skip empty blocks
        data_type : str
            Type of data for specialized naming
            
        Returns:
        --------
        df : pd.DataFrame
            Intermediate discretized data
        """
        n_pts = cube.shape[0]
        columns = []
        data_list = []
        skipped_h = 0
        
        for row in range(dim_v):
            for g in range(num_groups_h):
                # Calculate column range with proper edge handling
                col_start = g * block_h
                col_end = min((g + 1) * block_h, dim_h)
                
                # Extract and average block
                block_data = cube[:, row, col_start:col_end]
                
                # Check if block is empty
                if ignore_empty and np.all(np.isnan(block_data)):
                    skipped_h += 1
                    continue
                
                # Average across columns
                avg_spectrum = np.nanmean(block_data, axis=1)
                
                data_list.append(avg_spectrum)
                
                # SPECIALIZED NAMING BASED ON DATA TYPE
                if data_type == 'iv':
                    columns.append(f"I_Row{row}_HGroup{g}")
                elif data_type == 'didv':
                    columns.append(f"dIdV_Row{row}_HGroup{g}")
                elif data_type == 'd2idv2':
                    columns.append(f"d2IdV2_Row{row}_HGroup{g}")
                else:
                    columns.append(f"Row{row}_HGroup{g}")
        
        # Create DataFrame
        if not data_list:
            logger.warning("No data after horizontal averaging")
            return pd.DataFrame({var_name: cube[:, 0, 0]})  # Return minimal DataFrame
        
        data_array = np.column_stack(data_list)
        df = pd.DataFrame(data_array, columns=columns)
        
        # Add independent variable
        df.insert(0, var_name, np.arange(n_pts))  # Will be replaced with actual values
        
        logger.debug(f"Horizontal averaging: {len(data_list)} columns generated, {skipped_h} skipped")
        
        return df
    
    def _vertical_averaging(self,
                          cube: np.ndarray,
                          dim_h: int,
                          dim_v: int,
                          block_h: int,
                          block_v: int,
                          num_groups_h: int,
                          num_groups_v: int,
                          var_name: str,
                          ignore_empty: bool,
                          data_type: str = 'unknown') -> pd.DataFrame:
        """
        Perform vertical averaging stage to create final blocks.
        
        Parameters:
        -----------
        cube : np.ndarray
            3D data cube (n_pts, dim_v, dim_h)
        dim_h : int
            Horizontal dimension
        dim_v : int
            Vertical dimension
        block_h : int
            Horizontal block size
        block_v : int
            Vertical block size
        num_groups_h : int
            Number of horizontal groups
        num_groups_v : int
            Number of vertical groups
        var_name : str
            Independent variable name
        ignore_empty : bool
            Whether to skip empty blocks
        data_type : str
            Type of data for specialized naming
            
        Returns:
        --------
        df : pd.DataFrame
            Final discretized data
        """
        n_pts = cube.shape[0]
        columns = []
        data_list = []
        block_idx = 0
        skipped_v = 0
        
        # Process each block with proper edge handling
        # CRITICAL: Order matches original TRANS - horizontal groups first, then vertical
        # This ensures blocks are numbered column-by-column (not row-by-row)
        for i in range(num_groups_h):
            for j in range(num_groups_v):
                # Calculate row range
                row_start = j * block_v
                row_end = min((j + 1) * block_v, dim_v)
                
                # Calculate column range
                col_start = i * block_h
                col_end = min((i + 1) * block_h, dim_h)
                
                # Extract block (handling edges properly)
                block_data = cube[:, row_start:row_end, col_start:col_end]
                
                # Check if block is empty
                if ignore_empty and np.all(np.isnan(block_data)):
                    skipped_v += 1
                    continue
                
                # Average across spatial dimensions
                avg_spectrum = np.nanmean(block_data.reshape(n_pts, -1), axis=1)
                
                data_list.append(avg_spectrum)
                
                # SPECIALIZED NAMING BASED ON DATA TYPE
                if data_type == 'iv':
                    columns.append(f"I_Block_{block_idx}")
                elif data_type == 'didv':
                    columns.append(f"dIdV_Block_{block_idx}")
                elif data_type == 'd2idv2':
                    columns.append(f"d2IdV2_Block_{block_idx}")
                else:
                    columns.append(f"Block_{block_idx}")
                    
                block_idx += 1
        
        # Create DataFrame
        if not data_list:
            logger.warning("No data after vertical averaging")
            return pd.DataFrame({var_name: cube[:, 0, 0]})
        
        data_array = np.column_stack(data_list)
        df = pd.DataFrame(data_array, columns=columns)
        
        # Add independent variable
        df.insert(0, var_name, np.arange(n_pts))
        
        logger.debug(f"Vertical averaging: {len(data_list)} blocks generated, {skipped_v} skipped")
        
        return df
    
    def _vertical_averaging_two_stage(self,
                                     cube: np.ndarray,
                                     dim_h: int,
                                     dim_v: int,
                                     block_h: int,
                                     block_v: int,
                                     num_groups_h: int,
                                     num_groups_v: int,
                                     var_name: str,
                                     var_values: np.ndarray,
                                     ignore_empty: bool,
                                     data_type: str = 'unknown') -> pd.DataFrame:
        """
        Two-stage vertical averaging matching original TRANS implementation.
        First computes horizontal averages, then uses those for vertical averaging.
        
        Parameters:
        -----------
        cube : np.ndarray
            3D data cube (n_pts, dim_v, dim_h)
        dim_h : int
            Horizontal dimension
        dim_v : int
            Vertical dimension
        block_h : int
            Horizontal block size
        block_v : int
            Vertical block size
        num_groups_h : int
            Number of horizontal groups
        num_groups_v : int
            Number of vertical groups
        var_name : str
            Independent variable name
        var_values : np.ndarray
            Independent variable values
        ignore_empty : bool
            Whether to skip empty blocks
        data_type : str
            Type of data for specialized naming
            
        Returns:
        --------
        df : pd.DataFrame
            Final discretized data
        """
        n_pts = cube.shape[0]
        
        # Stage 1: Compute horizontal averages for all scan lines
        # This creates h_avg with shape (n_pts, dim_v, num_groups_h)
        h_avg = np.full((n_pts, dim_v, num_groups_h), np.nan, dtype=float)
        
        for g in range(num_groups_h):
            col_start = g * block_h
            col_end = min((g + 1) * block_h, dim_h)
            h_avg[:, :, g] = np.nanmean(cube[:, :, col_start:col_end], axis=2)
        
        # Stage 2: Vertical averaging using intermediate results
        # Order: horizontal groups first, then vertical groups (matches original)
        columns = []
        data_list = []
        block_idx = 0
        skipped_v = 0
        
        for g in range(num_groups_h):
            for j in range(num_groups_v):
                row_start = j * block_v
                row_end = min((j + 1) * block_v, dim_v)
                
                # Extract slice from horizontally-averaged data
                slice_data = h_avg[:, row_start:row_end, g]  # Shape: (n_pts, row_height)
                
                # Check if block is empty
                if ignore_empty and np.all(np.isnan(slice_data)):
                    skipped_v += 1
                    continue
                
                # Average across rows (vertical dimension)
                avg_spectrum = np.nanmean(slice_data, axis=1)
                
                data_list.append(avg_spectrum)
                
                # SPECIALIZED NAMING BASED ON DATA TYPE
                if data_type == 'iv':
                    columns.append(f"I_Block_{block_idx}")
                elif data_type == 'didv':
                    columns.append(f"dIdV_Block_{block_idx}")
                elif data_type == 'd2idv2':
                    columns.append(f"d2IdV2_Block_{block_idx}")
                else:
                    columns.append(f"Block_{block_idx}")
                    
                block_idx += 1
        
        # Create DataFrame
        if not data_list:
            logger.warning("No data after two-stage vertical averaging")
            return pd.DataFrame({var_name: var_values})
        
        data_array = np.column_stack(data_list)
        df = pd.DataFrame(data_array, columns=columns)
        
        # Add independent variable with actual values
        df.insert(0, var_name, var_values)
        
        logger.debug(f"Two-stage vertical averaging: {len(data_list)} blocks generated, {skipped_v} skipped")
        
        return df
    
    def _create_selection_mask(self,
                              dim_h: int,
                              dim_v: int,
                              block_h: int,
                              block_v: int,
                              selected_blocks: List[Tuple[int, int]]) -> np.ndarray:
        """
        Create 2D boolean mask from selected blocks.
        
        Parameters:
        -----------
        dim_h : int
            Horizontal dimension
        dim_v : int
            Vertical dimension
        block_h : int
            Horizontal block size
        block_v : int
            Vertical block size
        selected_blocks : List[Tuple[int, int]]
            List of (row, col) block indices
            
        Returns:
        --------
        mask : np.ndarray
            2D boolean mask
        """
        mask = np.zeros((dim_v, dim_h), dtype=bool)
        
        for block_row, block_col in selected_blocks:
            # Calculate actual pixel ranges with edge handling
            row_start = block_row * block_v
            row_end = min((block_row + 1) * block_v, dim_v)
            col_start = block_col * block_h
            col_end = min((block_col + 1) * block_h, dim_h)
            
            # Set mask
            mask[row_start:row_end, col_start:col_end] = True
        
        logger.debug(f"Created selection mask with {len(selected_blocks)} blocks")
        
        return mask
    
    def _create_discretized_metadata(self,
                                    original_metadata: SpectralMetadata,
                                    stage: str,
                                    block_size: Tuple[int, int],
                                    num_blocks: int,
                                    data_type: str = 'unknown') -> SpectralMetadata:
        """
        Create metadata for discretized data.
        
        Parameters:
        -----------
        original_metadata : SpectralMetadata
            Original metadata
        stage : str
            'intermediate' or 'final'
        block_size : Tuple[int, int]
            Size of blocks used
        num_blocks : int
            Number of resulting blocks
        data_type : str
            Type of data for metadata
            
        Returns:
        --------
        metadata : SpectralMetadata
            Updated metadata
        """
        return SpectralMetadata(
            source_type=original_metadata.source_type,
            dimensions=(num_blocks, 1),  # Flattened after discretization
            scan_mode='discretized',
            units=original_metadata.units.copy(),
            acquisition_date=original_metadata.acquisition_date,
            additional_info={
                **original_metadata.additional_info,
                'discretization_stage': stage,
                'block_size': block_size,
                'original_dimensions': original_metadata.dimensions,
                'num_blocks': num_blocks,
                'data_type': data_type
            }
        )
    
    def validate_block_selection(self,
                                spectral_data: SpectralData,
                                block_h: int,
                                block_v: int,
                                selected_blocks: List[Tuple[int, int]]) -> bool:
        """
        Validate that selected blocks are within bounds.
        
        Parameters:
        -----------
        spectral_data : SpectralData
            Input data
        block_h : int
            Horizontal block size
        block_v : int
            Vertical block size
        selected_blocks : List[Tuple[int, int]]
            Block indices to validate
            
        Returns:
        --------
        valid : bool
            True if all blocks are valid
        """
        dim_h, dim_v = spectral_data.metadata.dimensions
        max_block_h = math.ceil(dim_h / block_h)
        max_block_v = math.ceil(dim_v / block_v)
        
        for block_row, block_col in selected_blocks:
            if not (0 <= block_row < max_block_v and 0 <= block_col < max_block_h):
                logger.error(f"Block ({block_row}, {block_col}) out of bounds "
                           f"(max: {max_block_v-1}, {max_block_h-1})")
                return False
        
        logger.info(f"Block selection validation passed: {len(selected_blocks)} blocks within bounds")
        return True
    
    def get_block_info(self,
                      spectral_data: SpectralData,
                      block_h: int,
                      block_v: int) -> Dict:
        """
        Get information about discretization blocks.
        
        Parameters:
        -----------
        spectral_data : SpectralData
            Input data
        block_h : int
            Horizontal block size
        block_v : int
            Vertical block size
            
        Returns:
        --------
        info : Dict
            Block information
        """
        dim_h, dim_v = spectral_data.metadata.dimensions
        num_groups_h = math.ceil(dim_h / block_h)
        num_groups_v = math.ceil(dim_v / block_v)
        
        # Calculate edge blocks
        edge_blocks = []
        for j in range(num_groups_v):
            for i in range(num_groups_h):
                is_edge = (i == 0 or i == num_groups_h - 1 or 
                          j == 0 or j == num_groups_v - 1)
                if is_edge:
                    edge_blocks.append((j, i))
        
        # Calculate actual block sizes (accounting for edges)
        block_sizes = {}
        for j in range(num_groups_v):
            for i in range(num_groups_h):
                actual_h = min(block_h, dim_h - i * block_h)
                actual_v = min(block_v, dim_v - j * block_v)
                block_sizes[(j, i)] = (actual_h, actual_v)
        
        info = {
            'original_dimensions': (dim_h, dim_v),
            'block_size': (block_h, block_v),
            'num_blocks_h': num_groups_h,
            'num_blocks_v': num_groups_v,
            'total_blocks': num_groups_h * num_groups_v,
            'edge_blocks': edge_blocks,
            'block_sizes': block_sizes
        }
        
        logger.debug(f"Block info: {info}")
        return info
    
    def export_discretized_data(self,
                               spectral_data: SpectralData,
                               block_h: int,
                               block_v: int,
                               output_directory: str,
                               data_type: str = 'unknown',
                               use_selection: bool = False,
                               selected_blocks: Optional[List[Tuple[int, int]]] = None,
                               ignore_empty_blocks: bool = True) -> Dict[str, str]:
        """
        Export discretized data to CSV files with specialized naming.
        
        Parameters:
        -----------
        spectral_data : SpectralData
            Input spectral data
        block_h : int
            Horizontal block size
        block_v : int
            Vertical block size
        output_directory : str
            Directory to save output files
        data_type : str
            Type of data for file naming
        use_selection : bool
            Whether to use block selection
        selected_blocks : List[Tuple[int, int]], optional
            Selected blocks if use_selection is True
        ignore_empty_blocks : bool
            Whether to ignore empty blocks
            
        Returns:
        --------
        file_paths : Dict[str, str]
            Paths to generated files
        """
        import os
        from pathlib import Path
        
        output_path = Path(output_directory)
        output_path.mkdir(parents=True, exist_ok=True)
        
        # Perform discretization
        results = self.discretize_spectral_data(
            spectral_data=spectral_data,
            block_h=block_h,
            block_v=block_v,
            selected_blocks=selected_blocks if use_selection else None,
            ignore_empty_blocks=ignore_empty_blocks,
            data_type=data_type
        )
        
        # Generate file names based on data type
        if data_type == 'iv':
            base_name = "IV"
        elif data_type == 'didv':
            base_name = "dIdV"
        elif data_type == 'd2idv2':
            base_name = "d2IdV2"
        else:
            base_name = "data"
        
        selection_suffix = "_selected" if use_selection else ""
        
        intermediate_file = output_path / f"{base_name}_intermediate{selection_suffix}.csv"
        final_file = output_path / f"{base_name}_discretized{selection_suffix}.csv"
        
        # Save files
        results['intermediate'].data.to_csv(intermediate_file, index=False)
        results['final'].data.to_csv(final_file, index=False)
        
        file_paths = {
            'intermediate': str(intermediate_file),
            'final': str(final_file)
        }
        
        logger.info(f"Exported discretized data: {file_paths}")
        return file_paths
    
    def batch_discretize_multiple_types(self,
                                       data_dict: Dict[str, SpectralData],
                                       block_h: int,
                                       block_v: int,
                                       output_directory: str,
                                       use_selection: bool = False,
                                       selected_blocks: Optional[List[Tuple[int, int]]] = None,
                                       ignore_empty_blocks: bool = True) -> Dict[str, Dict[str, str]]:
        """
        Discretize multiple data types in batch.
        
        Parameters:
        -----------
        data_dict : Dict[str, SpectralData]
            Dictionary mapping data types to spectral data
        block_h : int
            Horizontal block size
        block_v : int
            Vertical block size
        output_directory : str
            Directory to save output files
        use_selection : bool
            Whether to use block selection
        selected_blocks : List[Tuple[int, int]], optional
            Selected blocks if use_selection is True
        ignore_empty_blocks : bool
            Whether to ignore empty blocks
            
        Returns:
        --------
        all_file_paths : Dict[str, Dict[str, str]]
            File paths for each data type
        """
        all_file_paths = {}
        
        for data_type, spectral_data in data_dict.items():
            try:
                file_paths = self.export_discretized_data(
                    spectral_data=spectral_data,
                    block_h=block_h,
                    block_v=block_v,
                    output_directory=output_directory,
                    data_type=data_type,
                    use_selection=use_selection,
                    selected_blocks=selected_blocks,
                    ignore_empty_blocks=ignore_empty_blocks
                )
                all_file_paths[data_type] = file_paths
                
            except Exception as e:
                logger.error(f"Failed to discretize {data_type}: {e}")
                continue
        
        logger.info(f"Batch discretization completed: {len(all_file_paths)} data types processed")
        return all_file_paths