"""Security utilities for Smart Farming Assistant."""
import logging
from werkzeug.utils import secure_filename
from flask import request

try:
    import magic
except Exception:  # pragma: no cover - optional dependency fallback
    magic = None

logger = logging.getLogger(__name__)

class FileValidator:
    """File validation utilities"""
    
    ALLOWED_MIME_TYPES = [
        'image/jpeg',
        'image/jpg', 
        'image/png',
        'image/webp'
    ]
    
    @staticmethod
    def validate_file(file, allowed_extensions=None, max_size=16 * 1024 * 1024):
        """Comprehensive file validation"""
        if not file or file.filename == '':
            return False, "No file selected"
        
        # Check filename
        filename = secure_filename(file.filename)
        if not filename:
            return False, "Invalid filename"
        
        # Check file extension
        allowed_extensions = allowed_extensions or ['.jpg', '.jpeg', '.png', '.webp']
        if not any(filename.lower().endswith(ext) for ext in allowed_extensions):
            return False, f"Invalid file type. Allowed: {', '.join(allowed_extensions)}"
        
        # Check file size
        file.seek(0, 2)  # Seek to end
        file_size = file.tell()
        file.seek(0)  # Reset to beginning
        
        if file_size > max_size:
            return False, f"File too large. Maximum size: {max_size // (1024*1024)}MB"
        
        # Check MIME type
        try:
            # Read first 1024 bytes for MIME detection
            file_content = file.read(1024)
            file.seek(0)  # Reset to beginning
            
            if magic is None:
                raise RuntimeError("python-magic is not installed")

            mime = magic.Magic(mime=True)
            mime_type = mime.from_buffer(file_content)
            
            if mime_type not in FileValidator.ALLOWED_MIME_TYPES:
                logger.warning(f"Rejected file with MIME type: {mime_type}")
                return False, f"File type {mime_type} not allowed"
                
        except Exception as e:
            logger.error(f"MIME type detection failed: {e}")
            # Continue without MIME check if python-magic is not available
            pass
        
        return True, "File valid"
    
    @staticmethod
    def sanitize_filename(filename):
        """Sanitize filename for secure storage"""
        return secure_filename(filename)

class RateLimiter:
    """Simple rate limiting implementation"""
    
    def __init__(self, max_requests=100, window_seconds=3600):
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self.requests = {}
    
    def is_allowed(self, identifier):
        """Check if request is allowed"""
        import time
        
        now = time.time()
        window_start = now - self.window_seconds
        
        # Clean old requests
        if identifier in self.requests:
            self.requests[identifier] = [
                req_time for req_time in self.requests[identifier] 
                if req_time > window_start
            ]
        else:
            self.requests[identifier] = []
        
        # Check limit
        if len(self.requests[identifier]) >= self.max_requests:
            return False
        
        # Add current request
        self.requests[identifier].append(now)
        return True

upload_limiter = RateLimiter(max_requests=10, window_seconds=60)
ai_advice_limiter = RateLimiter(max_requests=30, window_seconds=60)

def validate_rate_limit(limiter, identifier=None):
    """Validate a request against the provided limiter."""
    client_ip = identifier or get_client_ip()

    if not limiter.is_allowed(client_ip):
        logger.warning(f"Rate limit exceeded for IP: {client_ip}")
        return False, "Too many requests. Please try again later."

    return True, "Request allowed"

def validate_upload_request():
    """Validate upload request with rate limiting."""
    return validate_rate_limit(upload_limiter)

def validate_ai_advice_request():
    """Validate AI advice request rate limit."""
    return validate_rate_limit(ai_advice_limiter)

def get_client_ip():
    """Get client IP address safely"""
    # Check for forwarded headers (common in production)
    if request.headers.get('X-Forwarded-For'):
        return request.headers.get('X-Forwarded-For').split(',')[0].strip()
    elif request.headers.get('X-Real-IP'):
        return request.headers.get('X-Real-IP')
    else:
        return request.remote_addr
