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

# Extensions that are blocked unconditionally because they can reconfigure the web server
# or be executed server-side by the HTTP daemon (not by Python). .py/.exe/.sh are fine to
# store as data — they are served as downloads by Flask, never executed.
DANGEROUS_EXTENSIONS = {'htaccess', 'htpasswd'}

# Maps file extensions to their expected magic-byte signatures (first N bytes).
# Used to detect MIME spoofing (e.g. a PHP script renamed to .jpg).
_MAGIC_SIGNATURES: dict[str, list[bytes]] = {
    'jpg':  [b'\xff\xd8\xff'],
    'jpeg': [b'\xff\xd8\xff'],
    'png':  [b'\x89PNG\r\n\x1a\n'],
    'gif':  [b'GIF87a', b'GIF89a'],
    'webp': [b'RIFF'],
    'pdf':  [b'%PDF'],
    'bmp':  [b'BM'],
    'ico':  [b'\x00\x00\x01\x00'],
}

# Extensions where the actual content is binary-executable; detecting these in an
# uploaded file that claims to be a document type (e.g. .docx) is suspicious.
_EXECUTABLE_MAGIC: list[bytes] = [
    b'MZ',           # PE/EXE/DLL
    b'\x7fELF',      # ELF (Linux binary)
    b'\xca\xfe\xba\xbe',  # Mach-O fat binary
    b'\xfe\xed\xfa\xce', b'\xce\xfa\xed\xfe',  # Mach-O 32/64
]


def validate_mime_type(file_obj, declared_ext: str) -> tuple[bool, str]:
    """
    Validate that a file's actual content matches its declared extension.
    Returns (is_valid, reason_string).

    Rules:
    - If declared_ext is an image type, verify with PIL (most reliable).
    - If declared_ext has a known magic signature, verify bytes match.
    - Reject any file whose first bytes are an executable signature when the
      declared extension is a document/media type.
    - Files with no known signature (e.g. .txt, .csv, .py, .exe) are passed
      through — they are served as downloads, never executed server-side.
    """
    ext = declared_ext.lower()

    try:
        header = file_obj.read(16)
        file_obj.seek(0)
    except Exception:
        return False, 'Could not read file header'

    # Image validation via PIL — catches corrupt and spoofed images.
    image_exts = {'jpg', 'jpeg', 'png', 'gif', 'bmp', 'webp', 'tiff', 'tif'}
    if ext in image_exts:
        if not PILLOW_AVAILABLE:
            return True, 'PIL not available, skipping image validation'
        try:
            from PIL import Image
            import io
            file_obj.seek(0)
            raw = file_obj.read()
            file_obj.seek(0)
            img = Image.open(io.BytesIO(raw))
            img.verify()
            return True, 'ok'
        except Exception as e:
            return False, f'File is not a valid image: {e}'

    # Magic-byte check for known binary formats (PDF, etc.)
    if ext in _MAGIC_SIGNATURES:
        for sig in _MAGIC_SIGNATURES[ext]:
            if header[:len(sig)] == sig:
                return True, 'ok'
        return False, f'File content does not match declared type .{ext}'

    # Reject executable binaries masquerading as document/media types.
    # (Allow them when the extension itself is an executable type — stored as data.)
    binary_declared = ext in {'exe', 'dll', 'so', 'bin', 'elf', 'dmg', 'app'}
    if not binary_declared:
        for sig in _EXECUTABLE_MAGIC:
            if header[:len(sig)] == sig:
                return False, (
                    f'File appears to be a binary executable but is declared as .{ext}. '
                    'Upload the file with its correct extension.'
                )

    return True, 'ok'


def allowed_file(filename, allowed_extensions=None):
    """Check if file extension is allowed - respects DEMO_MODE setting"""
    from flask import current_app

    if '.' not in filename:
        return False

    ext = filename.rsplit('.', 1)[1].lower()

    # Block web-server config overrides unconditionally.
    if ext in DANGEROUS_EXTENSIONS:
        return False

    # Check if demo mode is enabled via app config
    demo_mode_enabled = current_app.config.get('DEMO_MODE', False)

    if demo_mode_enabled:
        # DEMO MODE: Use hardcoded whitelist only
        allowed_extensions = {'jpg', 'jpeg', 'png', 'txt', 'md'}
    elif allowed_extensions is None:
        # Non-demo mode: Try to get from database settings
        try:
            from models import Setting
            extensions_str = Setting.get('allowed_extensions', 'pdf,png,jpg,jpeg,gif,txt,doc,docx')
            allowed_extensions = set(e.strip().lower() for e in extensions_str.split(',') if e.strip())
        except Exception:
            allowed_extensions = {'pdf', 'png', 'jpg', 'jpeg', 'gif', 'txt', 'doc', 'docx'}

    return ext in allowed_extensions


def save_file(file, upload_folder, item_uuid):
    """Save uploaded file organized by item UUID - respects DEMO_MODE"""
    from flask import current_app
    
    if file and file.filename:
        # Check if demo mode is enabled
        demo_mode_enabled = current_app.config.get('DEMO_MODE', False)
        
        # In demo mode, enforce 1MB max file size
        if demo_mode_enabled:
            DEMO_MODE_MAX_SIZE = 1 * 1024 * 1024  # 1 MB in bytes
            file.seek(0, os.SEEK_END)  # Seek to end to get size
            file_size = file.tell()
            file.seek(0)  # Reset to beginning for actual save
            
            if file_size > DEMO_MODE_MAX_SIZE:
                return None  # File too large - will be caught by upload handler
        
        filename = secure_filename(file.filename)
        ext = filename.rsplit('.', 1)[1].lower() if '.' in filename else ''
        
        # Create item-specific folder: uploads/items/UUID/
        item_folder = os.path.join(upload_folder, 'items', item_uuid)
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
            'filename': f"items/{item_uuid}/{filename}",  # Store relative path
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
    """Decorator to require user/role management permission"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated or not current_user.has_permission('settings_sections.users_roles', 'view'):
            flash('Permission denied.', 'danger')
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
            for action in ['create', 'delete', 'edit_info', 'create_batch',
                           'edit_advance', 'delete_advance']
        ]) or any([
            current_user.has_permission('lending_return', action)
            for action in ['edit_batch', 'edit_lending', 'delete_batch', 'delete_lending']
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
            'thead', 'tbody', 'tr', 'th', 'td', 'a',
            # img intentionally excluded — external src allows IP tracking / script injection
        ]
        allowed_attributes = {
            'a': ['href', 'title'],
            'code': ['class'],
            'pre': ['class']
        }
        
        safe_html = bleach.clean(html, tags=allowed_tags, attributes=allowed_attributes)
        return safe_html
    except (ValueError, TypeError):
        # Fallback if markdown parsing fails
        from markupsafe import escape
        return escape(text).replace('\n', '<br>')


def get_item_edit_permissions(user):
    """Get item permissions from the role's permission matrix."""
    p  = lambda res, act: user.has_permission(res, act)
    lr = lambda perm: p('lending_return', perm)

    can_edit_batch = lr('edit_batch')

    return {
        'can_view':              p('items', 'view'),
        'can_create':            p('items', 'create'),
        'can_delete':            p('items', 'delete'),
        'can_view_info':         p('items', 'view_info'),
        'can_edit_info':         p('items', 'edit_info'),
        'can_view_batch':        p('items', 'view_info'),
        'can_create_batch':      p('items', 'create_batch') or can_edit_batch,
        'can_edit_batch':        can_edit_batch,
        'can_edit_quantity':     can_edit_batch,
        'can_edit_price':        can_edit_batch,
        'can_edit_sn':           can_edit_batch,
        'can_edit_lending':      lr('edit_lending'),
        'can_only_self_lending': p('lending_return', 'only_self_lending') and not can_edit_batch,
        'can_delete_batch':      lr('delete_batch'),
        'can_delete_lending':    lr('delete_lending'),
        'can_view_advance':      p('items', 'view_advance'),
        'can_edit_advance':      p('items', 'edit_advance'),
        'can_delete_advance':    p('items', 'delete_advance'),
        'can_view_lr_page':      lr('view_page'),
        'can_view_lr_log':       lr('view_log'),
    }

