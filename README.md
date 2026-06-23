# File Manager

A secure web application for uploading and downloading files with password protection. Files are stored in AWS S3.

## Features

- **Password Authentication**: Secure login using bcrypt password hashing
- **File Upload**: Upload files with size limit (100MB) and type restrictions
- **Direct-to-S3 Uploads**: Browser uploads files straight to S3 via presigned URLs (works inside Vercel's 4.5MB body limit)
- **File Download**: Download uploaded files securely from S3
- **File Management**: View, download, and delete files stored in S3
- **Modern UI**: Clean, responsive interface with gradient design
- **AWS S3 Storage**: All files are stored in AWS S3 for scalable cloud storage

## Supported File Types

any file type is supported

## Installation

1. Install Python 3.8 or higher
2. Install dependencies:
```bash
pip install -r requirements.txt
```

## AWS S3 Setup

Before running the application, you need to set up AWS S3:

1. **Create an S3 Bucket**:
   - Go to the AWS Console and create a new S3 bucket
   - Note the bucket name

2. **Create AWS Credentials**:
   - Create an IAM user with S3 access permissions
   - Generate Access Key ID and Secret Access Key
   - The IAM user needs the following permissions:
     ```json
     {
       "Version": "2012-10-17",
       "Statement": [
         {
           "Effect": "Allow",
           "Action": [
             "s3:PutObject",
             "s3:GetObject",
             "s3:DeleteObject",
             "s3:ListBucket"
           ],
           "Resource": [
             "arn:aws:s3:::your-bucket-name",
             "arn:aws:s3:::your-bucket-name/*"
           ]
         }
       ]
     }
     ```

3. **Set Environment Variables**:
   Set the following environment variables before running the application:
   ```bash
   export AWS_ACCESS_KEY_ID=your_access_key_id
   export AWS_SECRET_ACCESS_KEY=your_secret_access_key
   export AWS_REGION=us-east-1
   export S3_BUCKET_NAME=your_bucket_name
   ```
   
   On Windows:
   ```cmd
   set AWS_ACCESS_KEY_ID=your_access_key_id
   set AWS_SECRET_ACCESS_KEY=your_secret_access_key
   set AWS_REGION=us-east-1
   set S3_BUCKET_NAME=your_bucket_name
   ```

## Usage

1. Run the application:
```bash
python app.py
```

2. Open your browser and navigate to `http://localhost:5000`

3. Login with the default password:
- **Default Password**: `admin123`

### Deploying on Vercel / Handling 4.5MB Limits

Vercel limits incoming request bodies for serverless functions to ~4.5MB. To keep using Vercel while supporting large files:

1. **Direct Upload Flow**: The dashboard now requests a presigned URL from `/api/presigned-url` and streams the file directly from the browser to S3. No large files hit the Flask endpoint, so the Vercel limit is never triggered.
2. **CORS for Your Bucket**: Allow your Vercel domain (e.g., `https://your-app.vercel.app`) to perform `PUT` requests. Example policy:
   ```json
   {
     "CORSRules": [
       {
         "AllowedHeaders": ["*"],
         "AllowedMethods": ["GET", "PUT", "HEAD"],
         "AllowedOrigins": ["https://your-app.vercel.app"],
         "ExposeHeaders": ["ETag"],
         "MaxAgeSeconds": 3600
       }
     ]
   }
   ```
   You can configure this manually in S3 or by calling the `/api/configure-cors` endpoint with your allowed origins.
3. **Environment Variable**: Optionally adjust `PRESIGNED_URL_EXPIRATION` (default 15 minutes) to control how long each upload URL remains valid.

## Security

- Passwords are hashed using bcrypt
- Session-based authentication
- File type validation
- File size limits (100MB)
- Secure filename handling with `secure_filename`
- AWS S3 provides secure, scalable cloud storage

## Configuration

You can modify the following settings in `config.py`:

- `AWS_ACCESS_KEY_ID`: AWS access key ID (or set via environment variable)
- `AWS_SECRET_ACCESS_KEY`: AWS secret access key (or set via environment variable)
- `AWS_REGION`: AWS region (default: 'us-east-1')
- `S3_BUCKET_NAME`: S3 bucket name (or set via environment variable)
- `MAX_FILE_SIZE`: Maximum file size in bytes (default: 100MB)
- `PRESIGNED_URL_EXPIRATION`: Seconds before a presigned upload URL expires (default: 900)
- `DEFAULT_PASSWORD_HASH`: Change the default password by modifying the hash

To change the default password, replace the hash in `config.py`:
```python
# Generate a new hash using:
import bcrypt
new_hash = bcrypt.hashpw('your_new_password'.encode('utf-8'), bcrypt.gensalt())
print(new_hash)
```

## Project Structure

```
file-manager/
├── app.py              # Main Flask application
├── config.py           # Configuration settings
├── services.py         # File and authentication services
├── requirements.txt    # Python dependencies
├── templates/         # HTML templates
│   ├── login.html     # Login page
│   └── dashboard.html # File management dashboard
└── README.md          # This file
```

## Migration from Local Storage

This application has been migrated from local file storage to AWS S3. If you have existing files in the local `uploads/` directory, you can migrate them to S3 using the AWS CLI:

```bash
aws s3 sync uploads/ s3://your-bucket-name/
```

## License

MIT License
