"""
Inventory Manager Application - Main Entry Point
"""
from flask import Flask, render_template, request, send_from_directory, jsonify, url_for, abort
from flask_login import LoginManager, current_user, AnonymousUserMixin, login_required
from extensions import csrf, limiter
from config import Config
from models import db, User, Category, Item, Setting
from helpers import filesize_filter, jinja_format_amount, markdown_filter
import os
import json
import logging

# Initialize Flask app
app = Flask(__name__)
app.config.from_object(Config)

# Initialize database
db.init_app(app)

# Initialize shared extensions
csrf.init_app(app)
limiter.init_app(app)


# Custom Anonymous User with permission methods
class AnonymousUser(AnonymousUserMixin):
    """Anonymous user with permission checks that always return False"""
    
    def has_permission(self, resource, action):
        """Anonymous users have no permissions"""
        return False
    
    @property
    def theme(self):
        """Default theme for anonymous users"""
        return 'light'
    
    @property
    def user_font(self):
        """Default font for anonymous users"""
        return 'system'


# Initialize Flask-Login
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'auth.login'
login_manager.login_message = ''
login_manager.anonymous_user = AnonymousUser  # Use custom anonymous user

# Create upload and instance folders
os.makedirs(app.instance_path, exist_ok=True)
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
os.makedirs(os.path.join(app.config['UPLOAD_FOLDER'], 'userpicture'), exist_ok=True)
for _share_cat in ('item', 'icon', 'profile', 'project', 'sticker'):
    os.makedirs(os.path.join(app.config['UPLOAD_FOLDER'], 'share', _share_cat), exist_ok=True)

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@login_manager.user_loader
def load_user(user_id):
    """Load user for Flask-Login"""
    return db.session.get(User, int(user_id))


# Register Jinja2 filters
app.jinja_env.filters['filesize'] = filesize_filter
app.jinja_env.filters['format_amount'] = jinja_format_amount
app.jinja_env.filters['markdown'] = markdown_filter

def from_json_filter(value):
    try:
        return json.loads(value) if value else []
    except (json.JSONDecodeError, TypeError):
        return []

app.jinja_env.filters['from_json'] = from_json_filter


# ── Display timezone ──────────────────────────────────────────────────────
import re as _re, os as _os
from datetime import timezone as _tz_cls, timedelta as _td

# UTC offset list: -12:00 → +14:00 in 15-minute steps (~105 entries)
TZ_OFFSETS = []
for _tm in range(-12 * 60, 14 * 60 + 1, 15):
    _s = '+' if _tm >= 0 else '-'
    _a = abs(_tm)
    _h, _m = divmod(_a, 60)
    _v = f"{_s}{_h:02d}:{_m:02d}"
    TZ_OFFSETS.append((_v, f"UTC{_v}"))

def _resolve_display_tz():
    raw = ''
    try:
        s = Setting.query.filter_by(key='display_timezone').first()
        if s and s.value:
            raw = s.value.strip()
    except Exception:
        pass
    if not raw:
        raw = _os.environ.get('TZ', '').strip()
    if not raw:
        return _tz_cls.utc, 'UTC+00:00'
    # Fixed offset: +08:00 / -05:30
    m = _re.fullmatch(r'([+-])(\d{1,2}):(\d{2})', raw)
    if m:
        sign = 1 if m.group(1) == '+' else -1
        h, mins = int(m.group(2)), int(m.group(3))
        tz = _tz_cls(sign * _td(hours=h, minutes=mins))
        return tz, f"UTC{m.group(1)}{h:02d}:{mins:02d}"
    # IANA name (TZ env, Docker users)
    try:
        from zoneinfo import ZoneInfo
        from datetime import datetime as _dtnow
        tz = ZoneInfo(raw)
        offset = _dtnow.now(tz).utcoffset()
        total = int(offset.total_seconds())
        sign = '+' if total >= 0 else '-'
        h, mins = divmod(abs(total) // 60, 60)
        return tz, f"UTC{sign}{h:02d}:{mins:02d} ({raw})"
    except Exception:
        return _tz_cls.utc, 'UTC+00:00'

def _get_display_tz():
    from flask import g, has_request_context
    if has_request_context():
        if not hasattr(g, '_tz_cache'):
            g._tz_cache = _resolve_display_tz()
        return g._tz_cache
    return _resolve_display_tz()

def _localtime_filter(dt, fmt='%Y-%m-%d %H:%M'):
    if not dt:
        return ''
    tz, _ = _get_display_tz()
    if not getattr(dt, 'tzinfo', None):
        dt = dt.replace(tzinfo=_tz_cls.utc)
    return dt.astimezone(tz).strftime(fmt)

app.jinja_env.filters['localtime'] = _localtime_filter

@app.context_processor
def _inject_server_time():
    from datetime import datetime as _dt
    tz, label = _get_display_tz()
    now_local = _dt.now(_tz_cls.utc).astimezone(tz)
    return {'server_now': now_local, 'tz_label': label}

def load_dependencies():
    """Return core static assets bundled in the repository."""
    return [
        'lib/bootstrap.min.css',
        'icons/bootstrap-icons.css',
        'css/pygments.css',
        'lib/highlight-theme.css',
    ], [
        'lib/bootstrap.bundle.min.js',
        'lib/sortable.min.js',
    ], [
        {'name': 'Bootstrap', 'version': '5.3.0'},
        {'name': 'Bootstrap Icons', 'version': '1.11.1'},
        {'name': 'SortableJS', 'version': '1.15.0'},
        {'name': 'Pygments', 'version': '2.x'},
        {'name': 'highlight.js', 'version': '11.9.0'},
    ]


@app.context_processor
def inject_theme():
    """Inject validated theme settings into all templates with fallback"""
    import os

    def get_available_themes():
        themes_dir = os.path.join(app.root_path, 'static', 'custom', 'theme')
        theme_ids = []
        if os.path.exists(themes_dir):
            for file in os.listdir(themes_dir):
                if file.endswith('.css'):
                    theme_ids.append(file[:-4])
        return theme_ids if theme_ids else ['light']

    def validate_theme(theme):
        available = get_available_themes()
        return theme if theme in available else 'light'

    default_theme = validate_theme(Setting.get('default_theme', 'light'))

    if current_user.is_authenticated:
        validated_theme = validate_theme(current_user.theme or default_theme)
        return {'current_theme': validated_theme, 'default_theme': default_theme}
    return {'current_theme': default_theme, 'default_theme': default_theme}


@app.context_processor
def inject_settings():
    """Inject global settings into all templates"""
    settings_dict = {}

    # Core settings
    settings_to_inject = [
        'app_name', 'currency', 'currency_decimal_places',
        'company_name', 'company_address', 'company_logo'
    ]

    for key in settings_to_inject:
        settings_dict[key] = Setting.get(key, '')

    # System name and logo
    system_name = Setting.get('system_name', '')
    system_logo_file = Setting.get('system_logo', '')
    system_logo_url = url_for('instance_file', filename=system_logo_file) if system_logo_file else ''

    # Categories for dropdowns
    categories = Category.query.order_by(Category.name).all()

    # Notification count (default to 0 if no notifications)
    notification_count = 0

    # Banner timeout
    banner_timeout = Setting.get('banner_timeout', '5')

    # Load JS dependencies dynamically
    css_files, js_files, libs = load_dependencies()

    return {
        'app_settings': settings_dict,
        'all_categories': categories,
        'notification_count': notification_count,
        'banner_timeout': banner_timeout,
        'css_files': css_files,
        'js_files': js_files,
        'dependencies': libs,
        'system_name': system_name,
        'system_logo_url': system_logo_url,
        'demo_mode': app.config.get('DEMO_MODE', False),
    }


# Main application routes
@app.route('/')
@login_required
def index():
    """Redirect to items list"""
    return render_template('index.html')


# Main application routes
@app.route('/uploads/<path:filename>')
@login_required  # Protects general uploads (item photos, icons, etc.)
def uploaded_file(filename):
    """Serve uploaded files"""
    from werkzeug.security import safe_join
    from flask import abort
    
    # Security: prevent directory traversal
    safe_path = safe_join(app.config['UPLOAD_FOLDER'], filename)
    if safe_path is None or not os.path.exists(safe_path):
        abort(404)
    
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)


@app.route('/uploads/userpicture/<filename>')
@login_required  # Protects user profile pictures
def user_picture(filename):
    """Serve user profile pictures"""
    from werkzeug.security import safe_join
    from flask import abort
    
    user_pic_folder = os.path.join(app.config['UPLOAD_FOLDER'], 'userpicture')
    safe_path = safe_join(user_pic_folder, filename)
    if safe_path is None or not os.path.exists(safe_path):
        abort(404)
    
    return send_from_directory(user_pic_folder, filename)


@app.route('/favicon.ico')
def favicon():
    """Serve favicon.ico from instance folder if available, else fall back to static."""
    favicon_path = os.path.join(app.instance_path, 'favicon.ico')
    if os.path.exists(favicon_path):
        return send_from_directory(app.instance_path, 'favicon.ico', mimetype='image/x-icon')
    static_favicon = os.path.join(app.root_path, 'static', 'favicon.ico')
    if os.path.exists(static_favicon):
        return send_from_directory(os.path.join(app.root_path, 'static'), 'favicon.ico', mimetype='image/x-icon')
    abort(404)


_INSTANCE_FILE_ALLOWED_EXTS = {'png', 'jpg', 'jpeg', 'gif', 'ico', 'svg', 'webp'}

@app.route('/instance-file/<filename>')
def instance_file(filename):
    """Serve logo/favicon files stored in the instance folder. Restricted to image types only."""
    from werkzeug.utils import secure_filename
    safe_name = secure_filename(filename)
    if not safe_name:
        abort(404)
    ext = safe_name.rsplit('.', 1)[-1].lower() if '.' in safe_name else ''
    if ext not in _INSTANCE_FILE_ALLOWED_EXTS:
        abort(404)
    instance_dir = app.instance_path
    full_path = os.path.join(instance_dir, safe_name)
    if not os.path.exists(full_path):
        abort(404)
    return send_from_directory(instance_dir, safe_name)


@app.after_request
def set_security_headers(response):
    """Add security headers to every response."""
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['X-Frame-Options'] = 'SAMEORIGIN'
    response.headers['X-XSS-Protection'] = '1; mode=block'
    response.headers['Referrer-Policy'] = 'strict-origin-when-cross-origin'
    return response


# Error handlers
@app.errorhandler(404)
def not_found_error(error):
    """Handle 404 errors"""
    return render_template('404.html'), 404


@app.errorhandler(500)
def internal_error(error):
    """Handle 500 errors"""
    db.session.rollback()
    return render_template('500.html'), 500


# Register all modular blueprints
from routes import register_blueprints
register_blueprints(app)

# Exempt REST API blueprints from CSRF — they authenticate via Bearer token, not cookies.
from routes.api import api_bp
from routes.api_v1 import api_v1_bp
csrf.exempt(api_bp)
csrf.exempt(api_v1_bp)

# Validate Bootstrap Icons at startup
from qr_utils import validate_bootstrap_icons
with app.app_context():
    validate_bootstrap_icons()

# Apply any pending column migrations to existing databases
def _apply_column_migrations():
    """Add new columns to existing tables that predate them."""
    additions = [
        ("batch_lend_records",   "lend_note",           "VARCHAR(128)"),
        ("batch_serial_numbers", "lend_note",           "VARCHAR(128)"),
        ("batch_serial_numbers", "lending_session_id",  "INTEGER"),
        ("batch_lend_records",   "lending_session_id",  "INTEGER"),
        ("batch_lend_records",   "returned_at",         "DATETIME"),
        ("batch_lend_records",   "return_session_id",    "INTEGER"),
        ("batch_serial_numbers", "return_session_id",    "INTEGER"),
        ("batch_serial_numbers", "returned_at",          "DATETIME"),
        ("batch_serial_numbers", "returned_from_label",  "VARCHAR(128)"),
        ("users",                "allow_change_name",    "BOOLEAN DEFAULT 1"),
        ("item_batches",         "lend_disabled",        "BOOLEAN DEFAULT 0"),
        ("racks",                "drawer_icons",         "TEXT DEFAULT NULL"),
        ("racks",                "rack_icon",            "TEXT DEFAULT NULL"),
        ("projects",             "thumbnail",            "VARCHAR(300)"),
        ("project_bom_items",    "sort_order",           "INTEGER DEFAULT 0"),
        ("users",                "user_uid",             "VARCHAR(6)"),
        ("lending_sessions",     "is_api",               "BOOLEAN DEFAULT 0"),
        ("users",                "api_key_hash",         "VARCHAR(64)"),
        ("users",                "api_key_prefix",       "VARCHAR(16)"),
        ("kanban_tasks",         "start_date",           "DATE"),
        ("kanban_boards",        "notify_start_enabled", "BOOLEAN DEFAULT 0"),
        ("kanban_boards",        "notify_start_days",    "INTEGER DEFAULT 1"),
        ("kanban_boards",        "notify_due_enabled",   "BOOLEAN DEFAULT 0"),
        ("kanban_boards",        "notify_due_days",      "INTEGER DEFAULT 1"),
        ("kanban_cards",         "category_id",          "INTEGER"),
        ("kanban_boards",        "board_icon",            "VARCHAR(48) DEFAULT 'bi-kanban'"),
        ("kanban_boards",        "board_color",           "VARCHAR(7) DEFAULT '#6b7280'"),
        ("kanban_boards",        "board_status",          "VARCHAR(10) DEFAULT 'shown'"),
        ("kanban_boards",        "board_uuid",            "VARCHAR(12)"),
        ("kanban_boards",        "is_public",             "BOOLEAN DEFAULT 0"),
        ("kanban_boards",        "share_view_users",      "TEXT"),
        ("kanban_boards",        "share_edit_users",      "TEXT"),
        ("kanban_boards",        "created_at",            "DATETIME"),
        ("kanban_boards",        "updated_at",            "DATETIME"),
        ("kanban_cards",         "created_at",            "DATETIME"),
        ("kanban_cards",         "updated_at",            "DATETIME"),
    ]
    with db.engine.connect() as conn:
        for table, col, col_type in additions:
            try:
                conn.execute(db.text(f"ALTER TABLE {table} ADD COLUMN {col} {col_type}"))
                conn.commit()
                logger.info(f"DB migration: added {table}.{col}")
            except Exception:
                pass  # column already exists

    # Backfill user_uid for existing users that don't have one yet
    import secrets, string
    def _gen_uid():
        chars = string.ascii_uppercase + string.digits
        return 'U' + ''.join(secrets.choice(chars) for _ in range(5))

    with db.engine.connect() as conn:
        rows = conn.execute(db.text("SELECT id FROM users WHERE user_uid IS NULL")).fetchall()
        if rows:
            existing = {r[0] for r in conn.execute(db.text("SELECT user_uid FROM users WHERE user_uid IS NOT NULL")).fetchall()}
            for (uid_row,) in rows:
                uid = _gen_uid()
                while uid in existing:
                    uid = _gen_uid()
                existing.add(uid)
                conn.execute(db.text("UPDATE users SET user_uid = :uid WHERE id = :id"), {"uid": uid, "id": uid_row})
            conn.commit()
            logger.info(f"DB migration: backfilled user_uid for {len(rows)} user(s)")

    # Backfill board_uuid for existing kanban boards that don't have one yet
    def _gen_board_uuid():
        chars = string.ascii_uppercase + string.digits
        return ''.join(secrets.choice(chars) for _ in range(11)) + 'K'

    with db.engine.connect() as conn:
        rows = conn.execute(db.text("SELECT id FROM kanban_boards WHERE board_uuid IS NULL")).fetchall()
        if rows:
            existing = {r[0] for r in conn.execute(db.text("SELECT board_uuid FROM kanban_boards WHERE board_uuid IS NOT NULL")).fetchall()}
            for (bid,) in rows:
                uid = _gen_board_uuid()
                while uid in existing:
                    uid = _gen_board_uuid()
                existing.add(uid)
                conn.execute(db.text("UPDATE kanban_boards SET board_uuid = :uid WHERE id = :id"), {"uid": uid, "id": bid})
            conn.commit()
            logger.info(f"DB migration: backfilled board_uuid for {len(rows)} board(s)")


with app.app_context():
    db.create_all()          # create any brand-new tables (e.g. lending_sessions)
    _apply_column_migrations()


if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    debug_mode = os.getenv('FLASK_DEBUG', '').lower() in ('1', 'true', 'yes')
    app.run(host='0.0.0.0', port=5000, debug=debug_mode)
