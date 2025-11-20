"""
Footprint Tag Routes Blueprint
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

footprint_tag_bp = Blueprint('footprint_tag', __name__)


@footprint_tag_bp.route('/api/footprint/add', methods=['POST'])
@login_required
@permission_required("settings_sections.item_management", "edit")
def api_add_footprint():
    """API endpoint to add footprint from item form"""
    try:
        data = request.get_json()
        name = data.get('name', '').strip()
        description = data.get('description', '').strip()
        color = data.get('color', '#6c757d')
        
        if not name:
            return jsonify({'success': False, 'error': 'Footprint name is required'})
        
        # Check if exists
        existing = Footprint.query.filter_by(name=name).first()
        if existing:
            return jsonify({'success': False, 'error': 'Footprint already exists'})
        
        footprint = Footprint(name=name, description=description, color=color)
        db.session.add(footprint)
        db.session.commit()
        
        log_audit(current_user.id, 'create', 'footprint', footprint.id, f'Created footprint: {footprint.name}')
        
        return jsonify({
            'success': True,
            'footprint': {'id': footprint.id, 'name': footprint.name, 'color': footprint.color}
        })
    except Exception as e:
        db.session.rollback()
        logging.error(f"Error adding footprint: {str(e)}")
        return jsonify({'success': False, 'error': 'An error occurred while adding the footprint'})



@footprint_tag_bp.route('/api/tag/add', methods=['POST'])
@login_required
@permission_required("settings_sections.item_management", "edit")
def api_add_tag():
    """API endpoint to add tag from item form"""
    try:
        data = request.get_json()
        name = data.get('name', '').strip()
        description = data.get('description', '').strip()
        color = data.get('color', '#6c757d')
        
        if not name:
            return jsonify({'success': False, 'error': 'Tag name is required'})
        
        # Check if exists
        existing = Tag.query.filter_by(name=name).first()
        if existing:
            return jsonify({'success': False, 'error': 'Tag already exists'})
        
        tag = Tag(name=name, description=description, color=color)
        db.session.add(tag)
        db.session.commit()
        
        log_audit(current_user.id, 'create', 'tag', tag.id, f'Created tag: {tag.name}')
        
        return jsonify({
            'success': True,
            'tag': {'id': tag.id, 'name': tag.name, 'description': tag.description, 'color': tag.color}
        })
    except Exception as e:
        db.session.rollback()
        logging.error(f"Error adding tag: {str(e)}")
        return jsonify({'success': False, 'error': 'An error occurred while adding the tag'})



@footprint_tag_bp.route('/footprints', endpoint='footprints')
@login_required
def footprints():
    """Redirect to unified item management page"""
    return redirect(url_for('settings.manage_types'))




@footprint_tag_bp.route('/footprint/new', endpoint='footprint_new', methods=['GET', 'POST'])
@login_required
@permission_required("settings_sections.item_management", "edit")
def footprint_new():
    from models import Footprint
    from forms import FootprintForm
    form = FootprintForm()
    
    if form.validate_on_submit():
        # Check for duplicate name
        existing = Footprint.query.filter_by(name=form.name.data).first()
        if existing:
            flash(f'Footprint "{form.name.data}" already exists!', 'danger')
            return render_template('footprint_form.html', form=form, title='New Footprint')
        
        footprint = Footprint(
            name=form.name.data,
            description=form.description.data,
            color=form.color.data or '#6c757d'
        )
        db.session.add(footprint)
        db.session.commit()
        log_audit(current_user.id, 'create', 'footprint', footprint.id, f'Created footprint: {footprint.name}')
        flash(f'Footprint "{footprint.name}" created successfully!', 'success')
        return redirect(url_for('settings.manage_types'))
    return render_template('footprint_form.html', form=form, title='New Footprint')



@footprint_tag_bp.route('/footprint/<int:id>/edit', endpoint='footprint_edit', methods=['GET', 'POST'])
@login_required
@permission_required("settings_sections.item_management", "edit")
def footprint_edit(id):
    from models import Footprint
    from forms import FootprintForm
    footprint = Footprint.query.get_or_404(id)
    form = FootprintForm(obj=footprint)
    
    if form.validate_on_submit():
        footprint.name = form.name.data
        footprint.description = form.description.data
        footprint.color = form.color.data or '#6c757d'
        db.session.commit()
        log_audit(current_user.id, 'update', 'footprint', footprint.id, f'Updated footprint: {footprint.name}')
        flash(f'Footprint "{footprint.name}" updated successfully!', 'success')
        return redirect(url_for('settings.manage_types'))
    return render_template('footprint_form.html', form=form, footprint=footprint, title='Edit Footprint')



@footprint_tag_bp.route('/footprint/<int:id>/delete', endpoint='footprint_delete', methods=['POST'])
@login_required
@permission_required("settings_sections.item_management", "delete")
def footprint_delete(id):
    from models import Footprint
    footprint = Footprint.query.get_or_404(id)
    name = footprint.name
    db.session.delete(footprint)
    db.session.commit()
    flash(f'Footprint "{name}" deleted!', 'success')
    return redirect(url_for('settings.manage_types'))

# ============= TAGS =============



@footprint_tag_bp.route('/tags', endpoint='tags')
@login_required
def tags():
    """Redirect to unified item management page"""
    return redirect(url_for('settings.manage_types'))




@footprint_tag_bp.route('/tag/new', endpoint='tag_new', methods=['GET', 'POST'])
@login_required
@permission_required("settings_sections.item_management", "edit")
def tag_new():
    from models import Tag
    from forms import TagForm
    form = TagForm()
    
    if form.validate_on_submit():
        # Check for duplicate name
        existing = Tag.query.filter_by(name=form.name.data).first()
        if existing:
            flash(f'Tag "{form.name.data}" already exists!', 'danger')
            return render_template('tag_form.html', form=form, title='New Tag')
        
        tag = Tag(
            name=form.name.data,
            description=form.description.data,
            color=form.color.data or '#6c757d'
        )
        db.session.add(tag)
        db.session.commit()
        log_audit(current_user.id, 'create', 'tag', tag.id, f'Created tag: {tag.name}')
        flash(f'Tag "{tag.name}" created successfully!', 'success')
        return redirect(url_for('settings.manage_types'))
    return render_template('tag_form.html', form=form, title='New Tag')



@footprint_tag_bp.route('/tag/<int:id>/edit', endpoint='tag_edit', methods=['GET', 'POST'])
@login_required
@permission_required("settings_sections.item_management", "edit")
def tag_edit(id):
    from models import Tag
    from forms import TagForm
    tag = Tag.query.get_or_404(id)
    form = TagForm(obj=tag)
    
    if form.validate_on_submit():
        tag.name = form.name.data
        tag.description = form.description.data
        tag.color = form.color.data or '#6c757d'
        db.session.commit()
        log_audit(current_user.id, 'update', 'tag', tag.id, f'Updated tag: {tag.name}')
        flash(f'Tag "{tag.name}" updated successfully!', 'success')
        return redirect(url_for('settings.manage_types'))
    return render_template('tag_form.html', form=form, tag=tag, title='Edit Tag')



@footprint_tag_bp.route('/tag/<int:id>/delete', endpoint='tag_delete', methods=['POST'])
@login_required
@permission_required("settings_sections.item_management", "delete")
def tag_delete(id):
    from models import Tag
    tag = Tag.query.get_or_404(id)
    name = tag.name
    db.session.delete(tag)
    db.session.commit()
    flash(f'Tag "{name}" deleted!', 'success')
    return redirect(url_for('settings.manage_types'))

# ============= BACKUP =============



