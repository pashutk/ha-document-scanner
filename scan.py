#!/usr/bin/env python3
"""Scanner automation for HP printers via eSCL protocol.

Reads commands from stdin: "append" or "new" (one per line).

Environment variables:
  SCANNER_PRINTER_IP   - Printer IP address (required)
  SCANNER_OUTPUT_DIR   - Directory to save scanned PDFs (required)
  SCANNER_RESOLUTION   - Scan resolution in DPI (default: 300)
  SUPERVISOR_TOKEN     - HA API token (injected by HA)
"""

import io
import json
import os
import sys
import time
import urllib.error
import urllib.request
from datetime import date
from pathlib import Path

PRINTER_IP = os.environ.get("SCANNER_PRINTER_IP")
SCAN_DIR_STR = os.environ.get("SCANNER_OUTPUT_DIR")
RESOLUTION = int(os.environ.get("SCANNER_RESOLUTION", "300"))
SUPERVISOR_TOKEN = os.environ.get("SUPERVISOR_TOKEN")
HA_API = "http://supervisor/core/api"

WIDTH = 2550
HEIGHT = 3508

SCAN_SETTINGS = """\
<?xml version="1.0" encoding="UTF-8"?>
<scan:ScanSettings xmlns:scan="http://schemas.hp.com/imaging/escl/2011/05/03"
                   xmlns:pwg="http://www.pwg.org/schemas/2010/12/sm">
    <pwg:Version>2.63</pwg:Version>
    <pwg:ScanRegions>
        <pwg:ScanRegion>
            <pwg:XOffset>0</pwg:XOffset>
            <pwg:YOffset>0</pwg:YOffset>
            <pwg:Width>{width}</pwg:Width>
            <pwg:Height>{height}</pwg:Height>
            <pwg:ContentRegionUnits>escl:ThreeHundredthsOfInches</pwg:ContentRegionUnits>
        </pwg:ScanRegion>
    </pwg:ScanRegions>
    <pwg:InputSource>Platen</pwg:InputSource>
    <pwg:DocumentFormat>application/pdf</pwg:DocumentFormat>
    <scan:ColorMode>RGB24</scan:ColorMode>
    <scan:XResolution>{resolution}</scan:XResolution>
    <scan:YResolution>{resolution}</scan:YResolution>
    <scan:Intent>Document</scan:Intent>
</scan:ScanSettings>"""


def set_status(state, filename=""):
    if not SUPERVISOR_TOKEN:
        return
    data = json.dumps({
        "state": state,
        "attributes": {"friendly_name": "Scanner", "file": filename},
    }).encode()
    req = urllib.request.Request(
        f"{HA_API}/states/sensor.scanner_status",
        data=data,
        headers={
            "Authorization": f"Bearer {SUPERVISOR_TOKEN}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        urllib.request.urlopen(req, timeout=5)
    except Exception as e:
        print(f"Failed to set status: {e}", flush=True)


def get_latest_file(scan_dir):
    today = date.today().isoformat()
    latest = scan_dir / f"{today}.pdf"
    n = 2
    while True:
        path = scan_dir / f"{today}_{n}.pdf"
        if path.exists():
            latest = path
            n += 1
        else:
            break
    return latest


def get_next_file(scan_dir):
    today = date.today().isoformat()
    base = scan_dir / f"{today}.pdf"
    if not base.exists():
        return base
    n = 2
    while True:
        path = scan_dir / f"{today}_{n}.pdf"
        if not path.exists():
            return path
        n += 1


def scan_page():
    base_url = f"http://{PRINTER_IP}"

    req = urllib.request.Request(f"{base_url}/eSCL/ScannerStatus")
    resp = urllib.request.urlopen(req, timeout=10)
    status_xml = resp.read().decode()
    if "Idle" not in status_xml:
        raise RuntimeError("Scanner is not idle")

    xml = SCAN_SETTINGS.format(width=WIDTH, height=HEIGHT, resolution=RESOLUTION)
    req = urllib.request.Request(
        f"{base_url}/eSCL/ScanJobs",
        data=xml.encode(),
        headers={"Content-Type": "text/xml"},
        method="POST",
    )
    resp = urllib.request.urlopen(req, timeout=30)
    if resp.status != 201:
        raise RuntimeError(f"Failed to create scan job: HTTP {resp.status}")

    job_url = resp.headers["Location"]
    if not job_url.startswith("http"):
        job_url = f"{base_url}{job_url}"

    doc_url = f"{job_url}/NextDocument"
    for _ in range(60):
        time.sleep(2)
        try:
            req = urllib.request.Request(doc_url)
            resp = urllib.request.urlopen(req, timeout=30)
            return resp.read()
        except urllib.error.HTTPError as e:
            if e.code == 503:
                continue
            raise

    raise RuntimeError("Timeout waiting for scan")


def merge_pdfs(existing_path, new_pdf_bytes):
    from pypdf import PdfReader, PdfWriter

    writer = PdfWriter()
    reader = PdfReader(str(existing_path))
    for page in reader.pages:
        writer.add_page(page)
    new_reader = PdfReader(io.BytesIO(new_pdf_bytes))
    for page in new_reader.pages:
        writer.add_page(page)
    with open(existing_path, "wb") as f:
        writer.write(f)


def do_scan(mode, scan_dir):
    scan_dir.mkdir(parents=True, exist_ok=True)
    pdf_bytes = scan_page()

    if mode == "new":
        target = get_next_file(scan_dir)
        with open(target, "wb") as f:
            f.write(pdf_bytes)
    else:
        target = get_latest_file(scan_dir)
        if target.exists():
            merge_pdfs(target, pdf_bytes)
        else:
            with open(target, "wb") as f:
                f.write(pdf_bytes)

    return str(target)


def check_scripts():
    if not SUPERVISOR_TOKEN:
        return
    for script_id in ["scanner_append", "scanner_new"]:
        try:
            req = urllib.request.Request(
                f"{HA_API}/states/script.{script_id}",
                headers={"Authorization": f"Bearer {SUPERVISOR_TOKEN}"},
            )
            urllib.request.urlopen(req, timeout=5)
        except urllib.error.HTTPError:
            print(f"WARNING: script.{script_id} not found. See addon documentation for setup.", flush=True)


def main():
    if not PRINTER_IP:
        print("SCANNER_PRINTER_IP is not set", file=sys.stderr)
        sys.exit(1)
    if not SCAN_DIR_STR:
        print("SCANNER_OUTPUT_DIR is not set", file=sys.stderr)
        sys.exit(1)

    scan_dir = Path(SCAN_DIR_STR)
    print("Scanner ready, waiting for commands...", flush=True)
    set_status("idle")
    check_scripts()

    for line in sys.stdin:
        try:
            mode = json.loads(line)
        except json.JSONDecodeError:
            mode = line.strip()
        if mode not in ("append", "new"):
            print(f"Unknown command: {mode}", flush=True)
            continue

        print(f"Scanning ({mode})...", flush=True)
        set_status("scanning")
        try:
            target = do_scan(mode, scan_dir)
            print(f"Saved to {target}", flush=True)
            set_status("idle", filename=os.path.basename(target))
        except Exception as e:
            print(f"Error: {e}", flush=True)
            set_status("error")


if __name__ == "__main__":
    main()
