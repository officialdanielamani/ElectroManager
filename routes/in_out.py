from flask import Blueprint, render_template, request, jsonify, abort, redirect, url_for, flash
from flask_login import login_required, current_user
from models import (db, AuditLog, User, Item, ItemBatch, BatchSerialNumber,
                    BatchLendRecord, LendingSession, _generate_lending_id, Setting)
from utils import log_audit, get_item_edit_permissions
from datetime import datetime, timezone
import json
import re

in_out_bp = Blueprint('in_out', __name__)

LOG_PAGE_SIZE = 25

_LENDING_ID_RE = re.compile(r'^\d{8}-[A-Z0-9]{6}$')


def _parse_dt(s):
    if not s:
        return None
    for fmt in ('%Y-%m-%dT%H:%M:%S', '%Y-%m-%dT%H:%M', '%Y-%m-%d %H:%M:%S', '%Y-%m-%d'):
        try:
            return datetime.strptime(s, fmt)
        except ValueError:
            continue
    return None


def _format_log_details(action, details):
    if not details:
        return ''
    if action == 'return':
        try:
            d = json.loads(details)
            parts = []
            cnt = d.get('count') or d.get('qty')
            if cnt is not None:
                parts.append(f'{cnt} unit(s)')
            on_time = d.get('on_time')
            if on_time is True:
                parts.append('on time')
            elif on_time is False:
                parts.append('LATE')
            ret_dt = d.get('return_dt', '')
            if ret_dt:
                parts.append(f'@ {ret_dt}')
            notes = d.get('notes', '')
            if notes:
                parts.append(f'— {notes}')
            return ' | '.join(parts) if parts else details[:120]
        except (ValueError, TypeError):
            pass
    return details[:120] + ('…' if len(details) > 120 else '')


def _build_log_entries(page=1, can_view_log=True):
    if not can_view_log:
        return [], 0
    actions = ['lend', 'return', 'update', 'delete', 'batch_sn_purge', 'lend_update', 'sn_batch_save']
    q = (AuditLog.query
         .filter(AuditLog.entity_type.in_(['batch', 'item', 'sn', 'lending_session']))
         .filter(AuditLog.action.in_(actions))
         .order_by(AuditLog.timestamp.desc()))
    total = q.count()
    total_pages = max(1, (total + LOG_PAGE_SIZE - 1) // LOG_PAGE_SIZE)
    page = max(1, min(page, total_pages))
    raw = q.offset((page - 1) * LOG_PAGE_SIZE).limit(LOG_PAGE_SIZE).all()
    entries = []
    for log in raw:
        user = User.query.get(log.user_id)
        entries.append({
            'log': log,
            'username': user.username if user else 'Unknown',
            'timestamp': log.timestamp.strftime('%d/%m/%Y %H:%M') if log.timestamp else '?',
            'display': _format_log_details(log.action, log.details),
        })
    return entries, total_pages


@in_out_bp.route('/in-out')
@login_required
def in_out():
    if not current_user.has_permission('lending_return', 'view_page') and not current_user.is_admin():
        abort(403)

    can_view_log    = current_user.is_admin() or current_user.has_permission('lending_return', 'view_log')
    can_lend        = current_user.is_admin() or current_user.has_permission('lending_return', 'edit_lending') or current_user.has_permission('lending_return', 'only_self_lending')
    can_edit_batch  = current_user.is_admin() or current_user.has_permission('lending_return', 'edit_batch')
    can_delete_batch= current_user.is_admin() or current_user.has_permission('lending_return', 'delete_batch')
    can_only_self   = (not current_user.is_admin()
                       and current_user.has_permission('lending_return', 'only_self_lending')
                       and not current_user.has_permission('lending_return', 'edit_batch'))
    scan_enabled    = Setting.get('lr_scan_enabled', False) is True

    log_page = request.args.get('log_page', 1, type=int)
    logs, log_total_pages = _build_log_entries(log_page, can_view_log)

    lr_settings = {
        'lend_start_date_required': Setting.get('lr_lend_start_date_required', False) is True,
        'lend_start_time_required': Setting.get('lr_lend_start_time_required', False) is True,
        'lend_end_date_required': Setting.get('lr_lend_end_date_required', False) is True,
        'lend_end_time_required': Setting.get('lr_lend_end_time_required', False) is True,
        'return_date_required': Setting.get('lr_return_date_required', False) is True,
        'return_time_required': Setting.get('lr_return_time_required', False) is True,
    }

    return render_template('in_out.html',
                           logs=logs, can_view_log=can_view_log,
                           log_page=log_page, log_total_pages=log_total_pages,
                           can_lend=can_lend, can_edit_batch=can_edit_batch,
                           can_delete_batch=can_delete_batch, can_only_self=can_only_self,
                           scan_enabled=scan_enabled,
                           lr_settings=lr_settings,
                           current_user_id=current_user.id,
                           currency=Setting.get('currency', '$'))


@in_out_bp.route('/in-out/search')
@login_required
def in_out_search():
    """AJAX: search by item name, UUID, ISN, batch ID, or lending session ID."""
    q = request.args.get('q', '').strip()
    if len(q) < 2:
        return jsonify({'results': [], 'type': 'none'})

    # Check for lending session ID: YYYYMMDD-XXXXXX
    if _LENDING_ID_RE.match(q.upper()):
        session = LendingSession.query.filter_by(lending_id=q.upper()).first()
        if session:
            return jsonify({'type': 'session', 'results': [_session_json(session)]})

    # Try ISN exact match
    sn_row = BatchSerialNumber.query.filter_by(internal_serial_number=q).first()
    if sn_row:
        batch = sn_row.batch
        item  = batch.item
        return jsonify({'type': 'sn', 'results': [_batch_json(batch, item, sn_row)]})

    # Try batch ID format {uuid}-B{n}
    if '-B' in q:
        parts = q.rsplit('-B', 1)
        if len(parts) == 2:
            uuid_part, num_part = parts
            try:
                num = int(num_part)
                item = Item.query.filter_by(uuid=uuid_part).first()
                if item:
                    batch = ItemBatch.query.filter_by(item_id=item.id, batch_number=num).first()
                    if batch:
                        return jsonify({'type': 'batch', 'results': [_batch_json(batch, item)]})
            except ValueError:
                pass

    # Try UUID exact match
    item_by_uuid = Item.query.filter_by(uuid=q).first()
    if item_by_uuid:
        return jsonify({'type': 'item_batches', 'results': [_item_json(item_by_uuid)]})

    # Full-text search by name / SKU / short_info
    items = (Item.query.filter(
        db.or_(
            Item.name.ilike(f'%{q}%'),
            Item.sku.ilike(f'%{q}%'),
            Item.short_info.ilike(f'%{q}%'),
        )
    ).order_by(Item.name).limit(20).all())

    return jsonify({'type': 'items', 'results': [_item_json(i) for i in items]})


def _item_json(item):
    return {
        'id': item.id,
        'name': item.name,
        'uuid': item.uuid,
        'short_info': item.short_info or '',
        'batches': [_batch_summary(b) for b in item.batches],
    }

def _batch_summary(batch):
    return {
        'id': batch.id,
        'display_label': batch.get_display_label(),
        'quantity': batch.quantity,
        'sn_tracking': batch.sn_tracking_enabled,
        'lend_qty': batch.get_lend_quantity(),
        'available_qty': batch.get_available_quantity(),
        'item_uuid': batch.item.uuid,
    }

def _batch_json(batch, item, sn_row=None):
    base = _batch_summary(batch)
    base.update({
        'item_name': item.name,
        'item_uuid': item.uuid,
        'item_short_info': item.short_info or '',
        'batch_label': batch.batch_label or '',
        'manufacturer': batch.manufacturer or '',
        'price_per_unit': float(batch.price_per_unit or 0),
        'purchase_date': batch.purchase_date.strftime('%Y-%m-%d') if batch.purchase_date else '',
        'note': batch.note or '',
        'location_id': batch.location_id,
        'rack_id': batch.rack_id,
        'drawer': batch.drawer or '',
        'follow_main_location': batch.follow_main_location if batch.follow_main_location is not None else True,
        'lend_records': batch.get_lend_records_data() if not batch.sn_tracking_enabled else [],
        'serial_numbers': batch.get_serial_numbers_data() if batch.sn_tracking_enabled else [],
        'preselected_sn_id': sn_row.id if sn_row else None,
    })
    return base

def _session_json(session):
    """Serialise a LendingSession for JS consumption."""
    items = []
    for rec in session.lend_records:
        try:
            batch = rec.batch
            item = batch.item
            items.append({
                'type': 'lend_record',
                'batch_id': batch.id,
                'lend_record_id': rec.id,
                'item_name': item.name,
                'item_uuid': item.uuid,
                'item_short_info': item.short_info or '',
                'batch_label': batch.get_display_label(),
                'qty': rec.quantity,
                'lend_note': rec.lend_note or '',
                'returnable': rec.returned_at is None,
            })
        except Exception:
            pass
    for sn in session.serial_number_records:
        try:
            if sn.is_deleted:
                continue
            batch = sn.batch
            item = batch.item
            items.append({
                'type': 'sn',
                'batch_id': batch.id,
                'sn_id': sn.id,
                'item_name': item.name,
                'item_uuid': item.uuid,
                'item_short_info': item.short_info or '',
                'batch_label': batch.get_display_label(),
                'isn': sn.internal_serial_number,
                'lend_note': sn.lend_note or '',
                'returnable': bool(sn.lend_to_id),
            })
        except Exception:
            pass
    return {
        'lending_id': session.lending_id,
        'mode': session.mode,
        'lend_to_label': session.get_lend_to_display(),
        'lend_to_id': session.lend_to_id,
        'lend_to_type': session.lend_to_type or '',
        'lend_start': session.lend_start.strftime('%Y-%m-%dT%H:%M') if session.lend_start else '',
        'lend_end': session.lend_end.strftime('%Y-%m-%dT%H:%M') if session.lend_end else '',
        'notes': session.notes or '',
        'created_at': session.created_at.strftime('%d/%m/%Y %H:%M') if session.created_at else '',
        'items': items,
    }


@in_out_bp.route('/in-out/batch/<int:batch_id>/detail')
@login_required
def in_out_batch_detail(batch_id):
    batch = ItemBatch.query.get_or_404(batch_id)
    item  = batch.item
    return jsonify(_batch_json(batch, item))


@in_out_bp.route('/in-out/session/<lending_id>')
@login_required
def in_out_session_detail(lending_id):
    """AJAX: get full details for a lending session by its lending_id."""
    session = LendingSession.query.filter_by(lending_id=lending_id.upper()).first_or_404()
    return jsonify(_session_json(session))


@in_out_bp.route('/in-out/sessions')
@login_required
def in_out_sessions_list():
    """AJAX: list lending sessions with date / contact filters."""
    can_lend = (current_user.is_admin()
                or current_user.has_permission('lending_return', 'edit_lending')
                or current_user.has_permission('lending_return', 'only_self_lending'))
    if not can_lend:
        return jsonify({'sessions': []})

    can_only_self = (not current_user.is_admin()
                     and current_user.has_permission('lending_return', 'only_self_lending')
                     and not current_user.has_permission('lending_return', 'edit_batch'))

    start_str  = request.args.get('start_date', '').strip()
    end_str    = request.args.get('end_date',   '').strip()
    contact_id = request.args.get('contact_id', '').strip()
    contact_type = request.args.get('contact_type', '').strip()

    q = LendingSession.query.filter_by(mode='lend').order_by(LendingSession.created_at.desc())

    if can_only_self:
        q = q.filter_by(created_by_id=current_user.id)

    if start_str:
        try:
            q = q.filter(LendingSession.lend_start >= datetime.strptime(start_str, '%Y-%m-%d'))
        except ValueError:
            pass

    if end_str:
        try:
            from datetime import timedelta
            end_dt = datetime.strptime(end_str, '%Y-%m-%d') + timedelta(days=1)
            q = q.filter(db.or_(LendingSession.lend_end == None,
                                 LendingSession.lend_end <= end_dt))
        except ValueError:
            pass

    if contact_id and contact_type:
        try:
            q = q.filter_by(lend_to_id=int(contact_id), lend_to_type=contact_type)
        except ValueError:
            pass

    sessions = q.limit(80).all()

    def _list_json(s):
        item_count = (len(s.lend_records) +
                      sum(1 for sn in s.serial_number_records if not sn.is_deleted))
        return {
            'lending_id':   s.lending_id,
            'lend_to_label': s.get_lend_to_display(),
            'lend_to_id':   s.lend_to_id,
            'lend_to_type': s.lend_to_type or '',
            'lend_start':   s.lend_start.strftime('%d/%m/%y') if s.lend_start else '',
            'lend_end':     s.lend_end.strftime('%d/%m/%y')   if s.lend_end   else '',
            'notes':        s.notes or '',
            'item_count':   item_count,
        }

    return jsonify({'sessions': [_list_json(s) for s in sessions]})


@in_out_bp.route('/in-out/submit-cart', methods=['POST'])
@login_required
def in_out_submit_cart():
    """Process a multi-item cart submission (lend or return)."""
    can_lend = (current_user.is_admin()
                or current_user.has_permission('lending_return', 'edit_lending')
                or current_user.has_permission('lending_return', 'only_self_lending'))
    if not can_lend:
        return jsonify({'success': False, 'message': 'Permission denied'}), 403

    data   = request.get_json()
    mode   = data.get('mode', 'lend')
    cart   = data.get('cart', [])
    detail = data.get('detail', {})
    now    = datetime.now(timezone.utc)

    can_only_self = (not current_user.is_admin()
                     and current_user.has_permission('lending_return', 'only_self_lending')
                     and not current_user.has_permission('lending_return', 'edit_batch'))

    global_notes = (detail.get('notes', '') or '').strip()[:256]

    if not cart:
        return jsonify({'success': False, 'message': 'Cart is empty'}), 400

    if mode == 'lend':
        lend_to_type = detail.get('lend_to_type', '')
        try:
            lend_to_id = int(detail.get('lend_to_id')) if detail.get('lend_to_id') else None
        except (ValueError, TypeError):
            lend_to_id = None

        if can_only_self:
            lend_to_id   = current_user.id
            lend_to_type = 'user'
        elif not lend_to_id:
            return jsonify({'success': False, 'message': 'A contact is required for lending'}), 400

        lend_start = _parse_dt(detail.get('lend_start', ''))
        lend_end   = _parse_dt(detail.get('lend_end', ''))

        session_obj = LendingSession(
            lending_id=_generate_lending_id(),
            mode='lend',
            created_by_id=current_user.id,
            lend_to_type=lend_to_type,
            lend_to_id=lend_to_id,
            lend_start=lend_start,
            lend_end=lend_end,
            notes=global_notes or None,
        )
        db.session.add(session_obj)
        db.session.flush()

        errors = []
        processed = 0

        for cart_item in cart:
            item_type = cart_item.get('type')
            batch_id  = cart_item.get('batch_id')
            item_note = (cart_item.get('note', '') or '').strip()[:128] or (global_notes[:128] if global_notes else None)

            batch = ItemBatch.query.get(batch_id)
            if not batch:
                errors.append(f'Batch {batch_id} not found')
                continue

            if item_type == 'sn':
                sn_id = cart_item.get('sn_id')
                sn = BatchSerialNumber.query.get(sn_id)
                if not sn or sn.batch_id != batch.id or sn.is_deleted or sn.lend_to_id:
                    errors.append(f'Serial number {sn_id} not available for lending')
                    continue
                sn.lend_to_type           = lend_to_type
                sn.lend_to_id             = lend_to_id
                sn.lend_start             = lend_start
                sn.lend_end               = lend_end
                sn.lend_note              = item_note
                sn.lend_notify_enabled    = False
                sn.lending_session_id     = session_obj.id
                batch.item.updated_by     = current_user.id
                batch.item.updated_at     = now
                processed += 1

            elif item_type == 'normal':
                qty          = max(1, int(cart_item.get('qty', 1)))
                current_lent = batch.get_lend_quantity()
                if current_lent + qty > batch.quantity:
                    errors.append(f'Qty {qty} exceeds available for "{batch.get_display_label()}" (avail: {batch.get_available_quantity()})')
                    continue
                rec = BatchLendRecord(
                    batch_id           = batch.id,
                    lend_to_type       = lend_to_type,
                    lend_to_id         = lend_to_id,
                    quantity           = qty,
                    lend_start         = lend_start,
                    lend_end           = lend_end,
                    lend_note          = item_note,
                    lending_session_id = session_obj.id,
                )
                db.session.add(rec)
                batch.item.updated_by = current_user.id
                batch.item.updated_at = now
                processed += 1

        db.session.commit()
        log_audit(current_user.id, 'lend', 'lending_session', session_obj.id,
                  f'Lending session {session_obj.lending_id}: {processed} item(s) lent' +
                  (f' | Errors: {"; ".join(errors)}' if errors else ''))
        return jsonify({
            'success': True,
            'lending_id': session_obj.lending_id,
            'processed': processed,
            'errors': errors,
        })

    elif mode == 'return':
        return_dt    = _parse_dt(detail.get('return_datetime', '')) or now
        return_notes = (detail.get('return_notes', '') or '').strip()[:128]

        session_obj = LendingSession(
            lending_id    = _generate_lending_id(),
            mode          = 'return',
            created_by_id = current_user.id,
            notes         = return_notes or global_notes or None,
        )
        db.session.add(session_obj)
        db.session.flush()

        errors      = []
        processed   = 0
        any_late    = False

        for cart_item in cart:
            item_type = cart_item.get('type')
            batch_id  = cart_item.get('batch_id')
            item_note = (cart_item.get('note', '') or '').strip()[:128] or (return_notes[:128] if return_notes else None)

            batch = ItemBatch.query.get(batch_id)
            if not batch:
                errors.append(f'Batch {batch_id} not found')
                continue

            if item_type == 'sn':
                sn_id = cart_item.get('sn_id')
                sn = BatchSerialNumber.query.get(sn_id)
                if not sn or sn.batch_id != batch.id or sn.is_deleted or not sn.lend_to_id:
                    errors.append(f'SN {sn_id} is not currently lent out')
                    continue
                lend_end = sn.lend_end
                on_time  = (lend_end is None) or (return_dt.replace(tzinfo=None) <= lend_end)
                if not on_time:
                    any_late = True
                sn.lend_to_type        = ''
                sn.lend_to_id          = None
                sn.lend_start          = None
                sn.lend_end            = None
                sn.lend_note           = item_note
                sn.lend_notify_enabled = False
                batch.item.updated_by  = current_user.id
                batch.item.updated_at  = now
                processed += 1

            elif item_type == 'lend_record':
                lend_record_id = cart_item.get('lend_record_id')
                rec = BatchLendRecord.query.get(lend_record_id)
                if not rec or rec.batch_id != batch.id or rec.returned_at is not None:
                    errors.append(f'Lend record {lend_record_id} not found or already returned')
                    continue
                return_qty = max(1, int(cart_item.get('qty') or rec.quantity))
                return_qty = min(return_qty, rec.quantity)
                lend_end = rec.lend_end
                on_time  = (lend_end is None) or (return_dt.replace(tzinfo=None) <= lend_end)
                if not on_time:
                    any_late = True
                if return_qty >= rec.quantity:
                    rec.returned_at = return_dt.replace(tzinfo=None)
                else:
                    rec.quantity -= return_qty
                batch.item.updated_by = current_user.id
                batch.item.updated_at = now
                processed += 1

        db.session.commit()
        log_audit(current_user.id, 'return', 'lending_session', session_obj.id,
                  json.dumps({
                      'count': processed, 'on_time': not any_late,
                      'return_dt': return_dt.strftime('%Y-%m-%d %H:%M'),
                      'notes': return_notes or global_notes,
                  }))
        return jsonify({
            'success': True,
            'lending_id': session_obj.lending_id,
            'processed': processed,
            'errors': errors,
            'on_time': not any_late,
        })

    return jsonify({'success': False, 'message': 'Invalid mode'}), 400


# ── Legacy single-batch endpoints (kept for backward compatibility) ──────────

@in_out_bp.route('/in-out/lend', methods=['POST'])
@login_required
def in_out_lend():
    can_lend = (current_user.is_admin()
                or current_user.has_permission('lending_return', 'edit_lending')
                or current_user.has_permission('lending_return', 'only_self_lending'))
    if not can_lend:
        return jsonify({'success': False, 'message': 'Permission denied'}), 403

    data       = request.get_json()
    batch_id   = data.get('batch_id')
    batch      = ItemBatch.query.get_or_404(batch_id)
    item       = batch.item
    now        = datetime.now(timezone.utc)

    can_only_self = (not current_user.is_admin()
                     and current_user.has_permission('lending_return', 'only_self_lending')
                     and not current_user.has_permission('lending_return', 'edit_batch'))

    if batch.sn_tracking_enabled:
        sn_ids    = data.get('sn_ids', [])
        lend_type = data.get('lend_to_type', '')
        try:
            lend_id = int(data.get('lend_to_id')) if data.get('lend_to_id') else None
        except (ValueError, TypeError):
            lend_id = None
        if can_only_self and lend_id != current_user.id:
            return jsonify({'success': False, 'message': 'Only self-lending is allowed for your role'}), 403
        lend_start = _parse_dt(data.get('lend_start', ''))
        lend_end   = _parse_dt(data.get('lend_end', ''))
        lend_note  = (data.get('lend_note', '') or '').strip()[:128] or None
        notify     = bool(data.get('lend_notify', False))
        try:
            days = int(data.get('lend_days', 3))
        except (ValueError, TypeError):
            days = 3
        updated = 0
        for sid in sn_ids:
            sn = BatchSerialNumber.query.get(int(sid))
            if not sn or sn.batch_id != batch.id or sn.is_deleted:
                continue
            sn.lend_to_type = lend_type
            sn.lend_to_id   = lend_id
            sn.lend_start   = lend_start
            sn.lend_end     = lend_end
            sn.lend_note    = lend_note
            sn.lend_notify_enabled     = notify
            sn.lend_notify_before_days = days
            updated += 1
        item.updated_by = current_user.id
        item.updated_at = now
        db.session.commit()
        log_audit(current_user.id, 'lend', 'batch', batch.id,
                  f'Lent {updated} SN(s) from {batch.get_display_label()} of {item.name}')
        return jsonify({'success': True, 'updated': updated})
    else:
        records = data.get('lend_records', [])
        current_lent = batch.get_lend_quantity()
        new_request_qty = sum(max(1, int(r.get('qty', 1))) for r in records if isinstance(r, dict))
        if (current_lent + new_request_qty) > batch.quantity:
            return jsonify({
                'success': False,
                'message': f'Total lend qty ({current_lent + new_request_qty}) exceeds batch qty ({batch.quantity})'
            }), 400
        if can_only_self:
            for r in records:
                try:
                    cid = int(r.get('contact_id', 0))
                except (ValueError, TypeError):
                    cid = 0
                if cid != current_user.id:
                    return jsonify({'success': False, 'message': 'Only self-lending allowed'}), 403

        from routes.batch import _save_lend_records
        _save_lend_records(batch, records, batch.quantity)
        item.updated_by = current_user.id
        item.updated_at = now
        db.session.commit()
        log_audit(current_user.id, 'lend', 'batch', batch.id,
                  f'Added lending for {batch.get_display_label()} of {item.name} ({len(records)} new record(s))')
        return jsonify({'success': True})


@in_out_bp.route('/in-out/return', methods=['POST'])
@login_required
def in_out_return():
    can_lend = (current_user.is_admin()
                or current_user.has_permission('lending_return', 'edit_lending')
                or current_user.has_permission('lending_return', 'only_self_lending'))
    if not can_lend:
        return jsonify({'success': False, 'message': 'Permission denied'}), 403

    data       = request.get_json()
    batch_id   = data.get('batch_id')
    batch      = ItemBatch.query.get_or_404(batch_id)
    item       = batch.item
    now        = datetime.now(timezone.utc)
    return_dt  = _parse_dt(data.get('return_datetime', '')) or now
    return_notes = (data.get('return_notes', '') or '').strip()[:128]

    if batch.sn_tracking_enabled:
        sn_ids = data.get('sn_ids', [])
        returned = []
        for sid in sn_ids:
            sn = BatchSerialNumber.query.get(int(sid))
            if not sn or sn.batch_id != batch.id or sn.is_deleted or not sn.lend_to_id:
                continue
            lend_end = sn.lend_end
            on_time  = (lend_end is None) or (return_dt.replace(tzinfo=None) <= lend_end)
            returned.append({'isn': sn.internal_serial_number, 'on_time': on_time,
                             'lend_end': lend_end.strftime('%Y-%m-%d %H:%M') if lend_end else None})
            sn.lend_to_type = ''
            sn.lend_to_id   = None
            sn.lend_start   = None
            sn.lend_end     = None
            sn.lend_note    = return_notes or None
            sn.lend_notify_enabled = False
        all_on_time = all(r['on_time'] for r in returned)
        item.updated_by = current_user.id
        item.updated_at = now
        db.session.commit()
        log_audit(current_user.id, 'return', 'batch', batch.id,
                  json.dumps({'count': len(returned), 'on_time': all_on_time,
                              'return_dt': return_dt.strftime('%Y-%m-%d %H:%M'),
                              'notes': return_notes, 'items': returned}))
        return jsonify({'success': True, 'returned': len(returned), 'on_time': all_on_time})
    else:
        lend_record_ids = data.get('lend_record_ids', [])
        return_qty  = int(data.get('return_qty', 0))
        returned_count = 0
        any_late = False
        for rid in lend_record_ids:
            rec = BatchLendRecord.query.get(int(rid))
            if not rec or rec.batch_id != batch.id:
                continue
            lend_end = rec.lend_end
            on_time  = (lend_end is None) or (return_dt.replace(tzinfo=None) <= lend_end)
            if not on_time:
                any_late = True
            rqty = min(return_qty if return_qty > 0 else rec.quantity, rec.quantity)
            if rqty >= rec.quantity:
                rec.returned_at = return_dt.replace(tzinfo=None)
            else:
                rec.quantity -= rqty
            returned_count += rqty
        item.updated_by = current_user.id
        item.updated_at = now
        db.session.commit()
        log_audit(current_user.id, 'return', 'batch', batch.id,
                  json.dumps({'qty': returned_count, 'on_time': not any_late,
                              'return_dt': return_dt.strftime('%Y-%m-%d %H:%M'),
                              'notes': return_notes}))
        return jsonify({'success': True, 'returned': returned_count, 'on_time': not any_late})


@in_out_bp.route('/in-out/batch/<int:batch_id>/edit', methods=['POST'])
@login_required
def in_out_edit_batch(batch_id):
    if not (current_user.is_admin() or current_user.has_permission('lending_return', 'edit_batch')):
        return jsonify({'success': False, 'message': 'Permission denied'}), 403
    batch = ItemBatch.query.get_or_404(batch_id)
    item  = batch.item
    data  = request.get_json()
    orig_qty = batch.quantity

    batch.batch_label   = (data.get('batch_label', '') or '').strip()[:50] or None
    batch.manufacturer  = (data.get('manufacturer', '') or '').strip()[:100] or None
    try:
        new_qty = int(data.get('quantity', batch.quantity))
        if new_qty >= 0 and not batch.sn_tracking_enabled:
            batch.quantity = new_qty
    except (ValueError, TypeError):
        pass
    try:
        batch.price_per_unit = float(data.get('price_per_unit', batch.price_per_unit or 0))
    except (ValueError, TypeError):
        pass
    pd_str = data.get('purchase_date', '')
    if pd_str:
        try:
            batch.purchase_date = datetime.strptime(pd_str, '%Y-%m-%d').date()
        except ValueError:
            pass
    batch.note = (data.get('note', '') or '').strip()[:256] or None
    item.recalculate_from_batches()
    item.updated_by = current_user.id
    item.updated_at = datetime.now(timezone.utc)
    db.session.commit()
    log_audit(current_user.id, 'update', 'batch', batch.id,
              f'Edited batch {batch.get_display_label()} of {item.name} via /in-out '
              f'(qty: {orig_qty}→{batch.quantity})')
    return jsonify({'success': True})


@in_out_bp.route('/in-out/batch/<int:batch_id>/purge-deleted-sn', methods=['POST'])
@login_required
def in_out_purge_deleted_sn(batch_id):
    if not (current_user.is_admin() or current_user.has_permission('lending_return', 'delete_batch')):
        return jsonify({'success': False, 'message': 'Permission denied'}), 403
    batch = ItemBatch.query.get_or_404(batch_id)
    item  = batch.item
    deleted_sns = BatchSerialNumber.query.filter_by(batch_id=batch_id, is_deleted=True).all()
    if not deleted_sns:
        return jsonify({'success': True, 'freed': 0, 'message': 'No deleted serial numbers to purge.'})
    freed = len(deleted_sns)
    isn_list = ', '.join(sn.internal_serial_number for sn in deleted_sns)
    for sn in deleted_sns:
        db.session.delete(sn)
    item.recalculate_from_batches()
    item.updated_by = current_user.id
    item.updated_at = datetime.now(timezone.utc)
    db.session.commit()
    log_audit(current_user.id, 'batch_sn_purge', 'batch', batch_id,
              f'Purged {freed} deleted SN(s) from batch "{batch.get_display_label()}" of {item.name} | ISNs: {isn_list}')
    return jsonify({'success': True, 'freed': freed,
                    'message': f'Freed {freed} deleted serial number(s).'})


@in_out_bp.route('/in-out/batch/<int:batch_id>/delete', methods=['POST'])
@login_required
def in_out_delete_batch(batch_id):
    if not (current_user.is_admin() or current_user.has_permission('lending_return', 'delete_batch')):
        return jsonify({'success': False, 'message': 'Permission denied'}), 403
    batch = ItemBatch.query.get_or_404(batch_id)
    item  = batch.item
    label = batch.get_display_label()
    if batch.sn_tracking_enabled and batch.serial_numbers:
        isn_list = ', '.join(sn.internal_serial_number for sn in batch.serial_numbers)
        log_audit(current_user.id, 'batch_sn_purge', 'batch', batch_id,
                  f'Deleted SN batch "{label}" from {item.name} | ISNs: {isn_list}')
    db.session.delete(batch)
    item.recalculate_from_batches()
    item.updated_by = current_user.id
    item.updated_at = datetime.now(timezone.utc)
    db.session.commit()
    log_audit(current_user.id, 'delete', 'batch', batch_id,
              f'Deleted batch "{label}" from {item.name} via /in-out')
    return jsonify({'success': True, 'message': f'Batch "{label}" deleted.'})
