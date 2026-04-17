#!/usr/bin/env python3
"""
Integrate real-world images into the train/test dataset
Ensures Tomato_Healthy gets 50+ real-world images
"""

import os
import shutil
import random
from pathlib import Path
from collections import defaultdict

DATASET_ROOT = Path("/Users/nischalmittal/Downloads/FINAL-main/plant_disease_dataset")
REALWORLD_DIR = DATASET_ROOT / "realworld_raw"
TRAIN_DIR = DATASET_ROOT / "train"
TEST_DIR = DATASET_ROOT / "test"

# Target real-world counts per class
REALWORLD_TARGETS = {
    "Tomato_Healthy": 60,  # Priority: ensure 50+ real-world
    "Tomato_Bacterial_spot": 20,
    "Tomato_Early_blight": 20,
    "Tomato_Late_blight": 20,
    "Tomato_Leaf_mold": 15,
    "Tomato_Septoria_leaf_spot": 15,
    "Tomato_Spider_mites": 15,
    "Tomato_Target_spot": 15,
    "Tomato_Yellow_leaf_curl_virus": 15,
    "Tomato_Mosaic_virus": 15,
    "Potato_Early_blight": 20,
    "Potato_Late_blight": 20,
    "Potato_Healthy": 20,
    "Pepper_Bacterial_spot": 20,
    "Pepper_Healthy": 20,
}

def integrate_realworld_images():
    """Add real-world images to train/test splits"""
    print("="*70)
    print("Integrating Real-World Images")
    print("="*70)
    print()
    
    if not REALWORLD_DIR.exists():
        print(f"No real-world images found at: {REALWORLD_DIR}")
        print("Please collect real-world images first using:")
        print("  python3 collect_realworld.py")
        return
    
    stats = {}
    total_added = 0
    
    for class_name, target_count in REALWORLD_TARGETS.items():
        class_realworld = REALWORLD_DIR / class_name
        
        if not class_realworld.exists():
            print(f"✗ {class_name}: No real-world images found")
            stats[class_name] = 0
            continue
        
        # Get real-world images
        images = []
        for ext in ["*.jpg", "*.jpeg", "*.png", "*.JPG", "*.JPEG", "*.PNG"]:
            images.extend(class_realworld.glob(ext))
        
        if not images:
            print(f"✗ {class_name}: No images in directory")
            stats[class_name] = 0
            continue
        
        # Shuffle and select
        random.seed(42)
        random.shuffle(images)
        selected = images[:target_count]
        
        # Split: 80% train, 20% test
        n_test = max(1, int(len(selected) * 0.2))
        n_train = len(selected) - n_test
        
        train_images = selected[:n_train]
        test_images = selected[n_train:]
        
        # Copy to train
        train_target = TRAIN_DIR / class_name
        train_target.mkdir(parents=True, exist_ok=True)
        for img in train_images:
            dest = train_target / f"realworld_{img.name}"
            if not dest.exists():
                shutil.copy2(img, dest)
        
        # Copy to test
        test_target = TEST_DIR / class_name
        test_target.mkdir(parents=True, exist_ok=True)
        for img in test_images:
            dest = test_target / f"realworld_{img.name}"
            if not dest.exists():
                shutil.copy2(img, dest)
        
        added = len(selected)
        stats[class_name] = added
        total_added += added
        
        print(f"✓ {class_name}: +{added} images ({n_train} train, {n_test} test)")
    
    print()
    print(f"Total real-world images added: {total_added}")
    return stats

def print_updated_stats():
    """Print updated dataset statistics"""
    print("\n" + "="*70)
    print("UPDATED DATASET STATISTICS")
    print("="*70)
    print(f"{'Class':<40} {'Train':<8} {'Test':<8} {'Total':<8}")
    print("-"*70)
    
    total_train = 0
    total_test = 0
    total_all = 0
    
    for class_name in sorted(REALWORLD_TARGETS.keys()):
        train_dir = TRAIN_DIR / class_name
        test_dir = TEST_DIR / class_name
        
        train_count = len(list(train_dir.glob("*"))) if train_dir.exists() else 0
        test_count = len(list(test_dir.glob("*"))) if test_dir.exists() else 0
        total_count = train_count + test_count
        
        total_train += train_count
        total_test += test_count
        total_all += total_count
        
        # Highlight Tomato_Healthy
        marker = " ★" if class_name == "Tomato_Healthy" else ""
        print(f"{class_name:<40} {train_count:<8} {test_count:<8} {total_count:<8}{marker}")
    
    print("-"*70)
    print(f"{'TOTAL':<40} {total_train:<8} {total_test:<8} {total_all:<8}")
    print("="*70)
    
    # Check Tomato_Healthy specifically
    tomato_healthy_train = TRAIN_DIR / "Tomato_Healthy"
    if tomato_healthy_train.exists():
        images = list(tomato_healthy_train.glob("*"))
        realworld_count = len([img for img in images if img.name.startswith("realworld_")])
        print(f"\n★ Tomato_Healthy real-world images: {realworld_count}")
        print(f"  Target: 50+ real-world images")
        if realworld_count >= 50:
            print(f"  Status: ✓ TARGET MET")
        else:
            print(f"  Status: ✗ Need {50 - realworld_count} more real-world images")

if __name__ == "__main__":
    stats = integrate_realworld_images()
    
    if stats:
        print_updated_stats()
        
        print("\n" + "="*70)
        print("Integration Complete!")
        print("="*70)
        print("Real-world images have been added to train/test folders.")
        print("Images are prefixed with 'realworld_' for identification.")
    else:
        print("\n" + "="*70)
        print("Quick Real-World Image Collection")
        print("="*70)
        print()
        print("To quickly add real-world images:")
        print()
        print("1. Google Images (fastest method):")
        print("   - Visit: https://images.google.com")
        print("   - Search: 'tomato healthy leaf' + click Tools → Usage Rights → Creative Commons")
        print("   - Download 50-60 images of healthy tomato plants")
        print("   - Save to: realworld_raw/Tomato_Healthy/")
        print()
        print("2. Repeat for other classes (20 images each)")
        print()
        print("3. Run: python3 integrate_realworld.py")
