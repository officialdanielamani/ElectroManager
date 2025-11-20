"""
Notification Routes Blueprint
"""
from flask import Blueprint, render_template, redirect, url_for, flash, request, jsonify, send_file, abort
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

notification_bp = Blueprint('notification', __name__)


@notification_bp.route('/notifications', endpoint='notifications')
@login_required
def notifications():
    """Show items with date parameter notifications due"""
    from models import ItemParameter
    from datetime import datetime
    
    # Check view permission
    if not current_user.has_permission('pages.notifications', 'view'):
        flash('You do not have permission to view notifications.', 'danger')
        return redirect(url_for('index'))
    
    # Check if user can edit notifications
    can_edit = current_user.has_permission('pages.notifications', 'edit')
    
    # Get all item parameters with notifications enabled
    notifications = []
    params = ItemParameter.query.join(ItemParameter.parameter).filter(
        ItemParameter.parameter.has(param_type='date'),
        ItemParameter.parameter.has(notify_enabled=True)
    ).all()
    
    today = datetime.now().date()
    
    for param in params:
        try:
            if param.operation in ['value', 'start', 'end'] and param.value:
                param_date = datetime.strptime(param.value, '%Y-%m-%d').date()
                if param_date == today:
                    notifications.append({
                        'item': param.item,
                        'parameter': param,
                        'message': f"{param.parameter.name} is due today",
                        'type': 'due'
                    })
                elif param_date < today:
                    notifications.append({
                        'item': param.item,
                        'parameter': param,
                        'message': f"{param.parameter.name} is overdue",
                        'type': 'overdue'
                    })
            elif param.operation == 'duration' and param.value and param.value2:
                start_date = datetime.strptime(param.value, '%Y-%m-%d').date()
                end_date = datetime.strptime(param.value2, '%Y-%m-%d').date()
                if start_date <= today <= end_date:
                    notifications.append({
                        'item': param.item,
                        'parameter': param,
                        'message': f"{param.parameter.name} is active",
                        'type': 'active'
                    })
        except:
            pass
    
    return render_template('notifications.html', notifications=notifications, can_edit_notifications=can_edit)


# ============= USER PROFILE PICTURES =============



