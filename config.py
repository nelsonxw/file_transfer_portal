import os
import logging
from typing import Final
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()


def setup_logging(level: int = logging.INFO) -> None:
    """Configure application logging."""
    logging.basicConfig(
        level=level,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )


class Config:
    """Application configuration class."""
    
    # Flask configuration
    SECRET_KEY: str = os.environ.get('SECRET_KEY', 'dev-secret-key-change-in-production')
    
    # File upload configuration
    METADATA_FILE: Final[str] = 'file_metadata.json'
    MAX_FILE_SIZE: Final[int] = 1024 * 1024 * 1024  # 1 GB
    PRESIGNED_URL_EXPIRATION: Final[int] = int(os.environ.get('PRESIGNED_URL_EXPIRATION', "900"))
    
    # Firebase Storage configuration (required)
    # Path to the service account JSON file (required for signed upload URLs)
    FIREBASE_SERVICE_ACCOUNT_PATH: str = os.environ.get('FIREBASE_SERVICE_ACCOUNT_PATH', '')
    # Storage bucket name, e.g. "my-app.appspot.com"
    FIREBASE_STORAGE_BUCKET: str = os.environ.get('FIREBASE_STORAGE_BUCKET', '')
    
    # Authentication
    # Default password is "admin123"
    DEFAULT_PASSWORD_HASH: Final[bytes] = b'$2b$12$o/bSBL6nwXgCeETQBdXu4uKnMxanD2lOEVM5GHfnfcVABGqVLhD4q'
    
    @staticmethod
    def validate() -> bool:
        """Validate required configuration values."""
        if not Config.FIREBASE_STORAGE_BUCKET:
            raise ValueError("FIREBASE_STORAGE_BUCKET is required")
        if not Config.FIREBASE_SERVICE_ACCOUNT_PATH:
            raise ValueError("FIREBASE_SERVICE_ACCOUNT_PATH is required for signed URLs")
        if not os.path.exists(Config.FIREBASE_SERVICE_ACCOUNT_PATH):
            raise ValueError(f"Service account file not found: {Config.FIREBASE_SERVICE_ACCOUNT_PATH}")
        return True
    
    @staticmethod
    def init_app(app):
        """Initialize Flask app with configuration."""
        Config.validate()
        app.config['SECRET_KEY'] = Config.SECRET_KEY
        app.config['MAX_CONTENT_LENGTH'] = Config.MAX_FILE_SIZE
