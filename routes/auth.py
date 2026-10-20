"""
Auth Routes Blueprint
"""
from flask import Blueprint, render_template, redirect, url_for, flash, request, jsonify, send_file, abort, current_app, session
from flask_login import login_required, current_user, login_user, logout_user
from extensions import limiter
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
import pyotp
import qrcode
import io
import base64

logger = logging.getLogger(__name__)

auth_bp = Blueprint('auth', __name__)


@auth_bp.route('/login', endpoint='login', methods=['GET', 'POST'])
@limiter.limit("20 per minute; 5 per second", methods=["POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('index'))
    
    from models import Setting
    signup_enabled = Setting.get('signup_enabled', True)
    demo_mode = current_app.config.get('DEMO_MODE', False)
    demo_username = current_app.config.get('DEMO_ADMIN_USERNAME', 'admin')
    demo_password = os.getenv('ADMIN_PASSWORD', 'admin123') if demo_mode else None
    
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

            # If MFA is enabled, stash user id and redirect to MFA challenge
            if user.mfa_enabled:
                session['mfa_pending_user_id'] = user.id
                session['mfa_remember_me'] = bool(form.remember_me.data)
                return redirect(url_for('auth.login_mfa'))

            login_user(user, remember=form.remember_me.data)
            log_audit(user.id, 'login', 'user', user.id, 'User logged in')
            next_page = request.args.get('next')
            # Prevent open redirects by mapping user input to trusted in-app destinations.
            allowed_next_paths = {
                '/': '/',
                '/dashboard': '/dashboard',
                '/items': '/items',
                '/categories': '/categories',
                '/racks': '/racks',
                '/locations': '/locations',
                '/settings': '/settings',
                '/profile': '/profile',
            }
            safe_next = allowed_next_paths.get(next_page)
            if safe_next:
                return redirect(safe_next)
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



@auth_bp.route('/login/mfa', endpoint='login_mfa', methods=['GET', 'POST'])
@limiter.limit("10 per minute; 3 per second", methods=["POST"])
def login_mfa():
    """TOTP MFA challenge step — only reachable after password check."""
    if current_user.is_authenticated:
        return redirect(url_for('index'))
    user_id = session.get('mfa_pending_user_id')
    if not user_id:
        return redirect(url_for('auth.login'))
    user = db.session.get(User, user_id)
    if not user:
        session.pop('mfa_pending_user_id', None)
        return redirect(url_for('auth.login'))

    error = None
    if request.method == 'POST':
        code = (request.form.get('totp_code') or '').strip().replace(' ', '')
        totp = pyotp.TOTP(user.mfa_secret)
        valid = totp.verify(code, valid_window=1)

        if not valid:
            # Check backup codes
            backup = _use_backup_code(user, code)
            if backup:
                valid = True
            else:
                log_audit(user.id, 'mfa_failed', 'user', user.id, 'MFA code rejected')
                error = 'Invalid authentication code. Please try again.'

        if valid:
            remember = session.pop('mfa_remember_me', False)
            session.pop('mfa_pending_user_id', None)
            login_user(user, remember=remember)
            log_audit(user.id, 'login', 'user', user.id, 'User logged in (MFA)')
            return redirect(url_for('index'))

    return render_template('login_mfa.html', error=error)


def _use_backup_code(user, code):
    """Consume a single-use backup code. Returns True if valid."""
    try:
        codes = json.loads(user.mfa_backup_codes or '[]')
    except (json.JSONDecodeError, TypeError):
        codes = []
    code = code.upper().replace('-', '').replace(' ', '')
    for stored in codes:
        if secrets.compare_digest(stored, code):
            codes.remove(stored)
            user.mfa_backup_codes = json.dumps(codes)
            db.session.commit()
            return True
    return False


@auth_bp.route('/register', endpoint='register', methods=['GET', 'POST'])
@limiter.limit("10 per minute; 3 per second", methods=["POST"])
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
        # Default new registrations to the least-privileged system role
        viewer_role = (Role.query.filter_by(name='Viewer').first()
                       or Role.query.filter_by(is_system_role=True).order_by(Role.id.desc()).first())
        if not viewer_role:
            flash('System error: No default role found. Please contact your administrator.', 'danger')
            return redirect(url_for('auth.login'))
        
        user = User(
            username=form.username.data,
            name=form.username.data,
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
@limiter.limit("10 per minute; 3 per second")
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





# ── MFA Setup Routes ────────────────────────────────────────────────────────

@auth_bp.route('/settings/mfa/setup', endpoint='mfa_setup', methods=['GET', 'POST'])
@login_required
def mfa_setup():
    """Begin TOTP setup: generate secret, show QR code."""
    if current_user.mfa_enabled:
        flash('Two-factor authentication is already enabled.', 'info')
        return redirect(url_for('settings.settings_general'))

    if request.method == 'POST':
        secret = request.form.get('mfa_secret', '').strip()
        code = request.form.get('totp_code', '').strip().replace(' ', '')
        if not secret or not code:
            flash('Missing data. Please try again.', 'danger')
            return redirect(url_for('auth.mfa_setup'))

        totp = pyotp.TOTP(secret)
        if not totp.verify(code, valid_window=1):
            flash('Invalid code. Please scan the QR code again and re-enter the 6-digit code.', 'danger')
            return redirect(url_for('auth.mfa_setup'))

        # Generate 8 backup codes (8 chars each, uppercase alphanumeric)
        backup_codes = [
            ''.join(secrets.choice(string.ascii_uppercase + string.digits) for _ in range(8))
            for _ in range(8)
        ]
        current_user.mfa_secret = secret
        current_user.mfa_enabled = True
        current_user.mfa_backup_codes = json.dumps(backup_codes)
        db.session.commit()
        log_audit(current_user.id, 'mfa_enabled', 'user', current_user.id, 'TOTP MFA enabled')
        flash('Two-factor authentication has been enabled.', 'success')
        return render_template('mfa_backup_codes.html', backup_codes=backup_codes)

    # GET — generate a fresh secret and QR code
    secret = pyotp.random_base32()
    app_name = Setting.get('system_name') or Setting.get('app_name') or 'ElectroManager'
    totp_uri = pyotp.TOTP(secret).provisioning_uri(
        name=current_user.email, issuer_name=app_name
    )
    # Build a data-URI QR image
    img = qrcode.make(totp_uri)
    buf = io.BytesIO()
    img.save(buf, format='PNG')
    qr_data = 'data:image/png;base64,' + base64.b64encode(buf.getvalue()).decode()
    return render_template('mfa_setup.html', secret=secret, qr_data=qr_data, totp_uri=totp_uri)


@auth_bp.route('/settings/mfa/disable', endpoint='mfa_disable', methods=['POST'])
@login_required
@limiter.limit("5 per minute")
def mfa_disable():
    """Disable MFA after confirming password."""
    password = (request.form.get('password') or '').strip()
    if not password or not current_user.check_password(password):
        flash('Incorrect password. MFA was not disabled.', 'danger')
        return redirect(url_for('settings.settings_general'))

    current_user.mfa_enabled = False
    current_user.mfa_secret = None
    current_user.mfa_backup_codes = None
    db.session.commit()
    log_audit(current_user.id, 'mfa_disabled', 'user', current_user.id, 'TOTP MFA disabled')
    flash('Two-factor authentication has been disabled.', 'warning')
    return redirect(url_for('settings.settings_general'))
