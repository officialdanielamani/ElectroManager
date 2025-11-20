"""
Item Routes Blueprint
"""
from flask import Blueprint, render_template, redirect, url_for, flash, request, jsonify, send_file, abort, current_app
from flask_login import login_required, current_user, login_user, logout_user
from models import db, User, Category, Item, Attachment, Rack, Footprint, Tag, Setting, Location, AuditLog, StickerTemplate
from forms import (LoginForm, RegistrationForm, CategoryForm, ItemAddForm, ItemEditForm, AttachmentForm, 
                   SearchForm, UserForm, MagicParameterForm, ParameterUnitForm, ParameterStringOptionForm, ItemParameterForm)
from helpers import is_safe_url, format_currency, is_safe_file_path
from utils import save_file, log_audit, admin_required, permission_required, item_permission_required, format_file_size, allowed_file, get_item_edit_permissions
from qr_utils import get_item_data, render_template_to_svg, generate_single_sticker_pdf
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

item_bp = Blueprint('item', __name__)


@item_bp.route('/items', endpoint='items')
@login_required
def items():
    """Main items listing page"""
    # Check if user has permission to view items
    if not current_user.has_permission('items', 'view'):
        flash('You do not have permission to view items.', 'danger')
        return redirect(url_for('index'))
    
    search_form = SearchForm()
    
    search_query = request.args.get('search', '')
    category_id = request.args.get('category', 0, type=int)
    status_filter = request.args.get('status', '')
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 25, type=int)
    
    # Cap per_page at a reasonable maximum
    if per_page > 999999:
        per_page = 999999
    
    query = Item.query
    
    if search_query:
        query = query.filter(
            db.or_(
                Item.name.ilike(f'%{search_query}%'),
                Item.description.ilike(f'%{search_query}%'),
                Item.sku.ilike(f'%{search_query}%')
            )
        )
    
    if category_id > 0:
        query = query.filter_by(category_id=category_id)
    
    # Apply status filter
    if status_filter:
        statuses = status_filter.split(',')
        filtered_items = []
        
        for item in query.all():
            if 'ok' in statuses and not item.is_no_stock() and not item.is_low_stock():
                filtered_items.append(item)
            elif 'low' in statuses and item.is_low_stock():
                filtered_items.append(item)
            elif 'no' in statuses and item.is_no_stock():
                filtered_items.append(item)
        
        # Sort by updated_at descending
        filtered_items.sort(key=lambda x: x.updated_at, reverse=True)
        
        # Manually paginate
        total = len(filtered_items)
        start = (page - 1) * per_page
        end = start + per_page
        items = filtered_items[start:end]
        
        # Create a manual pagination object
        class Pagination:
            def __init__(self, items, page, per_page, total):
                self.items = items
                self.page = page
                self.per_page = per_page
                self.total = total
                self.pages = (total + per_page - 1) // per_page
            
            @property
            def has_next(self):
                return self.page < self.pages
            
            @property
            def has_prev(self):
                return self.page > 1
            
            @property
            def next_num(self):
                return self.page + 1 if self.has_next else None
            
            @property
            def prev_num(self):
                return self.page - 1 if self.has_prev else None
            
            def iter_pages(self, left_edge=1, right_edge=1, left_current=1, right_current=2):
                for num in range(1, self.pages + 1):
                    if (num <= left_edge or
                        num > self.pages - right_edge or
                        (self.page - left_current <= num <= self.page + right_current)):
                        yield num
                    elif num == left_edge + 1 or num == self.pages - right_edge:
                        yield None
        
        pagination = Pagination(items, page, per_page, total)
    else:
        # Default sort by updated_at descending
        pagination = query.order_by(Item.updated_at.desc()).paginate(
            page=page, per_page=per_page, error_out=False
        )
    
    items = pagination.items
    
    total_items = Item.query.count()
    # Low stock: quantity > 0 AND quantity <= min_quantity
    low_stock_items = Item.query.filter(Item.quantity > 0, Item.quantity <= Item.min_quantity).count()
    # No stock: quantity = 0
    no_stock_items = Item.query.filter(Item.quantity == 0).count()
    total_categories = Category.query.count()
    
    # Get user's table columns preference
    user_columns = current_user.get_table_columns()
    currency_symbol = Setting.get('currency', '$')
    currency_decimal_places = int(Setting.get('currency_decimal_places', '2'))
    
    return render_template('items.html', 
                         items=items,
                         pagination=pagination,
                         search_form=search_form,
                         search_query=search_query,
                         category_id=category_id,
                         status_filter=status_filter,
                         total_items=total_items,
                         low_stock_items=low_stock_items,
                         no_stock_items=no_stock_items,
                         total_categories=total_categories,
                         user_columns=user_columns,
                         per_page=per_page,
                         currency_symbol=currency_symbol,
                         currency_decimal_places=currency_decimal_places)

# ============= ITEM ROUTES =============



@item_bp.route('/item/new', endpoint='item_new', methods=['GET', 'POST'])
@login_required
@item_permission_required
def item_new():
    from models import Tag
    from forms import ItemAddForm
    import json
    
    # Get user permissions
    perms = get_item_edit_permissions(current_user)
    
    # Check if user has permission to create items
    if not perms.get('can_create'):
        flash('You do not have permission to create new items.', 'danger')
        return redirect(url_for('item.items'))
    
    # Also check if user has ANY edit permission (in case someone tries to create with form directly)
    if not (perms.get('can_edit_name') or perms.get('can_edit_sku_type') or 
            perms.get('can_edit_description') or perms.get('can_edit_datasheet') or
            perms.get('can_edit_upload') or perms.get('can_edit_lending') or
            perms.get('can_edit_price') or perms.get('can_edit_quantity') or
            perms.get('can_edit_location') or perms.get('can_edit_category') or
            perms.get('can_edit_footprint') or perms.get('can_edit_tags') or
            perms.get('can_edit_parameters')):
        flash('You do not have permission to create items.', 'danger')
        return redirect(url_for('item.items'))
    
    # Create form with permission-based field disabling
    form = ItemAddForm(perms=perms)
    locations = Location.query.order_by(Location.name).all()
    racks = Rack.query.order_by(Rack.name).all()
    racks_data = [{'id': r.id, 'name': r.name, 'rows': r.rows, 'cols': r.cols, 
                   'unavailable_drawers': r.get_unavailable_drawers()} for r in racks]
    all_tags = [{'id': t.id, 'name': t.name, 'color': t.color} for t in Tag.query.order_by(Tag.name).all()]
    
    prefill_rack_id = request.args.get('rack_id', type=int)
    prefill_drawer = request.args.get('drawer')
    
    if form.validate_on_submit():
        # For view-only users, check if they're trying to edit
        if not (perms.get('can_edit_name') or perms.get('can_edit_sku_type') or 
                perms.get('can_edit_description') or perms.get('can_edit_datasheet') or
                perms.get('can_edit_upload') or perms.get('can_edit_lending') or
                perms.get('can_edit_price') or perms.get('can_edit_quantity') or
                perms.get('can_edit_location') or perms.get('can_edit_category') or
                perms.get('can_edit_footprint') or perms.get('can_edit_tags') or
                perms.get('can_edit_parameters')):
            flash('You do not have permission to create items with any editable fields.', 'danger')
            return redirect(url_for('item.items'))
        
        # Apply default values for fields user cannot edit
        location_id = form.location_id.data if form.location_id.data and perms['can_edit_location'] else None
        rack_id = request.form.get('rack_id') if perms['can_edit_location'] else None
        drawer = request.form.get('drawer') if perms['can_edit_location'] else None
        
        # Determine location type
        if rack_id and int(rack_id) > 0:
            # Drawer storage
            location_id_value = None
            rack_id_value = int(rack_id)
            drawer_value = drawer
        else:
            # General location
            location_id_value = location_id if location_id and location_id != 0 else None
            rack_id_value = None
            drawer_value = None
        
        # Get selected tags (only if can edit tags)
        selected_tags = request.form.getlist('tags[]') if perms['can_edit_tags'] else []
        tags_json = json.dumps([int(t) for t in selected_tags if t])
        
        # Create item with role-based restrictions
        item = Item(
            name=form.name.data if perms['can_edit_name'] else 'New Item',
            sku=form.sku.data if form.sku.data and perms['can_edit_sku_type'] else None,
            info=form.info.data if perms['can_edit_sku_type'] else None,
            description=form.description.data if perms['can_edit_description'] else None,
            quantity=form.quantity.data if perms['can_edit_quantity'] else 0,
            price=form.price.data if form.price.data and perms['can_edit_price'] else 0.0,
            location_id=location_id_value,
            rack_id=rack_id_value,
            drawer=drawer_value,
            min_quantity=form.min_quantity.data if form.min_quantity.data and perms['can_edit_quantity'] else 0,
            no_stock_warning=form.no_stock_warning.data if perms['can_edit_quantity'] else True,
            category_id=form.category_id.data if form.category_id.data and form.category_id.data > 0 and perms['can_edit_category'] else None,
            footprint_id=form.footprint_id.data if form.footprint_id.data and form.footprint_id.data > 0 and perms['can_edit_footprint'] else None,
            tags=tags_json,
            lend_to=form.lend_to.data if perms['can_edit_lending'] else None,
            lend_quantity=form.lend_quantity.data if form.lend_quantity.data and perms['can_edit_lending'] else 0,
            datasheet_urls=form.datasheet_urls.data if perms['can_edit_datasheet'] else None,
            created_by=current_user.id,
            updated_by=current_user.id
        )
        db.session.add(item)
        db.session.commit()
        
        log_audit(current_user.id, 'create', 'item', item.id, f'Created item: {item.name}')
        flash(f'Item "{item.name}" created successfully!', 'success')
        return redirect(url_for('item.item_detail', uuid=item.uuid))
    
    return render_template('item_form.html', form=form, locations=locations, racks=racks, racks_data=racks_data, all_tags=all_tags, title='New Item',
                         prefill_rack_id=prefill_rack_id, prefill_drawer=prefill_drawer, 
                         currency=Setting.get('currency', '$'),
                         item_perms=perms)



@item_bp.route('/item/<string:uuid>', endpoint='item_detail')
@login_required
def item_detail(uuid):
    item = Item.query.filter_by(uuid=uuid).first_or_404()
    
    # Check if user has view permission
    if not current_user.has_permission('items', 'view'):
        flash('You do not have permission to view items.', 'danger')
        return redirect(url_for('item.items'))
    
    attachment_form = AttachmentForm()
    currency_symbol = Setting.get('currency', '$')
    
    # Get available QR sticker templates for Items
    from models import StickerTemplate
    qr_templates = StickerTemplate.query.filter_by(template_type='Items').all()
    
    return render_template('item_detail.html', item=item, attachment_form=attachment_form, 
                         currency_symbol=currency_symbol, qr_templates=qr_templates)



@item_bp.route('/item/<string:uuid>/edit', endpoint='item_edit', methods=['GET', 'POST'])
@login_required
@item_permission_required
def item_edit(uuid):
    from models import Tag
    from forms import ItemEditForm
    import json
    
    item = Item.query.filter_by(uuid=uuid).first_or_404()
    
    # Get user permissions for this item
    perms = get_item_edit_permissions(current_user)
    
    # Check if user has any edit permissions
    if not (perms.get('can_edit_name') or perms.get('can_edit_sku_type') or 
            perms.get('can_edit_description') or perms.get('can_edit_datasheet') or
            perms.get('can_edit_upload') or perms.get('can_edit_lending') or
            perms.get('can_edit_price') or perms.get('can_edit_quantity') or
            perms.get('can_edit_location') or perms.get('can_edit_category') or
            perms.get('can_edit_footprint') or perms.get('can_edit_tags') or
            perms.get('can_edit_parameters')):
        flash('You do not have permission to edit items.', 'danger')
        return redirect(url_for('item.item_detail', uuid=item.uuid))
    
    # Create form with permission-based field disabling
    form = ItemEditForm(obj=item, perms=perms)
    locations = Location.query.order_by(Location.name).all()
    racks = Rack.query.order_by(Rack.name).all()
    racks_data = [{'id': r.id, 'name': r.name, 'rows': r.rows, 'cols': r.cols, 
                   'unavailable_drawers': r.get_unavailable_drawers()} for r in racks]
    all_tags = [{'id': t.id, 'name': t.name, 'color': t.color} for t in Tag.query.order_by(Tag.name).all()]
    
    if form.validate_on_submit():
        # Check if user has permission to edit anything
        if not (perms.get('can_edit_name') or perms.get('can_edit_sku_type') or 
                perms.get('can_edit_description') or perms.get('can_edit_datasheet') or
                perms.get('can_edit_upload') or perms.get('can_edit_lending') or
                perms.get('can_edit_price') or perms.get('can_edit_quantity') or
                perms.get('can_edit_location') or perms.get('can_edit_category') or
                perms.get('can_edit_footprint') or perms.get('can_edit_tags') or
                perms.get('can_edit_parameters')):
            flash('You do not have permission to edit this item.', 'danger')
            return redirect(url_for('item.item_detail', uuid=item.uuid))
        
        # Only update fields user has permission for
        if perms['can_edit_name']:
            item.name = form.name.data
        
        if perms['can_edit_sku_type']:
            item.sku = form.sku.data if form.sku.data else None
            item.info = form.info.data
        
        if perms['can_edit_description']:
            item.description = form.description.data
        
        if perms['can_edit_datasheet']:
            item.datasheet_urls = form.datasheet_urls.data
        
        if perms['can_edit_lending']:
            item.lend_to = form.lend_to.data
            item.lend_quantity = form.lend_quantity.data or 0
        
        if perms['can_edit_price']:
            item.price = form.price.data
        
        if perms['can_edit_quantity']:
            item.quantity = form.quantity.data
            item.min_quantity = form.min_quantity.data
            item.no_stock_warning = form.no_stock_warning.data
        
        if perms['can_edit_location']:
            location_id = form.location_id.data if form.location_id.data else None
            rack_id = request.form.get('rack_id')
            drawer = request.form.get('drawer')
            
            # Determine location type
            if rack_id and int(rack_id) > 0:
                # Drawer storage
                item.location_id = None
                item.rack_id = int(rack_id)
                item.drawer = drawer
            else:
                # General location
                item.location_id = location_id if location_id and location_id != 0 else None
                item.rack_id = None
                item.drawer = None
        
        if perms['can_edit_category']:
            item.category_id = form.category_id.data if form.category_id.data and form.category_id.data > 0 else None
        
        if perms['can_edit_footprint']:
            item.footprint_id = form.footprint_id.data if form.footprint_id.data and form.footprint_id.data > 0 else None
        
        if perms['can_edit_tags']:
            # Get selected tags
            selected_tags = request.form.getlist('tags[]')
            tags_json = json.dumps([int(t) for t in selected_tags if t])
            item.tags = tags_json
        
        item.updated_at = datetime.now(timezone.utc)
        item.updated_by = current_user.id
        
        db.session.commit()
        
        log_audit(current_user.id, 'update', 'item', item.id, f'Updated item: {item.name}')
        flash(f'Item "{item.name}" updated successfully!', 'success')
        return redirect(url_for('item.item_detail', uuid=item.uuid))
    
    # Get file upload settings
    max_size_mb = int(Setting.get('max_file_size_mb', '10'))
    extensions_str = Setting.get('allowed_extensions', 'pdf,png,jpg,jpeg,gif,txt,doc,docx')
    
    return render_template('item_form.html', form=form, item=item, locations=locations, racks=racks, racks_data=racks_data, all_tags=all_tags, title='Edit Item', currency=Setting.get('currency', '$'), max_file_size_mb=max_size_mb, allowed_file_types=extensions_str, item_perms=perms)



@item_bp.route('/item/<string:uuid>/delete', endpoint='item_delete', methods=['POST'])
@login_required
@item_permission_required
def item_delete(uuid):
    item = Item.query.filter_by(uuid=uuid).first_or_404()
    
    # Check if user has permission to delete items
    perms = get_item_edit_permissions(current_user)
    if not perms.get('can_delete'):
        flash('You do not have permission to delete items.', 'danger')
        return redirect(url_for('item.item_detail', uuid=item.uuid))
    
    item_name = item.name

    for attachment in item.attachments:
        try:
            if attachment.file_path and is_safe_file_path(attachment.file_path):
                if os.path.exists(attachment.file_path):
                    os.remove(attachment.file_path)
        except Exception as e:
            logging.error(f"Error deleting attachment file {attachment.id}: {e}")

    from models import ItemParameter
    ItemParameter.query.filter_by(item_id=item.id).delete()

    db.session.delete(item)
    db.session.commit()
    
    log_audit(current_user.id, 'delete', 'item', item.id, f'Deleted item: {item_name}')
    flash(f'Item "{item_name}" deleted successfully!', 'success')
    return redirect(url_for('item.items'))



@item_bp.route('/items/bulk-delete', endpoint='bulk_delete_items', methods=['POST'])
@login_required
def bulk_delete_items():
    """Bulk delete items (password should be verified before calling this)"""
    try:
        # Check if user has permission to delete items
        if not current_user.has_permission('items', 'delete'):
            return jsonify({'success': False, 'message': 'You do not have permission to delete items.'}), 403
        
        # Get JSON data
        data = request.get_json()
        item_ids = data.get('item_ids', [])
        
        # Validate item_ids
        if not item_ids or not isinstance(item_ids, list):
            return jsonify({'success': False, 'message': 'No items selected.'}), 400
        
        # Convert to integers
        try:
            item_ids = [int(id) for id in item_ids]
        except (ValueError, TypeError):
            return jsonify({'success': False, 'message': 'Invalid item IDs.'}), 400
        
        # Get items to delete
        items_to_delete = Item.query.filter(Item.id.in_(item_ids)).all()
        
        if not items_to_delete:
            return jsonify({'success': False, 'message': 'No items found to delete.'}), 404
        
        deleted_items = []
        deleted_count = 0
        
        # Delete each item
        for item in items_to_delete:
            item_name = item.name
            item_id = item.id
            
            # Delete attachments
            for attachment in item.attachments:
                try:
                    if attachment.file_path and is_safe_file_path(attachment.file_path):
                        if os.path.exists(attachment.file_path):
                            os.remove(attachment.file_path)
                except Exception as e:
                    logging.error(f"Error deleting attachment file {attachment.id}: {e}")
            
            # Delete item parameters
            from models import ItemParameter
            ItemParameter.query.filter_by(item_id=item.id).delete()
            
            # Delete the item
            db.session.delete(item)
            deleted_items.append(f"{item_name} (ID: {item_id})")
            deleted_count += 1
        
        # Commit all deletions
        db.session.commit()
        
        # Create audit log entry
        deleted_items_str = ", ".join(deleted_items)
        log_audit(
            current_user.id, 
            'bulk_delete', 
            'item', 
            None,  # No single entity ID for bulk operation
            f'Bulk deleted {deleted_count} items: {deleted_items_str}'
        )
        
        return jsonify({
            'success': True, 
            'deleted_count': deleted_count,
            'message': f'Successfully deleted {deleted_count} item(s).'
        }), 200
        
    except Exception as e:
        db.session.rollback()
        logging.error(f"Error in bulk delete: {e}")
        return jsonify({'success': False, 'message': 'An error occurred during deletion.'}), 500


# ============= ATTACHMENT ROUTES =============



@item_bp.route('/item/<int:item_id>/upload', methods=['POST'], endpoint='upload_attachment')
@login_required
@item_permission_required
def upload_attachment(item_id):
    item = Item.query.get_or_404(item_id)
    form = AttachmentForm()
    
    # SECURITY CHECK: Verify user has upload permission
    if not current_user.has_permission('items', 'edit_upload'):
        flash('❌ You do not have permission to upload files.', 'danger')
        log_audit(current_user.id, 'denied', 'attachment_upload', item.id, f'Unauthorized upload attempt to item: {item.name}')
        return redirect(url_for('item.item_detail', uuid=item.uuid))
    
    files = request.files.getlist('files')
    
    # Get dynamic settings
    max_size_mb = int(Setting.get('max_file_size_mb', '10'))
    max_size_bytes = max_size_mb * 1024 * 1024
    extensions_str = Setting.get('allowed_extensions', 'pdf,png,jpg,jpeg,gif,txt,doc,docx')
    allowed_extensions = set(ext.strip().lower() for ext in extensions_str.split(',') if ext.strip())
    
    uploaded_count = 0
    rejected_count = 0
    
    for file in files:
        if not file or not file.filename:
            continue
            
        # Check file extension
        if not allowed_file(file.filename):
            flash(f'❌ File "{file.filename}" rejected: Incompatible file type. Allowed: {extensions_str}', 'danger')
            rejected_count += 1
            continue
        
        # Check file size
        file.seek(0, 2)  # Seek to end
        file_size = file.tell()
        file.seek(0)  # Reset to beginning
        
        if file_size > max_size_bytes:
            flash(f'❌ File "{file.filename}" rejected: Too large ({format_file_size(file_size)}). Max: {max_size_mb}MB', 'danger')
            rejected_count += 1
            continue
        
        file_info = save_file(file, current_app.config['UPLOAD_FOLDER'], item.uuid)
        
        if file_info:
            attachment = Attachment(
                filename=file_info['filename'],
                original_filename=file_info['original_filename'],
                file_path=file_info['file_path'],
                file_type=file_info['file_type'],
                file_size=file_info['file_size'],
                item_id=item.id,
                uploaded_by=current_user.id
            )
            db.session.add(attachment)
            uploaded_count += 1
    
    if uploaded_count > 0:
        db.session.commit()
        log_audit(current_user.id, 'upload', 'attachment', item.id, f'Uploaded {uploaded_count} file(s) to item: {item.name}')
        flash(f'✅ {uploaded_count} file(s) uploaded successfully!', 'success')
    
    if rejected_count > 0 and uploaded_count == 0:
        flash(f'⚠️ All {rejected_count} file(s) were rejected. Check file types and sizes above.', 'warning')
    
    return redirect(url_for('item.item_detail', uuid=item.uuid))



@item_bp.route('/attachment/<int:id>/delete', methods=['POST'])
@login_required
@item_permission_required
def delete_attachment(id):
    attachment = Attachment.query.get_or_404(id)
    item = attachment.item
    
    try:
        if attachment.file_path and is_safe_file_path(attachment.file_path):
            if os.path.exists(attachment.file_path):
                os.remove(attachment.file_path)
    except Exception as e:
        logging.error(f"Error deleting attachment file {attachment.id}: {e}")
    
    db.session.delete(attachment)
    db.session.commit()
    
    log_audit(current_user.id, 'delete', 'attachment', id, f'Deleted attachment: {attachment.original_filename}')
    flash('Attachment deleted successfully!', 'success')
    return redirect(url_for('item.item_edit', uuid=item.uuid))



@item_bp.route('/attachment/<int:attachment_id>/rename', methods=['POST'])
@login_required
@item_permission_required
def rename_attachment(attachment_id):
    """Rename an attachment file"""
    attachment = Attachment.query.get_or_404(attachment_id)
    
    try:
        data = request.get_json()
        new_name = data.get('new_name', '').strip()
        
        if not new_name:
            return jsonify({'success': False, 'error': 'New name cannot be empty'}), 400
        
        # Update the original filename
        old_name = attachment.original_filename
        attachment.original_filename = new_name
        db.session.commit()
        
        log_audit(current_user.id, 'update', 'attachment', attachment_id, f'Renamed attachment from "{old_name}" to "{new_name}"')

        return jsonify({'success': True})

    except Exception as e:
        logging.error(f"Error renaming attachment {attachment_id}: {str(e)}")
        return jsonify({'success': False, 'error': 'An error occurred while renaming the attachment'}), 500




@item_bp.route('/item/<int:item_id>/datasheets', methods=['POST'])
@login_required
@item_permission_required
def update_datasheets(item_id):
    """Update item datasheet URLs via AJAX"""
    item = Item.query.get_or_404(item_id)
    
    try:
        data = request.get_json()
        datasheets = data.get('datasheets', [])
        
        # Validate datasheets
        for ds in datasheets:
            if not isinstance(ds, dict) or 'url' not in ds:
                return jsonify({'success': False, 'error': 'Invalid datasheet format'}), 400
            if not ds['url'].strip():
                return jsonify({'success': False, 'error': 'URL cannot be empty'}), 400
        
        # Save as JSON
        import json
        item.datasheet_urls = json.dumps(datasheets)
        db.session.commit()
        
        log_audit(current_user.id, 'update', 'item', item.id, f'Updated datasheets for item: {item.name}')

        return jsonify({'success': True})

    except Exception as e:
        logging.error(f"Error updating datasheets for item {item_id}: {str(e)}")
        return jsonify({'success': False, 'error': 'An error occurred while updating datasheets'}), 500




@item_bp.route('/item/<int:id>/populate-template', methods=['POST'])
@login_required
@item_permission_required
def item_populate_template(id):
    from models import ItemParameter, ParameterTemplate
    item = Item.query.get_or_404(id)
    
    # SECURITY CHECK: Verify user has parameter edit permission
    if not current_user.has_permission('items', 'edit_parameters'):
        flash('❌ You do not have permission to apply templates.', 'danger')
        log_audit(current_user.id, 'denied', 'item_template_apply', id, f'Unauthorized template apply attempt to item: {item.name}')
        return redirect(url_for('item.item_edit', uuid=item.uuid))
    
    template_id = int(request.form.get('template_id', 0))
    
    template = ParameterTemplate.query.get(template_id)
    if not template:
        flash('Invalid template selected!', 'danger')
        return redirect(url_for('item.item_edit', uuid=item.uuid))
    
    # Add all template parameters to the item
    added_count = 0
    for tp in template.template_parameters:
        item_param = ItemParameter(
            item_id=id,
            parameter_id=tp.parameter_id,
            operation=tp.operation,
            value=tp.value,
            value2=tp.value2,
            unit=tp.unit,
            string_option=tp.string_option,
            description=tp.description
        )
        db.session.add(item_param)
        added_count += 1
    
    db.session.commit()
    
    log_audit(current_user.id, 'update', 'item', id, f'Applied template "{template.name}" to item: {item.name}')
    flash(f'Added {added_count} parameters from template "{template.name}"!', 'success')
    return redirect(url_for('item.item_edit', uuid=item.uuid))




@item_bp.route('/item/<int:id>/add-parameter', methods=['POST'])
@login_required
@item_permission_required
def item_add_parameter(id):
    from models import ItemParameter, MagicParameter
    item = Item.query.get_or_404(id)
    
    # SECURITY CHECK: Verify user has parameter edit permission
    if not current_user.has_permission('items', 'edit_parameters'):
        flash('❌ You do not have permission to add parameters.', 'danger')
        log_audit(current_user.id, 'denied', 'item_parameter_add', id, f'Unauthorized parameter add attempt to item: {item.name}')
        return redirect(url_for('item.item_edit', uuid=item.uuid))
    
    # Get form data
    param_type = request.form.get('param_type')
    parameter_id = int(request.form.get('parameter_id', 0))
    operation = request.form.get('operation')
    value = request.form.get('value', '').strip()
    value2 = request.form.get('value2', '').strip()
    unit = request.form.get('unit', '').strip()
    string_option = request.form.get('string_option', '').strip()
    description = request.form.get('description', '').strip()
    
    # Validate parameter exists
    parameter = MagicParameter.query.get(parameter_id)
    if not parameter:
        flash('Invalid parameter selected!', 'danger')
        return redirect(url_for('item.item_edit', uuid=item.uuid))
    
    # Create new item parameter
    item_param = ItemParameter(
        item_id=id,
        parameter_id=parameter_id,
        operation=operation if param_type in ['number', 'date'] else None,
        value=value if param_type in ['number', 'date'] else None,
        value2=value2 if operation in ['range', 'duration'] else None,
        unit=unit if param_type == 'number' else None,
        string_option=string_option if param_type == 'string' else None,
        description=description
    )
    
    db.session.add(item_param)
    db.session.commit()
    
    log_audit(current_user.id, 'update', 'item', id, f'Added parameter to item: {item.name}')
    flash('Parameter added successfully!', 'success')
    return redirect(url_for('item.item_edit', uuid=item.uuid))




@item_bp.route('/item/<int:item_id>/delete-parameter/<int:param_id>', methods=['POST'])
@login_required
@item_permission_required
def item_delete_parameter(item_id, param_id):
    from models import ItemParameter
    item = Item.query.get_or_404(item_id)
    item_param = ItemParameter.query.get_or_404(param_id)
    
    # SECURITY CHECK: Verify user has parameter edit permission
    if not current_user.has_permission('items', 'edit_parameters'):
        flash('❌ You do not have permission to delete parameters.', 'danger')
        log_audit(current_user.id, 'denied', 'item_parameter_delete', item_id, f'Unauthorized parameter delete attempt to item: {item.name}')
        return redirect(url_for('item.item_edit', uuid=item.uuid))
    
    if item_param.item_id != item_id:
        flash('Invalid parameter!', 'danger')
        return redirect(url_for('item.item_edit', uuid=item.uuid))
    
    db.session.delete(item_param)
    db.session.commit()
    
    log_audit(current_user.id, 'update', 'item', item_id, f'Removed parameter from item: {item.name}')
    flash('Parameter removed successfully!', 'success')
    return redirect(url_for('item.item_edit', uuid=item.uuid))




@item_bp.route('/item/<int:item_id>/edit-parameter/<int:param_id>', methods=['GET', 'POST'])
@login_required
@item_permission_required
def item_edit_parameter(item_id, param_id):
    from models import ItemParameter, MagicParameter
    item = Item.query.get_or_404(item_id)
    item_param = ItemParameter.query.get_or_404(param_id)
    
    if item_param.item_id != item_id:
        flash('Invalid parameter!', 'danger')
        return redirect(url_for('item.item_edit', uuid=item.uuid))
    
    if request.method == 'POST':
        # Update parameter values
        item_param.operation = request.form.get('operation')
        item_param.value = request.form.get('value', '').strip()
        item_param.value2 = request.form.get('value2', '').strip() if request.form.get('operation') in ['range', 'duration'] else None
        item_param.unit = request.form.get('unit', '').strip()
        item_param.string_option = request.form.get('string_option', '').strip()
        item_param.description = request.form.get('description', '').strip()
        
        db.session.commit()
        
        log_audit(current_user.id, 'update', 'item', item_id, f'Updated parameter for item: {item.name}')
        flash('Parameter updated successfully!', 'success')
        return redirect(url_for('item.item_edit', uuid=item.uuid))
    
    return render_template('item_parameter_edit.html', item=item, item_param=item_param)




@item_bp.route('/items/print', endpoint='items_print')
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
        
        if search_query:
            query = query.filter(
                db.or_(
                    Item.name.ilike(f'%{search_query}%'),
                    Item.description.ilike(f'%{search_query}%'),
                    Item.sku.ilike(f'%{search_query}%')
                )
            )
        
        if category_id > 0:
            query = query.filter_by(category_id=category_id)
        
        # Apply status filter
        if status_filter:
            statuses = status_filter.split(',')
            filtered_items = []
            
            for item in query.all():
                if 'ok' in statuses and not item.is_no_stock() and not item.is_low_stock():
                    filtered_items.append(item)
                elif 'low' in statuses and item.is_low_stock():
                    filtered_items.append(item)
                elif 'no' in statuses and item.is_no_stock():
                    filtered_items.append(item)
            
            # Sort by updated_at descending
            filtered_items.sort(key=lambda x: x.updated_at, reverse=True)
            
            # Manually paginate
            total = len(filtered_items)
            start = (page - 1) * per_page
            end = start + per_page
            items = filtered_items[start:end]
            
            # Create a manual pagination object
            class Pagination:
                def __init__(self, items, page, per_page, total):
                    self.items = items
                    self.page = page
                    self.per_page = per_page
                    self.total = total
                    self.pages = (total + per_page - 1) // per_page
                
                @property
                def has_next(self):
                    return self.page < self.pages
                
                @property
                def has_prev(self):
                    return self.page > 1
                
                @property
                def next_num(self):
                    return self.page + 1 if self.has_next else None
                
                @property
                def prev_num(self):
                    return self.page - 1 if self.has_prev else None
                
                def iter_pages(self, left_edge=1, right_edge=1, left_current=1, right_current=2):
                    for num in range(1, self.pages + 1):
                        if (num <= left_edge or
                            num > self.pages - right_edge or
                            (self.page - left_current <= num <= self.page + right_current)):
                            yield num
                        elif num == left_edge + 1 or num == self.pages - right_edge:
                            yield None
            
            pagination = Pagination(items, page, per_page, total)
        else:
            # Default sort by updated_at descending
            pagination = query.order_by(Item.updated_at.desc()).paginate(
                page=page, per_page=per_page, error_out=False
            )
    
    items = pagination.items
    
    # Get user's table columns preference
    user_columns = current_user.get_table_columns()
    currency_symbol = Setting.get('currency', '$')
    currency_decimal_places = int(Setting.get('currency_decimal_places', '2'))
    
    # Get current datetime for footer
    from datetime import datetime
    current_datetime = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    
    return render_template('items_print.html', 
                         items=items,
                         page=page,
                         per_page=per_page,
                         view_type=view_type,
                         user_columns=user_columns,
                         currency_symbol=currency_symbol,
                         currency_decimal_places=currency_decimal_places,
                         current_user=current_user,
                         current_datetime=current_datetime)



@item_bp.route('/item/<string:uuid>/print')
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
    from datetime import datetime
    current_datetime = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    
    # Parse datasheets
    datasheets = []
    if item.datasheet_urls:
        try:
            import json
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


# ============= QR/BARCODE STICKER TEMPLATE ROUTES =============



@item_bp.route('/api/item/<string:uuid>/sticker-preview/<int:template_id>')
@login_required
def api_item_sticker_preview(uuid, template_id):
    """
    Generate sticker preview for an item with a specific template
    Returns: SVG image
    """
    from models import StickerTemplate
    item = Item.query.filter_by(uuid=uuid).first_or_404()
    template = StickerTemplate.query.get_or_404(template_id)
    
    # Verify template is for Items type
    if template.template_type != 'Items':
        return jsonify({'error': 'Template must be for Items'}), 400
    
    # Get item data with all placeholders
    data = get_item_data(item)
    
    # Render to SVG
    svg_data = render_template_to_svg(template, data)
    
    return jsonify({
        'svg': svg_data,
        'width_mm': template.width_mm,
        'height_mm': template.height_mm,
        'template_name': template.name
    })



@item_bp.route('/api/item/<string:uuid>/sticker-print/<int:template_id>')
@login_required
def api_item_sticker_print(uuid, template_id):
    """
    Generate printable sticker for an item
    Returns: PDF file download
    """
    from models import StickerTemplate
    item = Item.query.filter_by(uuid=uuid).first_or_404()
    template = StickerTemplate.query.get_or_404(template_id)
    
    if template.template_type != 'Items':
        return jsonify({'error': 'Template must be for Items'}), 400
    
    data = get_item_data(item)
    
    # Generate single-sticker PDF
    output = generate_single_sticker_pdf(template, data, item.uuid)
    
    log_audit(current_user.id, 'print', 'item', item.id, 
             f'Printed sticker: {template.name}')
    
    return send_file(
        output, 
        mimetype='application/pdf',
        as_attachment=True,
        download_name=f'{template.name}_{item.uuid}.pdf'
    )



@item_bp.route('/item/<string:uuid>/qr-sticker')
@login_required
def item_qr_sticker(uuid):
    """
    Page showing QR sticker preview and print options for an item
    """
    from models import StickerTemplate
    item = Item.query.filter_by(uuid=uuid).first_or_404()
    
    # Get all "Items" type templates
    templates = StickerTemplate.query.filter_by(template_type='Items').all()
    
    if not templates:
        flash('No QR/Barcode templates available for items.', 'warning')
        return redirect(url_for('item.item_detail', uuid=uuid))
    
    return render_template('item_qr_sticker.html', item=item, templates=templates)


# ============= ERROR HANDLERS =============



