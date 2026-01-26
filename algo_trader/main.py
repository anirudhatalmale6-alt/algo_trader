"""
Algo Trader - Main Entry Point
"""
import sys
import os

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import Qt
from loguru import logger

from algo_trader.ui.main_window import MainWindow


def setup_logging():
    """Configure logging"""
    logger.add(
        "logs/algo_trader_{time}.log",
        rotation="10 MB",
        retention="7 days",
        level="INFO"
    )


def main():
    """Main entry point"""
    setup_logging()
    logger.info("Starting Algo Trader...")

    # Create application
    app = QApplication(sys.argv)
    app.setApplicationName("Algo Trader")
    app.setApplicationVersion("1.0.0")

    # Set application style
    app.setStyle("Fusion")

    # Create and show main window
    window = MainWindow()
    window.show()

    logger.info("Application started successfully")

    # Run event loop
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
