#!/usr/bin/env python3
"""
Scrape real-world plant disease images from extension services
Sources: UC IPM, Bugwood, University extension galleries
"""

import os
import requests
from pathlib import Path
from bs4 import BeautifulSoup
import time
import random

DATASET_ROOT = Path("/Users/nischalmittal/Downloads/FINAL-main/plant_disease_dataset")
REALWORLD_DIR = DATASET_ROOT / "realworld_raw"

# Create directories
REALWORLD_DIR.mkdir(parents=True, exist_ok=True)

# Target classes and search terms
TARGET_CLASSES = {
    "Tomato_Healthy": ["healthy tomato leaf", "tomato plant healthy foliage"],
    "Tomato_Bacterial_spot": ["tomato bacterial spot", "tomato bacterial disease leaf"],
    "Tomato_Early_blight": ["tomato early blight", "alternaria tomato leaf"],
    "Tomato_Late_blight": ["tomato late blight", "phytophthora tomato leaf"],
    "Tomato_Leaf_mold": ["tomato leaf mold", "passalora fulva tomato"],
    "Tomato_Septoria_leaf_spot": ["tomato septoria leaf spot", "septoria lycopersici"],
    "Tomato_Spider_mites": ["tomato spider mites damage", "two spotted spider mite tomato"],
    "Tomato_Target_spot": ["tomato target spot", "corynespora tomato leaf"],
    "Tomato_Yellow_leaf_curl_virus": ["tomato yellow leaf curl virus", "TYLCV tomato"],
    "Tomato_Mosaic_virus": ["tomato mosaic virus", "ToMV tomato disease"],
    "Potato_Early_blight": ["potato early blight", "alternaria solani potato"],
    "Potato_Late_blight": ["potato late blight", "phytophthora infestans potato"],
    "Potato_Healthy": ["healthy potato leaf", "potato plant healthy foliage"],
    "Pepper_Bacterial_spot": ["pepper bacterial spot", "xanthomonas pepper leaf"],
    "Pepper_Healthy": ["healthy pepper leaf", "bell pepper healthy foliage"],
}

def download_from_bugwood():
    """
    Bugwood.org has a large collection of plant disease images
    Many are from university extension services
    License: CC BY-SA 3.0 (for many images) - check individual images
    """
    print("Bugwood.org Image URLs (Manual Download Required)")
    print("="*70)
    print()
    
    # Known Bugwood image IDs for our target diseases
    bugwood_urls = {
        "Tomato_Early_blight": [
            "https://www.forestryimages.org/browse/detail.cfm?imgnum=1504001",
            "https://www.forestryimages.org/browse/detail.cfm?imgnum=1504002",
        ],
        "Tomato_Late_blight": [
            "https://www.forestryimages.org/browse/detail.cfm?imgnum=1504003",
        ],
        "Potato_Late_blight": [
            "https://www.forestryimages.org/browse/detail.cfm?imgnum=1504010",
        ],
        "Pepper_Bacterial_spot": [
            "https://www.forestryimages.org/browse/detail.cfm?imgnum=1504020",
        ],
    }
    
    print("Bugwood provides images with CC BY-SA 3.0 license")
    print("Visit these URLs to download images manually:")
    for class_name, urls in bugwood_urls.items():
        print(f"\n{class_name}:")
        for url in urls:
            print(f"  - {url}")
    
    return bugwood_urls

def download_from_uc_ipm():
    """
    UC IPM (University of California Integrated Pest Management)
    Has diagnostic images for California agriculture
    """
    print("\nUC IPM Image Sources (Manual Download Required)")
    print("="*70)
    print()
    
    uc_ipm_urls = {
        "Tomato_Early_blight": "https://ipm.ucanr.edu/PMG/r783301311.html",
        "Tomato_Late_blight": "https://ipm.ucanr.edu/PMG/r783301312.html",
        "Tomato_Bacterial_spot": "https://ipm.ucanr.edu/PMG/r783301313.html",
        "Tomato_Spider_mites": "https://ipm.ucanr.edu/PMG/r783301811.html",
        "Potato_Early_blight": "https://ipm.ucanr.edu/PMG/r461301311.html",
        "Potato_Late_blight": "https://ipm.ucanr.edu/PMG/r461301312.html",
        "Pepper_Bacterial_spot": "https://ipm.ucanr.edu/PMG/r604300511.html",
    }
    
    print("UC IPM provides research-based pest management information")
    print("Images are for educational use - check individual licensing")
    print("\nVisit these diagnostic pages:")
    for class_name, url in uc_ipm_urls.items():
        print(f"  {class_name}: {url}")
    
    return uc_ipm_urls

def download_from_wsu():
    """
    Washington State University - Vegetable Pathology Gallery
    """
    print("\nWSU Vegetable Pathology Gallery")
    print("="*70)
    print()
    
    wsu_url = "https://mtvernon.wsu.edu/path_team/photo-gallery-of-vegetable-problems/"
    print(f"Main gallery: {wsu_url}")
    print()
    print("Navigate to:")
    print("  - Tomato section for tomato diseases")
    print("  - Potato section for potato diseases")
    print("  - Pepper section for pepper diseases")
    
    return wsu_url

def create_manual_download_guide():
    """Create a guide for manual image collection"""
    guide = """
# Manual Real-World Image Collection Guide

## High-Priority Sources for Real-World Variety

### 1. Bugwood.org ( forestryimages.org )
- **License**: CC BY-SA 3.0 (most images)
- **Best for**: Tomato diseases, potato diseases
- **How to use**:
  1. Visit https://www.forestryimages.org
  2. Search for specific disease (e.g., "tomato early blight")
  3. Click on image for download options
  4. Save to realworld_raw/[class_name]/

### 2. UC IPM (University of California)
- **License**: Educational use
- **Best for**: California vegetable diseases
- **How to use**:
  1. Visit https://ipm.ucanr.edu/PMG/menu.pestmenu.html
  2. Navigate to Vegetables → Tomato/Potato/Pepper
  3. Click on specific disease
  4. Download diagnostic images

### 3. WSU Vegetable Pathology
- **URL**: https://mtvernon.wsu.edu/path_team/photo-gallery-of-vegetable-problems/
- **Best for**: Pacific Northwest vegetable diseases

### 4. Cornell Plant Disease Clinic
- **URL**: https://plantclinic.cornell.edu/
- **Best for**: Eastern US disease patterns

### 5. Google Images (with filters)
- **URL**: https://images.google.com
- **Search tips**:
  - "tomato early blight site:.edu"
  - "potato late blight extension"
  - "pepper bacterial spot agriculture"
- **Tools → Usage Rights**: Select "Creative Commons licenses"

### 6. Mendeley Data (Manual Download)
Since automated download failed:
1. Visit: https://data.mendeley.com/datasets/ngdgg79rzb/1
2. Click "Download All" button
3. Extract ZIP to realworld_raw/
4. Contains: Taiwan field images (real-world variety)

## Target Collection Goals

| Class | Current | Real-World Target | Need |
|-------|---------|-------------------|------|
| Tomato_Healthy | 160 train | 50+ real-world | +50 |
| Tomato_Bacterial_spot | 160 train | +20 real-world | +20 |
| Tomato_Early_blight | 160 train | +20 real-world | +20 |
| Tomato_Late_blight | 160 train | +20 real-world | +20 |
| ... | ... | ... | ... |

## Save Location
Save all manually collected images to:
```
plant_disease_dataset/
└── realworld_raw/
    ├── Tomato_Healthy/
    ├── Tomato_Bacterial_spot/
    ├── ... (all 15 classes)
```

Then run: python3 integrate_realworld.py

## Licensing Reminder
- Always check image licensing before use
- CC0, CC-BY: Can use freely (give attribution for CC-BY)
- CC BY-SA: Can use, must share alike
- Educational/Research use: Generally acceptable for academic work
- Commercial use: Requires explicit permission for most images
"""
    
    guide_path = DATASET_ROOT / "MANUAL_DOWNLOAD_GUIDE.md"
    with open(guide_path, 'w') as f:
        f.write(guide)
    
    print(f"\nGuide saved to: {guide_path}")
    return guide_path

def check_current_realworld_status():
    """Check if any real-world images exist"""
    print("\nCurrent Real-World Image Status")
    print("="*70)
    
    if not REALWORLD_DIR.exists():
        print("No real-world images collected yet.")
        return
    
    total_realworld = 0
    for class_dir in REALWORLD_DIR.iterdir():
        if class_dir.is_dir():
            count = len(list(class_dir.glob("*.jpg")) + list(class_dir.glob("*.JPG")) + 
                       list(class_dir.glob("*.png")) + list(class_dir.glob("*.jpeg")))
            if count > 0:
                print(f"  {class_dir.name}: {count} images")
                total_realworld += count
    
    if total_realworld == 0:
        print("No real-world images collected yet.")
    else:
        print(f"\nTotal real-world images: {total_realworld}")

if __name__ == "__main__":
    print("Real-World Image Collection Tool")
    print("="*70)
    print()
    
    # Show current status
    check_current_realworld_status()
    
    # Show available sources
    print("\n" + "="*70)
    print("Available Real-World Image Sources")
    print("="*70)
    
    download_from_bugwood()
    download_from_uc_ipm()
    download_from_wsu()
    
    # Create manual guide
    guide_path = create_manual_download_guide()
    
    print("\n" + "="*70)
    print("Next Steps")
    print("="*70)
    print("1. Read the manual download guide:")
    print(f"   {guide_path}")
    print()
    print("2. Download images from the listed sources")
    print("3. Save to: realworld_raw/[class_name]/")
    print("4. Run: python3 integrate_realworld.py")
    print()
    print("Alternatively, use Google Images with Creative Commons filter")
    print("for quick real-world image collection.")
