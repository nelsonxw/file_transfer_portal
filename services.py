import os
import io
import json
import logging
import bcrypt
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple, Any
from werkzeug.utils import secure_filename
from werkzeug.exceptions import RequestEntityTooLarge
from werkzeug.datastructures import FileStorage

import firebase_admin
from firebase_admin import credentials, storage

from config import Config

logger = logging.getLogger(__name__)


class FileService:
    """Service class for file operations using Firebase Storage."""
    
    def __init__(self, app_root_path: str):
        self.app_root_path = app_root_path
        self.metadata_key = 'metadata/file_metadata.json'
        
        # Initialize Firebase Storage
        try:
            if not firebase_admin._apps:
                if Config.FIREBASE_SERVICE_ACCOUNT_JSON:
                    cred = credentials.Certificate(json.loads(Config.FIREBASE_SERVICE_ACCOUNT_JSON))
                else:
                    cred = credentials.Certificate(Config.FIREBASE_SERVICE_ACCOUNT_PATH)
                firebase_admin.initialize_app(
                    cred,
                    {'storageBucket': Config.FIREBASE_STORAGE_BUCKET}
                )
            self.bucket = storage.bucket()
            logger.info(f"Successfully connected to Firebase Storage bucket: {Config.FIREBASE_STORAGE_BUCKET}")
        except Exception as e:
            logger.error(f"Failed to initialize Firebase Storage: {e}")
            raise
    
    def load_metadata(self) -> Dict[str, Dict]:
        """Load file metadata from Firebase Storage by reading blob metadata."""
        metadata = {}
        try:
            blobs = self.bucket.list_blobs()
            
            for blob in blobs:
                # Skip metadata file
                if blob.name == self.metadata_key:
                    continue
                
                # Get object custom metadata
                try:
                    blob.reload()
                    upload_date = (blob.metadata or {}).get('upload_date')
                    if upload_date:
                        metadata[blob.name] = {'upload_date': upload_date}
                except Exception:
                    # Object might have been deleted, skip
                    continue
            
            return metadata
        except Exception as e:
            logger.error(f"Error loading metadata from Firebase Storage: {e}")
            return {}
    
    def save_metadata(self, metadata: Dict[str, Dict], etag: Optional[str] = None) -> bool:
        """Save file metadata to Firebase Storage (deprecated - metadata now stored per-object)."""
        # This method is kept for backward compatibility but no longer used
        return True
    
    def get_file_extension(self, filename: str) -> str:
        """Extract file extension from filename."""
        return filename.rsplit('.', 1)[1].lower() if '.' in filename else ''
    
    def list_files(
        self, 
        search_query: str = '', 
        sort_by: str = 'name', 
        sort_order: str = 'asc'
    ) -> List[Dict[str, any]]:
        """List files with optional search and sorting."""
        files = []
        metadata = self.load_metadata()
        search_query_lower = search_query.lower().strip() if search_query else ''
        
        try:
            # List objects from Firebase Storage
            blobs = self.bucket.list_blobs()
            
            for blob in blobs:
                filename = blob.name
                
                # Skip metadata file
                if filename == self.metadata_key:
                    continue
                
                # Search filter - only filter if search_query is not empty
                if search_query_lower and search_query_lower not in filename.lower():
                    continue
                
                file_size = blob.size or 0
                file_ext = self.get_file_extension(filename)
                upload_date = metadata.get(filename, {}).get('upload_date', '')
                
                files.append({
                    'name': filename,
                    'size': file_size,
                    'extension': file_ext,
                    'upload_date': upload_date
                })
        except Exception as e:
            logger.error(f"Error listing files from Firebase Storage: {e}")
        
        # Sort files
        sort_key = self._get_sort_key(sort_by)
        if sort_key:
            files.sort(key=sort_key, reverse=(sort_order == 'desc'))
        
        return files
    
    def _get_sort_key(self, sort_by: str):
        """Get sort key function based on sort criteria."""
        sort_keys = {
            'name': lambda x: x['name'].lower(),
            'size': lambda x: x['size'],
            'type': lambda x: x['extension'].lower(),
            'date': lambda x: x['upload_date'] or ''
        }
        return sort_keys.get(sort_by)
    
    def _current_iso_timestamp(self) -> str:
        """Return a UTC ISO-8601 timestamp without microseconds."""
        return datetime.utcnow().replace(microsecond=0).isoformat() + 'Z'

    def validate_upload_request(self, filename: str, file_size: Optional[int]) -> Tuple[bool, str, Optional[str]]:
        """Validate filename and file size before creating a presigned URL."""
        if not filename:
            return False, 'Filename is required', None

        sanitized_name = secure_filename(filename)
        if not sanitized_name:
            return False, 'Invalid filename provided', None

        if file_size is None:
            return False, 'File size is required', None

        if file_size > Config.MAX_FILE_SIZE:
            max_gb = Config.MAX_FILE_SIZE / (1024 * 1024 * 1024)
            return False, f'File too large. Maximum size is {max_gb:.0f}GB', None

        return True, '', sanitized_name

    def upload_file(self, file: FileStorage) -> Tuple[bool, str]:
        """Upload a file to Firebase Storage with upload date as custom metadata."""
        try:
            if not file or file.filename == '':
                return False, 'No file selected'
            
            filename = secure_filename(file.filename)
            upload_date = self._current_iso_timestamp()
            
            # Upload file to Firebase Storage with metadata
            blob = self.bucket.blob(filename)
            blob.upload_from_file(file, content_type=file.content_type or 'application/octet-stream')
            blob.metadata = {'upload_date': upload_date}
            blob.patch()
            logger.info(f"File uploaded successfully to Firebase Storage with metadata: {filename}")
            
            return True, f'File "{filename}" uploaded successfully'
            
        except RequestEntityTooLarge:
            max_gb = Config.MAX_FILE_SIZE / (1024 * 1024 * 1024)
            return False, f'File too large. Maximum size is {max_gb:.0f}GB'
        except Exception as e:
            logger.error(f"Error uploading file to Firebase Storage: {e}")
            return False, f'Error uploading file to Firebase Storage: {str(e)}'
    
    def file_exists(self, filename: str) -> bool:
        """Check if a file exists in Firebase Storage."""
        filename = secure_filename(filename)
        try:
            return self.bucket.blob(filename).exists()
        except Exception:
            return False
    
    def download_file(self, filename: str) -> Tuple[bool, Optional[Any], str]:
        """Download a file from Firebase Storage and return the file stream and content type."""
        filename = secure_filename(filename)
        try:
            blob = self.bucket.blob(filename)
            if not blob.exists():
                return False, None, 'File not found'
            data = blob.download_as_bytes()
            content_type = blob.content_type or 'application/octet-stream'
            logger.info(f'File downloaded from Firebase Storage: {filename}')
            return True, io.BytesIO(data), content_type
        except Exception as e:
            logger.error(f'Error downloading from Firebase Storage: {e}')
            return False, None, str(e)
    
    def delete_file(self, filename: str) -> Tuple[bool, str]:
        """Delete a file from Firebase Storage (metadata is automatically removed with the file)."""
        try:
            filename = secure_filename(filename)
            
            blob = self.bucket.blob(filename)
            if not blob.exists():
                return False, 'File not found'
            
            # Delete file from Firebase Storage (metadata is stored with the file, so it's removed automatically)
            blob.delete()
            logger.info(f"File deleted successfully from Firebase Storage: {filename}")
            
            return True, f'File "{filename}" deleted successfully'
            
        except Exception as e:
            logger.error(f"Error deleting file from Firebase Storage: {e}")
            return False, f'Error deleting file from Firebase Storage: {str(e)}'
    
    def generate_presigned_url(
        self,
        filename: str,
        content_type: Optional[str] = None,
        upload_date: Optional[str] = None,
        expiration: Optional[int] = None
    ) -> Tuple[bool, Optional[str], Optional[Dict[str, str]], Optional[str]]:
        """Generate a signed URL and headers for uploading a file directly to Firebase Storage."""
        try:
            sanitized_name = secure_filename(filename)
            normalized_content_type = content_type or 'application/octet-stream'
            timestamp = upload_date or self._current_iso_timestamp()

            blob = self.bucket.blob(sanitized_name)
            presigned_url = blob.generate_signed_url(
                version='v4',
                expiration=timedelta(seconds=expiration or Config.PRESIGNED_URL_EXPIRATION),
                method='PUT',
                content_type=normalized_content_type,
                headers={'x-goog-meta-upload_date': timestamp}
            )

            headers = {
                'Content-Type': normalized_content_type,
                'x-goog-meta-upload_date': timestamp
            }

            logger.info(f"Generated signed URL for: {sanitized_name}")
            return True, presigned_url, headers, sanitized_name

        except Exception as e:
            logger.error(f"Error generating signed URL: {e}")
            return False, None, None, None
    
    def configure_cors(self, allowed_origins: List[str] = None) -> Tuple[bool, str]:
        """Configure CORS policy for the Firebase Storage bucket to allow cross-origin requests."""
        if allowed_origins is None:
            allowed_origins = ['*']  # Allow all origins by default
        
        cors_configuration = [
            {
                'origin': allowed_origins,
                'method': ['PUT', 'POST', 'GET', 'DELETE', 'HEAD', 'OPTIONS'],
                'responseHeader': ['ETag', 'Content-Type'],
                'maxAgeSeconds': 3600
            }
        ]
        
        try:
            self.bucket.cors = cors_configuration
            self.bucket.patch()
            logger.info(f"CORS configuration updated for bucket: {Config.FIREBASE_STORAGE_BUCKET}")
            return True, 'CORS configuration updated successfully'
        except Exception as e:
            logger.error(f"Error configuring CORS: {e}")
            return False, f'Error configuring CORS: {str(e)}'


class AuthService:
    """Service class for authentication operations."""
    
    @staticmethod
    def verify_password(password: str) -> bool:
        """Verify password against stored hash."""
        try:
            return bcrypt.checkpw(
                password.encode('utf-8'), 
                Config.DEFAULT_PASSWORD_HASH
            )
        except Exception as e:
            logger.error(f"Error verifying password: {e}")
            return False
