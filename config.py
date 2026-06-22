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
    MAX_FILE_SIZE: Final[int] = 500 * 1024 * 1024  # 500 MB
    
    # AWS S3 configuration (required)
    AWS_ACCESS_KEY_ID: str = os.environ.get('AWS_ACCESS_KEY_ID', '')
    AWS_SECRET_ACCESS_KEY: str = os.environ.get('AWS_SECRET_ACCESS_KEY', '')
    AWS_REGION: str = os.environ.get('AWS_REGION', 'us-east-1')
    S3_BUCKET_NAME: str = os.environ.get('S3_BUCKET_NAME', '')
    
    # Authentication
    # Default password is "admin123"
    DEFAULT_PASSWORD_HASH: Final[bytes] = b'$2b$12$o/bSBL6nwXgCeETQBdXu4uKnMxanD2lOEVM5GHfnfcVABGqVLhD4q'
    
    @staticmethod
    def validate() -> bool:
        """Validate required configuration values."""
        if not Config.AWS_ACCESS_KEY_ID:
            raise ValueError("AWS_ACCESS_KEY_ID is required")
        if not Config.AWS_SECRET_ACCESS_KEY:
            raise ValueError("AWS_SECRET_ACCESS_KEY is required")
        if not Config.S3_BUCKET_NAME:
            raise ValueError("S3_BUCKET_NAME is required")
        return True
    
    @staticmethod
    def init_app(app):
        """Initialize Flask app with configuration."""
        Config.validate()
        app.config['SECRET_KEY'] = Config.SECRET_KEY
        app.config['MAX_CONTENT_LENGTH'] = Config.MAX_FILE_SIZE
