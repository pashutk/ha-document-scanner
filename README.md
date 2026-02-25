# Document Scanner for Home Assistant

![GitHub release](https://img.shields.io/github/v/release/pashutk/ha-document-scanner)
![License](https://img.shields.io/github/license/pashutk/ha-document-scanner)
![HA addon](https://img.shields.io/badge/Home%20Assistant-Addon-blue)

A Home Assistant addon that scans documents from any eSCL/AirScan compatible printer (HP, Brother, Canon, etc.). Two dashboard buttons: **Scan Page** appends to today's document, **New Document** starts a fresh file.

## Features

- Scan to PDF from any eSCL-compatible printer (most modern HP, Brother, Canon)
- Append pages to today's document or start a new one
- Dashboard status indicator (idle/scanning/error)
- Dashboard buttons auto-hide while scanning, replaced with status indicator
- Files accessible via Samba share

## Installation

1. Copy this repository to `/addons/scanner` on your Home Assistant instance
2. Go to **Settings → Add-ons → Add-on Store → Check for updates**
3. Install **Document Scanner** from Local add-ons
4. Follow the [setup instructions](DOCS.md)

## Compatibility

Tested with HP Envy 6420e. Should work with any printer that supports the eSCL (AirScan) protocol.

## Credits

Created with [Claude Code](https://claude.ai/claude-code).
