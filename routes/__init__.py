"""
Routes Package - Modularized Blueprint Registration
"""
from flask import Flask
import logging

logger = logging.getLogger(__name__)


def register_blueprints(app: Flask):
    """
    Register all application blueprints with the Flask app
    
    Args:
        app: Flask application instance
    """
    # Import all blueprints
    from routes.auth import auth_bp
    from routes.item import item_bp
    from routes.category import category_bp
    from routes.user_role import user_role_bp
    from routes.location_rack import location_rack_bp
    from routes.visual_storage import visual_storage_bp
    from routes.settings import settings_bp
    from routes.footprint_tag import footprint_tag_bp
    from routes.backup import backup_bp
    from routes.magic_parameter import magic_parameter_bp
    from routes.notification import notification_bp
    from routes.print import print_bp as print_routes_bp
    from routes.report import report_bp
    from routes.api import api_bp
    from routes.qr_template import qr_template_bp
    
    # Register blueprints
    app.register_blueprint(auth_bp)
    app.register_blueprint(item_bp)
    app.register_blueprint(category_bp)
    app.register_blueprint(user_role_bp)
    app.register_blueprint(location_rack_bp)
    app.register_blueprint(visual_storage_bp)
    app.register_blueprint(settings_bp)
    app.register_blueprint(footprint_tag_bp)
    app.register_blueprint(backup_bp)
    app.register_blueprint(magic_parameter_bp)
    app.register_blueprint(notification_bp)
    app.register_blueprint(print_routes_bp)
    app.register_blueprint(report_bp)
    app.register_blueprint(api_bp)
    app.register_blueprint(qr_template_bp)
    
    logger.info("✓ All blueprints registered successfully")
