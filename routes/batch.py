"""
Batch Routes Blueprint - Manages item batches, transfers, and serial numbers
"""
from flask import Blueprint, render_template, redirect, url_for, flash, request, jsonify
from flask_login import login_required, current_user
from models import db, Item, ItemBatch, BatchSerialNumber, BatchLendRecord, Setting
from utils import log_audit
from datetime import datetime, date, timezone
import logging
import json

logger = logging.getLogger(__name__)

batch_bp = Blueprint('batch', __name__)


def _parse_datetime(s):
    """Parse a date or datetime string into a datetime object (or None)."""
    if not s:
        return None
    for fmt in ('%Y-%m-%dT%H:%M:%S', '%Y-%m-%dT%H:%M', '%Y-%m-%d %H:%M:%S', '%Y-%m-%d'):
        try:
            return datetime.strptime(s, fmt)
        except ValueError:
            continue
    return None


def _fmt_dt(dt):
    """Format a datetime for display: date-only when time is midnight."""
    if not dt:
        return '—'
    if dt.hour == 0 and dt.minute == 0:
        return dt.strftime('%d/%m/%Y')
    return dt.strftime('%d/%m/%Y %H:%M')


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
        if not contact_id:
            continue  # lend_to is required — skip records without a contact
        try:
            qty = max(1, min(int(r.get('qty', 1)), max_qty))
        except (ValueError, TypeError):
            qty = 1
        try:
            days = int(r.get('days', 3))
        except (ValueError, TypeError):
            days = 3
        note = (r.get('lend_note', '') or '').strip()[:128] or None
        rec = BatchLendRecord(
            batch_id=batch.id,
            lend_to_type=r.get('type', '').strip(),
            lend_to_id=contact_id,
            quantity=qty,
            lend_start=_parse_datetime(r.get('start', '')),
            lend_end=_parse_datetime(r.get('end', '')),
            lend_notify_enabled=bool(r.get('notify', False)),
            lend_notify_before_days=days,
            lend_note=note,
        )
        db.session.add(rec)


@batch_bp.route('/item/<string:uuid>/batch/add', methods=['POST'])
@login_required
def add_batch(uuid):
    """Add a new batch to an item"""
    item = Item.query.filter_by(uuid=uuid).first_or_404()

    # Adding a batch requires at least the general batch-edit permission.
    if not current_user.has_permission('lending_return', 'edit_batch'):
        flash('You do not have permission to manage batches.', 'danger')
        return redirect(url_for('item.item_detail', uuid=uuid))

    can_edit_qty = current_user.has_permission('lending_return', 'edit_batch')
    can_edit_price = current_user.has_permission('lending_return', 'edit_batch')
    can_edit_sn = current_user.has_permission('lending_return', 'edit_batch')
    can_edit_lending = current_user.has_permission('lending_return', 'edit_lending')

    batch_label = request.form.get('batch_label', '').strip()[:32]
    manufacturer = request.form.get('manufacturer', '').strip()[:128]
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

    # Hard cap: max 32 batches per item
    current_batch_count = ItemBatch.query.filter_by(item_id=item.id).count()
    if current_batch_count >= 32:
        flash('This item has reached the maximum of 32 batches.', 'danger')
        return redirect(url_for('item.item_edit', uuid=uuid) + '#batches-section')

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
        manufacturer=manufacturer or None,
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


@batch_bp.route('/item/<string:uuid>/batch/<int:batch_id>/edit-location', methods=['POST'])
@login_required
def edit_batch_location(uuid, batch_id):
    """Update only the location fields of a batch — requires items.edit_info."""
    item = Item.query.filter_by(uuid=uuid).first_or_404()
    batch = ItemBatch.query.get_or_404(batch_id)
    if batch.item_id != item.id:
        return jsonify({'success': False, 'message': 'Batch does not belong to this item'}), 400
    if not (current_user.is_admin() or current_user.has_permission('items', 'edit_info')):
        return jsonify({'success': False, 'message': 'Permission denied'}), 403

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

    item.updated_by = current_user.id
    item.updated_at = datetime.now(timezone.utc)
    db.session.commit()
    log_audit(current_user.id, 'update', 'batch', batch.id,
              f'Updated location of batch "{batch.get_display_label()}" for {item.name}')
    return jsonify({'success': True})


@batch_bp.route('/item/<string:uuid>/batch/<int:batch_id>/edit', methods=['POST'])
@login_required
def edit_batch(uuid, batch_id):
    """Edit an existing batch"""
    item = Item.query.filter_by(uuid=uuid).first_or_404()
    batch = ItemBatch.query.get_or_404(batch_id)

    if batch.item_id != item.id:
        flash('Batch does not belong to this item.', 'danger')
        return redirect(url_for('item.item_detail', uuid=uuid))

    can_edit_batch = current_user.has_permission('lending_return', 'edit_batch')
    can_edit_qty = current_user.has_permission('lending_return', 'edit_batch')
    can_edit_price = current_user.has_permission('lending_return', 'edit_batch')
    can_edit_sn = current_user.has_permission('lending_return', 'edit_batch')
    can_edit_lending = current_user.has_permission('lending_return', 'edit_lending')

    if not (can_edit_batch or can_edit_qty or can_edit_price or can_edit_lending or can_edit_sn):
        flash('You do not have permission to manage batches.', 'danger')
        return redirect(url_for('item.item_detail', uuid=uuid))

    old_qty = batch.quantity

    # General batch fields (label, date, note, location)
    if can_edit_batch:
        batch.batch_label = (request.form.get('batch_label', '').strip()[:32]) or None
        batch.manufacturer = (request.form.get('manufacturer', '').strip()[:128]) or None
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
    can_edit_lending = current_user.has_permission('lending_return', 'edit_lending')
    if not can_edit_lending:
        return jsonify({'success': False, 'message': 'No permission.'})
    lend_records_json = request.form.get('lend_records', '[]')
    try:
        lend_records_data = json.loads(lend_records_json)
    except (ValueError, TypeError):
        lend_records_data = []
    total_lend_qty = sum(
        max(1, int(r.get('qty', 1))) for r in lend_records_data if isinstance(r, dict)
    )
    if total_lend_qty > batch.quantity:
        return jsonify({
            'success': False,
            'message': f'Total lend quantity ({total_lend_qty}) exceeds batch quantity ({batch.quantity}).'
        })
    old_count = BatchLendRecord.query.filter_by(batch_id=batch.id).count()
    BatchLendRecord.query.filter_by(batch_id=batch.id).delete()
    _save_lend_records(batch, lend_records_data, batch.quantity)
    db.session.commit()
    new_count = len(lend_records_data)
    log_audit(current_user.id, 'lend_update', 'batch', batch.id,
              f'Updated lending for batch #{batch.batch_number} "{batch.get_display_label()}" of item: {item.name} '
              f'(was {old_count} record(s), now {new_count} record(s), total lent: {batch.get_lend_quantity()})')
    return jsonify({'success': True, 'lend_qty': batch.get_lend_quantity()})


@batch_bp.route('/item/<string:uuid>/batch/<int:batch_id>/delete', methods=['POST'])
@login_required
def delete_batch(uuid, batch_id):
    """Delete a batch, logging SN records first for SN-tracked batches."""
    item = Item.query.filter_by(uuid=uuid).first_or_404()
    batch = ItemBatch.query.get_or_404(batch_id)

    if batch.item_id != item.id:
        flash('Batch does not belong to this item.', 'danger')
        return redirect(url_for('item.item_detail', uuid=uuid))

    if not current_user.has_permission('lending_return', 'delete_batch'):
        flash('You do not have permission to delete batches.', 'danger')
        return redirect(url_for('item.item_detail', uuid=uuid))

    batch_label = batch.get_display_label()

    if batch.sn_tracking_enabled and batch.serial_numbers:
        isn_list = ', '.join(sn.internal_serial_number for sn in batch.serial_numbers)
        log_audit(current_user.id, 'batch_sn_purge', 'batch', batch_id,
                  f'Deleted SN-tracked batch "{batch_label}" (B{batch.batch_number:02d}) '
                  f'from item: {item.name} | {len(batch.serial_numbers)} SN records purged: {isn_list}')

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

    if not current_user.has_permission('lending_return', 'delete_batch'):
        return jsonify({'success': False, 'message': 'Permission denied'}), 403

    data = request.get_json()
    batch_ids = data.get('batch_ids', [])
    
    if not batch_ids:
        return jsonify({'success': False, 'message': 'No batches selected'}), 400
    
    deleted = 0
    for bid in batch_ids:
        batch = ItemBatch.query.get(int(bid))
        if batch and batch.item_id == item.id:
            if batch.sn_tracking_enabled and batch.serial_numbers:
                isn_list = ', '.join(sn.internal_serial_number for sn in batch.serial_numbers)
                log_audit(current_user.id, 'batch_sn_purge', 'batch', batch.id,
                          f'Bulk-deleted SN-tracked batch "{batch.get_display_label()}" (B{batch.batch_number:02d}) '
                          f'from item: {item.name} | {len(batch.serial_numbers)} SN records purged: {isn_list}')
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

    # Transferring changes both quantities; require batch edit permission.
    if not current_user.has_permission('lending_return', 'edit_batch'):
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
    
    if not current_user.has_permission('lending_return', 'edit_batch'):
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
    
    if not current_user.has_permission('lending_return', 'edit_batch'):
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
    
    if not current_user.has_permission('lending_return', 'edit_lending'):
        flash('You do not have permission to manage lending.', 'danger')
        return redirect(url_for('item.item_detail', uuid=uuid))
    
    lent_count = 0
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
        sn.lend_start = _parse_datetime(lend_start_str)
        sn.lend_end = _parse_datetime(lend_end_str)
        sn.lend_notify_enabled = request.form.get(f'lend_notify_{sn.id}', '0') == '1'
        try:
            sn.lend_notify_before_days = int(request.form.get(f'lend_notify_days_{sn.id}', 3))
        except (ValueError, TypeError):
            sn.lend_notify_before_days = 3
        if sn.lend_to_id:
            lent_count += 1

    db.session.commit()

    log_audit(current_user.id, 'lend_update', 'batch', batch.id,
              f'Updated SN lending for batch #{batch.batch_number} "{batch.get_display_label()}" of item: {item.name} '
              f'({lent_count} unit(s) on lend)')
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
    if sn.is_deleted:
        return jsonify({'success': False, 'message': 'Cannot edit a removed serial number'}), 400

    if field == 'sn':
        if not current_user.has_permission('lending_return', 'edit_batch'):
            return jsonify({'success': False, 'message': 'Permission denied'}), 403
        sn.serial_number = value
    elif field == 'info':
        if not current_user.has_permission('lending_return', 'edit_batch'):
            return jsonify({'success': False, 'message': 'Permission denied'}), 403
        sn.info = value[:32]
    elif field == 'lend':
        if not current_user.has_permission('lending_return', 'edit_lending'):
            return jsonify({'success': False, 'message': 'Permission denied'}), 403
        lend_to_id_raw = data.get('lend_to_id')
        try:
            lend_to_id = int(lend_to_id_raw) if lend_to_id_raw else None
        except (ValueError, TypeError):
            lend_to_id = None
        if not lend_to_id:
            return jsonify({'success': False, 'message': 'Lend to contact is required.'}), 400
        sn.lend_to_type = data.get('lend_to_type', '').strip()
        sn.lend_to_id = lend_to_id
        sn.lend_start = _parse_datetime(data.get('lend_start', ''))
        sn.lend_end = _parse_datetime(data.get('lend_end', ''))
        sn.lend_notify_enabled = bool(data.get('lend_notify_enabled', False))
        try:
            sn.lend_notify_before_days = int(data.get('lend_notify_before_days', 3))
        except (ValueError, TypeError):
            sn.lend_notify_before_days = 3
        sn.lend_note = (data.get('lend_note', '') or '').strip()[:128] or None
    else:
        return jsonify({'success': False, 'message': 'Invalid field'}), 400

    db.session.commit()
    if field == 'lend':
        lend_display = sn.get_lend_to_display() or 'cleared'
        log_audit(current_user.id, 'lend_update', 'serial_number', sn.id,
                  f'Set lending on SN #{sn.sequence_number} (ISN: {sn.internal_serial_number}) '
                  f'in item: {item.name} → {lend_display}')
    else:
        log_audit(current_user.id, 'update', 'serial_number', sn.id,
                  f'Updated {field} for SN #{sn.sequence_number} in item: {item.name}')
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

    can_edit_sn = current_user.has_permission('lending_return', 'edit_batch')
    can_edit_lending = current_user.has_permission('lending_return', 'edit_lending')

    count = 0
    for sn_id in sn_ids:
        sn = BatchSerialNumber.query.get(sn_id)
        if not sn or sn.batch.item_id != item.id or sn.is_deleted:
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
                sn.lend_start = None
                sn.lend_end = None
                sn.lend_notify_enabled = False
                sn.lend_notify_before_days = 3
                sn.lend_note = None
            elif isinstance(lend_data, dict):
                lend_id_raw = lend_data.get('id')
                try:
                    lend_id = int(lend_id_raw) if lend_id_raw else None
                except (ValueError, TypeError):
                    lend_id = None
                if not lend_id:
                    count += 1
                    continue  # contact required for non-clear lend
                sn.lend_to_type = lend_data.get('type', '').strip()
                sn.lend_to_id = lend_id
                sn.lend_start = _parse_datetime(lend_data.get('start', ''))
                sn.lend_end = _parse_datetime(lend_data.get('end', ''))
                sn.lend_notify_enabled = bool(lend_data.get('notify', False))
                try:
                    sn.lend_notify_before_days = int(lend_data.get('days', 3))
                except (ValueError, TypeError):
                    sn.lend_notify_before_days = 3
                sn.lend_note = (lend_data.get('lend_note', '') or '').strip()[:128] or None
            count += 1

    db.session.commit()
    field_names = ', '.join(fields.keys())
    log_audit(current_user.id, 'lend_update' if 'lend' in fields else 'bulk_update',
              'serial_numbers', None,
              f'Bulk updated field(s) [{field_names}] on {len(sn_ids)} SN(s) in item: {item.name}')
    return jsonify({'success': True, 'updated': count})


@batch_bp.route('/item/<string:uuid>/batch/sn/delete-selected', methods=['POST'])
@login_required
def delete_selected_sn(uuid):
    """Soft-delete selected serial numbers, recording who, why, and when."""
    item = Item.query.filter_by(uuid=uuid).first_or_404()

    if not (current_user.has_permission('lending_return', 'edit_batch') and
            current_user.has_permission('lending_return', 'edit_batch')):
        return jsonify({'success': False, 'message': 'Permission denied'}), 403

    data = request.get_json()
    sn_ids = data.get('sn_ids', [])
    batch_id = data.get('batch_id')
    reason = (data.get('reason', '') or '').strip()[:256] or None

    batch = ItemBatch.query.get(batch_id)
    if not batch or batch.item_id != item.id:
        return jsonify({'success': False, 'message': 'Invalid batch'}), 400

    now = datetime.utcnow()
    deleted = 0
    for sn_id in sn_ids:
        sn = BatchSerialNumber.query.get(sn_id)
        if sn and sn.batch_id == batch.id and not sn.is_deleted:
            sn.is_deleted = True
            sn.deleted_by_id = current_user.id
            sn.deleted_at = now
            sn.deleted_reason = reason
            deleted += 1

    batch.quantity = max(batch.quantity - deleted, 0)
    item.recalculate_from_batches()
    item.updated_by = current_user.id
    db.session.commit()

    log_audit(current_user.id, 'delete', 'serial_numbers', batch.id,
              f'Soft-deleted {deleted} SNs from batch #{batch.batch_number} of item: {item.name}')
    return jsonify({'success': True, 'deleted': deleted})


@batch_bp.route('/item/<string:uuid>/batch/sn/add', methods=['POST'])
@login_required
def add_sn_to_batch(uuid):
    """Add new serial numbers to a batch (appends to end)"""
    item = Item.query.filter_by(uuid=uuid).first_or_404()

    # Adding SNs increases quantity; require both SN edit and quantity edit.
    if not (current_user.has_permission('lending_return', 'edit_batch') and
            current_user.has_permission('lending_return', 'edit_batch')):
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
    batch_id_str = f"B{batch.batch_number:02d}"

    for i in range(1, qty + 1):
        seq = max_seq + i
        isn = f"{item.uuid}-{date_str}-{batch_id_str}-{seq:03d}"
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


@batch_bp.route('/item/<string:uuid>/batch/<int:batch_id>/sn/save-pending', methods=['POST'])
@login_required
def save_sn_pending(uuid, batch_id):
    """Apply all pending SN changes (adds, soft-deletes, field edits, lend changes) atomically."""
    item = Item.query.filter_by(uuid=uuid).first_or_404()

    if not current_user.has_permission('lending_return', 'edit_batch'):
        return jsonify({'success': False, 'message': 'Permission denied'}), 403

    batch = ItemBatch.query.get(batch_id)
    if not batch or batch.item_id != item.id or not batch.sn_tracking_enabled:
        return jsonify({'success': False, 'message': 'Invalid batch'}), 400

    data = request.get_json()
    adds    = int(data.get('adds', 0))
    deletes = data.get('deletes', [])   # [{sn_id, reason}]
    edits   = data.get('edits', [])     # [{sn_id, sn, info}]  — only non-null fields applied
    lend_changes = data.get('lend_changes', [])  # [{sn_id, lend_to_type, lend_to_id, lend_start, lend_end, lend_note, lend_notify, lend_days}]

    can_qty  = current_user.has_permission('lending_return', 'edit_batch')
    can_lend = current_user.has_permission('lending_return', 'edit_lending')
    now = datetime.utcnow()

    # ── Adds ──
    added = 0
    if adds > 0 and can_qty:
        active_count = sum(1 for sn in batch.serial_numbers if not sn.is_deleted)
        if active_count + adds > 100:
            return jsonify({'success': False, 'message': f'Would exceed max 100. Can add up to {100 - active_count}.'}), 400
        max_seq = db.session.query(db.func.max(BatchSerialNumber.sequence_number)).filter_by(batch_id=batch.id).scalar() or 0
        date_str = batch.purchase_date.strftime('%Y%m%d') if batch.purchase_date else '00000000'
        batch_id_str = f"B{batch.batch_number:02d}"
        for i in range(1, adds + 1):
            seq = max_seq + i
            isn = f"{item.uuid}-{date_str}-{batch_id_str}-{seq:03d}"
            sn = BatchSerialNumber(batch_id=batch.id, sequence_number=seq,
                                   internal_serial_number=isn, serial_number='', info='')
            db.session.add(sn)
        batch.quantity += adds
        added = adds

    # ── Soft-deletes ──
    deleted = 0
    if deletes and can_qty:
        for d in deletes:
            sn_id = d.get('sn_id')
            reason = (d.get('reason', '') or '').strip()[:256] or None
            sn = BatchSerialNumber.query.get(sn_id)
            if sn and sn.batch_id == batch.id and not sn.is_deleted:
                sn.is_deleted = True
                sn.deleted_by_id = current_user.id
                sn.deleted_at = now
                sn.deleted_reason = reason
                deleted += 1
        batch.quantity = max(batch.quantity - deleted, 0)

    # ── Field edits ──
    edited = 0
    for e in edits:
        sn_id = e.get('sn_id')
        sn = BatchSerialNumber.query.get(sn_id)
        if not sn or sn.batch_id != batch.id or sn.is_deleted:
            continue
        if e.get('sn') is not None:
            sn.serial_number = str(e['sn']).strip()[:200]
        if e.get('info') is not None:
            sn.info = str(e['info']).strip()[:32]
        edited += 1

    # ── Lending changes ──
    lent = 0
    if can_lend:
        for lc in lend_changes:
            sn_id = lc.get('sn_id')
            sn = BatchSerialNumber.query.get(sn_id)
            if not sn or sn.batch_id != batch.id or sn.is_deleted:
                continue
            lend_id_raw = lc.get('lend_to_id')
            try:
                lend_id = int(lend_id_raw) if lend_id_raw else None
            except (ValueError, TypeError):
                lend_id = None
            if lend_id:
                sn.lend_to_type = lc.get('lend_to_type', '')
                sn.lend_to_id = lend_id
                sn.lend_start = _parse_datetime(lc.get('lend_start', ''))
                sn.lend_end = _parse_datetime(lc.get('lend_end', ''))
                sn.lend_note = (lc.get('lend_note', '') or '').strip()[:128] or None
                sn.lend_notify_enabled = bool(lc.get('lend_notify', False))
                try:
                    sn.lend_notify_before_days = int(lc.get('lend_days', 3))
                except (ValueError, TypeError):
                    sn.lend_notify_before_days = 3
            else:
                # Clear lend
                sn.lend_to_type = ''
                sn.lend_to_id = None
                sn.lend_start = None
                sn.lend_end = None
                sn.lend_note = None
                sn.lend_notify_enabled = False
                sn.lend_notify_before_days = 3
            lent += 1

    item.recalculate_from_batches()
    item.updated_by = current_user.id
    db.session.commit()

    log_audit(current_user.id, 'sn_batch_save', 'batch', batch.id,
              f'Saved pending SN changes for batch #{batch.batch_number} of item: {item.name} '
              f'(+{added} adds, -{deleted} removes, {edited} edits, {lent} lend changes)')
    return jsonify({'success': True, 'added': added, 'deleted': deleted, 'edited': edited, 'lent': lent})
