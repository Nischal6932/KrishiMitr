#!/usr/bin/env python3
"""Ensemble predictor for the best models."""

import os
import numpy as np
import tensorflow as tf
from pathlib import Path
import logging

logger = logging.getLogger(__name__)

class EnsemblePredictor:
    def __init__(self):
        self.models = {}
        self.load_models()
    
    def load_models(self):
        """Load all available ensemble models."""
        models_dir = Path(__file__).resolve().parent / "ensemble_models"
        
        model_files = [
            "best_simple_cnn.keras",
            "best_mobilenetv3.keras", 
            "plant_disease_realworld_15class_best_v4.keras"
        ]
        
        for model_file in model_files:
            model_path = models_dir / model_file
            if model_path.exists():
                try:
                    model = tf.keras.models.load_model(model_path, compile=False)
                    self.models[model_file.replace('.keras', '')] = model
                    logger.info(f"Loaded ensemble model: {model_file}")
                except Exception as e:
                    logger.error(f"Failed to load {model_file}: {e}")
        
        if not self.models:
            logger.warning("No ensemble models loaded!")
    
    def predict(self, image_array):
        """Make ensemble prediction."""
        if not self.models:
            raise ValueError("No models available for ensemble prediction")
        
        predictions = []
        
        for model_name, model in self.models.items():
            try:
                pred = model.predict(image_array, verbose=0)
                predictions.append(pred)
            except Exception as e:
                logger.error(f"Error in model {model_name}: {e}")
                continue
        
        if not predictions:
            raise ValueError("No models could make predictions")
        
        # Simple average ensemble
        ensemble_pred = np.mean(predictions, axis=0)
        return ensemble_pred
    
    def get_model_count(self):
        """Get number of loaded models."""
        return len(self.models)

# Global ensemble predictor instance
ensemble_predictor = None

def get_ensemble_predictor():
    """Get or create ensemble predictor."""
    global ensemble_predictor
    if ensemble_predictor is None:
        ensemble_predictor = EnsemblePredictor()
    return ensemble_predictor
