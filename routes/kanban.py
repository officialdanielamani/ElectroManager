"""
Kanban Routes Blueprint
"""
from flask import Blueprint, render_template, request, jsonify, abort
from flask_login import login_required, current_user
from models import (db, KanbanBoard, KanbanColumn, KanbanCard, KanbanTask,
                    DEFAULT_KANBAN_COLUMNS)
from datetime import datetime, timezone, date
import json
import logging

logger = logging.getLogger(__name__)

kanban_bp = Blueprint('kanban', __name__)


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


def _card_to_dict(card):
    return {
        'id': card.id,
        'title': card.title,
        'description': card.description or '',
        'priority': card.priority,
        'label_color': card.label_color or '',
        'label_name': card.label_name or '',
        'key_persons': card.get_key_persons(),
        'start_date': card.start_date.isoformat() if card.start_date else '',
        'due_date': card.due_date.isoformat() if card.due_date else '',
        'completed_at': card.completed_at.isoformat() if card.completed_at else '',
        'is_overdue': card.is_overdue,
        'position': card.position,
        'column_id': card.column_id,
        'task_count': card.task_count,
        'completed_task_count': card.completed_task_count,
        'tasks': [
            {
                'id': t.id,
                'title': t.title,
                'completed': t.completed,
                'due_date': t.due_date.isoformat() if t.due_date else '',
                'position': t.position,
            }
            for t in card.tasks
        ],
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
    name = (data.get('name') or '').strip()
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


@kanban_bp.route('/kanban/boards/<int:board_id>', methods=['PUT'])
@login_required
def update_board(board_id):
    board = _board_or_404(board_id)
    data = request.get_json(silent=True) or {}
    name = (data.get('name') or '').strip()
    if not name:
        return jsonify({'error': 'Board name required'}), 400
    board.name = name
    db.session.commit()
    return jsonify({'id': board.id, 'name': board.name})


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


# ── Column CRUD ──────────────────────────────────────────────────

@kanban_bp.route('/kanban/boards/<int:board_id>/columns', methods=['POST'])
@login_required
def create_column(board_id):
    board = _board_or_404(board_id)
    data = request.get_json(silent=True) or {}
    name = (data.get('name') or '').strip()
    if not name:
        return jsonify({'error': 'Column name required'}), 400

    max_pos = db.session.query(db.func.max(KanbanColumn.position)).filter_by(board_id=board.id).scalar() or 0
    col = KanbanColumn(
        board_id=board.id,
        name=name,
        color=data.get('color', '#6b7280'),
        icon=data.get('icon', 'bi-circle'),
        position=max_pos + 1,
    )
    db.session.add(col)
    db.session.commit()
    return jsonify({'id': col.id, 'name': col.name, 'color': col.color, 'icon': col.icon, 'position': col.position}), 201


@kanban_bp.route('/kanban/columns/<int:col_id>', methods=['PUT'])
@login_required
def update_column(col_id):
    col = _column_or_404(col_id)
    data = request.get_json(silent=True) or {}
    if 'name' in data:
        name = data['name'].strip()
        if not name:
            return jsonify({'error': 'Column name required'}), 400
        col.name = name
    if 'color' in data:
        col.color = data['color']
    if 'icon' in data:
        col.icon = data['icon']
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
    title = (data.get('title') or '').strip()
    col_id = data.get('column_id')
    if not title:
        return jsonify({'error': 'Card title required'}), 400

    col = KanbanColumn.query.filter_by(id=col_id, board_id=board.id).first()
    if not col:
        return jsonify({'error': 'Invalid column'}), 400

    max_pos = db.session.query(db.func.max(KanbanCard.position)).filter_by(column_id=col.id).scalar() or 0
    card = KanbanCard(
        board_id=board.id,
        column_id=col.id,
        title=title,
        description=data.get('description', ''),
        priority=int(data.get('priority', 1)),
        label_color=data.get('label_color', ''),
        label_name=data.get('label_name', ''),
        key_persons=json.dumps(data.get('key_persons', [])),
        start_date=_parse_date(data.get('start_date')),
        due_date=_parse_date(data.get('due_date')),
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
        title = data['title'].strip()
        if not title:
            return jsonify({'error': 'Title required'}), 400
        card.title = title
    if 'description' in data:
        card.description = data['description']
    if 'priority' in data:
        card.priority = int(data['priority'])
    if 'label_color' in data:
        card.label_color = data['label_color']
    if 'label_name' in data:
        card.label_name = data['label_name']
    if 'key_persons' in data:
        card.key_persons = json.dumps(data['key_persons'])
    if 'start_date' in data:
        card.start_date = _parse_date(data['start_date'])
    if 'due_date' in data:
        card.due_date = _parse_date(data['due_date'])
    if 'completed_at' in data:
        val = data['completed_at']
        card.completed_at = datetime.now(timezone.utc) if val else None
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


@kanban_bp.route('/kanban/cards/<int:card_id>/move', methods=['POST'])
@login_required
def move_card(card_id):
    card = _card_or_404(card_id)
    data = request.get_json(silent=True) or {}
    col_id = data.get('column_id')
    position = data.get('position', 0)

    col = KanbanColumn.query.filter_by(id=col_id, board_id=card.board_id).first()
    if not col:
        return jsonify({'error': 'Invalid column'}), 400

    card.column_id = col.id
    card.position = position
    card.updated_at = datetime.now(timezone.utc)
    db.session.commit()
    return jsonify({'ok': True})


@kanban_bp.route('/kanban/cards/reorder', methods=['POST'])
@login_required
def reorder_cards():
    data = request.get_json(silent=True) or {}
    # [{column_id, card_ids: [...]}, ...]
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
    title = (data.get('title') or '').strip()
    if not title:
        return jsonify({'error': 'Task title required'}), 400

    max_pos = db.session.query(db.func.max(KanbanTask.position)).filter_by(card_id=card.id).scalar() or 0
    task = KanbanTask(
        card_id=card.id,
        title=title,
        due_date=_parse_date(data.get('due_date')),
        position=max_pos + 1,
    )
    db.session.add(task)
    db.session.commit()
    return jsonify({
        'id': task.id,
        'title': task.title,
        'completed': task.completed,
        'due_date': task.due_date.isoformat() if task.due_date else '',
        'position': task.position,
    }), 201


@kanban_bp.route('/kanban/tasks/<int:task_id>', methods=['PUT'])
@login_required
def update_task(task_id):
    task = _task_or_404(task_id)
    data = request.get_json(silent=True) or {}
    if 'title' in data:
        title = data['title'].strip()
        if not title:
            return jsonify({'error': 'Task title required'}), 400
        task.title = title
    if 'completed' in data:
        task.completed = bool(data['completed'])
    if 'due_date' in data:
        task.due_date = _parse_date(data['due_date'])
    db.session.commit()
    return jsonify({
        'id': task.id,
        'title': task.title,
        'completed': task.completed,
        'due_date': task.due_date.isoformat() if task.due_date else '',
    })


@kanban_bp.route('/kanban/tasks/<int:task_id>', methods=['DELETE'])
@login_required
def delete_task(task_id):
    task = _task_or_404(task_id)
    db.session.delete(task)
    db.session.commit()
    return jsonify({'ok': True})


# ── Helper ───────────────────────────────────────────────────────

def _parse_date(val):
    if not val:
        return None
    try:
        return date.fromisoformat(str(val))
    except (ValueError, TypeError):
        return None
