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

    # --- Batch lend record notifications (user-specific: only show to the borrower) ---
    from models import BatchLendRecord
    lend_recs_with_notify = BatchLendRecord.query.filter(
        BatchLendRecord.lend_notify_enabled == True,
        BatchLendRecord.lend_end.isnot(None),
        BatchLendRecord.returned_at.is_(None),
        BatchLendRecord.lend_to_type == 'user',
        BatchLendRecord.lend_to_id == current_user.id,
    ).all()

    for rec in lend_recs_with_notify:
        try:
            batch = rec.batch
            if not batch or not batch.item:
                continue
            days_before = rec.lend_notify_before_days or 3
            lend_end_date = rec.lend_end.date() if rec.lend_end else None
            if not lend_end_date:
                continue
            remind_date = lend_end_date - timedelta(days=days_before)
            session_label = rec.lending_session.lending_id if rec.lending_session else '—'
            if lend_end_date < today:
                notifications.append({
                    'item': batch.item, 'batch': batch, 'rec': rec,
                    'session_label': session_label,
                    'message': f"The item you borrowed is overdue (due {lend_end_date.strftime('%d/%m/%Y')})",
                    'type': 'lend_overdue',
                })
            elif lend_end_date == today:
                notifications.append({
                    'item': batch.item, 'batch': batch, 'rec': rec,
                    'session_label': session_label,
                    'message': f"You have items to return today ({lend_end_date.strftime('%d/%m/%Y')})",
                    'type': 'lend_due',
                })
            elif remind_date <= today:
                days_left = (lend_end_date - today).days
                notifications.append({
                    'item': batch.item, 'batch': batch, 'rec': rec,
                    'session_label': session_label,
                    'message': f"You have items to return before {lend_end_date.strftime('%d/%m/%Y')} ({days_left} day(s) left)",
                    'type': 'lend_soon',
                })
        except Exception:
            pass

    # --- SN-level lending notifications (user-specific) ---
    sns_with_notify = BatchSerialNumber.query.filter(
        BatchSerialNumber.lend_notify_enabled == True,
        BatchSerialNumber.lend_end.isnot(None),
        BatchSerialNumber.lend_to_id == current_user.id,
        BatchSerialNumber.lend_to_type == 'user',
    ).all()

    for sn in sns_with_notify:
        try:
            batch = sn.batch
            if not batch or not batch.item:
                continue
            days_before = sn.lend_notify_before_days or 3
            lend_end_date = sn.lend_end.date() if sn.lend_end else None
            if not lend_end_date:
                continue
            remind_date = lend_end_date - timedelta(days=days_before)
            session_label = sn.lending_session.lending_id if sn.lending_session else '—'
            if lend_end_date < today:
                notifications.append({
                    'item': batch.item, 'batch': batch, 'sn': sn,
                    'session_label': session_label,
                    'message': f"The item you borrowed is overdue (due {lend_end_date.strftime('%d/%m/%Y')})",
                    'type': 'lend_overdue',
                })
            elif lend_end_date == today:
                notifications.append({
                    'item': batch.item, 'batch': batch, 'sn': sn,
                    'session_label': session_label,
                    'message': f"You have items to return today ({lend_end_date.strftime('%d/%m/%Y')})",
                    'type': 'lend_due',
                })
            elif remind_date <= today:
                days_left = (lend_end_date - today).days
                notifications.append({
                    'item': batch.item, 'batch': batch, 'sn': sn,
                    'session_label': session_label,
                    'message': f"You have items to return before {lend_end_date.strftime('%d/%m/%Y')} ({days_left} day(s) left)",
                    'type': 'lend_soon',
                })
        except Exception:
            pass

    # --- Project deadline notifications ---
    from models import Project
    projects_with_notify = Project.query.filter(
        Project.enable_dateline_notification == True,
        Project.date_end.isnot(None),
    ).all()
    for proj in projects_with_notify:
        try:
            days_before = proj.notify_before_days or 3
            end_date = proj.date_end
            remind_date = end_date - timedelta(days=days_before)
            if end_date < today:
                notifications.append({
                    'project': proj,
                    'item': None,
                    'message': f'Project "{proj.name}" deadline has passed ({end_date.strftime("%d/%m/%Y")})',
                    'type': 'project_overdue',
                })
            elif end_date == today:
                notifications.append({
                    'project': proj,
                    'item': None,
                    'message': f'Project "{proj.name}" is due today ({end_date.strftime("%d/%m/%Y")})',
                    'type': 'project_due',
                })
            elif remind_date <= today:
                days_left = (end_date - today).days
                notifications.append({
                    'project': proj,
                    'item': None,
                    'message': f'Project "{proj.name}" deadline in {days_left} day(s) ({end_date.strftime("%d/%m/%Y")})',
                    'type': 'project_soon',
                })
        except Exception:
            pass

    return render_template('notifications.html', notifications=notifications, can_edit_notifications=can_edit)


# ============= USER PROFILE PICTURES =============



