"""
Visual Storage Routes Blueprint
"""
from flask import Blueprint, render_template, redirect, url_for, flash, request, jsonify, send_file, abort
from flask_login import login_required, current_user, login_user, logout_user
from models import db, User, Category, Item, Attachment, Rack, Footprint, Tag, Setting, Location, AuditLog, StickerTemplate, ItemBatch
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
    
    rack_uuid = request.args.get('rack', type=str)
    location_uuid = request.args.get('location', type=str)
    page = request.args.get('page', 1, type=int)
    
    # Pagination settings
    racks_per_page = 5
    
    # Get racks for display (filtered by location if selected)
    if location_uuid:
        # Filter by location
        location = Location.query.filter_by(uuid=location_uuid).first_or_404()
        racks_to_display = location.racks
    else:
        # All racks
        racks_to_display = Rack.query.order_by(Rack.name).all()
    
    # Then filter by specific rack if requested
    if rack_uuid:
        racks_query = [r for r in racks_to_display if r.uuid == rack_uuid]
    else:
        racks_query = racks_to_display
    
    # Paginate the racks
    total_racks = len(racks_query)
    total_pages = (total_racks + racks_per_page - 1) // racks_per_page
    
    # Ensure page is valid
    if page < 1:
        page = 1
    elif page > total_pages and total_pages > 0:
        page = total_pages
    
    # Get racks for current page
    start_idx = (page - 1) * racks_per_page
    end_idx = start_idx + racks_per_page
    racks_for_page = racks_query[start_idx:end_idx]
    
    def _first_image_url(item):
        if not item:
            return None
        for att in item.attachments:
            if att.file_type in ['png', 'jpg', 'jpeg', 'gif']:
                return url_for('uploaded_file', filename=att.filename)
        return None

    rack_data = []
    for rack in racks_for_page:
        # Items whose main location is this rack (shown without quantity)
        items_main = Item.query.filter_by(rack_id=rack.id).all()
        # Batches that override to this rack (shown with quantity)
        batches_here = ItemBatch.query.filter_by(rack_id=rack.id, follow_main_location=False).all()

        drawers = {}

        def _ensure(drawer_key):
            if drawer_key not in drawers:
                drawers[drawer_key] = {'items': [], 'batches': [], 'preview_image': None}
            return drawers[drawer_key]

        for item in items_main:
            if item.drawer:
                entry = _ensure(item.drawer)
                entry['items'].append(item)
                if not entry['preview_image']:
                    entry['preview_image'] = _first_image_url(item)

        for batch in batches_here:
            if batch.drawer:
                entry = _ensure(batch.drawer)
                entry['batches'].append(batch)
                if not entry['preview_image']:
                    entry['preview_image'] = _first_image_url(batch.item)

        skip_cells, cell_spans, group_cells = rack.compute_merge_layout()
        rack_data.append({
            'id': rack.id,
            'uuid': rack.uuid,
            'name': rack.name,
            'description': rack.description,
            'physical_location': rack.physical_location,
            'rows': rack.rows,
            'cols': rack.cols,
            'drawers': drawers,
            'item_count': len(items_main) + len(batches_here),
            'unavailable_drawers': rack.get_unavailable_drawers(),
            'merged_cells': rack.get_merged_cells(),
            'skip_cells': list(skip_cells),
            'cell_spans': cell_spans,
            'group_cells': group_cells,
        })
    
    # For the dropdown, show all racks for location selection, but filtered by current location for rack selection
    all_racks_for_dropdown = racks_to_display
    locations = Location.query.order_by(Location.name).all()
    return render_template('visual_storage.html', 
                          racks=rack_data, 
                          all_racks=all_racks_for_dropdown, 
                          locations=locations, 
                          current_location_uuid=location_uuid, 
                          current_rack_uuid=rack_uuid,
                          current_page=page,
                          total_pages=total_pages,
                          total_racks=total_racks,
                          can_edit_visual_storage=can_edit,
                          can_manage_racks=can_manage_racks,
                          max=max,
                          min=min)



@visual_storage_bp.route('/api/drawer/<string:rack_uuid>/<path:drawer_id>')
@login_required
def get_drawer_contents(rack_uuid, drawer_id):
    """API endpoint to get drawer contents (items with main here + batches overriding here)"""
    rack = Rack.query.filter_by(uuid=rack_uuid).first_or_404()
    items_main = Item.query.filter_by(rack_id=rack.id, drawer=drawer_id).all()
    batches_here = ItemBatch.query.filter_by(rack_id=rack.id, drawer=drawer_id, follow_main_location=False).all()

    entries = []
    for item in items_main:
        entries.append({
            'type': 'item_main',
            'item_id': item.id,
            'item_uuid': item.uuid,
            'name': item.name,
            'sku': item.sku or 'N/A',
        })
    for batch in batches_here:
        item = batch.item
        entries.append({
            'type': 'batch',
            'item_id': item.id if item else None,
            'item_uuid': item.uuid if item else None,
            'name': item.name if item else 'Unknown',
            'sku': (item.sku if item and item.sku else 'N/A'),
            'batch_id': batch.id,
            'batch_label': batch.get_display_label(),
            'quantity': batch.quantity,
            'available': batch.get_available_quantity(),
        })

    return jsonify({
        'entries': entries,
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
        rack_uuid = data.get('rack_id')  # Now receives UUID instead of ID
        drawer_id = data.get('drawer_id')
        is_unavailable = data.get('is_unavailable', False)
        
        rack = Rack.query.filter_by(uuid=rack_uuid).first_or_404()
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
        rack_uuid = data.get('rack_id')  # Now receives UUID
        drawer_id = data.get('drawer_id')
        location_type = data.get('location_type')  # 'general' or 'drawer'
        
        # Get rack by UUID to get ID for queries
        rack = Rack.query.filter_by(uuid=rack_uuid).first_or_404()
        
        # Get all items in the drawer
        items = Item.query.filter_by(rack_id=rack.id, drawer=drawer_id).all()
        
        if not items:
            return jsonify({'success': False, 'error': 'No items in this drawer'})
        
        # Move items based on location type
        if location_type == 'general':
            new_location_uuid = data.get('location_id')
            if not new_location_uuid or new_location_uuid == 0:
                return jsonify({'success': False, 'error': 'Please select a general location'})
            
            new_location = Location.query.filter_by(uuid=new_location_uuid).first_or_404()
            
            for item in items:
                item.location_id = new_location.id
                item.rack_id = None
                item.drawer = None
        else:  # drawer
            new_rack_uuid = data.get('new_rack_id')
            new_drawer = data.get('new_drawer')
            
            if not new_rack_uuid or new_rack_uuid == 0 or not new_drawer:
                return jsonify({'success': False, 'error': 'Please select a rack and drawer'})
            
            new_rack = Rack.query.filter_by(uuid=new_rack_uuid).first_or_404()
            
            for item in items:
                item.location_id = None
                item.rack_id = new_rack.id
                item.drawer = new_drawer
        
        db.session.commit()
        
        log_audit(current_user.id, 'bulk_update', 'item', None,
                 f'Moved {len(items)} items from Rack {rack.uuid} Drawer {drawer_id}')

        return jsonify({'success': True, 'items_moved': len(items)})
    except Exception as e:
        db.session.rollback()
        import traceback
        logger.error(f"Error moving drawer items: {str(e)}")
        logger.error(traceback.format_exc())
        return jsonify({'success': False, 'error': 'An error occurred while moving drawer items.'})

def _parse_cell(cell):
    """Parse 'R{row}-C{col}' → (row, col) ints. Raises ValueError on bad input."""
    parts = cell[1:].split('-C')
    return int(parts[0]), int(parts[1])


def _cells_connected(cells):
    """Return True if all cells form a single connected (4-adjacency) component."""
    if len(cells) <= 1:
        return True
    cell_set = set(cells)
    parsed = {}
    for c in cells:
        try:
            parsed[c] = _parse_cell(c)
        except (ValueError, IndexError):
            return False
    visited = {cells[0]}
    queue = [cells[0]]
    while queue:
        curr = queue.pop()
        r, col = parsed[curr]
        for dr, dc in ((0, 1), (0, -1), (1, 0), (-1, 0)):
            nb = f'R{r + dr}-C{col + dc}'
            if nb in cell_set and nb not in visited:
                visited.add(nb)
                queue.append(nb)
    return len(visited) == len(cells)


@visual_storage_bp.route('/api/rack/<string:rack_uuid>/merge-cells', methods=['POST'])
@login_required
@permission_required("settings_sections.location_management", "edit")
def merge_rack_cells(rack_uuid):
    """Merge a connected selection of cells into one logical cell."""
    rack = Rack.query.filter_by(uuid=rack_uuid).first_or_404()
    data = request.get_json()
    cells = data.get('cells', [])

    if len(cells) < 2:
        return jsonify({'success': False, 'error': 'Select at least 2 cells to merge'})

    cell_coords = []
    max_row, max_col = 0, 0
    for cell in cells:
        try:
            r, c = _parse_cell(cell)
            cell_coords.append((r, c, cell))
            max_row = max(max_row, r)
            max_col = max(max_col, c)
        except (ValueError, IndexError):
            return jsonify({'success': False, 'error': f'Invalid cell ID: {cell}'})

    if not _cells_connected(cells):
        return jsonify({'success': False, 'error': 'Selected cells must all be adjacent to each other'})

    if max_row > rack.rows or max_col > rack.cols:
        return jsonify({'success': False, 'error': 'Cells are outside rack bounds'})

    existing = rack.get_merged_cells()
    occupied = set()
    for group in existing:
        for c in group.get('cells', []):
            occupied.add(c)

    for cell in cells:
        if cell in occupied:
            return jsonify({'success': False, 'error': f'Cell {cell} is already part of a merge group'})

    # Master = top-left selected cell (min row, then min col)
    cell_coords.sort(key=lambda x: (x[0], x[1]))
    master = cell_coords[0][2]

    existing.append({'master': master, 'cells': cells})
    rack.merged_cells = json.dumps(existing)
    db.session.commit()

    log_audit(current_user.id, 'update', 'rack', rack.id,
              f'Merged cells {cells} with master {master}')
    return jsonify({'success': True, 'master': master})


@visual_storage_bp.route('/api/rack/<string:rack_uuid>/split-cells', methods=['POST'])
@login_required
@permission_required("settings_sections.location_management", "edit")
def split_rack_cells(rack_uuid):
    """Split a merged cell group back to individual cells."""
    rack = Rack.query.filter_by(uuid=rack_uuid).first_or_404()
    data = request.get_json()
    master = data.get('master')

    existing = rack.get_merged_cells()
    new_merged = [g for g in existing if g.get('master') != master]

    if len(new_merged) == len(existing):
        return jsonify({'success': False, 'error': 'No merge group found for this cell'})

    rack.merged_cells = json.dumps(new_merged)
    db.session.commit()

    log_audit(current_user.id, 'update', 'rack', rack.id,
              f'Split merged cells with master {master}')
    return jsonify({'success': True})


# ============= ERROR HANDLERS =============



