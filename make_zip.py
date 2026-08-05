"""
make_zip.py — tạo output.zip đúng chuẩn nộp bài.

Files trong ZIP phải ở ROOT (EC_001.json), KHÔNG phải trong subdir (output/EC_001.json).
Dùng script này thay vì PowerShell Compress-Archive (PowerShell lưu cả path).

Usage:
    python make_zip.py
"""
import os
import zipfile
from pathlib import Path

OUTPUT_DIR = Path("output")
ZIP_NAME = "output.zip"


def make_zip() -> None:
    files = sorted(OUTPUT_DIR.glob("EC_*.json"))
    if len(files) != 50:
        print(f"[WARNING] Found {len(files)} files, expected 50!")

    with zipfile.ZipFile(ZIP_NAME, "w", zipfile.ZIP_DEFLATED) as zf:
        for f in files:
            # arcname = only filename, no directory prefix
            zf.write(f, arcname=f.name)

    # Verify
    with zipfile.ZipFile(ZIP_NAME, "r") as z:
        names = z.namelist()
        bad = [n for n in names if "/" in n or "\\" in n]
        print(f"ZIP '{ZIP_NAME}': {len(names)} files")
        print(f"  First: {names[0]}  Last: {names[-1]}")
        if bad:
            print(f"  [ERROR] Bad paths found: {bad}")
        else:
            print("  [OK] All files at root — ready to submit!")


if __name__ == "__main__":
    make_zip()
