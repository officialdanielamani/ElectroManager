"""
Share Files Blueprint - Manages shared file library
"""
import os
import uuid
from flask import Blueprint, render_template, redirect, url_for, flash, request, send_from_directory, current_app
from flask_login import login_required, current_user
from werkzeug.utils import secure_filename
from models import db, SharedFile, Setting
from utils import log_audit

share_bp = Blueprint('share', __name__)

SHARE_CATEGORIES = ['item', 'profile', 'project', 'sticker']
IMAGE_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'webp', 'svg'}

CATEGORY_DEFAULTS = {
    'item':    {'extensions': 'pdf,png,jpg,jpeg,gif,txt,doc,docx', 'max_size': '10'},
    'profile': {'extensions': 'jpg,jpeg,png',                      'max_size': '1'},
    'project': {'extensions': 'pdf,png,jpg,jpeg,gif,txt,doc,docx', 'max_size': '10'},
    'sticker': {'extensions': 'png,jpg,jpeg',                      'max_size': '1'},
}

PROFILE_FIXED = True  # profile limits are not configurable


def get_share_config(category):
    """Return (allowed_ext_set, max_bytes) for the given category."""
    if category == 'profile':
        return {'jpg', 'jpeg', 'png'}, 1 * 1024 * 1024
    d = CATEGORY_DEFAULTS.get(category, CATEGORY_DEFAULTS['item'])
    ext_str = Setting.get(f'share_{category}_extensions', d['extensions'])
    size_mb_str = Setting.get(f'share_{category}_max_size', d['max_size'])
    try:
        size_mb = int(size_mb_str)
    except (ValueError, TypeError):
        size_mb = int(d['max_size'])
    exts = {e.strip().lower() for e in ext_str.split(',') if e.strip()}
    return exts, size_mb * 1024 * 1024


@share_bp.route('/settings/share-files', endpoint='share_files')
@login_required
def share_files():
    if not current_user.has_permission('settings_sections.share_files', 'view'):
        flash('No permission.', 'danger')
        return redirect(url_for('settings.settings'))

    category_filter = request.args.get('category', '')
    view_mode = request.args.get('view', 'card')

    query = SharedFile.query
    if category_filter in SHARE_CATEGORIES:
        query = query.filter_by(category=category_filter)
    files = query.order_by(SharedFile.created_at.desc()).all()

    can_add = current_user.has_permission('settings_sections.share_files', 'add')
    can_edit = current_user.has_permission('settings_sections.share_files', 'edit')
    can_delete = current_user.has_permission('settings_sections.share_files', 'delete')

    # Counts per category for tabs
    counts = {}
    for cat in SHARE_CATEGORIES:
        counts[cat] = SharedFile.query.filter_by(category=cat).count()

    # Build display strings for upload hints
    share_ext = {}
    share_size = {}
    for cat in SHARE_CATEGORIES:
        exts, max_b = get_share_config(cat)
        share_ext[cat] = ', '.join(sorted(exts))
        share_size[cat] = str(max_b // (1024 * 1024))

    return render_template('share_files.html',
                           files=files,
                           categories=SHARE_CATEGORIES,
                           category_filter=category_filter,
                           view_mode=view_mode,
                           can_add=can_add, can_edit=can_edit, can_delete=can_delete,
                           counts=counts,
                           share_ext=share_ext,
                           share_size=share_size)


@share_bp.route('/settings/share-files/upload', endpoint='share_upload', methods=['POST'])
@login_required
def share_upload():
    if not current_user.has_permission('settings_sections.share_files', 'add'):
        flash('No permission.', 'danger')
        return redirect(url_for('share.share_files'))

    file = request.files.get('file')
    category = request.form.get('category', '').strip()
    display_name = request.form.get('name', '').strip()

    if not file or not file.filename:
        flash('No file selected.', 'danger')
        return redirect(url_for('share.share_files'))

    if category not in SHARE_CATEGORIES:
        flash('Invalid category.', 'danger')
        return redirect(url_for('share.share_files'))

    ext = file.filename.rsplit('.', 1)[1].lower() if '.' in file.filename else ''
    allowed_exts, max_bytes = get_share_config(category)

    if ext not in allowed_exts:
        flash(f'File type .{ext} is not allowed for {category}. Allowed: {", ".join(sorted(allowed_exts))}', 'danger')
        return redirect(url_for('share.share_files', category=category))

    file.seek(0, os.SEEK_END)
    file_size = file.tell()
    file.seek(0)

    if file_size > max_bytes:
        flash(f'File too large. Maximum size for {category} is {max_bytes // (1024 * 1024)} MB.', 'danger')
        return redirect(url_for('share.share_files', category=category))

    share_folder = os.path.join(current_app.config['UPLOAD_FOLDER'], 'share', category)
    os.makedirs(share_folder, exist_ok=True)

    safe_base = secure_filename(file.filename)
    stored_name = f"{uuid.uuid4().hex}_{safe_base}"
    file.save(os.path.join(share_folder, stored_name))

    sf = SharedFile(
        name=display_name or safe_base,
        filename=stored_name,
        category=category,
        file_size=file_size,
        uploaded_by_id=current_user.id,
    )
    db.session.add(sf)
    db.session.commit()

    log_audit(current_user.id, 'create', 'shared_file', sf.id, f'Uploaded shared file: {sf.name}')
    flash(f'File "{sf.name}" uploaded successfully.', 'success')
    return redirect(url_for('share.share_files', category=category))


@share_bp.route('/settings/share-files/<int:id>/rename', endpoint='share_rename', methods=['POST'])
@login_required
def share_rename(id):
    if not current_user.has_permission('settings_sections.share_files', 'edit'):
        flash('No permission.', 'danger')
        return redirect(url_for('share.share_files'))

    sf = SharedFile.query.get_or_404(id)
    new_name = request.form.get('name', '').strip()
    if not new_name:
        flash('Name cannot be empty.', 'danger')
        return redirect(url_for('share.share_files'))

    sf.name = new_name
    db.session.commit()
    log_audit(current_user.id, 'update', 'shared_file', id, f'Renamed shared file to: {new_name}')
    flash('File renamed.', 'success')
    return redirect(url_for('share.share_files', category=sf.category))


@share_bp.route('/settings/share-files/<int:id>/delete', endpoint='share_delete', methods=['POST'])
@login_required
def share_delete(id):
    if not current_user.has_permission('settings_sections.share_files', 'delete'):
        flash('No permission.', 'danger')
        return redirect(url_for('share.share_files'))

    sf = SharedFile.query.get_or_404(id)
    name = sf.name
    category = sf.category

    file_path = os.path.join(current_app.config['UPLOAD_FOLDER'], 'share', sf.category, sf.filename)
    if os.path.exists(file_path):
        os.remove(file_path)

    db.session.delete(sf)
    db.session.commit()
    log_audit(current_user.id, 'delete', 'shared_file', id, f'Deleted shared file: {name}')
    flash(f'File "{name}" deleted.', 'success')
    return redirect(url_for('share.share_files', category=category))


@share_bp.route('/uploads/share/<category>/<path:filename>', endpoint='share_serve')
@login_required
def share_serve(category, filename):
    if category not in SHARE_CATEGORIES:
        from flask import abort
        abort(404)
    folder = os.path.join(current_app.config['UPLOAD_FOLDER'], 'share', category)
    return send_from_directory(folder, filename)
