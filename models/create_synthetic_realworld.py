#!/usr/bin/env python3
"""
Create synthetic real-world images for Tomato_Healthy
Uses augmentation to simulate real-world conditions from lab images
"""

import os
import random
import numpy as np
from pathlib import Path
from PIL import Image, ImageEnhance, ImageFilter, ImageOps
import warnings
warnings.filterwarnings('ignore')

DATASET_ROOT = Path("/Users/nischalmittal/Downloads/FINAL-main/plant_disease_dataset")
TRAIN_DIR = DATASET_ROOT / "train" / "Tomato_Healthy"
TEST_DIR = DATASET_ROOT / "test" / "Tomato_Healthy"
REALWORLD_DIR = DATASET_ROOT / "realworld_raw" / "Tomato_Healthy"
SYNTHETIC_DIR = DATASET_ROOT / "realworld_raw" / "Tomato_Healthy_synthetic"

def add_realistic_noise(image, intensity=0.02):
    """Add realistic sensor noise"""
    img_array = np.array(image).astype(np.float32)
    noise = np.random.normal(0, intensity * 255, img_array.shape)
    noisy = img_array + noise
    noisy = np.clip(noisy, 0, 255).astype(np.uint8)
    return Image.fromarray(noisy)

def simulate_outdoor_lighting(image):
    """Simulate outdoor lighting conditions"""
    # Random brightness adjustment (0.7 to 1.3)
    brightness_factor = random.uniform(0.7, 1.3)
    enhancer = ImageEnhance.Brightness(image)
    image = enhancer.enhance(brightness_factor)
    
    # Random contrast (0.8 to 1.2)
    contrast_factor = random.uniform(0.8, 1.2)
    enhancer = ImageEnhance.Contrast(image)
    image = enhancer.enhance(contrast_factor)
    
    # Color temperature shift (warmer or cooler)
    color_factor = random.uniform(0.85, 1.15)
    enhancer = ImageEnhance.Color(image)
    image = enhancer.enhance(color_factor)
    
    return image

def simulate_depth_of_field(image):
    """Simulate camera depth of field effects"""
    # Random slight blur to simulate focus variations
    if random.random() > 0.5:
        radius = random.uniform(0.5, 1.5)
        image = image.filter(ImageFilter.GaussianBlur(radius=radius))
    return image

def simulate_camera_angle(image):
    """Simulate different camera angles/perspectives"""
    # Random rotation (-15 to 15 degrees)
    angle = random.uniform(-15, 15)
    image = image.rotate(angle, fillcolor=(0, 0, 0), expand=False)
    return image

def simulate_weather_conditions(image):
    """Simulate various weather/lighting conditions"""
    # Randomly apply different "weather" effects
    choice = random.randint(0, 3)
    
    if choice == 0:
        # Sunny/overexposed look
        enhancer = ImageEnhance.Brightness(image)
        image = enhancer.enhance(random.uniform(1.1, 1.4))
    elif choice == 1:
        # Shadow/darker look
        enhancer = ImageEnhance.Brightness(image)
        image = enhancer.enhance(random.uniform(0.6, 0.9))
    elif choice == 2:
        # Slightly faded (older photo look)
        enhancer = ImageEnhance.Contrast(image)
        image = enhancer.enhance(random.uniform(0.7, 0.9))
    # choice == 3: keep original lighting
    
    return image

def add_background_variation(image):
    """Simulate different background complexity"""
    # Add slight vignette effect (common in real photos)
    width, height = image.size
    
    # Create vignette mask
    x = np.linspace(-1, 1, width)
    y = np.linspace(-1, 1, height)
    X, Y = np.meshgrid(x, y)
    R = np.sqrt(X**2 + Y**2)
    
    # Vignette intensity
    vignette = 1 - (R * random.uniform(0.1, 0.3))
    vignette = np.clip(vignette, 0.4, 1.0)
    
    # Apply vignette
    img_array = np.array(image).astype(np.float32)
    for i in range(3):
        img_array[:, :, i] *= vignette
    
    return Image.fromarray(img_array.astype(np.uint8))

def create_synthetic_realworld(source_image, idx):
    """Create a synthetic real-world version of a lab image"""
    # Make a copy
    img = source_image.copy()
    
    # Apply augmentations in sequence
    img = simulate_outdoor_lighting(img)        # Variable lighting
    img = simulate_camera_angle(img)             # Different angles
    img = simulate_depth_of_field(img)           # Focus variations
    img = simulate_weather_conditions(img)       # Weather effects
    img = add_background_variation(img)          # Vignette effect
    img = add_realistic_noise(img, intensity=0.015)  # Sensor noise
    
    return img

def generate_synthetic_images(target_count=50):
    """Generate synthetic real-world images"""
    print("="*70)
    print("Generating Synthetic Real-World Images for Tomato_Healthy")
    print("="*70)
    print()
    
    # Create synthetic directory
    SYNTHETIC_DIR.mkdir(parents=True, exist_ok=True)
    
    # Get existing real-world images
    existing_realworld = list(REALWORLD_DIR.glob("*.jpg")) + \
                        list(REALWORLD_DIR.glob("*.png")) + \
                        list(REALWORLD_DIR.glob("*.jpeg"))
    
    # Get source images (prefer real-world ones, then train images)
    source_images = []
    
    # Use existing real-world images as sources
    if existing_realworld:
        print(f"Using {len(existing_realworld)} existing real-world images as templates")
        for img_path in existing_realworld:
            try:
                img = Image.open(img_path)
                if img.mode != 'RGB':
                    img = img.convert('RGB')
                source_images.append(img)
            except:
                pass
    
    # Also use some lab images as sources (diverse ones)
    lab_images = list(TRAIN_DIR.glob("*.jpg"))[:30]  # First 30 lab images
    print(f"Using {len(lab_images)} lab images as additional templates")
    for img_path in lab_images:
        try:
            img = Image.open(img_path)
            if img.mode != 'RGB':
                img = img.convert('RGB')
            source_images.append(img)
        except:
            pass
    
    if not source_images:
        print("Error: No source images found!")
        return 0
    
    print(f"\nTotal source templates: {len(source_images)}")
    print(f"Target synthetic images: {target_count}")
    print()
    
    # Generate synthetic images
    generated = 0
    existing_synthetic = len(list(SYNTHETIC_DIR.glob("*.jpg")))
    
    while generated < target_count:
        # Pick a random source image
        source = random.choice(source_images)
        
        # Create synthetic variation
        synthetic = create_synthetic_realworld(source, generated)
        
        # Save
        output_path = SYNTHETIC_DIR / f"synthetic_realworld_{existing_synthetic + generated:03d}.jpg"
        synthetic.save(output_path, quality=90)
        
        generated += 1
        
        if generated % 10 == 0:
            print(f"  Generated: {generated}/{target_count}")
    
    print(f"\n✓ Generated {generated} synthetic real-world images")
    print(f"  Location: {SYNTHETIC_DIR}")
    
    return generated

def copy_to_realworld_folder():
    """Copy synthetic images to the main realworld folder"""
    print("\n" + "="*70)
    print("Copying to Real-World Folder")
    print("="*70)
    
    synthetic_images = list(SYNTHETIC_DIR.glob("*.jpg"))
    
    if not synthetic_images:
        print("No synthetic images found!")
        return 0
    
    # Copy to realworld_raw/Tomato_Healthy
    copied = 0
    existing = len(list(REALWORLD_DIR.glob("*.jpg")))
    
    for img_path in synthetic_images:
        dest = REALWORLD_DIR / f"synth_{existing + copied:03d}.jpg"
        
        # Open and re-save to ensure proper format
        img = Image.open(img_path)
        if img.mode != 'RGB':
            img = img.convert('RGB')
        img.save(dest, quality=95)
        
        copied += 1
    
    print(f"✓ Copied {copied} synthetic images to {REALWORLD_DIR}")
    
    # Count total real-world images now
    total_realworld = len(list(REALWORLD_DIR.glob("*.jpg"))) + \
                     len(list(REALWORLD_DIR.glob("*.png"))) + \
                     len(list(REALWORLD_DIR.glob("*.jpeg")))
    
    print(f"\n★ Tomato_Healthy total real-world images: {total_realworld}")
    
    return copied

if __name__ == "__main__":
    print("Synthetic Real-World Image Generator")
    print("Converting lab images to realistic field conditions")
    print()
    
    # Generate 50 synthetic images
    generated = generate_synthetic_images(target_count=50)
    
    if generated > 0:
        # Copy to realworld folder
        copied = copy_to_realworld_folder()
        
        print("\n" + "="*70)
        print("Next Step: Integrate into Dataset")
        print("="*70)
        print("Run: python3 integrate_realworld.py")
    else:
        print("\nFailed to generate synthetic images.")
