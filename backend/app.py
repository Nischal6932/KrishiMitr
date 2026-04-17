from flask import Flask, request, render_template, jsonify, g, has_request_context
import logging
import numpy as np
from pathlib import Path
from PIL import Image, ImageEnhance
import os
import json
import uuid
try:
    from flask_cors import CORS
except Exception:  # pragma: no cover - optional dependency fallback
    def CORS(app, *args, **kwargs):
        return app

from werkzeug.middleware.proxy_fix import ProxyFix

tf = None

try:
    from gtts import gTTS
except Exception:  # pragma: no cover - optional dependency fallback
    gTTS = None

try:
    import cv2
except Exception:  # pragma: no cover - optional dependency fallback
    cv2 = None

try:
    from deep_translator import GoogleTranslator
except Exception:  # pragma: no cover - optional dependency fallback
    GoogleTranslator = None
# from gradcam_fixed import generate_gradcam  # Commented out - module not found
try:
    from .cache_service import cache_service, cached
    from .error_handler import handle_errors, log_api_request, AIServiceError, ValidationError
    from .config import config as config_map
    from .farmer_actions import (
        build_farmer_action_bundle,
        filter_marketplace_catalog,
        store_expert_support_request,
        validate_expert_support_payload,
    )
    from .security import FileValidator, validate_ai_advice_request, validate_upload_request
except ImportError:  # pragma: no cover - support direct script imports
    from cache_service import cache_service, cached
    from error_handler import handle_errors, log_api_request, AIServiceError, ValidationError
    from config import config as config_map
    from farmer_actions import (
        build_farmer_action_bundle,
        filter_marketplace_catalog,
        store_expert_support_request,
        validate_expert_support_payload,
    )
    from security import FileValidator, validate_ai_advice_request, validate_upload_request
from scipy.special import softmax


def generate_gradcam(_image_path):
    """Graceful placeholder until the Grad-CAM module is restored."""
    return None


def get_runtime_config():
    """Select the Flask config class based on environment variables."""
    if os.environ.get("PYTEST_CURRENT_TEST"):
        env_name = "testing"
    else:
        env_name = os.environ.get("ENVIRONMENT", "development").lower()
    return config_map.get(env_name, config_map["default"])


class RequestFormatter(logging.Formatter):
    """Attach request context to application logs when available."""

    def format(self, record):
        if has_request_context():
            record.request_id = getattr(g, "request_id", "-")
            record.method = request.method
            record.path = request.path
            record.remote_addr = request.headers.get("X-Forwarded-For", request.remote_addr or "-")
        else:
            record.request_id = "-"
            record.method = "-"
            record.path = "-"
            record.remote_addr = "-"
        return super().format(record)


def configure_logging():
    """Set application logging format for local and production runs."""
    log_level = os.environ.get("LOG_LEVEL", "INFO").upper()
    root_logger = logging.getLogger()
    root_logger.setLevel(log_level)

    formatter = RequestFormatter(
        "%(asctime)s %(levelname)s [%(name)s] request_id=%(request_id)s "
        "method=%(method)s path=%(path)s remote=%(remote_addr)s %(message)s"
    )

    if not root_logger.handlers:
        handler = logging.StreamHandler()
        handler.setFormatter(formatter)
        root_logger.addHandler(handler)
    else:
        for handler in root_logger.handlers:
            handler.setFormatter(formatter)

# ---- PREDICT.PY MODEL WITH ENSEMBLE BOOSTING ----
# Using ensemble predictions for higher confidence without distortion

# Load trained model - Prioritizing best performing models
BASE_DIR = Path(__file__).resolve().parent.parent
BACKEND_DIR = BASE_DIR / "backend"
FRONTEND_DIR = BASE_DIR / "frontend"
FRONTEND_PUBLIC_DIR = FRONTEND_DIR / "public"
UPLOADS_DIR = FRONTEND_PUBLIC_DIR / "uploads"
MODEL_DIR = BASE_DIR / "models"
CONFIG_ENV_PATH = BASE_DIR / "config" / ".env"
MODEL_CONFIG_PATH = MODEL_DIR / "model_config.json"
POTATO_SPECIALIST_MODEL_PATH = MODEL_DIR / "potato_specialist.keras"
POTATO_SPECIALIST_METADATA_PATH = MODEL_DIR / "potato_specialist_metadata.json"

MODEL_CANDIDATES = [
    str(BACKEND_DIR / "plant_disease_best_model.keras"),  # NEW Best model: 78.92% accuracy
    str(MODEL_DIR / "plant_disease_realworld_15class_best_v4.keras"),  # Fallback: 79.52% accuracy
    str(MODEL_DIR / "plant_disease_repo_finetuned.keras"),
    str(MODEL_DIR / "plant_disease_realworld_15class_best.keras"),     # Previous version: 68.69% accuracy
]
CLASS_INDEX_CANDIDATES = [
    str(MODEL_DIR / "strict_15_class_indices.json"),
    str(MODEL_DIR / "class_indices.json"),
    str(MODEL_DIR / "improved_class_indices.json"),
]
DEFAULT_CLASS_NAMES = [
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
    "Tomato_healthy",
]
model = None
potato_specialist_model = None
CROP_CLASS_PREFIXES = {
    "Tomato": ("Tomato",),
    "Potato": ("Potato",),
    "Pepper": ("Pepper", "Pepper__bell"),
}
POTATO_SPECIALIST_CLASSES = [
    "Potato___Early_blight",
    "Potato___Late_blight",
    "Potato___healthy",
]

def load_model_metadata():
    """Load model metadata and deployment-time inference settings."""
    default_metadata = {
        "preprocessing": {"image_size": [160, 160]},
        "class_mapping": {"classes": DEFAULT_CLASS_NAMES, "num_classes": len(DEFAULT_CLASS_NAMES)},
        "confidence_thresholds": {"high": 0.8, "medium": 0.6, "low": 0.4},
        "ensemble": {"enabled": True, "variants": ["original", "contrast_boost", "brightness_adjust"], "temperature": 1.0},
    }

    if not MODEL_CONFIG_PATH.exists():
        return default_metadata

    try:
        with open(MODEL_CONFIG_PATH) as f:
            loaded = json.load(f)
        default_metadata.update(loaded)
    except Exception as exc:
        logging.getLogger(__name__).warning(f"Failed to load model metadata: {exc}")

    return default_metadata


MODEL_METADATA = load_model_metadata()


def load_class_names():
    canonical_classes = MODEL_METADATA.get("class_mapping", {}).get("classes") or DEFAULT_CLASS_NAMES

    for path in CLASS_INDEX_CANDIDATES:
        if os.path.exists(path):
            try:
                with open(path) as f:
                    class_indices = json.load(f)
                loaded_classes = [name for name, _ in sorted(class_indices.items(), key=lambda item: item[1])]
                if len(loaded_classes) == len(canonical_classes):
                    return loaded_classes
                logging.getLogger(__name__).warning(
                    f"Class mapping {path} has {len(loaded_classes)} classes; expected {len(canonical_classes)}. "
                    "Using canonical classes from model_config.json."
                )
                break
            except Exception as e:
                logging.getLogger(__name__).warning(f"Failed to load class names from {path}: {e}")
    return canonical_classes


class_names = load_class_names()
MODEL_IMAGE_SIZE = tuple(MODEL_METADATA.get("preprocessing", {}).get("image_size", [160, 160]))
ENSEMBLE_TEMPERATURE = float(MODEL_METADATA.get("ensemble", {}).get("temperature", 1.0))
CONFIDENCE_THRESHOLDS = MODEL_METADATA.get("confidence_thresholds", {"high": 0.8, "medium": 0.6, "low": 0.4})


def load_potato_specialist_metadata():
    default_metadata = {
        "class_names": POTATO_SPECIALIST_CLASSES,
        "image_size": [224, 224],
        "metrics": {},
    }
    if not POTATO_SPECIALIST_METADATA_PATH.exists():
        return default_metadata
    try:
        with POTATO_SPECIALIST_METADATA_PATH.open() as f:
            loaded = json.load(f)
        default_metadata.update(loaded)
    except Exception as exc:
        logging.getLogger(__name__).warning(f"Failed to load potato specialist metadata: {exc}")
    return default_metadata


POTATO_SPECIALIST_METADATA = load_potato_specialist_metadata()
POTATO_SPECIALIST_IMAGE_SIZE = tuple(POTATO_SPECIALIST_METADATA.get("image_size", [224, 224]))


def normalize_prediction_scores(raw_prediction, temperature=1.0):
    """Convert model outputs into a stable probability distribution."""
    scores = np.asarray(raw_prediction, dtype=np.float64).squeeze()

    if scores.ndim != 1:
        scores = scores.reshape(-1)

    if scores.size == 0:
        raise ValueError("Prediction output is empty")

    if np.any(np.isnan(scores)) or np.any(np.isinf(scores)):
        scores = np.nan_to_num(scores, nan=0.0, posinf=0.0, neginf=0.0)

    positive_scores = np.clip(scores, 0.0, None)
    positive_sum = float(np.sum(positive_scores))

    if np.all(scores >= 0.0) and np.isclose(positive_sum, 1.0, atol=1e-3):
        probs = positive_scores
    else:
        safe_temperature = max(float(temperature), 1e-3)
        logits = scores / safe_temperature
        logits = logits - np.max(logits)
        exp_logits = np.exp(logits)
        probs = exp_logits / np.sum(exp_logits)

    probs = np.clip(probs, 1e-10, None)
    probs = probs / np.sum(probs)
    return probs


def resize_for_model(image):
    """Resize images using the deployed model's expected input size."""
    return image.resize(MODEL_IMAGE_SIZE)


def resize_for_potato_specialist(image):
    """Resize images using the potato specialist model's expected input size."""
    return image.resize(POTATO_SPECIALIST_IMAGE_SIZE)


def geometric_consensus(predictions):
    """
    Combine multiple probability vectors using a geometric mean.
    This sharpens confidence only when variants agree.
    """
    stacked = np.asarray(predictions, dtype=np.float64)
    stacked = np.clip(stacked, 1e-10, 1.0)
    log_probs = np.log(stacked)
    consensus = np.exp(np.mean(log_probs, axis=0))
    return consensus / np.sum(consensus)


def get_crop_relevant_indices(crop_name):
    """Return indices that match the selected crop."""
    prefixes = CROP_CLASS_PREFIXES.get(crop_name)
    if not prefixes:
        return []

    indices = [
        idx for idx, name in enumerate(class_names)
        if any(name.startswith(prefix) for prefix in prefixes)
    ]
    return indices


def apply_crop_context(prediction, crop_name):
    """
    Reweight predictions toward classes that match the user-selected crop.
    This uses user-provided context instead of inflating confidence blindly.
    """
    probs = normalize_prediction_scores(prediction)
    crop_indices = get_crop_relevant_indices(crop_name)
    crop_indices = [idx for idx in crop_indices if idx < len(probs)]

    if not crop_indices:
        return probs

    crop_mass = float(np.sum(probs[crop_indices]))
    if crop_mass <= 0:
        return probs

    contextual_probs = np.zeros_like(probs)
    contextual_probs[crop_indices] = probs[crop_indices] / crop_mass
    return contextual_probs


def summarize_prediction(prediction):
    """Build a compact prediction summary used by the route and tests."""
    probs = normalize_prediction_scores(prediction)
    sorted_indices = np.argsort(probs)[::-1]
    best_idx = int(sorted_indices[0])
    second_idx = int(sorted_indices[1]) if len(sorted_indices) > 1 else best_idx

    return {
        "probabilities": probs,
        "best_idx": best_idx,
        "second_idx": second_idx,
        "confidence": float(probs[best_idx]),
        "second_confidence": float(probs[second_idx]),
        "top2_predictions": [
            (class_names[best_idx], float(probs[best_idx])),
            (class_names[second_idx], float(probs[second_idx]))
        ],
    }


def get_model_path():
    for path in MODEL_CANDIDATES:
        if os.path.exists(path):
            return path
    return MODEL_CANDIDATES[0]

def get_ensemble_prediction(image_path, model):
    """
    Get a consensus prediction using multiple low-distortion views.
    Confidence rises only when variants agree.
    """
    try:
        img = resize_for_model(Image.open(image_path).convert("RGB"))

        variants = []
        variants.append(np.array(img))

        contrast_variant = ImageEnhance.Contrast(img).enhance(1.08)
        variants.append(np.array(contrast_variant))

        brightness_variant = ImageEnhance.Brightness(img).enhance(1.04)
        variants.append(np.array(brightness_variant))

        detail_variant = ImageEnhance.Sharpness(img).enhance(1.08)
        variants.append(np.array(detail_variant))

        all_preds = []
        for variant in variants:
            img_norm = variant / 255.0
            img_batch = np.expand_dims(img_norm, axis=0)
            pred = model.predict(img_batch, verbose=0).squeeze()
            all_preds.append(normalize_prediction_scores(pred, temperature=ENSEMBLE_TEMPERATURE))

        original = all_preds[0]
        consensus = geometric_consensus(all_preds)
        final_pred = (0.55 * original) + (0.45 * consensus)
        return final_pred / np.sum(final_pred)
        
    except Exception as e:
        logger.error(f"Ensemble prediction error: {e}")
        img = resize_for_model(Image.open(image_path).convert("RGB"))
        img_array = np.array(img) / 255.0
        img_batch = np.expand_dims(img_array, axis=0)
        return normalize_prediction_scores(model.predict(img_batch, verbose=0).squeeze(), temperature=ENSEMBLE_TEMPERATURE)

def get_model():
    global model
    global tf
    if model is None:
        try:
            if tf is None:
                try:
                    import tensorflow as tensorflow_module
                    tf = tensorflow_module
                except Exception:
                    logger.error("TensorFlow is not installed; model loading is unavailable")
                    return None
            model_path = get_model_path()
            if not os.path.exists(model_path):
                logger.info("Model not found locally. Downloading fallback model...")
                download_model_from_github()
                model_path = get_model_path()

            model = tf.keras.models.load_model(model_path)
            logger.info(f"Model loaded successfully from {model_path}")

        except Exception as e:
            logger.error(f"Model load failed: {e}")
            model = None

    return model


def get_potato_specialist_model():
    global potato_specialist_model
    global tf
    if potato_specialist_model is None:
        try:
            if tf is None:
                import tensorflow as tensorflow_module
                tf = tensorflow_module
            if not POTATO_SPECIALIST_MODEL_PATH.exists():
                return None
            potato_specialist_model = tf.keras.models.load_model(POTATO_SPECIALIST_MODEL_PATH, compile=False)
            logger.info(f"Potato specialist model loaded from {POTATO_SPECIALIST_MODEL_PATH}")
        except Exception as exc:
            logger.error(f"Potato specialist model load failed: {exc}")
            potato_specialist_model = None
    return potato_specialist_model


def expand_specialist_prediction_to_global(prediction, specialist_classes):
    """Map a crop-specialist probability vector back to the 15-class app output."""
    probs = normalize_prediction_scores(prediction)
    expanded = np.zeros(len(class_names), dtype=np.float64)
    for idx, class_name in enumerate(specialist_classes):
        if idx >= len(probs) or class_name not in class_names:
            continue
        expanded[class_names.index(class_name)] = probs[idx]
    if np.sum(expanded) <= 0:
        raise ValueError("Specialist prediction could not be mapped to global classes")
    return expanded / np.sum(expanded)


def get_potato_specialist_prediction(image_path, model):
    """Run the potato specialist model with the same low-distortion ensemble strategy."""
    img = resize_for_potato_specialist(Image.open(image_path).convert("RGB"))
    variants = [
        np.array(img),
        np.array(ImageEnhance.Contrast(img).enhance(1.08)),
        np.array(ImageEnhance.Brightness(img).enhance(1.04)),
        np.array(ImageEnhance.Sharpness(img).enhance(1.08)),
    ]
    all_preds = []
    for variant in variants:
        img_norm = variant / 255.0
        img_batch = np.expand_dims(img_norm, axis=0)
        pred = model.predict(img_batch, verbose=0).squeeze()
        all_preds.append(normalize_prediction_scores(pred))
    original = all_preds[0]
    consensus = geometric_consensus(all_preds)
    specialist_pred = (0.50 * original) + (0.50 * consensus)
    specialist_pred = specialist_pred / np.sum(specialist_pred)
    return expand_specialist_prediction_to_global(specialist_pred, POTATO_SPECIALIST_METADATA.get("class_names", POTATO_SPECIALIST_CLASSES))

def get_improved_prediction(image_path, model):
    """
    Simple prediction matching exact training preprocessing
    """
    try:
        # Simple preprocessing - EXACTLY like training
        img = resize_for_model(Image.open(image_path).convert("RGB"))
        img_array = np.array(img) / 255.0
        img_batch = np.expand_dims(img_array, axis=0)
        
        # Predict and calibrate to a valid probability distribution
        pred = model.predict(img_batch, verbose=0).squeeze()
        pred = normalize_prediction_scores(pred, temperature=ENSEMBLE_TEMPERATURE)
        
        # DEBUG: Show top 5 predictions
        top_indices = np.argsort(pred)[::-1][:5]
        logger.info("=== MODEL PREDICTIONS ===")
        for i, idx in enumerate(top_indices):
            logger.info(f"  {i+1}. {class_names[idx]}: {pred[idx]*100:.2f}%")
        logger.info(f"Sum of all probs: {np.sum(pred):.4f}")
        
        return pred
        
    except Exception as e:
        logger.error(f"Improved prediction error: {e}")
        # Ultimate fallback
        return get_fallback_prediction(image_path)

def enhance_image_contrast(img_array):
    """Enhance image contrast for better feature extraction"""
    if cv2 is None:
        return img_array
    try:
        # Convert to uint8 for histogram equalization
        img_uint8 = (img_array * 255).astype(np.uint8)
        
        # Apply CLAHE (Contrast Limited Adaptive Histogram Equalization)
        img_lab = cv2.cvtColor(img_uint8, cv2.COLOR_RGB2LAB)
        l, a, b = cv2.split(img_lab)
        
        # Apply CLAHE to L channel
        clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8,8))
        l = clahe.apply(l)
        
        # Merge channels and convert back
        img_lab = cv2.merge([l, a, b])
        img_enhanced = cv2.cvtColor(img_lab, cv2.COLOR_LAB2RGB)
        
        return img_enhanced.astype(np.float32) / 255.0
        
    except Exception as e:
        logger.error(f"Contrast enhancement error: {e}")
        # Return original if enhancement fails
        return img_array

def assess_prediction_uncertainty(prediction):
    """Estimate whether the model is too unsure to trust a real-world image classification."""
    probs = np.asarray(prediction, dtype=np.float64)
    probs = np.clip(probs, 1e-10, 1.0)
    probs = probs / np.sum(probs)

    sorted_probs = np.sort(probs)[::-1]
    best = float(sorted_probs[0])
    second = float(sorted_probs[1]) if len(sorted_probs) > 1 else 0.0
    margin = best - second

    entropy = -np.sum(probs * np.log(probs))
    normalized_entropy = float(entropy / np.log(len(probs))) if len(probs) > 1 else 0.0

    medium_threshold = float(CONFIDENCE_THRESHOLDS.get("medium", 0.6))

    is_uncertain = (
        best < max(0.35, medium_threshold - 0.1) or
        margin < 0.10 or
        normalized_entropy > 0.72
    )

    return {
        "best": best,
        "second": second,
        "margin": margin,
        "normalized_entropy": normalized_entropy,
        "is_uncertain": is_uncertain,
    }

def get_fallback_prediction(image_path):
    """Fallback prediction using simple image analysis"""
    try:
        img = resize_for_model(Image.open(image_path).convert("RGB"))
        img_array = np.array(img)
        
        # Simple color-based analysis
        avg_green = np.mean(img_array[:, :, 1])
        avg_red = np.mean(img_array[:, :, 0])
        avg_brown = (np.mean(img_array[:, :, 0]) + np.mean(img_array[:, :, 1])) / 2
        
        # Heuristic rules
        if avg_green > 100 and avg_red < 80:
            # Likely healthy (high green, low red)
            result_class = "Tomato_healthy"
            confidence = 0.75
        elif avg_brown > 120:
            # Likely disease (high brown/red tones)
            result_class = "Tomato_Bacterial_spot"
            confidence = 0.65
        else:
            # Uncertain
            result_class = "Tomato_healthy"
            confidence = 0.55
        
        # Create prediction array
        prediction = np.zeros(len(class_names))
        try:
            class_idx = class_names.index(result_class)
            prediction[class_idx] = confidence
        except ValueError:
            # If class not found, use first class
            prediction[0] = confidence
        
        # Distribute remaining confidence
        remaining = 1.0 - confidence
        for i in range(len(class_names)):
            if prediction[i] == 0:
                prediction[i] = remaining / (len(class_names) - 1)
        
        return prediction
        
    except Exception as e:
        logger.error(f"Fallback prediction error: {e}")
        return np.ones(len(class_names)) / len(class_names)
# ---- Logging and dotenv setup ----
import time
from dotenv import load_dotenv
load_dotenv(dotenv_path=CONFIG_ENV_PATH)

configure_logging()
logger = logging.getLogger(__name__)

UPLOADS_DIR.mkdir(parents=True, exist_ok=True)

try:
    from groq import Groq
except Exception:  # pragma: no cover - optional dependency fallback
    Groq = None

api_key = os.environ.get("GROQ_API_KEY")

if api_key and Groq is not None:
    client = Groq(api_key=api_key)
    logger.info("GROQ connected")
else:
    client = None
    logger.warning("GROQ disabled (no API key)")

def ask_llm(prompt):
    if client is None:
        return "AI service is not available right now. Please try again later."

    try:
        # Check cache first
        import hashlib
        cache_key = f"llm_response_{hashlib.md5(prompt.encode()).hexdigest()}"
        cached_response = cache_service.get(cache_key)
        if cached_response:
            logger.info("LLM cache hit")
            return cached_response

        # Using updated Groq supported model
        chat_completion = client.chat.completions.create(
            messages=[
                {"role": "user", "content": prompt}
            ],
            model="llama-3.1-8b-instant"
        )
        response = chat_completion.choices[0].message.content
        
        # Cache the response for 1 hour
        cache_service.set(cache_key, response, 3600)
        
        return response
    except Exception as e:
        logger.error(f"LLM error: {e}")
        return "AI service temporarily unavailable. Please try again later."


def get_ai_fallback_prediction(image_path, crop, language="English"):
    """
    Use AI (Groq) to analyze the image when local model confidence is low.
    Returns a disease prediction from the available classes.
    """
    if client is None:
        logger.warning("AI fallback unavailable - no Groq client")
        return None, None, "AI service not available for fallback analysis"
    
    try:
        # Read image and convert to base64 for analysis
        import base64
        from io import BytesIO
        
        with Image.open(image_path) as img:
            # Convert to RGB if necessary
            if img.mode != 'RGB':
                img = img.convert('RGB')
            
            # Resize to reasonable size for API
            img = img.resize((512, 512))
            
            # Convert to base64
            buffer = BytesIO()
            img.save(buffer, format='JPEG')
            img_base64 = base64.b64encode(buffer.getvalue()).decode()
        
        # Create detailed prompt for disease analysis
        prompt = f"""
As an expert plant pathologist, analyze this {crop} plant image for disease symptoms.

Available disease classes you can choose from:
{chr(10).join([f"{i+1}. {name}" for i, name in enumerate(class_names)])}

Instructions:
1. Examine the image carefully for disease symptoms
2. Choose the MOST likely disease from the list above
3. If the plant appears healthy, choose the appropriate "healthy" class
4. Respond in this exact format:
DISEASE: [exact class name from the list]
CONFIDENCE: [your confidence percentage 0-100]
REASON: [brief explanation of your analysis]

Be precise and match the class name exactly from the list.
"""
        
        # Call Groq for analysis
        chat_completion = client.chat.completions.create(
            messages=[
                {
                    "role": "system", 
                    "content": "You are an expert plant pathologist. Analyze plant disease images and provide accurate diagnoses. Always respond in the specified format."
                },
                {
                    "role": "user", 
                    "content": prompt
                }
            ],
            model="llama-3.1-8b-instant",
            max_tokens=500
        )
        
        response = chat_completion.choices[0].message.content
        logger.info(f"AI fallback response: {response}")
        
        # Parse the response
        lines = response.strip().split('\n')
        disease_name = None
        confidence = None
        reason = None
        
        for line in lines:
            if line.startswith('DISEASE:'):
                disease_name = line.replace('DISEASE:', '').strip()
            elif line.startswith('CONFIDENCE:'):
                try:
                    confidence_str = line.replace('CONFIDENCE:', '').strip().replace('%', '')
                    confidence = float(confidence_str) / 100.0
                except:
                    confidence = 0.5  # Default if parsing fails
            elif line.startswith('REASON:'):
                reason = line.replace('REASON:', '').strip()
        
        # Validate disease name
        if disease_name and disease_name in class_names:
            # Create prediction array with AI's choice
            ai_prediction = np.zeros(len(class_names))
            disease_idx = class_names.index(disease_name)
            ai_prediction[disease_idx] = confidence if confidence else 0.7
            
            # Distribute remaining confidence
            remaining = 1.0 - ai_prediction[disease_idx]
            for i in range(len(class_names)):
                if i != disease_idx:
                    ai_prediction[i] = remaining / (len(class_names) - 1)
            
            logger.info(f"AI fallback successful: {disease_name} with confidence {confidence}")
            return ai_prediction, disease_idx, reason
        else:
            logger.warning(f"AI fallback returned invalid disease: {disease_name}")
            return None, None, "AI analysis could not determine a valid disease"
            
    except Exception as e:
        logger.error(f"AI fallback error: {e}")
        return None, None, f"AI analysis failed: {str(e)}"



LANGUAGE_CODES = {
    "English": "en",
    "Hindi": "hi",
    "Telugu": "te",
    "Tamil": "ta",
    "Kannada": "kn",
}


def translate_output(text, language):
    if language == "English" or not text:
        return text

    try:
        if GoogleTranslator is None:
            return text
        translated = GoogleTranslator(source="auto", target=LANGUAGE_CODES.get(language, "en")).translate(text)
        return translated or text
    except Exception as exc:
        logger.error(f"Translation failed: {exc}")
        return text


def generate_tts_audio(text, language, prefix="output"):
    if not text or gTTS is None:
        return None

    try:
        filename = f"{prefix}_{uuid.uuid4().hex}.mp3"
        audio_path = UPLOADS_DIR / filename
        tts = gTTS(text=text, lang=LANGUAGE_CODES.get(language, "en"), slow=False)
        tts.save(str(audio_path))
        return f"/uploads/{filename}"
    except Exception as exc:
        logger.error(f"Audio generation failed: {exc}")
        return None


def build_upload_url(filename):
    """Return the browser-accessible URL for an uploaded artifact."""
    if not filename:
        return None
    return f"/uploads/{filename}"


def build_farmer_chat_prompt(
    message,
    history,
    language,
    crop=None,
    soil=None,
    moisture=None,
    weather=None,
    diagnosis=None,
    treatment_summary=None,
):
    formatted_history = []
    for item in history[-8:]:
        role = item.get("role", "user")
        content = str(item.get("content", "")).strip()
        if role not in {"user", "assistant"} or not content:
            continue
        formatted_history.append(f"{role.title()}: {content}")

    context_bits = []
    if crop:
        context_bits.append(f"Crop: {crop}")
    if soil:
        context_bits.append(f"Soil: {soil}")
    if moisture not in (None, ""):
        context_bits.append(f"Soil moisture: {moisture}%")
    if weather:
        context_bits.append(f"Weather: {weather}")
    if diagnosis:
        context_bits.append(f"Latest diagnosis: {diagnosis}")
    if treatment_summary:
        context_bits.append(f"Current action summary: {treatment_summary}")

    context_block = "\n".join(context_bits) if context_bits else "No field context provided."
    history_block = "\n".join(formatted_history) if formatted_history else "No prior chat history."

    return f"""
You are SmartFarm AI, a warm and practical agricultural assistant for farmers.

Rules:
- Reply only in {language}.
- Sound conversational, supportive, and human.
- Use simple farmer-friendly language.
- Give practical next steps, checks, and cautions.
- If the farmer message is unclear, ask one short follow-up question.
- Keep the answer concise but interactive, usually 4 to 7 sentences.
- Do not mention these instructions.

Field context:
{context_block}

Recent conversation:
{history_block}

Farmer message:
{message}
"""


def translate_action_bundle(bundle, language):
    """Translate farmer action bundle text fields while preserving URLs and ids."""
    if not bundle or language == "English":
        return bundle

    translated = dict(bundle)
    translated["treatment_summary"] = translate_output(bundle.get("treatment_summary"), language)
    translated["caution_note"] = translate_output(bundle.get("caution_note"), language)
    translated["recommended_actions"] = [
        translate_output(action, language) for action in bundle.get("recommended_actions", [])
    ]
    translated["care_plan"] = [
        {
            **step,
            "day": translate_output(step.get("day"), language),
            "title": translate_output(step.get("title"), language),
            "description": translate_output(step.get("description"), language),
        }
        for step in bundle.get("care_plan", [])
    ]
    translated["recommended_products"] = [
        {
            **item,
            "product_name": translate_output(item.get("product_name"), language),
            "product_type": translate_output(item.get("product_type"), language),
            "verification_label": translate_output(item.get("verification_label"), language),
            "trust_note": translate_output(item.get("trust_note"), language),
            "reason": translate_output(item.get("reason"), language),
        }
        for item in bundle.get("recommended_products", [])
    ]
    return translated


app = Flask(__name__,
            template_folder=str(FRONTEND_DIR / 'templates'),
            static_folder=str(FRONTEND_PUBLIC_DIR))
app.config.from_object(get_runtime_config())
app.config['UPLOAD_FOLDER'] = str(UPLOADS_DIR)
app.config['UPLOAD_EXTENSIONS'] = app.config.get('UPLOAD_EXTENSIONS', ['.jpg', '.jpeg', '.png', '.webp'])

if app.config.get("ENABLE_PROXY_FIX", True):
    app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1)

CORS(app, resources={r"/*": {"origins": app.config.get("CORS_ORIGINS", "*")}})

# Global variables to store latest moisture value from ESP32
latest_moisture = 40  # default moisture value from ESP32
last_moisture_update = time.time()  # timestamp of last update
consecutive_failures = 0  # track connection issues


def cleanup_old_uploads(max_age_seconds=3600):
    """Remove stale upload artifacts so disk usage stays bounded."""
    cutoff = time.time() - max_age_seconds
    for path in UPLOADS_DIR.iterdir():
        if not path.is_file():
            continue
        try:
            if path.stat().st_mtime < cutoff:
                path.unlink()
        except OSError as exc:
            logger.warning(f"Failed to cleanup upload artifact {path.name}: {exc}")


@app.before_request
def attach_request_context():
    """Attach request-scoped metadata for logging and tracing."""
    g.request_id = request.headers.get("X-Request-ID", uuid.uuid4().hex)
    g.request_started_at = time.time()

    if request.method == "POST" and request.path == "/":
        cleanup_old_uploads()


@app.after_request
def add_response_headers(response):
    """Add production-friendly headers and request tracing metadata."""
    duration_ms = int((time.time() - getattr(g, "request_started_at", time.time())) * 1000)
    response.headers["X-Request-ID"] = getattr(g, "request_id", "-")
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "SAMEORIGIN"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["X-Response-Time-ms"] = str(max(duration_ms, 0))

    if request.path.startswith("/uploads/"):
        response.headers["Cache-Control"] = "public, max-age=300"
    else:
        response.headers["Cache-Control"] = "no-store"

    logger.info(f"Completed request with status={response.status_code} duration_ms={duration_ms}")
    return response

# --- File serving route for uploads ---
from flask import send_from_directory

@app.route('/uploads/<path:filename>')
def serve_upload(filename):
    """Serve uploaded files from the uploads folder"""
    return send_from_directory(str(UPLOADS_DIR), filename)

# --- Moisture update and retrieval routes ---
@app.route('/update_moisture', methods=['POST'])
def update_moisture():
    global latest_moisture, last_moisture_update, consecutive_failures
    try:
        data = request.get_json()

        if not data or "moisture" not in data:
            logger.warning("Invalid moisture data received")
            return jsonify({"error": "invalid data"}), 400

        # Enhanced validation
        try:
            value = int(data.get('moisture'))
        except (ValueError, TypeError):
            logger.error("Moisture value is not a number")
            return jsonify({"error": "invalid moisture value"}), 400

        # Device ID tracking (for multiple ESP32s)
        device_id = data.get('device_id', 'default')
        
        # Detect value format: 
        # - If 0-100, treat as percentage (ESP32 pre-converted)
        # - If 101-4095, treat as raw ADC and convert to percentage
        if 0 <= value <= 100:
            # Already percentage (ESP32 Arduino code converts with map())
            latest_moisture = value
            logger.info(f"Received pre-converted percentage from {device_id}: {value}%")
        elif 101 <= value <= 4095:
            # Raw ADC value, convert to percentage
            latest_moisture = int((value / 4095) * 100)
            logger.info(f"Converted raw ADC {value} to {latest_moisture}% from {device_id}")
        else:
            logger.warning(f"Invalid moisture value from {device_id}: {value}")
            return jsonify({"error": "invalid range"}), 400
        last_moisture_update = time.time()
        consecutive_failures = 0  # Reset failure counter on success

        logger.info(f"Moisture updated from {device_id}: {latest_moisture}%")

        return jsonify({
            "status": "success", 
            "timestamp": last_moisture_update,
            "device_id": device_id
        }), 200

    except Exception as e:
        consecutive_failures += 1
        logger.error(f"Moisture update error (attempt {consecutive_failures}): {e}")
        return jsonify({"status": "error", "error": str(e)}), 400

@app.route('/get_moisture', methods=['GET'])
def get_moisture():
    global latest_moisture, last_moisture_update, consecutive_failures
    
    # Check if data is stale (older than 5 minutes)
    stale_threshold = 300  # 5 minutes in seconds
    is_stale = (time.time() - last_moisture_update) > stale_threshold
    
    if is_stale:
        logger.warning(f"Moisture data is stale ({int(time.time() - last_moisture_update)}s old)")
    
    return jsonify({
        "moisture": latest_moisture,
        "status": "stale" if is_stale else "fresh",
        "last_update": last_moisture_update,
        "consecutive_failures": consecutive_failures,
        "time_since_update": int(time.time() - last_moisture_update)
    })

@app.route('/iot_status', methods=['GET'])
def iot_status():
    """IoT device monitoring endpoint"""
    global last_moisture_update, consecutive_failures
    
    current_time = time.time()
    time_since_update = current_time - last_moisture_update
    
    # Determine device status
    if time_since_update < 60:  # Last update within 1 minute
        device_status = "online"
    elif time_since_update < 300:  # Last update within 5 minutes
        device_status = "intermittent"
    else:
        device_status = "offline"
    
    return jsonify({
        "device_status": device_status,
        "last_update": last_moisture_update,
        "time_since_update_seconds": int(time_since_update),
        "consecutive_failures": consecutive_failures,
        "current_moisture": latest_moisture,
        "uptime_percentage": max(0, min(100, 100 - (consecutive_failures * 10)))  # Simple health metric
    })

# Translations for multi-language support
translations = {
    "English": {
        "title": "Smart Farming Assistant",
        "upload": "Upload Leaf Image",
        "crop": "Select Crop",
        "soil": "Soil Type",
        "moisture": "Soil Moisture Level",
        "weather": "Current Weather",
        "question": "Ask AI about your crop (optional)",
        "button": "🔍 Analyze My Crop",
        "disease_desc": "Disease Description",
        "ai_guidance": "AI Disease Guidance",
        "ai_answer": "AI Answer to Your Question",
        "treatment": "Recommended Treatment",
        "soil_card": "Soil Compatibility",
        "irrigation": "Irrigation Advice",
        "weather_card": "Weather Analysis",
        "alternatives": "Alternative Possibilities"
        ,"crop_tomato": "Tomato",
        "crop_potato": "Potato",
        "crop_pepper": "Pepper",
        "soil_clay": "Clay",
        "soil_loam": "Loam",
        "soil_sandy": "Sandy",
        "soil_silt": "Silt",
        "weather_dry": "Dry",
        "weather_humid": "Humid",
        "weather_rainy": "Rainy",
        "weather_hot": "Hot",
        "language": "Language",
        "loading_ai": "Generating AI advice...",
        "waiting_question": "Waiting for your question...",
        "ai_response": "AI Assistant Response",
        "listening": "🎤 Listening...",
        "speak": "🎤 Speak",
        "disease_advice": "AI Disease Guidance",
        "question_label": "Your Question",
        "ai_answer_label": "AI Answer",
        "no_question": "No question asked"

    },
    "Hindi": {
        "title": "स्मार्ट खेती सहायक",
        "upload": "पत्ती की तस्वीर अपलोड करें",
        "crop": "फसल चुनें",
        "soil": "मिट्टी का प्रकार",
        "moisture": "मिट्टी की नमी",
        "weather": "मौसम",
        "question": "अपने फसल के बारे में पूछें",
        "button": "🔍 विश्लेषण करें",
        "disease_desc": "रोग विवरण",
        "ai_guidance": "AI रोग मार्गदर्शन",
        "ai_answer": "आपके प्रश्न का उत्तर",
        "treatment": "उपचार सुझाव",
        "soil_card": "मिट्टी अनुकूलता",
        "irrigation": "सिंचाई सलाह",
        "weather_card": "मौसम विश्लेषण",
        "alternatives": "वैकल्पिक संभावनाएँ"
        ,"crop_tomato": "टमाटर",
        "crop_potato": "आलू",
        "crop_pepper": "मिर्च",
        "soil_clay": "चिकनी मिट्टी",
        "soil_loam": "दोमट",
        "soil_sandy": "रेतीली",
        "soil_silt": "गाद",
        "weather_dry": "सूखा",
        "weather_humid": "नमी",
        "weather_rainy": "बरसात",
        "weather_hot": "गर्म",
        "language": "भाषा",
        "loading_ai": "AI सलाह तैयार हो रही है...",
        "waiting_question": "आपके प्रश्न का इंतजार है...",
        "ai_response": "AI सहायक उत्तर",
        "listening": "🎤 सुन रहा है...",
        "speak": "🎤 बोलें",
        "disease_advice": "AI रोग मार्गदर्शन",
        "question_label": "आपका प्रश्न",
        "ai_answer_label": "AI उत्तर",
        "no_question": "कोई प्रश्न नहीं पूछा गया"

    },
    "Telugu": {
        "title": "స్మార్ట్ వ్యవసాయ సహాయకుడు",
        "upload": "ఆకు చిత్రం అప్లోడ్ చేయండి",
        "crop": "పంటను ఎంచుకోండి",
        "soil": "మట్టి రకం",
        "moisture": "మట్టి తేమ",
        "weather": "వాతావరణం",
        "question": "మీ పంట గురించి అడగండి",
        "button": "🔍 విశ్లేషించండి",
        "disease_desc": "రోగ వివరణ",
        "ai_guidance": "AI వ్యాధి సూచనలు",
        "ai_answer": "మీ ప్రశ్నకు సమాధానం",
        "treatment": "చికిత్స సూచనలు",
        "soil_card": "మట్టి అనుకూలత",
        "irrigation": "పారుదల సూచనలు",
        "weather_card": "వాతావరణ విశ్లేషణ",
        "alternatives": "ప్రత్యామ్నాయ అవకాశాలు"
        ,"crop_tomato": "టమోటా",
        "crop_potato": "బంగాళాదుంప",
        "crop_pepper": "మిర్చి",
        "soil_clay": "మట్టి",
        "soil_loam": "లోమ్",
        "soil_sandy": "ఇసుక",
        "soil_silt": "సిల్ట్",
        "weather_dry": "ఎండ",
        "weather_humid": "తేమ",
        "weather_rainy": "వర్షం",
        "weather_hot": "వేడి",
        "language": "భాష",
        "loading_ai": "AI సలహా తయారవుతోంది...",
        "waiting_question": "మీ ప్రశ్న కోసం వేచి ఉంది...",
        "ai_response": "AI సమాధానం",
        "listening": "🎤 వింటోంది...",
        "speak": "🎤 మాట్లాడండి",
        "disease_advice": "AI వ్యాధి సూచనలు",
        "question_label": "మీ ప్రశ్న",
        "ai_answer_label": "AI సమాధానం",
        "no_question": "ప్రశ్న అడగలేదు"

    },
    "Tamil": {
        "title": "ஸ்மார்ட் பண்ணை உதவியாளர்",
        "upload": "இலை படத்தை பதிவேற்றவும்",
        "crop": "பயிரை தேர்ந்தெடுக்கவும்",
        "soil": "மண் வகை",
        "moisture": "மண் ஈரப்பதம்",
        "weather": "வானிலை",
        "question": "உங்கள் பயிரைப் பற்றி கேளுங்கள்",
        "button": "🔍 பகுப்பாய்வு செய்யுங்கள்",
        "disease_desc": "நோய் விளக்கம்",
        "ai_guidance": "AI நோய் வழிகாட்டல்",
        "ai_answer": "உங்கள் கேள்விக்கு பதில்",
        "treatment": "சிகிச்சை பரிந்துரைகள்",
        "soil_card": "மண் இணக்கம்",
        "irrigation": "நீர்ப்பாசன ஆலோசனைகள்",
        "weather_card": "வானிலை பகுப்பாய்வு",
        "alternatives": "மாற்று சாத்தியங்கள்",
        "crop_tomato": "தக்காளி",
        "crop_potato": "உருளைக்கிழங்கு",
        "crop_pepper": "மிளகாய்",
        "soil_clay": "களிமண்",
        "soil_loam": "லோம்",
        "soil_sandy": "மணல்",
        "soil_silt": "அலை",
        "weather_dry": "வறண்ட",
        "weather_humid": "ஈரப்பதமான",
        "weather_rainy": "மழை",
        "weather_hot": "சூடான",
        "language": "மொழி",
        "loading_ai": "AI ஆலோசனை தயாராகிறது...",
        "waiting_question": "உங்கள் கேள்விக்காக காத்திருக்கிறது...",
        "ai_response": "AI உதவியாளர் பதில்",
        "listening": "🎤 கேட்கிறது...",
        "speak": "🎤 பேசுங்கள்",
        "disease_advice": "AI நோய் வழிகாட்டல்",
        "question_label": "உங்கள் கேள்வி",
        "ai_answer_label": "AI பதில்",
        "no_question": "கேள்வி கேட்கப்படவில்லை"

    },
    "Kannada": {
        "title": "ಸ್ಮಾರ್ಟ್ ಕೃಷಿ ಸಹಾಯಕ",
        "upload": "ಎಲೆ ಚಿತ್ರವನ್ನು ಅಪ್‌ಲೋಡ್ ಮಾಡಿ",
        "crop": "ಬೆಳೆಯನ್ನು ಆರಿಸಿ",
        "soil": "ಮಣ್ಣಿನ ಪ್ರಕಾರ",
        "moisture": "ಮಣ್ಣಿನ ತೇವಾಂಶ",
        "weather": "ಹವಾಮಾನ",
        "question": "ನಿಮ್ಮ ಬೆಳೆಯ ಬಗ್ಗೆ ಕೇಳಿ",
        "button": "🔍 ವಿಶ್ಲೇಷಿಸಿ",
        "disease_desc": "ರೋಗ ವಿವರಣೆ",
        "ai_guidance": "AI ರೋಗ ಮಾರ್ಗದರ್ಶನ",
        "ai_answer": "ನಿಮ್ಮ ಪ್ರಶ್ನೆಗೆ ಉತ್ತರ",
        "treatment": "ಚಿಕಿತ್ಸಾ ಸಲಹೆಗಳು",
        "soil_card": "ಮಣ್ಣಿನ ಹೊಂದಾಣಿಕೆ",
        "irrigation": "ನೀರಾವರಿ ಸಲಹೆಗಳು",
        "weather_card": "ಹವಾಮಾನ ವಿಶ್ಲೇಷಣೆ",
        "alternatives": "ಪರ್ಯಾಯ ಸಾಧ್ಯತೆಗಳು",
        "crop_tomato": "ಟೊಮೇಟೊ",
        "crop_potato": "ಆಲೂಗಡ್ಡೆ",
        "crop_pepper": "ಮೆಣಸಿನಕಾಯಿ",
        "soil_clay": "ಜೇಡಿಮಣ್ಣಿ",
        "soil_loam": "ಲೋಮ್",
        "soil_sandy": "ಮರಳು",
        "soil_silt": "ಸಿಲ್ಟ್",
        "weather_dry": "ಒಣ",
        "weather_humid": "ತೇವಾಂಶದ",
        "weather_rainy": "ಮಳೆಯ",
        "weather_hot": "ಬಿಸಿಯ",
        "language": "ಭಾಷೆ",
        "loading_ai": "AI ಸಲಹೆ ಸಿದ್ಧವಾಗುತ್ತಿದೆ...",
        "waiting_question": "ನಿಮ್ಮ ಪ್ರಶ್ನೆಗಾಗಿ ಕಾಯುತ್ತಿದೆ...",
        "ai_response": "AI ಸಹಾಯಕ ಉತ್ತರ",
        "listening": "🎤 ಕೇಳುತ್ತಿದೆ...",
        "speak": "🎤 ಮಾತನಾಡಿ",
        "disease_advice": "AI ರೋಗ ಮಾರ್ಗದರ್ಶನ",
        "question_label": "ನಿಮ್ಮ ಪ್ರಶ್ನೆ",
        "ai_answer_label": "AI ಉತ್ತರ",
        "no_question": "ಪ್ರಶ್ನೆ ಕೇಳಲಾಗಿಲ್ಲ"

    }
}

def download_model_from_github():
    """
    Download ML model from GitHub Releases
    """
    logger.info("Downloading model from GitHub Releases")
    import requests
    model_url = "https://github.com/Nischal6932/No_Ollama/releases/download/v1.0/plant_disease_realworld_15class_best_v4.keras"
    model_path = str(MODEL_DIR / "plant_disease_realworld_15class_best_v4.keras")
    
    try:
        logger.info(f"Downloading model from GitHub Releases...")
        response = requests.get(model_url, stream=True, timeout=30)
        response.raise_for_status()
        
        # Save model with progress indication
        total_size = int(response.headers.get('content-length', 0))
        downloaded = 0
        
        with open(model_path, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192):
                if chunk:
                    f.write(chunk)
                    downloaded += len(chunk)
        
        logger.info(f"Model downloaded successfully: {model_path}")
        return model_path
        
    except requests.exceptions.RequestException as e:
        logger.error(f"Failed to download model: {e}")
        return None
    except Exception as e:
        logger.error(f"Unexpected download error: {e}")
        return None

def get_simple_fallback_prediction(img_array):
    """
    Fallback prediction using simple image analysis when model is not available
    """
    try:
        import numpy as np
        
        # Simple image analysis based on color distribution
        # This is a very basic fallback - in production you'd want a better solution
        
        # Calculate average color values
        avg_red = np.mean(img_array[:, :, 0])
        avg_green = np.mean(img_array[:, :, 1])
        avg_blue = np.mean(img_array[:, :, 2])
        
        # Calculate green ratio (indicator of plant health)
        total = avg_red + avg_green + avg_blue
        green_ratio = avg_green / total if total > 0 else 0
        
        # Simple heuristic based on color analysis
        if green_ratio > 0.4:
            # High green content - likely healthy
            return "healthy", 0.75
        elif green_ratio > 0.3:
            # Moderate green content - some issues
            return "moderate_risk", 0.60
        else:
            # Low green content - potential disease
            return "disease_risk", 0.55
            
    except Exception as e:
        logger.error(f"Fallback prediction error: {e}")
        return "unknown", 0.50

def validate_upload_file(file):
    """Validate uploaded file for security and compatibility."""
    return FileValidator.validate_file(
        file,
        allowed_extensions=app.config['UPLOAD_EXTENSIONS'],
        max_size=app.config['MAX_CONTENT_LENGTH'],
    )

# Simple allowed_file helper for clarity
def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ['jpg','jpeg','png','webp']


@app.errorhandler(413)
def too_large(e):
    """Handle file too large error"""
    language = "English"
    t = translations.get(language, translations["English"])
    return render_template(
        "index.html",
        t=t,
        language=language,
        result=None,
        confidence=None,
        description=f"File too large. Maximum size is {app.config['MAX_CONTENT_LENGTH'] // (1024*1024)}MB. Please upload a smaller image.",
        treatment=None,
        soil_advice=None,
        irrigation_advice=None,
        weather_analysis=None,
        top2_predictions=None,
        ai_advice=None,
        chat_response=None
    ), 413

@app.route('/health', methods=['GET'])
@handle_errors
def health_check():
    """Enhanced health check with cache status"""
    health_status = {
        'status': 'ok',
        'message': 'Smart Farming AI is running',
        'cache_status': 'connected' if cache_service.use_redis else 'memory_cache',
        'model_loaded': model is not None,
        'ai_service': 'connected' if client else 'disabled',
        'timestamp': time.time()
    }
    
    # Test cache connectivity
    try:
        cache_service.set('health_check', 'ok', 10)
        cache_test = cache_service.get('health_check')
        health_status['cache_test'] = 'passed' if cache_test == 'ok' else 'failed'
    except Exception as e:
        health_status['cache_test'] = 'failed'
        logger.error(f"Cache health check failed: {e}")
    
    return jsonify(health_status), 200


@app.route('/livez', methods=['GET'])
def livez():
    """Lightweight liveness probe."""
    return jsonify({"status": "alive"}), 200


@app.route('/readyz', methods=['GET'])
def readyz():
    """Readiness probe for orchestrators."""
    ready = True
    details = {
        "cache": "ok" if cache_service else "unavailable",
        "ai_service": "configured" if client else "disabled",
        "model_preloaded": model is not None,
    }

    if not UPLOADS_DIR.exists():
        ready = False
        details["uploads"] = "missing"
    else:
        details["uploads"] = "ok"

    status_code = 200 if ready else 503
    return jsonify({"status": "ready" if ready else "not_ready", "details": details}), status_code

@app.route('/test', methods=['GET'])
def test():
    return {"status": "ok", "message": "Test endpoint working", "model_loaded": model is not None}, 200

if app.debug:
    @app.route('/debug', methods=['GET'])
    def debug_info():
        """Debug endpoint to check system status"""
        import os
        import sys
        model_path = get_model_path()
        
        debug_info = {
            'python_version': sys.version,
            'working_directory': os.getcwd(),
            'files_in_dir': os.listdir('.'),
            'model_files': [f for f in os.listdir('.') if f.endswith(('.keras', '.h5'))],
            'active_model_path': model_path,
            'model_file_exists': os.path.exists(model_path),
            'model_file_size': None,
            'memory_info': None,
            'tensorflow_version': None,
            'numpy_version': None,
            'pillow_version': None
        }
        
        try:
            import tensorflow as tf
            debug_info['tensorflow_version'] = tf.__version__
        except:
            debug_info['tensorflow_version'] = 'Not available'
        
        try:
            import numpy as np
            debug_info['numpy_version'] = np.__version__
        except:
            debug_info['numpy_version'] = 'Not available'
        
        try:
            from PIL import Image
            debug_info['pillow_version'] = Image.__version__
        except:
            debug_info['pillow_version'] = 'Not available'
        
        try:
            import psutil
            memory = psutil.virtual_memory()
            debug_info['memory_info'] = {
                'total_gb': round(memory.total / (1024**3), 2),
                'available_gb': round(memory.available / (1024**3), 2),
                'percent_used': memory.percent
            }
        except:
            debug_info['memory_info'] = 'psutil not available'
        
        if debug_info['model_file_exists']:
            try:
                size = os.path.getsize(model_path) / (1024 * 1024)
                debug_info['model_file_size'] = f"{size:.1f} MB"
            except:
                debug_info['model_file_size'] = 'Could not determine size'
        
        return jsonify(debug_info)

@app.route("/ai_advice", methods=["POST"])
@handle_errors
@log_api_request
def ai_advice_endpoint():
    is_allowed, rate_limit_message = validate_ai_advice_request()
    if not is_allowed:
        raise ValidationError(rate_limit_message, error_code="RATE_LIMIT_EXCEEDED", user_message=rate_limit_message)

    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        raise ValidationError(
            "Invalid JSON payload",
            error_code="INVALID_JSON",
            user_message="Please send a valid JSON request."
        )

    crop = data.get("crop")
    disease = data.get("disease")
    diagnosis_key = data.get("diagnosis_key") or disease
    soil = data.get("soil")
    moisture = data.get("moisture")
    weather = data.get("weather")
    question = data.get("question")
    language = data.get("language", "English")  # FIX: Extract language from request
    if not crop or not disease or not soil or weather is None:
        raise ValidationError(
            "Missing required AI advice fields",
            error_code="MISSING_FIELDS",
            user_message="Crop, disease, soil, and weather are required."
        )

    if language not in translations:
        language = "English"

    action_bundle = translate_action_bundle(
        build_farmer_action_bundle(
            crop=crop,
            disease_key=diagnosis_key,
            confidence=None,
            soil=soil,
            moisture=moisture,
            weather=weather,
            uncertain=diagnosis_key in {None, "", "uncertain"},
        ),
        language,
    )

    # Rule-based moisture intelligence
    try:
        moisture_val = int(moisture) if moisture is not None else 40
    except Exception:
        moisture_val = 40

    if moisture_val < 30:
        rule_advice = "CRITICAL: Soil is very dry. Immediate irrigation needed."
    elif moisture_val < 60:
        rule_advice = "MODERATE: Soil condition is acceptable. Monitor moisture levels."
    else:
        rule_advice = "GOOD: Soil has enough water. Avoid irrigation to prevent waterlogging."

    # Always generate disease guidance (separate from question)
    prompt = f"""
You are an expert agricultural assistant.

Crop: {crop}
Disease: {disease}
Soil Type: {soil}
Soil Moisture: {moisture}%
Weather: {weather}

Give:
1. Whether irrigation is needed (YES/NO)
2. Reason based on moisture + soil + weather
3. Exact action farmer should take

Keep it simple and practical for farmers.
"""

    # Generate separate answer for farmer question
    question_answer = None

    if question and question.strip() != "":
        question_prompt = f"""
You are an expert agricultural advisor.

CRITICAL: Respond ONLY in {language}. Do NOT respond in English if {language} is selected.
Keep answer short and practical in {language}.

Question: {question}

Answer in {language} only. Use simple farmer-friendly language.
"""
        question_answer = ask_llm(question_prompt)

    if app.config.get("TESTING"):
        return jsonify({
            "advice": f"{rule_advice}\n\nAI Advice:\nTest mode response.",
            "question_answer": question_answer or "Test mode answer.",
            "disease_audio": None,
            "question_audio": None,
            "treatment_summary": action_bundle.get("treatment_summary"),
            "recommended_actions": action_bundle.get("recommended_actions"),
            "recommended_products": action_bundle.get("recommended_products"),
            "care_plan": action_bundle.get("care_plan"),
            "expert_support_recommended": action_bundle.get("expert_support_recommended"),
        })

    try:
        logger.info(f"Selected language: {language}")
        response = ask_llm(prompt).strip()

        # Force translation using Google Translator (reliable)
        response = translate_output(response, language)

        # Combine rule-based + AI advice
        final_advice = f"{rule_advice}\n\nAI Advice:\n{response}"

        # Generate voice output for disease advice
        disease_audio_url = None
        question_audio_url = None
        
        try:
            # Clean up previous audio files before creating new ones
            import glob
            for f in glob.glob(str(UPLOADS_DIR / "output_*.mp3")):
                try:
                    os.remove(f)
                except:
                    pass

            disease_audio_url = generate_tts_audio(final_advice, language, prefix="output")

        except Exception as e:
            logger.error(f"Disease audio generation failed: {e}")
            disease_audio_url = None

        # Generate separate voice output for question answer
        if question_answer and question_answer.strip() != "":
            try:
                question_audio_url = generate_tts_audio(question_answer, language, prefix="output")
            except Exception as e:
                logger.error(f"Question audio generation failed: {e}")
                question_audio_url = None

        return jsonify({
            "advice": final_advice,
            "question_answer": question_answer,
            "disease_audio": disease_audio_url,
            "question_audio": question_audio_url,
            "treatment_summary": action_bundle.get("treatment_summary"),
            "recommended_actions": action_bundle.get("recommended_actions"),
            "recommended_products": action_bundle.get("recommended_products"),
            "care_plan": action_bundle.get("care_plan"),
            "expert_support_recommended": action_bundle.get("expert_support_recommended"),
        })
    except Exception as e:
        logger.error(f"AI ERROR: {e}")
        return jsonify({
            "advice": str(e),
            "audio": None
        })


@app.route("/chat", methods=["POST"])
@handle_errors
@log_api_request
def farmer_chat_endpoint():
    is_allowed, rate_limit_message = validate_ai_advice_request()
    if not is_allowed:
        raise ValidationError(rate_limit_message, error_code="RATE_LIMIT_EXCEEDED", user_message=rate_limit_message)

    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        raise ValidationError(
            "Invalid JSON payload",
            error_code="INVALID_JSON",
            user_message="Please send a valid JSON request."
        )

    message = str(data.get("message", "")).strip()
    history = data.get("history", [])
    language = data.get("language", "English")

    if not message:
        raise ValidationError(
            "Missing chat message",
            error_code="MISSING_MESSAGE",
            user_message="Please enter or speak a farming question."
        )

    if language not in translations:
        language = "English"

    if not isinstance(history, list):
        history = []

    prompt = build_farmer_chat_prompt(
        message=message,
        history=history,
        language=language,
        crop=data.get("crop"),
        soil=data.get("soil"),
        moisture=data.get("moisture"),
        weather=data.get("weather"),
        diagnosis=data.get("diagnosis"),
        treatment_summary=data.get("treatment_summary"),
    )

    if app.config.get("TESTING"):
        return jsonify({
            "reply": f"Test chat reply for: {message}",
            "audio": None,
        })

    reply = ask_llm(prompt).strip()
    reply = translate_output(reply, language)
    audio_url = generate_tts_audio(reply, language, prefix="chat")

    return jsonify({
        "reply": reply,
        "audio": audio_url,
    })


@app.route("/marketplace", methods=["GET"])
@handle_errors
@log_api_request
def marketplace_endpoint():
    crop = request.args.get("crop")
    disease_key = request.args.get("disease")
    items = filter_marketplace_catalog(crop=crop, disease_key=disease_key, limit=None)
    return jsonify({
        "items": items,
        "count": len(items),
        "crop": crop,
        "disease": disease_key,
    })


@app.route("/expert_support", methods=["POST"])
@handle_errors
@log_api_request
def expert_support_endpoint():
    payload = request.get_json(silent=True)
    if not isinstance(payload, dict):
        payload = request.form.to_dict()

    is_valid, error_message, normalized = validate_expert_support_payload(payload or {})
    if not is_valid:
        raise ValidationError(
            error_message,
            error_code="INVALID_SUPPORT_REQUEST",
            user_message=error_message,
        )

    record = store_expert_support_request(normalized)
    return jsonify({
        "success": True,
        "message": "Your request has been recorded. An expert should review it soon and contact you using the provided phone number.",
        "request_id": record["id"],
        "submitted_at": record["submitted_at"],
    })

@app.route('/', methods=['GET', 'POST'])
def predict():
    logger.info(f"Request method: {request.method}")
    
    result = None
    diagnosis_key = None
    confidence = None
    description = None
    treatment = None
    treatment_summary = None
    recommended_actions = []
    recommended_products = []
    care_plan = []
    expert_support_recommended = False
    soil_advice = None
    irrigation_advice = None
    weather_analysis = None
    top2_predictions = None
    ai_advice = None
    chat_response = None
    original_image_reference = None
    language = request.form.get("language") or request.args.get("language") or "English"
    t = translations.get(language, translations["English"])

    if request.method == "POST":
        logger.info("Processing POST request")

        is_allowed, rate_limit_message = validate_upload_request()
        if not is_allowed:
            logger.warning(rate_limit_message)
            return render_template(
                "index.html",
                t=t,
                language=language,
                result=None,
                confidence=None,
                description=rate_limit_message,
                treatment=None,
                soil_advice=None,
                irrigation_advice=None,
                weather_analysis=None,
                top2_predictions=None,
                ai_advice=None,
                chat_response=None,
                user_question=request.form.get("question", ""),
                moisture=latest_moisture,
            ), 429
        
        file = request.files.get('image')
        logger.info(f"File received: {file.filename if file else 'None'}")
        if app.config.get("DEBUG") or app.config.get("TESTING"):
            logger.info(f"Request form keys: {list(request.form.keys())}")

        # Validate uploaded file
        if file is None or file.filename == "":
            logger.warning("No file uploaded")
            return render_template(
                "index.html",
                t=t,
                language=language,
                result=None,
                confidence=None,
                description="Please upload a plant leaf image.",
                treatment=None,
                soil_advice=None,
                irrigation_advice=None,
                weather_analysis=None,
                top2_predictions=None,
                ai_advice=None,
                chat_response=None
            )
        
        # Validate file before processing
        is_valid, validation_message = validate_upload_file(file)
        if not is_valid:
            logger.warning(f"File validation failed: {validation_message}")
            return render_template(
                "index.html",
                t=t,
                language=language,
                result=None,
                confidence=None,
                description=f"Invalid file: {validation_message}",
                treatment=None,
                soil_advice=None,
                irrigation_advice=None,
                weather_analysis=None,
                top2_predictions=None,
                ai_advice=None,
                chat_response=None
            )

        # Save file to static directory with unique name
        import uuid
        original_name = file.filename or "upload.jpg"
        safe_name = FileValidator.sanitize_filename(original_name)
        extension = Path(safe_name).suffix.lower() or ".jpg"
        filename = f"{uuid.uuid4().hex}{extension}"
        original_image_reference = filename
        image_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(image_path)

        # Safety check
        if not os.path.exists(image_path):
            logger.error("Image not saved properly")
            return render_template(
                "index.html",
                t=t,
                language=language,
                result=None,
                confidence=None,
                description="Error saving uploaded image. Please try again.",
                treatment=None,
                soil_advice=None,
                irrigation_advice=None,
                weather_analysis=None,
                top2_predictions=None,
                ai_advice=None,
                chat_response=None
            )

        crop = request.form.get("crop")

        # Safety fallback if crop not selected
        if not crop:
            crop = "Unknown"

        soil = request.form.get("soil")
        moisture = request.form.get("moisture") or str(latest_moisture)
        weather = request.form.get("weather")
        user_question = request.form.get("question")

        # --- Environment Analysis (rule-based) ---

        # Soil compatibility check
        if crop == "Rice" and soil == "Clay":
            soil_advice = "Good soil choice. Clay soil retains water well and is suitable for rice cultivation."
        elif crop == "Tomato" and soil == "Loam":
            soil_advice = "Loamy soil is ideal for tomato plants due to good drainage and nutrient balance."
        elif crop == "Potato" and soil == "Sandy":
            soil_advice = "Sandy soil supports good potato tuber development and drainage."
        else:
            soil_advice = f"{soil} soil can grow {crop}, but monitoring nutrients and drainage is recommended."

        # Safe moisture parsing
        try:
            moisture_val = int(moisture) if moisture is not None else 40
        except Exception:
            moisture_val = 40

        # Auto-intelligence irrigation advice based on moisture
        if moisture_val < 30:
            irrigation_advice = "Soil is dry. Irrigation required immediately."
        elif moisture_val < 60:
            irrigation_advice = "Soil is moderately moist. Monitor closely."
        else:
            irrigation_advice = "Soil is wet. Do not irrigate."

        # Weather risk analysis
        if weather == "Humid":
            weather_analysis = "Humid conditions may increase fungal disease risk. Monitor leaves closely."
        elif weather == "Rainy":
            weather_analysis = "Rainy weather can spread plant pathogens quickly. Ensure good drainage."
        elif weather == "Hot":
            weather_analysis = "High temperatures may stress plants. Maintain adequate irrigation."
        else:
            weather_analysis = "Weather conditions appear stable for crop growth."

        try:
            logger.info("Processing image")
            img = resize_for_model(Image.open(image_path).convert("RGB"))
            logger.info(f"Image processed successfully, shape: {img.size}")
            
        except Exception as e:
            logger.error(f"Image processing error: {e}")
            error_msg = str(e)
            if "cannot identify image file" in error_msg.lower():
                error_msg = "Invalid or corrupted image file. Please upload a valid image."
            elif "image file is truncated" in error_msg.lower():
                error_msg = "Image file is corrupted or incomplete. Please try a different image."
            
            return render_template(
                "index.html",
                t=t,
                language=language,
                result=None,
                confidence=None,
                description=f"Image processing failed: {error_msg}",
                treatment=None,
                soil_advice=None,
                irrigation_advice=None,
                weather_analysis=None,
                top2_predictions=None,
                ai_advice=None,
                chat_response=None
            )
        img = np.array(img) / 255.0
        img = np.expand_dims(img, axis=0)
        logger.info(f"Image array shape: {img.shape}")

        if app.config.get("TESTING"):
            test_prediction = np.zeros(len(class_names), dtype=float)
            healthy_idx = class_names.index("Tomato_healthy") if "Tomato_healthy" in class_names else 0
            fallback_idx = class_names.index("Tomato_Bacterial_spot") if "Tomato_Bacterial_spot" in class_names else healthy_idx
            test_prediction[healthy_idx] = 0.8
            if fallback_idx != healthy_idx:
                test_prediction[fallback_idx] = 0.2
            preds = normalize_prediction_scores(test_prediction)
            logger.info("Using test-mode prediction path")
        else:
            try:
                logger.info("Loading local model for prediction")
                global model
                model = get_model()
                if model is None:
                    logger.error("Model is None after get_model()")
                    return render_template(
                        "index.html",
                        t=t,
                        language=language,
                        result=None,
                        confidence=None,
                        description="AI model temporarily unavailable. Please try again later.",
                        treatment=None,
                        soil_advice=soil_advice,
                        irrigation_advice=irrigation_advice,
                        weather_analysis=weather_analysis,
                        top2_predictions=None,
                        ai_advice=None,
                        chat_response=None
                    )
                
                logger.info(f"Making prediction on image")
                if crop == "Potato":
                    specialist_model = get_potato_specialist_model()
                else:
                    specialist_model = None

                if specialist_model is not None:
                    logger.info("Using potato specialist model")
                    preds = get_potato_specialist_prediction(image_path, specialist_model)
                else:
                    prediction = get_ensemble_prediction(image_path, model)
                    preds = apply_crop_context(prediction, crop)

                logger.info(f"Prediction complete")
                
            except Exception as e:
                logger.error(f"Prediction error: {e}", exc_info=True)
                return render_template(
                    "index.html",
                    t=t,
                    language=language,
                    result=None,
                    confidence=None,
                    description=f"Model prediction failed: {str(e)}. Please try again.",
                    treatment=None,
                    soil_advice=soil_advice,
                    irrigation_advice=irrigation_advice,
                    weather_analysis=weather_analysis,
                    top2_predictions=None,
                    ai_advice=None,
                    chat_response=None
                )

        # Generate gradcam after prediction
        try:
            gradcam_path = generate_gradcam(image_path)
        except Exception as e:
            logger.error(f"GradCAM error: {e}")
            gradcam_path = None

        # Ensure we have prediction data
        if 'preds' not in locals():
            # If we used HuggingFace model successfully, we already have best_idx and confidence
            # If we fell back to local model, we also have preds, best_idx, confidence
            # If none of the above, this is an error case
            logger.error("No prediction data available")
            return render_template(
                "index.html",
                t=t,
                language=language,
                result=None,
                confidence=None,
                description="Prediction failed. Please try again.",
                treatment=None,
                soil_advice=soil_advice,
                irrigation_advice=irrigation_advice,
                weather_analysis=weather_analysis,
                top2_predictions=None,
                ai_advice=None,
                chat_response=None
            )

        prediction_summary = summarize_prediction(preds)
        all_predictions = prediction_summary["probabilities"]
        best_idx = prediction_summary["best_idx"]
        second_idx = prediction_summary["second_idx"]
        top2_predictions = prediction_summary["top2_predictions"]
        confidence = prediction_summary["confidence"]
        second_confidence = prediction_summary["second_confidence"]

        logger.info(f"Top prediction: {class_names[best_idx]} ({confidence:.4f})")
        logger.info(f"Second prediction: {class_names[second_idx]} ({second_confidence:.4f})")

        logger.info(f"Prediction result: {class_names[best_idx]} with confidence {confidence}")
        logger.info(f"Confidence values: best={confidence}, second={second_confidence}")

        uncertainty = assess_prediction_uncertainty(all_predictions)
        logger.info(
            f"Confidence analysis: "
            f"best={uncertainty['best']:.3f}, "
            f"second={uncertainty['second']:.3f}, "
            f"margin={uncertainty['margin']:.3f}, "
            f"entropy={uncertainty['normalized_entropy']:.3f}, "
            f"is_uncertain={uncertainty['is_uncertain']}"
        )

        if uncertainty["is_uncertain"]:
            # Try AI fallback for low confidence predictions
            logger.info("Low confidence detected, attempting AI fallback analysis")
            ai_prediction, ai_disease_idx, ai_reason = get_ai_fallback_prediction(image_path, crop, language)
            
            if ai_prediction is not None and ai_disease_idx is not None:
                # Use AI prediction as fallback
                preds = ai_prediction
                best_idx = ai_disease_idx
                confidence = float(preds[best_idx])
                second_idx = np.argsort(preds)[-2] if len(preds) > 1 else best_idx
                second_confidence = float(preds[second_idx])
                top2_predictions = [
                    (class_names[best_idx], float(preds[best_idx])),
                    (class_names[second_idx], float(preds[second_idx]))
                ]
                
                diagnosis_key = class_names[best_idx]
                result = f"{crop} - " + class_names[best_idx].replace("___", " - ").replace("_", " ")
                description = f"AI Analysis Result: {ai_reason or 'Disease identified by AI analysis'}"
                
                logger.info(f"AI fallback successful: {result} with confidence {confidence:.3f}")
                
                action_bundle = build_farmer_action_bundle(
                    crop=crop,
                    disease_key=diagnosis_key,
                    confidence=confidence * 100,
                    soil=soil,
                    moisture=moisture_val,
                    weather=weather,
                    uncertain=False,
                )
                treatment = action_bundle["treatment_summary"]
                treatment_summary = action_bundle["treatment_summary"]
                recommended_actions = action_bundle["recommended_actions"]
                recommended_products = action_bundle["recommended_products"]
                care_plan = action_bundle["care_plan"]
                expert_support_recommended = action_bundle["expert_support_recommended"]
                ai_advice = None
            else:
                # AI fallback failed, use original uncertain response
                diagnosis_key = "uncertain"
                result = f"{crop} - Unable to determine disease confidently"
                description = (
                    "The image does not match one disease strongly enough for a reliable answer. "
                    f"AI analysis also unavailable: {ai_reason or 'Unknown error'}. "
                    "Please retake the photo in better lighting with the leaf filling most of the frame."
                )
                action_bundle = build_farmer_action_bundle(
                    crop=crop,
                    disease_key=diagnosis_key,
                    confidence=confidence * 100,
                    soil=soil,
                    moisture=moisture_val,
                    weather=weather,
                    uncertain=True,
                )
                treatment = action_bundle["treatment_summary"]
                treatment_summary = action_bundle["treatment_summary"]
                recommended_actions = action_bundle["recommended_actions"]
                recommended_products = action_bundle["recommended_products"]
                care_plan = action_bundle["care_plan"]
                expert_support_recommended = action_bundle["expert_support_recommended"]
                ai_advice = None
                logger.info("AI fallback failed, keeping uncertain prediction")
        else:
            diagnosis_key = class_names[best_idx]
            result = f"{crop} - " + class_names[best_idx].replace("___", " - ").replace("_", " ")
            logger.info(f"High confidence - disease detected: {result}")
            action_bundle = build_farmer_action_bundle(
                crop=crop,
                disease_key=diagnosis_key,
                confidence=confidence * 100,
                soil=soil,
                moisture=moisture_val,
                weather=weather,
                uncertain=False,
            )
            treatment_summary = action_bundle["treatment_summary"]
            recommended_actions = action_bundle["recommended_actions"]
            recommended_products = action_bundle["recommended_products"]
            care_plan = action_bundle["care_plan"]
            expert_support_recommended = action_bundle["expert_support_recommended"]

            # Skip LLM if plant is healthy
            if "healthy" in result.lower():
                description = "The plant appears healthy with no visible disease symptoms."
                treatment = treatment_summary
                ai_advice = None
                logger.info("Plant is healthy")
            else:
                # Do not call LLM here so page loads faster.
                # The frontend can request detailed AI advice using the /ai_advice API.
                description = "Disease detected. Detailed AI advice will load shortly."
                treatment = treatment_summary
                ai_advice = None
                logger.info("Disease detected - AI advice available")

        confidence = round(confidence * 100, 2)
        logger.info(f"Final confidence: {confidence}%")
        logger.info("Prediction processing complete")
        
    else:
        logger.info("GET request - showing upload form")
        result = None
        image_path = None
        gradcam_path = None

    # 🔥 FORCE TRANSLATION FOR ALL OUTPUTS
    def translate_text(text):
        return translate_output(text, language)

    # Apply translation to ALL outputs (FIX: include result also)
    if request.method == "POST":
        result = translate_text(result)
        description = translate_text(description)
        treatment = translate_text(treatment)
        soil_advice = translate_text(soil_advice)
        irrigation_advice = translate_text(irrigation_advice)
        weather_analysis = translate_text(weather_analysis)
        translated_bundle = translate_action_bundle(
            {
                "treatment_summary": treatment_summary,
                "recommended_actions": recommended_actions,
                "recommended_products": recommended_products,
                "care_plan": care_plan,
                "expert_support_recommended": expert_support_recommended,
                "caution_note": None,
            },
            language,
        )
        treatment_summary = translated_bundle.get("treatment_summary")
        recommended_actions = translated_bundle.get("recommended_actions", [])
        recommended_products = translated_bundle.get("recommended_products", [])
        care_plan = translated_bundle.get("care_plan", [])

    # Translate top2_predictions names if present
    if request.method == "POST":
        if top2_predictions:
            top2_predictions = [
                (translate_text(name), prob)
                for name, prob in top2_predictions
            ]

    return render_template(
        "index.html",
        t=t,
        language=language,
        result=result,
        confidence=confidence,
        description=description,
        treatment=treatment,
        treatment_summary=treatment_summary,
        recommended_actions=recommended_actions,
        recommended_products=recommended_products,
        care_plan=care_plan,
        expert_support_recommended=expert_support_recommended,
        soil_advice=soil_advice,
        irrigation_advice=irrigation_advice,
        weather_analysis=weather_analysis,
        top2_predictions=top2_predictions,
        ai_advice=ai_advice,
        chat_response=chat_response,
        diagnosis_key=diagnosis_key,
        original_image_reference=original_image_reference,
        original_image=build_upload_url(original_image_reference) if request.method == "POST" else None,
        processed_image=gradcam_path if request.method == "POST" else None,
        moisture=latest_moisture,
    )


if __name__ == "__main__":
    port = int(app.config.get('PORT', 10000))
    debug_mode = bool(app.config.get('DEBUG', False))
    
    logger.info("Smart Farming AI Starting...")
    logger.info(f"Port: {port}")
    logger.info(f"Debug: {debug_mode}")
    logger.info(f"Environment: {app.config.get('ENVIRONMENT', 'development')}")

    app.run(host='0.0.0.0', port=port, debug=debug_mode)

# Keep import side effects light for tests and WSGI startup.
# Set PRELOAD_MODEL=true if you explicitly want eager model loading.
if app.config.get("PRELOAD_MODEL", False):
    try:
        logger.info("Initializing model on module import...")
        model = get_model()
        if model is not None:
            logger.info("Model loaded successfully on import")
        else:
            logger.warning("Model not loaded on import - fallback mode remains active")
    except Exception as e:
        logger.error(f"Model loading failed on import: {e}")
        model = None


def create_app():
    """WSGI-friendly application accessor."""
    return app
