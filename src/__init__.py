"""
HyperSpec Analyzer
Advanced hyperspectral data analysis tool
"""

__version__ = "1.0.0"
__author__ = "HyperSpec Analysis Team"

# Setup logging
import logging

# Create logger
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

# Console handler
console_handler = logging.StreamHandler()
console_handler.setLevel(logging.INFO)

# Formatter
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
console_handler.setFormatter(formatter)

# Add handler to logger
logger.addHandler(console_handler)
