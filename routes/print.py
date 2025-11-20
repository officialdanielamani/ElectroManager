"""
Print Routes Blueprint
"""
from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_required, current_user
from models import db, Item, Setting
from datetime import datetime
import json
import logging

logger = logging.getLogger(__name__)

print_bp = Blueprint('print', __name__)


@print_bp.route('/items/print')
@login_required
def items_print():
    """Print view for items list"""
    # Check if user has permission to view items
    if not current_user.has_permission('items', 'view'):
        flash('You do not have permission to view items.', 'danger')
        return redirect(url_for('index'))
    
    # Get the same parameters as the items route
    search_query = request.args.get('search', '')
    category_id = request.args.get('category', 0, type=int)
    status_filter = request.args.get('status', '')
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 25, type=int)
    view_type = request.args.get('view', 'table')  # table or card
    item_ids = request.args.get('item_ids', '')  # Selected item IDs (comma-separated)
    
    # Cap per_page at a reasonable maximum
    if per_page > 999999:
        per_page = 999999
    
    # If specific items are selected, only print those
    if item_ids:
        # Parse the comma-separated IDs
        id_list = [int(id.strip()) for id in item_ids.split(',') if id.strip().isdigit()]
        
        # Query only the selected items
        items = Item.query.filter(Item.id.in_(id_list)).order_by(Item.updated_at.desc()).all()
        
        # Create a simple pagination object for selected items
        class SimplePagination:
            def __init__(self, items):
                self.items = items
                self.page = 1
                self.per_page = len(items)
                self.total = len(items)
                self.pages = 1
            
            @property
            def has_next(self):
                return False
            
            @property
            def has_prev(self):
                return False
        
        pagination = SimplePagination(items)
    else:
        # Print all items with current filters
        query = Item.query
        
        # Search filter
        if search_query:
            search_pattern = f'%{search_query}%'
            query = query.filter(
                db.or_(
                    Item.name.ilike(search_pattern),
                    Item.sku.ilike(search_pattern),
                    Item.description.ilike(search_pattern)
                )
            )
        
        # Category filter
        if category_id > 0:
            query = query.filter_by(category_id=category_id)
        
        # Status filter
        if status_filter == 'low':
            query = query.filter(Item.quantity <= Item.min_quantity)
        elif status_filter == 'out':
            query = query.filter(Item.quantity == 0)
        
        # Query items
        items = query.order_by(Item.updated_at.desc()).all()
        
        # Create a simple pagination object
        class SimplePagination:
            def __init__(self, items):
                self.items = items
                self.page = 1
                self.per_page = len(items)
                self.total = len(items)
                self.pages = 1
            
            @property
            def has_next(self):
                return False
            
            @property
            def has_prev(self):
                return False
        
        pagination = SimplePagination(items)
    
    currency_symbol = Setting.get('currency', '$')
    currency_decimal_places = int(Setting.get('currency_decimal_places', '2'))
    
    # Get current datetime for footer
    current_datetime = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    
    return render_template('items_print.html',
                         pagination=pagination,
                         search_query=search_query,
                         currency_symbol=currency_symbol,
                         currency_decimal_places=currency_decimal_places,
                         current_user=current_user,
                         current_datetime=current_datetime)


@print_bp.route('/item/<string:uuid>/print')
@login_required
def item_detail_print(uuid):
    """Print view for item detail"""
    item = Item.query.filter_by(uuid=uuid).first_or_404()
    
    # Check if user has view permission
    if not current_user.has_permission('items', 'view'):
        flash('You do not have permission to view items.', 'danger')
        return redirect(url_for('item.items'))
    
    currency_symbol = Setting.get('currency', '$')
    currency_decimal_places = int(Setting.get('currency_decimal_places', '2'))
    
    # Get current datetime for footer
    current_datetime = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    
    # Parse datasheets
    datasheets = []
    if item.datasheet_urls:
        try:
            datasheets = json.loads(item.datasheet_urls)
            if not isinstance(datasheets, list):
                datasheets = []
        except (json.JSONDecodeError, TypeError):
            # Fallback: old format (plain URLs separated by newlines)
            urls = item.datasheet_urls.split('\n')
            datasheets = [{'url': url.strip(), 'title': '', 'info': ''} for url in urls if url.strip()]
    
    return render_template('item_detail_print.html',
                         item=item,
                         currency_symbol=currency_symbol,
                         currency_decimal_places=currency_decimal_places,
                         current_user=current_user,
                         current_datetime=current_datetime,
                         datasheets=datasheets)
