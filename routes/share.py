"""
Share Files Blueprint - Manages shared file library
"""
import io
import os
import uuid
import zipfile
from flask import Blueprint, render_template, redirect, url_for, flash, request, send_from_directory, current_app, jsonify, send_file
from flask_login import login_required, current_user
from werkzeug.utils import secure_filename
from models import db, SharedFile, Setting, User
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


def _share_folder(upload_folder: str, category: str) -> str:
    """Return the absolute path for uploads/share/<category>.

    The category is re-derived from the SHARE_CATEGORIES allowlist so the
    resulting path never contains raw user input, satisfying the
    py/path-injection rule. A realpath containment check is also performed as
    defence-in-depth against path traversal.
    """
    safe_cat = next((c for c in SHARE_CATEGORIES if c == category), None)
    if safe_cat is None:
        raise ValueError(f'Invalid share category: {category!r}')
    share_root = os.path.realpath(os.path.join(upload_folder, 'share'))
    folder = os.path.realpath(os.path.join(share_root, safe_cat))
    if not folder.startswith(share_root + os.sep):
        raise ValueError(f'Path traversal detected for category: {category!r}')
    return folder


def _share_file_path(upload_folder: str, category: str, filename: str) -> str:
    """Return the absolute path for a file inside uploads/share/<category>.

    Both category (allowlist lookup) and filename (secure_filename) are
    sanitised, and a realpath containment check guards against traversal.
    """
    folder = _share_folder(upload_folder, category)
    safe_name = secure_filename(filename)
    if not safe_name:
        raise ValueError(f'Invalid filename: {filename!r}')
    path = os.path.realpath(os.path.join(folder, safe_name))
    if not path.startswith(folder + os.sep):
        raise ValueError(f'Path traversal detected for filename: {filename!r}')
    return path


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

    files = request.files.getlist('files')
    category = request.form.get('category', '').strip()

    if not files or all(not f.filename for f in files):
        flash('No files selected.', 'danger')
        return redirect(url_for('share.share_files'))

    if category not in SHARE_CATEGORIES:
        flash('Invalid category.', 'danger')
        return redirect(url_for('share.share_files'))

    allowed_exts, max_bytes = get_share_config(category)
    try:
        share_folder = _share_folder(current_app.config['UPLOAD_FOLDER'], category)
    except ValueError:
        flash('Invalid category.', 'danger')
        return redirect(url_for('share.share_files'))
    os.makedirs(share_folder, exist_ok=True)

    uploaded = 0
    errors = []
    for file in files:
        if not file or not file.filename:
            continue

        ext = file.filename.rsplit('.', 1)[1].lower() if '.' in file.filename else ''
        if ext not in allowed_exts:
            errors.append(f'"{file.filename}": type .{ext} not allowed')
            continue

        file.seek(0, os.SEEK_END)
        file_size = file.tell()
        file.seek(0)

        if file_size > max_bytes:
            errors.append(f'"{file.filename}": exceeds {max_bytes // (1024 * 1024)} MB limit')
            continue

        safe_base = secure_filename(file.filename)
        stored_name = f"{uuid.uuid4().hex}_{safe_base}"
        file.save(os.path.join(share_folder, stored_name))

        sf = SharedFile(
            name=safe_base,
            filename=stored_name,
            category=category,
            file_size=file_size,
            uploaded_by_id=current_user.id,
        )
        db.session.add(sf)
        db.session.flush()
        log_audit(current_user.id, 'create', 'shared_file', sf.id, f'Uploaded shared file: {sf.name}')
        uploaded += 1

    db.session.commit()

    if uploaded:
        flash(f'{uploaded} file(s) uploaded successfully.', 'success')
    for err in errors:
        flash(err, 'danger')

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
        return redirect(url_for('share.share_files', category=sf.category))

    # Ensure extension is preserved
    orig_ext = sf.ext
    if '.' not in new_name:
        new_name_with_ext = f'{new_name}.{orig_ext}'
    else:
        new_name_with_ext = new_name
    new_filename = secure_filename(new_name_with_ext)
    if not new_filename:
        flash('Invalid file name.', 'danger')
        return redirect(url_for('share.share_files', category=sf.category))

    # Duplicate check (same category, different record)
    dup = SharedFile.query.filter(
        SharedFile.category == sf.category,
        SharedFile.filename == new_filename,
        SharedFile.id != sf.id
    ).first()
    if dup:
        flash(f'A file named "{new_filename}" already exists in {sf.category}. Choose a different name.', 'danger')
        return redirect(url_for('share.share_files', category=sf.category))

    # Rename on disk
    try:
        old_path = _share_file_path(current_app.config['UPLOAD_FOLDER'], sf.category, sf.filename)
        share_folder = os.path.dirname(old_path)
        new_path = os.path.join(share_folder, new_filename)
    except ValueError:
        flash('File path error.', 'danger')
        return redirect(url_for('share.share_files', category=sf.category))
    old_filename = sf.filename
    if os.path.exists(old_path) and old_path != new_path:
        os.rename(old_path, new_path)

    sf.filename = new_filename
    sf.name = new_name_with_ext

    # Update any profile_photo references that pointed to the old filename
    old_ref = f'share/{old_filename}'
    new_ref = f'share/{new_filename}'
    if old_ref != new_ref:
        for u in User.query.filter_by(profile_photo=old_ref).all():
            u.profile_photo = new_ref

    db.session.commit()
    log_audit(current_user.id, 'update', 'shared_file', id, f'Renamed shared file to: {new_filename}')
    flash(f'File renamed to "{new_filename}".', 'success')
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

    try:
        file_path = _share_file_path(current_app.config['UPLOAD_FOLDER'], sf.category, sf.filename)
        if os.path.exists(file_path):
            os.remove(file_path)
    except ValueError:
        pass  # File already gone or path invalid — proceed with DB deletion

    db.session.delete(sf)
    db.session.commit()
    log_audit(current_user.id, 'delete', 'shared_file', id, f'Deleted shared file: {name}')
    flash(f'File "{name}" deleted.', 'success')
    return redirect(url_for('share.share_files', category=category))


@share_bp.route('/settings/share-files/bulk-delete', endpoint='share_bulk_delete', methods=['POST'])
@login_required
def share_bulk_delete():
    if not current_user.has_permission('settings_sections.share_files', 'delete'):
        return jsonify({'success': False, 'error': 'No permission.'}), 403

    data = request.get_json(silent=True) or {}
    ids = data.get('ids', [])
    if not ids:
        return jsonify({'success': False, 'error': 'No files specified.'}), 400

    files = SharedFile.query.filter(SharedFile.id.in_(ids)).all()
    count = 0
    for sf in files:
        try:
            file_path = _share_file_path(current_app.config['UPLOAD_FOLDER'], sf.category, sf.filename)
            if os.path.exists(file_path):
                os.remove(file_path)
        except ValueError:
            pass  # Invalid path — skip file delete, still remove DB record
        log_audit(current_user.id, 'delete', 'shared_file', sf.id, f'Bulk deleted shared file: {sf.name}')
        db.session.delete(sf)
        count += 1

    db.session.commit()
    return jsonify({'success': True, 'deleted': count})


@share_bp.route('/settings/share-files/bulk-download', endpoint='share_bulk_download')
@login_required
def share_bulk_download():
    if not current_user.has_permission('settings_sections.share_files', 'view'):
        flash('No permission.', 'danger')
        return redirect(url_for('share.share_files'))

    ids_param = request.args.get('ids', '')
    try:
        ids = [int(i) for i in ids_param.split(',') if i.strip()]
    except ValueError:
        ids = []

    if not ids:
        flash('No files selected.', 'danger')
        return redirect(url_for('share.share_files'))

    files = SharedFile.query.filter(SharedFile.id.in_(ids)).all()
    if not files:
        flash('No files found.', 'danger')
        return redirect(url_for('share.share_files'))

    buf = io.BytesIO()
    seen_names = {}
    with zipfile.ZipFile(buf, 'w', zipfile.ZIP_DEFLATED) as zf:
        for sf in files:
            try:
                file_path = _share_file_path(current_app.config['UPLOAD_FOLDER'], sf.category, sf.filename)
            except ValueError:
                continue
            if not os.path.exists(file_path):
                continue
            # Use display name with extension, deduplicate if needed
            ext = sf.ext
            arc_name = sf.name if sf.name.lower().endswith(f'.{ext}') else f'{sf.name}.{ext}'
            if arc_name in seen_names:
                seen_names[arc_name] += 1
                base, dot_ext = arc_name.rsplit('.', 1)
                arc_name = f'{base}_{seen_names[arc_name]}.{dot_ext}'
            else:
                seen_names[arc_name] = 0
            zf.write(file_path, arc_name)

    buf.seek(0)
    return send_file(buf, as_attachment=True, download_name='share_files.zip', mimetype='application/zip')


@share_bp.route('/uploads/share/<category>/<path:filename>', endpoint='share_serve')
@login_required
def share_serve(category, filename):
    try:
        folder = _share_folder(current_app.config['UPLOAD_FOLDER'], category)
    except ValueError:
        from flask import abort
        abort(404)
    return send_from_directory(folder, filename)
