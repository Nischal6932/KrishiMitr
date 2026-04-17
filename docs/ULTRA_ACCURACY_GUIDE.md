# Ultra-Accuracy Model Training Guide

## 🎯 Target: 90%+ Accuracy

### Current vs Proposed

| Metric | Current Model | Ultra Model |
|--------|--------------|-------------|
| **Architecture** | MobileNetV3-Large | **EfficientNetV2-B3** |
| **Image Size** | 160×160 | **380×380** |
| **Test Accuracy** | 79.52% | **Target: 90%+** |
| **Top-3 Accuracy** | 96.03% | **Expected: 98%+** |
| **TTA Boost** | No | **+2-3% with TTA** |

## 🔑 Key Improvements

### 1. **Larger Input Size (380×380)**
- Current: 160×160 loses fine details
- New: 380×380 captures leaf texture patterns better
- Impact: **+3-5% accuracy**

### 2. **Better Backbone: EfficientNetV2-B3**
- Current: MobileNetV3-Large (lightweight, less powerful)
- New: EfficientNetV2-B3 (state-of-the-art, better feature extraction)
- Impact: **+4-6% accuracy**

### 3. **Progressive Training Strategy**
```
Phase 1: Frozen backbone → train classifier (5 epochs)
Phase 2: Partial unfreeze → fine-tune top 150 layers (30 epochs)  
Phase 3: Full unfreeze → fine-tune all layers (165 epochs)
```

### 4. **Aggressive Data Augmentation**
- Random flip, rotation, zoom
- Color jitter (brightness, contrast, saturation, hue)
- Random erasing/cutout simulation
- Impact: Better generalization, prevents overfitting

### 5. **Label Smoothing (0.1)**
- Prevents overconfidence on ambiguous samples
- Better calibration on hard-to-classify diseases

### 6. **Test-Time Augmentation (TTA)**
- Average predictions over 5 augmented versions
- Impact: **+2-3% accuracy boost**

### 7. **Advanced Regularization**
- L2 weight regularization
- Higher dropout (0.6)
- Batch normalization at every layer

## 🚀 How to Train

### Prerequisites
```bash
cd models
# Ensure you have TensorFlow 2.16+ installed
pip install tensorflow scikit-learn matplotlib seaborn
```

### Step 1: Update Dataset Path
Edit `train_ultra_accuracy.py` line 25:
```python
DATA_DIR = "../data/datasets/plant_disease_dataset"  # Your dataset path
```

### Step 2: Run Training
```bash
cd /Users/nischalmittal/Downloads/FINAL-main/models
python3 train_ultra_accuracy.py
```

**Expected training time:**
- With GPU: 3-6 hours
- With CPU: 20-40 hours

### Step 3: Monitor Progress
The script saves:
- `plant_disease_ultra_90plus.keras` - Best model
- `ultra_class_indices.json` - Class mappings
- `ultra_metadata.json` - Performance metrics
- TensorBoard logs in `logs/` directory

## 📊 Expected Results

| Phase | Expected Accuracy | Epochs |
|-------|------------------|--------|
| Phase 1 (Frozen) | ~75-80% | 5 |
| Phase 2 (Partial) | ~82-86% | 30 |
| Phase 3 (Full) | **88-92%** | 165 |
| With TTA | **90-94%** | - |

## 🔧 Integration with App

### Update `backend/app.py`:

```python
# Add to MODEL_CANDIDATES
MODEL_CANDIDATES = [
    "../models/plant_disease_ultra_90plus.keras",  # New ultra model
    "../models/plant_disease_realworld_15class_best_v4.keras",  # Fallback
]

# Update image preprocessing
IMG_SIZE = (380, 380)  # Was 160

# Optional: Add TTA for inference
def predict_with_tta(image, model, rounds=5):
    """Test-time augmentation prediction"""
    predictions = []
    for _ in range(rounds):
        aug_image = apply_random_augment(image)
        pred = model.predict(aug_image, verbose=0)
        predictions.append(pred)
    return np.mean(predictions, axis=0)
```

## 💡 Tips for Best Results

1. **Ensure dataset quality**: Remove blurry/dark images
2. **Class balance**: Each class should have 800+ images
3. **Use GPU**: Training on CPU will take 5-10x longer
4. **Monitor for overfitting**: Check validation loss vs training loss
5. **Early stopping**: Script has patience=30, but you can adjust

## ⚠️ Memory Requirements

| Component | Requirement |
|-----------|-------------|
| GPU VRAM | 8GB+ (RTX 3070/4060 or better) |
| System RAM | 16GB+ |
| Storage | 5GB free space |

If you have limited VRAM:
- Reduce batch_size to 8 (line 35)
- Use EfficientNetV2-B0 instead of B3 (line 135)

## 🎯 Summary

This new training approach should boost accuracy from **79.52% → 90%+** through:
- Better architecture (EfficientNetV2-B3)
- Larger input size (380×380)
- Progressive unfreezing
- Heavy augmentation
- Test-time augmentation

**Start training and monitor validation accuracy - you should see 90%+ within 100 epochs!**
