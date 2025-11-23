"""
Topography Widget - COM SELEÇÃO INTERATIVA AVANÇADA
Interactive widget for topography display and block selection
"""

from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QMessageBox
from PySide6.QtCore import Qt, Signal, QRect, QPoint
from PySide6.QtGui import QPixmap, QPainter, QColor, QBrush, QPen, QImage, QMouseEvent
import numpy as np
from typing import Optional, List, Tuple
import logging

from ..models.topography_data import TopographyData

logger = logging.getLogger(__name__)


class TopographyWidget(QWidget):
    """
    Widget for displaying topography and allowing interactive block selection.
    
    CRITICAL INDEXING CONVENTION:
    Blocks are indexed as (h_group, v_group) where:
    - h_group: horizontal group index (column of blocks) 
    - v_group: vertical group index (row of blocks)
    
    This matches the H→V (column-by-column) order used in discretization:
    - Block_0 is at (h_group=0, v_group=0)
    - Block_1 is at (h_group=0, v_group=1)
    - Block_N is at (h_group=1, v_group=0)
    
    When blocks are drawn/stored, they use this (h, v) indexing, NOT (row, col).
    """
    
    # Signal emitted when selection changes
    selection_changed = Signal(list)
    
    def __init__(self, parent=None):
        """Initialize topography widget."""
        super().__init__(parent)
        
        self.topography: Optional[TopographyData] = None
        self.pixmap: Optional[QPixmap] = None
        self.scaled_pixmap: Optional[QPixmap] = None
        
        # Selection state - AVANÇADO
        self.selecting = False
        self.block_rects: dict = {}  # Maps block (i,j) to QRect
        self.selected_blocks: List[Tuple[int, int]] = []
        self.hovered_block: Optional[Tuple[int, int]] = None
        
        # Display settings
        self.scale_factor = 1.0
        self.colormap = 'viridis'
        
        # Selection colors
        self.selected_color = QColor(30, 144, 255, 120)  # Semi-transparent blue
        self.hover_color = QColor(255, 165, 0, 80)  # Semi-transparent orange
        
        self.setup_ui()
        
    def setup_ui(self):
        """Setup the widget UI."""
        layout = QVBoxLayout(self)
        
        # Controls
        controls_layout = QHBoxLayout()
        
        self.clear_btn = QPushButton("Clear Selection")
        self.clear_btn.clicked.connect(self.clear_selection)
        controls_layout.addWidget(self.clear_btn)
        
        self.select_mode_btn = QPushButton("Toggle Select Mode")
        self.select_mode_btn.clicked.connect(self.toggle_select_mode)
        self.select_mode_btn.setCheckable(True)
        self.select_mode_btn.setChecked(True)
        controls_layout.addWidget(self.select_mode_btn)
        
        self.zoom_in_btn = QPushButton("Zoom In")
        self.zoom_in_btn.clicked.connect(self.zoom_in)
        controls_layout.addWidget(self.zoom_in_btn)
        
        self.zoom_out_btn = QPushButton("Zoom Out")
        self.zoom_out_btn.clicked.connect(self.zoom_out)
        controls_layout.addWidget(self.zoom_out_btn)
        
        self.reset_btn = QPushButton("Reset View")
        self.reset_btn.clicked.connect(self.reset_view)
        controls_layout.addWidget(self.reset_btn)
        
        controls_layout.addStretch()
        layout.addLayout(controls_layout)
        
        # Display area
        self.display_label = QLabel()
        self.display_label.setMinimumSize(400, 400)
        self.display_label.setMaximumSize(800, 800)
        self.display_label.setScaledContents(False)
        self.display_label.setAlignment(Qt.AlignCenter)
        self.display_label.setStyleSheet("border: 1px solid #ccc; background-color: #f0f0f0;")
        
        # Enable mouse tracking for interactive selection
        self.display_label.setMouseTracking(True)
        self.display_label.mousePressEvent = self.on_mouse_press
        self.display_label.mouseMoveEvent = self.on_mouse_move
        self.display_label.leaveEvent = self.on_mouse_leave
        
        layout.addWidget(self.display_label)
        
        # Info label
        self.info_label = QLabel("No topography loaded")
        layout.addWidget(self.info_label)
        
        # Selection info
        self.selection_info = QLabel("Selected blocks: 0")
        layout.addWidget(self.selection_info)
        
    def set_topography(self, topography: TopographyData):
        """
        Set topography data to display.
        
        Parameters:
        -----------
        topography : TopographyData
            Topography to display
        """
        self.topography = topography
        self.selected_blocks = topography.selected_blocks.copy()
        
        # Create pixmap from topography
        self.create_pixmap()
        
        # Update display
        self.update_display()
        self.update_info()
        
    def create_pixmap(self):
        """Create QPixmap from topography data with block overlay."""
        if self.topography is None:
            return
        
        # Convert to image
        img = self.topography.to_image(self.colormap)
        
        # Convert PIL Image to QPixmap
        if img.mode == 'L':
            # Grayscale
            height, width = self.topography.shape
            qimage = QImage(np.array(img), width, height, width, QImage.Format_Grayscale8)
        else:
            # RGB
            height, width = self.topography.shape
            img_array = np.array(img)
            qimage = QImage(img_array.data, width, height, 3 * width, QImage.Format_RGB888)
        
        self.pixmap = QPixmap.fromImage(qimage)
        
        # Always create block overlay for selection
        self.create_block_overlay()
    
    def create_block_overlay(self):
        """Create overlay showing discretized blocks and selection."""
        if self.topography is None:
            return
        
        # Get dimensions
        orig_h, orig_w = self.topography.shape
        
        # If not discretized, create a default grid for selection
        if self.topography.discretized_data is None:
            # Use default block size or create sensible grid
            block_size = min(orig_w // 10, orig_h // 10)  # Default to ~10 blocks per dimension
            if block_size < 1:
                block_size = 1
                
            n_blocks_w = orig_w // block_size
            n_blocks_h = orig_h // block_size
            
            # Create painter
            painter = QPainter(self.pixmap)
            painter.setRenderHint(QPainter.Antialiasing)
            
            # Draw grid lines
            pen = QPen(QColor(255, 255, 255, 150))  # Semi-transparent white
            pen.setWidth(1)
            painter.setPen(pen)
            
            # Clear block rectangles
            self.block_rects = {}
            
            # CRITICAL: Draw blocks in H→V order (column-by-column) to match discretization
            for j in range(n_blocks_w):  # Horizontal (columns) first
                for i in range(n_blocks_h):  # Vertical (rows) second
                    # Calculate block position
                    y = i * block_size
                    x = j * block_size
                    h = min(block_size, orig_h - y)
                    w = min(block_size, orig_w - x)
                    
                    # Draw rectangle
                    rect = QRect(x, y, w, h)
                    painter.drawRect(rect)
                    
                    # Store rectangle for hit detection
                    # Use (j, i) to represent (horizontal_group, vertical_group)
                    self.block_rects[(j, i)] = rect
                    
                    # Highlight selected blocks
                    # Note: blocks are indexed as (h_group, v_group)
                    if (j, i) in self.selected_blocks:
                        brush = QBrush(self.selected_color)
                        painter.fillRect(rect, brush)
            
            painter.end()
            
        else:
            # Use actual discretization
            block_v, block_h = self.topography.block_size
            n_blocks_v, n_blocks_h = self.topography.discretized_data.shape
            
            # Create painter
            painter = QPainter(self.pixmap)
            painter.setRenderHint(QPainter.Antialiasing)
            
            # Draw grid lines
            pen = QPen(QColor(255, 255, 255, 150))
            pen.setWidth(1)
            painter.setPen(pen)
            
            # Clear block rectangles
            self.block_rects = {}
            
            # CRITICAL: Draw blocks in H→V order (column-by-column) to match discretization
            # Block_0 is at (row=0, col=0), Block_1 at (row=1, col=0), etc.
            for j in range(n_blocks_h):  # Horizontal groups (columns) first
                for i in range(n_blocks_v):  # Vertical groups (rows) second
                    # Calculate block position in image coordinates
                    y = i * block_v
                    x = j * block_h
                    h = min(block_v, orig_h - y)
                    w = min(block_h, orig_w - x)
                    
                    # Draw rectangle
                    rect = QRect(x, y, w, h)
                    painter.drawRect(rect)
                    
                    # Store rectangle for hit detection
                    # Use (j, i) to represent (horizontal_group, vertical_group)
                    # This matches the order used in discretization
                    self.block_rects[(j, i)] = rect
                    
                    # Highlight selected blocks
                    # Note: blocks are indexed as (h_group, v_group)
                    if (j, i) in self.selected_blocks:
                        brush = QBrush(self.selected_color)
                        painter.fillRect(rect, brush)
            
            painter.end()
    
    def on_mouse_press(self, event: QMouseEvent):
        """Handle mouse click for block selection."""
        if not self.selecting or self.topography is None:
            return
        
        # Get click position in image coordinates
        pos = self.get_image_pos(event.pos())
        if pos is not None:
            # Find which block was clicked
            block = self.get_block_at_pos(pos)
            if block is not None:
                self.toggle_block(block)
    
    def on_mouse_move(self, event: QMouseEvent):
        """Handle mouse movement for hover effects."""
        if not self.selecting or self.topography is None:
            return
        
        pos = self.get_image_pos(event.pos())
        if pos is not None:
            block = self.get_block_at_pos(pos)
            
            # Update hover state
            if block != self.hovered_block:
                self.hovered_block = block
                self.create_pixmap()  # Redraw with hover effect
                self.update_display()
    
    def on_mouse_leave(self, event):
        """Handle mouse leaving the widget."""
        self.hovered_block = None
        self.create_pixmap()
        self.update_display()
    
    def get_image_pos(self, widget_pos: QPoint) -> Optional[QPoint]:
        """
        Convert widget position to image coordinates.
        
        Parameters:
        -----------
        widget_pos : QPoint
            Position in widget coordinates
            
        Returns:
        --------
        image_pos : QPoint or None
            Position in image coordinates
        """
        if self.scaled_pixmap is None:
            return None
        
        # Get display label size and pixmap size
        label_size = self.display_label.size()
        pixmap_size = self.scaled_pixmap.size()
        
        # Calculate offset (for centered display)
        x_offset = (label_size.width() - pixmap_size.width()) // 2
        y_offset = (label_size.height() - pixmap_size.height()) // 2
        
        # Check if click is within pixmap area
        rel_x = widget_pos.x() - x_offset
        rel_y = widget_pos.y() - y_offset
        
        if (0 <= rel_x < pixmap_size.width() and 
            0 <= rel_y < pixmap_size.height()):
            # Scale back to original image coordinates
            img_x = int(rel_x / self.scale_factor)
            img_y = int(rel_y / self.scale_factor)
            return QPoint(img_x, img_y)
        
        return None
    
    def get_block_at_pos(self, pos: QPoint) -> Optional[Tuple[int, int]]:
        """
        Get block indices at given position.
        
        Parameters:
        -----------
        pos : QPoint
            Position in image coordinates
            
        Returns:
        --------
        block : Tuple[int, int] or None
            Block indices as (h_group, v_group) where:
            - h_group: horizontal group (column of blocks)
            - v_group: vertical group (row of blocks)
        """
        for (h, v), rect in self.block_rects.items():
            if rect.contains(pos):
                return (h, v)
        return None
    
    def toggle_block(self, block: Tuple[int, int]):
        """
        Toggle selection state of a block.
        
        Parameters:
        -----------
        block : Tuple[int, int]
            Block indices as (h_group, v_group)
        """
        if block in self.selected_blocks:
            self.selected_blocks.remove(block)
            logger.info(f"Deselected block (h={block[0]}, v={block[1]})")
        else:
            self.selected_blocks.append(block)
            logger.info(f"Selected block (h={block[0]}, v={block[1]})")
        
        # Update topography object
        if self.topography:
            self.topography.selected_blocks = self.selected_blocks.copy()
        
        # Recreate display with updated selection
        self.create_pixmap()
        self.update_display()
        self.update_info()
        
        # Emit signal
        self.selection_changed.emit(self.selected_blocks)
    
    def toggle_select_mode(self):
        """Toggle selection mode on/off."""
        self.selecting = not self.selecting
        self.select_mode_btn.setChecked(self.selecting)
        
        if self.selecting:
            self.display_label.setCursor(Qt.PointingHandCursor)
        else:
            self.display_label.setCursor(Qt.ArrowCursor)
    
    def clear_selection(self):
        """Clear all selected blocks."""
        self.selected_blocks = []
        if self.topography:
            self.topography.clear_selection()
        
        self.create_pixmap()
        self.update_display()
        self.update_info()
        
        self.selection_changed.emit(self.selected_blocks)
        logger.info("Cleared selection")
    
    def zoom_in(self):
        """Zoom in the display."""
        self.scale_factor = min(self.scale_factor * 1.25, 5.0)
        self.update_display()
    
    def zoom_out(self):
        """Zoom out the display."""
        self.scale_factor = max(self.scale_factor / 1.25, 0.1)
        self.update_display()
    
    def reset_view(self):
        """Reset view to fit window."""
        self.scale_factor = 1.0
        self.update_display()
    
    def update_display(self):
        """Update the display with current pixmap and scale."""
        if self.pixmap is None:
            return
        
        # Scale pixmap
        scaled_size = self.pixmap.size() * self.scale_factor
        
        # Limit maximum size to label size
        label_size = self.display_label.size()
        if scaled_size.width() > label_size.width() or scaled_size.height() > label_size.height():
            # Fit to window
            self.scaled_pixmap = self.pixmap.scaled(
                label_size,
                Qt.KeepAspectRatio,
                Qt.SmoothTransformation
            )
            # Update scale factor
            self.scale_factor = self.scaled_pixmap.width() / self.pixmap.width()
        else:
            self.scaled_pixmap = self.pixmap.scaled(
                scaled_size,
                Qt.KeepAspectRatio,
                Qt.SmoothTransformation
            )
        
        # Set pixmap
        self.display_label.setPixmap(self.scaled_pixmap)
    
    def update_info(self):
        """Update information labels."""
        if self.topography is None:
            self.info_label.setText("No topography loaded")
            self.selection_info.setText("Selected blocks: 0")
            return
        
        info = []
        info.append(f"Size: {self.topography.shape[1]}×{self.topography.shape[0]}")
        
        if self.topography.discretized_data is not None:
            n_v, n_h = self.topography.discretized_data.shape
            info.append(f"Blocks: {n_h}×{n_v}")
            info.append(f"Block size: {self.topography.block_size[1]}×{self.topography.block_size[0]}")
        
        self.info_label.setText(" | ".join(info))
        self.selection_info.setText(f"Selected blocks: {len(self.selected_blocks)}")
    
    def set_colormap(self, colormap: str):
        """
        Change colormap for topography display.
        
        Parameters:
        -----------
        colormap : str
            Matplotlib colormap name
        """
        self.colormap = colormap
        if self.topography:
            self.create_pixmap()
            self.update_display()
    
    def get_selected_blocks(self) -> List[Tuple[int, int]]:
        """Get currently selected blocks."""
        return self.selected_blocks.copy()