"""
Magic Parameter Routes Blueprint
"""
from flask import Blueprint, render_template, redirect, url_for, flash, request, jsonify, send_file, abort
from flask_login import login_required, current_user, login_user, logout_user
from models import db, User, Category, Item, Attachment, Rack, Footprint, Tag, Setting, Location, AuditLog, StickerTemplate
from forms import (LoginForm, RegistrationForm, CategoryForm, ItemAddForm, ItemEditForm, AttachmentForm, 
                   SearchForm, UserForm, MagicParameterForm, ParameterUnitForm, ParameterStringOptionForm, ItemParameterForm)
from helpers import is_safe_url, format_currency, is_safe_file_path
from utils import save_file, log_audit, admin_required, permission_required, item_permission_required, format_file_size, allowed_file
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from datetime import datetime, timezone
from urllib.parse import urlparse, urljoin
import os
import json
import secrets
import string
import logging

logger = logging.getLogger(__name__)

magic_parameter_bp = Blueprint('magic_parameter', __name__)


@magic_parameter_bp.route('/magic-parameters', endpoint='magic_parameters')
@login_required
def magic_parameters():
    """Magic Parameters settings page"""
    from models import MagicParameter, ParameterTemplate
    
    # Check view permission for magic parameter settings
    if not current_user.has_permission('settings_sections.magic_parameters', 'view'):
        flash('You do not have permission to view magic parameters.', 'danger')
        return redirect(url_for('settings.settings'))
    
    # Get parameters grouped by type
    number_params = MagicParameter.query.filter_by(param_type='number').order_by(MagicParameter.name).all()
    date_params = MagicParameter.query.filter_by(param_type='date').order_by(MagicParameter.name).all()
    string_params = MagicParameter.query.filter_by(param_type='string').order_by(MagicParameter.name).all()
    templates = ParameterTemplate.query.order_by(ParameterTemplate.name).all()
    
    can_edit = current_user.has_permission('settings_sections.magic_parameters', 'edit')
    can_delete = current_user.has_permission('settings_sections.magic_parameters', 'delete')
    
    return render_template('magic_parameters.html', 
                          number_params=number_params,
                          date_params=date_params,
                          string_params=string_params,
                          templates=templates,
                          can_edit=can_edit,
                          can_delete=can_delete)


@magic_parameter_bp.route('/magic-parameter/new', endpoint='magic_parameter_new', methods=['POST'])
@login_required
@permission_required("settings_sections.magic_parameters", "edit")
def magic_parameter_new():
    from models import MagicParameter, ParameterUnit, ParameterStringOption
    
    # Get form data directly from request
    name = request.form.get('name', '').strip()
    param_type = request.form.get('param_type', '').strip()
    description = request.form.get('description', '').strip()
    unit = request.form.get('unit', '').strip()
    notify_enabled = 'notify_enabled' in request.form
    
    # Number type fields
    is_whole_number = 'is_whole_number' in request.form
    number_min = request.form.get('number_min', '')
    number_max = request.form.get('number_max', '')
    number_step = request.form.get('number_step', '')
    number_decimal_places = request.form.get('number_decimal_places', 0, type=int)
    number_required = 'number_required' in request.form
    
    # Validation
    errors = []
    
    if not name:
        errors.append('Parameter name is required')
    
    if not param_type or param_type not in ['number', 'date', 'string']:
        errors.append('Valid parameter type is required')
    
    if name and param_type:
        existing = MagicParameter.query.filter_by(name=name).first()
        if existing:
            errors.append(f'Parameter "{name}" already exists')
    
    # Validate number fields if type is number
    if param_type == 'number':
        if number_min and number_max:
            try:
                min_val = float(number_min)
                max_val = float(number_max)
                if min_val > max_val:
                    errors.append('Min value cannot be greater than max value')
                
                # Check if min/max are whole numbers when is_whole_number is True
                if is_whole_number:
                    if min_val != int(min_val):
                        errors.append('Minimum value must be a whole number')
                    if max_val != int(max_val):
                        errors.append('Maximum value must be a whole number')
            except ValueError:
                errors.append('Min and max must be valid numbers')
        elif number_min:
            try:
                min_val = float(number_min)
                if is_whole_number and min_val != int(min_val):
                    errors.append('Minimum value must be a whole number')
            except ValueError:
                errors.append('Min must be a valid number')
        elif number_max:
            try:
                max_val = float(number_max)
                if is_whole_number and max_val != int(max_val):
                    errors.append('Maximum value must be a whole number')
            except ValueError:
                errors.append('Max must be a valid number')
        
        if number_step:
            try:
                step_val = float(number_step)
                if step_val <= 0:
                    errors.append('Step must be greater than 0')
                # Check if step is a whole number when is_whole_number is True
                if is_whole_number and step_val != int(step_val):
                    errors.append('Step must be a whole number')
            except ValueError:
                errors.append('Step must be a valid number')
        
        if is_whole_number and number_decimal_places > 0:
            errors.append('Decimal places should be 0 for whole numbers')
    
    # If there are errors, return them as JSON
    if errors:
        return jsonify({
            'success': False,
            'errors': errors
        }), 400
    
    try:
        parameter = MagicParameter(
            name=name,
            param_type=param_type,
            description=description,
            notify_enabled=notify_enabled if param_type == 'date' else False,
            is_whole_number=is_whole_number if param_type == 'number' else True,
            number_min=int(float(number_min)) if number_min and is_whole_number else (float(number_min) if number_min else None),
            number_max=int(float(number_max)) if number_max and is_whole_number else (float(number_max) if number_max else None),
            number_step=int(float(number_step)) if number_step and is_whole_number else (float(number_step) if number_step else None),
            number_decimal_places=number_decimal_places if param_type == 'number' else 0,
            number_required=number_required if param_type == 'number' else False
        )
        db.session.add(parameter)
        db.session.flush()
        
        # Add initial unit for number type
        if param_type == 'number' and unit:
            unit_obj = ParameterUnit(parameter_id=parameter.id, unit=unit)
            db.session.add(unit_obj)
        
        db.session.commit()
        
        log_audit(current_user.id, 'create', 'magic_parameter', parameter.id, f'Created parameter: {name}')
        
        return jsonify({
            'success': True,
            'parameter_id': parameter.id,
            'redirect_url': url_for('magic_parameter.magic_parameter_manage', id=parameter.id)
        })

    except Exception as e:
        db.session.rollback()
        logging.error(f"Error creating parameter: {str(e)}")
        return jsonify({
            'success': False,
            'errors': ['An error occurred while creating the parameter']
        }), 500




@magic_parameter_bp.route('/magic-parameter/<int:id>/edit', methods=['POST'])
@login_required
@permission_required("settings_sections.magic_parameters", "edit")
def magic_parameter_edit(id):
    from models import MagicParameter, ParameterUnit, ParameterStringOption
    parameter = MagicParameter.query.get_or_404(id)
    
    parameter.name = request.form.get('name', '').strip()
    parameter.description = request.form.get('description', '').strip()

    if parameter.param_type == 'date':
        parameter.notify_enabled = 'notify_enabled' in request.form

    if parameter.param_type == 'string':
        string_select_min = request.form.get('string_select_min', 0, type=int)
        string_select_max = request.form.get('string_select_max', 1, type=int)
        errors = []
        if string_select_min < 0:
            errors.append('Minimum selection cannot be negative')
        if string_select_max < 1:
            errors.append('Maximum selection must be at least 1')
        if string_select_min > string_select_max:
            errors.append('Minimum selection cannot exceed maximum selection')
        if errors:
            for error in errors:
                flash(error, 'danger')
            return redirect(url_for('magic_parameter.magic_parameter_manage', id=parameter.id))
        parameter.string_select_min = string_select_min
        parameter.string_select_max = string_select_max
        parameter.string_allow_custom = 'string_allow_custom' in request.form
        parameter.string_regex = request.form.get('string_regex', '').strip() or None
        parameter.string_regex_info = request.form.get('string_regex_info', '').strip() or None

    # Update number validation fields if type is number
    if parameter.param_type == 'number':
        parameter.is_whole_number = 'is_whole_number' in request.form
        number_min = request.form.get('number_min', '')
        number_max = request.form.get('number_max', '')
        number_step = request.form.get('number_step', '')
        number_decimal_places = request.form.get('number_decimal_places', 0, type=int)
        
        # Validation
        errors = []
        if number_min and number_max:
            try:
                min_val = float(number_min)
                max_val = float(number_max)
                if min_val > max_val:
                    errors.append('Min value cannot be greater than max value')
                
                # Check if min/max are whole numbers when is_whole_number is True
                if parameter.is_whole_number:
                    if min_val != int(min_val):
                        errors.append('Minimum value must be a whole number')
                    if max_val != int(max_val):
                        errors.append('Maximum value must be a whole number')
            except ValueError:
                errors.append('Min and max must be valid numbers')
        elif number_min:
            try:
                min_val = float(number_min)
                if parameter.is_whole_number and min_val != int(min_val):
                    errors.append('Minimum value must be a whole number')
            except ValueError:
                errors.append('Min must be a valid number')
        elif number_max:
            try:
                max_val = float(number_max)
                if parameter.is_whole_number and max_val != int(max_val):
                    errors.append('Maximum value must be a whole number')
            except ValueError:
                errors.append('Max must be a valid number')
        
        if number_step:
            try:
                step_val = float(number_step)
                if step_val <= 0:
                    errors.append('Step must be greater than 0')
                # Check if step is a whole number when is_whole_number is True
                if parameter.is_whole_number and step_val != int(step_val):
                    errors.append('Step must be a whole number')
            except ValueError:
                errors.append('Step must be a valid number')
        
        if parameter.is_whole_number and number_decimal_places > 0:
            errors.append('Decimal places should be 0 for whole numbers')
        
        if errors:
            for error in errors:
                flash(error, 'danger')
            return redirect(url_for('magic_parameter.magic_parameter_manage', id=parameter.id))
        
        parameter.number_min = int(float(number_min)) if number_min and parameter.is_whole_number else (float(number_min) if number_min else None)
        parameter.number_max = int(float(number_max)) if number_max and parameter.is_whole_number else (float(number_max) if number_max else None)
        parameter.number_step = int(float(number_step)) if number_step and parameter.is_whole_number else (float(number_step) if number_step else None)
        parameter.number_decimal_places = number_decimal_places if not parameter.is_whole_number else 0
        parameter.number_required = 'number_required' in request.form
    
    db.session.commit()
    
    log_audit(current_user.id, 'update', 'magic_parameter', parameter.id, f'Updated parameter: {parameter.name}')
    flash(f'Magic Parameter "{parameter.name}" updated successfully!', 'success')
    return redirect(url_for('magic_parameter.magic_parameter_manage', id=parameter.id))




@magic_parameter_bp.route('/magic-parameter/<int:id>/manage')
@login_required
@permission_required("settings_sections.magic_parameters", "edit")
def magic_parameter_manage(id):
    from models import MagicParameter
    parameter = MagicParameter.query.get_or_404(id)
    return render_template('magic_parameter_manage.html', parameter=parameter)




@magic_parameter_bp.route('/magic-parameter/<int:id>/add-unit', methods=['POST'])
@login_required
@permission_required("settings_sections.magic_parameters", "edit")
def magic_parameter_add_unit(id):
    from models import MagicParameter, ParameterUnit
    parameter = MagicParameter.query.get_or_404(id)
    
    if parameter.param_type != 'number':
        flash('Units can only be added to Number type parameters!', 'danger')
        return redirect(url_for('magic_parameter.magic_parameter_manage', id=id))
    
    unit = request.form.get('unit', '').strip()
    if not unit:
        flash('Unit cannot be empty!', 'danger')
        return redirect(url_for('magic_parameter.magic_parameter_manage', id=id))
    
    # Check for duplicate
    existing = ParameterUnit.query.filter_by(parameter_id=id, unit=unit).first()
    if existing:
        flash(f'Unit "{unit}" already exists for this parameter!', 'danger')
        return redirect(url_for('magic_parameter.magic_parameter_manage', id=id))
    
    new_unit = ParameterUnit(parameter_id=id, unit=unit)
    db.session.add(new_unit)
    db.session.commit()
    
    flash(f'Unit "{unit}" added successfully!', 'success')
    return redirect(url_for('magic_parameter.magic_parameter_manage', id=id))




@magic_parameter_bp.route('/magic-parameter/<int:id>/delete-unit/<int:unit_id>', methods=['POST'])
@login_required
@permission_required("settings_sections.magic_parameters", "edit")
def magic_parameter_delete_unit(id, unit_id):
    from models import ParameterUnit, ItemParameter
    unit = ParameterUnit.query.get_or_404(unit_id)
    
    if unit.parameter_id != id:
        flash('Invalid unit!', 'danger')
        return redirect(url_for('magic_parameter.magic_parameter_manage', id=id))
    
    # Check if any items use this unit
    items_using = ItemParameter.query.filter_by(parameter_id=id, unit=unit.unit).count()
    if items_using > 0:
        flash(f'Cannot delete unit "{unit.unit}" - it is used by {items_using} item(s)!', 'danger')
        return redirect(url_for('magic_parameter.magic_parameter_manage', id=id))
    
    db.session.delete(unit)
    db.session.commit()
    
    flash(f'Unit "{unit.unit}" deleted successfully!', 'success')
    return redirect(url_for('magic_parameter.magic_parameter_manage', id=id))




@magic_parameter_bp.route('/magic-parameter/<int:id>/add-option', methods=['POST'])
@login_required
@permission_required("settings_sections.magic_parameters", "edit")
def magic_parameter_add_option(id):
    from models import MagicParameter, ParameterStringOption
    parameter = MagicParameter.query.get_or_404(id)
    
    if parameter.param_type != 'string':
        flash('Options can only be added to String type parameters!', 'danger')
        return redirect(url_for('magic_parameter.magic_parameter_manage', id=id))
    
    option = request.form.get('option', '').strip()
    if not option:
        flash('Option cannot be empty!', 'danger')
        return redirect(url_for('magic_parameter.magic_parameter_manage', id=id))
    
    # Check for duplicate
    existing = ParameterStringOption.query.filter_by(parameter_id=id, value=option).first()
    if existing:
        flash(f'Option "{option}" already exists for this parameter!', 'danger')
        return redirect(url_for('magic_parameter.magic_parameter_manage', id=id))
    
    new_option = ParameterStringOption(parameter_id=id, value=option)
    db.session.add(new_option)
    db.session.commit()
    
    flash(f'Option "{option}" added successfully!', 'success')
    return redirect(url_for('magic_parameter.magic_parameter_manage', id=id))




@magic_parameter_bp.route('/magic-parameter/<int:id>/delete-option/<int:option_id>', methods=['POST'])
@login_required
@permission_required("settings_sections.magic_parameters", "edit")
def magic_parameter_delete_option(id, option_id):
    from models import ParameterStringOption, ItemParameter, ItemParameterStringValue
    option = ParameterStringOption.query.get_or_404(option_id)

    if option.parameter_id != id:
        flash('Invalid option!', 'danger')
        return redirect(url_for('magic_parameter.magic_parameter_manage', id=id))

    # Check if any items use this option (legacy field or new multi-select table)
    legacy_count = ItemParameter.query.filter_by(parameter_id=id, string_option=option.value).count()
    param_item_ids = [ip.id for ip in ItemParameter.query.filter_by(parameter_id=id).all()]
    new_count = 0
    if param_item_ids:
        new_count = ItemParameterStringValue.query.filter(
            ItemParameterStringValue.item_parameter_id.in_(param_item_ids),
            ItemParameterStringValue.value == option.value,
            ItemParameterStringValue.is_custom == False
        ).count()
    items_using = legacy_count + new_count
    if items_using > 0:
        flash(f'Cannot delete option "{option.value}" - it is used by {items_using} item(s)!', 'danger')
        return redirect(url_for('magic_parameter.magic_parameter_manage', id=id))
    
    db.session.delete(option)
    db.session.commit()
    
    flash(f'Option "{option.value}" deleted successfully!', 'success')
    return redirect(url_for('magic_parameter.magic_parameter_manage', id=id))




@magic_parameter_bp.route('/magic-parameter/<int:id>/delete', methods=['POST'])
@login_required
@permission_required("settings_sections.magic_parameters", "delete")
def magic_parameter_delete(id):
    from models import MagicParameter
    parameter = MagicParameter.query.get_or_404(id)
    parameter_name = parameter.name
    
    if parameter.item_parameters:
        flash(f'Cannot delete parameter "{parameter_name}" because it is used by {len(parameter.item_parameters)} item(s).', 'danger')
        return redirect(url_for('item.items'))
    
    db.session.delete(parameter)
    db.session.commit()
    
    log_audit(current_user.id, 'delete', 'magic_parameter', id, f'Deleted parameter: {parameter_name}')
    flash(f'Magic Parameter "{parameter_name}" deleted successfully!', 'success')
    return redirect(url_for('magic_parameter.magic_parameters'))




@magic_parameter_bp.route('/api/magic-parameters/<type>')
@login_required
def api_magic_parameters(type):
    """API endpoint to get parameters by type"""
    from models import MagicParameter
    parameters = MagicParameter.query.filter_by(param_type=type).order_by(MagicParameter.name).all()
    
    result = []
    for param in parameters:
        data = {
            'id': param.id,
            'name': param.name,
            'description': param.description,
            'notify_enabled': param.notify_enabled
        }
        
        if type == 'number':
            data['units'] = param.get_units_list()
            data['is_whole_number'] = param.is_whole_number
            data['number_min'] = param.number_min
            data['number_max'] = param.number_max
            data['number_step'] = param.number_step
            data['number_decimal_places'] = param.number_decimal_places
            data['number_required'] = param.number_required
        elif type == 'string':
            data['options'] = param.get_string_options_list()
            data['string_select_min'] = param.string_select_min or 0
            data['string_select_max'] = param.string_select_max if param.string_select_max is not None else 1
            data['string_allow_custom'] = param.string_allow_custom or False
            data['string_regex'] = param.string_regex or ''
            data['string_regex_info'] = param.string_regex_info or ''
        
        result.append(data)
    
    return jsonify(result)


# ============= PARAMETER TEMPLATES =============



@magic_parameter_bp.route('/parameter-template/new', endpoint='parameter_template_new', methods=['GET', 'POST'])
@login_required
@permission_required("settings_sections.magic_parameters", "edit")
def parameter_template_new():
    from models import ParameterTemplate
    
    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        description = request.form.get('description', '').strip()
        
        if not name:
            flash('Template name is required!', 'danger')
            return redirect(url_for('magic_parameter.magic_parameters'))
        
        # Check for duplicate name
        existing = ParameterTemplate.query.filter_by(name=name).first()
        if existing:
            flash(f'Template "{name}" already exists!', 'danger')
            return redirect(url_for('magic_parameter.magic_parameters'))
        
        template = ParameterTemplate(
            name=name,
            description=description
        )
        db.session.add(template)
        db.session.commit()
        
        log_audit(current_user.id, 'create', 'parameter_template', template.id, f'Created template: {template.name}')
        flash(f'Parameter Template "{template.name}" created successfully!', 'success')
        return redirect(url_for('magic_parameter.parameter_template_manage', id=template.id))
    
    return render_template('parameter_template_form.html', title='New Parameter Template')




@magic_parameter_bp.route('/parameter-template/<int:id>/manage')
@login_required
@permission_required("settings_sections.magic_parameters", "edit")
def parameter_template_manage(id):
    from models import ParameterTemplate
    template = ParameterTemplate.query.get_or_404(id)
    return render_template('parameter_template_manage.html', template=template)




@magic_parameter_bp.route('/parameter-template/<int:id>/edit', methods=['GET', 'POST'])
@login_required
@permission_required("settings_sections.magic_parameters", "edit")
def parameter_template_edit(id):
    from models import ParameterTemplate
    template = ParameterTemplate.query.get_or_404(id)
    
    if request.method == 'POST':
        template.name = request.form.get('name', '').strip()
        template.description = request.form.get('description', '').strip()
        
        db.session.commit()
        
        log_audit(current_user.id, 'update', 'parameter_template', template.id, f'Updated template: {template.name}')
        flash(f'Template "{template.name}" updated successfully!', 'success')
        return redirect(url_for('magic_parameter.parameter_template_manage', id=template.id))
    
    return render_template('parameter_template_form.html', template=template, title='Edit Parameter Template')




@magic_parameter_bp.route('/parameter-template/<int:id>/add-parameter', methods=['POST'])
@login_required
@permission_required("settings_sections.magic_parameters", "edit")
def template_add_parameter(id):
    from models import TemplateParameter, MagicParameter, ParameterTemplate
    template = ParameterTemplate.query.get_or_404(id)
    
    # Get form data (same as item_add_parameter)
    param_type = request.form.get('param_type')
    parameter_id = int(request.form.get('parameter_id', 0))
    operation = request.form.get('operation')
    value = request.form.get('value', '').strip()
    value2 = request.form.get('value2', '').strip()
    unit = request.form.get('unit', '').strip()
    string_option = request.form.get('string_option', '').strip()
    description = request.form.get('description', '').strip()
    
    # Validate parameter exists
    parameter = MagicParameter.query.get(parameter_id)
    if not parameter:
        flash('Invalid parameter selected!', 'danger')
        return redirect(url_for('magic_parameter.parameter_template_manage', id=id))
    
    # Get max display order
    max_order = db.session.query(db.func.max(TemplateParameter.display_order)).filter_by(template_id=id).scalar() or 0
    
    # Create new template parameter
    template_param = TemplateParameter(
        template_id=id,
        parameter_id=parameter_id,
        operation=operation if param_type in ['number', 'date'] else None,
        value=value if param_type in ['number', 'date'] else None,
        value2=value2 if operation in ['range', 'duration'] else None,
        unit=unit if param_type == 'number' else None,
        string_option=string_option if param_type == 'string' else None,
        description=description,
        display_order=max_order + 1
    )
    
    db.session.add(template_param)
    db.session.commit()
    
    flash('Parameter added to template successfully!', 'success')
    return redirect(url_for('magic_parameter.parameter_template_manage', id=id))




@magic_parameter_bp.route('/parameter-template/<int:template_id>/delete-parameter/<int:param_id>', methods=['POST'])
@login_required
@permission_required("settings_sections.magic_parameters", "edit")
def template_delete_parameter(template_id, param_id):
    from models import TemplateParameter
    template_param = TemplateParameter.query.get_or_404(param_id)
    
    if template_param.template_id != template_id:
        flash('Invalid parameter!', 'danger')
        return redirect(url_for('magic_parameter.parameter_template_manage', id=template_id))
    
    db.session.delete(template_param)
    db.session.commit()
    
    flash('Parameter removed from template successfully!', 'success')
    return redirect(url_for('magic_parameter.parameter_template_manage', id=template_id))




@magic_parameter_bp.route('/parameter-template/<int:id>/delete', methods=['POST'])
@login_required
@permission_required("settings_sections.magic_parameters", "delete")
def parameter_template_delete(id):
    from models import ParameterTemplate
    template = ParameterTemplate.query.get_or_404(id)
    template_name = template.name
    
    db.session.delete(template)
    db.session.commit()
    
    log_audit(current_user.id, 'delete', 'parameter_template', id, f'Deleted template: {template_name}')
    flash(f'Template "{template_name}" deleted successfully!', 'success')
    return redirect(url_for('magic_parameter.magic_parameters'))




@magic_parameter_bp.route('/api/parameter-templates')
@login_required
def api_parameter_templates():
    """API endpoint to get all parameter templates"""
    from models import ParameterTemplate
    templates = ParameterTemplate.query.order_by(ParameterTemplate.name).all()
    
    result = []
    for template in templates:
        data = {
            'id': template.id,
            'name': template.name,
            'description': template.description,
            'parameters': []
        }
        
        for tp in template.template_parameters:
            param_data = {
                'id': tp.id,
                'parameter_id': tp.parameter_id,
                'param_type': tp.parameter.param_type,
                'operation': tp.operation,
                'value': tp.value,
                'value2': tp.value2,
                'unit': tp.unit,
                'string_option': tp.string_option,
                'description': tp.description,
                'display_text': tp.get_display_text()
            }
            data['parameters'].append(param_data)
        
        result.append(data)
    
    return jsonify(result)




