"""
Kanban Routes Blueprint
"""
from flask import Blueprint, render_template, request, jsonify, abort
from flask_login import login_required, current_user
from models import (db, KanbanBoard, KanbanColumn, KanbanCard, KanbanTask,
                    KanbanCategory, DEFAULT_KANBAN_COLUMNS,
                    ContactPerson, ContactOrganization)
from datetime import datetime, timezone, date
import json
import re
import logging

logger = logging.getLogger(__name__)

kanban_bp = Blueprint('kanban', __name__)

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


def _safe_persons(raw_list):
    if not isinstance(raw_list, list):
        return []
    out = []
    for item in raw_list[:20]:
        if isinstance(item, dict):
            pid = item.get('id')
            name = _strip(str(item.get('name', '')), 256)
            if name:
                out.append({'id': int(pid) if pid is not None else None, 'name': name})
    return out


# ── Auth helpers ─────────────────────────────────────────────────

def _board_or_404(board_id):
    board = KanbanBoard.query.filter_by(id=board_id, user_id=current_user.id).first()
    if not board:
        abort(404)
    return board


def _column_or_404(col_id):
    col = KanbanColumn.query.get_or_404(col_id)
    _board_or_404(col.board_id)
    return col


def _card_or_404(card_id):
    card = KanbanCard.query.get_or_404(card_id)
    _board_or_404(card.board_id)
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
    }


# ── Main board view ──────────────────────────────────────────────

@kanban_bp.route('/kanban')
@login_required
def kanban():
    boards = KanbanBoard.query.filter_by(user_id=current_user.id).order_by(KanbanBoard.position).all()
    active_board_id = request.args.get('board', type=int)
    active_board = None

    if active_board_id:
        active_board = KanbanBoard.query.filter_by(id=active_board_id, user_id=current_user.id).first()

    if not active_board and boards:
        active_board = boards[0]

    return render_template('kanban.html', boards=boards, active_board=active_board)


# ── Board CRUD ───────────────────────────────────────────────────

@kanban_bp.route('/kanban/boards', methods=['POST'])
@login_required
def create_board():
    data = request.get_json(silent=True) or {}
    name = _strip(data.get('name'), _LIMITS['board_name'])
    if not name:
        return jsonify({'error': 'Board name required'}), 400

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
    board = _board_or_404(board_id)
    return jsonify({
        'id': board.id,
        'name': board.name,
        'notify_start_enabled': board.notify_start_enabled or False,
        'notify_start_days': board.notify_start_days or 1,
        'notify_due_enabled': board.notify_due_enabled or False,
        'notify_due_days': board.notify_due_days or 1,
        'categories': [
            {'id': c.id, 'name': c.name, 'position': c.position}
            for c in board.categories
        ],
    })


@kanban_bp.route('/kanban/boards/<int:board_id>/settings', methods=['PUT'])
@login_required
def update_board_settings(board_id):
    board = _board_or_404(board_id)
    data = request.get_json(silent=True) or {}
    if 'name' in data:
        name = _strip(data['name'], _LIMITS['board_name'])
        if not name:
            return jsonify({'error': 'Board name required'}), 400
        board.name = name
    if 'notify_start_enabled' in data:
        board.notify_start_enabled = bool(data['notify_start_enabled'])
    if 'notify_start_days' in data:
        board.notify_start_days = max(1, min(365, int(data.get('notify_start_days') or 1)))
    if 'notify_due_enabled' in data:
        board.notify_due_enabled = bool(data['notify_due_enabled'])
    if 'notify_due_days' in data:
        board.notify_due_days = max(1, min(365, int(data.get('notify_due_days') or 1)))
    db.session.commit()
    return jsonify({'ok': True, 'name': board.name})


# ── Category CRUD ────────────────────────────────────────────────

@kanban_bp.route('/kanban/boards/<int:board_id>/categories', methods=['POST'])
@login_required
def create_category(board_id):
    board = _board_or_404(board_id)
    data = request.get_json(silent=True) or {}
    name = _strip(data.get('name'), _LIMITS['cat_name'])
    if not name:
        return jsonify({'error': 'Category name required'}), 400
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
    board = _board_or_404(board_id)
    data = request.get_json(silent=True) or {}
    title = _strip(data.get('title'), _LIMITS['card_title'])
    col_id = data.get('column_id')
    if not title:
        return jsonify({'error': 'Card title required'}), 400

    col = KanbanColumn.query.filter_by(id=col_id, board_id=board.id).first()
    if not col:
        return jsonify({'error': 'Invalid column'}), 400

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
    )
    db.session.add(card)
    db.session.commit()
    return jsonify(_card_to_dict(card)), 201


@kanban_bp.route('/kanban/cards/<int:card_id>', methods=['GET'])
@login_required
def get_card(card_id):
    card = _card_or_404(card_id)
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
    db.session.commit()
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
    for col_data in columns_data:
        col_id = col_data.get('column_id')
        card_ids = col_data.get('card_ids', [])
        col = KanbanColumn.query.get(col_id)
        if not col:
            continue
        _board_or_404(col.board_id)
        for pos, cid in enumerate(card_ids):
            KanbanCard.query.filter_by(id=cid, board_id=col.board_id).update(
                {'column_id': col_id, 'position': pos}
            )
    db.session.commit()
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
    max_pos = db.session.query(db.func.max(KanbanTask.position)).filter_by(card_id=card.id).scalar() or 0
    task = KanbanTask(
        card_id=card.id,
        title=title,
        start_date=start_date,
        due_date=due_date,
        position=max_pos + 1,
    )
    db.session.add(task)
    db.session.commit()
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
    db.session.commit()
    return jsonify(_task_to_dict(task))


@kanban_bp.route('/kanban/tasks/<int:task_id>', methods=['DELETE'])
@login_required
def delete_task(task_id):
    task = _task_or_404(task_id)
    db.session.delete(task)
    db.session.commit()
    return jsonify({'ok': True})


# ── Contacts ─────────────────────────────────────────────────────

@kanban_bp.route('/kanban/contacts', methods=['GET'])
@login_required
def kanban_contacts():
    if not current_user.has_permission('settings_sections.contacts', 'view_other'):
        return jsonify({'error': 'No permission'}), 403
    persons = ContactPerson.query.order_by(ContactPerson.name).all()
    result = []
    for p in persons:
        org_name = ''
        if p.organization_id:
            org = ContactOrganization.query.get(p.organization_id)
            if org:
                org_name = org.name
        result.append({'id': p.id, 'name': p.name, 'email': p.email or '', 'org': org_name})
    return jsonify(result)


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
