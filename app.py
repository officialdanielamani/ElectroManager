"""
Inventory Manager Application - Main Entry Point (Refactored)
"""
from flask import Flask, render_template, request, send_from_directory, jsonify
from flask_login import LoginManager, current_user, AnonymousUserMixin, login_required
from config import Config
from models import db, User, Category, Item, Setting
from helpers import filesize_filter, jinja_format_amount, markdown_filter
import os
import logging

# Initialize Flask app
app = Flask(__name__)
app.config.from_object(Config)

# Initialize database
db.init_app(app)


# Custom Anonymous User with permission methods
class AnonymousUser(AnonymousUserMixin):
    """Anonymous user with permission checks that always return False"""
    
    def has_permission(self, resource, action):
        """Anonymous users have no permissions"""
        return False
    
    def is_admin(self):
        """Anonymous users are not admins"""
        return False
    
    def is_editor(self):
        """Anonymous users are not editors"""
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
login_manager.login_message = 'Please log in to access this page.'
login_manager.anonymous_user = AnonymousUser  # Use custom anonymous user

# Create upload folders
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
os.makedirs(os.path.join(app.config['UPLOAD_FOLDER'], 'userpicture'), exist_ok=True)

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


@app.context_processor
def inject_theme():
    """Inject theme settings into all templates"""
    if current_user.is_authenticated:
        return {'current_theme': current_user.theme or 'light'}
    return {'current_theme': 'light'}


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
    
    # Categories for dropdowns
    categories = Category.query.order_by(Category.name).all()
    
    # Notification count (default to 0 if no notifications)
    notification_count = 0
    
    # Banner timeout
    banner_timeout = Setting.get('banner_timeout', '5')
    
    return {
        'app_settings': settings_dict,
        'all_categories': categories,
        'notification_count': notification_count,
        'banner_timeout': banner_timeout
    }


# Main application routes
@app.route('/')
@login_required
def index():
    """Redirect to items list"""
    return render_template('index.html')



@app.route('/uploads/<path:filename>')
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
def user_picture(filename):
    """Serve user profile pictures"""
    from werkzeug.security import safe_join
    from flask import abort
    
    user_pic_folder = os.path.join(app.config['UPLOAD_FOLDER'], 'userpicture')
    safe_path = safe_join(user_pic_folder, filename)
    if safe_path is None or not os.path.exists(safe_path):
        abort(404)
    
    return send_from_directory(user_pic_folder, filename)


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


if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(host='0.0.0.0', port=5000, debug=True)
