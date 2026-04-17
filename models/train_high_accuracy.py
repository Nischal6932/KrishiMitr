#!/usr/bin/env python3
"""
Advanced Plant Disease Detection Model Training
Optimized for 90%+ accuracy using modern techniques
"""

import os
import sys
import time
import json
import numpy as np
import tensorflow as tf
from tensorflow import keras
from tensorflow.keras import layers, models, optimizers, callbacks
from tensorflow.keras.preprocessing.image import ImageDataGenerator
from tensorflow.keras.applications import EfficientNetB3
from sklearn.utils.class_weight import compute_class_weight
from sklearn.metrics import classification_report, confusion_matrix
import matplotlib.pyplot as plt
import seaborn as sns

# Suppress warnings
os.environ['TF_CPP_MIN_LOG_LEVEL'] = '2'
tf.get_logger().setLevel('ERROR')

# Configuration
class Config:
    """Training configuration optimized for high accuracy"""
    
    # Paths
    DATA_DIR = "/Users/nischalmittal/Desktop/PlantVillage"
    MODEL_SAVE_PATH = "plant_disease_high_accuracy.keras"
    
    # Image parameters - larger input for better feature extraction
    IMG_SIZE = (300, 300)  # Increased from 224
    BATCH_SIZE = 32  # Larger batch for stable gradients
    
    # Training epochs with early stopping
    EPOCHS = 150
    
    # Learning rate schedule
    INITIAL_LR = 1e-3
    WARMUP_EPOCHS = 5
    
    # Model architecture
    NUM_CLASSES = 15
    DROPOUT_RATE = 0.5
    
    # Class names (must match directory names)
    CLASS_NAMES = [
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
        "Tomato_Spider_mites_Two_spotted_spider_mite",
        "Tomato__Target_Spot",
        "Tomato__Tomato_YellowLeaf__Curl_Virus",
        "Tomato__Tomato_mosaic_virus",
        "Tomato_healthy"
    ]


def create_advanced_data_generators():
    """Create enhanced data generators with aggressive augmentation"""
    
    print("📊 Creating advanced data generators...")
    
    # Aggressive training augmentation
    train_datagen = ImageDataGenerator(
        rescale=1./255,
        rotation_range=40,
        width_shift_range=0.4,
        height_shift_range=0.4,
        shear_range=0.3,
        zoom_range=0.4,
        horizontal_flip=True,
        vertical_flip=True,
        brightness_range=[0.6, 1.4],
        fill_mode='nearest',
        validation_split=0.15
    )
    
    # Validation - only rescaling
    val_datagen = ImageDataGenerator(
        rescale=1./255,
        validation_split=0.15
    )
    
    # Training generator
    train_generator = train_datagen.flow_from_directory(
        Config.DATA_DIR,
        target_size=Config.IMG_SIZE,
        batch_size=Config.BATCH_SIZE,
        class_mode='categorical',
        subset='training',
        shuffle=True,
        classes=Config.CLASS_NAMES,
        seed=42
    )
    
    # Validation generator
    val_generator = val_datagen.flow_from_directory(
        Config.DATA_DIR,
        target_size=Config.IMG_SIZE,
        batch_size=Config.BATCH_SIZE,
        class_mode='categorical',
        subset='validation',
        shuffle=False,
        classes=Config.CLASS_NAMES,
        seed=42
    )
    
    # Calculate class weights
    class_weights = calculate_class_weights(train_generator)
    
    return train_generator, val_generator, class_weights


def calculate_class_weights(generator):
    """Calculate balanced class weights"""
    
    print("\n⚖️  Calculating class weights...")
    
    # Get class distribution
    class_counts = np.bincount(generator.classes)
    total_samples = len(generator.classes)
    
    print("\n📊 Class distribution:")
    for idx, (class_name, count) in enumerate(zip(generator.class_indices.keys(), class_counts)):
        percentage = (count / total_samples) * 100
        print(f"   {class_name}: {count} images ({percentage:.1f}%)")
    
    # Calculate weights
    weights = compute_class_weight(
        'balanced',
        classes=np.unique(generator.classes),
        y=generator.classes
    )
    
    class_weights = {i: weight for i, weight in enumerate(weights)}
    
    print(f"\n✅ Class weights calculated")
    return class_weights


def create_advanced_model():
    """Create high-accuracy model with EfficientNetB3"""
    
    print("\n🤖 Creating advanced EfficientNetB3 model...")
    
    # Use EfficientNetB3 (better than B1/B0)
    base_model = EfficientNetB3(
        include_top=False,
        weights='imagenet',
        input_shape=(*Config.IMG_SIZE, 3),
        pooling='avg'
    )
    
    # Progressive unfreezing strategy
    base_model.trainable = True
    
    # Freeze early layers, fine-tune deeper layers
    # Freeze first 100 layers (low-level features)
    for layer in base_model.layers[:100]:
        layer.trainable = False
    
    # Partially freeze next 100 layers
    for layer in base_model.layers[100:200]:
        if 'bn' not in layer.name:  # Keep batch norm trainable
            layer.trainable = False
    
    # Last 70 layers are trainable (high-level features)
    
    print(f"   Base model layers: {len(base_model.layers)}")
    print(f"   Trainable layers: {sum(1 for l in base_model.layers if l.trainable)}")
    
    # Build model
    inputs = keras.Input(shape=(*Config.IMG_SIZE, 3))
    
    # Built-in augmentation layers
    x = layers.RandomFlip("horizontal")(inputs)
    x = layers.RandomRotation(0.3)(x)
    x = layers.RandomZoom(0.3)(x)
    x = layers.RandomContrast(0.3)(x)
    x = layers.RandomBrightness(0.2)(x)
    
    # Through base model
    x = base_model(x, training=True)
    
    # Advanced classification head
    x = layers.BatchNormalization()(x)
    x = layers.Dropout(Config.DROPOUT_RATE)(x)
    
    x = layers.Dense(512, activation='swish')(x)
    x = layers.BatchNormalization()(x)
    x = layers.Dropout(0.4)(x)
    
    x = layers.Dense(256, activation='swish')(x)
    x = layers.BatchNormalization()(x)
    x = layers.Dropout(0.3)(x)
    
    x = layers.Dense(128, activation='swish')(x)
    x = layers.BatchNormalization()(x)
    x = layers.Dropout(0.2)(x)
    
    outputs = layers.Dense(Config.NUM_CLASSES, activation='softmax')(x)
    
    model = keras.Model(inputs, outputs)
    
    return model


def get_lr_scheduler(epoch, lr):
    """Custom learning rate schedule with warmup and cosine decay"""
    
    if epoch < Config.WARMUP_EPOCHS:
        # Linear warmup
        return Config.INITIAL_LR * (epoch + 1) / Config.WARMUP_EPOCHS
    else:
        # Cosine decay after warmup
        progress = (epoch - Config.WARMUP_EPOCHS) / (Config.EPOCHS - Config.WARMUP_EPOCHS)
        return Config.INITIAL_LR * 0.5 * (1 + np.cos(np.pi * progress))


def create_advanced_callbacks():
    """Create comprehensive training callbacks"""
    
    callback_list = [
        # Early stopping with patience
        callbacks.EarlyStopping(
            monitor='val_accuracy',
            patience=25,
            restore_best_weights=True,
            verbose=1,
            min_delta=0.001
        ),
        
        # Learning rate reduction on plateau
        callbacks.ReduceLROnPlateau(
            monitor='val_loss',
            factor=0.5,
            patience=10,
            min_lr=1e-7,
            verbose=1,
            min_delta=0.001
        ),
        
        # Model checkpoint - save best
        callbacks.ModelCheckpoint(
            Config.MODEL_SAVE_PATH,
            monitor='val_accuracy',
            save_best_only=True,
            verbose=1,
            save_weights_only=False
        ),
        
        # Backup checkpoint every 10 epochs
        callbacks.ModelCheckpoint(
            'backup_checkpoint.keras',
            save_freq=10 * 100,  # Every 10 epochs (approximate)
            verbose=0
        ),
        
        # Learning rate scheduler
        callbacks.LearningRateScheduler(get_lr_scheduler, verbose=1),
        
        # TensorBoard logging
        callbacks.TensorBoard(
            log_dir='./logs',
            histogram_freq=1,
            write_graph=True,
            update_freq='epoch'
        )
    ]
    
    return callback_list


def train_advanced_model():
    """Main advanced training pipeline"""
    
    print("\n" + "="*60)
    print("🌱 ADVANCED PLANT DISEASE MODEL TRAINING")
    print("   Target: 90%+ Accuracy")
    print("="*60)
    
    # Check data
    if not os.path.exists(Config.DATA_DIR):
        print(f"❌ Data directory not found: {Config.DATA_DIR}")
        return None, None
    
    # Create generators
    train_gen, val_gen, class_weights = create_advanced_data_generators()
    
    print(f"\n📈 Dataset:")
    print(f"   Training samples: {train_gen.samples}")
    print(f"   Validation samples: {val_gen.samples}")
    print(f"   Number of classes: {len(train_gen.class_indices)}")
    print(f"   Batch size: {Config.BATCH_SIZE}")
    print(f"   Image size: {Config.IMG_SIZE}")
    
    # Create model
    model = create_advanced_model()
    
    # Print model summary
    print("\n📋 Model Architecture:")
    model.summary()
    
    # Compile with optimal settings
    optimizer = optimizers.AdamW(
        learning_rate=Config.INITIAL_LR,
        weight_decay=1e-4,
        clipnorm=1.0  # Gradient clipping
    )
    
    model.compile(
        optimizer=optimizer,
        loss='categorical_crossentropy',
        metrics=[
            'accuracy',
            keras.metrics.TopKCategoricalAccuracy(k=3, name='top3_accuracy'),
            keras.metrics.Precision(name='precision'),
            keras.metrics.Recall(name='recall')
        ]
    )
    
    # Create callbacks
    training_callbacks = create_advanced_callbacks()
    
    # Train
    print(f"\n🚀 Starting training for up to {Config.EPOCHS} epochs...")
    print(f"   Warmup epochs: {Config.WARMUP_EPOCHS}")
    print(f"   Initial learning rate: {Config.INITIAL_LR}")
    print(f"   Using class weights: Yes")
    print()
    
    start_time = time.time()
    
    history = model.fit(
        train_gen,
        epochs=Config.EPOCHS,
        validation_data=val_gen,
        callbacks=training_callbacks,
        class_weight=class_weights,
        verbose=1
    )
    
    training_time = time.time() - start_time
    
    print(f"\n⏱️  Training completed in {training_time/60:.1f} minutes")
    
    # Save history
    save_training_history(history)
    
    # Evaluate
    evaluate_model_advanced(model, val_gen)
    
    # Save class mapping
    save_class_indices(train_gen.class_indices)
    
    print(f"\n✅ High-accuracy model saved to: {Config.MODEL_SAVE_PATH}")
    
    return model, history


def save_training_history(history):
    """Save detailed training history"""
    
    history_dict = {
        'accuracy': [float(x) for x in history.history['accuracy']],
        'val_accuracy': [float(x) for x in history.history['val_accuracy']],
        'loss': [float(x) for x in history.history['loss']],
        'val_loss': [float(x) for x in history.history['val_loss']],
        'top3_accuracy': [float(x) for x in history.history.get('top3_accuracy', [])],
        'val_top3_accuracy': [float(x) for x in history.history.get('val_top3_accuracy', [])],
        'precision': [float(x) for x in history.history.get('precision', [])],
        'recall': [float(x) for x in history.history.get('recall', [])]
    }
    
    with open('advanced_training_history.json', 'w') as f:
        json.dump(history_dict, f, indent=2)
    
    print("📊 Training history saved to: advanced_training_history.json")


def save_class_indices(class_indices):
    """Save class indices mapping"""
    with open('advanced_class_indices.json', 'w') as f:
        json.dump(class_indices, f, indent=2)
    print("📋 Class indices saved to: advanced_class_indices.json")


def evaluate_model_advanced(model, val_gen):
    """Comprehensive model evaluation"""
    
    print("\n📊 EVALUATION RESULTS")
    print("="*50)
    
    # Reset generator
    val_gen.reset()
    
    # Evaluate
    results = model.evaluate(val_gen, verbose=1)
    
    print(f"\n🎯 Performance Metrics:")
    print(f"   Accuracy: {results[1]*100:.2f}%")
    print(f"   Top-3 Accuracy: {results[2]*100:.2f}%")
    print(f"   Precision: {results[3]*100:.2f}%")
    print(f"   Recall: {results[4]*100:.2f}%")
    print(f"   Loss: {results[0]:.4f}")
    
    # Performance rating
    acc = results[1]
    if acc > 0.90:
        print("   🏆 OUTSTANDING! 90%+ accuracy achieved!")
    elif acc > 0.80:
        print("   🎉 EXCELLENT! 80%+ accuracy achieved!")
    elif acc > 0.70:
        print("   ✅ GOOD! 70%+ accuracy achieved!")
    elif acc > 0.60:
        print("   🟡 MODERATE - Room for improvement")
    else:
        print("   ❌ NEEDS IMPROVEMENT - Consider more training")


def plot_training_curves(history):
    """Plot and save training curves"""
    
    fig, axes = plt.subplots(2, 2, figsize=(15, 10))
    
    # Accuracy
    axes[0, 0].plot(history.history['accuracy'], label='Train')
    axes[0, 0].plot(history.history['val_accuracy'], label='Validation')
    axes[0, 0].set_title('Model Accuracy')
    axes[0, 0].set_xlabel('Epoch')
    axes[0, 0].set_ylabel('Accuracy')
    axes[0, 0].legend()
    axes[0, 0].grid(True)
    
    # Loss
    axes[0, 1].plot(history.history['loss'], label='Train')
    axes[0, 1].plot(history.history['val_loss'], label='Validation')
    axes[0, 1].set_title('Model Loss')
    axes[0, 1].set_xlabel('Epoch')
    axes[0, 1].set_ylabel('Loss')
    axes[0, 1].legend()
    axes[0, 1].grid(True)
    
    # Top-3 Accuracy
    if 'top3_accuracy' in history.history:
        axes[1, 0].plot(history.history['top3_accuracy'], label='Train')
        axes[1, 0].plot(history.history['val_top3_accuracy'], label='Validation')
        axes[1, 0].set_title('Top-3 Accuracy')
        axes[1, 0].set_xlabel('Epoch')
        axes[1, 0].set_ylabel('Accuracy')
        axes[1, 0].legend()
        axes[1, 0].grid(True)
    
    # Precision vs Recall
    if 'precision' in history.history:
        axes[1, 1].plot(history.history['precision'], label='Precision')
        axes[1, 1].plot(history.history['recall'], label='Recall')
        axes[1, 1].set_title('Precision vs Recall')
        axes[1, 1].set_xlabel('Epoch')
        axes[1, 1].set_ylabel('Score')
        axes[1, 1].legend()
        axes[1, 1].grid(True)
    
    plt.tight_layout()
    plt.savefig('advanced_training_curves.png', dpi=150)
    print("📈 Training curves saved to: advanced_training_curves.png")


def main():
    """Main training entry point"""
    
    try:
        # Set random seeds for reproducibility
        tf.random.set_seed(42)
        np.random.seed(42)
        
        # Run training
        model, history = train_advanced_model()
        
        if model is not None:
            # Plot curves
            plot_training_curves(history)
            
            print("\n" + "="*60)
            print("🎉 TRAINING COMPLETE!")
            print("="*60)
            print(f"📁 Model: {Config.MODEL_SAVE_PATH}")
            print(f"📁 History: advanced_training_history.json")
            print(f"📁 Classes: advanced_class_indices.json")
            print(f"📁 Plots: advanced_training_curves.png")
            print("\nTo use this model in your app:")
            print("1. Replace 'plant_disease_efficientnet.keras' with the new model")
            print("2. Update class names if they changed")
            print("3. Test predictions to verify accuracy")
            
    except KeyboardInterrupt:
        print("\n⚠️ Training interrupted by user")
        print("Best model saved so far is available")
        
    except Exception as e:
        print(f"\n❌ Training error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
