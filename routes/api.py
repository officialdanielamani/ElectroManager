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
    location_id = data.get('location_id')
    rack_id = data.get('rack_id')
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
    
    for item in items:
        # Apply location and rack filters if specified
        if location_id and item.location_id != location_id:
            continue
        
        if rack_id and item.rack_id != rack_id:
            continue
        
        # Check if item is in a rack (drawer storage)
        if item.rack_id and item.drawer:
            rack = Rack.query.get(item.rack_id)
            location_name = None
            if rack and rack.physical_location:
                location_name = rack.physical_location.name
            
            results.append({
                'type': 'rack',
                'id': item.id,
                'name': item.name,
                'uuid': item.uuid,
                'quantity': item.quantity,
                'sku': item.sku or 'N/A',
                'rack_id': item.rack_id,
                'rack_name': rack.name if rack else 'Unknown Rack',
                'drawer': item.drawer,
                'location_name': location_name
            })
        # Check if item is in a general location
        elif item.location_id:
            location = Location.query.get(item.location_id)
            results.append({
                'type': 'general',
                'id': item.id,
                'name': item.name,
                'uuid': item.uuid,
                'quantity': item.quantity,
                'sku': item.sku or 'N/A',
                'location_id': item.location_id,
                'location_name': location.name if location else 'Unknown Location'
            })
    
    # Sort: rack items first, then general location items
    rack_items = [item for item in results if item['type'] == 'rack']
    general_items = [item for item in results if item['type'] == 'general']
    
    return jsonify({'items': rack_items + general_items})

# ============= API ENDPOINTS FOR INLINE ADD =============



