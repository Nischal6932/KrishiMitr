import os
import requests
import tensorflow as tf
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

# Global model variable
model = None

def download_model_from_github():
    """
    Download ML model from GitHub Releases
    """
    # Updated to use the best performing model (78.92% accuracy)
    model_url = "https://github.com/Nischal6932/No_Ollama/releases/download/v1.0/plant_disease_best_model.keras"
    model_path = "plant_disease_best_model.keras"
    
    # Check if model already exists
    if os.path.exists(model_path):
        logger.info(f"Model already exists at {model_path}")
        return model_path
    
    try:
        logger.info("Downloading model from GitHub Releases...")
        response = requests.get(model_url, stream=True)
        response.raise_for_status()
        
        # Save model with progress indication
        with open(model_path, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192):
                f.write(chunk)
        
        logger.info(f"Model downloaded successfully: {model_path}")
        return model_path
        
    except Exception as e:
        logger.error(f"Failed to download model: {e}")
        return None

# Update the get_model() function to use this
def get_model():
    """
    Enhanced model loading with GitHub download
    """
    global model
    if model is None:
        try:
            # Try to download model if not present
            model_path = download_model_from_github()
            if not model_path:
                logger.warning("Model not available, using fallback mode")
                model = None
                return model
            
            # Load model with memory-efficient settings
            model = tf.keras.models.load_model(model_path, compile=False)
            logger.info("Model loaded successfully")
            
        except Exception as e:
            logger.error(f"Model loading failed: {e}")
            model = None
    
    return model
