"""
Visual Storage Routes Blueprint
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

visual_storage_bp = Blueprint('visual_storage', __name__)


@visual_storage_bp.route('/visual-storage', endpoint='visual_storage')
@login_required
def visual_storage():
    """Display visual storage system"""
    # Check view permission
    if not current_user.has_permission('pages.visual_storage', 'view'):
        flash('You do not have permission to view visual storage.', 'danger')
        return redirect(url_for('index'))
    
    # Store edit permission in context for template
    can_edit = current_user.has_permission('pages.visual_storage', 'edit')
    
    # Check if user can access location management (for Manage Racks button)
    can_manage_racks = current_user.has_permission('settings_sections.location_management', 'view')
    
    rack_id = request.args.get('rack', type=int)
    location_id = request.args.get('location', type=int)
    
    # Get racks for display (filtered by location if selected)
    if location_id:
        # Filter by location
        location = Location.query.get_or_404(location_id)
        racks_to_display = location.racks
    else:
        # All racks
        racks_to_display = Rack.query.order_by(Rack.name).all()
    
    # Then filter by specific rack if requested
    if rack_id:
        racks_query = [r for r in racks_to_display if r.id == rack_id]
    else:
        racks_query = racks_to_display
    
    rack_data = []
    for rack in racks_query:
        items = Item.query.filter_by(rack_id=rack.id).all()
        
        drawers = {}
        for item in items:
            if item.drawer:
                if item.drawer not in drawers:
                    drawers[item.drawer] = {
                        'items': [],
                        'preview_image': None
                    }
                drawers[item.drawer]['items'].append(item)
                
                # Get first image for preview
                if not drawers[item.drawer]['preview_image'] and item.attachments:
                    for att in item.attachments:
                        if att.file_type in ['png', 'jpg', 'jpeg', 'gif']:
                            drawers[item.drawer]['preview_image'] = url_for('uploaded_file', filename=att.filename)
                            break
        
        rack_data.append({
            'id': rack.id,
            'name': rack.name,
            'description': rack.description,
            'physical_location': rack.physical_location,
            'rows': rack.rows,
            'cols': rack.cols,
            'drawers': drawers,
            'item_count': len(items),
            'unavailable_drawers': rack.get_unavailable_drawers()
        })
    
    # For the dropdown, show all racks for location selection, but filtered by current location for rack selection
    all_racks_for_dropdown = racks_to_display
    locations = Location.query.order_by(Location.name).all()
    return render_template('visual_storage.html', 
                          racks=rack_data, 
                          all_racks=all_racks_for_dropdown, 
                          locations=locations, 
                          current_location_id=location_id, 
                          current_rack_id=rack_id, 
                          can_edit_visual_storage=can_edit,
                          can_manage_racks=can_manage_racks)



@visual_storage_bp.route('/api/drawer/<int:rack_id>/<path:drawer_id>')
@login_required
def get_drawer_contents(rack_id, drawer_id):
    """API endpoint to get drawer contents"""
    rack = Rack.query.get_or_404(rack_id)
    items = Item.query.filter_by(rack_id=rack_id, drawer=drawer_id).all()
    
    items_data = []
    for item in items:
        items_data.append({
            'id': item.id,
            'name': item.name,
            'sku': item.sku or 'N/A',
            'quantity': item.quantity,
            'available': item.get_available_quantity(),
            'uuid': item.uuid
        })
    
    return jsonify({
        'items': items_data,
        'rack': {
            'id': rack.id,
            'name': rack.name
        },
        'drawer_id': drawer_id,
        'is_unavailable': rack.is_drawer_unavailable(drawer_id)
    })



@visual_storage_bp.route('/api/drawer/toggle-availability', methods=['POST'])
@login_required
@permission_required("settings_sections.location_management", "edit")
def toggle_drawer_availability():
    """Toggle drawer availability status"""
    try:
        data = request.get_json()
        rack_id = data.get('rack_id')
        drawer_id = data.get('drawer_id')
        is_unavailable = data.get('is_unavailable', False)
        
        rack = Rack.query.get_or_404(rack_id)
        unavailable = rack.get_unavailable_drawers()
        
        if is_unavailable:
            # Mark as unavailable
            if drawer_id not in unavailable:
                unavailable.append(drawer_id)
        else:
            # Mark as available
            if drawer_id in unavailable:
                unavailable.remove(drawer_id)
        
        rack.unavailable_drawers = json.dumps(unavailable)
        db.session.commit()
        
        log_audit(current_user.id, 'update', 'rack', rack.id,
                 f'Drawer {drawer_id} marked as {"unavailable" if is_unavailable else "available"}')

        return jsonify({'success': True})
    except Exception as e:
        db.session.rollback()
        logging.error(f"Error toggling drawer availability: {str(e)}")
        return jsonify({'success': False, 'error': 'An error occurred while toggling drawer availability'})



@visual_storage_bp.route('/api/drawer/move-items', methods=['POST'])
@login_required
@permission_required("settings_sections.location_management", "edit")
def move_drawer_items():
    """Move all items from a drawer to a new location"""
    try:
        data = request.get_json()
        rack_id = data.get('rack_id')
        drawer_id = data.get('drawer_id')
        location_type = data.get('location_type')  # 'general' or 'drawer'
        
        # Get all items in the drawer
        items = Item.query.filter_by(rack_id=rack_id, drawer=drawer_id).all()
        
        if not items:
            return jsonify({'success': False, 'error': 'No items in this drawer'})
        
        # Move items based on location type
        if location_type == 'general':
            new_location_id = data.get('location_id')
            if not new_location_id or new_location_id == 0:
                return jsonify({'success': False, 'error': 'Please select a general location'})
            
            for item in items:
                item.location_id = new_location_id
                item.rack_id = None
                item.drawer = None
        else:  # drawer
            new_rack_id = data.get('new_rack_id')
            new_drawer = data.get('new_drawer')
            
            if not new_rack_id or new_rack_id == 0 or not new_drawer:
                return jsonify({'success': False, 'error': 'Please select a rack and drawer'})
            
            for item in items:
                item.location_id = None
                item.rack_id = new_rack_id
                item.drawer = new_drawer
        
        db.session.commit()
        
        log_audit(current_user.id, 'bulk_update', 'item', None,
                 f'Moved {len(items)} items from Rack {rack_id} Drawer {drawer_id}')

        return jsonify({'success': True, 'items_moved': len(items)})
    except Exception as e:
        db.session.rollback()
        logging.error(f"Error moving drawer items: {str(e)}")
        return jsonify({'success': False, 'error': 'An error occurred while moving drawer items'})

# ============= ERROR HANDLERS =============



