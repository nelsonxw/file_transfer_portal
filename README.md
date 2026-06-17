# File Manager

A secure web application for uploading and downloading files with password protection.

## Features

- **Password Authentication**: Secure login using bcrypt password hashing
- **File Upload**: Upload files with size limit (16MB) and type restrictions
- **File Download**: Download uploaded files securely
- **File Management**: View, download, and delete files
- **Modern UI**: Clean, responsive interface with gradient design

## Supported File Types

txt, pdf, png, jpg, jpeg, gif, doc, docx, xls, xlsx, zip, rar

## Installation

1. Install Python 3.8 or higher
2. Install dependencies:
```bash
pip install -r requirements.txt
```

## Usage

1. Run the application:
```bash
python app.py
```

2. Open your browser and navigate to `http://localhost:5000`

3. Login with the default password:
- **Default Password**: `admin123`

## Security

- Passwords are hashed using bcrypt
- Session-based authentication
- File type validation
- File size limits (16MB)
- Secure filename handling with `secure_filename`

## Configuration

You can modify the following settings in `app.py`:

- `UPLOAD_FOLDER`: Directory for uploaded files (default: 'uploads')
- `ALLOWED_EXTENSIONS`: Set of allowed file extensions
- `MAX_FILE_SIZE`: Maximum file size in bytes (default: 16MB)
- `DEFAULT_PASSWORD_HASH`: Change the default password by modifying the hash

To change the default password, replace the hash in `app.py`:
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
├── requirements.txt    # Python dependencies
├── uploads/           # Directory for uploaded files
├── templates/         # HTML templates
│   ├── login.html     # Login page
│   └── dashboard.html # File management dashboard
└── README.md          # This file
```

## License

MIT License
