import logging
from typing import Callable
from functools import wraps
from flask import Flask, render_template, request, redirect, url_for, session, send_file, flash, Response, jsonify
from werkzeug.utils import secure_filename
from werkzeug.exceptions import RequestEntityTooLarge
from botocore.exceptions import ClientError

from config import Config, setup_logging
from services import FileService, AuthService

# Configure logging
setup_logging()
logger = logging.getLogger(__name__)

app = Flask(__name__)
Config.init_app(app)
# Ensure MAX_CONTENT_LENGTH is set (already set by Config.init_app but ensuring it)
app.config['MAX_CONTENT_LENGTH'] = Config.MAX_FILE_SIZE
logger.info(f"MAX_CONTENT_LENGTH configured: {app.config['MAX_CONTENT_LENGTH']} bytes ({app.config['MAX_CONTENT_LENGTH'] / (1024*1024)} MB)")

# Initialize services
file_service = FileService(app.root_path)
auth_service = AuthService()

def login_required(f: Callable) -> Callable:
    """Decorator to require login for routes."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'logged_in' not in session:
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

@app.route('/')
def index() -> Response:
    if 'logged_in' in session:
        return redirect(url_for('dashboard'))
    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login() -> Response:
    """Handle user login."""
    if request.method == 'POST':
        password = request.form.get('password')
        if password and auth_service.verify_password(password):
            session['logged_in'] = True
            logger.info('User logged in successfully')
            return redirect(url_for('dashboard'))
        else:
            flash('Invalid password', 'error')
            logger.warning('Failed login attempt')
    return render_template('login.html')

@app.route('/logout')
def logout() -> Response:
    session.clear()
    return redirect(url_for('login'))

@app.route('/favicon.ico')
def favicon():
    """Return empty response for favicon request to avoid 404 errors."""
    return '', 204

@app.route('/favicon.png')
def favicon_png():
    """Return empty response for favicon request to avoid 404 errors."""
    return '', 204

@app.route('/dashboard')
@login_required
def dashboard() -> str:
    """Display file dashboard with search and sorting."""
    search_query = request.args.get('search', '')
    sort_by = request.args.get('sort', 'name')
    sort_order = request.args.get('order', 'asc')
    
    files = file_service.list_files(search_query, sort_by, sort_order)
    
    return render_template(
        'dashboard.html',
        files=files,
        search_query=search_query,
        sort_by=sort_by,
        sort_order=sort_order
    )


# API Routes
@app.route('/api/files')
@login_required
def api_files() -> Response:
    """API endpoint to return file list as JSON."""
    search_query = request.args.get('search', '')
    sort_by = request.args.get('sort', 'name')
    sort_order = request.args.get('order', 'asc')
    
    files = file_service.list_files(search_query, sort_by, sort_order)
    
    return jsonify({'files': files})

@app.route('/api/presigned-url', methods=['POST'])
@login_required
def get_presigned_url() -> Response:
    """API endpoint to generate presigned URL for direct S3 upload."""
    filename = request.json.get('filename')
    if not filename:
        return jsonify({'error': 'Filename is required'}), 400
    
    success, url = file_service.generate_presigned_url(filename)
    if success and url:
        return jsonify({'url': url})
    else:
        return jsonify({'error': 'Failed to generate presigned URL'}), 500

@app.route('/upload', methods=['POST'])
@login_required
def upload_file() -> Response:
    """Handle file upload."""
    try:
        logger.info(f"Upload request received. Content-Length: {request.content_length if 'Content-Length' in request.headers else 'unknown'}")
        
        if 'file' not in request.files:
            flash('No file selected', 'error')
            return redirect(url_for('dashboard'))
        
        file = request.files['file']
        logger.info(f"File received: {file.filename}, size: {file.content_length if hasattr(file, 'content_length') else 'unknown'}")
        
        success, message = file_service.upload_file(file)
        
        if success:
            flash(message, 'success')
        else:
            flash(message, 'error')
        
        return redirect(url_for('dashboard'))
    except RequestEntityTooLarge as e:
        logger.error(f"RequestEntityTooLarge exception: {e}")
        flash('File too large. Maximum size is 500MB.', 'error')
        return redirect(url_for('dashboard'))
    except Exception as e:
        logger.error(f"Unexpected error during upload: {e}")
        flash(f'Upload failed: {str(e)}', 'error')
        return redirect(url_for('dashboard'))

@app.route('/download/<filename>')
@login_required
def download_file(filename: str) -> Response:
    """Handle file download from S3."""
    filename = secure_filename(filename)
    
    if not file_service.file_exists(filename):
        flash('File not found', 'error')
        return redirect(url_for('dashboard'))
    
    success, file_stream, content_type = file_service.download_file(filename)
    
    if success and file_stream:
        return send_file(
            file_stream,
            as_attachment=True,
            download_name=filename,
            mimetype=content_type
        )
    else:
        flash('Error downloading file', 'error')
        return redirect(url_for('dashboard'))

@app.route('/delete/<filename>')
@login_required
def delete_file(filename: str) -> Response:
    """Handle file deletion."""
    success, message = file_service.delete_file(filename)
    
    if success:
        flash(message, 'success')
    else:
        flash(message, 'error')
    
    return redirect(url_for('dashboard'))

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
