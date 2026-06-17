import os
import json
import logging
from datetime import datetime
from typing import Dict, List, Optional, Tuple
from werkzeug.utils import secure_filename
from werkzeug.exceptions import RequestEntityTooLarge

from config import Config

logger = logging.getLogger(__name__)


class FileService:
    """Service class for file operations."""
    
    def __init__(self, app_root_path: str):
        self.app_root_path = app_root_path
        self.upload_folder = os.path.join(app_root_path, Config.UPLOAD_FOLDER)
        self.metadata_path = os.path.join(app_root_path, Config.METADATA_FILE)
    
    def load_metadata(self) -> Dict:
        """Load file metadata from JSON file."""
        try:
            if os.path.exists(self.metadata_path):
                with open(self.metadata_path, 'r') as f:
                    return json.load(f)
            return {}
        except (json.JSONDecodeError, IOError) as e:
            logger.error(f"Error loading metadata: {e}")
            return {}
    
    def save_metadata(self, metadata: Dict) -> bool:
        """Save file metadata to JSON file."""
        try:
            with open(self.metadata_path, 'w') as f:
                json.dump(metadata, f, indent=2)
            return True
        except IOError as e:
            logger.error(f"Error saving metadata: {e}")
            return False
    
    def get_file_extension(self, filename: str) -> str:
        """Extract file extension from filename."""
        return filename.rsplit('.', 1)[1].lower() if '.' in filename else ''
    
    def get_upload_folder(self) -> str:
        """Ensure upload folder exists and return path."""
        os.makedirs(self.upload_folder, exist_ok=True)
        return self.upload_folder
    
    def list_files(
        self, 
        search_query: str = '', 
        sort_by: str = 'name', 
        sort_order: str = 'asc'
    ) -> List[Dict]:
        """List files with optional search and sorting."""
        files = []
        
        if not os.path.exists(self.upload_folder):
            return files
        
        metadata = self.load_metadata()
        search_query = search_query.lower()
        
        for filename in os.listdir(self.upload_folder):
            file_path = os.path.join(self.upload_folder, filename)
            
            if not os.path.isfile(file_path):
                continue
            
            # Search filter
            if search_query and search_query not in filename.lower():
                continue
            
            file_size = os.path.getsize(file_path)
            file_ext = self.get_file_extension(filename)
            upload_date = metadata.get(filename, {}).get('upload_date', '')
            
            files.append({
                'name': filename,
                'size': file_size,
                'extension': file_ext,
                'upload_date': upload_date
            })
        
        # Sort files
        sort_key = self._get_sort_key(sort_by)
        if sort_key:
            files.sort(key=sort_key, reverse=(sort_order == 'desc'))
        
        return files
    
    def _get_sort_key(self, sort_by: str):
        """Get sort key function based on sort criteria."""
        sort_keys = {
            'name': lambda x: x['name'],
            'size': lambda x: x['size'],
            'type': lambda x: x['extension'],
            'date': lambda x: x['upload_date'] or ''
        }
        return sort_keys.get(sort_by)
    
    def upload_file(self, file) -> Tuple[bool, str]:
        """Upload a file and save metadata."""
        try:
            if not file or file.filename == '':
                return False, 'No file selected'
            
            filename = secure_filename(file.filename)
            upload_folder = self.get_upload_folder()
            file_path = os.path.join(upload_folder, filename)
            
            # Save file
            file.save(file_path)
            
            # Update metadata
            metadata = self.load_metadata()
            metadata[filename] = {
                'upload_date': datetime.now().isoformat()
            }
            self.save_metadata(metadata)
            
            logger.info(f"File uploaded successfully: {filename}")
            return True, f'File "{filename}" uploaded successfully'
            
        except RequestEntityTooLarge:
            max_mb = Config.MAX_FILE_SIZE / (1024 * 1024)
            return False, f'File too large. Maximum size is {max_mb:.0f}MB'
        except Exception as e:
            logger.error(f"Error uploading file: {e}")
            return False, f'Error uploading file: {str(e)}'
    
    def get_file_path(self, filename: str) -> Optional[str]:
        """Get full path for a file if it exists."""
        filename = secure_filename(filename)
        file_path = os.path.join(self.upload_folder, filename)
        
        if os.path.exists(file_path) and os.path.isfile(file_path):
            return file_path
        return None
    
    def delete_file(self, filename: str) -> Tuple[bool, str]:
        """Delete a file and its metadata."""
        try:
            filename = secure_filename(filename)
            file_path = os.path.join(self.upload_folder, filename)
            
            if not os.path.exists(file_path):
                return False, 'File not found'
            
            # Remove file
            os.remove(file_path)
            
            # Remove metadata
            metadata = self.load_metadata()
            if filename in metadata:
                del metadata[filename]
                self.save_metadata(metadata)
            
            logger.info(f"File deleted successfully: {filename}")
            return True, f'File "{filename}" deleted successfully'
            
        except Exception as e:
            logger.error(f"Error deleting file: {e}")
            return False, f'Error deleting file: {str(e)}'


class AuthService:
    """Service class for authentication operations."""
    
    @staticmethod
    def verify_password(password: str) -> bool:
        """Verify password against stored hash."""
        import bcrypt
        try:
            return bcrypt.checkpw(
                password.encode('utf-8'), 
                Config.DEFAULT_PASSWORD_HASH
            )
        except Exception as e:
            logger.error(f"Error verifying password: {e}")
            return False
