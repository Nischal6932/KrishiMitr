"""
Enhanced error handling for Smart Farming Assistant
"""
import logging
import traceback
from functools import wraps
from flask import jsonify
import time

logger = logging.getLogger(__name__)

class SmartFarmingError(Exception):
    """Base exception for Smart Farming Assistant"""
    def __init__(self, message, error_code=None, user_message=None):
        super().__init__(message)
        self.error_code = error_code
        self.user_message = user_message or message
        self.timestamp = time.time()

class ModelError(SmartFarmingError):
    """Model-related errors"""
    pass

class AIServiceError(SmartFarmingError):
    """AI service related errors"""
    pass

class ValidationError(SmartFarmingError):
    """Validation errors"""
    pass

class FileProcessingError(SmartFarmingError):
    """File processing errors"""
    pass

def handle_errors(func):
    """Decorator for consistent error handling"""
    @wraps(func)
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except SmartFarmingError as e:
            logger.error(f"Smart Farming Error: {e}", exc_info=True)
            return {
                'success': False,
                'error': e.user_message,
                'error_code': e.error_code,
                'timestamp': e.timestamp
            }, 400
        except Exception as e:
            logger.error(f"Unexpected error in {func.__name__}: {e}", exc_info=True)
            return {
                'success': False,
                'error': 'An unexpected error occurred. Please try again.',
                'error_code': 'INTERNAL_ERROR',
                'timestamp': time.time()
            }, 500
    return wrapper

def log_api_request(func):
    """Decorator for API request logging"""
    @wraps(func)
    def wrapper(*args, **kwargs):
        start_time = time.time()
        try:
            result = func(*args, **kwargs)
            end_time = time.time()
            logger.info(f"{func.__name__} completed in {end_time - start_time:.2f}s")
            return result
        except Exception as e:
            end_time = time.time()
            logger.error(f"{func.__name__} failed after {end_time - start_time:.2f}s: {e}")
            raise
    return wrapper

# Error messages for different scenarios
ERROR_MESSAGES = {
    'file_too_large': 'File size exceeds 16MB limit. Please choose a smaller image.',
    'invalid_file_type': 'Invalid file type. Please upload JPG, PNG, or WebP images.',
    'no_file_uploaded': 'Please select an image file to analyze.',
    'model_not_loaded': 'AI model is currently unavailable. Please try again later.',
    'ai_service_down': 'AI service is temporarily unavailable. Please try again later.',
    'processing_failed': 'Image processing failed. Please try with a different image.',
    'network_error': 'Network connection issue. Please check your internet connection.',
    'invalid_parameters': 'Invalid parameters provided. Please check your inputs.'
}

def get_user_friendly_error(error_key, default_message="An error occurred. Please try again."):
    """Get user-friendly error message"""
    return ERROR_MESSAGES.get(error_key, default_message)
