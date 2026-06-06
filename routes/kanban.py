"""
Kanban Routes Blueprint
"""
from flask import Blueprint, render_template, request, jsonify, abort, redirect, url_for, flash
from flask_login import login_required, current_user
from models import (db, KanbanBoard, KanbanBoardUserState, KanbanColumn, KanbanCard,
                    KanbanTask, KanbanCategory, DEFAULT_KANBAN_COLUMNS,
                    ContactPerson, ContactOrganization, ContactGroup, User)
from datetime import datetime, timezone, date
import json
import re
import logging
import threading
import time
from collections import defaultdict, deque

logger = logging.getLogger(__name__)

kanban_bp = Blueprint('kanban', __name__)

# ── Real-time collaboration ───────────────────────────────────────
_PRESENCE_TTL = 12
_MAX_EVENTS   = 300
_store_lock   = threading.Lock()
_presence: dict     = defaultdict(dict)   # board_id -> {user_id: {...}}
_board_events: dict = defaultdict(deque)  # board_id -> deque[(ts, event)]

def _push_event(board_id: int, event: dict):
    with _store_lock:
        q = _board_events[board_id]
        q.append((time.time(), event))
        while len(q) > _MAX_EVENTS:
            q.popleft()

def _collect_events_since(board_id: int, since_ts: float) -> list:
    with _store_lock:
        return [ev for ts, ev in _board_events[board_id] if ts > since_ts]

def _collect_presence(board_id: int) -> list:
    now = time.time()
    with _store_lock:
        stale = [uid for uid, p in _presence[board_id].items()
                 if now - p['last_seen'] > _PRESENCE_TTL]
        for uid in stale:
            del _presence[board_id][uid]
        return list(_presence[board_id].values())


@kanban_bp.before_request
def _require_kanban_perm():
    """Block all kanban routes for users without view_manage permission."""
    if not current_user.is_authenticated:
        return  # individual @login_required decorators handle unauthenticated redirect
    if not current_user.has_permission('kanban', 'view_manage'):
        if request.path == '/kanban' and request.method == 'GET':
            flash('You do not have permission to access Kanban.', 'danger')
            return redirect(url_for('index'))
        return jsonify({'error': 'No permission to access Kanban'}), 403


# ── Char limits ──────────────────────────────────────────────────
_LIMITS = {
    'board_name':  128,
    'col_name':     64,
    'col_icon':     48,
    'col_color':     7,
    'card_title':  256,
    'card_desc':  2048,
    'cat_name':     64,
    'task_title':  256,
}
_COLOR_RE = re.compile(r'^#[0-9a-fA-F]{3,6}$')

# ── Hard limits ───────────────────────────────────────────────────
_MAX_BOARDS_PER_USER   = 24
_MAX_COLS_PER_BOARD    = 16
_MAX_CARDS_PER_BOARD   = 64
_MAX_TASKS_PER_CARD    = 64
_MAX_CATS_PER_BOARD    = 32


def _strip(text, max_len):
    return (text or '').strip()[:max_len]


def _safe_color(val, default='#6b7280'):
    v = (val or '').strip()
    return v if _COLOR_RE.match(v) else default


def _safe_icon(val, default='bi-circle'):
    v = re.sub(r'[^a-z0-9-]', '', (val or 'bi-circle').lower().strip())
    if not v.startswith('bi-'):
        v = 'bi-' + v
    return v[:_LIMITS['col_icon']] or default


_VALID_PERSON_TYPES = {'user', 'person', 'organization', 'group'}

def _safe_persons(raw_list):
    if not isinstance(raw_list, list):
        return []
    out = []
    for item in raw_list[:20]:
        if isinstance(item, dict):
            pid = item.get('id')
            name = _strip(str(item.get('name', '')), 256)
            ptype = item.get('type', 'person')
            if ptype not in _VALID_PERSON_TYPES:
                ptype = 'person'
            if name:
                out.append({'id': int(pid) if pid is not None else None, 'name': name, 'type': ptype})
    return out


def _safe_share_users(raw_list):
    """Validate a list of {id, name} user dicts for board sharing."""
    if not isinstance(raw_list, list):
        return []
    out, seen = [], set()
    for item in raw_list[:50]:
        if isinstance(item, dict):
            uid = item.get('id')
            name = _strip(str(item.get('name', '')), 256)
            if uid is not None and name and uid not in seen:
                out.append({'id': int(uid), 'name': name})
                seen.add(uid)
    return out


# ── Auth helpers ─────────────────────────────────────────────────

def _board_or_404(board_id):
    """Requires current user to OWN the board (board management operations)."""
    board = KanbanBoard.query.filter_by(id=board_id, user_id=current_user.id).first()
    if not board:
        abort(404)
    return board

def _writable_board_or_404(board_id):
    """Returns board if current user owns it OR has edit-shared access; 403 otherwise."""
    board = KanbanBoard.query.filter_by(id=board_id, user_id=current_user.id).first()
    if board:
        return board
    board = db.session.get(KanbanBoard, board_id)
    if board and board.share_edit_users:
        try:
            if any(u.get('id') == current_user.id for u in json.loads(board.share_edit_users)):
                return board
        except (json.JSONDecodeError, TypeError):
            pass
    abort(403)

def _accessible_board_or_404(board_id):
    """Returns (board, is_owner). Allows: own, edit-shared, view-shared, public."""
    board = KanbanBoard.query.filter_by(id=board_id, user_id=current_user.id).first()
    if board:
        return board, True
    board = db.session.get(KanbanBoard, board_id)
    if board:
        if board.is_public:
            return board, False
        for attr in ('share_edit_users', 'share_view_users'):
            raw = getattr(board, attr, None)
            if raw:
                try:
                    if any(u.get('id') == current_user.id for u in json.loads(raw)):
                        return board, False
                except (json.JSONDecodeError, TypeError):
                    pass
    abort(404)

def _column_or_404(col_id):
    col = KanbanColumn.query.get_or_404(col_id)
    _board_or_404(col.board_id)
    return col

def _card_or_404(card_id):
    """Card write access: requires own or edit-shared board."""
    card = KanbanCard.query.get_or_404(card_id)
    _writable_board_or_404(card.board_id)
    return card

def _card_readable_or_404(card_id):
    """Returns card if current user can read it (owns board OR has any shared access)."""
    card = db.session.get(KanbanCard, card_id)
    if not card:
        abort(404)
    _accessible_board_or_404(card.board_id)
    return card

def _task_or_404(task_id):
    task = KanbanTask.query.get_or_404(task_id)
    _card_or_404(task.card_id)
    return task


def _category_or_404(cat_id):
    cat = KanbanCategory.query.get_or_404(cat_id)
    _board_or_404(cat.board_id)
    return cat


# ── Serializers ──────────────────────────────────────────────────

def _task_to_dict(t):
    return {
        'id': t.id,
        'title': t.title,
        'completed': t.completed,
        'start_date': t.start_date.isoformat() if t.start_date else '',
        'due_date': t.due_date.isoformat() if t.due_date else '',
        'position': t.position,
    }


def _card_to_dict(card):
    return {
        'id': card.id,
        'title': card.title,
        'description': card.description or '',
        'priority': card.priority,
        'label_color': card.label_color or '',
        'category_id': card.category_id,
        'category_name': card.category.name if card.category_id and card.category else '',
        'key_persons': card.get_key_persons(),
        'start_date': card.start_date.isoformat() if card.start_date else '',
        'due_date': card.due_date.isoformat() if card.due_date else '',
        'completed_at': card.completed_at.isoformat() if card.completed_at else '',
        'is_overdue': card.is_overdue,
        'position': card.position,
        'column_id': card.column_id,
        'task_count': card.task_count,
        'completed_task_count': card.completed_task_count,
        'tasks': [_task_to_dict(t) for t in card.tasks],
        'created_at': card.created_at.strftime('%Y-%m-%d %H:%M') if card.created_at else '',
        'updated_at': card.updated_at.strftime('%Y-%m-%d %H:%M') if card.updated_at else '',
        'created_by_name': (card.created_by.name or card.created_by.username) if card.created_by else '',
        'updated_by_name': (card.updated_by.name or card.updated_by.username) if card.updated_by else '',
    }


# ── Main board view ──────────────────────────────────────────────

def _owner_display(user):
    """Returns 'Name - title' or just 'Name' for a board owner."""
    if not user:
        return 'Unknown'
    name = user.name or user.username
    return f"{name} - {user.short_info}" if user.short_info else name


@kanban_bp.route('/kanban')
@login_required
def kanban():
    # ── Own boards ──────────────────────────────────────────────
    own_boards = KanbanBoard.query.filter_by(user_id=current_user.id).order_by(KanbanBoard.position).all()

    # ── Public boards (other users) ────────────────────────────
    public_boards = KanbanBoard.query.filter(
        KanbanBoard.user_id != current_user.id,
        KanbanBoard.is_public == True
    ).order_by(KanbanBoard.id).all()

    # ── View-only shared boards ─────────────────────────────────
    view_only_boards = []
    public_ids = {b.id for b in public_boards}
    for b in KanbanBoard.query.filter(
        KanbanBoard.user_id != current_user.id,
        KanbanBoard.is_public == False,
        KanbanBoard.share_view_users.isnot(None),
    ).all():
        if b.id in public_ids:
            continue
        try:
            if any(u.get('id') == current_user.id for u in json.loads(b.share_view_users or '[]')):
                view_only_boards.append(b)
        except (json.JSONDecodeError, TypeError):
            pass

    # ── Edit-shared boards ─────────────────────────────────────────
    edit_boards = []
    for b in KanbanBoard.query.filter(
        KanbanBoard.user_id != current_user.id,
        KanbanBoard.is_public == False,
        KanbanBoard.share_edit_users.isnot(None),
    ).all():
        if b.id in public_ids:
            continue
        try:
            if any(u.get('id') == current_user.id
                   for u in json.loads(b.share_edit_users or '[]')):
                edit_boards.append(b)
        except (json.JSONDecodeError, TypeError):
            pass

    # ── Per-user state for non-own boards ───────────────────────
    non_own_ids = {b.id for b in public_boards + view_only_boards + edit_boards}
    user_states = {}
    if non_own_ids:
        for s in KanbanBoardUserState.query.filter(
            KanbanBoardUserState.user_id == current_user.id,
            KanbanBoardUserState.board_id.in_(non_own_ids)
        ).all():
            user_states[s.board_id] = s

    def _meta(board, share_type):
        if share_type == 'own':
            return {
                'board': board, 'share_type': 'own', 'is_own': True,
                'status': board.board_status or 'shown',
                'position': board.position,
                'owner_name': _owner_display(board.user),
                'owner_id': board.user_id,
            }
        st = user_states.get(board.id)
        return {
            'board': board, 'share_type': share_type, 'is_own': False,
            'status': st.status if st else 'shown',
            'position': st.position if st else 999,
            'owner_name': _owner_display(board.user),
            'owner_id': board.user_id,
        }

    all_meta = (
        [_meta(b, 'own') for b in own_boards] +
        [_meta(b, 'public') for b in public_boards] +
        [_meta(b, 'view_only') for b in view_only_boards] +
        [_meta(b, 'edit') for b in edit_boards]
    )

    # Visible (not hidden), pinned first
    visible_meta = sorted(
        [m for m in all_meta if m['status'] != 'hidden'],
        key=lambda m: (0 if m['status'] == 'pinned' else 1, m['position'])
    )
    boards = [m['board'] for m in visible_meta]

    # Board share type + owner lookup dicts (for template)
    board_share_types = {m['board'].id: m['share_type'] for m in all_meta}
    board_owners      = {m['board'].id: m['owner_name'] for m in all_meta}

    # Active board selection
    active_board_id = request.args.get('board', type=int)
    active_meta = None
    if active_board_id:
        active_meta = next((m for m in all_meta if m['board'].id == active_board_id), None)
    if not active_meta and visible_meta:
        active_meta = visible_meta[0]
    active_board   = active_meta['board'] if active_meta else None
    is_owner        = active_meta['is_own'] if active_meta else True
    active_share_type = active_meta['share_type'] if active_meta else 'own'

    # Listing data for Board Listing JS (all accessible boards)
    listing_boards = [
        {
            'id':          m['board'].id,
            'name':        m['board'].name,
            'board_icon':  m['board'].board_icon or 'bi-kanban',
            'board_color': m['board'].board_color or '#6b7280',
            'board_status': m['status'],
            'position':    m['position'],
            'share_type':  m['share_type'],
            'owner_name':  m['owner_name'],
            'is_own':      m['is_own'],
        }
        for m in all_meta
    ]

    can_share_board = (
        current_user.has_permission('kanban', 'share_board') and
        current_user.has_permission('settings_sections.contacts', 'view_users')
    )
    return render_template('kanban.html',
        boards=boards,
        all_boards=own_boards,
        active_board=active_board,
        is_owner=is_owner,
        active_share_type=active_share_type,
        board_share_types=board_share_types,
        board_owners=board_owners,
        listing_boards=listing_boards,
        can_share_board=can_share_board,
    )


# ── Board CRUD ───────────────────────────────────────────────────

@kanban_bp.route('/kanban/boards', methods=['POST'])
@login_required
def create_board():
    data = request.get_json(silent=True) or {}
    name = _strip(data.get('name'), _LIMITS['board_name'])
    if not name:
        return jsonify({'error': 'Board name required'}), 400

    board_count = KanbanBoard.query.filter_by(user_id=current_user.id).count()
    if board_count >= _MAX_BOARDS_PER_USER:
        return jsonify({'error': f'Maximum {_MAX_BOARDS_PER_USER} boards allowed per user'}), 400

    max_pos = db.session.query(db.func.max(KanbanBoard.position)).filter_by(user_id=current_user.id).scalar() or 0
    board = KanbanBoard(user_id=current_user.id, name=name, position=max_pos + 1)
    db.session.add(board)
    db.session.flush()

    for i, col_def in enumerate(DEFAULT_KANBAN_COLUMNS):
        col = KanbanColumn(board_id=board.id, name=col_def['name'],
                           color=col_def['color'], icon=col_def['icon'], position=i)
        db.session.add(col)

    db.session.commit()
    return jsonify({'id': board.id, 'name': board.name}), 201


@kanban_bp.route('/kanban/boards/<int:board_id>', methods=['DELETE'])
@login_required
def delete_board(board_id):
    board = _board_or_404(board_id)
    db.session.delete(board)
    db.session.commit()
    return jsonify({'ok': True})


@kanban_bp.route('/kanban/boards/reorder', methods=['POST'])
@login_required
def reorder_boards():
    data = request.get_json(silent=True) or {}
    order = data.get('order', [])
    for pos, bid in enumerate(order):
        KanbanBoard.query.filter_by(id=bid, user_id=current_user.id).update({'position': pos})
    db.session.commit()
    return jsonify({'ok': True})


# ── Board Settings ───────────────────────────────────────────────

@kanban_bp.route('/kanban/boards/<int:board_id>/settings', methods=['GET'])
@login_required
def get_board_settings(board_id):
    board, viewer_is_owner = _accessible_board_or_404(board_id)
    owner = board.user
    owner_display = _owner_display(owner)

    # Notification prefs: owner uses board-level fields; non-owner uses their user state
    if viewer_is_owner:
        notify_start_enabled = board.notify_start_enabled or False
        notify_start_days    = board.notify_start_days or 1
        notify_due_enabled   = board.notify_due_enabled or False
        notify_due_days      = board.notify_due_days or 1
    else:
        state = KanbanBoardUserState.query.filter_by(
            board_id=board.id, user_id=current_user.id
        ).first()
        notify_start_enabled = state.notify_start_enabled if state else False
        notify_start_days    = state.notify_start_days    if state else 1
        notify_due_enabled   = state.notify_due_enabled   if state else False
        notify_due_days      = state.notify_due_days      if state else 1

    return jsonify({
        'id': board.id,
        'name': board.name,
        'board_uuid': board.board_uuid or '',
        'board_icon': board.board_icon or 'bi-kanban',
        'board_color': board.board_color or '#6b7280',
        'board_status': board.board_status or 'shown',
        'is_public': board.is_public or False,
        'share_view_users': json.loads(board.share_view_users) if board.share_view_users else [],
        'share_edit_users': json.loads(board.share_edit_users) if board.share_edit_users else [],
        'notify_start_enabled': notify_start_enabled,
        'notify_start_days':    notify_start_days,
        'notify_due_enabled':   notify_due_enabled,
        'notify_due_days':      notify_due_days,
        'categories': [
            {'id': c.id, 'name': c.name, 'position': c.position}
            for c in board.categories
        ],
        'owner_display': owner_display,
        'created_at': board.created_at.strftime('%Y-%m-%d %H:%M') if board.created_at else '',
        'updated_at': board.updated_at.strftime('%Y-%m-%d %H:%M') if board.updated_at else '',
        'is_owner': viewer_is_owner,
    })


@kanban_bp.route('/kanban/boards/<int:board_id>/settings', methods=['PUT'])
@login_required
def update_board_settings(board_id):
    board, is_owner = _accessible_board_or_404(board_id)
    data = request.get_json(silent=True) or {}

    if is_owner:
        # Owner can change all board-level settings
        if 'name' in data:
            name = _strip(data['name'], _LIMITS['board_name'])
            if not name:
                return jsonify({'error': 'Board name required'}), 400
            board.name = name
        if 'board_icon' in data:
            board.board_icon = _safe_icon(data['board_icon'], 'bi-kanban')
        if 'board_color' in data:
            board.board_color = _safe_color(data['board_color'], '#6b7280')
        if 'board_status' in data and data['board_status'] in ('pinned', 'shown', 'hidden'):
            board.board_status = data['board_status']
        if 'notify_start_enabled' in data:
            board.notify_start_enabled = bool(data['notify_start_enabled'])
        if 'notify_start_days' in data:
            board.notify_start_days = max(1, min(365, int(data.get('notify_start_days') or 1)))
        if 'notify_due_enabled' in data:
            board.notify_due_enabled = bool(data['notify_due_enabled'])
        if 'notify_due_days' in data:
            board.notify_due_days = max(1, min(365, int(data.get('notify_due_days') or 1)))
        # Sharing fields — only saved if caller has share_board permission
        if current_user.has_permission('kanban', 'share_board'):
            if 'is_public' in data:
                board.is_public = bool(data['is_public'])
            if 'share_view_users' in data:
                board.share_view_users = json.dumps(_safe_share_users(data['share_view_users']))
            if 'share_edit_users' in data:
                edit_users = _safe_share_users(data['share_edit_users'])
                if len(edit_users) > 5:
                    return jsonify({'error': 'Maximum 5 users can have edit access'}), 400
                board.share_edit_users = json.dumps(edit_users)
        board.updated_at = datetime.now(timezone.utc)
    else:
        # Non-owner can only save their personal notification preferences
        state = KanbanBoardUserState.query.filter_by(
            board_id=board.id, user_id=current_user.id
        ).first()
        if not state:
            state = KanbanBoardUserState(board_id=board.id, user_id=current_user.id)
            db.session.add(state)
        if 'notify_start_enabled' in data:
            state.notify_start_enabled = bool(data['notify_start_enabled'])
        if 'notify_start_days' in data:
            state.notify_start_days = max(1, min(365, int(data.get('notify_start_days') or 1)))
        if 'notify_due_enabled' in data:
            state.notify_due_enabled = bool(data['notify_due_enabled'])
        if 'notify_due_days' in data:
            state.notify_due_days = max(1, min(365, int(data.get('notify_due_days') or 1)))

    db.session.commit()
    return jsonify({'ok': True, 'name': board.name})


@kanban_bp.route('/kanban/boards/listing', methods=['PUT'])
@login_required
def update_boards_listing():
    """Batch-update board order and status from the Board Listing tab.
    Own boards: update board.position / board.board_status directly.
    Shared boards: upsert KanbanBoardUserState per user.
    """
    data = request.get_json(silent=True) or {}
    items = data.get('boards', [])
    own_board_ids = {
        b.id for b in KanbanBoard.query.filter_by(user_id=current_user.id).all()
    }
    valid_statuses = ('pinned', 'shown', 'hidden')
    for item in items:
        bid = item.get('id')
        if not bid:
            continue
        new_pos    = int(item.get('position', 0))
        new_status = item.get('board_status', 'shown')
        if new_status not in valid_statuses:
            new_status = 'shown'
        if bid in own_board_ids:
            KanbanBoard.query.filter_by(id=bid).update(
                {'position': new_pos, 'board_status': new_status}
            )
        elif item.get('is_own') is False:
            # Shared board — upsert per-user state
            state = KanbanBoardUserState.query.filter_by(
                board_id=bid, user_id=current_user.id
            ).first()
            if state:
                state.position = new_pos
                state.status   = new_status
            else:
                db.session.add(KanbanBoardUserState(
                    board_id=bid, user_id=current_user.id,
                    position=new_pos, status=new_status
                ))
    db.session.commit()
    return jsonify({'ok': True})


@kanban_bp.route('/kanban/boards/<int:board_id>/presence', methods=['POST'])
@login_required
def board_presence(board_id):
    board, is_owner = _accessible_board_or_404(board_id)
    data = request.get_json(silent=True) or {}
    editing_card_id = data.get('editing_card_id')
    name = current_user.name or current_user.username
    access = 'edit'
    if not is_owner:
        access = 'view'
        if board.share_edit_users:
            try:
                if any(u.get('id') == current_user.id for u in json.loads(board.share_edit_users)):
                    access = 'edit'
            except (json.JSONDecodeError, TypeError):
                pass
    with _store_lock:
        _presence[board_id][current_user.id] = {
            'id': current_user.id, 'name': name,
            'last_seen': time.time(),
            'editing_card_id': int(editing_card_id) if editing_card_id else None,
            'access': access,
        }
    return jsonify({'ok': True})


@kanban_bp.route('/kanban/boards/<int:board_id>/poll')
@login_required
def board_poll(board_id):
    _accessible_board_or_404(board_id)
    since = request.args.get('since', type=float, default=0.0)
    return jsonify({
        'events':   _collect_events_since(board_id, since),
        'presence': _collect_presence(board_id),
        'ts':       time.time(),
    })


# ── Category CRUD ────────────────────────────────────────────────

@kanban_bp.route('/kanban/boards/<int:board_id>/categories', methods=['POST'])
@login_required
def create_category(board_id):
    board = _board_or_404(board_id)
    data = request.get_json(silent=True) or {}
    name = _strip(data.get('name'), _LIMITS['cat_name'])
    if not name:
        return jsonify({'error': 'Category name required'}), 400
    cat_count = KanbanCategory.query.filter_by(board_id=board.id).count()
    if cat_count >= _MAX_CATS_PER_BOARD:
        return jsonify({'error': f'Maximum {_MAX_CATS_PER_BOARD} categories per board'}), 400
    max_pos = db.session.query(db.func.max(KanbanCategory.position)).filter_by(board_id=board.id).scalar() or 0
    cat = KanbanCategory(board_id=board.id, name=name, position=max_pos + 1)
    db.session.add(cat)
    db.session.commit()
    return jsonify({'id': cat.id, 'name': cat.name, 'position': cat.position}), 201


@kanban_bp.route('/kanban/categories/<int:cat_id>', methods=['PUT'])
@login_required
def update_category(cat_id):
    cat = _category_or_404(cat_id)
    data = request.get_json(silent=True) or {}
    name = _strip(data.get('name'), _LIMITS['cat_name'])
    if not name:
        return jsonify({'error': 'Category name required'}), 400
    cat.name = name
    # Keep label_name in sync for all cards using this category
    KanbanCard.query.filter_by(category_id=cat.id).update({'label_name': name})
    db.session.commit()
    return jsonify({'id': cat.id, 'name': cat.name})


@kanban_bp.route('/kanban/categories/<int:cat_id>', methods=['DELETE'])
@login_required
def delete_category(cat_id):
    cat = _category_or_404(cat_id)
    KanbanCard.query.filter_by(category_id=cat.id).update({'category_id': None, 'label_name': ''})
    db.session.delete(cat)
    db.session.commit()
    return jsonify({'ok': True})


# ── Column CRUD ──────────────────────────────────────────────────

@kanban_bp.route('/kanban/boards/<int:board_id>/columns', methods=['POST'])
@login_required
def create_column(board_id):
    board = _board_or_404(board_id)
    data = request.get_json(silent=True) or {}
    name = _strip(data.get('name'), _LIMITS['col_name'])
    if not name:
        return jsonify({'error': 'Column name required'}), 400
    col_count = KanbanColumn.query.filter_by(board_id=board.id).count()
    if col_count >= _MAX_COLS_PER_BOARD:
        return jsonify({'error': f'Maximum {_MAX_COLS_PER_BOARD} columns per board'}), 400
    max_pos = db.session.query(db.func.max(KanbanColumn.position)).filter_by(board_id=board.id).scalar() or 0
    col = KanbanColumn(board_id=board.id, name=name,
                       color=_safe_color(data.get('color')),
                       icon=_safe_icon(data.get('icon')),
                       position=max_pos + 1)
    db.session.add(col)
    db.session.commit()
    return jsonify({'id': col.id, 'name': col.name, 'color': col.color,
                    'icon': col.icon, 'position': col.position}), 201


@kanban_bp.route('/kanban/columns/<int:col_id>', methods=['PUT'])
@login_required
def update_column(col_id):
    col = _column_or_404(col_id)
    data = request.get_json(silent=True) or {}
    if 'name' in data:
        name = _strip(data['name'], _LIMITS['col_name'])
        if not name:
            return jsonify({'error': 'Column name required'}), 400
        col.name = name
    if 'color' in data:
        col.color = _safe_color(data['color'], col.color)
    if 'icon' in data:
        col.icon = _safe_icon(data['icon'])
    db.session.commit()
    return jsonify({'id': col.id, 'name': col.name, 'color': col.color, 'icon': col.icon})


@kanban_bp.route('/kanban/columns/<int:col_id>', methods=['DELETE'])
@login_required
def delete_column(col_id):
    col = _column_or_404(col_id)
    db.session.delete(col)
    db.session.commit()
    return jsonify({'ok': True})


@kanban_bp.route('/kanban/columns/reorder', methods=['POST'])
@login_required
def reorder_columns():
    data = request.get_json(silent=True) or {}
    board_id = data.get('board_id')
    order = data.get('order', [])
    board = _board_or_404(board_id)
    col_ids = {c.id for c in board.columns}
    for pos, cid in enumerate(order):
        if cid in col_ids:
            KanbanColumn.query.filter_by(id=cid).update({'position': pos})
    db.session.commit()
    return jsonify({'ok': True})


# ── Card CRUD ────────────────────────────────────────────────────

@kanban_bp.route('/kanban/boards/<int:board_id>/cards', methods=['POST'])
@login_required
def create_card(board_id):
    board = _writable_board_or_404(board_id)
    data = request.get_json(silent=True) or {}
    title = _strip(data.get('title'), _LIMITS['card_title'])
    col_id = data.get('column_id')
    if not title:
        return jsonify({'error': 'Card title required'}), 400

    col = KanbanColumn.query.filter_by(id=col_id, board_id=board.id).first()
    if not col:
        return jsonify({'error': 'Invalid column'}), 400

    card_count = KanbanCard.query.filter_by(board_id=board.id).count()
    if card_count >= _MAX_CARDS_PER_BOARD:
        return jsonify({'error': f'Maximum {_MAX_CARDS_PER_BOARD} cards per board'}), 400

    prio = max(1, min(4, int(data.get('priority', 1))))
    cat_id = data.get('category_id')
    cat_name = ''
    if cat_id:
        cat = KanbanCategory.query.filter_by(id=cat_id, board_id=board.id).first()
        if cat:
            cat_id = cat.id
            cat_name = cat.name
        else:
            cat_id = None

    start_date = _parse_date(data.get('start_date'))
    due_date   = _parse_date(data.get('due_date'))
    if not _dates_valid(start_date, due_date):
        return jsonify({'error': 'Start date must be on or before the due date'}), 400

    max_pos = db.session.query(db.func.max(KanbanCard.position)).filter_by(column_id=col.id).scalar() or 0
    card = KanbanCard(
        board_id=board.id,
        column_id=col.id,
        title=title,
        description=_strip(data.get('description'), _LIMITS['card_desc']),
        priority=prio,
        label_color=_safe_color(data.get('label_color'), ''),
        category_id=cat_id,
        label_name=cat_name,
        key_persons=json.dumps(_safe_persons(data.get('key_persons', []))),
        start_date=start_date,
        due_date=due_date,
        position=max_pos + 1,
        created_by_id=current_user.id,
        updated_by_id=current_user.id,
    )
    db.session.add(card)
    db.session.commit()
    _push_event(board.id, {'type': 'card_created', 'user_id': current_user.id, 'card': _card_to_dict(card)})
    return jsonify(_card_to_dict(card)), 201


@kanban_bp.route('/kanban/cards/<int:card_id>', methods=['GET'])
@login_required
def get_card(card_id):
    card = _card_readable_or_404(card_id)
    return jsonify(_card_to_dict(card))


@kanban_bp.route('/kanban/cards/<int:card_id>', methods=['PUT'])
@login_required
def update_card(card_id):
    card = _card_or_404(card_id)
    data = request.get_json(silent=True) or {}

    if 'title' in data:
        title = _strip(data['title'], _LIMITS['card_title'])
        if not title:
            return jsonify({'error': 'Title required'}), 400
        card.title = title
    if 'description' in data:
        card.description = _strip(data['description'], _LIMITS['card_desc'])
    if 'priority' in data:
        card.priority = max(1, min(4, int(data['priority'])))
    if 'label_color' in data:
        card.label_color = _safe_color(data['label_color'], card.label_color or '')
    if 'category_id' in data:
        cat_id = data['category_id']
        if cat_id:
            cat = KanbanCategory.query.filter_by(id=cat_id, board_id=card.board_id).first()
            card.category_id = cat.id if cat else None
            card.label_name = cat.name if cat else ''
        else:
            card.category_id = None
            card.label_name = ''
    if 'key_persons' in data:
        card.key_persons = json.dumps(_safe_persons(data['key_persons']))
    if 'start_date' in data:
        card.start_date = _parse_date(data['start_date'])
    if 'due_date' in data:
        card.due_date = _parse_date(data['due_date'])
    if not _dates_valid(card.start_date, card.due_date):
        return jsonify({'error': 'Start date must be on or before the due date'}), 400
    if 'completed_at' in data:
        card.completed_at = datetime.now(timezone.utc) if data['completed_at'] else None
    card.updated_at = datetime.now(timezone.utc)
    card.updated_by_id = current_user.id
    db.session.commit()
    _push_event(card.board_id, {'type': 'card_updated', 'user_id': current_user.id, 'card': _card_to_dict(card)})
    return jsonify(_card_to_dict(card))


@kanban_bp.route('/kanban/cards/<int:card_id>', methods=['DELETE'])
@login_required
def delete_card(card_id):
    card = _card_or_404(card_id)
    db.session.delete(card)
    db.session.commit()
    return jsonify({'ok': True})


@kanban_bp.route('/kanban/cards/reorder', methods=['POST'])
@login_required
def reorder_cards():
    data = request.get_json(silent=True) or {}
    columns_data = data.get('columns', [])
    board_id_pushed = None
    for col_data in columns_data:
        col_id = col_data.get('column_id')
        card_ids = col_data.get('card_ids', [])
        col = KanbanColumn.query.get(col_id)
        if not col:
            continue
        _writable_board_or_404(col.board_id)
        now = datetime.now(timezone.utc)
        for pos, cid in enumerate(card_ids):
            KanbanCard.query.filter_by(id=cid, board_id=col.board_id).update(
                {'column_id': col_id, 'position': pos,
                 'updated_at': now, 'updated_by_id': current_user.id}
            )
        board_id_pushed = col.board_id
    db.session.commit()
    if board_id_pushed:
        _push_event(board_id_pushed, {
            'type': 'cards_reordered', 'user_id': current_user.id,
            'columns': [{'column_id': cd.get('column_id'), 'card_ids': cd.get('card_ids', [])}
                        for cd in columns_data],
        })
    return jsonify({'ok': True})


# ── Task CRUD ────────────────────────────────────────────────────

@kanban_bp.route('/kanban/cards/<int:card_id>/tasks', methods=['POST'])
@login_required
def create_task(card_id):
    card = _card_or_404(card_id)
    data = request.get_json(silent=True) or {}
    title = _strip(data.get('title'), _LIMITS['task_title'])
    if not title:
        return jsonify({'error': 'Task title required'}), 400
    start_date = _parse_date(data.get('start_date'))
    due_date   = _parse_date(data.get('due_date'))
    if not _dates_valid(start_date, due_date):
        return jsonify({'error': 'Task start date must be on or before the due date'}), 400
    task_count = KanbanTask.query.filter_by(card_id=card.id).count()
    if task_count >= _MAX_TASKS_PER_CARD:
        return jsonify({'error': f'Maximum {_MAX_TASKS_PER_CARD} tasks per card'}), 400
    max_pos = db.session.query(db.func.max(KanbanTask.position)).filter_by(card_id=card.id).scalar() or 0
    task = KanbanTask(
        card_id=card.id,
        title=title,
        start_date=start_date,
        due_date=due_date,
        position=max_pos + 1,
    )
    db.session.add(task)
    card.updated_at = datetime.now(timezone.utc)
    card.updated_by_id = current_user.id
    db.session.commit()
    _push_event(card.board_id, {
        'type': 'task_created', 'user_id': current_user.id,
        'task': _task_to_dict(task), 'card_id': card.id,
        'card_task_count': card.task_count,
        'card_completed_task_count': card.completed_task_count,
    })
    return jsonify(_task_to_dict(task)), 201


@kanban_bp.route('/kanban/tasks/<int:task_id>', methods=['PUT'])
@login_required
def update_task(task_id):
    task = _task_or_404(task_id)
    data = request.get_json(silent=True) or {}
    if 'title' in data:
        title = _strip(data['title'], _LIMITS['task_title'])
        if not title:
            return jsonify({'error': 'Task title required'}), 400
        task.title = title
    if 'completed' in data:
        task.completed = bool(data['completed'])
    if 'start_date' in data:
        task.start_date = _parse_date(data['start_date'])
    if 'due_date' in data:
        task.due_date = _parse_date(data['due_date'])
    if not _dates_valid(task.start_date, task.due_date):
        return jsonify({'error': 'Task start date must be on or before the due date'}), 400
    card = db.session.get(KanbanCard, task.card_id)
    if card:
        card.updated_at = datetime.now(timezone.utc)
        card.updated_by_id = current_user.id
    db.session.commit()
    if card:
        _push_event(card.board_id, {
            'type': 'task_updated', 'user_id': current_user.id,
            'task': _task_to_dict(task), 'card_id': card.id,
            'card_task_count': card.task_count,
            'card_completed_task_count': card.completed_task_count,
        })
    return jsonify(_task_to_dict(task))


@kanban_bp.route('/kanban/tasks/<int:task_id>', methods=['DELETE'])
@login_required
def delete_task(task_id):
    task = _task_or_404(task_id)
    saved_task_id = task.id
    card = db.session.get(KanbanCard, task.card_id)
    saved_card_id = card.id if card else None
    saved_board_id = card.board_id if card else None
    db.session.delete(task)
    if card:
        card.updated_at = datetime.now(timezone.utc)
        card.updated_by_id = current_user.id
    db.session.commit()
    if saved_board_id and card:
        db.session.refresh(card)
        _push_event(saved_board_id, {
            'type': 'task_deleted', 'user_id': current_user.id,
            'task_id': saved_task_id, 'card_id': saved_card_id,
            'card_task_count': card.task_count,
            'card_completed_task_count': card.completed_task_count,
        })
    return jsonify({'ok': True})


# ── Contacts ─────────────────────────────────────────────────────

@kanban_bp.route('/kanban/contacts', methods=['GET'])
@login_required
def kanban_contacts():
    can_users = current_user.has_permission('settings_sections.contacts', 'view_users')
    can_other = current_user.has_permission('settings_sections.contacts', 'view_other')
    if not can_users and not can_other:
        return jsonify({'error': 'No permission'}), 403

    results = []

    if can_users:
        for u in User.query.filter_by(is_active=True).order_by(User.name).all():
            if not u.name:
                continue  # skip users with no display name
            pic_url = ''
            if u.profile_photo:
                if u.profile_photo.startswith('share/'):
                    pic_url = f"/uploads/share/profile/{u.profile_photo[6:]}"
                else:
                    pic_url = f"/uploads/userpicture/{u.profile_photo}"
            results.append({
                'id': u.id, 'type': 'user',
                'label': u.name,
                'extra': u.short_info or '',
                'pic': pic_url,
            })

    if can_other:
        for p in ContactPerson.query.order_by(ContactPerson.name).all():
            extra = p.organization.name if p.organization else (p.email or '')
            results.append({'id': p.id, 'type': 'person', 'label': p.name, 'extra': extra})

        for o in ContactOrganization.query.order_by(ContactOrganization.name).all():
            results.append({'id': o.id, 'type': 'organization', 'label': o.name, 'extra': o.email or ''})

        for g in ContactGroup.query.order_by(ContactGroup.name).all():
            results.append({'id': g.id, 'type': 'group', 'label': g.name, 'extra': g.description or ''})

    return jsonify(results)


# ── Helpers ──────────────────────────────────────────────────────

def _parse_date(val):
    if not val:
        return None
    try:
        return date.fromisoformat(str(val))
    except (ValueError, TypeError):
        return None


def _dates_valid(start, end):
    """Return False if both dates are present and start is after end."""
    return not (start and end and start > end)
