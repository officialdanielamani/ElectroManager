"""
External REST API v1  —  /api/v1/
Authentication : Authorization: Bearer <api_key>
All timestamps : ISO 8601 naive (server timezone)
"""
from flask import Blueprint, request, jsonify, make_response
from models import (db, User, Item, ItemBatch, BatchSerialNumber,
                    BatchLendRecord, LendingSession, Rack, Location,
                    _generate_lending_id, Setting)
from utils import log_audit
from datetime import datetime, timezone
import hashlib
import time
import threading
import re

api_v1_bp = Blueprint('api_v1', __name__, url_prefix='/api/v1')


@api_v1_bp.after_request
def _cors(response):
    """Allow browser clients (e.g. ESP32-served pages) to call the API directly."""
    response.headers['Access-Control-Allow-Origin']  = '*'
    response.headers['Access-Control-Allow-Headers'] = 'Authorization, Content-Type'
    response.headers['Access-Control-Allow-Methods'] = 'GET, POST, OPTIONS'
    response.headers['Access-Control-Max-Age']       = '86400'
    return response


@api_v1_bp.route('/<path:_>', methods=['OPTIONS'])
def _preflight(_):
    """Handle CORS preflight for all API v1 routes."""
    return make_response('', 204)

# ── In-memory sliding-window rate limiter ─────────────────────────────────────
_rl_lock    = threading.Lock()
_rl_buckets = {}   # user_id (int) -> [monotonic timestamps within last second]

def _check_rate_limit(user_id: int, limit: int) -> bool:
    # Keyed on user_id so rotating API keys does not reset the rate limit counter.
    now = time.monotonic()
    with _rl_lock:
        ts = [t for t in _rl_buckets.get(user_id, []) if now - t < 1.0]
        if len(ts) >= limit:
            _rl_buckets[user_id] = ts
            return False
        ts.append(now)
        _rl_buckets[user_id] = ts
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

    key_hash = hashlib.sha256(key.encode()).hexdigest()
    user = User.query.filter_by(api_key_hash=key_hash, api_enabled=True).first()
    if not user:
        return None, _err(401, 'INVALID_KEY', 'API key not found or disabled')
    if not user.is_active:
        return None, _err(403, 'USER_DISABLED', 'User account is disabled')

    # Rate limit (default 5 req/s, configured in system settings)
    try:
        limit = max(1, min(int(Setting.get('api_rate_limit', '5')), 100))
    except (ValueError, TypeError):
        limit = 5

    if not _check_rate_limit(user.id, limit):
        resp = jsonify({'success': False, 'code': 'RATE_LIMITED',
                        'message': f'Rate limit exceeded ({limit} req/s)'})
        resp.headers['Retry-After'] = '1'
        return None, (resp, 429)

    # Scope check
    if scope and scope in _SCOPE_MAP:
        user_field, sys_key = _SCOPE_MAP[scope]
        if not Setting.get(sys_key, False):
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
        is_api        = True,
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
        is_api        = True,
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


# ════════════════════════════════════════════════════════════════════════════
# Location / Rack & Drawer — shared helpers
# ════════════════════════════════════════════════════════════════════════════

def _parse_cell(cell_id):
    """'R2-C3' → (2, 3); anything else → (None, None)"""
    if not cell_id:
        return None, None
    m = re.match(r'^R(\d+)-C(\d+)$', cell_id)
    return (int(m.group(1)), int(m.group(2))) if m else (None, None)


def _batch_summary(batch):
    return {
        'batch_uid':   batch.get_batch_uid(),
        'batch_label': batch.get_display_label(),
        'quantity':    batch.quantity,
        'available':   batch.get_available_quantity(),
        'sn_tracking': batch.sn_tracking_enabled,
    }


def _batch_location(batch):
    """Return location dict for one batch (respects follow_main_location)."""
    if batch.follow_main_location:
        item = batch.item
        rack = item.rack if item.rack_id else None
        loc  = item.general_location if item.location_id else None
    else:
        rack = batch.batch_rack if batch.rack_id else None
        loc  = batch.batch_location if batch.location_id else None

    if rack:
        cell = (batch.item.drawer if batch.follow_main_location else batch.drawer) or ''
        row, col = _parse_cell(cell)
        return {
            'location_type':       'rack',
            'rack_uuid':           rack.uuid,
            'rack_name':           rack.name,
            'rack_color':          rack.color or '#6c757d',
            'drawer_cell':         cell,
            'drawer_row':          row,
            'drawer_col':          col,
            'drawer_short_info':   rack.get_drawer_short_info(cell) if cell else '',
        }
    if loc:
        return {
            'location_type':  'location',
            'location_uuid':  loc.uuid,
            'location_name':  loc.name,
            'location_color': loc.color or '#6c757d',
        }
    return {'location_type': 'unspecified'}


def _drawer_entries(rack, cell_id):
    """Return item entries for one drawer cell, matching visual-storage format.

    item_main    → item whose main location is here; includes all follow_main batches.
    batch_override → one entry PER batch that has overridden its location to here.
    """
    items_main = Item.query.filter_by(rack_id=rack.id, drawer=cell_id).all()
    batches_ov = ItemBatch.query.filter_by(
        rack_id=rack.id, drawer=cell_id, follow_main_location=False).all()

    result = []
    for item in items_main:
        batches = [b for b in item.batches if b.follow_main_location]
        result.append({
            'type':       'item_main',
            'item_uuid':  item.uuid,
            'name':       item.name,
            'sku':        item.sku or '',
            'short_info': item.short_info or '',
            'batches':    [_batch_summary(b) for b in batches],
        })

    for batch in batches_ov:
        iobj = batch.item
        if not iobj:
            continue
        result.append({
            'type':        'batch_override',
            'item_uuid':   iobj.uuid,
            'name':        iobj.name,
            'sku':         iobj.sku or '',
            'short_info':  iobj.short_info or '',
            'batch_uid':   batch.get_batch_uid(),
            'batch_label': batch.get_display_label(),
            'quantity':    batch.quantity,
            'available':   batch.get_available_quantity(),
            'sn_tracking': batch.sn_tracking_enabled,
        })
    return result


# ════════════════════════════════════════════════════════════════════════════
# GET /api/v1/location/search?q=<query>[&limit=20]
# ════════════════════════════════════════════════════════════════════════════
@api_v1_bp.route('/location/search', methods=['GET'])
def api_location_search():
    user, err = _authenticate(scope='rack_drawer')
    if err:
        return err

    q = (request.args.get('q', '') or '').strip()
    if not q:
        return _err(400, 'MISSING_QUERY', 'q parameter is required')

    try:
        limit = max(1, min(int(request.args.get('limit', 20)), 50))
    except (ValueError, TypeError):
        limit = 20

    results    = []
    query_type = 'name'

    # 1 — ISN exact match
    sn = BatchSerialNumber.query.filter_by(internal_serial_number=q).first()
    if sn and not sn.is_deleted:
        query_type = 'isn'
        batch = sn.batch
        item  = batch.item
        entry = {
            'name':       item.name,
            'item_uuid':  item.uuid,
            'sku':        item.sku or '',
            'short_info': item.short_info or '',
            'isn':        sn.internal_serial_number,
            'lent_out':   bool(sn.lend_to_id),
            'locations':  [{**_batch_summary(batch), **_batch_location(batch)}],
        }
        results.append(entry)

    # 2 — Batch UID  (e.g. "ABCDEF12-B03")
    elif re.match(r'^[A-Za-z0-9]+-B\d{1,4}$', q):
        query_type = 'batch_uid'
        batch, _, err_d = _resolve_lookup(q)
        if not err_d and batch:
            item = batch.item
            results.append({
                'name':       item.name,
                'item_uuid':  item.uuid,
                'sku':        item.sku or '',
                'short_info': item.short_info or '',
                'locations':  [{**_batch_summary(batch), **_batch_location(batch)}],
            })
        else:
            return _err(404, err_d['code'] if err_d else 'NOT_FOUND', 'Batch not found')

    # 3 — Item UUID exact match
    elif re.match(r'^[A-Za-z0-9]{10,20}$', q):
        item = Item.query.filter_by(uuid=q).first()
        if item:
            query_type = 'uuid'
            locs = []
            for b in item.batches:
                locs.append({**_batch_summary(b), **_batch_location(b)})
            results.append({
                'name':       item.name,
                'item_uuid':  item.uuid,
                'sku':        item.sku or '',
                'short_info': item.short_info or '',
                'locations':  locs,
            })
        # fall through to name search if not found
        if not results:
            query_type = 'name'

    # 4 — Item name partial match
    if query_type == 'name':
        items = (Item.query
                 .filter(Item.name.ilike(f'%{q}%'))
                 .order_by(Item.name)
                 .limit(limit)
                 .all())
        for item in items:
            locs = [{**_batch_summary(b), **_batch_location(b)} for b in item.batches]
            results.append({
                'name':       item.name,
                'item_uuid':  item.uuid,
                'sku':        item.sku or '',
                'short_info': item.short_info or '',
                'locations':  locs,
            })

    return jsonify({
        'success':    True,
        'query':      q,
        'query_type': query_type,
        'count':      len(results),
        'results':    results,
    })


# ════════════════════════════════════════════════════════════════════════════
# GET /api/v1/location/<location_uuid>
# ════════════════════════════════════════════════════════════════════════════
@api_v1_bp.route('/location/<location_uuid>', methods=['GET'])
def api_location_info(location_uuid):
    user, err = _authenticate(scope='rack_drawer')
    if err:
        return err

    loc = Location.query.filter_by(uuid=location_uuid).first()
    if not loc:
        return _err(404, 'LOCATION_NOT_FOUND', 'Location not found')

    # Racks physically placed in this location
    racks_list = []
    for rack in loc.racks:
        unavail  = len(rack.get_unavailable_drawers())
        total    = rack.rows * rack.cols
        occupied = db.session.query(db.func.count()).select_from(
            Item.__table__
        ).filter_by(rack_id=rack.id).scalar() or 0
        occupied += db.session.query(db.func.count()).select_from(
            ItemBatch.__table__
        ).filter_by(rack_id=rack.id, follow_main_location=False).scalar() or 0
        racks_list.append({
            'uuid':       rack.uuid,
            'name':       rack.name,
            'short_info': rack.short_info or '',
            'color':      rack.color or '#6c757d',
            'rows':       rack.rows,
            'cols':       rack.cols,
            'stats': {
                'total_cells': total,
                'unavailable': unavail,
                'used':        occupied,
                'empty':       total - unavail - occupied,
            },
        })

    # Items whose general (non-rack) location is here
    items_main = Item.query.filter_by(location_id=loc.id, rack_id=None).all()
    item_list  = []
    for item in items_main:
        follow_batches = [b for b in item.batches if b.follow_main_location]
        total_qty = sum(b.quantity for b in follow_batches)
        avail_qty = sum(b.get_available_quantity() for b in follow_batches)
        item_list.append({
            'type':       'item_main',
            'name':       item.name,
            'item_uuid':  item.uuid,
            'sku':        item.sku or '',
            'short_info': item.short_info or '',
            'quantity':   total_qty,
            'available':  avail_qty,
        })

    # Batches whose overridden location (non-rack) is here
    batches_ov = ItemBatch.query.filter_by(
        location_id=loc.id, rack_id=None, follow_main_location=False).all()
    for batch in batches_ov:
        iobj = batch.item
        if not iobj:
            continue
        item_list.append({
            'type':        'batch_override',
            'name':        iobj.name,
            'item_uuid':   iobj.uuid,
            'sku':         iobj.sku or '',
            'short_info':  iobj.short_info or '',
            'batch_uid':   batch.get_batch_uid(),
            'batch_label': batch.get_display_label(),
            'quantity':    batch.quantity,
            'available':   batch.get_available_quantity(),
            'sn_tracking': batch.sn_tracking_enabled,
        })

    return jsonify({
        'success': True,
        'location': {
            'uuid':        loc.uuid,
            'name':        loc.name,
            'short_info':  loc.info or '',
            'description': loc.description or '',
            'color':       loc.color or '#6c757d',
        },
        'rack_count':  len(racks_list),
        'item_count':  len(item_list),
        'racks':  racks_list,
        'items':  item_list,
    })


# ════════════════════════════════════════════════════════════════════════════
# GET /api/v1/rack/<rack_uuid>
# ════════════════════════════════════════════════════════════════════════════
@api_v1_bp.route('/rack/<rack_uuid>', methods=['GET'])
def api_rack_info(rack_uuid):
    user, err = _authenticate(scope='rack_drawer')
    if err:
        return err

    rack = Rack.query.filter_by(uuid=rack_uuid).first()
    if not rack:
        return _err(404, 'RACK_NOT_FOUND', 'Rack not found')

    # Location
    loc = rack.physical_location
    loc_obj = {'uuid': loc.uuid, 'name': loc.name, 'color': loc.color or '#6c757d'} if loc else None

    # Drawer usage stats
    unavailable_set = set(rack.get_unavailable_drawers())
    total_cells = rack.rows * rack.cols
    unavail_cnt = len(unavailable_set)

    # Items in rack (main + batch-override)
    items_main = Item.query.filter_by(rack_id=rack.id).all()
    batches_ov = ItemBatch.query.filter_by(rack_id=rack.id, follow_main_location=False).all()
    occupied_cells = set()
    for i in items_main:
        if i.drawer:
            occupied_cells.add(i.drawer)
    for b in batches_ov:
        if b.drawer:
            occupied_cells.add(b.drawer)

    # Build items list (lightweight)
    item_list = []
    for item in items_main:
        cell = item.drawer or ''
        row, col = _parse_cell(cell)
        batches = [b for b in item.batches if b.follow_main_location]
        total_qty = sum(b.quantity for b in batches)
        avail_qty = sum(b.get_available_quantity() for b in batches)
        item_list.append({
            'type':        'item_main',
            'name':        item.name,
            'item_uuid':   item.uuid,
            'sku':         item.sku or '',
            'short_info':  item.short_info or '',
            'drawer_cell': cell,
            'drawer_row':  row,
            'drawer_col':  col,
            'quantity':    total_qty,
            'available':   avail_qty,
        })

    by_item = {}
    for batch in batches_ov:
        iobj = batch.item
        if not iobj:
            continue
        cell = batch.drawer or ''
        row, col = _parse_cell(cell)
        key = (iobj.id, cell)
        if key not in by_item:
            by_item[key] = {
                'type':        'batch_override',
                'name':        iobj.name,
                'item_uuid':   iobj.uuid,
                'sku':         iobj.sku or '',
                'short_info':  iobj.short_info or '',
                'drawer_cell': cell,
                'drawer_row':  row,
                'drawer_col':  col,
                'quantity':    0,
                'available':   0,
            }
        by_item[key]['quantity']  += batch.quantity
        by_item[key]['available'] += batch.get_available_quantity()
    item_list.extend(by_item.values())

    return jsonify({
        'success': True,
        'rack': {
            'uuid':        rack.uuid,
            'name':        rack.name,
            'short_info':  rack.short_info or '',
            'description': rack.description or '',
            'color':       rack.color or '#6c757d',
            'location':    loc_obj,
            'rows':        rack.rows,
            'cols':        rack.cols,
            'stats': {
                'total_cells':  total_cells,
                'unavailable':  unavail_cnt,
                'used':         len(occupied_cells),
                'empty':        total_cells - unavail_cnt - len(occupied_cells),
            },
        },
        'items': item_list,
    })


# ════════════════════════════════════════════════════════════════════════════
# GET /api/v1/rack/<rack_uuid>/layout
# ════════════════════════════════════════════════════════════════════════════
@api_v1_bp.route('/rack/<rack_uuid>/layout', methods=['GET'])
def api_rack_layout(rack_uuid):
    user, err = _authenticate(scope='rack_drawer')
    if err:
        return err

    rack = Rack.query.filter_by(uuid=rack_uuid).first()
    if not rack:
        return _err(404, 'RACK_NOT_FOUND', 'Rack not found')

    unavailable = set(rack.get_unavailable_drawers())
    drawer_info = rack.get_drawer_info()

    # compute_merge_layout() distinguishes two kinds of groups:
    #   rectangular merge  → skip_cells (slaves hidden) + cell_spans (master has rowspan/colspan)
    #   non-rectangular group → group_cells (all cells visible, master + slave roles)
    skip_cells, cell_spans, group_cells = rack.compute_merge_layout()

    # Pre-load occupied cells (2 queries, not N×M)
    item_drawers  = db.session.query(Item.drawer).filter_by(rack_id=rack.id).all()
    batch_drawers = db.session.query(ItemBatch.drawer).filter_by(
        rack_id=rack.id, follow_main_location=False).all()
    item_count_map = {}
    for (d,) in item_drawers:
        if d:
            item_count_map[d] = item_count_map.get(d, 0) + 1
    for (d,) in batch_drawers:
        if d:
            item_count_map[d] = item_count_map.get(d, 0) + 1

    cells = []
    # Cell IDs are 1-indexed (R1-C1 … R{rows}-C{cols}) matching visual-storage
    for r in range(1, rack.rows + 1):
        for c in range(1, rack.cols + 1):
            cid = f'R{r}-C{c}'

            if cid in unavailable:
                state = 'unavailable'
            elif cid in skip_cells:
                # Slave of a rectangular merge — physically absent from grid
                state = 'merged_away'
            elif cid in cell_spans:
                # Master of a rectangular merge — spans row_span × col_span cells
                state = 'merged_master'
            elif cid in group_cells:
                # Part of a non-rectangular group — all cells stay visible
                g = group_cells[cid]
                state = 'group_master' if g['role'] == 'master' else 'group_slave'
            elif cid in item_count_map:
                state = 'has_items'
            else:
                state = 'empty'

            cell = {
                'row':        r,
                'col':        c,
                'cell_id':    cid,
                'state':      state,
                'short_info': drawer_info.get(cid, ''),
            }

            if state == 'merged_master':
                spans = cell_spans[cid]
                cell['row_span']   = spans['rowspan']
                cell['col_span']   = spans['colspan']
                cell['item_count'] = item_count_map.get(cid, 0)
            elif state == 'unavailable' and cid in cell_spans:
                # Unavailable cell that is also a merge master — include span so
                # clients can render it at the correct size.
                spans = cell_spans[cid]
                cell['row_span'] = spans['rowspan']
                cell['col_span'] = spans['colspan']
            elif state == 'merged_away':
                # Find the master so the client knows which cell it belongs to
                for group in rack.get_merged_cells():
                    if cid in group.get('cells', []):
                        cell['master_cell'] = group.get('master')
                        break
            elif state in ('group_master', 'group_slave'):
                g = group_cells[cid]
                cell['group_master']  = g['master']
                cell['group_size']    = g['count']
                cell['item_count']    = item_count_map.get(cid, 0)
            elif state == 'has_items':
                cell['item_count'] = item_count_map.get(cid, 0)

            cells.append(cell)

    return jsonify({
        'success':   True,
        'rack_uuid': rack.uuid,
        'rack_name': rack.name,
        'rack_color': rack.color or '#6c757d',
        'rows':      rack.rows,
        'cols':      rack.cols,
        'legend': {
            'empty':        'Cell is empty',
            'has_items':    'Cell contains items',
            'merged_master':'Master of a rectangular merge (use row_span/col_span)',
            'merged_away':  'Hidden slave of a rectangular merge',
            'group_master': 'Master of a non-rectangular group (cell is visible)',
            'group_slave':  'Member of a non-rectangular group (cell is visible)',
            'unavailable':  'Cell marked as unavailable',
        },
        'cells':     cells,
    })


# ════════════════════════════════════════════════════════════════════════════
# GET /api/v1/rack/<rack_uuid>/drawer/<int:row>/<int:col>
# ════════════════════════════════════════════════════════════════════════════
@api_v1_bp.route('/rack/<rack_uuid>/drawer/<int:row>/<int:col>', methods=['GET'])
def api_rack_drawer(rack_uuid, row, col):
    user, err = _authenticate(scope='rack_drawer')
    if err:
        return err

    rack = Rack.query.filter_by(uuid=rack_uuid).first()
    if not rack:
        return _err(404, 'RACK_NOT_FOUND', 'Rack not found')

    if row < 1 or row > rack.rows or col < 1 or col > rack.cols:
        return _err(400, 'INVALID_POSITION',
                    f'Position ({row},{col}) is outside rack bounds '
                    f'(rows 1–{rack.rows}, cols 1–{rack.cols})')

    cid = f'R{row}-C{col}'

    # Determine cell state using the same logic as the layout endpoint
    unavailable = set(rack.get_unavailable_drawers())
    skip_cells, cell_spans, group_cells = rack.compute_merge_layout()

    if cid in unavailable:
        state = 'unavailable'
    elif cid in skip_cells:
        state = 'merged_away'
    elif cid in cell_spans:
        state = 'merged_master'
    elif cid in group_cells:
        g = group_cells[cid]
        state = 'group_master' if g['role'] == 'master' else 'group_slave'
    else:
        state = 'has_items' if _drawer_entries(rack, cid) else 'empty'

    entries = [] if state in ('merged_away', 'unavailable') else _drawer_entries(rack, cid)

    resp = {
        'success':    True,
        'rack_uuid':  rack.uuid,
        'rack_name':  rack.name,
        'row':        row,
        'col':        col,
        'cell_id':    cid,
        'state':      state,
        'short_info': rack.get_drawer_short_info(cid),
        'items':      entries,
    }
    if state == 'merged_away':
        for group in rack.get_merged_cells():
            if cid in group.get('cells', []):
                resp['master_cell'] = group.get('master')
                break
    elif state in ('group_master', 'group_slave'):
        g = group_cells[cid]
        resp['group_master'] = g['master']
        resp['group_size']   = g['count']

    return jsonify(resp)
