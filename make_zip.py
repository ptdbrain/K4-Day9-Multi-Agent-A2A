"""Build the required submission.zip without secrets, caches, or source code."""

import json
import zipfile
from pathlib import Path


OUTPUT_DIR = Path("output")
REQUIRED_FILES = (Path("architecture.md"), Path("trace.jsonl"), Path("metadata.json"))
ZIP_NAME = Path("submission.zip")


def make_zip() -> None:
    outputs = sorted(OUTPUT_DIR.glob("EC_*.json"))
    expected = [f"EC_{number:03}.json" for number in range(1, 51)]
    if [path.name for path in outputs] != expected:
        raise SystemExit("output/ must contain exactly EC_001.json through EC_050.json")
    if missing := [str(path) for path in REQUIRED_FILES if not path.is_file()]:
        raise SystemExit(f"Missing required files: {', '.join(missing)}")

    for path in (*outputs, Path("metadata.json")):
        json.loads(path.read_text(encoding="utf-8"))
    for line_number, line in enumerate(Path("trace.jsonl").read_text(encoding="utf-8").splitlines(), 1):
        try:
            json.loads(line)
        except json.JSONDecodeError as error:
            raise SystemExit(f"Invalid trace.jsonl line {line_number}: {error}") from error

    with zipfile.ZipFile(ZIP_NAME, "w", zipfile.ZIP_DEFLATED) as archive:
        for path in outputs:
            archive.write(path, path.as_posix())
        for path in REQUIRED_FILES:
            archive.write(path, path.name)

    print(f"Built {ZIP_NAME}: 50 outputs + architecture.md + trace.jsonl + metadata.json")


if __name__ == "__main__":
    make_zip()
