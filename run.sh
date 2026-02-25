#!/usr/bin/with-contenv bashio

export SCANNER_PRINTER_IP=$(bashio::config 'printer_ip')
export SCANNER_RESOLUTION=$(bashio::config 'resolution')
export SCANNER_OUTPUT_DIR=/media/scans

python3 -u /scan.py
