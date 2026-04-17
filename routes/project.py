"""
Project Routes Blueprint
"""
from flask import Blueprint, render_template, redirect, url_for, flash, request, jsonify, current_app, abort
from flask_login import login_required, current_user
from models import (db, User, Item, ItemBatch, BatchSerialNumber, Setting,
                    Project, ProjectCategory, ProjectTag, ProjectStatus, ProjectPerson,
                    ProjectGroup, ProjectGroupMember, ProjectBOMItem, ProjectAttachment, ProjectURL)
from utils import log_audit, permission_required, allowed_file
from werkzeug.utils import secure_filename
from datetime import datetime, timezone
import os
import re
import json
import secrets
import string
import logging

logger = logging.getLogger(__name__)

project_bp = Blueprint('project', __name__)

_SAFE_PROJECT_ID_RE = re.compile(r'^[A-Za-z0-9._-]+$')
_ALLOWED_ATTACHMENT_TYPES = {'picture', 'document', 'schematic', '2d_design', '3d_design'}


# ==================== HELPERS ====================

def get_project_file_settings(attachment_type):
    """Get allowed extensions and max size for a project attachment type"""
    defaults = {
        'picture': ('webp,png,svg,jpeg,jpg', '10'),
        'document': ('txt,doc,docx,pdf', '10'),
        'schematic': ('pdf,zip', '20'),
        '2d_design': ('pdf,zip', '20'),
        '3d_design': ('pdf,zip,stl,step', '50'),
    }
    default_ext, default_size = defaults.get(attachment_type, ('pdf,zip', '10'))
    ext_str = Setting.get(f'project_upload_{attachment_type}_extensions', default_ext)
    max_size = Setting.get(f'project_upload_{attachment_type}_max_size', default_size)
    extensions = set(ext.strip().lower() for ext in ext_str.split(',') if ext.strip())
    try:
        max_size = int(max_size)
    except (ValueError, TypeError):
        max_size = 10
    return extensions, max_size


def save_project_file(file, project_id_str, attachment_type):
    """Save uploaded file for a project"""
    if not file or not file.filename:
        return None, None

    if attachment_type not in _ALLOWED_ATTACHMENT_TYPES:
        return None, 'Invalid attachment type.'
    if not project_id_str or not _SAFE_PROJECT_ID_RE.match(str(project_id_str)):
        return None, 'Invalid project id.'

    allowed_ext, max_size_mb = get_project_file_settings(attachment_type)
    filename = secure_filename(file.filename)
    if not filename:
        return None, 'Invalid filename.'
    ext = filename.rsplit('.', 1)[1].lower() if '.' in filename else ''

    if ext not in allowed_ext:
        return None, f'File type .{ext} not allowed for {attachment_type}. Allowed: {", ".join(allowed_ext)}'

    file.seek(0, os.SEEK_END)
    file_size = file.tell()
    file.seek(0)

    if file_size > max_size_mb * 1024 * 1024:
        return None, f'File too large. Max {max_size_mb}MB for {attachment_type}'

    upload_root = os.path.abspath(current_app.config['UPLOAD_FOLDER'])
    folder = os.path.abspath(os.path.join(upload_root, 'projects', project_id_str, attachment_type))
    if not folder.startswith(upload_root + os.sep) and folder != upload_root:
        return None, 'Invalid upload path.'
    os.makedirs(folder, exist_ok=True)

    file_path = os.path.join(folder, filename)
    counter = 1
    base_name = filename.rsplit('.', 1)[0] if '.' in filename else filename
    while os.path.exists(file_path):
        new_filename = f"{base_name}_{counter}.{ext}"
        file_path = os.path.join(folder, new_filename)
        filename = new_filename
        counter += 1

    file.save(file_path)
    rel_path = os.path.relpath(file_path, upload_root)
    return {'filename': filename, 'original_filename': file.filename if hasattr(file, 'filename') else filename,
            'file_path': rel_path, 'file_type': ext, 'file_size': file_size}, None


# ==================== PROJECT LIST ====================

@project_bp.route('/projects', endpoint='projects')
@login_required
def projects():
    if not current_user.has_permission('projects', 'view'):
        flash('You do not have permission to view projects.', 'danger')
        return redirect(url_for('index'))

    search_query = request.args.get('search', '')
    category_id = request.args.get('category', 0, type=int)
    status_id = request.args.get('status', 0, type=int)
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 25, type=int)
    if per_page > 999999:
        per_page = 999999

    query = Project.query

    if search_query:
        query = query.filter(
            db.or_(
                Project.name.ilike(f'%{search_query}%'),
                Project.info.ilike(f'%{search_query}%'),
                Project.project_id.ilike(f'%{search_query}%')
            )
        )
    if category_id > 0:
        query = query.filter_by(category_id=category_id)
    if status_id > 0:
        query = query.filter_by(status_id=status_id)

    query = query.order_by(Project.updated_at.desc())
    pagination = query.paginate(page=page, per_page=per_page, error_out=False)
    project_list = pagination.items

    total_projects = Project.query.count()
    categories = ProjectCategory.query.order_by(ProjectCategory.name).all()
    statuses = ProjectStatus.query.order_by(ProjectStatus.name).all()

    # Stats cards
    active_count = Project.query.join(ProjectStatus).filter(ProjectStatus.name.ilike('%active%')).count() if ProjectStatus.query.first() else 0
    completed_count = Project.query.join(ProjectStatus).filter(ProjectStatus.name.ilike('%completed%')).count() if ProjectStatus.query.first() else 0
    overdue_count = Project.query.filter(Project.date_end < datetime.now(timezone.utc).date(), Project.date_end.isnot(None)).count()

    user_columns = current_user.get_project_table_columns()
    currency = Setting.get('currency', 'USD')
    currency_decimal = int(Setting.get('currency_decimal_places', '2'))

    return render_template('projects.html',
                           projects=project_list,
                           pagination=pagination,
                           total_projects=total_projects,
                           active_count=active_count,
                           completed_count=completed_count,
                           overdue_count=overdue_count,
                           categories=categories,
                           statuses=statuses,
                           search_query=search_query,
                           category_id=category_id,
                           status_id=status_id,
                           user_columns=user_columns,
                           per_page=per_page,
                           currency=currency,
                           currency_decimal=currency_decimal)


# ==================== ADD PROJECT ====================

@project_bp.route('/project/new', endpoint='project_new', methods=['GET', 'POST'])
@login_required
def project_new():
    if not current_user.has_permission('projects', 'create'):
        flash('You do not have permission to create projects.', 'danger')
        return redirect(url_for('project.projects'))

    categories = ProjectCategory.query.order_by(ProjectCategory.name).all()
    tags = ProjectTag.query.order_by(ProjectTag.name).all()
    statuses = ProjectStatus.query.order_by(ProjectStatus.name).all()
    users = User.query.filter_by(is_active=True).order_by(User.username).all()
    groups = ProjectGroup.query.order_by(ProjectGroup.name).all()

    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        if not name:
            flash('Project name is required.', 'danger')
            return render_template('project_form.html', title='New Project', project=None,
                                   categories=categories, tags=tags, statuses=statuses, users=users, groups=groups)

        project = Project(
            name=name,
            info=request.form.get('info', '').strip(),
            category_id=request.form.get('category_id', type=int) or None,
            status_id=request.form.get('status_id', type=int) or None,
            group_id=request.form.get('group_id', type=int) or None,
            quantity=request.form.get('quantity', 1, type=int),
            created_by=current_user.id,
            updated_by=current_user.id
        )

        # Tags
        selected_tags = request.form.getlist('tags')
        if selected_tags:
            project.tags = json.dumps([int(t) for t in selected_tags])

        # Users
        selected_users = request.form.getlist('users')
        if selected_users:
            project.users = json.dumps([int(u) for u in selected_users])

        # Dates
        date_start = request.form.get('date_start')
        if date_start:
            try:
                project.date_start = datetime.strptime(date_start, '%Y-%m-%d').date()
            except ValueError:
                pass
        date_end = request.form.get('date_end')
        if date_end:
            try:
                project.date_end = datetime.strptime(date_end, '%Y-%m-%d').date()
            except ValueError:
                pass

        db.session.add(project)
        db.session.commit()

        log_audit(current_user.id, 'create', 'project', project.id, f'Created project: {project.name}')
        flash(f'Project "{project.name}" created successfully!', 'success')
        return redirect(url_for('project.project_detail', project_id=project.project_id))

    return render_template('project_form.html', title='New Project', project=None,
                           categories=categories, tags=tags, statuses=statuses, users=users, groups=groups)


# ==================== PROJECT DETAIL ====================

@project_bp.route('/project/<project_id>', endpoint='project_detail')
@login_required
def project_detail(project_id):
    if not current_user.has_permission('projects', 'view'):
        flash('You do not have permission to view projects.', 'danger')
        return redirect(url_for('project.projects'))

    project = Project.query.filter_by(project_id=project_id).first_or_404()
    currency = Setting.get('currency', 'USD')
    currency_decimal = int(Setting.get('currency_decimal_places', '2'))

    # BOM items
    bom_items = ProjectBOMItem.query.filter_by(project_id=project.id).all()

    # Attachments by type
    attachments = {}
    for atype in ['picture', 'document', 'schematic', '2d_design', '3d_design']:
        attachments[atype] = ProjectAttachment.query.filter_by(project_id=project.id, attachment_type=atype).all()

    can_edit = current_user.has_permission('projects', 'edit')
    can_delete = current_user.has_permission('projects', 'delete')

    return render_template('project_detail.html',
                           project=project,
                           bom_items=bom_items,
                           attachments=attachments,
                           currency=currency,
                           currency_decimal=currency_decimal,
                           can_edit=can_edit,
                           can_delete=can_delete)


# ==================== EDIT PROJECT ====================

@project_bp.route('/project/<project_id>/edit', endpoint='project_edit', methods=['GET', 'POST'])
@login_required
def project_edit(project_id):
    if not current_user.has_permission('projects', 'edit'):
        flash('You do not have permission to edit projects.', 'danger')
        return redirect(url_for('project.projects'))

    project = Project.query.filter_by(project_id=project_id).first_or_404()
    categories = ProjectCategory.query.order_by(ProjectCategory.name).all()
    tags = ProjectTag.query.order_by(ProjectTag.name).all()
    statuses = ProjectStatus.query.order_by(ProjectStatus.name).all()
    users = User.query.filter_by(is_active=True).order_by(User.username).all()
    groups = ProjectGroup.query.order_by(ProjectGroup.name).all()

    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        if not name:
            flash('Project name is required.', 'danger')
            return redirect(url_for('project.project_edit', project_id=project_id))

        project.name = name
        project.info = request.form.get('info', '').strip()
        project.description = request.form.get('description', '').strip()
        project.category_id = request.form.get('category_id', type=int) or None
        project.status_id = request.form.get('status_id', type=int) or None
        project.group_id = request.form.get('group_id', type=int) or None
        project.quantity = request.form.get('quantity', 1, type=int)
        project.updated_by = current_user.id

        project.enable_dateline_notification = 'enable_dateline_notification' in request.form
        project.notify_before_days = request.form.get('notify_before_days', 3, type=int)

        selected_tags = request.form.getlist('tags')
        project.tags = json.dumps([int(t) for t in selected_tags]) if selected_tags else None

        selected_users = request.form.getlist('users')
        project.users = json.dumps([int(u) for u in selected_users]) if selected_users else None

        date_start = request.form.get('date_start')
        project.date_start = datetime.strptime(date_start, '%Y-%m-%d').date() if date_start else None
        date_end = request.form.get('date_end')
        project.date_end = datetime.strptime(date_end, '%Y-%m-%d').date() if date_end else None

        db.session.commit()
        log_audit(current_user.id, 'update', 'project', project.id, f'Updated project: {project.name}')
        flash(f'Project "{project.name}" updated!', 'success')
        return redirect(url_for('project.project_detail', project_id=project.project_id))

    return render_template('project_form.html', title='Edit Project', project=project,
                           categories=categories, tags=tags, statuses=statuses, users=users, groups=groups,
                           bom_items=ProjectBOMItem.query.filter_by(project_id=project.id).all(),
                           attachments={atype: ProjectAttachment.query.filter_by(project_id=project.id, attachment_type=atype).all() for atype in ['picture', 'document', 'schematic', '2d_design', '3d_design']},
                           currency=Setting.get('currency', 'USD'),
                           currency_decimal=int(Setting.get('currency_decimal_places', '2')))


# ==================== DELETE PROJECT ====================

@project_bp.route('/project/<project_id>/delete', endpoint='project_delete', methods=['POST'])
@login_required
def project_delete(project_id):
    if not current_user.has_permission('projects', 'delete'):
        return jsonify({'error': 'No permission'}), 403

    from werkzeug.security import check_password_hash
    data = request.get_json() if request.is_json else {}
    password = (data or {}).get('password', '')
    if not password or not current_user.check_password(password):
        return jsonify({'success': False, 'message': 'Incorrect password.'}), 401

    project = Project.query.filter_by(project_id=project_id).first_or_404()
    name = project.name
    db.session.delete(project)
    db.session.commit()
    log_audit(current_user.id, 'delete', 'project', 0, f'Deleted project: {name}')
    return jsonify({'success': True, 'redirect': url_for('project.projects')})


# ==================== BOM MANAGEMENT ====================

@project_bp.route('/project/<project_id>/bom/search-items', endpoint='bom_search_items')
@login_required
def bom_search_items(project_id):
    """API: Search items for BOM. Returns batches with available qty info (no SN lists - those are for used_qty editor)."""
    project = Project.query.filter_by(project_id=project_id).first_or_404()
    search = request.args.get('q', '')
    category_id = request.args.get('category', 0, type=int)

    query = Item.query
    if search:
        query = query.filter(db.or_(Item.name.ilike(f'%{search}%'), Item.sku.ilike(f'%{search}%')))
    if category_id > 0:
        query = query.filter_by(category_id=category_id)
    items = query.limit(20).all()

    result = []
    for item in items:
        batches = []
        for b in item.batches:
            batches.append({
                'id': b.id,
                'label': b.get_display_label(),
                'quantity': b.quantity,
                'available': b.get_available_quantity(),
                'price': b.price_per_unit,
                'sn_tracking': b.sn_tracking_enabled,
            })
        result.append({
            'id': item.id,
            'name': item.name,
            'uuid': item.uuid,
            'category': item.category.name if item.category else '',
            'batches': batches
        })
    return jsonify(result)


@project_bp.route('/project/<project_id>/bom/<int:bom_id>/available-sns', endpoint='bom_available_sns')
@login_required
def bom_available_sns(project_id, bom_id):
    """API: Return available SNs for the batch of a BOM entry (for used_qty SN selection)."""
    bom = ProjectBOMItem.query.get_or_404(bom_id)
    if not bom.batch or not bom.batch.sn_tracking_enabled:
        return jsonify([])
    batch = bom.batch
    used_sn_ids = batch.get_project_used_sn_ids()
    # Include SNs already assigned to THIS bom entry so they show as selectable
    own_sn_ids = set()
    if bom.serial_numbers:
        try:
            own_sn_ids = set(json.loads(bom.serial_numbers))
        except (json.JSONDecodeError, TypeError):
            pass
    sns = []
    for sn in batch.serial_numbers:
        is_lent = bool(sn.lend_to and sn.lend_to.strip())
        is_used_elsewhere = sn.id in used_sn_ids and sn.id not in own_sn_ids
        if not is_lent and not is_used_elsewhere:
            sns.append({
                'id': sn.id,
                'isn': sn.internal_serial_number,
                'sn': sn.serial_number or '',
                'selected': sn.id in own_sn_ids,
            })
    return jsonify(sns)


@project_bp.route('/project/<project_id>/bom/add', endpoint='bom_add', methods=['POST'])
@login_required
def bom_add(project_id):
    if not current_user.has_permission('projects', 'edit'):
        return jsonify({'error': 'No permission'}), 403

    project = Project.query.filter_by(project_id=project_id).first_or_404()
    data = request.get_json() if request.is_json else None
    if not data:
        return jsonify({'error': 'Invalid request'}), 400

    item_id = data.get('item_id')
    batch_id = data.get('batch_id')
    quantity = max(1, int(data.get('quantity', 1)))  # required_quantity, no cap

    item = Item.query.get(item_id)
    if not item:
        return jsonify({'error': 'Item not found'}), 404

    # Merge with existing BOM entry for same item+batch, otherwise create new
    existing = ProjectBOMItem.query.filter_by(
        project_id=project.id, item_id=item_id, batch_id=batch_id
    ).first()
    if existing:
        existing.quantity += quantity
        db.session.commit()
        return jsonify({'success': True, 'id': existing.id})

    bom = ProjectBOMItem(
        project_id=project.id,
        item_id=item_id,
        batch_id=batch_id,
        quantity=quantity,
        used_quantity=0,
        item_name_snapshot=item.name,
    )
    db.session.add(bom)
    db.session.commit()
    log_audit(current_user.id, 'create', 'project_bom', bom.id,
              f'Added BOM item {item.name} to project {project.name}')
    return jsonify({'success': True, 'id': bom.id})


@project_bp.route('/project/<project_id>/bom/<int:bom_id>/edit', endpoint='bom_edit', methods=['POST'])
@login_required
def bom_edit(project_id, bom_id):
    if not current_user.has_permission('projects', 'edit'):
        return jsonify({'error': 'No permission'}), 403

    bom = ProjectBOMItem.query.get_or_404(bom_id)
    data = request.get_json() if request.is_json else None
    if not data:
        return jsonify({'error': 'Invalid request'}), 400

    # Change item/batch
    if 'item_id' in data and data['item_id'] != bom.item_id:
        new_item = Item.query.get(data['item_id'])
        if new_item:
            bom.item_id = data['item_id']
            bom.item_name_snapshot = new_item.name
            bom.used_quantity = 0
            bom.serial_numbers = None
    if 'batch_id' in data and data['batch_id'] != bom.batch_id:
        bom.batch_id = data['batch_id']
        bom.used_quantity = 0
        bom.serial_numbers = None

    # Update required quantity (no cap)
    if 'quantity' in data:
        bom.quantity = max(1, int(data['quantity']))

    # Update used quantity (validated against available stock)
    if 'used_quantity' in data:
        new_used = max(0, int(data['used_quantity']))
        if bom.batch:
            available = bom.batch.get_available_quantity() + (bom.used_quantity or 0)
            new_used = min(new_used, available)
        bom.used_quantity = new_used
        # Handle SN assignment for used_quantity
        if 'serial_number_ids' in data:
            sn_ids = data['serial_number_ids'] or []
            bom.serial_numbers = json.dumps(sn_ids) if sn_ids else None
            bom.used_quantity = len(sn_ids)
        elif new_used == 0:
            bom.serial_numbers = None

    db.session.commit()
    log_audit(current_user.id, 'update', 'project_bom', bom.id, 'Edited BOM item in project')
    return jsonify({'success': True})


@project_bp.route('/project/<project_id>/bom/<int:bom_id>/delete', endpoint='bom_delete', methods=['POST'])
@login_required
def bom_delete(project_id, bom_id):
    if not current_user.has_permission('projects', 'edit'):
        return jsonify({'error': 'No permission'}), 403

    bom = ProjectBOMItem.query.get_or_404(bom_id)
    db.session.delete(bom)
    db.session.commit()
    return jsonify({'success': True})


# ==================== PROJECT ATTACHMENTS ====================

@project_bp.route('/project/<project_id>/upload/<attachment_type>', endpoint='project_upload', methods=['POST'])
@login_required
def project_upload(project_id, attachment_type):
    if not current_user.has_permission('projects', 'edit'):
        flash('No permission.', 'danger')
        return redirect(url_for('project.project_detail', project_id=project_id))

    valid_types = ['picture', 'document', 'schematic', '2d_design', '3d_design']
    if attachment_type not in valid_types:
        flash('Invalid attachment type.', 'danger')
        return redirect(url_for('project.project_detail', project_id=project_id))

    project = Project.query.filter_by(project_id=project_id).first_or_404()

    files = request.files.getlist('files')
    uploaded = 0
    for file in files:
        if not file or not file.filename:
            continue
        result, error = save_project_file(file, project.project_id, attachment_type)
        if error:
            flash(error, 'danger')
            continue
        att = ProjectAttachment(
            project_id=project.id,
            filename=result['filename'],
            original_filename=result['original_filename'],
            file_path=result['file_path'],
            file_type=result['file_type'],
            file_size=result['file_size'],
            attachment_type=attachment_type,
            uploaded_by=current_user.id
        )
        db.session.add(att)
        uploaded += 1

    if uploaded:
        db.session.commit()
        flash(f'{uploaded} file(s) uploaded.', 'success')

    return redirect(url_for('project.project_detail', project_id=project_id))


@project_bp.route('/project/attachment/<int:att_id>/delete', endpoint='project_attachment_delete', methods=['POST'])
@login_required
def project_attachment_delete(att_id):
    if not current_user.has_permission('projects', 'edit'):
        return jsonify({'error': 'No permission'}), 403

    att = ProjectAttachment.query.get_or_404(att_id)
    project = att.project

    # Delete file
    full_path = os.path.join(current_app.config['UPLOAD_FOLDER'], att.file_path)
    if os.path.exists(full_path):
        os.remove(full_path)

    db.session.delete(att)
    db.session.commit()
    flash('Attachment deleted.', 'success')
    return redirect(url_for('project.project_detail', project_id=project.project_id))


# ==================== PROJECT URLS ====================

@project_bp.route('/project/<project_id>/url/add', endpoint='project_url_add', methods=['POST'])
@login_required
def project_url_add(project_id):
    if not current_user.has_permission('projects', 'edit'):
        flash('No permission.', 'danger')
        return redirect(url_for('project.project_detail', project_id=project_id))

    project = Project.query.filter_by(project_id=project_id).first_or_404()
    url_val = request.form.get('url', '').strip()
    if not url_val:
        flash('URL is required.', 'danger')
        return redirect(url_for('project.project_detail', project_id=project_id))

    purl = ProjectURL(
        project_id=project.id,
        url=url_val,
        title=request.form.get('title', '').strip() or None,
        description=request.form.get('url_description', '').strip() or None
    )
    db.session.add(purl)
    db.session.commit()
    flash('URL added.', 'success')
    return redirect(url_for('project.project_detail', project_id=project_id))


@project_bp.route('/project/url/<int:url_id>/delete', endpoint='project_url_delete', methods=['POST'])
@login_required
def project_url_delete(url_id):
    if not current_user.has_permission('projects', 'edit'):
        return jsonify({'error': 'No permission'}), 403

    purl = ProjectURL.query.get_or_404(url_id)
    project = purl.project
    db.session.delete(purl)
    db.session.commit()
    flash('URL removed.', 'success')
    return redirect(url_for('project.project_detail', project_id=project.project_id))


# ==================== PROJECT SETTINGS (Categories, Tags, Status, Groups, Persons) ====================

@project_bp.route('/settings/project', endpoint='project_settings')
@login_required
def project_settings():
    if not current_user.has_permission('settings_sections.project_settings', 'view'):
        flash('No permission.', 'danger')
        return redirect(url_for('settings.settings'))

    categories = ProjectCategory.query.order_by(ProjectCategory.name).all()
    tags = ProjectTag.query.order_by(ProjectTag.name).all()
    statuses = ProjectStatus.query.order_by(ProjectStatus.name).all()
    groups = ProjectGroup.query.order_by(ProjectGroup.name).all()
    persons = ProjectPerson.query.order_by(ProjectPerson.name).all()
    users = User.query.filter_by(is_active=True).order_by(User.username).all()

    can_edit = current_user.has_permission('settings_sections.project_settings', 'edit')
    can_delete = current_user.has_permission('settings_sections.project_settings', 'delete')

    return render_template('project_settings.html',
                           categories=categories, tags=tags, statuses=statuses,
                           groups=groups, persons=persons, users=users,
                           can_edit=can_edit, can_delete=can_delete)


# --- Category CRUD ---
@project_bp.route('/settings/project/category/add', endpoint='project_category_add', methods=['POST'])
@login_required
def project_category_add():
    if not current_user.has_permission('settings_sections.project_settings', 'edit'):
        flash('No permission.', 'danger')
        return redirect(url_for('project.project_settings'))
    name = request.form.get('name', '').strip()
    if not name:
        flash('Name required.', 'danger')
        return redirect(url_for('project.project_settings'))
    if ProjectCategory.query.filter_by(name=name).first():
        flash('Category already exists.', 'danger')
        return redirect(url_for('project.project_settings'))
    cat = ProjectCategory(name=name, description=request.form.get('description', '').strip(),
                          color=request.form.get('color', '#6c757d'))
    db.session.add(cat)
    db.session.commit()
    flash(f'Category "{name}" added.', 'success')
    return redirect(url_for('project.project_settings'))


@project_bp.route('/settings/project/category/<int:id>/edit', endpoint='project_category_edit', methods=['POST'])
@login_required
def project_category_edit(id):
    if not current_user.has_permission('settings_sections.project_settings', 'edit'):
        flash('No permission.', 'danger')
        return redirect(url_for('project.project_settings'))
    cat = ProjectCategory.query.get_or_404(id)
    cat.name = request.form.get('name', cat.name).strip()
    cat.description = request.form.get('description', '').strip()
    cat.color = request.form.get('color', cat.color)
    db.session.commit()
    flash('Category updated.', 'success')
    return redirect(url_for('project.project_settings'))


@project_bp.route('/settings/project/category/<int:id>/delete', endpoint='project_category_delete', methods=['POST'])
@login_required
def project_category_delete(id):
    if not current_user.has_permission('settings_sections.project_settings', 'delete'):
        flash('No permission.', 'danger')
        return redirect(url_for('project.project_settings'))
    cat = ProjectCategory.query.get_or_404(id)
    db.session.delete(cat)
    db.session.commit()
    flash('Category deleted.', 'success')
    return redirect(url_for('project.project_settings'))


# --- Tag CRUD ---
@project_bp.route('/settings/project/tag/add', endpoint='project_tag_add', methods=['POST'])
@login_required
def project_tag_add():
    if not current_user.has_permission('settings_sections.project_settings', 'edit'):
        flash('No permission.', 'danger')
        return redirect(url_for('project.project_settings'))
    name = request.form.get('name', '').strip()
    if not name:
        flash('Name required.', 'danger')
        return redirect(url_for('project.project_settings'))
    if ProjectTag.query.filter_by(name=name).first():
        flash('Tag already exists.', 'danger')
        return redirect(url_for('project.project_settings'))
    tag = ProjectTag(name=name, description=request.form.get('description', '').strip(),
                     color=request.form.get('color', '#6c757d'))
    db.session.add(tag)
    db.session.commit()
    flash(f'Tag "{name}" added.', 'success')
    return redirect(url_for('project.project_settings'))


@project_bp.route('/settings/project/tag/<int:id>/edit', endpoint='project_tag_edit', methods=['POST'])
@login_required
def project_tag_edit(id):
    if not current_user.has_permission('settings_sections.project_settings', 'edit'):
        flash('No permission.', 'danger')
        return redirect(url_for('project.project_settings'))
    tag = ProjectTag.query.get_or_404(id)
    tag.name = request.form.get('name', tag.name).strip()
    tag.description = request.form.get('description', '').strip()
    tag.color = request.form.get('color', tag.color)
    db.session.commit()
    flash('Tag updated.', 'success')
    return redirect(url_for('project.project_settings'))


@project_bp.route('/settings/project/tag/<int:id>/delete', endpoint='project_tag_delete', methods=['POST'])
@login_required
def project_tag_delete(id):
    if not current_user.has_permission('settings_sections.project_settings', 'delete'):
        flash('No permission.', 'danger')
        return redirect(url_for('project.project_settings'))
    tag = ProjectTag.query.get_or_404(id)
    db.session.delete(tag)
    db.session.commit()
    flash('Tag deleted.', 'success')
    return redirect(url_for('project.project_settings'))


# --- Status CRUD ---
@project_bp.route('/settings/project/status/add', endpoint='project_status_add', methods=['POST'])
@login_required
def project_status_add():
    if not current_user.has_permission('settings_sections.project_settings', 'edit'):
        flash('No permission.', 'danger')
        return redirect(url_for('project.project_settings'))
    name = request.form.get('name', '').strip()
    if not name:
        flash('Name required.', 'danger')
        return redirect(url_for('project.project_settings'))
    if ProjectStatus.query.filter_by(name=name).first():
        flash('Status already exists.', 'danger')
        return redirect(url_for('project.project_settings'))
    st = ProjectStatus(name=name, color=request.form.get('color', '#6c757d'),
                       description=request.form.get('description', '').strip())
    db.session.add(st)
    db.session.commit()
    flash(f'Status "{name}" added.', 'success')
    return redirect(url_for('project.project_settings'))


@project_bp.route('/settings/project/status/<int:id>/edit', endpoint='project_status_edit', methods=['POST'])
@login_required
def project_status_edit(id):
    if not current_user.has_permission('settings_sections.project_settings', 'edit'):
        flash('No permission.', 'danger')
        return redirect(url_for('project.project_settings'))
    st = ProjectStatus.query.get_or_404(id)
    st.name = request.form.get('name', st.name).strip()
    st.color = request.form.get('color', st.color)
    st.description = request.form.get('description', '').strip()
    db.session.commit()
    flash('Status updated.', 'success')
    return redirect(url_for('project.project_settings'))


@project_bp.route('/settings/project/status/<int:id>/delete', endpoint='project_status_delete', methods=['POST'])
@login_required
def project_status_delete(id):
    if not current_user.has_permission('settings_sections.project_settings', 'delete'):
        flash('No permission.', 'danger')
        return redirect(url_for('project.project_settings'))
    st = ProjectStatus.query.get_or_404(id)
    db.session.delete(st)
    db.session.commit()
    flash('Status deleted.', 'success')
    return redirect(url_for('project.project_settings'))


# --- Person CRUD ---
@project_bp.route('/settings/project/person/add', endpoint='project_person_add', methods=['POST'])
@login_required
def project_person_add():
    if not current_user.has_permission('settings_sections.project_settings', 'edit'):
        flash('No permission.', 'danger')
        return redirect(url_for('project.project_settings'))
    name = request.form.get('name', '').strip()
    if not name:
        flash('Name required.', 'danger')
        return redirect(url_for('project.project_settings'))
    person = ProjectPerson(name=name, email=request.form.get('email', '').strip(),
                           organization=request.form.get('organization', '').strip(),
                           tel=request.form.get('tel', '').strip())
    db.session.add(person)
    db.session.commit()
    flash(f'Person "{name}" added.', 'success')
    return redirect(url_for('project.project_settings'))


@project_bp.route('/settings/project/person/<int:id>/edit', endpoint='project_person_edit', methods=['POST'])
@login_required
def project_person_edit(id):
    if not current_user.has_permission('settings_sections.project_settings', 'edit'):
        flash('No permission.', 'danger')
        return redirect(url_for('project.project_settings'))
    p = ProjectPerson.query.get_or_404(id)
    p.name = request.form.get('name', p.name).strip()
    p.email = request.form.get('email', '').strip()
    p.organization = request.form.get('organization', '').strip()
    p.tel = request.form.get('tel', '').strip()
    db.session.commit()
    flash('Person updated.', 'success')
    return redirect(url_for('project.project_settings'))


@project_bp.route('/settings/project/person/<int:id>/delete', endpoint='project_person_delete', methods=['POST'])
@login_required
def project_person_delete(id):
    if not current_user.has_permission('settings_sections.project_settings', 'delete'):
        flash('No permission.', 'danger')
        return redirect(url_for('project.project_settings'))
    p = ProjectPerson.query.get_or_404(id)
    db.session.delete(p)
    db.session.commit()
    flash('Person deleted.', 'success')
    return redirect(url_for('project.project_settings'))


# --- Group CRUD ---
@project_bp.route('/settings/project/group/add', endpoint='project_group_add', methods=['POST'])
@login_required
def project_group_add():
    if not current_user.has_permission('settings_sections.project_settings', 'edit'):
        flash('No permission.', 'danger')
        return redirect(url_for('project.project_settings'))
    name = request.form.get('name', '').strip()
    if not name:
        flash('Name required.', 'danger')
        return redirect(url_for('project.project_settings'))
    if ProjectGroup.query.filter_by(name=name).first():
        flash('Group already exists.', 'danger')
        return redirect(url_for('project.project_settings'))
    grp = ProjectGroup(name=name, description=request.form.get('description', '').strip())
    db.session.add(grp)
    db.session.commit()
    flash(f'Group "{name}" created.', 'success')
    return redirect(url_for('project.project_settings'))


@project_bp.route('/settings/project/group/<int:id>/edit', endpoint='project_group_edit', methods=['POST'])
@login_required
def project_group_edit(id):
    if not current_user.has_permission('settings_sections.project_settings', 'edit'):
        flash('No permission.', 'danger')
        return redirect(url_for('project.project_settings'))
    grp = ProjectGroup.query.get_or_404(id)
    grp.name = request.form.get('name', grp.name).strip()
    grp.description = request.form.get('description', '').strip()
    db.session.commit()
    flash('Group updated.', 'success')
    return redirect(url_for('project.project_settings'))


@project_bp.route('/settings/project/group/<int:id>/delete', endpoint='project_group_delete', methods=['POST'])
@login_required
def project_group_delete(id):
    if not current_user.has_permission('settings_sections.project_settings', 'delete'):
        flash('No permission.', 'danger')
        return redirect(url_for('project.project_settings'))
    grp = ProjectGroup.query.get_or_404(id)
    db.session.delete(grp)
    db.session.commit()
    flash('Group deleted.', 'success')
    return redirect(url_for('project.project_settings'))


@project_bp.route('/settings/project/group/<int:id>/add-member', endpoint='project_group_add_member', methods=['POST'])
@login_required
def project_group_add_member(id):
    if not current_user.has_permission('settings_sections.project_settings', 'edit'):
        flash('No permission.', 'danger')
        return redirect(url_for('project.project_settings'))
    grp = ProjectGroup.query.get_or_404(id)
    member_type = request.form.get('member_type', 'user')
    member_id = request.form.get('member_id', type=int)
    if not member_id:
        flash('Select a member.', 'danger')
        return redirect(url_for('project.project_settings'))

    if member_type == 'user':
        existing = ProjectGroupMember.query.filter_by(group_id=id, user_id=member_id).first()
        if existing:
            flash('User already in group.', 'warning')
            return redirect(url_for('project.project_settings'))
        m = ProjectGroupMember(group_id=id, user_id=member_id)
    else:
        existing = ProjectGroupMember.query.filter_by(group_id=id, person_id=member_id).first()
        if existing:
            flash('Person already in group.', 'warning')
            return redirect(url_for('project.project_settings'))
        m = ProjectGroupMember(group_id=id, person_id=member_id)

    db.session.add(m)
    db.session.commit()
    flash('Member added to group.', 'success')
    return redirect(url_for('project.project_settings'))


@project_bp.route('/settings/project/group/member/<int:member_id>/remove', endpoint='project_group_remove_member', methods=['POST'])
@login_required
def project_group_remove_member(member_id):
    if not current_user.has_permission('settings_sections.project_settings', 'edit'):
        flash('No permission.', 'danger')
        return redirect(url_for('project.project_settings'))
    m = ProjectGroupMember.query.get_or_404(member_id)
    db.session.delete(m)
    db.session.commit()
    flash('Member removed.', 'success')
    return redirect(url_for('project.project_settings'))


# ==================== PRINT ====================

@project_bp.route('/projects/print', endpoint='projects_print')
@login_required
def projects_print():
    if not current_user.has_permission('projects', 'view'):
        abort(403)

    search_query = request.args.get('search', '')
    category_id = request.args.get('category', 0, type=int)
    status_id = request.args.get('status', 0, type=int)

    query = Project.query
    if search_query:
        query = query.filter(db.or_(Project.name.ilike(f'%{search_query}%'), Project.info.ilike(f'%{search_query}%')))
    if category_id > 0:
        query = query.filter_by(category_id=category_id)
    if status_id > 0:
        query = query.filter_by(status_id=status_id)

    projects_list = query.order_by(Project.updated_at.desc()).all()
    user_columns = current_user.get_project_table_columns()
    currency = Setting.get('currency', 'USD')
    currency_decimal = int(Setting.get('currency_decimal_places', '2'))

    return render_template('projects_print.html',
                           projects=projects_list,
                           user_columns=user_columns,
                           currency=currency,
                           currency_decimal=currency_decimal)


# ==================== SAVE PROJECT TABLE COLUMNS ====================

@project_bp.route('/save-project-table-columns', endpoint='save_project_table_columns', methods=['POST'])
@login_required
def save_project_table_columns():
    columns_json = request.form.get('columns', '[]')
    try:
        columns = json.loads(columns_json)
        valid_columns = ['project_name', 'info', 'categories', 'tags', 'date_start', 'dateline',
                         'total_cost', 'status', 'users', 'group', 'project_id']
        columns = [col for col in columns if col in valid_columns]
        current_user.set_project_table_columns(columns)
        db.session.commit()
        flash('Project table columns updated!', 'success')
    except Exception as e:
        logger.error(f"Error saving project table columns: {e}")
        flash('Error saving columns.', 'danger')
    return redirect(url_for('settings.settings_general'))
