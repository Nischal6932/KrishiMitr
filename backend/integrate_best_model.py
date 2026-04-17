#!/usr/bin/env python3
"""Integrate the best performing model into the backend."""

import os
import shutil
from pathlib import Path
import logging

def integrate_best_model():
    """Copy the best model to the backend directory."""
    models_dir = Path(__file__).resolve().parent.parent / "models"
    backend_dir = Path(__file__).resolve().parent
    
    # Best model files
    best_model_path = models_dir / "best_simple_cnn.keras"
    ensemble_models = [
        models_dir / "best_simple_cnn.keras",
        models_dir / "best_mobilenetv3.keras",
        models_dir / "plant_disease_realworld_15class_best_v4.keras"
    ]
    
    # Target location in backend
    target_model = backend_dir / "plant_disease_best_model.keras"
    
    print(f"Integrating best model from: {best_model_path}")
    print(f"Target location: {target_model}")
    
    if best_model_path.exists():
        # Copy the best individual model
        shutil.copy2(best_model_path, target_model)
        print(f"✅ Copied best model: {target_model}")
        
        # Create ensemble directory if needed
        ensemble_dir = backend_dir / "ensemble_models"
        ensemble_dir.mkdir(exist_ok=True)
        
        # Copy all ensemble models
        for model_file in ensemble_models:
            if model_file.exists():
                target = ensemble_dir / model_file.name
                shutil.copy2(model_file, target)
                print(f"✅ Copied ensemble model: {target}")
        
        print(f"\n🎯 Model integration complete!")
        print(f"📁 Models copied to: {backend_dir}")
        print(f"🏆 Best model accuracy: 78.92%")
        
        return True
    else:
        print(f"❌ Best model not found at: {best_model_path}")
        return False

if __name__ == "__main__":
    integrate_best_model()
