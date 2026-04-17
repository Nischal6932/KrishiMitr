#!/usr/bin/env python3
"""Import PlantVillage into a dedicated pretraining dataset layout."""

from __future__ import annotations

import argparse
import json
import os
import shutil
from pathlib import Path

from expected_classes import STRICT_15_CLASSES


def parse_args():
    repo_root = Path(__file__).resolve().parent.parent
    parser = argparse.ArgumentParser(description="Import PlantVillage into pretrain_plantvillage/")
    parser.add_argument(
        "--source-root",
        default="/Users/nischalmittal/Downloads/PlantVillage",
        help="Root folder containing PlantVillage class directories",
    )
    parser.add_argument(
        "--target-root",
        default=str(repo_root / "data" / "datasets" / "plant_disease_dataset" / "pretrain_plantvillage"),
        help="Target folder for the imported pretraining dataset",
    )
    parser.add_argument(
        "--mode",
        choices=["hardlink", "copy"],
        default="hardlink",
        help="Use hardlinks by default to avoid duplicating 20k+ images",
    )
    return parser.parse_args()


def discover_source_root(source_root: Path) -> Path:
    nested = source_root / "PlantVillage"
    if nested.exists() and nested.is_dir():
        nested_classes = {p.name for p in nested.iterdir() if p.is_dir()}
        if all(class_name in nested_classes for class_name in STRICT_15_CLASSES):
            return nested

    source_classes = {p.name for p in source_root.iterdir() if p.is_dir()}
    if all(class_name in source_classes for class_name in STRICT_15_CLASSES):
        return source_root

    raise SystemExit(
        f"Could not find a complete 15-class PlantVillage root under {source_root}. "
        "Expected the strict runtime class names."
    )


def ensure_layout(target_root: Path):
    target_root.mkdir(parents=True, exist_ok=True)
    for class_name in STRICT_15_CLASSES:
        (target_root / class_name).mkdir(parents=True, exist_ok=True)


def import_class(source_dir: Path, target_dir: Path, mode: str) -> int:
    count = 0
    for image_path in sorted([p for p in source_dir.iterdir() if p.is_file()]):
        target_path = target_dir / image_path.name
        if target_path.exists():
            count += 1
            continue

        if mode == "hardlink":
            try:
                os.link(image_path, target_path)
            except OSError:
                shutil.copy2(image_path, target_path)
        else:
            shutil.copy2(image_path, target_path)
        count += 1
    return count


def main():
    args = parse_args()
    source_root = discover_source_root(Path(args.source_root).resolve())
    target_root = Path(args.target_root).resolve()
    ensure_layout(target_root)

    stats = {}
    total = 0
    for class_name in STRICT_15_CLASSES:
        imported = import_class(source_root / class_name, target_root / class_name, args.mode)
        stats[class_name] = imported
        total += imported

    manifest = {
        "source_root": str(source_root),
        "target_root": str(target_root),
        "mode": args.mode,
        "total_images": total,
        "class_counts": stats,
    }
    manifest_path = target_root / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2))
    print(json.dumps(manifest, indent=2))


if __name__ == "__main__":
    main()
