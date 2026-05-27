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
    all_items = Item.query.all()
    items = [i for i in all_items if i.is_low_stock() or i.is_no_stock()]
    items.sort(key=lambda x: x.get_overall_quantity())
    return render_template('low_stock.html', items=items)



@report_bp.route('/reports', endpoint='reports')
@login_required
def reports():
    if not current_user.has_permission('settings_sections.reports', 'view'):
        flash('You do not have permission to view reports.', 'danger')
        return redirect(url_for('settings.settings'))

    from models import ItemBatch, Project, ProjectStatus, BatchLendRecord, LendingSession, ProjectBOMItem

    sections = {}

    # ── Inventory ──────────────────────────────────────────────────────────────
    if current_user.has_permission('items', 'view'):
        all_items = Item.query.all()
        total_value = db.session.query(
            db.func.sum(ItemBatch.price_per_unit * ItemBatch.quantity)
        ).scalar() or 0

        category_stats = db.session.query(
            Category.name,
            db.func.count(Item.id).label('count')
        ).join(Item).group_by(Category.name).order_by(db.func.count(Item.id).desc()).all()

        footprint_stats = db.session.query(
            Footprint.name,
            db.func.count(Item.id).label('count')
        ).join(Item).group_by(Footprint.name).order_by(db.func.count(Item.id).desc()).limit(10).all()

        sections['inventory'] = {
            'total_items':    len(all_items),
            'low_stock':      sum(1 for i in all_items if i.is_low_stock()),
            'no_stock':       sum(1 for i in all_items if i.is_no_stock()),
            'total_batches':  ItemBatch.query.count(),
            'total_value':    total_value,
            'category_stats': category_stats,
            'footprint_stats': footprint_stats,
        }

    # ── Lending & Return ────────────────────────────────────────────────────────
    if current_user.has_permission('lending_return', 'view_log'):
        now = datetime.now(timezone.utc).replace(tzinfo=None)
        active_records = BatchLendRecord.query.filter(BatchLendRecord.returned_at.is_(None)).all()
        overdue = [r for r in active_records if r.lend_end and r.lend_end < now]
        unique_items = set(r.batch.item_id for r in active_records if r.batch)
        recent_sessions = (LendingSession.query
                           .filter_by(mode='lend')
                           .order_by(LendingSession.created_at.desc())
                           .limit(10).all())
        sections['lending'] = {
            'active_records':    len(active_records),
            'overdue_count':     len(overdue),
            'total_lent_qty':    sum(r.quantity for r in active_records),
            'unique_items_lent': len(unique_items),
            'recent_sessions':   recent_sessions,
        }

    # ── Projects ───────────────────────────────────────────────────────────────
    if current_user.has_permission('projects', 'view'):
        today = datetime.now(timezone.utc).date()
        has_statuses = ProjectStatus.query.first() is not None
        sections['projects'] = {
            'total':       Project.query.count(),
            'active':      (Project.query.join(ProjectStatus)
                            .filter(ProjectStatus.name.ilike('%active%')).count()
                            if has_statuses else 0),
            'completed':   (Project.query.join(ProjectStatus)
                            .filter(ProjectStatus.name.ilike('%complete%')).count()
                            if has_statuses else 0),
            'overdue':     Project.query.filter(
                               Project.date_end < today,
                               Project.date_end.isnot(None)
                           ).count(),
            'bom_entries': ProjectBOMItem.query.count(),
        }

    # ── Storage ────────────────────────────────────────────────────────────────
    if current_user.has_permission('pages.visual_storage', 'view'):
        all_racks = Rack.query.all()
        total_drawers = sum(r.rows * r.cols for r in all_racks)
        occupied = set(
            db.session.query(Item.rack_id, Item.drawer)
            .filter(Item.rack_id.isnot(None), Item.drawer.isnot(None)).all()
        ) | set(
            db.session.query(ItemBatch.rack_id, ItemBatch.drawer)
            .filter(ItemBatch.rack_id.isnot(None), ItemBatch.drawer.isnot(None),
                    ItemBatch.follow_main_location == False).all()
        )
        sections['storage'] = {
            'total_racks':     len(all_racks),
            'total_drawers':   total_drawers,
            'occupied_drawers': len(occupied),
            'empty_drawers':   max(0, total_drawers - len(occupied)),
        }

    # ── Recent Activity ────────────────────────────────────────────────────────
    recent_activity = (AuditLog.query
                       .order_by(AuditLog.created_at.desc())
                       .limit(15).all())

    return render_template('reports.html', sections=sections, recent_activity=recent_activity)

# ============= LOCATION MANAGEMENT ROUTES =============



