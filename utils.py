import os
import secrets
from werkzeug.utils import secure_filename
try:
    from PIL import Image
    PILLOW_AVAILABLE = True
except ImportError:
    PILLOW_AVAILABLE = False
from models import AuditLog, db
from functools import wraps
from flask import flash, redirect, url_for
from flask_login import current_user

try:
    import markdown
    import bleach
    MARKDOWN_AVAILABLE = True
except ImportError:
    MARKDOWN_AVAILABLE = False

def allowed_file(filename, allowed_extensions=None):
    """Check if file extension is allowed"""
    if allowed_extensions is None:
        # Try to get from database settings
        try:
            from models import Setting
            extensions_str = Setting.get('allowed_extensions', 'pdf,png,jpg,jpeg,gif,txt,doc,docx')
            allowed_extensions = set(ext.strip().lower() for ext in extensions_str.split(',') if ext.strip())
        except:
            # Fallback to default if database not available
            allowed_extensions = {'pdf', 'png', 'jpg', 'jpeg', 'gif', 'txt', 'doc', 'docx'}
    
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in allowed_extensions


def save_file(file, upload_folder, item_uuid):
    """Save uploaded file organized by item UUID"""
    if file and file.filename:
        filename = secure_filename(file.filename)
        ext = filename.rsplit('.', 1)[1].lower() if '.' in filename else ''
        
        # Create item-specific folder: uploads/UUID/
        item_folder = os.path.join(upload_folder, item_uuid)
        os.makedirs(item_folder, exist_ok=True)
        
        # Keep original filename
        file_path = os.path.join(item_folder, filename)
        
        # If file exists, add number suffix
        counter = 1
        base_name = filename.rsplit('.', 1)[0] if '.' in filename else filename
        while os.path.exists(file_path):
            new_filename = f"{base_name}_{counter}.{ext}"
            file_path = os.path.join(item_folder, new_filename)
            filename = new_filename
            counter += 1
        
        # Save file
        file.save(file_path)
        
        # Get file size
        file_size = os.path.getsize(file_path)
        
        return {
            'filename': f"{item_uuid}/{filename}",  # Store relative path
            'original_filename': secure_filename(file.filename),
            'file_path': file_path,
            'file_type': ext,
            'file_size': file_size
        }
    return None


def create_thumbnail(image_path, thumbnail_path, size=(200, 200)):
    """Create a thumbnail for images"""
    if not PILLOW_AVAILABLE:
        return False
    try:
        with Image.open(image_path) as img:
            img.thumbnail(size)
            img.save(thumbnail_path)
            return True
    except Exception as e:
        print(f"Error creating thumbnail: {e}")
        return False


def log_audit(user_id, action, entity_type, entity_id, details=None):
    """Create an audit log entry"""
    try:
        log = AuditLog(
            user_id=user_id,
            action=action,
            entity_type=entity_type,
            entity_id=entity_id,
            details=details
        )
        db.session.add(log)
        db.session.commit()
    except Exception as e:
        print(f"Error creating audit log: {e}")


def admin_required(f):
    """Decorator to require admin role"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated or not current_user.is_admin():
            flash('You need admin privileges to access this page.', 'danger')
            return redirect(url_for('index'))
        return f(*args, **kwargs)
    return decorated_function


def permission_required(resource, action):
    """Decorator to check specific permission"""
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if not current_user.is_authenticated:
                flash('Please log in to access this page.', 'danger')
                return redirect(url_for('login'))
            if not current_user.has_permission(resource, action):
                flash(f'You do not have permission to {action} {resource}.', 'danger')
                return redirect(url_for('index'))
            return f(*args, **kwargs)
        return decorated_function
    return decorator


def item_permission_required(f):
    """Decorator to check if user can edit items (any granular item edit permission)"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated:
            flash('Please log in to access this page.', 'danger')
            return redirect(url_for('login'))
        
        # Check if user has view permission first
        if not current_user.has_permission('items', 'view'):
            flash('You do not have permission to view items.', 'danger')
            return redirect(url_for('index'))
        
        # Check if user has ANY item edit permission (not just 'edit')
        has_any_edit_perm = any([
            current_user.has_permission('items', action) 
            for action in ['create', 'edit_name', 'edit_data', 'edit_price', 'edit_quantity', 'edit_location', 'edit_classification', 'edit_parameters', 'delete']
        ])
        
        if not has_any_edit_perm:
            flash('You do not have permission to edit items.', 'danger')
            return redirect(url_for('index'))
        
        return f(*args, **kwargs)
    return decorated_function


def format_file_size(size_bytes):
    """Format file size in human readable format"""
    for unit in ['B', 'KB', 'MB', 'GB']:
        if size_bytes < 1024.0:
            return f"{size_bytes:.1f} {unit}"
        size_bytes /= 1024.0
    return f"{size_bytes:.1f} TB"


def markdown_to_html(text):
    """Convert markdown text to safe HTML"""
    if not text:
        return ''
    
    if not MARKDOWN_AVAILABLE:
        # If markdown not available, just escape and convert line breaks
        from markupsafe import escape
        return escape(text).replace('\n', '<br>')
    
    try:
        # Convert markdown to HTML
        html = markdown.markdown(
            text,
            extensions=['tables', 'fenced_code', 'codehilite', 'nl2br'],
            extension_configs={
                'codehilite': {'css_class': 'highlight'}
            }
        )
        
        # Sanitize HTML - allow safe tags
        allowed_tags = [
            'p', 'br', 'strong', 'em', 'u', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6',
            'ul', 'ol', 'li', 'blockquote', 'code', 'pre', 'hr', 'table', 
            'thead', 'tbody', 'tr', 'th', 'td', 'a', 'img'
        ]
        allowed_attributes = {
            'a': ['href', 'title'],
            'img': ['src', 'alt', 'title'],
            'code': ['class'],
            'pre': ['class']
        }
        
        safe_html = bleach.clean(html, tags=allowed_tags, attributes=allowed_attributes)
        return safe_html
    except (ValueError, TypeError):
        # Fallback if markdown parsing fails
        from markupsafe import escape
        return escape(text).replace('\n', '<br>')
