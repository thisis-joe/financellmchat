from __future__ import annotations

import argparse
import csv
import shutil
import zipfile
from pathlib import Path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Extract Busan Bank product disclosure zip files.")
    parser.add_argument("--zip", required=True, type=Path, help="Source zip path")
    parser.add_argument("--dest", required=True, type=Path, help="Destination directory")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    args.dest.mkdir(parents=True, exist_ok=True)
    manifest_path = args.dest / "manifest.csv"

    rows = []
    with zipfile.ZipFile(args.zip) as zip_file:
        for info in zip_file.infolist():
            if info.is_dir():
                continue

            filename = Path(info.filename).name
            target = args.dest / filename
            with zip_file.open(info) as source, target.open("wb") as output:
                shutil.copyfileobj(source, output)

            rows.append(
                {
                    "source_zip": str(args.zip),
                    "zip_member": info.filename,
                    "stored_file": target.name,
                    "bytes": target.stat().st_size,
                }
            )

    with manifest_path.open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=["source_zip", "zip_member", "stored_file", "bytes"])
        writer.writeheader()
        writer.writerows(rows)

    print(f"extracted={len(rows)}")
    print(f"dest={args.dest}")
    print(f"manifest={manifest_path}")


if __name__ == "__main__":
    main()
