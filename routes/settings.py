"""
Settings Routes Blueprint
"""
from flask import Blueprint, render_template, redirect, url_for, flash, request, jsonify, send_file, abort, current_app
from flask_login import login_required, current_user, login_user, logout_user
from models import db, User, Category, Item, Attachment, Rack, Footprint, Tag, Setting, Location, AuditLog, StickerTemplate
from forms import (LoginForm, RegistrationForm, CategoryForm, ItemAddForm, ItemEditForm, AttachmentForm, 
                   SearchForm, UserForm, MagicParameterForm, ParameterUnitForm, ParameterStringOptionForm, ItemParameterForm)
from helpers import is_safe_url, format_currency, is_safe_file_path
from utils import save_file, log_audit, admin_required, permission_required, item_permission_required, format_file_size, allowed_file
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from datetime import datetime, timezone
from urllib.parse import urlparse, urljoin
import os
import json
import secrets
import string
import logging

logger = logging.getLogger(__name__)

settings_bp = Blueprint('settings', __name__)


@settings_bp.route('/settings', endpoint='settings')
@login_required
def settings():
    """Settings page hub - accessible to all users"""
    # Settings page is now accessible to all authenticated users
    # Edit capabilities for sub-sections are controlled by settings_sections permissions
    
    return render_template('settings.html')



@settings_bp.route('/settings/general', endpoint='settings_general')
@login_required
def settings_general():
    current_theme = current_user.theme or 'light'
    current_font = current_user.user_font or 'system'
    return render_template('settings_general.html', current_theme=current_theme, current_font=current_font)



@settings_bp.route('/save-theme', methods=['POST'])
@login_required
def save_theme():
    theme = request.form.get('theme', 'light')
    
    # Validate theme
    valid_themes = ['light', 'dark', 'blue', 'keqing']
    if theme not in valid_themes:
        theme = 'light'
    
    # Save to current user
    current_user.theme = theme
    db.session.commit()
    
    flash(f'Your theme changed to "{theme.capitalize()}"!', 'success')
    log_audit(current_user.id, 'update', 'user', current_user.id, f'Changed theme to {theme}')
    return redirect(url_for('settings.settings_general'))



@settings_bp.route('/save-font', methods=['POST'])
@login_required
def save_font():
    user_font = request.form.get('user_font', 'system')
    
    # Validate font
    valid_fonts = ['system', 'open-dyslexic', 'courier']
    if user_font not in valid_fonts:
        user_font = 'system'
    
    # Save to current user
    current_user.user_font = user_font
    db.session.commit()
    
    font_names = {
        'system': 'System (Default)',
        'open-dyslexic': 'OpenDyslexic',
        'courier': 'Courier New'
    }
    
    flash(f'Your font changed to "{font_names.get(user_font, user_font)}"!', 'success')
    log_audit(current_user.id, 'update', 'user', current_user.id, f'Changed font to {user_font}')
    return redirect(url_for('settings.settings_general'))



@settings_bp.route('/save-ui-preference', endpoint='save_ui_preference', methods=['POST'])
@login_required
def save_ui_preference():
    """Save both theme and font together"""
    # Save theme
    theme = request.form.get('theme', 'light')
    valid_themes = ['light', 'dark', 'blue', 'keqing']
    if theme not in valid_themes:
        theme = 'light'
    
    current_user.theme = theme
    
    # Save font
    user_font = request.form.get('user_font', 'system')
    valid_fonts = ['system', 'open-dyslexic', 'courier']
    if user_font not in valid_fonts:
        user_font = 'system'
    
    current_user.user_font = user_font
    db.session.commit()
    
    flash(f'Your UI preferences have been saved!', 'success')
    log_audit(current_user.id, 'update', 'user', current_user.id, f'Changed UI preference: theme={theme}, font={user_font}')
    return redirect(url_for('settings.settings_general'))



@settings_bp.route('/change-password', methods=['POST'])
@login_required
def change_password():
    """Change current user password"""
    if not current_user.allow_password_reset:
        flash('Password change is disabled for your account.', 'danger')
        return redirect(url_for('settings.settings_general'))
    
    current_password = request.form.get('current_password')
    new_password = request.form.get('new_password')
    confirm_password = request.form.get('confirm_password')
    
    # Validate inputs
    if not current_password or not new_password or not confirm_password:
        flash('All password fields are required.', 'danger')
        return redirect(url_for('settings.settings_general'))
    
    # Check current password
    if not current_user.check_password(current_password):
        flash('Current password is incorrect.', 'danger')
        return redirect(url_for('settings.settings_general'))
    
    # Check new passwords match
    if new_password != confirm_password:
        flash('New passwords do not match.', 'danger')
        return redirect(url_for('settings.settings_general'))
    
    # Check minimum length
    if len(new_password) < 6:
        flash('New password must be at least 6 characters.', 'danger')
        return redirect(url_for('settings.settings_general'))
    
    # Set new password
    current_user.set_password(new_password)
    current_user.failed_login_attempts = 0  # Reset failed attempts
    current_user.account_locked_until = None
    db.session.commit()
    
    log_audit(current_user.id, 'update', 'user', current_user.id, 'Changed password')
    flash('Password changed successfully!', 'success')
    return redirect(url_for('settings.settings_general'))



@settings_bp.route('/upload-profile-photo', methods=['POST'])
@login_required
def upload_profile_photo():
    """Upload user profile photo"""
    if 'profile_photo' not in request.files:
        flash('No file selected.', 'danger')
        return redirect(url_for('settings.settings_general'))
    
    file = request.files['profile_photo']
    
    if file.filename == '':
        flash('No file selected.', 'danger')
        return redirect(url_for('settings.settings_general'))
    
    if not allowed_file(file.filename, {'png', 'jpg', 'jpeg'}):
        flash('Only PNG and JPEG files are allowed.', 'danger')
        return redirect(url_for('settings.settings_general'))
    
    # Check file size (max 1MB)
    file.seek(0, os.SEEK_END)
    file_size = file.tell()
    file.seek(0)
    
    if file_size > 1024 * 1024:  # 1MB
        flash('Profile photo must be smaller than 1MB.', 'danger')
        return redirect(url_for('settings.settings_general'))
    
    # Delete old photo if exists
    if current_user.profile_photo:
        old_file = os.path.join(current_app.config['UPLOAD_FOLDER'], 'userpicture', current_user.profile_photo)
        if is_safe_file_path(old_file) and os.path.exists(old_file):
            os.remove(old_file)

    # Save with username as filename - sanitize extension
    ext = secure_filename(file.filename.rsplit('.', 1)[1].lower())
    filename = f"{secure_filename(current_user.username)}.{ext}"
    filepath = os.path.join(current_app.config['UPLOAD_FOLDER'], 'userpicture', filename)
    file.save(filepath)
    
    current_user.profile_photo = filename
    db.session.commit()
    
    log_audit(current_user.id, 'update', 'user', current_user.id, 'Updated profile photo')
    flash('Profile photo updated successfully!', 'success')
    return redirect(url_for('settings.settings_general'))



@settings_bp.route('/delete-profile-photo', methods=['POST'])
@login_required
def delete_profile_photo():
    """Delete user profile photo"""
    if current_user.profile_photo:
        filepath = os.path.join(current_app.config['UPLOAD_FOLDER'], 'userpicture', current_user.profile_photo)
        if is_safe_file_path(filepath) and os.path.exists(filepath):
            os.remove(filepath)
        
        current_user.profile_photo = None
        db.session.commit()
        
        log_audit(current_user.id, 'update', 'user', current_user.id, 'Deleted profile photo')
        flash('Profile photo deleted successfully!', 'success')
    
    return redirect(url_for('settings.settings_general'))



@settings_bp.route('/save-table-columns-view', methods=['POST'])
@login_required
def save_table_columns_view():
    """Save user's preferred table columns view"""
    columns_json = request.form.get('columns', '[]')
    
    try:
        columns = json.loads(columns_json)
        
        # Validate columns
        valid_columns = ['type_model', 'sku', 'category', 'tags', 'footprint', 'quantity', 'total_price', 'price_per_unit', 'location', 'uuid', 'status']
        columns = [col for col in columns if col in valid_columns]
        
        # Save to current user
        current_user.set_table_columns(columns)
        db.session.commit()
        
        flash('Table columns view updated successfully!', 'success')
        log_audit(current_user.id, 'update', 'user', current_user.id, f'Updated table columns view')
    except Exception as e:
        logging.error(f"Error saving table columns for user {current_user.id}: {str(e)}")
        flash('Error saving table columns. Please try again.', 'danger')
    
    return redirect(url_for('settings.settings_general'))



@settings_bp.route('/settings/system', endpoint='settings_system', methods=['GET', 'POST'])
@login_required
def settings_system():
    """System-wide settings"""
    # Check granular permission for system settings
    if not current_user.has_permission('settings_sections.system_settings', 'view'):
        flash('You do not have permission to view system settings.', 'danger')
        return redirect(url_for('settings.settings'))
    
    can_edit = current_user.has_permission('settings_sections.system_settings', 'edit')
    
    if request.method == 'POST':
        if not can_edit:
            flash('You do not have permission to edit system settings.', 'danger')
            return redirect(url_for('settings.settings_system'))
        try:
            # Currency setting
            currency = request.form.get('currency', '$').strip()
            if len(currency) > 7:
                flash('Currency symbol must be 7 characters or less!', 'danger')
                return redirect(url_for('settings.settings_system'))
            
            # Currency decimal places
            currency_decimal_places = request.form.get('currency_decimal_places', '2')
            try:
                currency_decimal_places = int(currency_decimal_places)
                if currency_decimal_places < 0 or currency_decimal_places > 5:
                    flash('Currency decimal places must be between 0 and 5!', 'danger')
                    return redirect(url_for('settings.settings_system'))
            except ValueError:
                flash('Invalid currency decimal places value!', 'danger')
                return redirect(url_for('settings.settings_system'))
            
            # In DEMO MODE, skip file validation and use stored defaults
            if current_app.config.get('DEMO_MODE', False):
                # Demo mode: use fixed values, ignore form input for file settings
                allowed_extensions = 'jpg,jpeg,png,txt,md'
                max_file_size = 1
            else:
                # Production mode: validate file settings from form
                allowed_extensions = request.form.get('allowed_extensions', '').strip()
                if not allowed_extensions:
                    flash('You must specify at least one allowed file type!', 'danger')
                    return redirect(url_for('settings.settings_system'))
                
                # Max file size validation (production mode only)
                max_file_size = request.form.get('max_file_size', '10')
                try:
                    max_file_size = int(max_file_size)
                    if max_file_size < 1 or max_file_size > 100:
                        flash('Max file size must be between 1 and 100 MB!', 'danger')
                        return redirect(url_for('settings.settings_system'))
                except ValueError:
                    flash('Invalid max file size value!', 'danger')
                    return redirect(url_for('settings.settings_system'))
            
            # Max drawer rows
            max_drawer_rows = request.form.get('max_drawer_rows', '10')
            try:
                max_drawer_rows = int(max_drawer_rows)
                if max_drawer_rows < 1 or max_drawer_rows > 32:
                    flash('Max drawer rows must be between 1 and 32!', 'danger')
                    return redirect(url_for('settings.settings_system'))
            except ValueError:
                flash('Invalid max drawer rows value!', 'danger')
                return redirect(url_for('settings.settings_system'))
            
            # Max drawer columns
            max_drawer_cols = request.form.get('max_drawer_cols', '10')
            try:
                max_drawer_cols = int(max_drawer_cols)
                if max_drawer_cols < 1 or max_drawer_cols > 32:
                    flash('Max drawer columns must be between 1 and 32!', 'danger')
                    return redirect(url_for('settings.settings_system'))
            except ValueError:
                flash('Invalid max drawer columns value!', 'danger')
                return redirect(url_for('settings.settings_system'))
            
            # Banner timeout
            banner_timeout = request.form.get('banner_timeout', '5')
            try:
                banner_timeout = int(banner_timeout)
                if banner_timeout < 0 or banner_timeout > 60:
                    flash('Banner timeout must be between 0 and 60 seconds!', 'danger')
                    return redirect(url_for('settings.settings_system'))
            except ValueError:
                flash('Invalid banner timeout value!', 'danger')
                return redirect(url_for('settings.settings_system'))
            
            # Save settings
            Setting.set('currency', currency, 'Currency symbol for prices')
            Setting.set('currency_decimal_places', currency_decimal_places, 'Currency decimal places (0-5)')
            Setting.set('max_file_size_mb', max_file_size, 'Maximum file upload size in MB')
            Setting.set('allowed_extensions', allowed_extensions, 'Allowed file extensions (comma-separated)')
            Setting.set('max_drawer_rows', max_drawer_rows, 'Maximum drawer rows (1-32)')
            Setting.set('max_drawer_cols', max_drawer_cols, 'Maximum drawer columns (1-32)')
            Setting.set('banner_timeout', banner_timeout, 'Banner auto-dismiss timeout in seconds (0=permanent)')
            
            # Update app config dynamically
            current_app.config['MAX_CONTENT_LENGTH'] = max_file_size * 1024 * 1024
            
            flash('System settings updated successfully!', 'success')
            log_audit(current_user.id, 'update', 'settings', 0,
                     f'Updated system settings: currency={currency}, decimal_places={currency_decimal_places}, max_file_size={max_file_size}MB, drawer_size={max_drawer_rows}x{max_drawer_cols}, banner_timeout={banner_timeout}s')

        except Exception as e:
            logging.error(f"Error saving system settings: {str(e)}")
            flash('Error saving settings. Please try again.', 'danger')
        
        return redirect(url_for('settings.settings_system'))
    
    # GET request - load current settings
    currency = Setting.get('currency', '$')
    currency_decimal_places = Setting.get('currency_decimal_places', '2')
    max_file_size = Setting.get('max_file_size_mb', '10')
    allowed_extensions = Setting.get('allowed_extensions', 'pdf,png,jpg,jpeg,gif,txt,doc,docx')
    max_drawer_rows = Setting.get('max_drawer_rows', '10')
    max_drawer_cols = Setting.get('max_drawer_cols', '10')
    banner_timeout = Setting.get('banner_timeout', '5')
    
    # Read system information from verinfo file
    verinfo_content = ""
    verinfo_path = None
    for filename in ['verinfo.md', 'verinfo.txt']:
        filepath = os.path.join(current_app.config['UPLOAD_FOLDER'], '..', filename)
        if os.path.exists(filepath):
            verinfo_path = filepath
            try:
                with open(filepath, 'r', encoding='utf-8') as f:
                    verinfo_content = f.read()
            except:
                verinfo_content = f"Error reading {filename}"
            break
    
    return render_template('settings_system.html', 
                          currency=currency,
                          currency_decimal_places=currency_decimal_places,
                          max_file_size=max_file_size,
                          allowed_extensions=allowed_extensions,
                          max_drawer_rows=max_drawer_rows,
                          max_drawer_cols=max_drawer_cols,
                          banner_timeout=banner_timeout,
                          verinfo_content=verinfo_content,
                          demo_mode=current_app.config.get('DEMO_MODE', False))


# ============= FOOTPRINTS =============



@settings_bp.route('/settings/magic-parameters')
@login_required
def magic_parameters():
    """Magic Parameters settings page"""
    from models import MagicParameter, ParameterTemplate
    
    # Check view permission for magic parameter settings
    if not current_user.has_permission('settings_sections.magic_parameters', 'view'):
        flash('You do not have permission to view magic parameters.', 'danger')
        return redirect(url_for('settings.settings'))
    
    # Get parameters grouped by type
    number_params = MagicParameter.query.filter_by(param_type='number').order_by(MagicParameter.name).all()
    date_params = MagicParameter.query.filter_by(param_type='date').order_by(MagicParameter.name).all()
    string_params = MagicParameter.query.filter_by(param_type='string').order_by(MagicParameter.name).all()
    templates = ParameterTemplate.query.order_by(ParameterTemplate.name).all()
    
    can_edit = current_user.has_permission('settings_sections.magic_parameters', 'edit')
    can_delete = current_user.has_permission('settings_sections.magic_parameters', 'delete')
    
    return render_template('magic_parameters.html', 
                          number_params=number_params,
                          date_params=date_params,
                          string_params=string_params,
                          templates=templates,
                          can_edit=can_edit,
                          can_delete=can_delete)


@settings_bp.route('/manage-types', endpoint='manage_types')
@login_required
def manage_types():
    """Manage item types - Categories, Footprints, Tags"""
    from models import Category, Footprint, Tag
    
    # Check if user has view permission for item settings
    if not current_user.has_permission('settings_sections.item_management', 'view'):
        flash('You do not have permission to view item management settings.', 'danger')
        return redirect(url_for('settings.settings'))
    
    categories = Category.query.order_by(Category.name).all()
    footprints = Footprint.query.order_by(Footprint.name).all()
    tags = Tag.query.order_by(Tag.name).all()
    
    can_edit = current_user.has_permission('settings_sections.item_management', 'edit')
    can_delete = current_user.has_permission('settings_sections.item_management', 'delete')
    
    return render_template('item_management.html', 
                         categories=categories, 
                         footprints=footprints, 
                         tags=tags,
                         can_edit=can_edit,
                         can_delete=can_delete)


# ==================== ITEM STICKER PREVIEW ====================



