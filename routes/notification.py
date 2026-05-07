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
    """Show items with date parameter notifications due, plus lending deadline reminders."""
    from models import ItemParameter, ItemBatch, BatchSerialNumber, Item
    from datetime import datetime, timedelta

    if not current_user.has_permission('pages.notifications', 'view'):
        flash('You do not have permission to view notifications.', 'danger')
        return redirect(url_for('index'))

    can_edit = current_user.has_permission('pages.notifications', 'edit')

    notifications = []
    today = datetime.now().date()

    # --- Parameter-based date notifications ---
    params = ItemParameter.query.join(ItemParameter.parameter).filter(
        ItemParameter.parameter.has(param_type='date'),
        ItemParameter.parameter.has(notify_enabled=True)
    ).all()

    for param in params:
        try:
            if param.operation in ['value', 'start', 'end'] and param.value:
                param_date = datetime.strptime(param.value, '%Y-%m-%d').date()
                if param_date == today:
                    notifications.append({'item': param.item, 'parameter': param,
                                          'message': f"{param.parameter.name} is due today", 'type': 'due'})
                elif param_date < today:
                    notifications.append({'item': param.item, 'parameter': param,
                                          'message': f"{param.parameter.name} is overdue", 'type': 'overdue'})
            elif param.operation == 'duration' and param.value and param.value2:
                start_date = datetime.strptime(param.value, '%Y-%m-%d').date()
                end_date = datetime.strptime(param.value2, '%Y-%m-%d').date()
                if start_date <= today <= end_date:
                    notifications.append({'item': param.item, 'parameter': param,
                                          'message': f"{param.parameter.name} is active", 'type': 'active'})
        except Exception:
            pass

    # --- Batch lend record notifications ---
    from models import BatchLendRecord
    lend_recs_with_notify = BatchLendRecord.query.filter(
        BatchLendRecord.lend_notify_enabled == True,
        BatchLendRecord.lend_end.isnot(None),
    ).all()

    for rec in lend_recs_with_notify:
        try:
            batch = rec.batch
            if not batch or not batch.item:
                continue
            days_before = rec.lend_notify_before_days or 3
            remind_date = rec.lend_end - timedelta(days=days_before)
            lend_label = rec.get_lend_to_display() or 'Unknown'
            if rec.lend_end < today:
                notifications.append({
                    'item': batch.item, 'batch': batch,
                    'message': f"Lending to {lend_label} (qty {rec.quantity}) was due {rec.lend_end.strftime('%d/%m/%Y')} (overdue)",
                    'type': 'lend_overdue',
                })
            elif rec.lend_end == today:
                notifications.append({
                    'item': batch.item, 'batch': batch,
                    'message': f"Lending to {lend_label} (qty {rec.quantity}) ends today",
                    'type': 'lend_due',
                })
            elif remind_date <= today:
                days_left = (rec.lend_end - today).days
                notifications.append({
                    'item': batch.item, 'batch': batch,
                    'message': f"Lending to {lend_label} (qty {rec.quantity}) ends in {days_left} day(s) ({rec.lend_end.strftime('%d/%m/%Y')})",
                    'type': 'lend_soon',
                })
        except Exception:
            pass

    # --- SN-level lending notifications ---
    sns_with_notify = BatchSerialNumber.query.filter(
        BatchSerialNumber.lend_notify_enabled == True,
        BatchSerialNumber.lend_end.isnot(None),
        BatchSerialNumber.lend_to_id.isnot(None),
    ).all()

    for sn in sns_with_notify:
        try:
            batch = sn.batch
            if not batch or not batch.item:
                continue
            days_before = sn.lend_notify_before_days or 3
            remind_date = sn.lend_end - timedelta(days=days_before)
            lend_label = sn.get_lend_to_display() or 'Unknown'
            sn_ref = sn.serial_number or sn.internal_serial_number
            if sn.lend_end < today:
                notifications.append({
                    'item': batch.item,
                    'batch': batch,
                    'sn': sn,
                    'message': f"SN {sn_ref} lent to {lend_label} was due {sn.lend_end.strftime('%d/%m/%Y')} (overdue)",
                    'type': 'lend_overdue',
                })
            elif sn.lend_end == today:
                notifications.append({
                    'item': batch.item,
                    'batch': batch,
                    'sn': sn,
                    'message': f"SN {sn_ref} lent to {lend_label} ends today",
                    'type': 'lend_due',
                })
            elif remind_date <= today:
                days_left = (sn.lend_end - today).days
                notifications.append({
                    'item': batch.item,
                    'batch': batch,
                    'sn': sn,
                    'message': f"SN {sn_ref} lent to {lend_label} ends in {days_left} day(s) ({sn.lend_end.strftime('%d/%m/%Y')})",
                    'type': 'lend_soon',
                })
        except Exception:
            pass

    return render_template('notifications.html', notifications=notifications, can_edit_notifications=can_edit)


# ============= USER PROFILE PICTURES =============



