"""
User Role Routes Blueprint
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

user_role_bp = Blueprint('user_role', __name__)


@user_role_bp.route('/users', endpoint='users')
@login_required
def users():
    # Check granular permission for user management
    if not current_user.has_permission('settings_sections.users_roles', 'view'):
        flash('You do not have permission to view users.', 'danger')
        return redirect(url_for('settings.settings'))
    
    from models import Setting, Role
    users = User.query.order_by(User.username).all()
    roles = Role.query.order_by(Role.name).all()
    signup_enabled = Setting.get('signup_enabled', True)
    
    can_create_user = current_user.has_permission('settings_sections.users_roles', 'users_create')
    can_edit_user = current_user.has_permission('settings_sections.users_roles', 'users_edit')
    can_delete_user = current_user.has_permission('settings_sections.users_roles', 'users_delete')
    can_create_role = current_user.has_permission('settings_sections.users_roles', 'roles_create')
    can_edit_role = current_user.has_permission('settings_sections.users_roles', 'roles_edit')
    can_delete_role = current_user.has_permission('settings_sections.users_roles', 'roles_delete')
    
    return render_template('users.html', 
                          users=users, 
                          roles=roles, 
                          signup_enabled=signup_enabled,
                          can_create_user=can_create_user,
                          can_edit_user=can_edit_user,
                          can_delete_user=can_delete_user,
                          can_create_role=can_create_role,
                          can_edit_role=can_edit_role,
                          can_delete_role=can_delete_role)



@user_role_bp.route('/toggle-signup', endpoint='toggle_signup', methods=['POST'])
@login_required
@permission_required("settings_sections.users_roles", "users_edit")
def toggle_signup():
    from models import Setting
    signup_enabled = request.form.get('signup_enabled') == 'on'
    Setting.set('signup_enabled', signup_enabled, 'Enable/disable user signup form')
    
    status = 'enabled' if signup_enabled else 'disabled'
    flash(f'User signup form has been {status}.', 'success')
    log_audit(current_user.id, 'update', 'setting', 0, f'Signup form {status}')
    return redirect(url_for('user_role.users'))


@user_role_bp.route('/change-password', endpoint='change_password', methods=['POST'])
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



@user_role_bp.route('/user/new', endpoint='user_new', methods=['GET', 'POST'])
@login_required
@permission_required("settings_sections.users_roles", "users_create")
def user_new():
    form = UserForm()
    
    if form.validate_on_submit():
        # Check for duplicate username or email
        existing_username = User.query.filter_by(username=form.username.data).first()
        existing_email = User.query.filter_by(email=form.email.data).first()
        
        if existing_username:
            flash(f'Username "{form.username.data}" already exists!', 'danger')
            return render_template('user_form.html', form=form, title='New User')
        
        if existing_email:
            flash(f'Email "{form.email.data}" already registered!', 'danger')
            return render_template('user_form.html', form=form, title='New User')
        
        user = User(
            username=form.username.data,
            email=form.email.data,
            role_id=form.role_id.data,
            is_active=form.is_active.data,
            max_login_attempts=form.max_login_attempts.data or 0,
            allow_password_reset=form.allow_password_reset.data,
            auto_unlock_enabled=form.auto_unlock_enabled.data,
            auto_unlock_minutes=form.auto_unlock_minutes.data
        )
        user.set_password(form.password.data)
        
        # Handle profile photo upload
        if form.profile_photo.data:
            file = form.profile_photo.data
            if file and allowed_file(file.filename, {'png', 'jpg', 'jpeg'}):
                # Check file size (max 1MB)
                file.seek(0, os.SEEK_END)
                file_size = file.tell()
                file.seek(0)
                
                if file_size > 1024 * 1024:  # 1MB
                    flash('Profile photo must be smaller than 1MB', 'danger')
                    return render_template('user_form.html', form=form, title='New User')
                
                # Save with username as filename - sanitize extension
                ext = secure_filename(file.filename.rsplit('.', 1)[1].lower())
                filename = f"{secure_filename(form.username.data)}.{ext}"
                filepath = os.path.join(current_app.config['UPLOAD_FOLDER'], 'userpicture', filename)
                file.save(filepath)
                user.profile_photo = filename
        
        db.session.add(user)
        db.session.commit()
        
        log_audit(current_user.id, 'create', 'user', user.id, f'Created user: {user.username}')
        flash(f'User "{user.username}" created successfully!', 'success')
        return redirect(url_for('user_role.users'))
    
    return render_template('user_form.html', form=form, title='New User')



@user_role_bp.route('/user/<int:id>/edit', endpoint='user_edit', methods=['GET', 'POST'])
@login_required
@permission_required("settings_sections.users_roles", "users_edit")
def user_edit(id):
    user = User.query.get_or_404(id)
    
    if user.is_demo_user and current_app.config.get('DEMO_MODE', False):
        flash('Cannot modify admin user profile in demo mode.', 'warning')
        return redirect(url_for('user_role.users'))
    
    form = UserForm()
    
    if form.validate_on_submit():
        # Check for action button clicks first
        action = request.form.get('action')
        
        # Handle profile photo delete (stay on form)
        if action == 'delete_photo':
            if user.profile_photo:
                filepath = os.path.join(current_app.config['UPLOAD_FOLDER'], 'userpicture', user.profile_photo)
                if is_safe_file_path(filepath) and os.path.exists(filepath):
                    os.remove(filepath)
                user.profile_photo = None
                log_audit(current_user.id, 'update', 'user', user.id, f'Deleted profile photo for user: {user.username}')
                db.session.commit()
                flash('Profile photo deleted successfully!', 'success')
            return redirect(url_for('user_role.user_edit', id=user.id))
        
        # Handle profile photo upload (stay on form)
        elif action == 'upload_photo':
            if form.profile_photo.data:
                file = form.profile_photo.data
                if file and allowed_file(file.filename, {'png', 'jpg', 'jpeg'}):
                    # Check file size (max 1MB)
                    file.seek(0, os.SEEK_END)
                    file_size = file.tell()
                    file.seek(0)
                    
                    if file_size > 1024 * 1024:  # 1MB
                        flash('Profile photo must be smaller than 1MB', 'danger')
                        return render_template('user_form.html', form=form, user=user, title='Edit User', config=current_app.config)
                    
                    # Delete old photo if exists
                    if user.profile_photo:
                        old_file = os.path.join(current_app.config['UPLOAD_FOLDER'], 'userpicture', user.profile_photo)
                        if is_safe_file_path(old_file) and os.path.exists(old_file):
                            os.remove(old_file)

                    # Save with username as filename - sanitize extension
                    ext = secure_filename(file.filename.rsplit('.', 1)[1].lower())
                    filename = f"{secure_filename(form.username.data)}.{ext}"
                    filepath = os.path.join(current_app.config['UPLOAD_FOLDER'], 'userpicture', filename)
                    file.save(filepath)
                    user.profile_photo = filename
                    log_audit(current_user.id, 'update', 'user', user.id, f'Updated profile photo for user: {user.username}')
                    db.session.commit()
                    flash('Profile photo uploaded successfully!', 'success')
                else:
                    flash('Only PNG and JPEG files are allowed.', 'danger')
            return redirect(url_for('user_role.user_edit', id=user.id))
        
        # Regular form submission (full user edit)
        user.username = form.username.data
        user.email = form.email.data
        user.role_id = form.role_id.data
        user.is_active = form.is_active.data
        user.max_login_attempts = form.max_login_attempts.data or 0
        user.allow_password_reset = form.allow_password_reset.data
        user.auto_unlock_enabled = form.auto_unlock_enabled.data
        user.auto_unlock_minutes = form.auto_unlock_minutes.data
        
        # Check if admin is unlocking the account
        unlock_account = request.form.get('unlock_account')
        if unlock_account and user.account_locked_until:
            user.account_locked_until = None
            user.failed_login_attempts = 0
            from datetime import timezone as tz_module
            timestamp = datetime.now(tz_module.utc).strftime('%Y-%m-%d %H:%M:%S UTC')
            log_audit(current_user.id, 'update', 'user', user.id, f'{current_user.username} manually unlock: {user.username} on {timestamp}')
            flash(f'Account "{user.username}" has been unlocked.', 'success')
        
        if form.password.data:
            user.set_password(form.password.data)
        
        db.session.commit()
        
        log_audit(current_user.id, 'update', 'user', user.id, f'Updated user: {user.username}')
        flash(f'User "{user.username}" updated successfully!', 'success')
        return redirect(url_for('user_role.users'))
    else:
        # Pre-populate form fields on GET request (for display)
        form.username.data = user.username
        form.email.data = user.email
        form.role_id.data = user.role_id
        form.is_active.data = user.is_active
        form.max_login_attempts.data = user.max_login_attempts
        form.allow_password_reset.data = user.allow_password_reset
        form.auto_unlock_enabled.data = user.auto_unlock_enabled
        form.auto_unlock_minutes.data = user.auto_unlock_minutes
    
    return render_template('user_form.html', form=form, user=user, title='Edit User', config=current_app.config)



@user_role_bp.route('/user/<int:id>/delete', endpoint='user_delete', methods=['POST'])
@login_required
@permission_required("settings_sections.users_roles", "users_delete")
def user_delete(id):
    if id == current_user.id:
        flash('You cannot delete your own account.', 'danger')
        return redirect(url_for('user_role.users'))
    
    user = User.query.get_or_404(id)
    
    if user.is_demo_user and current_app.config.get('DEMO_MODE', False):
        flash('Cannot delete admin user in demo mode.', 'warning')
        return redirect(url_for('user_role.users'))
    username = user.username
    
    db.session.delete(user)
    db.session.commit()
    
    log_audit(current_user.id, 'delete', 'user', id, f'Deleted user: {username}')
    flash(f'User "{username}" deleted successfully!', 'success')
    return redirect(url_for('user_role.users'))



@user_role_bp.route('/user/<int:id>/unlock', methods=['POST'])
@login_required
@permission_required("settings_sections.users_roles", "users_edit")
def user_unlock(id):
    """Unlock a locked user account"""
    user = User.query.get_or_404(id)
    
    if user.account_locked_until:
        user.account_locked_until = None
        user.failed_login_attempts = 0
        db.session.commit()
        
        from datetime import timezone as tz_module
        timestamp = datetime.now(tz_module.utc).strftime('%Y-%m-%d %H:%M:%S UTC')
        log_audit(current_user.id, 'update', 'user', user.id, f'{current_user.username} manually unlock: {user.username} on {timestamp}')
        flash(f'User "{user.username}" account unlocked successfully!', 'success')
    else:
        flash(f'User "{user.username}" account is not locked.', 'info')
    
    return redirect(url_for('user_role.users'))

# ============= ROLE MANAGEMENT =============



@user_role_bp.route('/roles', endpoint='roles')
@login_required
def roles():
    """Redirect to users page - role management is now integrated there"""
    return redirect(url_for('user_role.users'))



@user_role_bp.route('/role/new', endpoint='role_new', methods=['GET', 'POST'])
@login_required
@permission_required("settings_sections.users_roles", "roles_create")
def role_new():
    from models import Role
    from forms import RoleForm
    form = RoleForm()
    
    if form.validate_on_submit():
        # Check for duplicate role name
        existing_role = Role.query.filter_by(name=form.name.data).first()
        if existing_role:
            flash(f'Role "{form.name.data}" already exists!', 'danger')
            return render_template('role_form.html', form=form, title='New Role', role=None)
        
        # Create new role with default permissions (all false)
        default_perms = {
            # Item Management (granular)
            "items": {
                "view": False, 
                "create": False,
                "delete": False, 
                "edit_name": False,
                "edit_sku_type": False,
                "edit_description": False,
                "edit_datasheet": False,
                "edit_upload": False,
                "edit_lending": False,
                "edit_price": False, 
                "edit_quantity": False, 
                "edit_location": False,
                "edit_category": False,
                "edit_footprint": False,
                "edit_tags": False,
                "edit_parameters": False
            },
            # Page Permissions
            "pages": {
                "visual_storage": {"view": False},
                "notifications": {"view": False}
            },
            # Settings Page Sections
            "settings_sections": {
                "system_settings": {"view": False, "edit": False},
                "reports": {"view": False},
                "item_management": {"view": False, "edit": False, "delete": False},
                "magic_parameters": {"view": False, "edit": False, "delete": False},
                "location_management": {"view": False, "edit": False, "delete": False},
                "qr_templates": {"view": False, "edit": False, "delete": False},
                "users_roles": {
                    "view": False,
                    "roles_create": False,
                    "roles_edit": False,
                    "roles_delete": False,
                    "users_create": False,
                    "users_edit": False,
                    "users_delete": False
                },
                "backup_restore": {"view": False, "upload_export": False, "delete": False}
            }
        }
        
        role = Role(
            name=form.name.data,
            description=form.description.data,
            is_system_role=False
        )
        role.set_permissions(default_perms)
        db.session.add(role)
        db.session.commit()
        
        log_audit(current_user.id, 'create', 'role', role.id, f'Created role: {role.name}')
        flash(f'Role "{role.name}" created successfully! Now configure its permissions.', 'success')
        return redirect(url_for('user_role.role_edit', id=role.id))
    
    return render_template('role_form.html', form=form, title='New Role', role=None)



@user_role_bp.route('/role/<int:id>/edit', endpoint='role_edit', methods=['GET', 'POST'])
@login_required
@permission_required("settings_sections.users_roles", "roles_edit")
def role_edit(id):
    from models import Role
    from forms import RoleForm
    role = Role.query.get_or_404(id)
    
    form = RoleForm(obj=role)
    
    if request.method == 'POST':
        if 'update_info' in request.form:
            # Update role name and description
            if form.validate_on_submit():
                role.name = form.name.data
                role.description = form.description.data
                db.session.commit()
                log_audit(current_user.id, 'update', 'role', role.id, f'Updated role info: {role.name}')
                flash(f'Role "{role.name}" updated successfully!', 'success')
        
        if 'update_permissions' in request.form:
            # Update permissions with new structure
            perms = {
                "items": {},
                "pages": {},
                "settings_sections": {}
            }
            
            # Items permissions (granular)
            item_actions = ['view', 'create', 'delete', 'edit_name', 'edit_sku_type', 'edit_description', 
                           'edit_datasheet', 'edit_upload', 'edit_lending', 'edit_price', 'edit_quantity', 
                           'edit_location', 'edit_category', 'edit_footprint', 'edit_tags', 'edit_parameters']
            for action in item_actions:
                checkbox_name = f'items_{action}'
                perms['items'][action] = checkbox_name in request.form
            
            # Page permissions (Settings page removed - accessible to all users)
            # Visual Storage and Notifications edit controlled by settings_sections
            perms['pages']['visual_storage'] = {
                'view': 'pages_visual_storage_view' in request.form
            }
            perms['pages']['notifications'] = {
                'view': 'pages_notifications_view' in request.form
            }
            
            # Settings sections permissions
            # System Settings
            perms['settings_sections']['system_settings'] = {
                'view': 'settings_sections_system_settings_view' in request.form,
                'edit': 'settings_sections_system_settings_edit' in request.form
            }
            
            # Reports
            perms['settings_sections']['reports'] = {
                'view': 'settings_sections_reports_view' in request.form
            }
            
            # Item Management
            perms['settings_sections']['item_management'] = {
                'view': 'settings_sections_item_management_view' in request.form,
                'edit': 'settings_sections_item_management_edit' in request.form,
                'delete': 'settings_sections_item_management_delete' in request.form
            }
            
            # Magic Parameters
            perms['settings_sections']['magic_parameters'] = {
                'view': 'settings_sections_magic_parameters_view' in request.form,
                'edit': 'settings_sections_magic_parameters_edit' in request.form,
                'delete': 'settings_sections_magic_parameters_delete' in request.form
            }
            
            # Location Management
            perms['settings_sections']['location_management'] = {
                'view': 'settings_sections_location_management_view' in request.form,
                'edit': 'settings_sections_location_management_edit' in request.form,
                'delete': 'settings_sections_location_management_delete' in request.form
            }
            
            # QR/Barcode Templates
            perms['settings_sections']['qr_templates'] = {
                'view': 'settings_sections_qr_templates_view' in request.form,
                'edit': 'settings_sections_qr_templates_edit' in request.form,
                'delete': 'settings_sections_qr_templates_delete' in request.form
            }
            
            # User & Role Management
            perms['settings_sections']['users_roles'] = {
                'view': 'settings_sections_users_roles_view' in request.form,
                'roles_create': 'settings_sections_users_roles_roles_create' in request.form,
                'roles_edit': 'settings_sections_users_roles_roles_edit' in request.form,
                'roles_delete': 'settings_sections_users_roles_roles_delete' in request.form,
                'users_create': 'settings_sections_users_roles_users_create' in request.form,
                'users_edit': 'settings_sections_users_roles_users_edit' in request.form,
                'users_delete': 'settings_sections_users_roles_users_delete' in request.form
            }
            
            # Backup & Restore
            perms['settings_sections']['backup_restore'] = {
                'view': 'settings_sections_backup_restore_view' in request.form,
                'upload_export': 'settings_sections_backup_restore_upload_export' in request.form,
                'delete': 'settings_sections_backup_restore_delete' in request.form
            }
            
            role.set_permissions(perms)
            db.session.commit()
            
            log_audit(current_user.id, 'update', 'role', role.id, f'Updated permissions for role: {role.name}')
            flash(f'Permissions for role "{role.name}" updated successfully!', 'success')
        
        if 'update_info' in request.form or 'update_permissions' in request.form:
            # Reload the role from database and re-render the form
            db.session.refresh(role)
            form = RoleForm(obj=role)
            return render_template('role_form.html', form=form, role=role, title='Edit Role')
    
    return render_template('role_form.html', form=form, role=role, title='Edit Role')



@user_role_bp.route('/role/<int:id>/delete', endpoint='role_delete', methods=['POST'])
@login_required
@permission_required("settings_sections.users_roles", "roles_delete")
def role_delete(id):
    from models import Role
    role = Role.query.get_or_404(id)
    
    # Prevent deleting system roles
    if role.is_system_role:
        flash('Cannot delete system role templates.', 'danger')
        return redirect(url_for('user_role.roles'))
    
    # Check if any users have this role
    if role.users:
        flash(f'Cannot delete role "{role.name}" because it is assigned to {len(role.users)} user(s).', 'danger')
        return redirect(url_for('user_role.roles'))
    
    role_name = role.name
    db.session.delete(role)
    db.session.commit()
    
    log_audit(current_user.id, 'delete', 'role', id, f'Deleted role: {role_name}')
    flash(f'Role "{role_name}" deleted successfully!', 'success')
    return redirect(url_for('user_role.roles'))



@user_role_bp.route('/role/<int:id>/clone', endpoint='role_clone', methods=['POST'])
@login_required
@permission_required("settings_sections.users_roles", "roles_create")
def role_clone(id):
    from models import Role
    source_role = Role.query.get_or_404(id)
    
    # Generate unique name for cloned role
    base_name = f"{source_role.name} (Copy)"
    new_name = base_name
    counter = 1
    while Role.query.filter_by(name=new_name).first():
        new_name = f"{base_name} {counter}"
        counter += 1
    
    # Clone the role
    new_role = Role(
        name=new_name,
        description=source_role.description,
        is_system_role=False,
        permissions=source_role.permissions
    )
    db.session.add(new_role)
    db.session.commit()
    
    log_audit(current_user.id, 'create', 'role', new_role.id, f'Cloned role from: {source_role.name}')
    flash(f'Role "{source_role.name}" cloned as "{new_name}". You can now customize it.', 'success')
    return redirect(url_for('user_role.role_edit', id=new_role.id))

# ============= REPORTS AND ANALYTICS =============



@user_role_bp.route('/uploads/userpicture/<filename>', endpoint='serve_user_picture')
def serve_user_picture(filename):
    """Serve user profile pictures"""
    return send_from_directory(os.path.join(current_app.config['UPLOAD_FOLDER'], 'userpicture'), filename)


# ============= ITEMS PRINT =============



