#!/usr/bin/env python3
"""Simple and robust training script for PlantVillage dataset."""

import json
import os
import sys
from pathlib import Path
from typing import Dict, List, Tuple
import numpy as np
import tensorflow as tf
from sklearn.utils import class_weight
from sklearn.model_selection import train_test_split

os.environ.setdefault("MPLCONFIGDIR", "/tmp")

# Import existing utilities
from expected_classes import STRICT_15_CLASSES

# Dataset mapping
DATASET_LABEL_MAP = {
    "Pepper_Bacterial_spot": ("Pepper", "Pepper__bell___Bacterial_spot"),
    "Pepper_Healthy": ("Pepper", "Pepper__bell___healthy"),
    "Potato_Early_blight": ("Potato", "Potato___Early_blight"),
    "Potato_Healthy": ("Potato", "Potato___healthy"),
    "Potato_Late_blight": ("Potato", "Potato___Late_blight"),
    "Tomato_Bacterial_spot": ("Tomato", "Tomato_Bacterial_spot"),
    "Tomato_Early_blight": ("Tomato", "Tomato_Early_blight"),
    "Tomato_Healthy": ("Tomato", "Tomato_healthy"),
    "Tomato_Late_blight": ("Tomato", "Tomato_Late_blight"),
    "Tomato_Leaf_mold": ("Tomato", "Tomato_Leaf_Mold"),
    "Tomato_Mosaic_virus": ("Tomato", "Tomato__Tomato_mosaic_virus"),
    "Tomato_Septoria_leaf_spot": ("Tomato", "Tomato_Septoria_leaf_spot"),
    "Tomato_Spider_mites": ("Tomato", "Tomato_Spider_mites_Two_spotted_spider_mite"),
    "Tomato_Target_spot": ("Tomato", "Tomato__Target_Spot"),
    "Tomato_Yellow_leaf_curl_virus": ("Tomato", "Tomato__Tomato_YellowLeaf__Curl_Virus"),
}

def load_dataset(data_dir: Path, image_size=(160, 160)):
    """Load dataset from directory."""
    images = []
    labels = []
    
    for class_dir in sorted([p for p in data_dir.iterdir() if p.is_dir()]):
        if class_dir.name not in DATASET_LABEL_MAP:
            continue
            
        crop, label = DATASET_LABEL_MAP[class_dir.name]
        label_idx = STRICT_15_CLASSES.index(label)
        
        for image_path in class_dir.iterdir():
            if image_path.suffix.lower() in ['.jpg', '.jpeg', '.png']:
                try:
                    # Load and preprocess image
                    image = tf.keras.preprocessing.image.load_img(
                        image_path, target_size=image_size
                    )
                    image_array = tf.keras.preprocessing.image.img_to_array(image)
                    image_array = image_array / 255.0  # Normalize
                    
                    images.append(image_array)
                    labels.append(label_idx)
                except Exception as e:
                    print(f"Warning: Could not load {image_path}: {e}")
                    continue
    
    return np.array(images), np.array(labels)

def create_simple_model(input_shape=(160, 160, 3), num_classes=15):
    """Create a simple but effective CNN model."""
    inputs = tf.keras.layers.Input(shape=input_shape)
    
    # Data augmentation layer (simplified)
    data_augmentation = tf.keras.Sequential([
        tf.keras.layers.RandomFlip("horizontal"),
        tf.keras.layers.RandomRotation(0.1),
        tf.keras.layers.RandomZoom(0.1),
        tf.keras.layers.RandomContrast(0.1),
    ])
    
    # Apply augmentation only during training
    x = data_augmentation(inputs)
    
    # Feature extraction
    x = tf.keras.layers.Conv2D(32, 3, activation='relu', padding='same')(x)
    x = tf.keras.layers.BatchNormalization()(x)
    x = tf.keras.layers.Conv2D(32, 3, activation='relu', padding='same')(x)
    x = tf.keras.layers.BatchNormalization()(x)
    x = tf.keras.layers.MaxPooling2D()(x)
    x = tf.keras.layers.Dropout(0.25)(x)
    
    x = tf.keras.layers.Conv2D(64, 3, activation='relu', padding='same')(x)
    x = tf.keras.layers.BatchNormalization()(x)
    x = tf.keras.layers.Conv2D(64, 3, activation='relu', padding='same')(x)
    x = tf.keras.layers.BatchNormalization()(x)
    x = tf.keras.layers.MaxPooling2D()(x)
    x = tf.keras.layers.Dropout(0.25)(x)
    
    x = tf.keras.layers.Conv2D(128, 3, activation='relu', padding='same')(x)
    x = tf.keras.layers.BatchNormalization()(x)
    x = tf.keras.layers.Conv2D(128, 3, activation='relu', padding='same')(x)
    x = tf.keras.layers.BatchNormalization()(x)
    x = tf.keras.layers.MaxPooling2D()(x)
    x = tf.keras.layers.Dropout(0.3)(x)
    
    x = tf.keras.layers.GlobalAveragePooling2D()(x)
    x = tf.keras.layers.Dense(256, activation='relu')(x)
    x = tf.keras.layers.BatchNormalization()(x)
    x = tf.keras.layers.Dropout(0.5)(x)
    
    outputs = tf.keras.layers.Dense(num_classes, activation='softmax')(x)
    
    model = tf.keras.Model(inputs, outputs)
    return model

def create_mobilenet_model(input_shape=(160, 160, 3), num_classes=15):
    """Create MobileNetV3-based model."""
    # Create data augmentation
    data_augmentation = tf.keras.Sequential([
        tf.keras.layers.RandomFlip("horizontal"),
        tf.keras.layers.RandomRotation(0.1),
        tf.keras.layers.RandomZoom(0.1),
        tf.keras.layers.RandomContrast(0.1),
    ])
    
    # Create base model
    base_model = tf.keras.applications.MobileNetV3Small(
        input_shape=input_shape,
        include_top=False,
        weights='imagenet'
    )
    
    # Freeze base model initially
    base_model.trainable = False
    
    inputs = tf.keras.layers.Input(shape=input_shape)
    x = data_augmentation(inputs)
    x = tf.keras.applications.mobilenet_v3.preprocess_input(x)
    x = base_model(x, training=False)
    x = tf.keras.layers.GlobalAveragePooling2D()(x)
    x = tf.keras.layers.Dropout(0.2)(x)
    x = tf.keras.layers.Dense(128, activation='relu')(x)
    x = tf.keras.layers.Dropout(0.5)(x)
    outputs = tf.keras.layers.Dense(num_classes, activation='softmax')(x)
    
    model = tf.keras.Model(inputs, outputs)
    return model, base_model

def train_and_evaluate(model, X_train, y_train, X_val, y_val, class_weights, model_name, epochs=30):
    """Train and evaluate a model."""
    print(f"\nTraining {model_name}...")
    
    # Compile model
    model.compile(
        optimizer=tf.keras.optimizers.Adam(learning_rate=0.001),
        loss='sparse_categorical_crossentropy',
        metrics=['accuracy']
    )
    
    # Callbacks
    callbacks = [
        tf.keras.callbacks.EarlyStopping(patience=10, restore_best_weights=True, monitor='val_accuracy'),
        tf.keras.callbacks.ReduceLROnPlateau(factor=0.5, patience=5, min_lr=1e-6, monitor='val_accuracy'),
        tf.keras.callbacks.ModelCheckpoint(
            f'best_{model_name}.keras',
            save_best_only=True,
            monitor='val_accuracy',
            verbose=1
        )
    ]
    
    # Train
    history = model.fit(
        X_train, y_train,
        validation_data=(X_val, y_val),
        epochs=epochs,
        batch_size=32,
        class_weight=class_weights,
        callbacks=callbacks,
        verbose=1
    )
    
    # Evaluate
    test_loss, test_acc = model.evaluate(X_val, y_val, verbose=0)
    print(f"{model_name} - Test Accuracy: {test_acc:.4f}")
    
    return model, history, test_acc

def main():
    """Main training function."""
    models_dir = Path(__file__).resolve().parent
    plantvillage_dir = models_dir.parent / "data" / "datasets" / "plant_disease_dataset" / "raw" / "plantvillage"
    
    if not plantvillage_dir.exists():
        print(f"Error: PlantVillage dataset not found at {plantvillage_dir}")
        sys.exit(1)
    
    print("Loading PlantVillage dataset...")
    X, y = load_dataset(plantvillage_dir)
    print(f"Loaded {len(X)} images with {len(np.unique(y))} classes")
    
    # Split data
    X_train, X_val, y_train, y_val = train_test_split(
        X, y, test_size=0.2, stratify=y, random_state=42
    )
    
    # Calculate class weights
    class_weights = class_weight.compute_class_weight(
        'balanced',
        classes=np.unique(y_train),
        y=y_train
    )
    class_weight_dict = dict(enumerate(class_weights))
    
    print(f"Training set: {len(X_train)} images")
    print(f"Validation set: {len(X_val)} images")
    
    # Train models
    models_to_train = [
        ("simple_cnn", create_simple_model()),
        ("mobilenetv3", create_mobilenet_model()[0])
    ]
    
    results = {}
    
    for model_name, model in models_to_train:
        try:
            trained_model, history, test_acc = train_and_evaluate(
                model, X_train, y_train, X_val, y_val, class_weight_dict, model_name, epochs=30
            )
            
            results[model_name] = {
                'test_accuracy': float(test_acc),
                'epochs_trained': len(history.history['accuracy']),
                'final_train_accuracy': float(history.history['accuracy'][-1]),
                'final_val_accuracy': float(history.history['val_accuracy'][-1])
            }
            
            print(f"Successfully trained {model_name} with accuracy {test_acc:.4f}")
            
        except Exception as e:
            print(f"Error training {model_name}: {str(e)}")
            results[model_name] = {'error': str(e), 'test_accuracy': 0.0}
    
    # Save results
    results_file = models_dir / "simple_training_results.json"
    with results_file.open('w') as f:
        json.dump(results, f, indent=2)
    
    print(f"\n{'='*50}")
    print("TRAINING COMPLETED")
    print(f"{'='*50}")
    print("Results saved to:", results_file)
    
    # Show results
    for model_name, metrics in results.items():
        if 'error' in metrics:
            print(f"{model_name}: FAILED - {metrics['error']}")
        else:
            print(f"{model_name}: Accuracy={metrics['test_accuracy']:.4f}")
    
    # Find best model
    valid_results = {k: v for k, v in results.items() if 'error' not in v}
    if valid_results:
        best_model = max(valid_results.items(), key=lambda x: x[1]['test_accuracy'])
        print(f"\nBEST MODEL: {best_model[0]} with accuracy {best_model[1]['test_accuracy']:.4f}")

if __name__ == "__main__":
    main()
