"""
Api Routes Blueprint
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

api_bp = Blueprint('api', __name__)


@api_bp.route('/api/search-item', methods=['POST'])
@login_required
def search_item():
    """API endpoint to search for items in visual storage"""
    data = request.get_json()
    search_term = data.get('search', '').strip()
    location_uuid = data.get('location_uuid')
    rack_uuid = data.get('rack_uuid')
    exact_match = data.get('exact_match', False)
    
    if not search_term:
        return jsonify({'items': []})
    
    # Determine if searching by UUID or name
    is_uuid_search = search_term.lower().startswith('uuid:')
    
    if is_uuid_search:
        # Extract UUID from search term
        uuid_value = search_term[5:].strip()
        items = Item.query.filter_by(uuid=uuid_value).all()
    else:
        # Search by name (case-insensitive)
        if exact_match:
            # Exact match
            items = Item.query.filter(Item.name.ilike(search_term)).all()
        else:
            # Partial match
            items = Item.query.filter(Item.name.ilike(f'%{search_term}%')).all()
    
    results = []

    from models import ItemBatch

    for item in items:
        # Apply location and rack filters if specified (main-location scope)
        filter_loc_id = None
        if location_uuid:
            location = Location.query.filter_by(uuid=location_uuid).first()
            filter_loc_id = location.id if location else -1
        filter_rack_id = None
        if rack_uuid:
            rack = Rack.query.filter_by(uuid=rack_uuid).first()
            filter_rack_id = rack.id if rack else -1

        # 1) Item main location result
        matches_main_filters = True
        if filter_loc_id is not None and item.location_id != filter_loc_id:
            matches_main_filters = False
        if filter_rack_id is not None and item.rack_id != filter_rack_id:
            matches_main_filters = False

        if matches_main_filters:
            if item.rack_id and item.drawer:
                rack = Rack.query.get(item.rack_id)
                loc_name = rack.physical_location.name if rack and rack.physical_location else None
                results.append({
                    'type': 'rack',
                    'scope': 'main',
                    'id': item.id,
                    'name': item.name,
                    'uuid': item.uuid,
                    'quantity': item.get_overall_quantity(),
                    'sku': item.sku or 'N/A',
                    'rack_id': item.rack_id,
                    'rack_uuid': rack.uuid if rack else None,
                    'rack_name': rack.name if rack else 'Unknown Rack',
                    'drawer': item.drawer,
                    'location_name': loc_name,
                })
            elif item.location_id:
                location = Location.query.get(item.location_id)
                results.append({
                    'type': 'general',
                    'scope': 'main',
                    'id': item.id,
                    'name': item.name,
                    'uuid': item.uuid,
                    'quantity': item.get_overall_quantity(),
                    'sku': item.sku or 'N/A',
                    'location_id': item.location_id,
                    'location_uuid': location.uuid if location else None,
                    'location_name': location.name if location else 'Unknown Location',
                })

        # 2) Batch overrides: each batch with follow_main_location=False is a distinct result
        for batch in ItemBatch.query.filter_by(item_id=item.id, follow_main_location=False).all():
            if filter_loc_id is not None and batch.location_id != filter_loc_id:
                continue
            if filter_rack_id is not None and batch.rack_id != filter_rack_id:
                continue
            if batch.rack_id and batch.drawer:
                rack = Rack.query.get(batch.rack_id)
                loc_name = rack.physical_location.name if rack and rack.physical_location else None
                results.append({
                    'type': 'rack',
                    'scope': 'batch',
                    'id': item.id,
                    'batch_id': batch.id,
                    'batch_label': batch.get_display_label(),
                    'name': item.name,
                    'uuid': item.uuid,
                    'quantity': batch.quantity,
                    'sku': item.sku or 'N/A',
                    'rack_id': batch.rack_id,
                    'rack_uuid': rack.uuid if rack else None,
                    'rack_name': rack.name if rack else 'Unknown Rack',
                    'drawer': batch.drawer,
                    'location_name': loc_name,
                })
            elif batch.location_id:
                location = Location.query.get(batch.location_id)
                results.append({
                    'type': 'general',
                    'scope': 'batch',
                    'id': item.id,
                    'batch_id': batch.id,
                    'batch_label': batch.get_display_label(),
                    'name': item.name,
                    'uuid': item.uuid,
                    'quantity': batch.quantity,
                    'sku': item.sku or 'N/A',
                    'location_id': batch.location_id,
                    'location_uuid': location.uuid if location else None,
                    'location_name': location.name if location else 'Unknown Location',
                })
    
    # Sort: rack items first, then general location items
    rack_items = [item for item in results if item['type'] == 'rack']
    general_items = [item for item in results if item['type'] == 'general']
    
    # Calculate which page each item is on
    racks_per_page = 5
    
    # Get all racks to calculate positions
    if rack_uuid:
        rack = Rack.query.filter_by(uuid=rack_uuid).first()
        if rack:
            all_racks = [rack]
        else:
            all_racks = []
    elif location_uuid:
        location = Location.query.filter_by(uuid=location_uuid).first()
        all_racks = location.racks if location else []
    else:
        all_racks = Rack.query.order_by(Rack.name).all()
    
    # Create a mapping of rack UUID to page number
    rack_to_page = {}
    for idx, rack in enumerate(all_racks):
        page_num = (idx // racks_per_page) + 1
        rack_to_page[rack.uuid] = page_num
    
    # Add page number to results
    for item in rack_items:
        item['page'] = rack_to_page.get(item['rack_uuid'], 1)
    
    # General location items are not paginated, but we can add page=1
    for item in general_items:
        item['page'] = 1
    
    return jsonify({'items': rack_items + general_items})

# ============= API ENDPOINTS FOR INLINE ADD =============



