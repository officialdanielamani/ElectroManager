"""
Report Routes Blueprint
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

report_bp = Blueprint('report', __name__)


@report_bp.route('/low-stock', endpoint='low_stock')
@login_required
def low_stock():
    items = Item.query.filter(Item.quantity <= Item.min_quantity).order_by(Item.quantity).all()
    return render_template('low_stock.html', items=items)



@report_bp.route('/reports', endpoint='reports')
@login_required
def reports():
    # Check granular permission for reports
    if not current_user.has_permission('settings_sections.reports', 'view'):
        flash('You do not have permission to view reports.', 'danger')
        return redirect(url_for('settings.settings'))
    
    total_items = Item.query.count()
    total_value = db.session.query(db.func.sum(Item.price * Item.quantity)).scalar() or 0
    low_stock_count = Item.query.filter(Item.quantity <= Item.min_quantity).count()
    
    category_stats = db.session.query(
        Category.name,
        db.func.count(Item.id).label('count')
    ).join(Item).group_by(Category.name).all()
    
    return render_template('reports.html',
                         total_items=total_items,
                         total_value=total_value,
                         low_stock_count=low_stock_count,
                         category_stats=category_stats)

# ============= LOCATION MANAGEMENT ROUTES =============



