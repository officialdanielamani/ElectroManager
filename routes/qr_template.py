"""
QR/Barcode Sticker Template Routes - Blueprint
"""
from flask import Blueprint, render_template, request, jsonify, send_file, redirect, url_for, flash
from flask_login import login_required, current_user
from models import db, Item, Location, Rack, StickerTemplate
from qr_utils import (
    get_item_data, get_location_data, get_rack_data,
    render_template_to_svg, generate_single_sticker_pdf,
    generate_batch_stickers_pdf, AVAILABLE_PLACEHOLDERS
)
from routes.settings import get_available_fonts
from utils import log_audit, permission_required
from datetime import datetime, timezone
import json
import logging

logger = logging.getLogger(__name__)

qr_template_bp = Blueprint('qr_template', __name__)

@qr_template_bp.route('/settings/qr', methods=['GET'], endpoint='settings_qr')
@login_required
@permission_required('settings_sections.qr_templates', 'view')
def settings_qr():
    """QR/Sticker template list page"""
    templates = StickerTemplate.query.all()
    
    # Check permissions for actions
    can_edit = current_user.has_permission('settings_sections.qr_templates', 'edit')
    can_delete = current_user.has_permission('settings_sections.qr_templates', 'delete')
    
    return render_template('settings_qr.html', templates=templates, can_edit=can_edit, can_delete=can_delete)

@qr_template_bp.route('/settings/qr/new', methods=['GET', 'POST'], endpoint='create_qr_template')
@login_required
@permission_required('settings_sections.qr_templates', 'edit')
def create_qr_template():
    """Create new template"""
    if request.method == 'POST':
        try:
            template_type = request.form.get('template_type')
            name = request.form.get('name')
            width_mm = float(request.form.get('width_mm', 30))
            height_mm = float(request.form.get('height_mm', 20))
            
            if not template_type or not name:
                flash('Template type and name are required', 'danger')
                return redirect(url_for('qr_template.create_qr_template'))
            
            # Validate size: min 5mm, max 500mm
            if width_mm < 5 or width_mm > 500:
                flash('Width must be between 5mm and 500mm', 'danger')
                return redirect(url_for('qr_template.create_qr_template'))
            
            if height_mm < 5 or height_mm > 500:
                flash('Height must be between 5mm and 500mm', 'danger')
                return redirect(url_for('qr_template.create_qr_template'))
            
            template = StickerTemplate(
                name=name,
                template_type=template_type,
                width_mm=width_mm,
                height_mm=height_mm,
                created_by=current_user.id,
                layout=json.dumps([])
            )
            db.session.add(template)
            db.session.commit()
            
            flash(f'Template "{name}" created!', 'success')
            return redirect(url_for('qr_template.edit_qr_template', template_id=template.id))
        except ValueError:
            flash('Invalid width or height value', 'danger')
            return redirect(url_for('qr_template.create_qr_template'))
        except Exception as e:
            logger.error(f"Error creating template: {e}")
            flash('Error creating template', 'danger')
            return redirect(url_for('qr_template.create_qr_template'))
    
    return render_template('qr_template_form.html')

@qr_template_bp.route('/settings/qr/<int:template_id>/edit', methods=['GET'], endpoint='edit_qr_template')
@login_required
@permission_required('settings_sections.qr_templates', 'edit')
def edit_qr_template(template_id):
    """Open canvas editor"""
    template = StickerTemplate.query.get_or_404(template_id)
    placeholders = AVAILABLE_PLACEHOLDERS.get(template.template_type, [])
    return render_template('qr_template_editor.html', template=template, placeholders=placeholders)

@qr_template_bp.route('/api/qr-template/<int:template_id>', methods=['GET', 'POST', 'PUT'])
@login_required
@permission_required('settings_sections.qr_templates', 'edit')
def api_qr_template(template_id):
    """API: Get/Update template layout"""
    template = StickerTemplate.query.get_or_404(template_id)
    
    if request.method == 'POST':
        try:
            data = request.get_json()
            template.set_layout(data.get('layout', []))
            template.updated_at = datetime.now(timezone.utc)
            template.updated_by = current_user.id
            db.session.commit()
            return jsonify({'status': 'success'})
        except Exception as e:
            logger.error(f"Error saving template: {e}")
            return jsonify({'status': 'error', 'message': str(e)}), 400
    
    elif request.method == 'PUT':
        try:
            data = request.get_json()
            new_width = float(data.get('width_mm', template.width_mm))
            new_height = float(data.get('height_mm', template.height_mm))
            
            # Validate size: min 5mm, max 500mm
            if new_width < 5 or new_width > 500:
                return jsonify({'status': 'error', 'message': 'Width must be between 5mm and 500mm'}), 400
            
            if new_height < 5 or new_height > 500:
                return jsonify({'status': 'error', 'message': 'Height must be between 5mm and 500mm'}), 400
            
            template.name = data.get('name', template.name)
            template.width_mm = new_width
            template.height_mm = new_height
            template.set_layout(data.get('layout', template.get_layout()))
            template.updated_at = datetime.now(timezone.utc)
            template.updated_by = current_user.id
            db.session.commit()
            
            log_audit(current_user.id, 'update', 'sticker_template', template_id,
                     f'Updated template settings: name={template.name}, size={template.width_mm}x{template.height_mm}mm')
            
            return jsonify({'status': 'success'})
        except ValueError:
            return jsonify({'status': 'error', 'message': 'Invalid width or height value'}), 400
        except Exception as e:
            logger.error(f"Error updating template: {e}")
            return jsonify({'status': 'error', 'message': str(e)}), 400
    
    return jsonify({
        'id': template.id,
        'name': template.name,
        'type': template.template_type,
        'width_mm': template.width_mm,
        'height_mm': template.height_mm,
        'layout': template.get_layout(),
        'dpi': 96,
        'placeholders': AVAILABLE_PLACEHOLDERS.get(template.template_type, []),
        'available_fonts': get_available_fonts()
    })

@qr_template_bp.route('/api/qr-template/<int:template_id>/preview', methods=['POST', 'GET'])
@login_required
def preview_qr_template(template_id):
    """Preview template with sample data or unresolved placeholders"""
    try:
        template = StickerTemplate.query.get_or_404(template_id)
        
        # Check if unresolved placeholders requested (for settings preview)
        unresolved = request.args.get('unresolved', '').lower() == 'true'
        
        if unresolved:
            # Show literal unresolved placeholders like {ItemUUID}
            placeholders = AVAILABLE_PLACEHOLDERS.get(template.template_type, [])
            data = {ph: f'{{{ph}}}' for ph in placeholders}
        else:
            # Get sample data based on template type
            if template.template_type == 'Items':
                sample_item = Item.query.first()
                if sample_item:
                    data = get_item_data(sample_item)
                else:
                    data = {ph: f'Sample {ph}' for ph in AVAILABLE_PLACEHOLDERS.get('Items', [])}
            elif template.template_type == 'Locations':
                sample_location = Location.query.first()
                if sample_location:
                    data = get_location_data(sample_location)
                else:
                    data = {ph: f'Sample {ph}' for ph in AVAILABLE_PLACEHOLDERS.get('Locations', [])}
            elif template.template_type == 'Racks':
                sample_rack = Rack.query.first()
                if sample_rack:
                    data = get_rack_data(sample_rack)
                else:
                    data = {ph: f'Sample {ph}' for ph in AVAILABLE_PLACEHOLDERS.get('Racks', [])}
            else:
                data = {}
        
        svg_data = render_template_to_svg(template, data)
        return jsonify({'svg': svg_data})
    except Exception as e:
        logger.error(f"Error generating preview: {e}")
        return jsonify({'error': str(e)}), 400

@qr_template_bp.route('/api/item/<string:uuid>/sticker-preview/<int:template_id>')
@login_required
def api_item_sticker_preview(uuid, template_id):
    """Generate sticker preview for an item"""
    item = Item.query.filter_by(uuid=uuid).first_or_404()
    template = StickerTemplate.query.get_or_404(template_id)
    
    if template.template_type != 'Items':
        return jsonify({'error': 'Template must be for Items'}), 400
    
    data = get_item_data(item)
    svg_data = render_template_to_svg(template, data)
    
    return jsonify({
        'svg': svg_data,
        'width_mm': template.width_mm,
        'height_mm': template.height_mm,
        'template_name': template.name
    })

@qr_template_bp.route('/api/item/<string:uuid>/sticker-print/<int:template_id>')
@login_required
def api_item_sticker_print(uuid, template_id):
    """Generate printable sticker PDF"""
    item = Item.query.filter_by(uuid=uuid).first_or_404()
    template = StickerTemplate.query.get_or_404(template_id)
    
    try:
        data = get_item_data(item)
        pdf_data = generate_single_sticker_pdf(template, data, item.uuid)
        return send_file(pdf_data, mimetype='application/pdf', as_attachment=True, 
                        download_name=f'{item.name}_sticker.pdf')
    except Exception as e:
        logger.error(f"Error generating PDF: {e}")
        return jsonify({'error': str(e)}), 400

@qr_template_bp.route('/item/<string:uuid>/qr-sticker')
@login_required
def item_qr_sticker(uuid):
    """View and print QR stickers for an item"""
    item = Item.query.filter_by(uuid=uuid).first_or_404()
    templates = StickerTemplate.query.filter_by(template_type='Items').all()
    return render_template('item_qr_sticker.html', item=item, templates=templates)

@qr_template_bp.route('/qr-template/<int:template_id>/print', methods=['GET', 'POST'])
@login_required
def print_qr_template(template_id):
    """Batch print stickers using a template"""
    template = StickerTemplate.query.get_or_404(template_id)
    
    if request.method == 'POST':
        try:
            item_ids = request.form.getlist('item_ids')
            items = Item.query.filter(Item.id.in_(item_ids)).all()
            
            if not items:
                flash('No items selected', 'danger')
                return redirect(url_for('qr_template.print_qr_template', template_id=template_id))
            
            pdf_data = generate_batch_stickers_pdf(template, items, get_item_data)
            return send_file(pdf_data, mimetype='application/pdf', as_attachment=True,
                           download_name=f'stickers_{template.name}.pdf')
        except Exception as e:
            logger.error(f"Error generating batch PDF: {e}")
            flash(f'Error generating PDF: {str(e)}', 'danger')
    
    return render_template('qr_template_print.html', template=template)

@qr_template_bp.route('/api/qr-template/<int:template_id>/preview-element', methods=['POST'])
@login_required
def preview_element(template_id):
    """Preview a single QR/Barcode element with canvas content"""
    try:
        template = StickerTemplate.query.get_or_404(template_id)
        data = request.get_json()
        element_type = data.get('type')
        content = data.get('content', '')
        
        # Get dimensions from canvas (in mm) and convert to px
        width_mm = data.get('width_mm', 10)
        height_mm = data.get('height_mm', 10)
        mm_to_px = data.get('mm_to_px', 24.6)  # Standard 96 DPI / 4
        
        # Convert mm to px using the MM_TO_PX from canvas
        width = int(width_mm * mm_to_px)
        height = int(height_mm * mm_to_px)
        
        # Get barcode properties
        show_label = data.get('show_label', False)
        barcode_format = data.get('format', 'CODE128')
        
        # Use content as-is from canvas (may contain placeholders or actual data)
        preview_content = content if content else 'Sample'
        
        if element_type == 'qr':
            from qr_utils import generate_qr_svg
            error_correction = data.get('error_correction', 'M')
            svg = generate_qr_svg(preview_content, width, height, error_correction)
            return jsonify({'svg': svg, 'success': True})
        elif element_type == 'barcode':
            from qr_utils import generate_barcode_svg
            svg = generate_barcode_svg(preview_content, barcode_format, width, height, show_label)
            return jsonify({'svg': svg, 'success': True})
        else:
            return jsonify({'error': 'Unknown element type', 'success': False}), 400
    except Exception as e:
        logger.error(f"Error previewing element: {e}")
        return jsonify({'error': str(e), 'success': False}), 400

@qr_template_bp.route('/settings/qr/<int:template_id>/delete', methods=['POST'])
@login_required
@permission_required('settings_sections.qr_templates', 'delete')
def delete_qr_template(template_id):
    """Delete template"""
    try:
        template = StickerTemplate.query.get_or_404(template_id)
        name = template.name
        db.session.delete(template)
        db.session.commit()
        
        log_audit(current_user.id, 'delete', 'sticker_template', template_id, 
                 f'Deleted template: {name}')
        
        flash(f'Template "{name}" deleted.', 'success')
        return redirect(url_for('qr_template.settings_qr'))
    except Exception as e:
        logger.error(f"Error deleting template: {e}")
        flash('Error deleting template', 'danger')
        return redirect(url_for('qr_template.settings_qr'))


@qr_template_bp.route('/api/available-fonts')
def api_available_fonts():
    """Get list of available fonts (system + project)"""
    return jsonify(get_available_fonts())
