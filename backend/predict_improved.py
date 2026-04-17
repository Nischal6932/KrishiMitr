import tensorflow as tf
import numpy as np
import logging
from PIL import Image, ImageEnhance, ImageFilter
import cv2
import os

logger = logging.getLogger(__name__)

# Load trained model
model = tf.keras.models.load_model("plant_disease_realworld_15class_best_v4.keras")

# Class names
class_names = [
    "Pepper__bell___Bacterial_spot",
    "Pepper__bell___healthy",
    "Potato___Early_blight",
    "Potato___Late_blight",
    "Potato___healthy",
    "Tomato_Bacterial_spot",
    "Tomato_Early_blight",
    "Tomato_Late_blight",
    "Tomato_Leaf_Mold",
    "Tomato_Septoria_leaf_spot",
    "Tomato_Spider_mites",
    "Tomato_Target_Spot",
    "Tomato_Yellow_Leaf_Curl_Virus",
    "Tomato_mosaic_virus",
    "Tomato_healthy"
]

def enhance_image(image_path):
    """Enhance image for better predictions"""
    img = Image.open(image_path).convert("RGB")
    
    # Multiple enhancements
    enhanced_images = []
    
    # Original
    enhanced_images.append(img.resize((224, 224)))
    
    # Enhanced contrast
    enhancer = ImageEnhance.Contrast(img)
    enhanced_images.append(enhancer.enhance(1.5).resize((224, 224)))
    
    # Enhanced brightness
    enhancer = ImageEnhance.Brightness(img)
    enhanced_images.append(enhancer.enhance(1.2).resize((224, 224)))
    
    # Enhanced sharpness
    enhancer = ImageEnhance.Sharpness(img)
    enhanced_images.append(enhancer.enhance(1.3).resize((224, 224)))
    
    # Denoised
    denoised = img.filter(ImageFilter.UnsharpMask(radius=2, percent=150, threshold=3))
    enhanced_images.append(denoised.resize((224, 224)))
    
    return enhanced_images

def predict_with_augmentation(image_arrays):
    """Predict with multiple augmentations for better confidence"""
    all_predictions = []
    
    for img_array in image_arrays:
        # Normalize
        img_normalized = img_array / 255.0
        img_batch = np.expand_dims(img_normalized, axis=0)
        
        # Predict
        prediction = model.predict(img_batch, verbose=0).squeeze()
        all_predictions.append(prediction)
    
    # Average predictions
    avg_prediction = np.mean(all_predictions, axis=0)
    
    return avg_prediction

def test_image(image_path):
    """Test with improved preprocessing and augmentation"""
    print(f"🔍 Testing: {os.path.basename(image_path)}")
    print("-" * 40)
    
    if not os.path.exists(image_path):
        print(f"❌ Image not found: {image_path}")
        return
    
    try:
        # Enhanced images
        enhanced_images = enhance_image(image_path)
        
        # Convert to arrays
        image_arrays = [np.array(img) for img in enhanced_images]
        
        # Predict with augmentation
        prediction = predict_with_augmentation(image_arrays)
        
        # Get results
        max_probability = np.max(prediction)
        class_index = np.argmax(prediction)
        confidence = float(max_probability)
        
        # Realistic threshold
        threshold = 0.2  # 20% is more achievable
        
        if confidence < threshold:
            result = "Unknown Disease"
        else:
            result = class_names[class_index]
        
        print(f"🌿 Prediction: {result}")
        print(f"📊 Confidence: {confidence:.2%}")
        print(f"🎯 Threshold: {threshold:.0%}")
        print(f"🔧 Method: Enhanced + Augmentation")
        
        return result, confidence
        
    except Exception as e:
        print(f"❌ Error: {e}")
        return None, 0.0

def main():
    """Test with available images"""
    print("🚀 Improved Confidence Predictor")
    print("=" * 50)
    
    # Test with actual project images
    test_images = [
        "/Users/nischalmittal/Downloads/FINAL-main/synthetic_plantvillage/Tomato_healthy/Tomato_healthy_000.jpg",
        "/Users/nischalmittal/Downloads/FINAL-main/synthetic_plantvillage/Potato___healthy/Potato___healthy_041.jpg",
        "/Users/nischalmittal/Downloads/FINAL-main/synthetic_plantvillage/Tomato_Bacterial_spot/Tomato_Bacterial_spot_000.jpg"
    ]
    
    for image_path in test_images:
        result, confidence = test_image(image_path)
        if result:
            if confidence >= 0.3:
                print("✅ GOOD: 30%+ confidence achieved!")
            elif confidence >= 0.2:
                print("🟡 OK: 20%+ confidence achieved")
            else:
                print("❌ LOW: Below 20% confidence")
        print()

if __name__ == "__main__":
    main()
