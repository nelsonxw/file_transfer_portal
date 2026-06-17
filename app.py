import os
import secrets
import json
from datetime import datetime
from flask import Flask, render_template, request, redirect, url_for, session, send_file, flash
from werkzeug.utils import secure_filename
from werkzeug.exceptions import RequestEntityTooLarge
from functools import wraps
import bcrypt

app = Flask(__name__)
app.secret_key = secrets.token_hex(32)

# Configuration
UPLOAD_FOLDER = 'uploads'
METADATA_FILE = 'file_metadata.json'
MAX_FILE_SIZE = 100 * 1024 * 1024  # 100 MB

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = MAX_FILE_SIZE

# Default password (hashed)
# Default password is "admin123"
DEFAULT_PASSWORD_HASH = bcrypt.hashpw('admin123'.encode('utf-8'), bcrypt.gensalt())

def load_metadata():
    metadata_path = os.path.join(app.root_path, METADATA_FILE)
    if os.path.exists(metadata_path):
        with open(metadata_path, 'r') as f:
            return json.load(f)
    return {}

def save_metadata(metadata):
    metadata_path = os.path.join(app.root_path, METADATA_FILE)
    with open(metadata_path, 'w') as f:
        json.dump(metadata, f, indent=2)

def get_file_extension(filename):
    return filename.rsplit('.', 1)[1].lower() if '.' in filename else ''

def login_required(f):
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
    if request.method == 'POST':
        password = request.form.get('password')
        if password and bcrypt.checkpw(password.encode('utf-8'), DEFAULT_PASSWORD_HASH):
            session['logged_in'] = True
            return redirect(url_for('dashboard'))
        else:
            flash('Invalid password', 'error')
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

@app.route('/dashboard')
@login_required
def dashboard():
    search_query = request.args.get('search', '').lower()
    sort_by = request.args.get('sort', 'name')
    sort_order = request.args.get('order', 'asc')
    
    files = []
    upload_folder = os.path.join(app.root_path, app.config['UPLOAD_FOLDER'])
    metadata = load_metadata()
    
    if os.path.exists(upload_folder):
        file_list = os.listdir(upload_folder)
        for filename in file_list:
            file_path = os.path.join(upload_folder, filename)
            file_size = os.path.getsize(file_path)
            file_ext = get_file_extension(filename)
            upload_date = metadata.get(filename, {}).get('upload_date', '')
            
            # Search filter
            if search_query and search_query not in filename.lower():
                continue
            
            files.append({
                'name': filename,
                'size': file_size,
                'extension': file_ext,
                'upload_date': upload_date
            })
        
        # Sort files
        if sort_by == 'name':
            files.sort(key=lambda x: x['name'], reverse=(sort_order == 'desc'))
        elif sort_by == 'size':
            files.sort(key=lambda x: x['size'], reverse=(sort_order == 'desc'))
        elif sort_by == 'type':
            files.sort(key=lambda x: x['extension'], reverse=(sort_order == 'desc'))
        elif sort_by == 'date':
            files.sort(key=lambda x: x['upload_date'] or '', reverse=(sort_order == 'desc'))
    
    return render_template('dashboard.html', files=files, search_query=search_query, sort_by=sort_by, sort_order=sort_order)

@app.route('/upload', methods=['POST'])
@login_required
def upload_file():
    try:
        if 'file' not in request.files:
            flash('No file selected', 'error')
            return redirect(url_for('dashboard'))
        
        file = request.files['file']
        if file.filename == '':
            flash('No file selected', 'error')
            return redirect(url_for('dashboard'))
        
        if file:
            filename = secure_filename(file.filename)
            upload_folder = os.path.join(app.root_path, app.config['UPLOAD_FOLDER'])
            os.makedirs(upload_folder, exist_ok=True)
            file.save(os.path.join(upload_folder, filename))
            
            # Save metadata
            metadata = load_metadata()
            metadata[filename] = {
                'upload_date': datetime.now().isoformat()
            }
            save_metadata(metadata)
            
            flash(f'File "{filename}" uploaded successfully', 'success')
        
        return redirect(url_for('dashboard'))
    except RequestEntityTooLarge:
        flash(f'File too large. Maximum size is {MAX_FILE_SIZE / (1024*1024):.0f}MB', 'error')
        return redirect(url_for('dashboard'))

@app.route('/download/<filename>')
@login_required
def download_file(filename):
    filename = secure_filename(filename)
    upload_folder = os.path.join(app.root_path, app.config['UPLOAD_FOLDER'])
    file_path = os.path.join(upload_folder, filename)
    
    if os.path.exists(file_path):
        return send_file(file_path, as_attachment=True)
    else:
        flash('File not found', 'error')
        return redirect(url_for('dashboard'))

@app.route('/delete/<filename>')
@login_required
def delete_file(filename):
    filename = secure_filename(filename)
    upload_folder = os.path.join(app.root_path, app.config['UPLOAD_FOLDER'])
    file_path = os.path.join(upload_folder, filename)
    
    if os.path.exists(file_path):
        os.remove(file_path)
        # Remove metadata
        metadata = load_metadata()
        if filename in metadata:
            del metadata[filename]
            save_metadata(metadata)
        flash(f'File "{filename}" deleted successfully', 'success')
    else:
        flash('File not found', 'error')
    
    return redirect(url_for('dashboard'))

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
