"""
Batch Routes Blueprint - Manages item batches, transfers, and serial numbers
"""
from flask import Blueprint, render_template, redirect, url_for, flash, request, jsonify
from flask_login import login_required, current_user
from models import db, Item, ItemBatch, BatchSerialNumber, BatchLendRecord, Setting
from utils import log_audit
from datetime import datetime, date
import logging
import json

logger = logging.getLogger(__name__)

batch_bp = Blueprint('batch', __name__)


def _parse_date(s):
    try:
        return datetime.strptime(s, '%Y-%m-%d').date() if s else None
    except ValueError:
        return None


def _save_lend_records(batch, records_data, max_qty):
    """Create BatchLendRecord rows from a list of dicts (as submitted from JS)."""
    for r in records_data:
        if not isinstance(r, dict):
            continue
        contact_id_raw = r.get('contact_id')
        try:
            contact_id = int(contact_id_raw) if contact_id_raw else None
        except (ValueError, TypeError):
            contact_id = None
        try:
            qty = max(1, min(int(r.get('qty', 1)), max_qty))
        except (ValueError, TypeError):
            qty = 1
        try:
            days = int(r.get('days', 3))
        except (ValueError, TypeError):
            days = 3
        rec = BatchLendRecord(
            batch_id=batch.id,
            lend_to_type=r.get('type', '').strip(),
            lend_to_id=contact_id,
            quantity=qty,
            lend_start=_parse_date(r.get('start', '')),
            lend_end=_parse_date(r.get('end', '')),
            lend_notify_enabled=bool(r.get('notify', False)),
            lend_notify_before_days=days,
        )
        db.session.add(rec)


@batch_bp.route('/item/<string:uuid>/batch/add', methods=['POST'])
@login_required
def add_batch(uuid):
    """Add a new batch to an item"""
    item = Item.query.filter_by(uuid=uuid).first_or_404()

    # Adding a batch requires at least the general batch-edit permission.
    if not current_user.has_permission('items', 'edit_batch'):
        flash('You do not have permission to manage batches.', 'danger')
        return redirect(url_for('item.item_detail', uuid=uuid))

    can_edit_qty = current_user.has_permission('items', 'edit_quantity')
    can_edit_price = current_user.has_permission('items', 'edit_price')
    can_edit_sn = current_user.has_permission('items', 'edit_sn')
    can_edit_lending = current_user.has_permission('items', 'edit_lending')

    batch_label = request.form.get('batch_label', '').strip()[:32]
    quantity = int(request.form.get('quantity', 0)) if can_edit_qty else 0
    price_per_unit = float(request.form.get('price_per_unit', 0)) if can_edit_price else 0.0
    purchase_date_str = request.form.get('purchase_date', '')
    note = request.form.get('note', '').strip()[:128]
    lend_records_json = request.form.get('lend_records', '[]') if can_edit_lending else '[]'
    try:
        lend_records_data = json.loads(lend_records_json)
    except (ValueError, TypeError):
        lend_records_data = []
    sn_tracking = (request.form.get('sn_tracking', '') == 'on') if can_edit_sn else False

    # Per-batch location
    follow_main = request.form.get('follow_main_location', '') == 'on'
    batch_loc_id_raw = request.form.get('batch_location_id', '')
    batch_rack_id_raw = request.form.get('batch_rack_id', '')
    batch_drawer = request.form.get('batch_drawer', '').strip() or None
    try:
        batch_loc_id = int(batch_loc_id_raw) if batch_loc_id_raw else None
    except (ValueError, TypeError):
        batch_loc_id = None
    try:
        batch_rack_id = int(batch_rack_id_raw) if batch_rack_id_raw else None
    except (ValueError, TypeError):
        batch_rack_id = None
    if follow_main:
        batch_loc_id = None
        batch_rack_id = None
        batch_drawer = None
    elif batch_rack_id:
        batch_loc_id = None  # rack overrides general location
    else:
        batch_rack_id = None
        batch_drawer = None

    if quantity < 0:
        flash('Quantity cannot be negative.', 'danger')
        return redirect(url_for('item.item_detail', uuid=uuid))

    # Limit per batch: 100 if tracking, otherwise 99999
    max_qty = 100 if sn_tracking else 99999
    if quantity > max_qty:
        quantity = max_qty

    purchase_date = None
    if purchase_date_str:
        try:
            purchase_date = datetime.strptime(purchase_date_str, '%Y-%m-%d').date()
        except ValueError:
            pass

    batch_number = item.get_next_batch_number()

    batch = ItemBatch(
        item_id=item.id,
        batch_number=batch_number,
        batch_label=batch_label or None,
        quantity=quantity,
        price_per_unit=price_per_unit,
        purchase_date=purchase_date,
        note=note or None,
        sn_tracking_enabled=sn_tracking,
        follow_main_location=follow_main,
        location_id=batch_loc_id,
        rack_id=batch_rack_id,
        drawer=batch_drawer,
    )
    db.session.add(batch)
    db.session.flush()  # Get batch id

    # Create lending records (only for non-SN batches)
    if can_edit_lending and not sn_tracking:
        _save_lend_records(batch, lend_records_data, quantity)

    # Generate serial numbers if tracking is enabled for this batch
    if sn_tracking:
        batch.generate_serial_numbers()

    # Recalculate item totals
    item.recalculate_from_batches()
    item.updated_by = current_user.id

    db.session.commit()

    log_audit(current_user.id, 'create', 'batch', batch.id,
              f'Added batch #{batch_number} to item: {item.name} (qty: {quantity}, price: {price_per_unit})')
    flash(f'Batch "{batch.get_display_label()}" added successfully!', 'success')
    return redirect(url_for('item.item_edit', uuid=uuid) + '#batches-section')


@batch_bp.route('/item/<string:uuid>/batch/<int:batch_id>/edit', methods=['POST'])
@login_required
def edit_batch(uuid, batch_id):
    """Edit an existing batch"""
    item = Item.query.filter_by(uuid=uuid).first_or_404()
    batch = ItemBatch.query.get_or_404(batch_id)

    if batch.item_id != item.id:
        flash('Batch does not belong to this item.', 'danger')
        return redirect(url_for('item.item_detail', uuid=uuid))

    can_edit_batch = current_user.has_permission('items', 'edit_batch')
    can_edit_qty = current_user.has_permission('items', 'edit_quantity')
    can_edit_price = current_user.has_permission('items', 'edit_price')
    can_edit_sn = current_user.has_permission('items', 'edit_sn')
    can_edit_lending = current_user.has_permission('items', 'edit_lending')

    if not (can_edit_batch or can_edit_qty or can_edit_price or can_edit_lending or can_edit_sn):
        flash('You do not have permission to manage batches.', 'danger')
        return redirect(url_for('item.item_detail', uuid=uuid))

    old_qty = batch.quantity

    # General batch fields (label, date, note, location)
    if can_edit_batch:
        batch.batch_label = (request.form.get('batch_label', '').strip()[:32]) or None
        batch.note = (request.form.get('note', '').strip()[:128]) or None

        purchase_date_str = request.form.get('purchase_date', '')
        if purchase_date_str:
            try:
                batch.purchase_date = datetime.strptime(purchase_date_str, '%Y-%m-%d').date()
            except ValueError:
                pass
        else:
            batch.purchase_date = None

        # Per-batch location
        follow_main = request.form.get('follow_main_location', '') == 'on'
        batch.follow_main_location = follow_main
        if follow_main:
            batch.location_id = None
            batch.rack_id = None
            batch.drawer = None
        else:
            batch_loc_id_raw = request.form.get('batch_location_id', '')
            batch_rack_id_raw = request.form.get('batch_rack_id', '')
            batch_drawer = request.form.get('batch_drawer', '').strip() or None
            try:
                batch_loc_id = int(batch_loc_id_raw) if batch_loc_id_raw else None
            except (ValueError, TypeError):
                batch_loc_id = None
            try:
                batch_rack_id = int(batch_rack_id_raw) if batch_rack_id_raw else None
            except (ValueError, TypeError):
                batch_rack_id = None
            if batch_rack_id:
                batch.location_id = None
                batch.rack_id = batch_rack_id
                batch.drawer = batch_drawer
            else:
                batch.location_id = batch_loc_id
                batch.rack_id = None
                batch.drawer = None

    # Quantity (only when SN tracking is off - else controlled via SN Add/Delete)
    if can_edit_qty and not batch.sn_tracking_enabled:
        try:
            new_qty = int(request.form.get('quantity', batch.quantity))
            batch.quantity = max(0, min(new_qty, 99999))
        except (ValueError, TypeError):
            pass

    # Price
    if can_edit_price:
        try:
            batch.price_per_unit = float(request.form.get('price_per_unit', batch.price_per_unit))
        except (ValueError, TypeError):
            pass

    # Lending records (only when SN tracking is off - per-SN lending used otherwise)
    if can_edit_lending and not batch.sn_tracking_enabled:
        lend_records_json = request.form.get('lend_records', '[]')
        try:
            lend_records_data = json.loads(lend_records_json)
        except (ValueError, TypeError):
            lend_records_data = []
        BatchLendRecord.query.filter_by(batch_id=batch.id).delete()
        _save_lend_records(batch, lend_records_data, batch.quantity)

    # Regenerate serial numbers if quantity changed and tracking enabled on this batch
    if batch.sn_tracking_enabled and batch.quantity != old_qty:
        batch.generate_serial_numbers()

    item.recalculate_from_batches()
    item.updated_by = current_user.id

    db.session.commit()

    log_audit(current_user.id, 'update', 'batch', batch.id,
              f'Updated batch #{batch.batch_number} of item: {item.name}')
    flash(f'Batch "{batch.get_display_label()}" updated successfully!', 'success')
    return redirect(url_for('item.item_edit', uuid=uuid) + '#batches-section')


@batch_bp.route('/item/<string:uuid>/batch/<int:batch_id>/manage_lend', methods=['POST'])
@login_required
def manage_lend(uuid, batch_id):
    """Save all lend records for a batch (replaces existing records)."""
    item = Item.query.filter_by(uuid=uuid).first_or_404()
    batch = ItemBatch.query.filter_by(id=batch_id, item_id=item.id).first_or_404()
    if batch.sn_tracking_enabled:
        return jsonify({'success': False, 'message': 'SN batches use per-SN lending.'})
    can_edit_lending = current_user.has_permission('items', 'edit_lending')
    if not can_edit_lending:
        return jsonify({'success': False, 'message': 'No permission.'})
    lend_records_json = request.form.get('lend_records', '[]')
    try:
        lend_records_data = json.loads(lend_records_json)
    except (ValueError, TypeError):
        lend_records_data = []
    BatchLendRecord.query.filter_by(batch_id=batch.id).delete()
    _save_lend_records(batch, lend_records_data, batch.quantity)
    db.session.commit()
    log_audit(current_user.id, 'batch_lend_update', item.id,
              f'Updated lend records for batch #{batch.batch_number} of item: {item.name}')
    return jsonify({'success': True, 'lend_qty': batch.get_lend_quantity()})


@login_required
def delete_batch(uuid, batch_id):
    """Delete a batch"""
    item = Item.query.filter_by(uuid=uuid).first_or_404()
    batch = ItemBatch.query.get_or_404(batch_id)
    
    if batch.item_id != item.id:
        flash('Batch does not belong to this item.', 'danger')
        return redirect(url_for('item.item_detail', uuid=uuid))

    if not current_user.has_permission('items', 'delete_batch'):
        flash('You do not have permission to delete batches.', 'danger')
        return redirect(url_for('item.item_detail', uuid=uuid))

    batch_label = batch.get_display_label()
    db.session.delete(batch)
    
    item.recalculate_from_batches()
    item.updated_by = current_user.id
    
    db.session.commit()
    
    log_audit(current_user.id, 'delete', 'batch', batch_id,
              f'Deleted batch "{batch_label}" from item: {item.name}')
    flash(f'Batch "{batch_label}" deleted successfully!', 'success')
    return redirect(url_for('item.item_edit', uuid=uuid) + '#batches-section')


@batch_bp.route('/item/<string:uuid>/batch/bulk-delete', methods=['POST'])
@login_required
def bulk_delete_batches(uuid):
    """Bulk delete batches"""
    item = Item.query.filter_by(uuid=uuid).first_or_404()

    if not current_user.has_permission('items', 'delete_batch'):
        return jsonify({'success': False, 'message': 'Permission denied'}), 403

    data = request.get_json()
    batch_ids = data.get('batch_ids', [])
    
    if not batch_ids:
        return jsonify({'success': False, 'message': 'No batches selected'}), 400
    
    deleted = 0
    for bid in batch_ids:
        batch = ItemBatch.query.get(int(bid))
        if batch and batch.item_id == item.id:
            db.session.delete(batch)
            deleted += 1
    
    item.recalculate_from_batches()
    item.updated_by = current_user.id
    db.session.commit()
    
    log_audit(current_user.id, 'bulk_delete', 'batch', None,
              f'Bulk deleted {deleted} batches from item: {item.name}')
    
    return jsonify({'success': True, 'deleted_count': deleted})


@batch_bp.route('/item/<string:uuid>/batch/transfer', methods=['POST'])
@login_required
def transfer_batch(uuid):
    """Transfer quantity between batches"""
    item = Item.query.filter_by(uuid=uuid).first_or_404()

    # Transferring changes both quantities; require quantity edit permission.
    if not current_user.has_permission('items', 'edit_quantity'):
        flash('You do not have permission to transfer quantities.', 'danger')
        return redirect(url_for('item.item_detail', uuid=uuid))
    
    from_batch_id = int(request.form.get('from_batch_id', 0))
    to_batch_id = int(request.form.get('to_batch_id', 0))
    transfer_qty = int(request.form.get('transfer_quantity', 0))
    
    if from_batch_id == to_batch_id:
        flash('Cannot transfer to the same batch.', 'danger')
        return redirect(url_for('item.item_detail', uuid=uuid))
    
    from_batch = ItemBatch.query.get_or_404(from_batch_id)
    to_batch = ItemBatch.query.get_or_404(to_batch_id)
    
    if from_batch.item_id != item.id or to_batch.item_id != item.id:
        flash('Batches do not belong to this item.', 'danger')
        return redirect(url_for('item.item_detail', uuid=uuid))
    
    if transfer_qty <= 0:
        flash('Transfer quantity must be positive.', 'danger')
        return redirect(url_for('item.item_detail', uuid=uuid))
    
    # Use max available quantity check instead of strictly absolute quantity
    available_qty = from_batch.get_available_quantity()
    if transfer_qty > available_qty:
        flash(f'Cannot transfer more than available quantity ({available_qty}). Ensure items are not lent or used in projects.', 'danger')
        return redirect(url_for('item.item_detail', uuid=uuid))
    
    # Block transfer from Tracking ON to Non-tracking (would lose SN data)
    if from_batch.sn_tracking_enabled and not to_batch.sn_tracking_enabled:
        flash('Cannot transfer from a tracked batch to a non-tracked batch. Serial number data would be lost.', 'danger')
        return redirect(url_for('item.item_detail', uuid=uuid))
    
    # Block transfer from Tracking ON via qty-based route (should use SN-based transfer)
    if from_batch.sn_tracking_enabled:
        flash('For tracked batches, use the Transfer button in the serial number table to select specific items.', 'warning')
        return redirect(url_for('item.item_detail', uuid=uuid))
    
    # Check destination batch won't exceed its limit
    dest_max = 100 if to_batch.sn_tracking_enabled else 99999
    if to_batch.quantity + transfer_qty > dest_max:
        flash(f'Destination batch would exceed limit of {dest_max}.', 'danger')
        return redirect(url_for('item.item_detail', uuid=uuid))
    
    from_batch.quantity -= transfer_qty
    to_batch.quantity += transfer_qty
    
    # If target has tracking enabled, generate new ISNs for the transferred qty
    if to_batch.sn_tracking_enabled:
        max_seq = db.session.query(db.func.max(BatchSerialNumber.sequence_number)).filter_by(batch_id=to_batch.id).scalar() or 0
        date_str = to_batch.purchase_date.strftime('%Y%m%d') if to_batch.purchase_date else '00000000'
        label = to_batch.batch_label or f"B{to_batch.batch_number}"
        for i in range(1, transfer_qty + 1):
            seq = max_seq + i
            isn = f"{item.uuid}-{date_str}-{label}-{seq:03d}"
            sn = BatchSerialNumber(
                batch_id=to_batch.id,
                sequence_number=seq,
                internal_serial_number=isn,
                serial_number='',
                info='',
            )
            db.session.add(sn)
    
    item.recalculate_from_batches()
    item.updated_by = current_user.id
    db.session.commit()
    
    log_audit(current_user.id, 'transfer', 'batch', None,
              f'Transferred {transfer_qty} from batch #{from_batch.batch_number} to #{to_batch.batch_number} in item: {item.name}')
    flash(f'Transferred {transfer_qty} units from "{from_batch.get_display_label()}" to "{to_batch.get_display_label()}".', 'success')
    return redirect(url_for('item.item_detail', uuid=uuid))


@batch_bp.route('/item/<string:uuid>/sn/toggle', methods=['POST'])
@login_required
def toggle_serial_numbers(uuid):
    """Legacy route - tracking is now per-batch. Redirect to item detail."""
    flash('Serial Number tracking is now configured per-batch when adding or editing batches.', 'info')
    return redirect(url_for('item.item_detail', uuid=uuid))


@batch_bp.route('/item/<string:uuid>/batch/<int:batch_id>/sn/update', methods=['POST'])
@login_required
def update_serial_numbers(uuid, batch_id):
    """Update user-editable serial numbers for a batch"""
    item = Item.query.filter_by(uuid=uuid).first_or_404()
    batch = ItemBatch.query.get_or_404(batch_id)
    
    if batch.item_id != item.id:
        flash('Batch does not belong to this item.', 'danger')
        return redirect(url_for('item.item_detail', uuid=uuid))
    
    if not current_user.has_permission('items', 'edit_sn'):
        flash('You do not have permission to manage serial numbers.', 'danger')
        return redirect(url_for('item.item_detail', uuid=uuid))
    
    # Update serial numbers from form
    for sn in batch.serial_numbers:
        new_sn = request.form.get(f'sn_{sn.id}', '').strip()
        sn.serial_number = new_sn
    
    db.session.commit()
    
    log_audit(current_user.id, 'update', 'serial_numbers', batch.id,
              f'Updated serial numbers for batch #{batch.batch_number} of item: {item.name}')
    flash(f'Serial numbers updated for "{batch.get_display_label()}".', 'success')
    return redirect(url_for('item.item_detail', uuid=uuid))


@batch_bp.route('/item/<string:uuid>/batch/<int:batch_id>/sn/update-info', methods=['POST'])
@login_required
def update_serial_info(uuid, batch_id):
    """Update info field for serial numbers in a batch"""
    item = Item.query.filter_by(uuid=uuid).first_or_404()
    batch = ItemBatch.query.get_or_404(batch_id)
    
    if batch.item_id != item.id:
        flash('Batch does not belong to this item.', 'danger')
        return redirect(url_for('item.item_detail', uuid=uuid))
    
    if not current_user.has_permission('items', 'edit_sn'):
        flash('You do not have permission to manage serial numbers.', 'danger')
        return redirect(url_for('item.item_detail', uuid=uuid))
    
    for sn in batch.serial_numbers:
        new_info = request.form.get(f'info_{sn.id}', '').strip()[:32]
        sn.info = new_info
    
    db.session.commit()
    
    log_audit(current_user.id, 'update', 'serial_info', batch.id,
              f'Updated serial info for batch #{batch.batch_number} of item: {item.name}')
    flash(f'Info updated for "{batch.get_display_label()}".', 'success')
    return redirect(url_for('item.item_detail', uuid=uuid))


@batch_bp.route('/item/<string:uuid>/batch/<int:batch_id>/sn/update-lend', methods=['POST'])
@login_required
def update_serial_lend(uuid, batch_id):
    """Update lend_to field for serial numbers in a batch"""
    item = Item.query.filter_by(uuid=uuid).first_or_404()
    batch = ItemBatch.query.get_or_404(batch_id)
    
    if batch.item_id != item.id:
        flash('Batch does not belong to this item.', 'danger')
        return redirect(url_for('item.item_detail', uuid=uuid))
    
    if not current_user.has_permission('items', 'edit_lending'):
        flash('You do not have permission to manage lending.', 'danger')
        return redirect(url_for('item.item_detail', uuid=uuid))
    
    for sn in batch.serial_numbers:
        lend_type = request.form.get(f'lend_type_{sn.id}', '').strip()
        lend_id_raw = request.form.get(f'lend_id_{sn.id}', '').strip()
        lend_start_str = request.form.get(f'lend_start_{sn.id}', '').strip()
        lend_end_str = request.form.get(f'lend_end_{sn.id}', '').strip()
        sn.lend_to_type = lend_type
        try:
            sn.lend_to_id = int(lend_id_raw) if lend_id_raw else None
        except (ValueError, TypeError):
            sn.lend_to_id = None
        try:
            sn.lend_start = datetime.strptime(lend_start_str, '%Y-%m-%d').date() if lend_start_str else None
        except ValueError:
            sn.lend_start = None
        try:
            sn.lend_end = datetime.strptime(lend_end_str, '%Y-%m-%d').date() if lend_end_str else None
        except ValueError:
            sn.lend_end = None
        sn.lend_notify_enabled = request.form.get(f'lend_notify_{sn.id}', '0') == '1'
        try:
            sn.lend_notify_before_days = int(request.form.get(f'lend_notify_days_{sn.id}', 3))
        except (ValueError, TypeError):
            sn.lend_notify_before_days = 3

    db.session.commit()

    log_audit(current_user.id, 'update', 'serial_lend', batch.id,
              f'Updated lending info for batch #{batch.batch_number} of item: {item.name}')
    flash(f'Lending info updated for "{batch.get_display_label()}".', 'success')
    return redirect(url_for('item.item_detail', uuid=uuid))


@batch_bp.route('/item/<string:uuid>/batch/sn/inline-update', methods=['POST'])
@login_required
def inline_update_sn(uuid):
    """Inline update a single SN field (sn, info, or lend)"""
    item = Item.query.filter_by(uuid=uuid).first_or_404()
    data = request.get_json()
    sn_id = data.get('sn_id')
    field = data.get('field')  # 'sn', 'info', 'lend'
    value = data.get('value', '')

    sn = BatchSerialNumber.query.get(sn_id)
    if not sn or sn.batch.item_id != item.id:
        return jsonify({'success': False, 'message': 'Invalid serial number'}), 400

    if field == 'sn':
        if not current_user.has_permission('items', 'edit_sn'):
            return jsonify({'success': False, 'message': 'Permission denied'}), 403
        sn.serial_number = value
    elif field == 'info':
        if not current_user.has_permission('items', 'edit_sn'):
            return jsonify({'success': False, 'message': 'Permission denied'}), 403
        sn.info = value[:32]
    elif field == 'lend':
        if not current_user.has_permission('items', 'edit_lending'):
            return jsonify({'success': False, 'message': 'Permission denied'}), 403
        sn.lend_to_type = data.get('lend_to_type', '').strip()
        lend_to_id_raw = data.get('lend_to_id')
        try:
            sn.lend_to_id = int(lend_to_id_raw) if lend_to_id_raw else None
        except (ValueError, TypeError):
            sn.lend_to_id = None
        lend_start_str = data.get('lend_start', '')
        lend_end_str = data.get('lend_end', '')
        try:
            sn.lend_start = datetime.strptime(lend_start_str, '%Y-%m-%d').date() if lend_start_str else None
        except ValueError:
            sn.lend_start = None
        try:
            sn.lend_end = datetime.strptime(lend_end_str, '%Y-%m-%d').date() if lend_end_str else None
        except ValueError:
            sn.lend_end = None
        sn.lend_notify_enabled = bool(data.get('lend_notify_enabled', False))
        try:
            sn.lend_notify_before_days = int(data.get('lend_notify_before_days', 3))
        except (ValueError, TypeError):
            sn.lend_notify_before_days = 3
    else:
        return jsonify({'success': False, 'message': 'Invalid field'}), 400

    db.session.commit()
    log_audit(current_user.id, 'update', 'serial_number', sn.id,
              f'Inline updated {field} for SN #{sn.sequence_number} in item: {item.name}')
    response = {'success': True}
    if field == 'lend':
        response['display'] = sn.get_lend_to_display() or '-'
    return jsonify(response)


@batch_bp.route('/item/<string:uuid>/batch/sn/bulk-update', methods=['POST'])
@login_required
def bulk_update_sn(uuid):
    """Bulk apply same values to multiple selected serial numbers"""
    item = Item.query.filter_by(uuid=uuid).first_or_404()
    data = request.get_json()
    sn_ids = data.get('sn_ids', [])
    fields = data.get('fields', {})

    can_edit_sn = current_user.has_permission('items', 'edit_sn')
    can_edit_lending = current_user.has_permission('items', 'edit_lending')

    count = 0
    for sn_id in sn_ids:
        sn = BatchSerialNumber.query.get(sn_id)
        if not sn or sn.batch.item_id != item.id:
            continue

        if 'sn' in fields and can_edit_sn:
            sn.serial_number = fields['sn']
            count += 1
        if 'info' in fields and can_edit_sn:
            sn.info = fields['info'][:32]
            count += 1
        if 'lend' in fields and can_edit_lending:
            lend_data = fields['lend']
            if lend_data is None:
                sn.lend_to_type = ''
                sn.lend_to_id = None
            elif isinstance(lend_data, dict):
                sn.lend_to_type = lend_data.get('type', '').strip()
                lend_id_raw = lend_data.get('id')
                try:
                    sn.lend_to_id = int(lend_id_raw) if lend_id_raw else None
                except (ValueError, TypeError):
                    sn.lend_to_id = None
            count += 1

    db.session.commit()
    log_audit(current_user.id, 'bulk_update', 'serial_numbers', None,
              f'Bulk updated {len(sn_ids)} SNs in item: {item.name}')
    return jsonify({'success': True, 'updated': count})


@batch_bp.route('/item/<string:uuid>/batch/sn/delete-selected', methods=['POST'])
@login_required
def delete_selected_sn(uuid):
    """Delete selected serial numbers and reduce batch quantity"""
    item = Item.query.filter_by(uuid=uuid).first_or_404()

    # Needs both SN edit (to remove SNs) and quantity edit (quantity is reduced).
    if not (current_user.has_permission('items', 'edit_sn') and
            current_user.has_permission('items', 'edit_quantity')):
        return jsonify({'success': False, 'message': 'Permission denied'}), 403

    data = request.get_json()
    sn_ids = data.get('sn_ids', [])
    batch_id = data.get('batch_id')

    batch = ItemBatch.query.get(batch_id)
    if not batch or batch.item_id != item.id:
        return jsonify({'success': False, 'message': 'Invalid batch'}), 400

    deleted = 0
    for sn_id in sn_ids:
        sn = BatchSerialNumber.query.get(sn_id)
        if sn and sn.batch_id == batch.id:
            db.session.delete(sn)
            deleted += 1

    # Update batch quantity
    batch.quantity = max(batch.quantity - deleted, 0)

    # Re-sequence the remaining serial numbers
    remaining = BatchSerialNumber.query.filter_by(batch_id=batch.id).order_by(BatchSerialNumber.sequence_number).all()
    for idx, sn in enumerate(remaining, 1):
        sn.sequence_number = idx

    item.recalculate_from_batches()
    item.updated_by = current_user.id
    db.session.commit()

    log_audit(current_user.id, 'delete', 'serial_numbers', batch.id,
              f'Deleted {deleted} SNs from batch #{batch.batch_number} of item: {item.name}')
    return jsonify({'success': True, 'deleted': deleted})


@batch_bp.route('/item/<string:uuid>/batch/sn/transfer-selected', methods=['POST'])
@login_required
def transfer_selected_sn(uuid):
    """Transfer selected serial numbers to another batch (ISN kept as-is)"""
    item = Item.query.filter_by(uuid=uuid).first_or_404()

    if not current_user.has_permission('items', 'edit_quantity'):
        return jsonify({'success': False, 'message': 'Permission denied'}), 403

    data = request.get_json()
    sn_ids = data.get('sn_ids', [])
    from_batch_id = data.get('from_batch_id')
    to_batch_id = data.get('to_batch_id')

    from_batch = ItemBatch.query.get(from_batch_id)
    to_batch = ItemBatch.query.get(to_batch_id)

    if not from_batch or not to_batch or from_batch.item_id != item.id or to_batch.item_id != item.id:
        return jsonify({'success': False, 'message': 'Invalid batch'}), 400

    if from_batch_id == to_batch_id:
        return jsonify({'success': False, 'message': 'Cannot transfer to same batch'}), 400

    # Block transfer from Tracking ON to Non-tracking (would lose SN data)
    if from_batch.sn_tracking_enabled and not to_batch.sn_tracking_enabled:
        return jsonify({'success': False, 'message': 'Cannot transfer from a tracked batch to a non-tracked batch. Serial number data would be lost.'}), 400

    # Check if target batch can accept all selected items
    if to_batch.quantity >= 100:
        return jsonify({'success': False, 'message': f'Target batch "{to_batch.get_display_label()}" is full (100/100).'}), 400

    space_available = 100 - to_batch.quantity
    if len(sn_ids) > space_available:
        return jsonify({'success': False, 'message': f'Target batch can only accept {space_available} more item(s). You selected {len(sn_ids)}.'}), 400

    # Collect existing ISNs in target batch to detect collisions
    existing_isns = set(
        s.internal_serial_number for s in BatchSerialNumber.query.filter_by(batch_id=to_batch.id).all()
    )

    # Find the max ISN suffix number in target batch for collision resolution
    import re
    max_suffix = 0
    for s in BatchSerialNumber.query.filter_by(batch_id=to_batch.id).all():
        match = re.search(r'-(\d+)$', s.internal_serial_number)
        if match:
            max_suffix = max(max_suffix, int(match.group(1)))

    transferred = 0
    for sn_id in sn_ids:
        sn = BatchSerialNumber.query.get(sn_id)
        if sn and sn.batch_id == from_batch.id:
            sn.batch_id = to_batch.id
            # Assign next sequence number in target batch
            max_seq = db.session.query(db.func.max(BatchSerialNumber.sequence_number)).filter_by(batch_id=to_batch.id).scalar() or 0
            sn.sequence_number = max_seq + 1

            # Keep original ISN, but if collision, generate new ISN with max+1 suffix
            if sn.internal_serial_number in existing_isns:
                to_date_str = to_batch.purchase_date.strftime('%Y%m%d') if to_batch.purchase_date else '00000000'
                to_label = to_batch.batch_label or f"B{to_batch.batch_number}"
                max_suffix += 1
                sn.internal_serial_number = f"{item.uuid}-{to_date_str}-{to_label}-{max_suffix:03d}"

            existing_isns.add(sn.internal_serial_number)
            # Enable tracking on target if not already
            if not to_batch.sn_tracking_enabled:
                to_batch.sn_tracking_enabled = True
            transferred += 1

    # Update quantities
    from_batch.quantity = max(from_batch.quantity - transferred, 0)
    to_batch.quantity = to_batch.quantity + transferred

    # Re-sequence source batch (row numbers only, keep ISNs as-is)
    remaining = BatchSerialNumber.query.filter_by(batch_id=from_batch.id).order_by(BatchSerialNumber.sequence_number).all()
    for idx, sn in enumerate(remaining, 1):
        sn.sequence_number = idx

    # Re-sequence target batch (row numbers only, keep ISNs as-is)
    target_sns = BatchSerialNumber.query.filter_by(batch_id=to_batch.id).order_by(BatchSerialNumber.sequence_number).all()
    for idx, sn in enumerate(target_sns, 1):
        sn.sequence_number = idx

    item.recalculate_from_batches()
    item.updated_by = current_user.id
    db.session.commit()

    log_audit(current_user.id, 'transfer', 'serial_numbers', None,
              f'Transferred {transferred} SNs from batch #{from_batch.batch_number} to #{to_batch.batch_number} in item: {item.name}')
    return jsonify({'success': True, 'transferred': transferred})


@batch_bp.route('/item/<string:uuid>/batch/sn/add', methods=['POST'])
@login_required
def add_sn_to_batch(uuid):
    """Add new serial numbers to a batch (appends to end)"""
    item = Item.query.filter_by(uuid=uuid).first_or_404()

    # Adding SNs increases quantity; require both SN edit and quantity edit.
    if not (current_user.has_permission('items', 'edit_sn') and
            current_user.has_permission('items', 'edit_quantity')):
        return jsonify({'success': False, 'message': 'Permission denied'}), 403

    data = request.get_json()
    batch_id = data.get('batch_id')
    qty = data.get('quantity', 0)

    batch = ItemBatch.query.get(batch_id)
    if not batch or batch.item_id != item.id:
        return jsonify({'success': False, 'message': 'Invalid batch'}), 400

    if batch.quantity + qty > 100:
        return jsonify({'success': False, 'message': f'Would exceed max 100. Can add up to {100 - batch.quantity}.'}), 400

    # Get current max sequence
    max_seq = db.session.query(db.func.max(BatchSerialNumber.sequence_number)).filter_by(batch_id=batch.id).scalar() or 0

    date_str = batch.purchase_date.strftime('%Y%m%d') if batch.purchase_date else '00000000'
    label = batch.batch_label or f"B{batch.batch_number}"

    for i in range(1, qty + 1):
        seq = max_seq + i
        isn = f"{item.uuid}-{date_str}-{label}-{seq:03d}"
        sn = BatchSerialNumber(
            batch_id=batch.id,
            sequence_number=seq,
            internal_serial_number=isn,
            serial_number='',
            info='',
        )
        db.session.add(sn)

    batch.quantity += qty
    item.recalculate_from_batches()
    item.updated_by = current_user.id
    db.session.commit()

    log_audit(current_user.id, 'create', 'serial_numbers', batch.id,
              f'Added {qty} SNs to batch #{batch.batch_number} of item: {item.name}')
    return jsonify({'success': True, 'added': qty})


@batch_bp.route('/item/<string:uuid>/batch/sn/remap-isn', methods=['POST'])
@login_required
def remap_isn(uuid):
    """Regenerate ISN sequence for a batch while keeping SN, info, lend_to"""
    item = Item.query.filter_by(uuid=uuid).first_or_404()

    if not current_user.has_permission('items', 'edit_sn'):
        return jsonify({'success': False, 'message': 'Permission denied'}), 403

    data = request.get_json()
    batch_id = data.get('batch_id')

    batch = ItemBatch.query.get(batch_id)
    if not batch or batch.item_id != item.id:
        return jsonify({'success': False, 'message': 'Invalid batch'}), 400

    date_str = batch.purchase_date.strftime('%Y%m%d') if batch.purchase_date else '00000000'
    label = batch.batch_label or f"B{batch.batch_number}"

    sns = BatchSerialNumber.query.filter_by(batch_id=batch.id).order_by(BatchSerialNumber.sequence_number).all()
    for idx, sn in enumerate(sns, 1):
        sn.sequence_number = idx
        sn.internal_serial_number = f"{item.uuid}-{date_str}-{label}-{idx:03d}"

    db.session.commit()

    log_audit(current_user.id, 'update', 'serial_numbers', batch.id,
              f'Remapped ISN for batch #{batch.batch_number} of item: {item.name}')
    return jsonify({'success': True, 'remapped': len(sns)})