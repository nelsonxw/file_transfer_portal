import os
import json
import logging
from datetime import datetime
from typing import Dict, List, Optional, Tuple
from werkzeug.utils import secure_filename
from werkzeug.exceptions import RequestEntityTooLarge
import boto3
from botocore.exceptions import ClientError, NoCredentialsError

from config import Config

logger = logging.getLogger(__name__)


class FileService:
    """Service class for file operations using AWS S3."""
    
    def __init__(self, app_root_path: str):
        self.app_root_path = app_root_path
        self.metadata_path = os.path.join(app_root_path, Config.METADATA_FILE)
        
        # Initialize S3 client
        try:
            self.s3_client = boto3.client(
                's3',
                aws_access_key_id=Config.AWS_ACCESS_KEY_ID,
                aws_secret_access_key=Config.AWS_SECRET_ACCESS_KEY,
                region_name=Config.AWS_REGION
            )
            self.bucket_name = Config.S3_BUCKET_NAME
            
            # Verify bucket exists and is accessible
            self.s3_client.head_bucket(Bucket=self.bucket_name)
            logger.info(f"Successfully connected to S3 bucket: {self.bucket_name}")
        except (ClientError, NoCredentialsError) as e:
            logger.error(f"Failed to initialize S3 client: {e}")
            raise
    
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
    
    def list_files(
        self, 
        search_query: str = '', 
        sort_by: str = 'name', 
        sort_order: str = 'asc'
    ) -> List[Dict]:
        """List files with optional search and sorting."""
        files = []
        
        try:
            metadata = self.load_metadata()
            search_query = search_query.lower()
            
            # List objects from S3
            response = self.s3_client.list_objects_v2(Bucket=self.bucket_name)
            
            if 'Contents' in response:
                for obj in response['Contents']:
                    filename = obj['Key']
                    
                    # Search filter
                    if search_query and search_query not in filename.lower():
                        continue
                    
                    file_size = obj['Size']
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
            
        except ClientError as e:
            logger.error(f"Error listing files from S3: {e}")
        
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
        """Upload a file to S3 and save metadata."""
        try:
            if not file or file.filename == '':
                return False, 'No file selected'
            
            filename = secure_filename(file.filename)
            
            # Upload file to S3
            self.s3_client.upload_fileobj(
                file,
                self.bucket_name,
                filename,
                ExtraArgs={'ContentType': file.content_type}
            )
            
            # Update metadata
            metadata = self.load_metadata()
            metadata[filename] = {
                'upload_date': datetime.now().isoformat()
            }
            self.save_metadata(metadata)
            
            logger.info(f"File uploaded successfully to S3: {filename}")
            return True, f'File "{filename}" uploaded successfully'
            
        except RequestEntityTooLarge:
            max_mb = Config.MAX_FILE_SIZE / (1024 * 1024)
            return False, f'File too large. Maximum size is {max_mb:.0f}MB'
        except ClientError as e:
            logger.error(f"Error uploading file to S3: {e}")
            return False, f'Error uploading file to S3: {str(e)}'
        except Exception as e:
            logger.error(f"Error uploading file: {e}")
            return False, f'Error uploading file: {str(e)}'
    
    def file_exists(self, filename: str) -> bool:
        """Check if a file exists in S3."""
        try:
            filename = secure_filename(filename)
            self.s3_client.head_object(Bucket=self.bucket_name, Key=filename)
            return True
        except ClientError:
            return False
    
    def delete_file(self, filename: str) -> Tuple[bool, str]:
        """Delete a file from S3 and its metadata."""
        try:
            filename = secure_filename(filename)
            
            if not self.file_exists(filename):
                return False, 'File not found'
            
            # Delete file from S3
            self.s3_client.delete_object(Bucket=self.bucket_name, Key=filename)
            
            # Remove metadata
            metadata = self.load_metadata()
            if filename in metadata:
                del metadata[filename]
                self.save_metadata(metadata)
            
            logger.info(f"File deleted successfully from S3: {filename}")
            return True, f'File "{filename}" deleted successfully'
            
        except ClientError as e:
            logger.error(f"Error deleting file from S3: {e}")
            return False, f'Error deleting file from S3: {str(e)}'
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
