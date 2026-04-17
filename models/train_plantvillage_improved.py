#!/usr/bin/env python3
"""Improved training script for PlantVillage dataset with data augmentation and class balancing."""

import json
import os
import sys
from pathlib import Path
from typing import Dict, List, Tuple
import numpy as np
import tensorflow as tf
from sklearn.utils import class_weight
from sklearn.metrics import classification_report, confusion_matrix
import matplotlib.pyplot as plt
import seaborn as sns

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

def create_enhanced_data_augmentation(image_size=(160, 160)):
    """Create enhanced data augmentation pipeline."""
    augmentation_layers = tf.keras.Sequential([
        tf.keras.layers.Rescaling(1./255),
        tf.keras.layers.RandomFlip("horizontal_and_vertical"),
        tf.keras.layers.RandomRotation(0.2),
        tf.keras.layers.RandomZoom(0.2),
        tf.keras.layers.RandomContrast(0.2),
        tf.keras.layers.RandomBrightness(0.2),
        tf.keras.layers.GaussianNoise(0.01),
        tf.keras.layers.RandomTranslation(0.1, 0.1),
    ])
    
    def augment(image):
        # Apply augmentation
        image = augmentation_layers(image)
        return image
    
    return augment

def create_balanced_dataset(data_dir: Path, image_size=(160, 160), batch_size=32, validation_split=0.2):
    """Create balanced dataset with proper train/validation split."""
    # Get all file paths and labels
    all_filepaths = []
    all_labels = []
    
    for class_dir in sorted([p for p in data_dir.iterdir() if p.is_dir()]):
        if class_dir.name not in DATASET_LABEL_MAP:
            continue
            
        crop, label = DATASET_LABEL_MAP[class_dir.name]
        label_idx = STRICT_15_CLASSES.index(label)
        
        for image_path in class_dir.iterdir():
            if image_path.suffix.lower() in ['.jpg', '.jpeg', '.png']:
                all_filepaths.append(str(image_path))
                all_labels.append(label_idx)
    
    # Convert to numpy arrays
    all_filepaths = np.array(all_filepaths)
    all_labels = np.array(all_labels)
    
    # Calculate class weights for balancing
    class_weights = class_weight.compute_class_weight(
        'balanced',
        classes=np.unique(all_labels),
        y=all_labels
    )
    class_weight_dict = dict(enumerate(class_weights))
    
    # Split data
    from sklearn.model_selection import train_test_split
    train_paths, val_paths, train_labels, val_labels = train_test_split(
        all_filepaths, all_labels, test_size=validation_split, stratify=all_labels, random_state=42
    )
    
    # Create TensorFlow datasets
    def load_and_preprocess(path, label, training=True):
        image = tf.io.read_file(path)
        image = tf.image.decode_jpeg(image, channels=3)
        image = tf.image.resize(image, image_size)
        
        if training:
            # Apply augmentation
            image = tf.image.random_flip_left_right(image)
            image = tf.image.random_flip_up_down(image)
            image = tf.image.random_brightness(image, 0.2)
            image = tf.image.random_contrast(image, 0.8, 1.2)
            image = tf.image.random_saturation(image, 0.8, 1.2)
            # Use keras layers for rotation instead of tf.image
            image = tf.keras.layers.RandomRotation(0.2)(image)
        
        image = tf.cast(image, tf.float32) / 255.0
        return image, label
    
    train_dataset = tf.data.Dataset.from_tensor_slices((train_paths, train_labels))
    train_dataset = train_dataset.map(
        lambda x, y: load_and_preprocess(x, y, training=True),
        num_parallel_calls=tf.data.AUTOTUNE
    )
    train_dataset = train_dataset.shuffle(buffer_size=len(train_paths))
    train_dataset = train_dataset.batch(batch_size).prefetch(tf.data.AUTOTUNE)
    
    val_dataset = tf.data.Dataset.from_tensor_slices((val_paths, val_labels))
    val_dataset = val_dataset.map(
        lambda x, y: load_and_preprocess(x, y, training=False),
        num_parallel_calls=tf.data.AUTOTUNE
    )
    val_dataset = val_dataset.batch(batch_size).prefetch(tf.data.AUTOTUNE)
    
    return train_dataset, val_dataset, class_weight_dict

def create_improved_model(input_shape=(160, 160, 3), num_classes=15):
    """Create an improved model architecture."""
    inputs = tf.keras.layers.Input(shape=input_shape)
    
    # Enhanced feature extraction
    x = tf.keras.layers.Conv2D(32, 3, activation='relu', padding='same')(inputs)
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
    
    x = tf.keras.layers.Conv2D(256, 3, activation='relu', padding='same')(x)
    x = tf.keras.layers.BatchNormalization()(x)
    x = tf.keras.layers.GlobalAveragePooling2D()(x)
    x = tf.keras.layers.Dropout(0.4)(x)
    
    # Dense layers
    x = tf.keras.layers.Dense(512, activation='relu')(x)
    x = tf.keras.layers.BatchNormalization()(x)
    x = tf.keras.layers.Dropout(0.5)(x)
    
    outputs = tf.keras.layers.Dense(num_classes, activation='softmax')(x)
    
    model = tf.keras.Model(inputs, outputs)
    return model

def create_mobilenetv3_model(input_shape=(160, 160, 3), num_classes=15):
    """Create MobileNetV3-based model."""
    base_model = tf.keras.applications.MobileNetV3Large(
        input_shape=input_shape,
        include_top=False,
        weights='imagenet'
    )
    
    # Freeze most layers initially
    base_model.trainable = False
    
    inputs = tf.keras.layers.Input(shape=input_shape)
    x = tf.keras.applications.mobilenet_v3.preprocess_input(inputs)
    x = base_model(x, training=False)
    x = tf.keras.layers.GlobalAveragePooling2D()(x)
    x = tf.keras.layers.Dropout(0.2)(x)
    x = tf.keras.layers.Dense(256, activation='relu')(x)
    x = tf.keras.layers.Dropout(0.5)(x)
    outputs = tf.keras.layers.Dense(num_classes, activation='softmax')(x)
    
    model = tf.keras.Model(inputs, outputs)
    return model, base_model

def train_model(model, train_dataset, val_dataset, class_weights, model_name, epochs=50):
    """Train the model with callbacks."""
    # Compile model
    model.compile(
        optimizer=tf.keras.optimizers.Adam(learning_rate=0.001),
        loss='sparse_categorical_crossentropy',
        metrics=['accuracy', tf.keras.metrics.TopKCategoricalAccuracy(k=3, name='top3_accuracy')]
    )
    
    # Callbacks
    callbacks = [
        tf.keras.callbacks.EarlyStopping(patience=15, restore_best_weights=True),
        tf.keras.callbacks.ReduceLROnPlateau(factor=0.5, patience=8, min_lr=1e-7),
        tf.keras.callbacks.ModelCheckpoint(
            f'improved_{model_name}.keras',
            save_best_only=True,
            monitor='val_accuracy'
        )
    ]
    
    # Train
    history = model.fit(
        train_dataset,
        validation_data=val_dataset,
        epochs=epochs,
        class_weight=class_weights,
        callbacks=callbacks,
        verbose=1
    )
    
    return model, history

def fine_tune_model(model, base_model, train_dataset, val_dataset, class_weights, epochs=30):
    """Fine-tune the model by unfreezing some layers."""
    # Unfreeze top layers
    base_model.trainable = True
    for layer in base_model.layers[:-30]:  # Freeze bottom layers
        layer.trainable = False
    
    # Recompile with lower learning rate
    model.compile(
        optimizer=tf.keras.optimizers.Adam(learning_rate=1e-4),
        loss='sparse_categorical_crossentropy',
        metrics=['accuracy', tf.keras.metrics.TopKCategoricalAccuracy(k=3, name='top3_accuracy')]
    )
    
    # Fine-tune
    history = model.fit(
        train_dataset,
        validation_data=val_dataset,
        epochs=epochs,
        class_weight=class_weights,
        callbacks=[
            tf.keras.callbacks.EarlyStopping(patience=10, restore_best_weights=True),
            tf.keras.callbacks.ReduceLROnPlateau(factor=0.5, patience=5, min_lr=1e-7)
        ],
        verbose=1
    )
    
    return model, history

def main():
    """Main training function."""
    models_dir = Path(__file__).resolve().parent
    plantvillage_dir = models_dir.parent / "data" / "datasets" / "plant_disease_dataset" / "raw" / "plantvillage"
    
    if not plantvillage_dir.exists():
        print(f"Error: PlantVillage dataset not found at {plantvillage_dir}")
        sys.exit(1)
    
    print("Creating balanced datasets...")
    train_dataset, val_dataset, class_weights = create_balanced_dataset(
        plantvillage_dir, image_size=(160, 160), batch_size=32
    )
    
    print(f"Class weights: {class_weights}")
    
    # Train multiple models
    models_to_train = [
        ("cnn_improved", create_improved_model()),
        ("mobilenetv3", create_mobilenetv3_model()[0])
    ]
    
    results = {}
    
    for model_name, model in models_to_train:
        print(f"\n{'='*50}")
        print(f"Training {model_name}...")
        print(f"{'='*50}")
        
        # Train initial model
        trained_model, history = train_model(
            model, train_dataset, val_dataset, class_weights, model_name, epochs=50
        )
        
        # Fine-tune if it's a transfer learning model
        if "mobilenet" in model_name:
            print("Fine-tuning MobileNetV3...")
            _, base_model = create_mobilenetv3_model()
            trained_model, fine_tune_history = fine_tune_model(
                trained_model, base_model, train_dataset, val_dataset, class_weights, epochs=30
            )
        
        # Evaluate model
        print(f"\nEvaluating {model_name}...")
        test_loss, test_acc, top3_acc = trained_model.evaluate(val_dataset, verbose=0)
        
        results[model_name] = {
            'test_accuracy': float(test_acc),
            'top3_accuracy': float(top3_acc),
            'test_loss': float(test_loss)
        }
        
        print(f"Test Accuracy: {test_acc:.4f}")
        print(f"Top-3 Accuracy: {top3_acc:.4f}")
    
    # Save results
    results_file = models_dir / "improved_training_results.json"
    with results_file.open('w') as f:
        json.dump(results, f, indent=2)
    
    print(f"\n{'='*50}")
    print("TRAINING COMPLETED")
    print(f"{'='*50}")
    print("Results saved to:", results_file)
    
    for model_name, metrics in results.items():
        print(f"{model_name}: Accuracy={metrics['test_accuracy']:.4f}, Top3={metrics['top3_accuracy']:.4f}")

if __name__ == "__main__":
    main()
