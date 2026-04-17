#!/usr/bin/env python3
"""
Improved training with better hyperparameters and class balancing
"""
import os
import tensorflow as tf
from tensorflow import keras
from tensorflow.keras import layers, models, optimizers
from tensorflow.keras.preprocessing.image import ImageDataGenerator
from tensorflow.keras.callbacks import EarlyStopping, ReduceLROnPlateau, ModelCheckpoint
import numpy as np
import matplotlib.pyplot as plt
from sklearn.metrics import classification_report, confusion_matrix
import seaborn as sns
import time
import json

# Configuration
class Config:
    # Data paths
    DATA_DIR = "/Users/nischalmittal/Desktop/PlantVillage"
    MODEL_SAVE_PATH = "plant_disease_improved.keras"
    
    # Training parameters
    IMG_SIZE = (224, 224)
    BATCH_SIZE = 16  # Smaller batch for better learning
    EPOCHS = 100  # More epochs
    LEARNING_RATE = 0.0001  # Lower learning rate
    
    # Model parameters
    NUM_CLASSES = 15
    
    # Data augmentation (more aggressive)
    AUGMENTATION = True
    
    # Class names
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

def create_balanced_data_generators():
    """Create balanced data generators with class weights"""
    
    # Enhanced training data generator
    train_datagen = ImageDataGenerator(
        rescale=1./255,
        rotation_range=30,
        width_shift_range=0.3,
        height_shift_range=0.3,
        shear_range=0.3,
        zoom_range=0.3,
        horizontal_flip=True,
        vertical_flip=True,
        brightness_range=[0.7, 1.3],
        fill_mode='nearest',
        validation_split=0.15  # 15% for validation
    )
    
    # Validation data generator
    val_datagen = ImageDataGenerator(
        rescale=1./255,
        validation_split=0.15
    )
    
    # Create generators
    train_generator = train_datagen.flow_from_directory(
        Config.DATA_DIR,
        target_size=Config.IMG_SIZE,
        batch_size=Config.BATCH_SIZE,
        class_mode='categorical',
        subset='training',
        shuffle=True,
        classes=Config.CLASS_NAMES
    )
    
    validation_generator = val_datagen.flow_from_directory(
        Config.DATA_DIR,
        target_size=Config.IMG_SIZE,
        batch_size=Config.BATCH_SIZE,
        class_mode='categorical',
        subset='validation',
        shuffle=False,
        classes=Config.CLASS_NAMES
    )
    
    # Calculate class weights for balancing
    class_weights = calculate_class_weights(train_generator)
    
    return train_generator, validation_generator, class_weights

def calculate_class_weights(generator):
    """Calculate class weights to handle imbalance"""
    from sklearn.utils.class_weight import compute_class_weight
    
    # Get class counts
    class_counts = {}
    for class_name, count in zip(generator.class_indices.keys(), 
                             np.bincount(generator.classes)):
        class_counts[class_name] = count
    
    print("📊 Class distribution:")
    for class_name, count in sorted(class_counts.items()):
        print(f"   {class_name}: {count} images")
    
    # Calculate weights
    classes = list(generator.class_indices.values())
    weights = compute_class_weight(
        'balanced',
        classes=np.unique(classes),
        y=classes
    )
    
    class_weights = dict(zip(range(len(weights)), weights))
    
    print(f"\n⚖️  Class weights calculated")
    return class_weights

def create_improved_model():
    """Create an improved CNN model"""
    
    # Use EfficientNetB1 for better performance
    base_model = keras.applications.EfficientNetB1(
        include_top=False,
        weights='imagenet',
        input_shape=(*Config.IMG_SIZE, 3),
        pooling='avg'
    )
    
    # Unfreeze last few layers for fine-tuning
    base_model.trainable = True
    for layer in base_model.layers[:-30]:  # Freeze all but last 30 layers
        layer.trainable = False
    
    # Create improved model
    inputs = keras.Input(shape=(*Config.IMG_SIZE, 3))
    
    # Data augmentation as part of model
    x = layers.RandomFlip("horizontal")(inputs)
    x = layers.RandomRotation(0.2)(x)
    x = layers.RandomZoom(0.2)(x)
    x = layers.RandomContrast(0.2)(x)
    
    # Through base model
    x = base_model(x, training=False)
    
    # Custom classification head
    x = layers.Dropout(0.5)(x)
    x = layers.Dense(512, activation='relu')(x)
    x = layers.BatchNormalization()(x)
    x = layers.Dropout(0.4)(x)
    x = layers.Dense(256, activation='relu')(x)
    x = layers.BatchNormalization()(x)
    x = layers.Dropout(0.3)(x)
    x = layers.Dense(128, activation='relu')(x)
    x = layers.BatchNormalization()(x)
    x = layers.Dropout(0.2)(x)
    outputs = layers.Dense(Config.NUM_CLASSES, activation='softmax')(x)
    
    model = keras.Model(inputs, outputs)
    
    # Compile with better optimizer
    optimizer = optimizers.Adam(
        learning_rate=Config.LEARNING_RATE,
        weight_decay=1e-4
    )
    
    model.compile(
        optimizer=optimizer,
        loss='categorical_crossentropy',
        metrics=['accuracy']
    )
    
    return model

def create_improved_callbacks():
    """Create better training callbacks"""
    
    callbacks = [
        EarlyStopping(
            monitor='val_accuracy',
            patience=20,  # More patience
            restore_best_weights=True,
            verbose=1,
            min_delta=0.001
        ),
        ReduceLROnPlateau(
            monitor='val_loss',
            factor=0.5,
            patience=8,
            min_lr=1e-7,
            verbose=1
        ),
        ModelCheckpoint(
            Config.MODEL_SAVE_PATH,
            monitor='val_accuracy',
            save_best_only=True,
            verbose=1,
            save_weights_only=False
        )
    ]
    
    return callbacks

def train_improved_model():
    """Main improved training function"""
    
    print("🌱 Improved PlantVillage Model Training")
    print("=" * 50)
    
    # Check data directory
    if not os.path.exists(Config.DATA_DIR):
        print(f"❌ Data directory not found: {Config.DATA_DIR}")
        return
    
    # Create data generators
    print("📊 Creating balanced data generators...")
    train_gen, val_gen, class_weights = create_balanced_data_generators()
    
    print(f"📈 Training samples: {train_gen.samples}")
    print(f"📉 Validation samples: {val_gen.samples}")
    print(f"🏷️  Classes: {len(train_gen.class_indices)}")
    
    # Create model
    print("🤖 Creating improved model...")
    model = create_improved_model()
    
    # Print model summary
    print("\n📋 Improved Model Architecture:")
    model.summary()
    
    # Create callbacks
    callbacks = create_improved_callbacks()
    
    # Train model with class weights
    print(f"\n🚀 Starting improved training for {Config.EPOCHS} epochs...")
    print(f"⚖️  Using class weights for balance")
    start_time = time.time()
    
    history = model.fit(
        train_gen,
        epochs=Config.EPOCHS,
        validation_data=val_gen,
        callbacks=callbacks,
        class_weight=class_weights,
        verbose=1
    )
    
    training_time = time.time() - start_time
    print(f"⏱️  Training completed in {training_time/60:.1f} minutes")
    
    # Save training history
    save_training_history(history)
    
    # Evaluate model
    evaluate_model(model, val_gen)
    
    # Save class indices
    save_class_indices(train_gen.class_indices)
    
    print(f"✅ Improved model saved to: {Config.MODEL_SAVE_PATH}")
    
    return model, history

def save_training_history(history):
    """Save training history"""
    history_dict = {
        'accuracy': [float(x) for x in history.history['accuracy']],
        'val_accuracy': [float(x) for x in history.history['val_accuracy']],
        'loss': [float(x) for x in history.history['loss']],
        'val_loss': [float(x) for x in history.history['val_loss']]
    }
    
    with open('improved_training_history.json', 'w') as f:
        json.dump(history_dict, f, indent=2)
    
    print("📊 Improved training history saved")

def save_class_indices(class_indices):
    """Save class indices mapping"""
    with open('improved_class_indices.json', 'w') as f:
        json.dump(class_indices, f, indent=2)
    
    print("📋 Improved class indices saved")

def evaluate_model(model, val_gen):
    """Evaluate model performance"""
    print("\n📊 Evaluating improved model...")
    
    val_gen.reset()
    test_loss, test_acc = model.evaluate(val_gen, verbose=0)
    
    print(f"\n🎯 Improved Results:")
    print(f"   Test Accuracy: {test_acc:.4f}")
    print(f"   Test Loss: {test_loss:.4f}")
    
    if test_acc > 0.8:
        print("   🎉 EXCELLENT performance!")
    elif test_acc > 0.6:
        print("   ✅ GOOD performance!")
    elif test_acc > 0.4:
        print("   🟡 MODERATE performance")
    else:
        print("   ❌ Needs improvement")

def main():
    """Main improved training pipeline"""
    
    try:
        # Set random seeds
        tf.random.set_seed(42)
        np.random.seed(42)
        
        # Train improved model
        model, history = train_improved_model()
        
        print("\n🎉 Improved training completed!")
        print(f"📁 Model: {Config.MODEL_SAVE_PATH}")
        print("📁 History: improved_training_history.json")
        print("📁 Classes: improved_class_indices.json")
        
    except Exception as e:
        print(f"❌ Improved training failed: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
