#!/usr/bin/with-contenv bashio

export SCANNER_PRINTER_IP=$(bashio::config 'printer_ip')
export SCANNER_RESOLUTION=$(bashio::config 'resolution')
export SCANNER_COLOR_MODE=$(bashio::config 'color_mode')
export SCANNER_PAPER_SIZE=$(bashio::config 'paper_size')
export SCANNER_OUTPUT_DIR=/media/$(bashio::config 'scan_folder')

python3 -u /scan.py
