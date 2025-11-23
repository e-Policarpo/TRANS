"""
Topography Data Model
Structure for handling topography/height data
"""

import numpy as np
from typing import Optional, Tuple, List
from dataclasses import dataclass
import logging
from PIL import Image

logger = logging.getLogger(__name__)


@dataclass
class TopographyMetadata:
    """Metadata for topography data"""
    dimensions: Tuple[int, int]  # (height, width) in pixels
    physical_size: Optional[Tuple[float, float]] = None  # Physical dimensions (y, x) in units
    units: str = 'nm'  # Physical units
    scan_mode: str = 'meander'  # Scan pattern
    
    @property
    def pixel_size(self) -> Optional[Tuple[float, float]]:
        """Calculate pixel size in physical units"""
        if self.physical_size is None:
            return None
        return (
            self.physical_size[0] / self.dimensions[0],
            self.physical_size[1] / self.dimensions[1]
        )


class TopographyData:
    """
    Container for topography/height data with discretization support.
    """
    
    def __init__(self, 
                 data: np.ndarray,
                 metadata: Optional[TopographyMetadata] = None):
        """
        Initialize TopographyData object.
        
        Parameters:
        -----------
        data : np.ndarray
            2D array of height values
        metadata : TopographyMetadata, optional
            Metadata about the topography
        """
        if data.ndim != 2:
            raise ValueError(f"Topography data must be 2D, got {data.ndim}D")
        
        self.data = data
        self.metadata = metadata or TopographyMetadata(dimensions=data.shape)
        
        # Discretization state
        self.discretized_data: Optional[np.ndarray] = None
        self.block_size: Optional[Tuple[int, int]] = None
        self.selected_blocks: List[Tuple[int, int]] = []
        
    @property
    def shape(self) -> Tuple[int, int]:
        """Get shape of topography data"""
        return self.data.shape
    
    @property
    def height(self) -> int:
        """Get height (rows) of topography"""
        return self.data.shape[0]
    
    @property
    def width(self) -> int:
        """Get width (columns) of topography"""
        return self.data.shape[1]
    
    def normalize(self, vmin: Optional[float] = None, 
                  vmax: Optional[float] = None) -> np.ndarray:
        """
        Normalize topography data to [0, 1] range.
        
        Parameters:
        -----------
        vmin : float, optional
            Minimum value for normalization (default: data min)
        vmax : float, optional
            Maximum value for normalization (default: data max)
            
        Returns:
        --------
        normalized : np.ndarray
            Normalized data in [0, 1] range
        """
        vmin = vmin if vmin is not None else np.nanmin(self.data)
        vmax = vmax if vmax is not None else np.nanmax(self.data)
        
        if vmax == vmin:
            logger.warning("vmin equals vmax, returning zeros")
            return np.zeros_like(self.data)
        
        normalized = (self.data - vmin) / (vmax - vmin)
        return np.clip(normalized, 0, 1)
    
    def to_image(self, colormap: str = 'gray') -> Image.Image:
        """
        Convert topography to PIL Image.
        
        Parameters:
        -----------
        colormap : str
            Matplotlib colormap name
            
        Returns:
        --------
        image : PIL.Image
            Grayscale or colored image
        """
        normalized = self.normalize()
        
        if colormap == 'gray':
            # Convert to 8-bit grayscale
            img_data = (normalized * 255).astype(np.uint8)
            return Image.fromarray(img_data, mode='L')
        else:
            # Apply colormap
            import matplotlib.cm as cm
            cmap = cm.get_cmap(colormap)
            colored = cmap(normalized)
            img_data = (colored[:, :, :3] * 255).astype(np.uint8)
            return Image.fromarray(img_data, mode='RGB')
    
    def discretize(self, block_v: int, block_h: int, 
                   resize_to_fit: bool = True) -> 'TopographyData':
        """
        Discretize topography into blocks.
        
        Parameters:
        -----------
        block_v : int
            Vertical block size (height)
        block_h : int
            Horizontal block size (width)
        resize_to_fit : bool
            If True, resize image to fit block dimensions exactly
            
        Returns:
        --------
        self : TopographyData
            Returns self for method chaining
        """
        height, width = self.shape
        
        # Calculate if resizing is needed
        needs_resize = (height % block_v != 0) or (width % block_h != 0)
        
        if needs_resize and resize_to_fit:
            # Calculate new dimensions
            new_height = (height // block_v) * block_v
            new_width = (width // block_h) * block_h
            
            # Resize using PIL for high-quality interpolation
            img = self.to_image()
            img_resized = img.resize((new_width, new_height), Image.BICUBIC)
            self.data = np.array(img_resized).astype(self.data.dtype)
            
            # Update metadata
            self.metadata.dimensions = (new_height, new_width)
            
            logger.info(f"Resized topography from {(height, width)} to "
                       f"{(new_height, new_width)} to fit blocks")
        
        # Calculate discretized dimensions
        n_blocks_v = self.height // block_v
        n_blocks_h = self.width // block_h
        
        # Create discretized data by averaging blocks
        self.discretized_data = np.zeros((n_blocks_v, n_blocks_h))
        
        for i in range(n_blocks_v):
            for j in range(n_blocks_h):
                # Extract block
                row_start = i * block_v
                row_end = (i + 1) * block_v
                col_start = j * block_h
                col_end = (j + 1) * block_h
                
                block = self.data[row_start:row_end, col_start:col_end]
                self.discretized_data[i, j] = np.mean(block)
        
        self.block_size = (block_v, block_h)
        logger.info(f"Discretized to {n_blocks_v}x{n_blocks_h} blocks")
        
        return self
    
    def get_selection_mask(self) -> np.ndarray:
        """
        Get boolean mask for selected blocks.
        
        Returns:
        --------
        mask : np.ndarray
            2D boolean array matching original data dimensions
        """
        if self.discretized_data is None or self.block_size is None:
            raise ValueError("Data not discretized yet")
        
        mask = np.zeros(self.shape, dtype=bool)
        block_v, block_h = self.block_size
        
        for i, j in self.selected_blocks:
            row_start = i * block_v
            row_end = min((i + 1) * block_v, self.height)
            col_start = j * block_h
            col_end = min((j + 1) * block_h, self.width)
            
            mask[row_start:row_end, col_start:col_end] = True
        
        return mask
    
    def add_selected_block(self, block_i: int, block_j: int):
        """Add a block to selection"""
        if (block_i, block_j) not in self.selected_blocks:
            self.selected_blocks.append((block_i, block_j))
            logger.debug(f"Added block ({block_i}, {block_j}) to selection")
    
    def remove_selected_block(self, block_i: int, block_j: int):
        """Remove a block from selection"""
        if (block_i, block_j) in self.selected_blocks:
            self.selected_blocks.remove((block_i, block_j))
            logger.debug(f"Removed block ({block_i}, {block_j}) from selection")
    
    def toggle_block_selection(self, block_i: int, block_j: int):
        """Toggle block selection state"""
        if (block_i, block_j) in self.selected_blocks:
            self.remove_selected_block(block_i, block_j)
        else:
            self.add_selected_block(block_i, block_j)
    
    def clear_selection(self):
        """Clear all selected blocks"""
        self.selected_blocks = []
        logger.debug("Cleared block selection")
    
    def get_block_value(self, block_i: int, block_j: int) -> float:
        """Get average value of a discretized block"""
        if self.discretized_data is None:
            raise ValueError("Data not discretized yet")
        
        n_blocks_v, n_blocks_h = self.discretized_data.shape
        if not (0 <= block_i < n_blocks_v and 0 <= block_j < n_blocks_h):
            raise IndexError(f"Block ({block_i}, {block_j}) out of bounds")
        
        return self.discretized_data[block_i, block_j]
    
    def save(self, filepath: str, format: str = 'tiff'):
        """
        Save topography data.
        
        Parameters:
        -----------
        filepath : str
            Output file path
        format : str
            Output format ('tiff', 'png', 'npy')
        """
        if format in ['tiff', 'png']:
            img = self.to_image()
            img.save(filepath)
        elif format == 'npy':
            np.save(filepath, self.data)
        else:
            raise ValueError(f"Unsupported format: {format}")
        
        logger.info(f"Topography saved to {filepath}")
    
    @classmethod
    def load(cls, filepath: str) -> 'TopographyData':
        """
        Load topography from file.
        
        Parameters:
        -----------
        filepath : str
            Input file path
            
        Returns:
        --------
        topography : TopographyData
            Loaded topography data
        """
        if filepath.endswith('.npy'):
            data = np.load(filepath)
        else:
            # Load as image
            img = Image.open(filepath)
            data = np.array(img)
            
            # Convert to grayscale if needed
            if data.ndim == 3:
                data = np.mean(data, axis=2)
        
        metadata = TopographyMetadata(dimensions=data.shape)
        return cls(data, metadata)
    
    @classmethod
    def from_forward_backward(cls, forward: np.ndarray, 
                            backward: np.ndarray,
                            flip_vertical: bool = True) -> 'TopographyData':
        """
        Create topography from forward and backward scans.
        
        Parameters:
        -----------
        forward : np.ndarray
            Forward scan data
        backward : np.ndarray
            Backward scan data
        flip_vertical : bool
            Whether to flip vertically (common for STM data)
            
        Returns:
        --------
        topography : TopographyData
            Average of forward and backward scans
        """
        # Average forward and backward
        avg_data = (forward + backward) / 2
        
        # Flip if needed (STM convention)
        if flip_vertical:
            avg_data = np.flipud(avg_data)
        
        metadata = TopographyMetadata(dimensions=avg_data.shape)
        return cls(avg_data, metadata)
    
    def __repr__(self) -> str:
        return (f"TopographyData(shape={self.shape}, "
                f"discretized={self.discretized_data is not None}, "
                f"selected_blocks={len(self.selected_blocks)})")
