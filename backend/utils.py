"""
Utility functions for Smart Farming Assistant
"""
import os
import logging
import gc
from functools import wraps
from flask import jsonify
import time

logger = logging.getLogger(__name__)

def cleanup_model(model):
    """Clean up model from memory"""
    try:
        if model:
            del model
            gc.collect()
            logger.info("Model cleaned up from memory")
    except Exception as e:
        logger.error(f"Error cleaning up model: {e}")

def format_error_message(error, user_friendly=True):
    """Format error message appropriately"""
    if user_friendly:
        # Return user-friendly message
        return "An error occurred. Please try again later."
    else:
        # Return detailed error for logging
        return str(error)

def validate_moisture_value(moisture):
    """Validate and normalize moisture value"""
    try:
        moisture_val = int(moisture) if moisture is not None else 40
        if moisture_val < 0:
            moisture_val = 0
        elif moisture_val > 100:
            moisture_val = 100
        return moisture_val
    except (ValueError, TypeError):
        return 40  # Default value

def get_unique_filename(original_filename):
    """Generate unique filename to prevent conflicts"""
    import uuid
    name, ext = os.path.splitext(original_filename)
    unique_id = uuid.uuid4().hex[:8]
    return f"{name}_{unique_id}{ext}"

def timer(func):
    """Decorator to time function execution"""
    @wraps(func)
    def wrapper(*args, **kwargs):
        start_time = time.time()
        result = func(*args, **kwargs)
        end_time = time.time()
        execution_time = end_time - start_time
        logger.info(f"{func.__name__} executed in {execution_time:.2f} seconds")
        return result
    return wrapper

def cache_response(ttl=300):
    """Simple response caching decorator"""
    cache = {}
    
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            # Create cache key
            cache_key = str(args) + str(sorted(kwargs.items()))
            
            # Check cache
            if cache_key in cache:
                cached_time, cached_result = cache[cache_key]
                if time.time() - cached_time < ttl:
                    logger.debug(f"Cache hit for {func.__name__}")
                    return cached_result
            
            # Execute function
            result = func(*args, **kwargs)
            
            # Cache result
            cache[cache_key] = (time.time(), result)
            logger.debug(f"Cached result for {func.__name__}")
            
            return result
        return wrapper
    return decorator

def create_response(success=True, message="", data=None, status_code=200):
    """Create standardized API response"""
    response = {
        'success': success,
        'message': message,
        'timestamp': time.time()
    }
    
    if data is not None:
        response['data'] = data
    
    return jsonify(response), status_code

def health_check():
    """Comprehensive health check"""
    status = {
        'status': 'healthy',
        'timestamp': time.time(),
        'checks': {}
    }
    
    # Check model availability
    try:
        from app import get_model
        model = get_model()
        status['checks']['model'] = {
            'status': 'healthy' if model else 'unavailable',
            'loaded': model is not None
        }
    except Exception as e:
        status['checks']['model'] = {
            'status': 'error',
            'error': str(e)
        }
    
    # Check AI service
    try:
        from app import client
        status['checks']['ai_service'] = {
            'status': 'healthy' if client else 'disabled',
            'configured': client is not None
        }
    except Exception as e:
        status['checks']['ai_service'] = {
            'status': 'error',
            'error': str(e)
        }
    
    # Check disk space
    try:
        import psutil
        disk = psutil.disk_usage('/')
        free_percent = (disk.free / disk.total) * 100
        status['checks']['disk_space'] = {
            'status': 'healthy' if free_percent > 10 else 'warning',
            'free_percent': round(free_percent, 2)
        }
    except:
        status['checks']['disk_space'] = {
            'status': 'unknown',
            'message': 'Could not check disk space'
        }
    
    # Overall status
    all_healthy = all(
        check.get('status') in ['healthy', 'disabled'] 
        for check in status['checks'].values()
    )
    
    status['status'] = 'healthy' if all_healthy else 'unhealthy'
    
    return status
