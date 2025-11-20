"""
Backup Routes Blueprint
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

backup_bp = Blueprint('backup', __name__)


@backup_bp.route('/backup-restore', endpoint='backup_restore')
@login_required
def backup_restore():
    # Check permission for backup/restore
    if not current_user.has_permission('settings_sections.backup_restore', 'view'):
        flash('You do not have permission to view backups.', 'danger')
        return redirect(url_for('settings.settings'))
    
    can_upload_export = current_user.has_permission('settings_sections.backup_restore', 'upload_export')
    can_delete = current_user.has_permission('settings_sections.backup_restore', 'delete')
    
    return render_template('backup_restore.html',
                          can_upload_export=can_upload_export,
                          can_delete=can_delete)



@backup_bp.route('/backup/download', endpoint='backup_download')
@login_required
@permission_required("settings_sections.backup_restore", "upload_export")
def backup_download():
    import shutil
    import os
    db_path = current_app.config.get('SQLALCHEMY_DATABASE_URI', 'sqlite:///inventory.db').replace('sqlite:///', '')
    if not os.path.exists(db_path):
        flash('Database file not found', 'danger')
        return redirect(url_for('backup.backup_restore'))
    backup_path = 'inventory_backup.db'
    shutil.copy(db_path, backup_path)
    return send_from_directory('.', 'inventory_backup.db', as_attachment=True)



@backup_bp.route('/backup/restore', endpoint='backup_restore_upload', methods=['POST'])
@login_required
@permission_required("settings_sections.backup_restore", "upload_export")
def backup_restore_upload():
    import shutil
    import os
    if 'backup' not in request.files:
        flash('No file uploaded', 'danger')
        return redirect(url_for('backup.backup_restore'))
    
    file = request.files['backup']
    if file.filename.endswith('.db'):
        db_path = current_app.config.get('SQLALCHEMY_DATABASE_URI', 'sqlite:///inventory.db').replace('sqlite:///', '')
        backup_old_path = 'inventory_backup_old.db'
        shutil.copy(db_path, backup_old_path)
        file.save(db_path)
        flash('Database restored! Please restart the app.', 'success')
    else:
        flash('Invalid file type', 'danger')
    
    return redirect(url_for('backup.backup_restore'))



@backup_bp.route('/backup/export-selective', endpoint='export_selective', methods=['POST'])
@login_required
@permission_required("settings_sections.backup_restore", "upload_export")
def export_selective():
    """Export selected data types"""
    from importexport import DataExporter
    
    try:
        # Handle Magic Parameters granular options
        mp_selection = None
        if request.form.get('magic_parameters') == 'on':
            mp_selection = {
                'parameters': request.form.get('mp_parameters') == 'on',
                'templates': request.form.get('mp_templates') == 'on',
                'units': request.form.get('mp_units') == 'on',
                'options': request.form.get('mp_options') == 'on'
            }
        
        selections = {
            'magic_parameters': mp_selection,
            'locations': request.form.get('locations') == 'on',
            'racks': request.form.get('racks') == 'on',
            'categories': request.form.get('categories') == 'on',
            'footprints': request.form.get('footprints') == 'on',
            'tags': request.form.get('tags') == 'on'
        }
        
        # Check if at least one selection is made
        if not any([selections['magic_parameters'], selections['locations'], selections['racks'], 
                   selections['categories'], selections['footprints'], selections['tags']]):
            flash('Please select at least one data type to export', 'warning')
            return redirect(url_for('backup.backup_restore'))
        
        include_item_values = request.form.get('include_item_values') == 'on'
        
        export_data = DataExporter.export_selective(selections, include_item_values)
        
        # Send as file download
        response = current_app.make_response(json.dumps(export_data, indent=2))
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        response.headers['Content-Disposition'] = f'attachment; filename=config_export_{timestamp}.json'
        response.headers['Content-Type'] = 'application/json'
        return response
    except Exception as e:
        logging.error(f"Export error: {str(e)}")
        flash('An error occurred during export. Please try again.', 'danger')
        return redirect(url_for('backup.backup_restore'))




@backup_bp.route('/backup/import-selective', endpoint='import_selective', methods=['POST'])
@login_required
@permission_required("settings_sections.backup_restore", "upload_export")
def import_selective():
    """Import selected data types"""
    from importexport import DataImporter
    
    try:
        if 'config' not in request.files:
            flash('No file uploaded', 'danger')
            return redirect(url_for('backup.backup_restore'))
        
        file = request.files['config']
        if not file or file.filename == '':
            flash('No file selected', 'danger')
            return redirect(url_for('backup.backup_restore'))
        
        # Load JSON
        try:
            config_data = json.load(file.stream)
        except Exception as e:
            flash(f'Invalid JSON file: {str(e)}', 'danger')
            return redirect(url_for('backup.backup_restore'))
        
        # Handle Magic Parameters granular options
        mp_selection = None
        if request.form.get('magic_parameters') == 'on':
            mp_selection = {
                'parameters': request.form.get('mp_parameters') == 'on',
                'templates': request.form.get('mp_templates') == 'on',
                'units': request.form.get('mp_units') == 'on',
                'options': request.form.get('mp_options') == 'on'
            }
        
        # Get selections from form
        selections = {
            'magic_parameters': mp_selection,
            'locations': request.form.get('locations') == 'on',
            'racks': request.form.get('racks') == 'on',
            'categories': request.form.get('categories') == 'on',
            'footprints': request.form.get('footprints') == 'on',
            'tags': request.form.get('tags') == 'on'
        }
        
        if not any([selections['magic_parameters'], selections['locations'], selections['racks'], 
                   selections['categories'], selections['footprints'], selections['tags']]):
            flash('Please select at least one data type to import', 'warning')
            return redirect(url_for('backup.backup_restore'))
        
        # Import data
        importer = DataImporter()
        results = importer.import_selective(config_data, selections)
        
        # Show results
        msg = f'✓ Import complete! Imported: {results["imported"]}, Skipped: {results["skipped"]}'
        if results['errors']:
            msg += f', {len(results["errors"])} error(s)'
        flash(msg, 'success')
        
        # Show details by type
        for data_type, details in results['details'].items():
            if details.get('imported', 0) > 0 or details.get('skipped', 0) > 0:
                detail_msg = f"{data_type.replace('_', ' ').title()}: {details.get('imported', 0)} imported, {details.get('skipped', 0)} skipped"
                if 'item_parameters' in details:
                    detail_msg += f" | Item Parameters: {details['item_parameters'].get('imported', 0)} imported, {details['item_parameters'].get('skipped', 0)} skipped"
                flash(detail_msg, 'info')
        
        # Show first 3 errors
        for err in results['errors'][:3]:
            flash(f'⚠️ {err}', 'warning')
        if len(results['errors']) > 3:
            flash(f'⚠️ +{len(results["errors"])-3} more errors', 'warning')
        
        return redirect(url_for('backup.backup_restore'))

    except Exception as e:
        db.session.rollback()
        logging.error(f"Import fatal error: {str(e)}")
        flash('A fatal error occurred during import. Please check the file and try again.', 'danger')
        return redirect(url_for('backup.backup_restore'))

# ============= MAGIC PARAMETERS =============



