#!/usr/bin/env python3
"""Build a potato-specialist dataset from the locally available sources."""

from __future__ import annotations

import json
import random
import shutil
from collections import defaultdict
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
DEFAULT_SOURCE_ROOT = Path("/Users/nischalmittal/Downloads/Datasett")
DEFAULT_TARGET_ROOT = ROOT / "data" / "datasets" / "plant_disease_dataset" / "potato_specialist"
SEED = 42

CLASS_NAMES = [
    "Potato___Early_blight",
    "Potato___Late_blight",
    "Potato___healthy",
]

PRIMARY_SOURCE_MAP = {
    "earlyblt": "Potato___Early_blight",
    "lateblt": "Potato___Late_blight",
    "healthy": "Potato___healthy",
}

FIELD_SOURCE_MAP = {
    "Healthy": "Potato___healthy",
    "Phytopthora": "Potato___Late_blight",
}

PLANTVILLAGE_SOURCE_MAP = {
    "Potato___Early_blight": "Potato___Early_blight",
    "Potato___Late_blight": "Potato___Late_blight",
    "Potato___healthy": "Potato___healthy",
}

IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png", ".bmp", ".webp", ".JPG", ".JPEG", ".PNG", ".BMP", ".WEBP"}


def iter_images(directory: Path):
    for path in sorted(directory.rglob("*")):
        if path.is_file() and path.suffix in IMAGE_SUFFIXES:
            yield path


def ensure_structure(target_root: Path):
    split_names = ["train", "val", "test", "field_finetune", "field_val", "field_test"]
    for split in split_names:
        for class_name in CLASS_NAMES:
            (target_root / split / class_name).mkdir(parents=True, exist_ok=True)


def clear_previous(target_root: Path):
    if not target_root.exists():
        return
    for child in target_root.iterdir():
        if child.is_dir():
            shutil.rmtree(child)
        else:
            child.unlink()


def write_link_or_copy(source: Path, target: Path):
    target.parent.mkdir(parents=True, exist_ok=True)
    try:
        target.hardlink_to(source)
    except Exception:
        shutil.copy2(source, target)


def allocate_primary_splits(paths, seed: int):
    rng = random.Random(seed)
    shuffled = list(paths)
    rng.shuffle(shuffled)
    n = len(shuffled)
    train_end = int(n * 0.8)
    val_end = train_end + int(n * 0.1)
    return {
        "train": shuffled[:train_end],
        "val": shuffled[train_end:val_end],
        "test": shuffled[val_end:],
    }


def allocate_field_splits(paths, seed: int):
    rng = random.Random(seed)
    shuffled = list(paths)
    rng.shuffle(shuffled)
    n = len(shuffled)
    finetune_end = int(n * 0.6)
    val_end = finetune_end + int(n * 0.2)
    return {
        "field_finetune": shuffled[:finetune_end],
        "field_val": shuffled[finetune_end:val_end],
        "field_test": shuffled[val_end:],
    }


def import_primary(source_root: Path, target_root: Path, manifest: dict):
    primary_root = source_root / "8286529"
    for source_name, class_name in PRIMARY_SOURCE_MAP.items():
        image_paths = list(iter_images(primary_root / source_name))
        split_map = allocate_primary_splits(image_paths, SEED)
        for split_name, split_paths in split_map.items():
            for idx, image_path in enumerate(split_paths):
                target_path = target_root / split_name / class_name / f"{source_name}_{idx:06d}{image_path.suffix.lower()}"
                write_link_or_copy(image_path, target_path)
        manifest["primary"][class_name] = {split_name: len(split_paths) for split_name, split_paths in split_map.items()}


def import_field(source_root: Path, target_root: Path, manifest: dict):
    field_root = source_root / "Potato Leaf Disease Dataset in Uncontrolled Environment"
    for source_name, class_name in FIELD_SOURCE_MAP.items():
        image_paths = list(iter_images(field_root / source_name))
        split_map = allocate_field_splits(image_paths, SEED)
        for split_name, split_paths in split_map.items():
            for idx, image_path in enumerate(split_paths):
                target_path = target_root / split_name / class_name / f"{source_name.lower()}_{idx:05d}{image_path.suffix.lower()}"
                write_link_or_copy(image_path, target_path)
        manifest["field"][class_name] = {split_name: len(split_paths) for split_name, split_paths in split_map.items()}


def import_plantvillage(source_root: Path, target_root: Path, manifest: dict):
    pv_root = source_root / "PlantVillage"
    if (pv_root / "PlantVillage").exists():
        pv_root = pv_root / "PlantVillage"
    for source_name, class_name in PLANTVILLAGE_SOURCE_MAP.items():
        image_paths = list(iter_images(pv_root / source_name))
        for idx, image_path in enumerate(image_paths):
            target_path = target_root / "train" / class_name / f"plantvillage_{idx:05d}{image_path.suffix.lower()}"
            write_link_or_copy(image_path, target_path)
        manifest["plantvillage"][class_name] = len(image_paths)


def summarize_target(target_root: Path):
    summary = defaultdict(dict)
    for split_dir in sorted([p for p in target_root.iterdir() if p.is_dir()]):
        for class_dir in sorted([p for p in split_dir.iterdir() if p.is_dir()]):
            summary[split_dir.name][class_dir.name] = sum(1 for _ in class_dir.iterdir())
    return summary


def main():
    source_root = DEFAULT_SOURCE_ROOT
    target_root = DEFAULT_TARGET_ROOT

    clear_previous(target_root)
    ensure_structure(target_root)

    manifest = {
        "source_root": str(source_root),
        "target_root": str(target_root),
        "class_names": CLASS_NAMES,
        "primary": {},
        "field": {},
        "plantvillage": {},
    }

    import_primary(source_root, target_root, manifest)
    import_field(source_root, target_root, manifest)
    import_plantvillage(source_root, target_root, manifest)
    manifest["final_counts"] = summarize_target(target_root)

    manifest_path = target_root / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(json.dumps(manifest, indent=2))


if __name__ == "__main__":
    main()
