"""
Project Routes Blueprint
"""
from flask import Blueprint, render_template, redirect, url_for, flash, request, jsonify, current_app, abort, send_file
from flask_login import login_required, current_user
from models import (db, User, Item, ItemBatch, BatchSerialNumber, Setting,
                    Project, ProjectCategory, ProjectTag, ProjectStatus,
                    ProjectPerson, ProjectGroup, ProjectGroupMember,
                    ContactPerson, ContactOrganization,
                    ProjectBOMItem, ProjectCostItem, ProjectAttachment, ProjectURL, SharedFile,
                    MagicParameter, ProjectParameter, ProjectParameterStringValue)
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
_ALLOWED_ATTACHMENT_TYPES = {'picture', 'document', 'schematic', '2d_design', '3d_design', 'program'}


# ==================== HELPERS ====================

def get_project_file_settings(attachment_type):
    """Get allowed extensions and max size for a project attachment type"""
    defaults = {
        'picture': ('webp,png,svg,jpeg,jpg', '10'),
        'document': ('txt,doc,docx,pdf', '10'),
        'schematic': ('pdf,zip', '20'),
        '2d_design': ('pdf,zip', '20'),
        '3d_design': ('pdf,zip,stl,step', '50'),
        'program': ('zip,txt,cpp,py', '10'),
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
    contact_persons = ContactPerson.query.order_by(ContactPerson.name).all()
    contact_orgs = ContactOrganization.query.order_by(ContactOrganization.name).all()

    if request.method == 'POST':
        name = request.form.get('name', '').strip()[:512]
        if not name:
            flash('Project name is required.', 'danger')
            return render_template('project_form.html', title='New Project', project=None,
                                   categories=categories, tags=tags, statuses=statuses,
                                   users=users, contact_persons=contact_persons, contact_orgs=contact_orgs)

        cat_id = request.form.get('category_id', type=int) or None
        stat_id = request.form.get('status_id', type=int) or None
        if cat_id and not ProjectCategory.query.get(cat_id):
            flash('Selected category does not exist.', 'danger')
            return render_template('project_form.html', title='New Project', project=None,
                                   categories=categories, tags=tags, statuses=statuses,
                                   users=users, contact_persons=contact_persons, contact_orgs=contact_orgs)
        if stat_id and not ProjectStatus.query.get(stat_id):
            flash('Selected status does not exist.', 'danger')
            return render_template('project_form.html', title='New Project', project=None,
                                   categories=categories, tags=tags, statuses=statuses,
                                   users=users, contact_persons=contact_persons, contact_orgs=contact_orgs)

        project = Project(
            name=name,
            info=request.form.get('info', '').strip()[:128],
            category_id=cat_id,
            status_id=stat_id,
            quantity=request.form.get('quantity', 1, type=int),
            created_by=current_user.id,
            updated_by=current_user.id
        )

        # Tags — validate each ID exists
        selected_tags = request.form.getlist('tags')
        valid_tag_ids = []
        for t in selected_tags:
            try:
                tid = int(t)
                if ProjectTag.query.get(tid):
                    valid_tag_ids.append(tid)
            except (ValueError, TypeError):
                pass
        project.tags = json.dumps(valid_tag_ids) if valid_tag_ids else None

        # Users
        selected_users = request.form.getlist('users')
        if selected_users:
            project.users = json.dumps([int(u) for u in selected_users if u])

        # Persons
        selected_persons = request.form.getlist('persons')
        if selected_persons:
            project.persons = json.dumps([int(p) for p in selected_persons if p])

        # Organizations
        selected_orgs = request.form.getlist('organizations')
        if selected_orgs:
            project.organizations = json.dumps([int(o) for o in selected_orgs if o])

        # Dates
        date_start = request.form.get('date_start', '').strip()
        if date_start:
            try:
                project.date_start = datetime.strptime(date_start, '%Y-%m-%d').date()
            except ValueError:
                flash(f'Invalid start date format: "{date_start}". Use YYYY-MM-DD.', 'danger')
                return render_template('project_form.html', title='New Project', project=None,
                                       categories=categories, tags=tags, statuses=statuses,
                                       users=users, contact_persons=contact_persons, contact_orgs=contact_orgs)
        date_end = request.form.get('date_end', '').strip()
        if date_end:
            try:
                project.date_end = datetime.strptime(date_end, '%Y-%m-%d').date()
            except ValueError:
                flash(f'Invalid end date format: "{date_end}". Use YYYY-MM-DD.', 'danger')
                return render_template('project_form.html', title='New Project', project=None,
                                       categories=categories, tags=tags, statuses=statuses,
                                       users=users, contact_persons=contact_persons, contact_orgs=contact_orgs)

        db.session.add(project)
        db.session.commit()

        log_audit(current_user.id, 'create', 'project', project.id, f'Created project: {project.name}')
        flash(f'Project "{project.name}" created successfully!', 'success')
        return redirect(url_for('project.project_detail', project_id=project.project_id))

    return render_template('project_form.html', title='New Project', project=None,
                           categories=categories, tags=tags, statuses=statuses,
                           users=users, contact_persons=contact_persons, contact_orgs=contact_orgs)


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

    # Cost items
    cost_items_per_qty = ProjectCostItem.query.filter_by(project_id=project.id, cost_type='per_qty').order_by(ProjectCostItem.sort_order).all()
    cost_items_overall = ProjectCostItem.query.filter_by(project_id=project.id, cost_type='overall').order_by(ProjectCostItem.sort_order).all()

    # Attachments by type
    attachments = {}
    for atype in ['picture', 'document', 'schematic', '2d_design', '3d_design', 'program']:
        attachments[atype] = ProjectAttachment.query.filter_by(project_id=project.id, attachment_type=atype).all()

    can_edit = current_user.has_permission('projects', 'edit')
    can_delete = current_user.has_permission('projects', 'delete')

    return render_template('project_detail.html',
                           project=project,
                           bom_items=bom_items,
                           cost_items_per_qty=cost_items_per_qty,
                           cost_items_overall=cost_items_overall,
                           attachments=attachments,
                           currency=currency,
                           currency_decimal=currency_decimal,
                           can_edit=can_edit,
                           can_delete=can_delete,
                           download_all_project_attachments=Setting.get('download_all_project_attachments', True),
                           download_all_project_share_files=Setting.get('download_all_project_share_files', True))


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
    contact_persons = ContactPerson.query.order_by(ContactPerson.name).all()
    contact_orgs = ContactOrganization.query.order_by(ContactOrganization.name).all()

    if request.method == 'POST':
        name = request.form.get('name', '').strip()[:512]
        if not name:
            flash('Project name is required.', 'danger')
            return redirect(url_for('project.project_edit', project_id=project_id))

        cat_id = request.form.get('category_id', type=int) or None
        stat_id = request.form.get('status_id', type=int) or None
        if cat_id and not ProjectCategory.query.get(cat_id):
            flash('Selected category does not exist.', 'danger')
            return redirect(url_for('project.project_edit', project_id=project_id))
        if stat_id and not ProjectStatus.query.get(stat_id):
            flash('Selected status does not exist.', 'danger')
            return redirect(url_for('project.project_edit', project_id=project_id))

        project.name = name
        project.info = request.form.get('info', '').strip()[:128]
        project.description = request.form.get('description', '').strip()
        project.category_id = cat_id
        project.status_id = stat_id
        project.quantity = request.form.get('quantity', 1, type=int)
        project.updated_by = current_user.id

        project.enable_dateline_notification = 'enable_dateline_notification' in request.form
        project.notify_before_days = max(1, min(request.form.get('notify_before_days', 3, type=int), 365))

        selected_tags = request.form.getlist('tags')
        valid_tag_ids = []
        for t in selected_tags:
            try:
                tid = int(t)
                if ProjectTag.query.get(tid):
                    valid_tag_ids.append(tid)
            except (ValueError, TypeError):
                pass
        project.tags = json.dumps(valid_tag_ids) if valid_tag_ids else None

        selected_users = request.form.getlist('users')
        project.users = json.dumps([int(u) for u in selected_users if u]) if selected_users else None

        selected_persons = request.form.getlist('persons')
        project.persons = json.dumps([int(p) for p in selected_persons if p]) if selected_persons else None

        selected_orgs = request.form.getlist('organizations')
        project.organizations = json.dumps([int(o) for o in selected_orgs if o]) if selected_orgs else None

        date_start = request.form.get('date_start', '').strip()
        if date_start:
            try:
                project.date_start = datetime.strptime(date_start, '%Y-%m-%d').date()
            except ValueError:
                flash(f'Invalid start date format: "{date_start}". Use YYYY-MM-DD.', 'danger')
                return redirect(url_for('project.project_edit', project_id=project_id))
        else:
            project.date_start = None
        date_end = request.form.get('date_end', '').strip()
        if date_end:
            try:
                project.date_end = datetime.strptime(date_end, '%Y-%m-%d').date()
            except ValueError:
                flash(f'Invalid end date format: "{date_end}". Use YYYY-MM-DD.', 'danger')
                return redirect(url_for('project.project_edit', project_id=project_id))
        else:
            project.date_end = None

        sf_ids = [int(i) for i in request.form.getlist('share_file_ids[]') if i]
        project.linked_share_files = SharedFile.query.filter(SharedFile.id.in_(sf_ids)).all() if sf_ids else []

        db.session.commit()
        log_audit(current_user.id, 'update', 'project', project.id, f'Updated project: {project.name}')
        flash(f'Project "{project.name}" updated!', 'success')
        return redirect(url_for('project.project_detail', project_id=project.project_id))

    return render_template('project_form.html', title='Edit Project', project=project,
                           categories=categories, tags=tags, statuses=statuses,
                           users=users, contact_persons=contact_persons, contact_orgs=contact_orgs,
                           bom_items=ProjectBOMItem.query.filter_by(project_id=project.id).all(),
                           attachments={atype: ProjectAttachment.query.filter_by(project_id=project.id, attachment_type=atype).all() for atype in ['picture', 'document', 'schematic', '2d_design', '3d_design', 'program']},
                           share_files_project=SharedFile.query.filter_by(category='project').order_by(SharedFile.name).all(),
                           currency=Setting.get('currency', 'USD'),
                           currency_decimal=int(Setting.get('currency_decimal_places', '2')))


# ==================== PROJECT MAGIC PARAMETERS ====================

@project_bp.route('/project/<project_id>/populate-template', endpoint='project_populate_template', methods=['POST'])
@login_required
def project_populate_template(project_id):
    if not current_user.has_permission('projects', 'edit'):
        flash('You do not have permission to edit projects.', 'danger')
        return redirect(url_for('project.projects'))

    project = Project.query.filter_by(project_id=project_id).first_or_404()
    from models import ParameterTemplate
    template_id = int(request.form.get('template_id', 0))
    template = ParameterTemplate.query.get(template_id)
    if not template:
        flash('Invalid template selected.', 'danger')
        return redirect(url_for('project.project_edit', project_id=project_id))

    added_count = 0
    for tp in template.template_parameters:
        proj_param = ProjectParameter(
            project_id=project.id,
            parameter_id=tp.parameter_id,
            operation=tp.operation,
            value=tp.value,
            value2=tp.value2,
            unit=tp.unit,
            description=tp.description
        )
        db.session.add(proj_param)
        added_count += 1

    db.session.commit()
    log_audit(current_user.id, 'update', 'project', project.id, f'Applied template "{template.name}" to project: {project.name}')
    flash(f'Added {added_count} parameters from template "{template.name}"!', 'success')
    return redirect(url_for('project.project_edit', project_id=project_id))


@project_bp.route('/project/<project_id>/add-parameter', endpoint='project_add_parameter', methods=['POST'])
@login_required
def project_add_parameter(project_id):
    if not current_user.has_permission('projects', 'edit'):
        flash('You do not have permission to edit projects.', 'danger')
        return redirect(url_for('project.projects'))

    project = Project.query.filter_by(project_id=project_id).first_or_404()

    param_type = request.form.get('param_type')
    parameter_id = int(request.form.get('parameter_id', 0))
    operation = request.form.get('operation')
    value = request.form.get('value', '').strip()
    value2 = request.form.get('value2', '').strip()
    unit = request.form.get('unit', '').strip()
    description = request.form.get('description', '').strip()

    parameter = MagicParameter.query.get(parameter_id)
    if not parameter:
        flash('Invalid parameter selected.', 'danger')
        return redirect(url_for('project.project_edit', project_id=project_id))

    errors = []

    if param_type == 'string':
        selected_options = request.form.getlist('string_options')
        custom_value = request.form.get('string_custom_value', '').strip()
        custom_values = [custom_value] if custom_value else []
        for opt in selected_options:
            if len(opt) > 128:
                errors.append(f"Option value too long (max 128 characters): {opt[:30]}...")
        for cv in custom_values:
            if len(cv) > 128:
                errors.append("Custom value too long (max 128 characters)")
        if not errors:
            ok, err = parameter.validate_string_selections(selected_options, custom_values)
            if not ok:
                errors.append(err)
    elif param_type == 'number':
        if parameter.number_required and not value:
            errors.append('This number parameter is required')
        if value:
            is_valid, error_msg = parameter.validate_number_value(value, False)
            if not is_valid:
                errors.append(f"Value: {error_msg}")
        if value2 and operation == 'range':
            is_valid, error_msg = parameter.validate_number_value(value2, True)
            if not is_valid:
                errors.append(f"Value2: {error_msg}")
        if operation == 'range' and value and value2:
            try:
                if float(value) >= float(value2):
                    errors.append('Range start must be less than range end')
            except ValueError:
                pass

    if errors:
        for error in errors:
            flash(error, 'danger')
        return redirect(url_for('project.project_edit', project_id=project_id))

    proj_param = ProjectParameter(
        project_id=project.id,
        parameter_id=parameter_id,
        operation=operation if param_type in ['number', 'date'] else None,
        value=value if param_type in ['number', 'date'] else None,
        value2=value2 if operation in ['range', 'duration'] else None,
        unit=unit if param_type == 'number' else None,
        description=description[:512]
    )
    db.session.add(proj_param)
    db.session.flush()

    if param_type == 'string':
        for opt in selected_options:
            db.session.add(ProjectParameterStringValue(project_parameter_id=proj_param.id, value=opt, is_custom=False))
        for cv in custom_values:
            db.session.add(ProjectParameterStringValue(project_parameter_id=proj_param.id, value=cv, is_custom=True))

    db.session.commit()
    log_audit(current_user.id, 'update', 'project', project.id, f'Added parameter to project: {project.name}')
    flash('Parameter added successfully!', 'success')
    return redirect(url_for('project.project_edit', project_id=project_id))


@project_bp.route('/project/<project_id>/delete-parameter/<int:param_id>', endpoint='project_delete_parameter', methods=['POST'])
@login_required
def project_delete_parameter(project_id, param_id):
    if not current_user.has_permission('projects', 'edit'):
        flash('You do not have permission to edit projects.', 'danger')
        return redirect(url_for('project.projects'))

    project = Project.query.filter_by(project_id=project_id).first_or_404()
    proj_param = ProjectParameter.query.get_or_404(param_id)

    if proj_param.project_id != project.id:
        flash('Invalid parameter.', 'danger')
        return redirect(url_for('project.project_edit', project_id=project_id))

    db.session.delete(proj_param)
    db.session.commit()
    log_audit(current_user.id, 'update', 'project', project.id, f'Removed parameter from project: {project.name}')
    flash('Parameter removed successfully!', 'success')
    return redirect(url_for('project.project_edit', project_id=project_id))


@project_bp.route('/project/<project_id>/edit-parameter/<int:param_id>', endpoint='project_edit_parameter', methods=['GET', 'POST'])
@login_required
def project_edit_parameter(project_id, param_id):
    if not current_user.has_permission('projects', 'edit'):
        flash('You do not have permission to edit projects.', 'danger')
        return redirect(url_for('project.projects'))

    project = Project.query.filter_by(project_id=project_id).first_or_404()
    proj_param = ProjectParameter.query.get_or_404(param_id)

    if proj_param.project_id != project.id:
        flash('Invalid parameter.', 'danger')
        return redirect(url_for('project.project_edit', project_id=project_id))

    if request.method == 'POST':
        param = proj_param.parameter
        operation = request.form.get('operation')
        value = request.form.get('value', '').strip()
        value2 = request.form.get('value2', '').strip() if operation in ['range', 'duration'] else None

        errors = []

        if param.param_type == 'string':
            selected_options = request.form.getlist('string_options')
            custom_value = request.form.get('string_custom_value', '').strip()
            custom_values = [custom_value] if custom_value else []
            for opt in selected_options:
                if len(opt) > 128:
                    errors.append(f"Option value too long (max 128 characters): {opt[:30]}...")
            for cv in custom_values:
                if len(cv) > 128:
                    errors.append("Custom value too long (max 128 characters)")
            if not errors:
                ok, err = param.validate_string_selections(selected_options, custom_values)
                if not ok:
                    errors.append(err)
        elif param.param_type == 'number':
            if param.number_required and not value:
                errors.append('This number parameter is required')
            if value:
                is_valid, error_msg = param.validate_number_value(value, False)
                if not is_valid:
                    errors.append(f"Value: {error_msg}")
            if value2 and operation in ['range', 'duration']:
                is_valid, error_msg = param.validate_number_value(value2, True)
                if not is_valid:
                    errors.append(f"Value2: {error_msg}")
            if operation == 'range' and value and value2:
                try:
                    if float(value) >= float(value2):
                        errors.append('Range start must be less than range end')
                except ValueError:
                    pass

        if errors:
            for error in errors:
                flash(error, 'danger')
            return redirect(url_for('project.project_edit_parameter', project_id=project_id, param_id=param_id))

        proj_param.operation = operation
        proj_param.value = value
        proj_param.value2 = value2
        proj_param.unit = request.form.get('unit', '').strip()
        proj_param.description = request.form.get('description', '').strip()[:512]

        if param.param_type == 'string':
            ProjectParameterStringValue.query.filter_by(project_parameter_id=proj_param.id).delete()
            for opt in selected_options:
                db.session.add(ProjectParameterStringValue(project_parameter_id=proj_param.id, value=opt, is_custom=False))
            for cv in custom_values:
                db.session.add(ProjectParameterStringValue(project_parameter_id=proj_param.id, value=cv, is_custom=True))

        db.session.commit()
        log_audit(current_user.id, 'update', 'project', project.id, f'Updated parameter for project: {project.name}')
        flash('Parameter updated successfully!', 'success')
        return redirect(url_for('project.project_edit', project_id=project_id))

    return render_template('project_parameter_edit.html', project=project, proj_param=proj_param)


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
        is_lent = bool(sn.lend_to_type and sn.lend_to_type.strip())
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
            new_used = max(0, min(new_used, available))
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


# ==================== PROJECT COST ITEMS ====================

@project_bp.route('/project/<project_id>/cost/add', endpoint='cost_item_add', methods=['POST'])
@login_required
def cost_item_add(project_id):
    if not current_user.has_permission('projects', 'edit'):
        return jsonify({'error': 'No permission'}), 403

    project = Project.query.filter_by(project_id=project_id).first_or_404()
    data = request.get_json()
    cost_type = data.get('cost_type', 'per_qty')
    if cost_type not in ('per_qty', 'overall'):
        return jsonify({'error': 'Invalid cost_type'}), 400

    # Assign sort_order as max + 1 for this type
    existing = ProjectCostItem.query.filter_by(project_id=project.id, cost_type=cost_type).all()
    sort_order = max((i.sort_order for i in existing), default=-1) + 1

    try:
        price = float(data.get('price', 0))
        qty = float(data.get('quantity', 1))
    except (ValueError, TypeError):
        return jsonify({'error': 'Invalid price or quantity'}), 400

    item = ProjectCostItem(
        project_id=project.id,
        cost_type=cost_type,
        name=(data.get('name') or '').strip(),
        description=(data.get('description') or '').strip(),
        price=price,
        unit_label=(data.get('unit_label') or '').strip(),
        quantity=qty,
        sort_order=sort_order,
    )
    if not item.name:
        return jsonify({'error': 'Name is required'}), 400
    db.session.add(item)
    db.session.commit()
    log_audit(current_user.id, 'create', 'project_cost_item', item.id, f'Added cost item to project {project.project_id}')
    return jsonify({'success': True, 'id': item.id})


@project_bp.route('/project/<project_id>/cost/<int:cost_id>/edit', endpoint='cost_item_edit', methods=['POST'])
@login_required
def cost_item_edit(project_id, cost_id):
    if not current_user.has_permission('projects', 'edit'):
        return jsonify({'error': 'No permission'}), 403

    project = Project.query.filter_by(project_id=project_id).first_or_404()
    item = ProjectCostItem.query.filter_by(id=cost_id, project_id=project.id).first_or_404()
    data = request.get_json()

    name = (data.get('name') or '').strip()
    if not name:
        return jsonify({'error': 'Name is required'}), 400

    try:
        price = float(data.get('price', 0))
        qty = float(data.get('quantity', 1))
    except (ValueError, TypeError):
        return jsonify({'error': 'Invalid price or quantity'}), 400

    item.name = name
    item.description = (data.get('description') or '').strip()
    item.price = price
    item.unit_label = (data.get('unit_label') or '').strip()
    item.quantity = qty
    db.session.commit()
    log_audit(current_user.id, 'update', 'project_cost_item', item.id, f'Edited cost item in project {project.project_id}')
    return jsonify({'success': True})


@project_bp.route('/project/<project_id>/cost/<int:cost_id>/delete', endpoint='cost_item_delete', methods=['POST'])
@login_required
def cost_item_delete(project_id, cost_id):
    if not current_user.has_permission('projects', 'edit'):
        return jsonify({'error': 'No permission'}), 403

    project = Project.query.filter_by(project_id=project_id).first_or_404()
    item = ProjectCostItem.query.filter_by(id=cost_id, project_id=project.id).first_or_404()
    db.session.delete(item)
    db.session.commit()
    return jsonify({'success': True})


@project_bp.route('/project/<project_id>/cost/<int:cost_id>/move', endpoint='cost_item_move', methods=['POST'])
@login_required
def cost_item_move(project_id, cost_id):
    if not current_user.has_permission('projects', 'edit'):
        return jsonify({'error': 'No permission'}), 403

    project = Project.query.filter_by(project_id=project_id).first_or_404()
    item = ProjectCostItem.query.filter_by(id=cost_id, project_id=project.id).first_or_404()
    direction = (request.get_json() or {}).get('direction', 'up')

    siblings = ProjectCostItem.query.filter_by(
        project_id=project.id, cost_type=item.cost_type
    ).order_by(ProjectCostItem.sort_order).all()

    idx = next((i for i, s in enumerate(siblings) if s.id == item.id), None)
    if idx is None:
        return jsonify({'error': 'Item not found'}), 404

    swap_idx = idx - 1 if direction == 'up' else idx + 1
    if swap_idx < 0 or swap_idx >= len(siblings):
        return jsonify({'success': True})  # already at boundary

    siblings[idx].sort_order, siblings[swap_idx].sort_order = siblings[swap_idx].sort_order, siblings[idx].sort_order
    db.session.commit()
    return jsonify({'success': True})


# ==================== PROJECT ATTACHMENTS ====================

@project_bp.route('/project/<project_id>/upload/<attachment_type>', endpoint='project_upload', methods=['POST'])
@login_required
def project_upload(project_id, attachment_type):
    if not current_user.has_permission('projects', 'edit'):
        flash('No permission.', 'danger')
        return redirect(url_for('project.project_detail', project_id=project_id))

    valid_types = ['picture', 'document', 'schematic', '2d_design', '3d_design', 'program']
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


@project_bp.route('/project/<project_id>/download-attachments', endpoint='project_download_attachments')
@login_required
def project_download_attachments(project_id):
    if not current_user.has_permission('projects', 'view'):
        abort(403)
    if not Setting.get('download_all_project_attachments', True):
        abort(403)
    import zipfile, io
    project = Project.query.filter_by(project_id=project_id).first_or_404()
    all_atts = ProjectAttachment.query.filter_by(project_id=project.id).all()
    if not all_atts:
        flash('No attachments to download.', 'warning')
        return redirect(url_for('project.project_detail', project_id=project_id))
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, 'w', zipfile.ZIP_DEFLATED) as zf:
        for att in all_atts:
            full_path = os.path.join(current_app.config['UPLOAD_FOLDER'], att.file_path)
            if os.path.exists(full_path):
                zf.write(full_path, f"{att.attachment_type}/{att.original_filename}")
    buf.seek(0)
    log_audit(current_user.id, 'download', 'project', project.id, f'Downloaded all attachments for project: {project.name}')
    return send_file(buf, download_name=f"{project.project_id}_attachments.zip", as_attachment=True, mimetype='application/zip')


@project_bp.route('/project/<project_id>/download-share-files', endpoint='project_download_share_files')
@login_required
def project_download_share_files(project_id):
    if not current_user.has_permission('projects', 'view'):
        abort(403)
    if not Setting.get('download_all_project_share_files', True):
        abort(403)
    import zipfile, io
    project = Project.query.filter_by(project_id=project_id).first_or_404()
    if not project.linked_share_files:
        flash('No share files to download.', 'warning')
        return redirect(url_for('project.project_detail', project_id=project_id))
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, 'w', zipfile.ZIP_DEFLATED) as zf:
        for sf in project.linked_share_files:
            full_path = os.path.join(current_app.config['UPLOAD_FOLDER'], 'share', sf.category, sf.filename)
            if os.path.exists(full_path):
                zf.write(full_path, f"{sf.name}.{sf.ext}")
    buf.seek(0)
    log_audit(current_user.id, 'download', 'project', project.id, f'Downloaded all share files for project: {project.name}')
    return send_file(buf, download_name=f"{project.project_id}_share_files.zip", as_attachment=True, mimetype='application/zip')


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
    if not url_val.startswith(('http://', 'https://')):
        flash('URL must start with http:// or https://', 'danger')
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

    can_edit = current_user.has_permission('settings_sections.project_settings', 'edit')
    can_delete = current_user.has_permission('settings_sections.project_settings', 'delete')

    return render_template('project_settings.html',
                           categories=categories, tags=tags, statuses=statuses,
                           can_edit=can_edit, can_delete=can_delete)


# --- Category CRUD ---
@project_bp.route('/settings/project/category/add', endpoint='project_category_add', methods=['POST'])
@login_required
def project_category_add():
    if not current_user.has_permission('settings_sections.project_settings', 'edit'):
        flash('No permission.', 'danger')
        return redirect(url_for('project.project_settings'))
    name = request.form.get('name', '').strip()[:128]
    if not name:
        flash('Name required.', 'danger')
        return redirect(url_for('project.project_settings'))
    if ProjectCategory.query.filter_by(name=name).first():
        flash('Category already exists.', 'danger')
        return redirect(url_for('project.project_settings'))
    cat = ProjectCategory(name=name, description=request.form.get('description', '').strip()[:512],
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
    cat.name = (request.form.get('name', cat.name).strip() or cat.name)[:128]
    cat.description = request.form.get('description', '').strip()[:512]
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
    name = request.form.get('name', '').strip()[:128]
    if not name:
        flash('Name required.', 'danger')
        return redirect(url_for('project.project_settings'))
    if ProjectTag.query.filter_by(name=name).first():
        flash('Tag already exists.', 'danger')
        return redirect(url_for('project.project_settings'))
    tag = ProjectTag(name=name, description=request.form.get('description', '').strip()[:512],
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
    tag.name = (request.form.get('name', tag.name).strip() or tag.name)[:128]
    tag.description = request.form.get('description', '').strip()[:512]
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
    name = request.form.get('name', '').strip()[:128]
    if not name:
        flash('Name required.', 'danger')
        return redirect(url_for('project.project_settings'))
    if ProjectStatus.query.filter_by(name=name).first():
        flash('Status already exists.', 'danger')
        return redirect(url_for('project.project_settings'))
    st = ProjectStatus(name=name, color=request.form.get('color', '#6c757d'),
                       description=request.form.get('description', '').strip()[:512])
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
    st.name = (request.form.get('name', st.name).strip() or st.name)[:128]
    st.color = request.form.get('color', st.color)
    st.description = request.form.get('description', '').strip()[:512]
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
