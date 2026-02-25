#!/usr/bin/env python3
"""Scanner automation script for HP printers via eSCL protocol.

Usage:
  scan.py append   - Scan and append to today's document
  scan.py new      - Scan to a new document
  scan.py serve    - Run HTTP server (for HA addon)

Environment variables:
  SCANNER_PRINTER_IP   - Printer IP address (required)
  SCANNER_OUTPUT_DIR   - Directory to save scanned PDFs (required)
  SCANNER_RESOLUTION   - Scan resolution in DPI (default: 300)
"""

import io
import json
import os
import sys
import time
import urllib.error
import urllib.request
from datetime import date
from http.server import HTTPServer, BaseHTTPRequestHandler
from pathlib import Path

PRINTER_IP = os.environ.get("SCANNER_PRINTER_IP")
SCAN_DIR_STR = os.environ.get("SCANNER_OUTPUT_DIR")
RESOLUTION = int(os.environ.get("SCANNER_RESOLUTION", "300"))

# A4 dimensions in 300ths of inches
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


class ScanHandler(BaseHTTPRequestHandler):
    def do_POST(self):
        path = self.path.strip("/")
        if path not in ("scan/append", "scan/new"):
            self.send_response(404)
            self.end_headers()
            return

        mode = path.split("/")[1]
        scan_dir = Path(SCAN_DIR_STR)

        try:
            target = do_scan(mode, scan_dir)
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"file": target}).encode())
        except Exception as e:
            self.send_response(500)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"error": str(e)}).encode())

    def log_message(self, format, *args):
        print(format % args, flush=True)


def main():
    if len(sys.argv) != 2 or sys.argv[1] not in ("append", "new", "serve"):
        print("Usage: scan.py [append|new|serve]", file=sys.stderr)
        sys.exit(1)

    if not PRINTER_IP:
        print("SCANNER_PRINTER_IP is not set", file=sys.stderr)
        sys.exit(1)
    if not SCAN_DIR_STR:
        print("SCANNER_OUTPUT_DIR is not set", file=sys.stderr)
        sys.exit(1)

    if sys.argv[1] == "serve":
        server = HTTPServer(("0.0.0.0", 8099), ScanHandler)
        print(f"Scanner server listening on port 8099", flush=True)
        server.serve_forever()
    else:
        mode = sys.argv[1]
        scan_dir = Path(SCAN_DIR_STR)
        target = do_scan(mode, scan_dir)
        print(f"Saved to {target}")


if __name__ == "__main__":
    main()
