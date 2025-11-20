"""
Category Routes Blueprint
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

category_bp = Blueprint('category', __name__)


@category_bp.route('/categories', endpoint='categories')
@login_required
def categories():
    """Redirect to unified item management page"""
    return redirect(url_for('settings.manage_types'))




@category_bp.route('/category/new', endpoint='category_new', methods=['GET', 'POST'])
@login_required
@permission_required("settings_sections.item_management", "edit")
def category_new():
    form = CategoryForm()
    
    if form.validate_on_submit():
        # Check for duplicate name
        existing = Category.query.filter_by(name=form.name.data).first()
        if existing:
            flash(f'Category "{form.name.data}" already exists!', 'danger')
            return render_template('category_form.html', form=form, title='New Category')
        
        category = Category(
            name=form.name.data,
            description=form.description.data,
            color=form.color.data or '#6c757d'
        )
        db.session.add(category)
        db.session.commit()
        
        log_audit(current_user.id, 'create', 'category', category.id, f'Created category: {category.name}')
        flash(f'Category "{category.name}" created successfully!', 'success')
        return redirect(url_for('settings.manage_types'))
    
    return render_template('category_form.html', form=form, title='New Category')



@category_bp.route('/category/<int:id>/edit', endpoint='category_edit', methods=['GET', 'POST'])
@login_required
@permission_required("settings_sections.item_management", "edit")
def category_edit(id):
    category = Category.query.get_or_404(id)
    form = CategoryForm(obj=category)
    
    if form.validate_on_submit():
        category.name = form.name.data
        category.description = form.description.data
        category.color = form.color.data or '#6c757d'
        db.session.commit()
        
        log_audit(current_user.id, 'update', 'category', category.id, f'Updated category: {category.name}')
        flash(f'Category "{category.name}" updated successfully!', 'success')
        return redirect(url_for('settings.manage_types'))
    
    return render_template('category_form.html', form=form, category=category, title='Edit Category')



@category_bp.route('/category/<int:id>/delete', endpoint='category_delete', methods=['POST'])
@login_required
@permission_required("settings_sections.item_management", "delete")
def category_delete(id):
    category = Category.query.get_or_404(id)
    category_name = category.name
    
    if category.items:
        flash(f'Cannot delete category "{category_name}" because it has {len(category.items)} items.', 'danger')
        return redirect(url_for('settings.manage_types'))
    
    db.session.delete(category)
    db.session.commit()
    
    log_audit(current_user.id, 'delete', 'category', id, f'Deleted category: {category_name}')
    flash(f'Category "{category_name}" deleted successfully!', 'success')
    return redirect(url_for('settings.manage_types'))

# ============= USER MANAGEMENT ROUTES =============



@category_bp.route('/api/category/add', methods=['POST'])
@login_required
@permission_required("settings_sections.item_management", "edit")
def api_add_category():
    """API endpoint to add category from item form"""
    try:
        data = request.get_json()
        name = data.get('name', '').strip()
        description = data.get('description', '').strip()
        color = data.get('color', '#6c757d')
        
        if not name:
            return jsonify({'success': False, 'error': 'Category name is required'})
        
        # Check if exists
        existing = Category.query.filter_by(name=name).first()
        if existing:
            return jsonify({'success': False, 'error': 'Category already exists'})
        
        category = Category(name=name, description=description, color=color)
        db.session.add(category)
        db.session.commit()
        
        log_audit(current_user.id, 'create', 'category', category.id, f'Created category: {category.name}')
        
        return jsonify({
            'success': True,
            'category': {'id': category.id, 'name': category.name, 'color': category.color}
        })
    except Exception as e:
        db.session.rollback()
        logging.error(f"Error adding category: {str(e)}")
        return jsonify({'success': False, 'error': 'An error occurred while adding the category'})



