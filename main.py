#!/usr/bin/env python3
"""
HyperSpec Analyzer - Main Entry Point
Advanced tool for hyperspectral data analysis
"""

import sys
import os
from pathlib import Path

# Add source directory to path
sys.path.insert(0, str(Path(__file__).parent))

from PySide6.QtWidgets import QApplication
from PySide6.QtCore import Qt
from PySide6.QtGui import QPalette, QColor, QIcon
import logging

from src.ui.main_window import MainWindow

import setproctitle


setproctitle.setproctitle("TRANS")

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)


def setup_application_style(app: QApplication):
    """
    Setup application style and theme.
    
    Parameters:
    -----------
    app : QApplication
        Qt application instance
    """
    # Set application style
    app.setStyle("Fusion")
    
    # Create custom palette for dark theme (optional)
    if False:  # Set to True for dark theme
        palette = QPalette()
        palette.setColor(QPalette.Window, QColor(53, 53, 53))
        palette.setColor(QPalette.WindowText, Qt.white)
        palette.setColor(QPalette.Base, QColor(25, 25, 25))
        palette.setColor(QPalette.AlternateBase, QColor(53, 53, 53))
        palette.setColor(QPalette.ToolTipBase, Qt.black)
        palette.setColor(QPalette.ToolTipText, Qt.white)
        palette.setColor(QPalette.Text, Qt.white)
        palette.setColor(QPalette.Button, QColor(53, 53, 53))
        palette.setColor(QPalette.ButtonText, Qt.white)
        palette.setColor(QPalette.BrightText, Qt.red)
        palette.setColor(QPalette.Link, QColor(42, 130, 218))
        palette.setColor(QPalette.Highlight, QColor(42, 130, 218))
        palette.setColor(QPalette.HighlightedText, Qt.black)
        app.setPalette(palette)


def setup_application_icon(app: QApplication):
    """
    Setup application icon with macOS-specific fixes.
    
    Parameters:
    -----------
    app : QApplication
        Qt application instance
    """
    # Possible icon paths to try
    icon_paths = [
        # Absolute path
        "/Users/eduardapolicarpo/Documents/Doutorado/TRANS_beta/src/ui/icon.png",
        # Relative paths from main.py location
        Path(__file__).parent / "src" / "ui" / "icon.png",
        Path(__file__).parent / "icon.png",
        # Development paths
        Path("src/ui/icon.png"),
        Path("../src/ui/icon.png"),
    ]
    
    icon_loaded = False
    
    for icon_path in icon_paths:
        if isinstance(icon_path, str):
            path = Path(icon_path)
        else:
            path = icon_path
            
        logger.info(f"Trying icon path: {path}")
        
        if path.exists():
            try:
                # Method 1: Direct QIcon
                icon = QIcon(str(path))
                if not icon.isNull():
                    app.setWindowIcon(icon)
                    logger.info(f"Icon loaded successfully: {path}")
                    icon_loaded = True
                    
                    # Additional macOS-specific setup
                    if sys.platform == "darwin":
                        # Force icon in menus
                        app.setAttribute(Qt.AA_DontShowIconsInMenus, False)
                        # Try to set dock icon
                        try:
                            from AppKit import NSApplication, NSImage
                            ns_app = NSApplication.sharedApplication()
                            ns_image = NSImage.alloc().initWithContentsOfFile_(str(path))
                            if ns_image:
                                ns_app.setApplicationIconImage_(ns_image)
                                logger.info("Dock icon set for macOS")
                        except ImportError:
                            logger.warning("AppKit not available for dock icon")
                        except Exception as e:
                            logger.warning(f"Could not set dock icon: {e}")
                    
                    break
                    
            except Exception as e:
                logger.error(f"Error loading icon {path}: {e}")
                continue
    
    if not icon_loaded:
        logger.warning("No application icon could be loaded")
        # Create a simple fallback icon
        create_fallback_icon(app)


def create_fallback_icon(app: QApplication):
    """
    Create a simple programmatic fallback icon.
    
    Parameters:
    -----------
    app : QApplication
        Qt application instance
    """
    try:
        from PySide6.QtGui import QPixmap, QPainter
        from PySide6.QtCore import QRect
        
        # Create a 64x64 pixmap
        pixmap = QPixmap(64, 64)
        pixmap.fill(Qt.transparent)
        
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.Antialiasing)
        
        # Draw blue circle
        painter.setBrush(QColor(70, 130, 180))  # SteelBlue
        painter.setPen(Qt.NoPen)
        painter.drawEllipse(8, 8, 48, 48)
        
        # Draw "T" in white
        painter.setPen(QColor(255, 255, 255))
        painter.setFont(painter.font())
        painter.drawText(QRect(0, 0, 64, 64), Qt.AlignCenter, "T")
        
        painter.end()
        
        app.setWindowIcon(QIcon(pixmap))
        logger.info("Fallback icon created and set")
        
    except Exception as e:
        logger.error(f"Failed to create fallback icon: {e}")


def setup_macos_specific_settings():
    """Setup macOS-specific environment settings."""
    if sys.platform == "darwin":
        # Force layer backing for better rendering
        os.environ['QT_MAC_WANTS_LAYER'] = '1'
        
        # Disable the "show tab bar" menu item that causes issues
        os.environ['QT_MAC_DISABLE_WINDOW_RESTORE'] = '1'
        
        logger.info("macOS-specific settings applied")


def main():
    """Main application entry point."""
    # Setup macOS-specific settings first
    setup_macos_specific_settings()
    
    # Create Qt application
    app = QApplication(sys.argv)
    app.setApplicationName("HyperSpec Analyzer")
    app.setApplicationVersion("1.0.0")
    app.setOrganizationName("HyperSpec Analysis")
    app.setOrganizationDomain("eduardapolicarpo.com")
    
    # Setup application icon (must be before creating windows)
    setup_application_icon(app)
    
    # Setup application style
    setup_application_style(app)
    
    try:
        # Create and show main window
        logger.info("Starting HyperSpec Analyzer...")
        window = MainWindow()
        
        # Additional icon setup for the window
        if sys.platform == "darwin":
            # Try to set icon again for the specific window
            icon_paths = [
                "/Users/eduardapolicarpo/Documents/Doutorado/TRANS_beta/src/ui/icon.png",
                Path(__file__).parent / "src" / "ui" / "icon.png",
            ]
            
            for icon_path in icon_paths:
                if isinstance(icon_path, str):
                    path = Path(icon_path)
                else:
                    path = icon_path
                    
                if path.exists():
                    window.setWindowIcon(QIcon(str(path)))
                    logger.info(f"Window icon set: {path}")
                    break
        
        window.show()
        
        # macOS specific: bring to front
        if sys.platform == "darwin":
            window.raise_()
            window.activateWindow()
        
        # Run application
        logger.info("Application started successfully")
        return_code = app.exec()
        
        logger.info("Application finished")
        sys.exit(return_code)
        
    except Exception as e:
        logger.error(f"Failed to start application: {e}")
        import traceback
        traceback.print_exc()
        
        # Show error message to user
        from PySide6.QtWidgets import QMessageBox
        error_box = QMessageBox()
        error_box.setIcon(QMessageBox.Critical)
        error_box.setWindowTitle("Application Error")
        error_box.setText(f"Failed to start application:\n{str(e)}")
        error_box.exec()
        
        sys.exit(1)


if __name__ == "__main__":
    main()