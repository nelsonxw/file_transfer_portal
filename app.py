import logging
from functools import wraps
from flask import Flask, render_template, request, redirect, url_for, session, send_file, flash

from config import Config
from services import FileService, AuthService

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

app = Flask(__name__)
Config.init_app(app)

# Initialize services
file_service = FileService(app.root_path)
auth_service = AuthService()

def login_required(f):
    """Decorator to require login for routes."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'logged_in' not in session:
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

@app.route('/')
def index():
    if 'logged_in' in session:
        return redirect(url_for('dashboard'))
    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
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
def logout():
    session.clear()
    return redirect(url_for('login'))

@app.route('/dashboard')
@login_required
def dashboard():
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

@app.route('/upload', methods=['POST'])
@login_required
def upload_file():
    """Handle file upload."""
    if 'file' not in request.files:
        flash('No file selected', 'error')
        return redirect(url_for('dashboard'))
    
    file = request.files['file']
    success, message = file_service.upload_file(file)
    
    if success:
        flash(message, 'success')
    else:
        flash(message, 'error')
    
    return redirect(url_for('dashboard'))

@app.route('/download/<filename>')
@login_required
def download_file(filename):
    """Handle file download."""
    file_path = file_service.get_file_path(filename)
    
    if file_path:
        logger.info(f'File downloaded: {filename}')
        return send_file(file_path, as_attachment=True)
    else:
        flash('File not found', 'error')
        return redirect(url_for('dashboard'))

@app.route('/delete/<filename>')
@login_required
def delete_file(filename):
    """Handle file deletion."""
    success, message = file_service.delete_file(filename)
    
    if success:
        flash(message, 'success')
    else:
        flash(message, 'error')
    
    return redirect(url_for('dashboard'))

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
