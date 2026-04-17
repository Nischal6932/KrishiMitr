#!/usr/bin/env python3
"""Create ensemble model combining multiple models for better performance."""

import json
import os
import sys
from pathlib import Path
import numpy as np
import tensorflow as tf
from sklearn.metrics import accuracy_score, classification_report

os.environ.setdefault("MPLCONFIGDIR", "/tmp")

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

def load_test_data(data_dir: Path, image_size=(160, 160)):
    """Load test data for evaluation."""
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
                    image = tf.keras.preprocessing.image.load_img(
                        image_path, target_size=image_size
                    )
                    image_array = tf.keras.preprocessing.image.img_to_array(image)
                    image_array = image_array / 255.0
                    
                    images.append(image_array)
                    labels.append(label_idx)
                except Exception as e:
                    continue
    
    return np.array(images), np.array(labels)

def load_available_models(models_dir: Path):
    """Load all available models."""
    models = {}
    model_files = [
        "best_simple_cnn.keras",
        "best_mobilenetv3.keras", 
        "plant_disease_realworld_15class_best_v4.keras",
        "plant_disease_repo_finetuned.keras",
        "fixed_plant_disease_repo_mobilenet.keras",
        "fixed_potato_specialist.keras"
    ]
    
    for model_file in model_files:
        model_path = models_dir / model_file
        if model_path.exists():
            try:
                model = tf.keras.models.load_model(model_path, compile=False)
                models[model_file.replace('.keras', '')] = model
                print(f"Loaded: {model_file}")
            except Exception as e:
                print(f"Failed to load {model_file}: {e}")
    
    return models

def create_ensemble_predictor(models):
    """Create ensemble prediction function."""
    def predict_ensemble(X):
        predictions = []
        
        for model_name, model in models.items():
            try:
                pred = model.predict(X, verbose=0)
                predictions.append(pred)
            except Exception as e:
                print(f"Error in model {model_name}: {e}")
                continue
        
        if not predictions:
            raise ValueError("No models could make predictions")
        
        # Average predictions (simple ensemble)
        ensemble_pred = np.mean(predictions, axis=0)
        return ensemble_pred
    
    return predict_ensemble

def create_weighted_ensemble(models, weights=None):
    """Create weighted ensemble prediction function."""
    if weights is None:
        # Equal weights for all models
        weights = [1.0 / len(models)] * len(models)
    
    def predict_weighted_ensemble(X):
        predictions = []
        valid_weights = []
        
        for i, (model_name, model) in enumerate(models.items()):
            try:
                pred = model.predict(X, verbose=0)
                predictions.append(pred)
                valid_weights.append(weights[i])
            except Exception as e:
                print(f"Error in model {model_name}: {e}")
                continue
        
        if not predictions:
            raise ValueError("No models could make predictions")
        
        # Normalize weights
        valid_weights = np.array(valid_weights)
        valid_weights = valid_weights / np.sum(valid_weights)
        
        # Weighted average
        ensemble_pred = np.zeros_like(predictions[0])
        for pred, weight in zip(predictions, valid_weights):
            ensemble_pred += weight * pred
        
        return ensemble_pred
    
    return predict_weighted_ensemble

def evaluate_ensemble(models, X_test, y_test):
    """Evaluate ensemble performance."""
    print(f"\nEvaluating ensemble of {len(models)} models...")
    
    # Test individual models
    individual_results = {}
    for model_name, model in models.items():
        try:
            pred = model.predict(X_test, verbose=0)
            pred_classes = np.argmax(pred, axis=1)
            accuracy = accuracy_score(y_test, pred_classes)
            individual_results[model_name] = accuracy
            print(f"{model_name}: {accuracy:.4f}")
        except Exception as e:
            print(f"Error evaluating {model_name}: {e}")
            individual_results[model_name] = 0.0
    
    # Test simple ensemble
    try:
        ensemble_predictor = create_ensemble_predictor(models)
        ensemble_pred = ensemble_predictor(X_test)
        ensemble_classes = np.argmax(ensemble_pred, axis=1)
        ensemble_accuracy = accuracy_score(y_test, ensemble_classes)
        print(f"Simple Ensemble: {ensemble_accuracy:.4f}")
    except Exception as e:
        print(f"Error in simple ensemble: {e}")
        ensemble_accuracy = 0.0
    
    # Test weighted ensemble (weight by individual performance)
    try:
        weights = list(individual_results.values())
        weights = np.array(weights)
        weights = weights / np.sum(weights)  # Normalize
        
        weighted_predictor = create_weighted_ensemble(models, weights)
        weighted_pred = weighted_predictor(X_test)
        weighted_classes = np.argmax(weighted_pred, axis=1)
        weighted_accuracy = accuracy_score(y_test, weighted_classes)
        print(f"Weighted Ensemble: {weighted_accuracy:.4f}")
    except Exception as e:
        print(f"Error in weighted ensemble: {e}")
        weighted_accuracy = 0.0
    
    return {
        'individual_models': individual_results,
        'simple_ensemble': ensemble_accuracy,
        'weighted_ensemble': weighted_accuracy
    }

def main():
    """Main ensemble evaluation function."""
    models_dir = Path(__file__).resolve().parent
    plantvillage_dir = models_dir.parent / "data" / "datasets" / "plant_disease_dataset" / "raw" / "plantvillage"
    
    if not plantvillage_dir.exists():
        print(f"Error: PlantVillage dataset not found at {plantvillage_dir}")
        sys.exit(1)
    
    print("Loading test data...")
    X_test, y_test = load_test_data(plantvillage_dir)
    print(f"Loaded {len(X_test)} test images")
    
    print("Loading available models...")
    models = load_available_models(models_dir)
    
    if not models:
        print("No models found for ensemble!")
        sys.exit(1)
    
    print(f"\nFound {len(models)} models for ensemble")
    
    # Evaluate ensemble
    results = evaluate_ensemble(models, X_test, y_test)
    
    # Save results
    results_file = models_dir / "ensemble_results.json"
    with results_file.open('w') as f:
        json.dump(results, f, indent=2)
    
    print(f"\n{'='*60}")
    print("ENSEMBLE RESULTS")
    print(f"{'='*60}")
    
    print("\nIndividual Model Performance:")
    for model_name, accuracy in results['individual_models'].items():
        print(f"  {model_name}: {accuracy:.4f}")
    
    print(f"\nEnsemble Performance:")
    print(f"  Simple Ensemble: {results['simple_ensemble']:.4f}")
    print(f"  Weighted Ensemble: {results['weighted_ensemble']:.4f}")
    
    # Find best method
    all_results = {
        'individual': max(results['individual_models'].values()),
        'simple_ensemble': results['simple_ensemble'],
        'weighted_ensemble': results['weighted_ensemble']
    }
    
    best_method = max(all_results.items(), key=lambda x: x[1])
    print(f"\nBEST METHOD: {best_method[0]} with accuracy {best_method[1]:.4f}")
    
    print(f"\nDetailed results saved to: {results_file}")

if __name__ == "__main__":
    main()
