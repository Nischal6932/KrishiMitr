#!/usr/bin/env python3
"""
Create a simple fallback model for testing purposes
"""

import tensorflow as tf
import numpy as np
from tensorflow import keras
from tensorflow.keras import layers, models

def create_simple_model():
    """Create a simple model for testing"""
    model = models.Sequential([
        layers.Input(shape=(160, 160, 3)),
        layers.Conv2D(16, (3, 3), activation='relu'),
        layers.MaxPooling2D(2, 2),
        layers.Conv2D(32, (3, 3), activation='relu'),
        layers.MaxPooling2D(2, 2),
        layers.Conv2D(64, (3, 3), activation='relu'),
        layers.MaxPooling2D(2, 2),
        layers.Flatten(),
        layers.Dense(128, activation='relu'),
        layers.Dense(15, activation='softmax')  # 15 classes
    ])
    
    model.compile(optimizer='adam',
                 loss='categorical_crossentropy',
                 metrics=['accuracy'])
    
    return model

# Create and save the model
model = create_simple_model()
model.save('plant_disease_realworld_15class_best_v4.keras')
print("✅ Fallback model created successfully!")
