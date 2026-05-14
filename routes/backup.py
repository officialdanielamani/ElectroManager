"""
Backup Routes Blueprint
"""
from flask import Blueprint, render_template, redirect, url_for, flash, request, jsonify, send_file, send_from_directory, abort, current_app
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
    demo_mode = current_app.config.get('DEMO_MODE', False)

    return render_template('backup_restore.html',
                          can_upload_export=can_upload_export,
                          can_delete=can_delete,
                          demo_mode=demo_mode)



@backup_bp.route('/backup/download', endpoint='backup_download')
@login_required
@permission_required("settings_sections.backup_restore", "upload_export")
def backup_download():
    if current_app.config.get('DEMO_MODE', False):
        flash('Database backup is disabled in Demo Mode.', 'warning')
        return redirect(url_for('backup.backup_restore'))
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
    if current_app.config.get('DEMO_MODE', False):
        flash('Database restore is disabled in Demo Mode.', 'warning')
        return redirect(url_for('backup.backup_restore'))
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
    if current_app.config.get('DEMO_MODE', False):
        flash('Config export is disabled in Demo Mode.', 'warning')
        return redirect(url_for('backup.backup_restore'))
    from importexport import DataExporter
    
    try:
        any_mp = any(request.form.get(k) == 'on' for k in ['mp_number','mp_string','mp_date','mp_template'])
        mp_selection = None
        if any_mp:
            mp_selection = {
                'number': request.form.get('mp_number') == 'on',
                'string': request.form.get('mp_string') == 'on',
                'date': request.form.get('mp_date') == 'on',
                'template': request.form.get('mp_template') == 'on',
            }

        selections = {
            'magic_parameters': mp_selection,
            'locations': request.form.get('loc_general') == 'on',
            'racks': request.form.get('loc_rack') == 'on',
            'categories': request.form.get('item_categories') == 'on',
            'footprints': request.form.get('item_footprint') == 'on',
            'tags': request.form.get('item_tags') == 'on',
            'project_categories': request.form.get('proj_categories') == 'on',
            'project_tags': request.form.get('proj_tags') == 'on',
            'project_statuses': request.form.get('proj_status') == 'on',
            'contact_persons': request.form.get('contact_persons') == 'on',
            'contact_organizations': request.form.get('contact_orgs') == 'on',
            'contact_groups': request.form.get('contact_groups') == 'on',
            'system_settings': request.form.get('system_settings') == 'on',
        }

        if not any(v for v in selections.values()):
            flash('Please select at least one data type to export', 'warning')
            return redirect(url_for('backup.backup_restore'))

        include_item_values = request.form.get('include_item_values') == 'on'
        export_data = DataExporter.export_selective(selections, include_item_values)

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
    if current_app.config.get('DEMO_MODE', False):
        flash('Config import is disabled in Demo Mode.', 'warning')
        return redirect(url_for('backup.backup_restore'))
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
        
        any_mp = any(request.form.get(k) == 'on' for k in ['mp_number','mp_string','mp_date','mp_template'])
        mp_selection = None
        if any_mp:
            mp_selection = {
                'number': request.form.get('mp_number') == 'on',
                'string': request.form.get('mp_string') == 'on',
                'date': request.form.get('mp_date') == 'on',
                'template': request.form.get('mp_template') == 'on',
            }

        selections = {
            'magic_parameters': mp_selection,
            'locations': request.form.get('loc_general') == 'on',
            'racks': request.form.get('loc_rack') == 'on',
            'categories': request.form.get('item_categories') == 'on',
            'footprints': request.form.get('item_footprint') == 'on',
            'tags': request.form.get('item_tags') == 'on',
            'project_categories': request.form.get('proj_categories') == 'on',
            'project_tags': request.form.get('proj_tags') == 'on',
            'project_statuses': request.form.get('proj_status') == 'on',
            'contact_persons': request.form.get('contact_persons') == 'on',
            'contact_organizations': request.form.get('contact_orgs') == 'on',
            'contact_groups': request.form.get('contact_groups') == 'on',
            'system_settings': request.form.get('system_settings') == 'on',
        }

        if not any(v for v in selections.values()):
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



