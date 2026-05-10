from flask import Blueprint, render_template, abort
from flask_login import login_required, current_user
from models import db, AuditLog, User

in_out_bp = Blueprint('in_out', __name__)


@in_out_bp.route('/in-out')
@login_required
def in_out():
    if not current_user.has_permission('lending_return', 'view_page') and not current_user.is_admin():
        abort(403)

    # Query recent batch-related audit logs
    logs = AuditLog.query.filter(
        AuditLog.entity_type.in_(['batch', 'item'])
    ).order_by(AuditLog.timestamp.desc()).limit(100).all()

    # Attach user display and item info to logs
    log_data = []
    for log in logs:
        user = User.query.get(log.user_id)
        log_data.append({
            'log': log,
            'username': user.username if user else 'Unknown',
            'timestamp': log.timestamp.strftime('%d/%m/%Y %H:%M') if log.timestamp else '?',
        })

    can_view_log = current_user.is_admin() or current_user.has_permission('lending_return', 'view_log')
    return render_template('in_out.html', log_data=log_data, can_view_log=can_view_log)
