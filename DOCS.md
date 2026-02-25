# Document Scanner

Scan documents from your HP printer directly from Home Assistant.

## Setup

### 1. Configure the addon

Go to the addon **Configuration** tab and set your printer's IP address.

### 2. Create scripts

Go to **Settings → Scripts → Create**, click the three dots → **Edit as YAML**, and paste:

**Scan Page** (appends to today's document):

```yaml
alias: Scan Page
icon: mdi:scanner
sequence:
  - condition: not
    conditions:
      - condition: state
        entity_id: sensor.scanner_status
        state: scanning
  - service: hassio.addon_stdin
    data:
      addon: local_scanner
      input: append
```

**New Document** (starts a new file):

```yaml
alias: New Document
icon: mdi:file-plus
sequence:
  - condition: not
    conditions:
      - condition: state
        entity_id: sensor.scanner_status
        state: scanning
  - service: hassio.addon_stdin
    data:
      addon: local_scanner
      input: new
```

### 3. Add dashboard card

Edit your dashboard, add a card, and paste this YAML:

```yaml
type: vertical-stack
cards:
  - type: conditional
    conditions:
      - entity: sensor.scanner_status
        state_not: scanning
    card:
      type: horizontal-stack
      cards:
        - type: button
          name: Scan Page
          icon: mdi:scanner
          tap_action:
            action: perform-action
            perform_action: script.scan_page
        - type: button
          name: New Document
          icon: mdi:file-plus
          tap_action:
            action: perform-action
            perform_action: script.new_document
  - type: conditional
    conditions:
      - entity: sensor.scanner_status
        state: scanning
    card:
      type: markdown
      content: "**Scanning in progress...**"
```

The buttons are hidden while a scan is in progress and replaced with a status message.

## File storage

Scanned files are saved to `/media/scans/` and accessible via the Samba `media` share.

Files are named by date: `2026-02-25.pdf`, `2026-02-25_2.pdf`, etc.

## Scan settings

| Option | Default | Description |
|--------|---------|-------------|
| `printer_ip` | — | Your printer's IP address |
| `resolution` | 300 | Scan resolution in DPI |
