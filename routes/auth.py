"""
Auth Routes Blueprint
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

auth_bp = Blueprint('auth', __name__)


@auth_bp.route('/login', endpoint='login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('index'))
    
    from models import Setting
    signup_enabled = Setting.get('signup_enabled', True)
    demo_mode = current_app.config.get('DEMO_MODE', False)
    demo_username = current_app.config.get('DEMO_ADMIN_USERNAME', 'admin')
    demo_password = os.getenv('ADMIN_PASSWORD', 'admin123')
    
    form = LoginForm()
    if form.validate_on_submit():
        user = User.query.filter_by(username=form.username.data).first()

        if user and user.account_locked_until:
            from datetime import timezone as tz_module
            now_utc = datetime.now(tz_module.utc)
            locked_until = user.account_locked_until

            if locked_until.tzinfo is None:
                locked_until = locked_until.replace(tzinfo=tz_module.utc)

            if now_utc < locked_until:
                flash('Account is temporarily locked due to too many failed login attempts. Please try again later.', 'danger')
                return render_template('login.html', form=form, signup_enabled=signup_enabled,
                                     demo_mode=demo_mode, demo_username=demo_username,
                                     demo_password=demo_password)
            else:
                user.account_locked_until = None
                user.failed_login_attempts = 0
                db.session.commit()

        if user and user.check_password(form.password.data) and user.is_active:
            user.failed_login_attempts = 0
            user.account_locked_until = None
            db.session.commit()

            login_user(user, remember=form.remember_me.data)
            log_audit(user.id, 'login', 'user', user.id, 'User logged in')
            next_page = request.args.get('next')
            # Validate redirect URL to prevent open redirect attacks
            if next_page and is_safe_url(next_page):
                return redirect(next_page)
            return redirect(url_for('index'))
        else:
            if user:
                if user.max_login_attempts > 0:
                    user.failed_login_attempts += 1

                    if user.failed_login_attempts >= user.max_login_attempts:
                        from datetime import timedelta, timezone as tz_module
                        if user.auto_unlock_enabled:
                            user.account_locked_until = datetime.now(tz_module.utc) + timedelta(minutes=user.auto_unlock_minutes)
                            unlock_msg = f"Try again in {user.auto_unlock_minutes} minutes."
                        else:
                            user.account_locked_until = datetime.now(tz_module.utc) + timedelta(days=365*10)
                            unlock_msg = "Contact administrator to unlock."
                        db.session.commit()
                        log_audit(user.id, 'login_failed_locked', 'user', user.id,
                                f'Account locked after {user.failed_login_attempts} failed attempts')
                        flash(f'Account locked due to {user.max_login_attempts} failed login attempts. {unlock_msg}', 'danger')
                        return render_template('login.html', form=form, signup_enabled=signup_enabled,
                                             demo_mode=demo_mode, demo_username=demo_username,
                                             demo_password=demo_password)
                    else:
                        db.session.commit()
                        remaining = user.max_login_attempts - user.failed_login_attempts
                        log_audit(user.id, 'login_failed', 'user', user.id,
                                f'Failed login attempt {user.failed_login_attempts}/{user.max_login_attempts}')
                        flash(f'Invalid username or password. {remaining} attempt(s) remaining before account lock.', 'danger')
                else:
                    log_audit(user.id, 'login_failed', 'user', user.id, 'Failed login attempt')
                    flash('Invalid username or password, or account is inactive.', 'danger')
            else:
                flash('Invalid username or password, or account is inactive.', 'danger')
    
    return render_template('login.html', form=form, signup_enabled=signup_enabled, 
                         demo_mode=demo_mode, demo_username=demo_username, 
                         demo_password=demo_password)



@auth_bp.route('/logout', endpoint='logout')
@login_required
def logout():
    log_audit(current_user.id, 'logout', 'user', current_user.id, 'User logged out')
    logout_user()
    flash('You have been logged out.', 'info')
    return redirect(url_for('auth.login'))



@auth_bp.route('/register', endpoint='register', methods=['GET', 'POST'])
def register():
    from models import Setting, Role
    signup_enabled = Setting.get('signup_enabled', True)
    
    if not signup_enabled:
        flash('User registration is currently disabled.', 'warning')
        return redirect(url_for('auth.login'))
    
    if current_user.is_authenticated:
        return redirect(url_for('index'))
    
    form = RegistrationForm()
    if form.validate_on_submit():
        # Get Viewer role as default for new registrations
        viewer_role = Role.query.filter_by(name='Viewer').first()
        if not viewer_role:
            flash('System error: Default role not found. Please contact administrator.', 'danger')
            return redirect(url_for('auth.login'))
        
        user = User(
            username=form.username.data,
            email=form.email.data,
            role_id=viewer_role.id
        )
        user.set_password(form.password.data)
        db.session.add(user)
        db.session.commit()
        
        flash('Registration successful! Please log in.', 'success')
        return redirect(url_for('auth.login'))
    
    return render_template('register.html', form=form)

# ============= CONTEXT PROCESSOR =============



@auth_bp.route('/verify-password', endpoint='verify_password', methods=['POST'])
@login_required
def verify_password():
    """Verify user's password"""
    try:
        data = request.get_json()
        password = data.get('password', '')
        
        if not password:
            return jsonify({'success': False, 'message': 'Password is required.'}), 400
        
        # Check password
        if current_user.check_password(password):
            return jsonify({'success': True, 'message': 'Password verified.'}), 200
        else:
            return jsonify({'success': False, 'message': 'Incorrect password. Please try again.'}), 401
            
    except Exception as e:
        logging.error(f"Error verifying password: {e}")
        return jsonify({'success': False, 'message': 'An error occurred.'}), 500



