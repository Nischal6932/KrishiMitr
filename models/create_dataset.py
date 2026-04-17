#!/usr/bin/env python3
"""
Download and organize Plant Disease Dataset
Sources:
1. PlantVillage (GitHub/Kaggle) - CC0 License
2. Mendeley Tomato Dataset - CC License
3. Zenodo Web-Sourced Dataset - CC-BY 4.0

Target: 100-200 images per class, 50+ real-world for Tomato_Healthy
"""

import os
import sys
import json
import urllib.request
import urllib.error
import zipfile
import tarfile
import shutil
from pathlib import Path
from collections import defaultdict

# Dataset configuration
DATASET_ROOT = Path("/Users/nischalmittal/Downloads/FINAL-main/plant_disease_dataset")

# 15 classes with target image counts
CLASSES = {
    # Tomato classes (9)
    "Tomato_Healthy": {"min": 50, "target": 200, "real_world_min": 50},
    "Tomato_Bacterial_spot": {"min": 100, "target": 200},
    "Tomato_Early_blight": {"min": 100, "target": 200},
    "Tomato_Late_blight": {"min": 100, "target": 200},
    "Tomato_Leaf_mold": {"min": 100, "target": 200},
    "Tomato_Septoria_leaf_spot": {"min": 100, "target": 200},
    "Tomato_Spider_mites": {"min": 100, "target": 200},  # Two-spotted spider mite
    "Tomato_Target_spot": {"min": 100, "target": 200},
    "Tomato_Yellow_leaf_curl_virus": {"min": 100, "target": 200},
    "Tomato_Mosaic_virus": {"min": 100, "target": 200},
    # Potato classes (3)
    "Potato_Early_blight": {"min": 100, "target": 200},
    "Potato_Late_blight": {"min": 100, "target": 200},
    "Potato_Healthy": {"min": 100, "target": 200},
    # Pepper classes (2)
    "Pepper_Bacterial_spot": {"min": 100, "target": 200},
    "Pepper_Healthy": {"min": 100, "target": 200},
}

# Dataset sources
SOURCES = {
    "plantvillage_github": {
        "url": "https://github.com/gabrieldgf4/PlantVillage-Dataset/archive/refs/heads/master.zip",
        "license": "CC0 1.0 Universal (Public Domain)",
        "description": "Primary dataset with all 15 classes"
    },
    "mendeley_tomato": {
        "url": "https://data.mendeley.com/public-files/datasets/ngdgg79rzb/files/38bc2ed9-2e45-4fd7-8eee-27bc6681363a/file_downloaded",
        "license": "Creative Commons",
        "description": "Taiwan field images for real-world variety"
    },
    "mendeley_multicrop": {
        "url": "https://data.mendeley.com/public-files/datasets/z6jp232g5j/files/",
        "license": "Creative Commons",
        "description": "Multi-crop dataset with Potato and Tomato"
    },
    "zenodo_web_sourced": {
        "url": "https://zenodo.org/records/14051480/files/web_sourced_dataset.zip",
        "license": "CC-BY 4.0",
        "description": "Real-world web images for diversity"
    }
}

# Mapping from source folder names to our class names
PLANTVILLAGE_MAPPING = {
    "Tomato___healthy": "Tomato_Healthy",
    "Tomato___Bacterial_spot": "Tomato_Bacterial_spot",
    "Tomato___Early_blight": "Tomato_Early_blight",
    "Tomato___Late_blight": "Tomato_Late_blight",
    "Tomato___Leaf_Mold": "Tomato_Leaf_mold",
    "Tomato___Septoria_leaf_spot": "Tomato_Septoria_leaf_spot",
    "Tomato___Spider_mites Two-spotted_spider_mite": "Tomato_Spider_mites",
    "Tomato___Target_Spot": "Tomato_Target_spot",
    "Tomato___Tomato_YellowLeaf__Curl_Virus": "Tomato_Yellow_leaf_curl_virus",
    "Tomato___Tomato_mosaic_virus": "Tomato_Mosaic_virus",
    "Potato___Early_blight": "Potato_Early_blight",
    "Potato___Late_blight": "Potato_Late_blight",
    "Potato___healthy": "Potato_Healthy",
    "Pepper,_bell___Bacterial_spot": "Pepper_Bacterial_spot",
    "Pepper,_bell___healthy": "Pepper_Healthy",
}

def download_file(url, dest_path, desc="Downloading"):
    """Download a file with progress"""
    try:
        print(f"{desc}: {url}")
        urllib.request.urlretrieve(url, dest_path)
        print(f"Downloaded to: {dest_path}")
        return True
    except Exception as e:
        print(f"Error downloading {url}: {e}")
        return False

def extract_archive(archive_path, extract_to):
    """Extract zip or tar archive"""
    try:
        if archive_path.endswith('.zip'):
            with zipfile.ZipFile(archive_path, 'r') as z:
                z.extractall(extract_to)
        elif archive_path.endswith(('.tar.gz', '.tgz')):
            with tarfile.open(archive_path, 'r:gz') as t:
                t.extractall(extract_to)
        print(f"Extracted: {archive_path}")
        return True
    except Exception as e:
        print(f"Error extracting {archive_path}: {e}")
        return False

def create_directories():
    """Create train and test directories for all classes"""
    splits = ['train', 'test']
    for split in splits:
        for class_name in CLASSES.keys():
            dir_path = DATASET_ROOT / split / class_name
            dir_path.mkdir(parents=True, exist_ok=True)
    print(f"Created directory structure at: {DATASET_ROOT}")

def get_dataset_stats():
    """Get current dataset statistics"""
    stats = defaultdict(lambda: {"train": 0, "test": 0, "total": 0})
    for split in ['train', 'test']:
        split_path = DATASET_ROOT / split
        if not split_path.exists():
            continue
        for class_dir in split_path.iterdir():
            if class_dir.is_dir():
                class_name = class_dir.name
                count = len(list(class_dir.glob("*.{jpg,jpeg,png,JPG,JPEG,PNG}")))
                stats[class_name][split] = count
                stats[class_name]["total"] += count
    return stats

def print_stats():
    """Print dataset statistics"""
    stats = get_dataset_stats()
    print("\n" + "="*80)
    print("DATASET STATISTICS")
    print("="*80)
    print(f"{'Class':<40} {'Train':<10} {'Test':<10} {'Total':<10} {'Target':<10}")
    print("-"*80)
    
    total_train, total_test, total_all = 0, 0, 0
    
    for class_name, targets in CLASSES.items():
        train_count = stats[class_name]["train"]
        test_count = stats[class_name]["test"]
        total_count = stats[class_name]["total"]
        target = targets["target"]
        
        total_train += train_count
        total_test += test_count
        total_all += total_count
        
        status = "✓" if total_count >= targets["min"] else "✗"
        print(f"{class_name:<40} {train_count:<10} {test_count:<10} {total_count:<10} {target:<10} {status}")
    
    print("-"*80)
    print(f"{'TOTAL':<40} {total_train:<10} {total_test:<10} {total_all:<10}")
    print("="*80)
    
    return stats

if __name__ == "__main__":
    print("Plant Disease Dataset Creator")
    print("="*50)
    create_directories()
    print("\nDirectory structure created.")
    print("\nTo download datasets:")
    print("1. Run: python3 download_plantvillage.py")
    print("2. Run: python3 download_mendeley.py")
    print("3. Run: python3 download_zenodo.py")
    print("4. Run: python3 organize_dataset.py")
    print("\nDataset sources:")
    for name, info in SOURCES.items():
        print(f"  - {name}: {info['license']}")
