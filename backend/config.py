"""Configuration management for Smart Farming Assistant."""
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

class Config:
    """Base configuration class"""
    # Flask Configuration
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'dev-secret-key-change-in-production'
    DEBUG = os.environ.get('FLASK_DEBUG', 'False').lower() == 'true'
    PORT = int(os.environ.get('PORT', 10000))
    ENVIRONMENT = os.environ.get('ENVIRONMENT', 'development')
    TESTING = False
    
    # File Upload Configuration
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # 16MB max file size
    UPLOAD_FOLDER = '/tmp'
    UPLOAD_EXTENSIONS = ['.jpg', '.jpeg', '.png', '.webp']
    PRELOAD_MODEL = os.environ.get('PRELOAD_MODEL', 'False').lower() == 'true'
    
    # Model Configuration
    MODEL_PATH = os.environ.get('MODEL_PATH', 'plant_disease_realworld_15class_best_v4.keras')
    GITHUB_MODEL_URL = os.environ.get('GITHUB_MODEL_URL', 
        'https://github.com/Nischal6932/No_Ollama/releases/download/v1.0/plant_disease_realworld_15class_best_v4.keras')
    
    # AI Service Configuration
    GROQ_API_KEY = os.environ.get('GROQ_API_KEY')
    
    # AWS S3 Configuration (optional)
    AWS_ACCESS_KEY_ID = os.environ.get('AWS_ACCESS_KEY_ID')
    AWS_SECRET_ACCESS_KEY = os.environ.get('AWS_SECRET_ACCESS_KEY')
    AWS_BUCKET_NAME = os.environ.get('AWS_BUCKET_NAME')
    AWS_REGION = os.environ.get('AWS_REGION', 'us-east-1')
    
    # Logging Configuration
    LOG_LEVEL = os.environ.get('LOG_LEVEL', 'INFO')
    LOG_FILE = os.environ.get('LOG_FILE', 'smart_farming.log')
    
    # Security Configuration
    RATE_LIMIT_STORAGE_URL = os.environ.get('RATE_LIMIT_STORAGE_URL', 'memory://')
    ENABLE_PROXY_FIX = os.environ.get('ENABLE_PROXY_FIX', 'True').lower() == 'true'
    CORS_ORIGINS = os.environ.get('CORS_ORIGINS', '*')

    @staticmethod
    def validate_required():
        """Validate required configuration"""
        missing = []
        if Config.ENVIRONMENT == 'production' and not Config.GROQ_API_KEY:
            missing.append('GROQ_API_KEY')
        
        if missing:
            raise ValueError(f"Missing required environment variables: {', '.join(missing)}")
        
        return True

class DevelopmentConfig(Config):
    """Development configuration"""
    DEBUG = True
    LOG_LEVEL = 'DEBUG'

class ProductionConfig(Config):
    """Production configuration"""
    DEBUG = False
    LOG_LEVEL = 'INFO'
    
    @staticmethod
    def validate_required():
        """Validate production configuration"""
        Config.validate_required()
        
        # Additional production validations
        if Config.SECRET_KEY == 'dev-secret-key-change-in-production':
            raise ValueError("SECRET_KEY must be set in production")

class TestingConfig(Config):
    """Testing configuration"""
    TESTING = True
    DEBUG = True
    ENVIRONMENT = 'testing'
    GROQ_API_KEY = 'test-key'

# Configuration mapping
config = {
    'development': DevelopmentConfig,
    'production': ProductionConfig,
    'testing': TestingConfig,
    'default': DevelopmentConfig
}
