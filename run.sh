#!/bin/bash
echo "Starting Algo Trader..."
cd "$(dirname "$0")"
python -m algo_trader.main
