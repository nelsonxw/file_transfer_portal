import os
import json
import logging
import bcrypt
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple, Any
from werkzeug.utils import secure_filename
from werkzeug.exceptions import RequestEntityTooLarge
from werkzeug.datastructures import FileStorage
import boto3
from botocore.exceptions import ClientError, NoCredentialsError

from config import Config

logger = logging.getLogger(__name__)


class FileService:
    """Service class for file operations using AWS S3."""
    
    def __init__(self, app_root_path: str):
        self.app_root_path = app_root_path
        self.metadata_path = os.path.join(app_root_path, Config.METADATA_FILE)
        self.metadata_key = 'metadata/file_metadata.json'
        
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
    
    def load_metadata(self) -> Dict[str, Dict]:
        """Load file metadata from S3 by scanning all objects and their metadata."""
        metadata = {}
        try:
            # List all objects in the bucket
            response = self.s3_client.list_objects_v2(Bucket=self.bucket_name)
            
            if 'Contents' in response:
                for obj in response['Contents']:
                    filename = obj['Key']
                    # Skip metadata file
                    if filename == self.metadata_key:
                        continue
                    
                    # Get object metadata (tags or user metadata)
                    try:
                        obj_response = self.s3_client.head_object(
                            Bucket=self.bucket_name,
                            Key=filename
                        )
                        # Check for upload date in object metadata
                        upload_date = obj_response.get('Metadata', {}).get('upload_date')
                        if upload_date:
                            metadata[filename] = {'upload_date': upload_date}
                    except ClientError:
                        # Object might have been deleted, skip
                        continue
            
            return metadata
        except ClientError as e:
            logger.error(f"Error loading metadata from S3: {e}")
            return {}
    
    def save_metadata(self, metadata: Dict[str, Dict], etag: Optional[str] = None) -> bool:
        """Save file metadata to S3 (deprecated - metadata now stored per-object)."""
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
            # List objects from S3
            response = self.s3_client.list_objects_v2(Bucket=self.bucket_name)
            
            if 'Contents' in response:
                for obj in response['Contents']:
                    filename = obj['Key']
                    
                    # Skip metadata file
                    if filename == self.metadata_key:
                        continue
                    
                    # Search filter - only filter if search_query is not empty
                    if search_query_lower and search_query_lower not in filename.lower():
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
        except ClientError as e:
            logger.error(f"Error listing files from S3: {e}")
        
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
            max_mb = Config.MAX_FILE_SIZE / (1024 * 1024)
            return False, f'File too large. Maximum size is {max_mb:.0f}MB', None

        return True, '', sanitized_name

    def upload_file(self, file: FileStorage) -> Tuple[bool, str]:
        """Upload a file to S3 with upload date as object metadata."""
        try:
            if not file or file.filename == '':
                return False, 'No file selected'
            
            filename = secure_filename(file.filename)
            upload_date = self._current_iso_timestamp()
            
            # Upload file to S3 with metadata
            self.s3_client.upload_fileobj(
                file,
                self.bucket_name,
                filename,
                ExtraArgs={
                    'ContentType': file.content_type,
                    'Metadata': {
                        'upload_date': upload_date
                    }
                }
            )
            logger.info(f"File uploaded successfully to S3 with metadata: {filename}")
            
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
        filename = secure_filename(filename)
        try:
            self.s3_client.head_object(Bucket=self.bucket_name, Key=filename)
            return True
        except ClientError:
            return False
    
    def download_file(self, filename: str) -> Tuple[bool, Optional[Any], str]:
        """Download a file from S3 and return the file stream and content type."""
        filename = secure_filename(filename)
        try:
            response = self.s3_client.get_object(
                Bucket=self.bucket_name,
                Key=filename
            )
            file_stream = response['Body']
            content_type = response.get('ContentType', 'application/octet-stream')
            logger.info(f'File downloaded from S3: {filename}')
            return True, file_stream, content_type
        except ClientError as e:
            logger.error(f'Error downloading from S3: {e}')
            return False, None, str(e)
    
    def delete_file(self, filename: str) -> Tuple[bool, str]:
        """Delete a file from S3 (metadata is automatically removed with the file)."""
        try:
            filename = secure_filename(filename)
            
            if not self.file_exists(filename):
                return False, 'File not found'
            
            # Delete file from S3 (metadata is stored with the file, so it's removed automatically)
            self.s3_client.delete_object(Bucket=self.bucket_name, Key=filename)
            logger.info(f"File deleted successfully from S3: {filename}")
            
            return True, f'File "{filename}" deleted successfully'
            
        except ClientError as e:
            logger.error(f"Error deleting file from S3: {e}")
            return False, f'Error deleting file from S3: {str(e)}'
        except Exception as e:
            logger.error(f"Error deleting file: {e}")
            return False, f'Error deleting file: {str(e)}'
    
    def generate_presigned_url(
        self,
        filename: str,
        content_type: Optional[str] = None,
        upload_date: Optional[str] = None,
        expiration: Optional[int] = None
    ) -> Tuple[bool, Optional[str], Optional[Dict[str, str]], Optional[str]]:
        """Generate a presigned URL and headers for uploading a file directly to S3."""
        try:
            sanitized_name = secure_filename(filename)
            normalized_content_type = content_type or 'application/octet-stream'
            timestamp = upload_date or self._current_iso_timestamp()

            presigned_url = self.s3_client.generate_presigned_url(
                'put_object',
                Params={
                    'Bucket': self.bucket_name,
                    'Key': sanitized_name,
                    'ContentType': normalized_content_type,
                    'Metadata': {
                        'upload_date': timestamp
                    }
                },
                ExpiresIn=expiration or Config.PRESIGNED_URL_EXPIRATION
            )

            headers = {
                'Content-Type': normalized_content_type,
                'x-amz-meta-upload_date': timestamp
            }

            logger.info(f"Generated presigned URL for: {sanitized_name}")
            return True, presigned_url, headers, sanitized_name

        except ClientError as e:
            logger.error(f"Error generating presigned URL: {e}")
            return False, None, None, None
        except Exception as e:
            logger.error(f"Error generating presigned URL: {e}")
            return False, None, None, None
    
    def configure_cors(self, allowed_origins: List[str] = None) -> Tuple[bool, str]:
        """Configure CORS policy for the S3 bucket to allow cross-origin requests."""
        if allowed_origins is None:
            allowed_origins = ['*']  # Allow all origins by default
        
        cors_configuration = {
            'CORSRules': [
                {
                    'AllowedHeaders': ['*'],
                    'AllowedMethods': ['PUT', 'POST', 'GET', 'DELETE', 'HEAD', 'OPTIONS'],
                    'AllowedOrigins': allowed_origins,
                    'ExposeHeaders': ['ETag'],
                    'MaxAgeSeconds': 3600
                }
            ]
        }
        
        try:
            # Try standard S3 CORS configuration first
            self.s3_client.put_bucket_cors(
                Bucket=self.bucket_name,
                CORSConfiguration=cors_configuration
            )
            logger.info(f"CORS configuration updated for bucket: {self.bucket_name}")
            return True, 'CORS configuration updated successfully'
        except ClientError as e:
            # If standard CORS fails, bucket might be S3 Express One Zone which doesn't support CORS the same way
            logger.error(f"Error configuring CORS (bucket might be S3 Express One Zone): {e}")
            return False, f'CORS not supported by this bucket type. Use backend proxy instead.'
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
