#!/usr/bin/env python3
"""
Ultra-High Accuracy Plant Disease Model Training
Target: 90%+ accuracy using state-of-the-art techniques
"""

import os
import sys
import json
import numpy as np
import tensorflow as tf
from tensorflow import keras
from tensorflow.keras import layers, optimizers, callbacks
from tensorflow.keras.applications import EfficientNetV2B0, EfficientNetV2B3
from sklearn.utils.class_weight import compute_class_weight
from sklearn.metrics import classification_report, confusion_matrix, top_k_accuracy_score
import warnings
warnings.filterwarnings('ignore')

os.environ['TF_CPP_MIN_LOG_LEVEL'] = '2'
tf.get_logger().setLevel('ERROR')

# =============================================================================
# CONFIGURATION - Optimized for 90%+ accuracy
# =============================================================================
class Config:
    """Ultra-high accuracy configuration"""
    
    # Data paths - UPDATE THESE
    DATA_DIR = "../data/datasets/plant_disease_dataset"  # Your dataset path
    OUTPUT_DIR = "../models"
    
    # Image parameters - LARGER = BETTER FEATURES
    IMG_SIZE = (380, 380)  # Increased from 160 - much better accuracy
    BATCH_SIZE = 16        # Smaller batch for larger images
    
    # Training schedule
    EPOCHS = 200
    
    # Learning rate strategy - WARMUP + COSINE DECAY
    INITIAL_LR = 5e-4
    WARMUP_EPOCHS = 10
    
    # Architecture
    NUM_CLASSES = 15
    DROPOUT_RATE = 0.6  # Higher dropout for regularization
    
    # Test-Time Augmentation (TTA) - boosts accuracy 2-3%
    TTA_ROUNDS = 5  # Number of augmented predictions to average
    
    # Progressive unfreezing strategy
    FREEZE_EPOCHS = 5      # Initial frozen training
    PARTIAL_EPOCHS = 30    # Partial unfreezing
    FULL_EPOCHS = 165      # Full fine-tuning
    
    # Label smoothing - helps with hard classes
    LABEL_SMOOTHING = 0.1
    
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

# =============================================================================
# ADVANCED DATA PIPELINE
# =============================================================================
def create_data_pipeline():
    """Create optimized tf.data pipeline with heavy augmentation"""
    
    print("\n📊 Creating ultra data pipeline...")
    
    # Training dataset with augmentation
    train_ds = keras.utils.image_dataset_from_directory(
        Config.DATA_DIR,
        validation_split=0.15,
        subset="training",
        seed=42,
        image_size=Config.IMG_SIZE,
        batch_size=Config.BATCH_SIZE,
        label_mode='categorical',
        shuffle=True
    )
    
    # Validation dataset - NO AUGMENTATION
    val_ds = keras.utils.image_dataset_from_directory(
        Config.DATA_DIR,
        validation_split=0.15,
        subset="validation", 
        seed=42,
        image_size=Config.IMG_SIZE,
        batch_size=Config.BATCH_SIZE,
        label_mode='categorical',
        shuffle=False
    )
    
    # Class weights for imbalance
    labels = []
    for _, y in train_ds:
        labels.extend(np.argmax(y.numpy(), axis=1))
    labels = np.array(labels)
    
    class_weights = compute_class_weight(
        'balanced',
        classes=np.unique(labels),
        y=labels
    )
    class_weight_dict = {i: w for i, w in enumerate(class_weights)}
    
    print("\n📊 Class distribution:")
    unique, counts = np.unique(labels, return_counts=True)
    for idx, (cls, count) in enumerate(zip(Config.CLASS_NAMES, counts)):
        print(f"   {cls}: {count} images (weight: {class_weight_dict[idx]:.2f})")
    
    # AUTOTUNE for performance
    AUTOTUNE = tf.data.AUTOTUNE
    
    # Heavy augmentation pipeline
    def augment(image, label):
        """Aggressive augmentation for robustness"""
        # Random flip
        image = tf.image.random_flip_left_right(image)
        image = tf.image.random_flip_up_down(image)
        
        # Rotation
        image = tf.image.rot90(image, k=tf.random.uniform([], 0, 4, dtype=tf.int32))
        
        # Color augmentations
        image = tf.image.random_brightness(image, 0.3)
        image = tf.image.random_contrast(image, 0.7, 1.3)
        image = tf.image.random_saturation(image, 0.8, 1.2)
        image = tf.image.random_hue(image, 0.1)
        
        # Zoom and translate
        scales = list(np.arange(0.8, 1.2, 0.02))
        scale = tf.random.uniform([], minval=scales[0], maxval=scales[-1])
        h, w = tf.cast(tf.shape(image)[0], tf.float32), tf.cast(tf.shape(image)[1], tf.float32)
        new_h, new_w = h * scale, w * scale
        image = tf.image.resize(image, [tf.cast(new_h, tf.int32), tf.cast(new_w, tf.int32)])
        image = tf.image.resize_with_crop_or_pad(image, Config.IMG_SIZE[0], Config.IMG_SIZE[1])
        
        # Cutout/Random erasing simulation
        if tf.random.uniform([]) > 0.5:
            mask_size = tf.random.uniform([], 20, 60, dtype=tf.int32)
            h_start = tf.random.uniform([], 0, Config.IMG_SIZE[0] - mask_size, dtype=tf.int32)
            w_start = tf.random.uniform([], 0, Config.IMG_SIZE[1] - mask_size, dtype=tf.int32)
            mask = tf.ones([mask_size, mask_size, 3]) * 0.5
            padding = [[h_start, Config.IMG_SIZE[0] - h_start - mask_size],
                      [w_start, Config.IMG_SIZE[1] - w_start - mask_size],
                      [0, 0]]
            mask = tf.pad(mask, padding)
            image = image * (1 - mask) + mask * 128
        
        # Clip values
        image = tf.clip_by_value(image, 0, 255)
        
        # Normalize
        image = image / 255.0
        
        return image, label
    
    def normalize(image, label):
        """Just normalize for validation"""
        image = image / 255.0
        return image, label
    
    # Apply augmentation to training only
    train_ds = train_ds.map(augment, num_parallel_calls=AUTOTUNE)
    train_ds = train_ds.prefetch(AUTOTUNE)
    
    val_ds = val_ds.map(normalize, num_parallel_calls=AUTOTUNE)
    val_ds = val_ds.prefetch(AUTOTUNE)
    
    return train_ds, val_ds, class_weight_dict

# =============================================================================
# ADVANCED MODEL ARCHITECTURE
# =============================================================================
def create_ultra_model(phase='initial'):
    """
    Create model with progressive unfreezing strategy
    phase: 'initial', 'partial', 'full'
    """
    
    print(f"\n🤖 Creating Ultra EfficientNetV2 model (phase: {phase})...")
    
    # Use EfficientNetV2B3 for better accuracy (or B0 if memory limited)
    # B3 gives ~2-3% better accuracy than B0
    base_model = EfficientNetV2B3(
        include_top=False,
        weights='imagenet',
        input_shape=(*Config.IMG_SIZE, 3),
        pooling='avg',
        include_preprocessing=False  # We do our own normalization
    )
    
    # Progressive unfreezing based on phase
    base_model.trainable = True
    
    if phase == 'initial':
        # Completely frozen for warm start
        base_model.trainable = False
        print("   Phase: FROZEN - Training classifier head only")
        
    elif phase == 'partial':
        # Unfreeze last 150 layers
        for layer in base_model.layers[:-150]:
            layer.trainable = False
        print(f"   Phase: PARTIAL - {sum(1 for l in base_model.layers if l.trainable)} layers trainable")
        
    else:  # full
        # Unfreeze all, but with differential learning rates handled by optimizer
        print(f"   Phase: FULL - All {len(base_model.layers)} layers trainable")
    
    # Build model with augmentation layers built-in
    inputs = keras.Input(shape=(*Config.IMG_SIZE, 3))
    
    # Built-in augmentation (applied at training time)
    x = layers.RandomFlip("horizontal_and_vertical")(inputs)
    x = layers.RandomRotation(0.5)(x)
    x = layers.RandomZoom(0.3)(x)
    x = layers.RandomContrast(0.3)(x)
    x = layers.RandomBrightness(0.3)(x)
    
    # Base model
    x = base_model(x, training=(phase != 'initial'))
    
    # Multi-layer classification head with heavy regularization
    x = layers.BatchNormalization()(x)
    x = layers.Dropout(Config.DROPOUT_RATE)(x)
    
    # First dense block
    x = layers.Dense(1024, kernel_regularizer=keras.regularizers.l2(1e-4))(x)
    x = layers.BatchNormalization()(x)
    x = layers.Activation('swish')(x)
    x = layers.Dropout(0.5)(x)
    
    # Second dense block  
    x = layers.Dense(512, kernel_regularizer=keras.regularizers.l2(1e-4))(x)
    x = layers.BatchNormalization()(x)
    x = layers.Activation('swish')(x)
    x = layers.Dropout(0.4)(x)
    
    # Third dense block
    x = layers.Dense(256, kernel_regularizer=keras.regularizers.l2(1e-4))(x)
    x = layers.BatchNormalization()(x)
    x = layers.Activation('swish')(x)
    x = layers.Dropout(0.3)(x)
    
    # Output with label smoothing
    outputs = layers.Dense(
        Config.NUM_CLASSES, 
        activation='softmax',
        kernel_regularizer=keras.regularizers.l2(1e-4)
    )(x)
    
    model = keras.Model(inputs, outputs)
    
    print(f"   Total params: {model.count_params():,}")
    print(f"   Trainable params: {sum([keras.backend.count_params(w) for w in model.trainable_weights]):,}")
    
    return model

# =============================================================================
# ADVANCED CALLBACKS
# =============================================================================
def create_ultra_callbacks(phase='initial'):
    """Create comprehensive callback suite"""
    
    callback_list = [
        # Early stopping with longer patience
        callbacks.EarlyStopping(
            monitor='val_accuracy',
            patience=30 if phase == 'full' else 15,
            restore_best_weights=True,
            verbose=1,
            min_delta=0.0005,
            mode='max'
        ),
        
        # Learning rate reduction
        callbacks.ReduceLROnPlateau(
            monitor='val_loss',
            factor=0.5,
            patience=8,
            min_lr=1e-8,
            verbose=1,
            mode='min'
        ),
        
        # Model checkpoint
        callbacks.ModelCheckpoint(
            os.path.join(Config.OUTPUT_DIR, f'ultra_model_{phase}_best.keras'),
            monitor='val_accuracy',
            save_best_only=True,
            verbose=1,
            mode='max'
        ),
        
        # TensorBoard logging
        callbacks.TensorBoard(
            log_dir=os.path.join(Config.OUTPUT_DIR, 'logs', phase),
            histogram_freq=1,
            update_freq='epoch'
        ),
        
        # Cosine learning rate decay after warmup
        callbacks.CosineDecayRestarts(
            initial_learning_rate=Config.INITIAL_LR,
            first_decay_steps=30,
            t_mul=2.0,
            m_mul=0.9,
            alpha=0.1
        ) if phase == 'full' else callbacks.LearningRateScheduler(
            lambda epoch, lr: Config.INITIAL_LR * (epoch + 1) / Config.WARMUP_EPOCHS 
            if epoch < Config.WARMUP_EPOCHS 
            else Config.INITIAL_LR
        )
    ]
    
    return callback_list

# =============================================================================
# TEST-TIME AUGMENTATION (TTA)
# =============================================================================
def create_tta_model(base_model):
    """Create TTA wrapper for inference"""
    
    inputs = keras.Input(shape=(*Config.IMG_SIZE, 3))
    
    # Multiple augmented versions
    predictions = []
    
    for _ in range(Config.TTA_ROUNDS):
        # Random augmentation
        x = layers.RandomFlip("horizontal")(inputs)
        x = layers.RandomRotation(0.2)(x)
        x = layers.RandomZoom(0.2)(x)
        x = layers.RandomContrast(0.2)(x)
        
        # Get prediction
        pred = base_model(x, training=False)
        predictions.append(pred)
    
    # Average predictions
    outputs = layers.Average()(predictions)
    
    return keras.Model(inputs, outputs)

# =============================================================================
# TRAINING LOOP
# =============================================================================
def train_ultra_model():
    """Main training with progressive phases"""
    
    print("\n" + "="*60)
    print("🚀 ULTRA ACCURACY MODEL TRAINING")
    print("🎯 Target: 90%+ accuracy")
    print("="*60)
    
    # Check dataset
    if not os.path.exists(Config.DATA_DIR):
        print(f"\n❌ Dataset not found: {Config.DATA_DIR}")
        print("Please update Config.DATA_DIR with your dataset path")
        return
    
    # Create data pipeline
    train_ds, val_ds, class_weights = create_data_pipeline()
    
    # ================================================================
    # PHASE 1: FROZEN BACKBONE (Warm Start)
    # ================================================================
    print("\n" + "="*60)
    print("PHASE 1: Training Classifier Head (Frozen Backbone)")
    print("="*60)
    
    model = create_ultra_model(phase='initial')
    
    model.compile(
        optimizer=optimizers.Adam(learning_rate=1e-3),
        loss='categorical_crossentropy',
        metrics=['accuracy', 'top_k_categorical_accuracy']
    )
    
    history1 = model.fit(
        train_ds,
        epochs=Config.FREEZE_EPOCHS,
        validation_data=val_ds,
        class_weight=class_weights,
        callbacks=create_ultra_callbacks('initial'),
        verbose=1
    )
    
    # ================================================================
    # PHASE 2: PARTIAL FINE-TUNING
    # ================================================================
    print("\n" + "="*60)
    print("PHASE 2: Partial Fine-Tuning (Last 150 Layers)")
    print("="*60)
    
    # Rebuild with partial unfreezing, loading weights from phase 1
    model = create_ultra_model(phase='partial')
    
    # Load best weights from phase 1
    best_phase1 = os.path.join(Config.OUTPUT_DIR, 'ultra_model_initial_best.keras')
    if os.path.exists(best_phase1):
        model.load_weights(best_phase1)
    
    model.compile(
        optimizer=optimizers.Adam(learning_rate=Config.INITIAL_LR),
        loss=keras.losses.CategoricalCrossentropy(label_smoothing=Config.LABEL_SMOOTHING),
        metrics=['accuracy', 'top_k_categorical_accuracy']
    )
    
    history2 = model.fit(
        train_ds,
        epochs=Config.FREEZE_EPOCHS + Config.PARTIAL_EPOCHS,
        initial_epoch=Config.FREEZE_EPOCHS,
        validation_data=val_ds,
        class_weight=class_weights,
        callbacks=create_ultra_callbacks('partial'),
        verbose=1
    )
    
    # ================================================================
    # PHASE 3: FULL FINE-TUNING
    # ================================================================
    print("\n" + "="*60)
    print("PHASE 3: Full Fine-Tuning (All Layers)")
    print("="*60)
    
    # Rebuild with full unfreezing
    model = create_ultra_model(phase='full')
    
    # Load best weights from phase 2
    best_phase2 = os.path.join(Config.OUTPUT_DIR, 'ultra_model_partial_best.keras')
    if os.path.exists(best_phase2):
        model.load_weights(best_phase2)
    
    # Lower learning rate for full fine-tuning
    model.compile(
        optimizer=optimizers.Adam(learning_rate=Config.INITIAL_LR / 10),
        loss=keras.losses.CategoricalCrossentropy(label_smoothing=Config.LABEL_SMOOTHING),
        metrics=['accuracy', 'top_k_categorical_accuracy']
    )
    
    history3 = model.fit(
        train_ds,
        epochs=Config.EPOCHS,
        initial_epoch=Config.FREEZE_EPOCHS + Config.PARTIAL_EPOCHS,
        validation_data=val_ds,
        class_weight=class_weights,
        callbacks=create_ultra_callbacks('full'),
        verbose=1
    )
    
    # ================================================================
    # SAVE FINAL MODEL
    # ================================================================
    final_model_path = os.path.join(Config.OUTPUT_DIR, 'plant_disease_ultra_90plus.keras')
    model.save(final_model_path)
    
    # Save class indices
    class_indices = {name: idx for idx, name in enumerate(Config.CLASS_NAMES)}
    with open(os.path.join(Config.OUTPUT_DIR, 'ultra_class_indices.json'), 'w') as f:
        json.dump(class_indices, f, indent=2)
    
    # ================================================================
    # EVALUATION
    # ================================================================
    print("\n" + "="*60)
    print("📊 FINAL EVALUATION")
    print("="*60)
    
    # Standard evaluation
    val_loss, val_acc, val_top5 = model.evaluate(val_ds, verbose=1)
    print(f"\n✅ Validation Accuracy: {val_acc*100:.2f}%")
    print(f"✅ Validation Top-5 Accuracy: {val_top5*100:.2f}%")
    
    # Test-Time Augmentation evaluation
    print("\n🔄 Evaluating with Test-Time Augmentation (TTA)...")
    tta_model = create_tta_model(model)
    
    tta_correct = 0
    tta_total = 0
    
    for images, labels in val_ds:
        preds = tta_model.predict(images, verbose=0)
        tta_correct += np.sum(np.argmax(preds, axis=1) == np.argmax(labels.numpy(), axis=1))
        tta_total += len(labels)
    
    tta_acc = tta_correct / tta_total
    print(f"✅ TTA Accuracy: {tta_acc*100:.2f}% (+{(tta_acc-val_acc)*100:.2f}%)")
    
    # Save metadata
    metadata = {
        "model": "plant_disease_ultra_90plus.keras",
        "validation_accuracy": float(val_acc),
        "validation_top5": float(val_top5),
        "tta_accuracy": float(tta_acc),
        "img_size": Config.IMG_SIZE,
        "backbone": "EfficientNetV2B3",
        "epochs": Config.EPOCHS,
        "batch_size": Config.BATCH_SIZE,
        "tta_rounds": Config.TTA_ROUNDS
    }
    
    with open(os.path.join(Config.OUTPUT_DIR, 'ultra_metadata.json'), 'w') as f:
        json.dump(metadata, f, indent=2)
    
    print("\n" + "="*60)
    print("🎉 TRAINING COMPLETE!")
    print(f"📁 Model: {final_model_path}")
    print(f"📁 Class indices: ultra_class_indices.json")
    print(f"📁 Metadata: ultra_metadata.json")
    print("="*60)
    
    # Update app.py instructions
    print("\n📝 To use this model in your app:")
    print("1. Update MODEL_CANDIDATES in backend/app.py:")
    print('   "../models/plant_disease_ultra_90plus.keras",')
    print("2. Update image size to 380x380 in preprocessing")
    print("3. Add TTA for 2-3% accuracy boost")
    
    return model, metadata

if __name__ == "__main__":
    # Check GPU
    gpus = tf.config.list_physical_devices('GPU')
    if gpus:
        print(f"✅ GPU available: {len(gpus)} device(s)")
        for gpu in gpus:
            print(f"   {gpu}")
    else:
        print("⚠️  No GPU detected - training will be slow on CPU")
    
    # Run training
    train_ultra_model()
