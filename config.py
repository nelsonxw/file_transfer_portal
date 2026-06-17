import os
from typing import Final


class Config:
    """Application configuration class."""
    
    # Flask configuration
    SECRET_KEY: str = os.environ.get('SECRET_KEY', 'dev-secret-key-change-in-production')
    
    # File upload configuration
    UPLOAD_FOLDER: Final[str] = 'uploads'
    METADATA_FILE: Final[str] = 'file_metadata.json'
    MAX_FILE_SIZE: Final[int] = 100 * 1024 * 1024  # 100 MB
    
    # Authentication
    # Default password is "admin123"
    DEFAULT_PASSWORD_HASH: Final[bytes] = b'$2b$12$o/bSBL6nwXgCeETQBdXu4uKnMxanD2lOEVM5GHfnfcVABGqVLhD4q'
    
    @staticmethod
    def init_app(app):
        """Initialize Flask app with configuration."""
        app.config['SECRET_KEY'] = Config.SECRET_KEY
        app.config['UPLOAD_FOLDER'] = Config.UPLOAD_FOLDER
        app.config['MAX_CONTENT_LENGTH'] = Config.MAX_FILE_SIZE
