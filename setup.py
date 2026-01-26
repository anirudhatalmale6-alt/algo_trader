"""
Setup script for Algo Trader
"""
from setuptools import setup, find_packages

setup(
    name="algo_trader",
    version="1.0.0",
    description="Pine Script & Chartink Based Algo Trading Platform",
    author="Anirudha Talmale",
    packages=find_packages(),
    python_requires=">=3.9",
    install_requires=[
        "PyQt6>=6.4.0",
        "requests>=2.28.0",
        "aiohttp>=3.8.0",
        "pandas>=1.5.0",
        "numpy>=1.23.0",
        "sqlalchemy>=2.0.0",
        "websocket-client>=1.4.0",
        "python-dateutil>=2.8.0",
        "cryptography>=38.0.0",
        "pyyaml>=6.0",
        "loguru>=0.6.0",
        "matplotlib>=3.6.0",
        "ta>=0.10.0",
    ],
    entry_points={
        "console_scripts": [
            "algo-trader=algo_trader.main:main",
        ],
    },
)
