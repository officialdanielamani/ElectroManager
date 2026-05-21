"""
External REST API v1  —  /api/v1/
Authentication : Authorization: Bearer <api_key>
All timestamps : ISO 8601 naive (server timezone)
"""
from flask import Blueprint, request, jsonify
from models import (db, User, Item, ItemBatch, BatchSerialNumber,
                    BatchLendRecord, LendingSession, _generate_lending_id, Setting)
from utils import log_audit
from datetime import datetime, timezone
import time
import threading
import re

api_v1_bp = Blueprint('api_v1', __name__, url_prefix='/api/v1')

# ── In-memory sliding-window rate limiter ─────────────────────────────────────
_rl_lock    = threading.Lock()
_rl_buckets = {}   # api_key -> [monotonic timestamps within last second]

def _check_rate_limit(api_key: str, limit: int) -> bool:
    now = time.monotonic()
    with _rl_lock:
        ts = [t for t in _rl_buckets.get(api_key, []) if now - t < 1.0]
        if len(ts) >= limit:
            _rl_buckets[api_key] = ts
            return False
        ts.append(now)
        _rl_buckets[api_key] = ts
        return True


# ── Helpers ───────────────────────────────────────────────────────────────────
def _err(http_status: int, code: str, message: str):
    return jsonify({'success': False, 'code': code, 'message': message}), http_status


def _parse_dt(s):
    if not s:
        return None
    for fmt in ('%Y-%m-%dT%H:%M:%S', '%Y-%m-%dT%H:%M', '%Y-%m-%d %H:%M:%S', '%Y-%m-%d'):
        try:
            return datetime.strptime(s, fmt)
        except ValueError:
            continue
    return None


# ── Authentication + scope gate ───────────────────────────────────────────────
# Scope map: api scope name -> (user field, system setting key)
_SCOPE_MAP = {
    'item_search':    ('api_item_search',   'api_item_search_enabled'),
    'rack_drawer':    ('api_rack_drawer',    'api_rack_drawer_enabled'),
    'lending_return': ('api_lending_return', 'api_lending_return_enabled'),
}

def _authenticate(scope: str = None):
    """
    Validate Bearer token, apply rate limit, check scope.
    Returns (user, None) on success, (None, (Response, status)) on failure.
    """
    auth = request.headers.get('Authorization', '')
    if not auth.startswith('Bearer '):
        return None, _err(401, 'INVALID_KEY', 'Authorization: Bearer <api_key> header required')
    key = auth[7:].strip()
    if not key:
        return None, _err(401, 'INVALID_KEY', 'API key is empty')

    user = User.query.filter_by(api_key=key, api_enabled=True).first()
    if not user:
        return None, _err(401, 'INVALID_KEY', 'API key not found or disabled')
    if not user.is_active:
        return None, _err(403, 'USER_DISABLED', 'User account is disabled')

    # Rate limit (default 5 req/s, configured in system settings)
    try:
        limit = max(1, min(int(Setting.get('api_rate_limit', '5')), 100))
    except (ValueError, TypeError):
        limit = 5

    if not _check_rate_limit(key, limit):
        resp = jsonify({'success': False, 'code': 'RATE_LIMITED',
                        'message': f'Rate limit exceeded ({limit} req/s)'})
        resp.headers['Retry-After'] = '1'
        return None, (resp, 429)

    # Scope check
    if scope and scope in _SCOPE_MAP:
        user_field, sys_key = _SCOPE_MAP[scope]
        if Setting.get(sys_key, 'false') != 'true':
            return None, _err(403, 'SCOPE_DISABLED',
                              'This API scope is disabled system-wide by an administrator')
        if not getattr(user, user_field, False):
            return None, _err(403, 'NO_PERMISSION',
                              f'Your account does not have the "{scope}" API scope enabled')

    return user, None


# ── Batch UID / ISN resolver ──────────────────────────────────────────────────
# Batch UID format:  {item_uuid}-B{batch_number}   e.g.  ABC123DEFG012345-B01
_BATCH_UID_RE = re.compile(r'^([A-Za-z0-9]+)-B(\d{1,4})$')

def _resolve_lookup(q: str):
    """
    Resolve a query string to (batch, sn_or_None, error_dict_or_None).
    Tries ISN first, then batch UID.
    """
    q = q.strip()
    if not q:
        return None, None, {'code': 'INVALID_QUERY', 'message': 'Query string is empty'}

    # Try ISN (BatchSerialNumber.internal_serial_number)
    sn = BatchSerialNumber.query.filter_by(
        internal_serial_number=q, is_deleted=False
    ).first()
    if sn:
        return sn.batch, sn, None

    # Try batch UID: {item_uuid}-B{num}
    m = _BATCH_UID_RE.match(q)
    if m:
        item_uuid = m.group(1)
        batch_num = int(m.group(2))
        item = Item.query.filter_by(uuid=item_uuid).first()
        if item:
            batch = ItemBatch.query.filter_by(
                item_id=item.id, batch_number=batch_num
            ).first()
            if batch:
                return batch, None, None

    return None, None, {'code': 'ITEM_NOT_FOUND',
                         'message': f'No item found for "{q}"'}


# ════════════════════════════════════════════════════════════════════════════
# GET /api/v1/lookup?q=<batch_uid or ISN>
# ════════════════════════════════════════════════════════════════════════════
@api_v1_bp.route('/lookup', methods=['GET'])
def api_lookup():
    user, err = _authenticate(scope='item_search')
    if err:
        return err

    q = request.args.get('q', '').strip()
    batch, sn, err_dict = _resolve_lookup(q)
    if err_dict:
        status = 400 if err_dict['code'] == 'INVALID_QUERY' else 404
        return _err(status, err_dict['code'], err_dict['message'])

    item = batch.item

    if sn:
        return jsonify({
            'success':              True,
            'type':                 'isn',
            'isn':                  sn.internal_serial_number,
            'batch_uid':            batch.get_batch_uid(),
            'item_name':            item.name,
            'short_info':           item.short_info or '',
            'available_for_lending': not sn.lend_to_id and not batch.lend_disabled,
            'currently_lent':       bool(sn.lend_to_id),
        })

    # Batch UID hit
    if batch.sn_tracking_enabled:
        return _err(400, 'BATCH_REQUIRES_ISN',
                    'This batch uses serial number tracking — search by ISN instead')

    return jsonify({
        'success':              True,
        'type':                 'batch',
        'batch_uid':            batch.get_batch_uid(),
        'item_name':            item.name,
        'short_info':           item.short_info or '',
        'available_for_lending': not batch.lend_disabled,
        'available_qty':        batch.get_available_quantity(),
        'total_qty':            batch.quantity,
    })


# ════════════════════════════════════════════════════════════════════════════
# GET /api/v1/session/<session_id>
# ════════════════════════════════════════════════════════════════════════════
@api_v1_bp.route('/session/<session_id>', methods=['GET'])
def api_session(session_id):
    user, err = _authenticate(scope='lending_return')
    if err:
        return err

    sess = LendingSession.query.filter_by(lending_id=session_id).first()
    if not sess:
        return _err(404, 'SESSION_NOT_FOUND', 'Lending session not found')
    if sess.created_by_id != user.id:
        return _err(403, 'NO_PERMISSION', 'This session does not belong to your account')

    def _fmt(dt):
        return dt.strftime('%Y-%m-%dT%H:%M:%S') if dt else None

    # Items from a lend session
    if sess.mode == 'lend':
        sn_items = [
            {
                'type':        'isn',
                'isn':         sn.internal_serial_number,
                'item_name':   sn.batch.item.name,
                'batch_uid':   sn.batch.get_batch_uid(),
                'returned':    sn.returned_at is not None,
                'returned_at': _fmt(sn.returned_at),
            }
            for sn in (sess.serial_number_records or [])
            if not sn.is_deleted
        ]
        lr_items = [
            {
                'type':        'batch',
                'batch_uid':   rec.batch.get_batch_uid(),
                'item_name':   rec.batch.item.name,
                'qty':         rec.quantity,
                'returned':    rec.returned_at is not None,
                'returned_at': _fmt(rec.returned_at),
            }
            for rec in (sess.lend_records or [])
        ]
        items = sn_items + lr_items
    else:
        # Return session — items are in returned_sn_records / returned_lend_records
        sn_items = [
            {
                'type':        'isn',
                'isn':         sn.internal_serial_number,
                'item_name':   sn.batch.item.name,
                'batch_uid':   sn.batch.get_batch_uid(),
                'returned_at': _fmt(sn.returned_at),
            }
            for sn in (sess.returned_sn_records or [])
            if not sn.is_deleted
        ]
        lr_items = [
            {
                'type':        'batch',
                'batch_uid':   rec.batch.get_batch_uid(),
                'item_name':   rec.batch.item.name,
                'qty':         rec.quantity,
                'returned_at': _fmt(rec.returned_at),
            }
            for rec in (sess.returned_lend_records or [])
        ]
        items = sn_items + lr_items

    return jsonify({
        'success':    True,
        'session_id': sess.lending_id,
        'mode':       sess.mode,
        'created_at': _fmt(sess.created_at),
        'lend_start': _fmt(sess.lend_start),
        'due_date':   _fmt(sess.lend_end),
        'notes':      sess.notes or '',
        'items':      items,
    })


# ════════════════════════════════════════════════════════════════════════════
# POST /api/v1/lend
# ════════════════════════════════════════════════════════════════════════════
@api_v1_bp.route('/lend', methods=['POST'])
def api_lend():
    user, err = _authenticate(scope='lending_return')
    if err:
        return err

    can_lend = (user.has_permission('lending_return', 'edit_lending') or
                user.has_permission('lending_return', 'only_self_lending'))
    if not can_lend:
        return _err(403, 'NO_PERMISSION', 'Your role does not allow lending')

    data    = request.get_json(silent=True) or {}
    items   = data.get('items', [])
    due_date = _parse_dt(data.get('due_date', ''))
    note    = (data.get('note', '') or '').strip()[:256]
    notify  = bool(data.get('notify', False))
    dry_run = bool(data.get('dry_run', False))
    try:
        notify_days = max(1, min(int(data.get('notify_days_before', 3)), 365))
    except (ValueError, TypeError):
        notify_days = 3

    if not items:
        return _err(400, 'CART_EMPTY', 'items array is required and must not be empty')

    now = datetime.now(timezone.utc)

    if due_date and due_date < now.replace(tzinfo=None):
        return _err(400, 'DUE_DATE_PAST', 'due_date must be in the future')

    # ── Validate every item before touching the DB ────────────────────────────
    resolved     = []   # items that passed validation
    item_results = []   # per-item status for response

    for idx, entry in enumerate(items):
        q = (entry.get('batch_id') or entry.get('isn') or '').strip()
        if not q:
            item_results.append({
                'index': idx, 'status': 'error',
                'code': 'INVALID_QUERY', 'message': 'Each item needs a batch_id or isn field',
            })
            continue

        batch, sn, err_dict = _resolve_lookup(q)
        if err_dict:
            item_results.append({
                'index': idx, 'query': q, 'status': 'error',
                'code': err_dict['code'], 'message': err_dict['message'],
            })
            continue

        item_obj = batch.item

        if batch.lend_disabled:
            item_results.append({
                'index': idx, 'query': q, 'status': 'error',
                'code': 'ITEM_DISABLED',
                'message': f'"{batch.get_display_label()}" is disabled from lending',
            })
            continue

        if sn:
            # ISN item
            if sn.lend_to_id:
                item_results.append({
                    'index': idx, 'query': q, 'status': 'error',
                    'code': 'ISN_IN_USE', 'message': f'{q} is already lent out',
                })
                continue
            resolved.append({'idx': idx, 'query': q, 'type': 'sn',
                              'batch': batch, 'sn': sn, 'item_name': item_obj.name})
            item_results.append({
                'index': idx, 'query': q, 'type': 'isn',
                'item_name': item_obj.name, 'batch_uid': batch.get_batch_uid(),
                'status': 'ok',
            })

        else:
            # Normal batch
            if batch.sn_tracking_enabled:
                item_results.append({
                    'index': idx, 'query': q, 'status': 'error',
                    'code': 'BATCH_REQUIRES_ISN',
                    'message': 'This batch uses serial number tracking — use ISN',
                })
                continue
            try:
                qty = max(1, int(entry.get('qty', 1)))
            except (ValueError, TypeError):
                qty = 1
            avail = batch.get_available_quantity()
            if qty > avail:
                item_results.append({
                    'index': idx, 'query': q, 'status': 'error',
                    'code': 'NO_STOCK',
                    'message': f'Requested qty {qty} exceeds available {avail}',
                })
                continue
            resolved.append({'idx': idx, 'query': q, 'type': 'normal',
                              'batch': batch, 'qty': qty, 'item_name': item_obj.name})
            item_results.append({
                'index': idx, 'query': q, 'type': 'batch',
                'item_name': item_obj.name, 'batch_uid': batch.get_batch_uid(),
                'qty': qty, 'status': 'ok',
            })

    # All-or-none gate
    if any(r['status'] == 'error' for r in item_results):
        return jsonify({
            'success': False,
            'code':    'CART_VALIDATION_FAILED',
            'message': 'One or more items could not be processed. No changes were made.',
            'items':   item_results,
        }), 409

    if dry_run:
        return jsonify({
            'success':  True,
            'dry_run':  True,
            'message':  'Validation passed. No changes made (dry_run=true).',
            'items':    item_results,
        })

    # ── Commit ────────────────────────────────────────────────────────────────
    lend_start = now.replace(tzinfo=None)
    item_note  = note[:128] or None

    session_obj = LendingSession(
        lending_id    = _generate_lending_id(),
        mode          = 'lend',
        created_by_id = user.id,
        lend_to_type  = 'user',
        lend_to_id    = user.id,
        lend_start    = lend_start,
        lend_end      = due_date,
        notes         = note or None,
    )
    db.session.add(session_obj)
    db.session.flush()

    for r in resolved:
        batch = r['batch']
        if r['type'] == 'sn':
            sn = r['sn']
            sn.lend_to_type            = 'user'
            sn.lend_to_id              = user.id
            sn.lend_start              = lend_start
            sn.lend_end                = due_date
            sn.lend_note               = item_note
            sn.lend_notify_enabled     = notify
            sn.lend_notify_before_days = notify_days
            sn.lending_session_id      = session_obj.id
        else:
            rec = BatchLendRecord(
                batch_id                = batch.id,
                lend_to_type            = 'user',
                lend_to_id              = user.id,
                quantity                = r['qty'],
                lend_start              = lend_start,
                lend_end                = due_date,
                lend_note               = item_note,
                lending_session_id      = session_obj.id,
                lend_notify_enabled     = notify,
                lend_notify_before_days = notify_days,
            )
            db.session.add(rec)
        batch.item.updated_by = user.id
        batch.item.updated_at = lend_start

    db.session.commit()
    log_audit(user.id, 'lend', 'lending_session', session_obj.id,
              f'API lend {session_obj.lending_id}: {len(resolved)} item(s)')

    for r in item_results:
        r['status'] = 'lent'

    return jsonify({
        'success':    True,
        'session_id': session_obj.lending_id,
        'lend_start': lend_start.strftime('%Y-%m-%dT%H:%M:%S'),
        'due_date':   due_date.strftime('%Y-%m-%dT%H:%M:%S') if due_date else None,
        'items':      item_results,
    })


# ════════════════════════════════════════════════════════════════════════════
# POST /api/v1/return
# ════════════════════════════════════════════════════════════════════════════
@api_v1_bp.route('/return', methods=['POST'])
def api_return():
    user, err = _authenticate(scope='lending_return')
    if err:
        return err

    can_return = (user.has_permission('lending_return', 'edit_lending') or
                  user.has_permission('lending_return', 'only_self_lending'))
    if not can_return:
        return _err(403, 'NO_PERMISSION', 'Your role does not allow returning items')

    data    = request.get_json(silent=True) or {}
    items   = data.get('items', [])
    note    = (data.get('note', '') or '').strip()[:256]
    dry_run = bool(data.get('dry_run', False))

    if not items:
        return _err(400, 'CART_EMPTY', 'items array is required and must not be empty')

    now       = datetime.now(timezone.utc)
    return_dt = now.replace(tzinfo=None)

    # ── Validate every item before touching the DB ────────────────────────────
    resolved     = []
    item_results = []

    for idx, entry in enumerate(items):
        q = (entry.get('batch_id') or entry.get('isn') or '').strip()
        if not q:
            item_results.append({
                'index': idx, 'status': 'error',
                'code': 'INVALID_QUERY', 'message': 'Each item needs a batch_id or isn field',
            })
            continue

        batch, sn, err_dict = _resolve_lookup(q)
        if err_dict:
            item_results.append({
                'index': idx, 'query': q, 'status': 'error',
                'code': err_dict['code'], 'message': err_dict['message'],
            })
            continue

        item_obj = batch.item

        if sn:
            # ISN return — must be lent to this user
            if not sn.lend_to_id:
                item_results.append({
                    'index': idx, 'query': q, 'status': 'error',
                    'code': 'NO_LENDING_RECORD', 'message': f'{q} is not currently lent out',
                })
                continue
            if sn.lend_to_type != 'user' or sn.lend_to_id != user.id:
                item_results.append({
                    'index': idx, 'query': q, 'status': 'error',
                    'code': 'RETURN_NO_RECORD', 'message': f'{q} is not lent to your account',
                })
                continue
            on_time = (sn.lend_end is None) or (return_dt <= sn.lend_end)
            resolved.append({'idx': idx, 'query': q, 'type': 'sn',
                              'batch': batch, 'sn': sn,
                              'item_name': item_obj.name, 'on_time': on_time})
            item_results.append({
                'index': idx, 'query': q, 'type': 'isn',
                'item_name': item_obj.name, 'batch_uid': batch.get_batch_uid(),
                'on_time': on_time, 'status': 'ok',
            })

        else:
            # Normal batch return
            if batch.sn_tracking_enabled:
                item_results.append({
                    'index': idx, 'query': q, 'status': 'error',
                    'code': 'BATCH_REQUIRES_ISN',
                    'message': 'This batch uses serial number tracking — use ISN',
                })
                continue
            try:
                qty = max(1, int(entry.get('qty', 1)))
            except (ValueError, TypeError):
                qty = 1

            # Active records lent to this user, oldest first (FIFO)
            recs = (BatchLendRecord.query
                    .filter_by(batch_id=batch.id, lend_to_type='user', lend_to_id=user.id)
                    .filter(BatchLendRecord.returned_at.is_(None))
                    .order_by(BatchLendRecord.lend_start.asc(), BatchLendRecord.id.asc())
                    .all())

            if not recs:
                item_results.append({
                    'index': idx, 'query': q, 'status': 'error',
                    'code': 'NO_LENDING_RECORD',
                    'message': f'No active lending record found for {q}',
                })
                continue

            total_lent = sum(r.quantity for r in recs)
            if qty > total_lent:
                item_results.append({
                    'index': idx, 'query': q, 'status': 'error',
                    'code': 'RETURN_QTY_EXCEEDED',
                    'message': f'Cannot return {qty} — only {total_lent} currently borrowed',
                })
                continue

            on_time = all((r.lend_end is None) or (return_dt <= r.lend_end) for r in recs)
            resolved.append({'idx': idx, 'query': q, 'type': 'normal',
                              'batch': batch, 'recs': recs, 'qty': qty,
                              'item_name': item_obj.name, 'on_time': on_time})
            item_results.append({
                'index': idx, 'query': q, 'type': 'batch',
                'item_name': item_obj.name, 'batch_uid': batch.get_batch_uid(),
                'qty': qty, 'on_time': on_time, 'status': 'ok',
            })

    # All-or-none gate
    if any(r['status'] == 'error' for r in item_results):
        return jsonify({
            'success': False,
            'code':    'CART_VALIDATION_FAILED',
            'message': 'One or more items could not be processed. No changes were made.',
            'items':   item_results,
        }), 409

    if dry_run:
        return jsonify({
            'success': True,
            'dry_run': True,
            'message': 'Validation passed. No changes made (dry_run=true).',
            'items':   item_results,
        })

    # ── Commit ────────────────────────────────────────────────────────────────
    any_late  = any(not r['on_time'] for r in resolved)
    item_note = note[:128] or None

    session_obj = LendingSession(
        lending_id    = _generate_lending_id(),
        mode          = 'return',
        created_by_id = user.id,
        notes         = note or None,
    )
    db.session.add(session_obj)
    db.session.flush()

    for r in resolved:
        batch = r['batch']
        if r['type'] == 'sn':
            sn = r['sn']
            sn.returned_from_label = sn.get_lend_to_display()
            sn.returned_at         = return_dt
            sn.lend_to_type        = ''
            sn.lend_to_id          = None
            sn.lend_start          = None
            # lend_end kept for history
            sn.lend_note           = item_note
            sn.lend_notify_enabled = False
            sn.return_session_id   = session_obj.id
        else:
            # FIFO: consume oldest records first
            remaining = r['qty']
            for rec in r['recs']:
                if remaining <= 0:
                    break
                take = min(remaining, rec.quantity)
                if take >= rec.quantity:
                    rec.returned_at       = return_dt
                    rec.return_session_id = session_obj.id
                else:
                    rec.quantity         -= take
                    rec.return_session_id = session_obj.id
                remaining -= take
        batch.item.updated_by = user.id
        batch.item.updated_at = return_dt

    db.session.commit()
    log_audit(user.id, 'return', 'lending_session', session_obj.id,
              f'API return {session_obj.lending_id}: {len(resolved)} item(s)')

    for r in item_results:
        r['status'] = 'returned'

    return jsonify({
        'success':         True,
        'session_id':      session_obj.lending_id,
        'status':          'on_time' if not any_late else 'late',
        'return_datetime': return_dt.strftime('%Y-%m-%dT%H:%M:%S'),
        'items':           item_results,
    })
