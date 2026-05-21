"""
QR/Barcode Sticker Template Routes - Blueprint
"""
from flask import Blueprint, render_template, request, jsonify, send_file, redirect, url_for, flash, current_app, abort
from flask_login import login_required, current_user
from models import db, Item, Location, Rack, StickerTemplate, ItemBatch, BatchSerialNumber
from qr_utils import (
    get_item_data, get_location_data, get_rack_data, get_batch_data,
    render_template_to_svg, generate_single_sticker_pdf,
    generate_batch_stickers_pdf, generate_svg_zip, generate_table_sticker_pdf,
    AVAILABLE_PLACEHOLDERS
)
from routes.settings import get_available_fonts
from utils import log_audit, permission_required
from datetime import datetime, timezone
import json
import logging
import re

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
            return jsonify({'status': 'error', 'message': 'Failed to save template.'}), 400
    
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
            return jsonify({'status': 'error', 'message': 'Failed to update template.'}), 400
    
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
            elif template.template_type == 'Location':
                sample_location = Location.query.first()
                if sample_location:
                    data = get_location_data(sample_location)
                else:
                    data = {ph: f'Sample {ph}' for ph in AVAILABLE_PLACEHOLDERS.get('Location', [])}
            elif template.template_type == 'Racks':
                sample_rack = Rack.query.first()
                if sample_rack:
                    data = get_rack_data(sample_rack)
                else:
                    data = {ph: f'Sample {ph}' for ph in AVAILABLE_PLACEHOLDERS.get('Racks', [])}
            elif template.template_type == 'Drawer':
                from qr_utils import get_drawer_data
                sample_rack = Rack.query.first()
                if sample_rack:
                    # Use the first drawer of the sample rack
                    first_drawer = f'R1-C1'
                    data = get_drawer_data(sample_rack, first_drawer)
                else:
                    data = {ph.strip('{}') : f'Sample {ph}' for ph in AVAILABLE_PLACEHOLDERS.get('Drawer', [])}
            elif template.template_type == 'In-Out':
                from models import LendingSession
                from qr_utils import get_session_data
                sample_session = LendingSession.query.first()
                if sample_session:
                    data = get_session_data(sample_session)
                else:
                    data = {ph.strip('{}') : f'Sample {ph}' for ph in AVAILABLE_PLACEHOLDERS.get('In-Out', [])}
            elif template.template_type == 'Item Batch':
                sample_batch = ItemBatch.query.first()
                if sample_batch:
                    data = get_batch_data(sample_batch)
                else:
                    data = {ph.strip('{}') : f'Sample {ph}' for ph in AVAILABLE_PLACEHOLDERS.get('Item Batch', [])}
            else:
                data = {}
        
        svg_data = render_template_to_svg(template, data)
        return jsonify({'svg': svg_data})
    except Exception as e:
        logger.error(f"Error generating preview: {e}")
        return jsonify({'error': 'Failed to generate preview.'}), 400

@qr_template_bp.route('/api/item/<string:uuid>/sticker-preview/<int:template_id>')
@login_required
def api_item_sticker_preview(uuid, template_id):
    """Generate sticker preview for an item"""
    if not current_user.has_permission('settings_sections.qr_templates', 'print_qr'):
        return jsonify({'error': 'Permission denied'}), 403
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
    if not current_user.has_permission('settings_sections.qr_templates', 'print_qr'):
        return jsonify({'error': 'Permission denied'}), 403
    item = Item.query.filter_by(uuid=uuid).first_or_404()
    template = StickerTemplate.query.get_or_404(template_id)
    
    try:
        data = get_item_data(item)
        pdf_data = generate_single_sticker_pdf(template, data, item.uuid)
        return send_file(pdf_data, mimetype='application/pdf', as_attachment=True, 
                        download_name=f'{item.name}_sticker.pdf')
    except Exception as e:
        logger.error(f"Error generating PDF: {e}")
        return jsonify({'error': 'Failed to generate PDF.'}), 400

@qr_template_bp.route('/item/<string:uuid>/qr-sticker')
@login_required
def item_qr_sticker(uuid):
    """View and print QR stickers for an item"""
    if not current_user.has_permission('settings_sections.qr_templates', 'print_qr'):
        abort(403)
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
            flash('Error generating PDF. Please try again.', 'danger')
    
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
        elif element_type == 'icon':
            from qr_utils import generate_icon_svg
            icon_name = data.get('icon_name', '')
            icon_color = data.get('icon_color', '#000000')
            # Scale icon to fit container (80% of minimum dimension)
            icon_size = min(width, height) * 0.8
            svg = generate_icon_svg(icon_name, int(icon_size), icon_color, width, height)
            return jsonify({'svg': svg, 'success': True})
        else:
            return jsonify({'error': 'Unknown element type', 'success': False}), 400
    except Exception as e:
        logger.error(f"Error previewing element: {e}")
        return jsonify({'error': 'Failed to preview element.', 'success': False}), 400

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

@qr_template_bp.route('/api/qr-template/shared-media', methods=['GET'])
@login_required
def api_qr_shared_media():
    """API: List sticker and icon shared files for Picture element media picker."""
    from models import SharedFile
    from flask import url_for
    files = SharedFile.query.filter(
        SharedFile.category.in_(['sticker', 'icon'])
    ).order_by(SharedFile.category, SharedFile.name).all()
    result = []
    for f in files:
        if not f.is_image:
            continue
        result.append({
            'id': f.id,
            'name': f.name,
            'filename': f.filename,
            'category': f.category,
            'url': url_for('share.share_serve', category=f.category, filename=f.filename)
        })
    return jsonify(result)


@qr_template_bp.route('/api/item-thumb-media')
@login_required
def api_item_thumb_media():
    """API: List item + icon share files for item thumbnail Share Files picker."""
    from models import SharedFile
    files = SharedFile.query.filter(
        SharedFile.category.in_(['item', 'icon'])
    ).order_by(SharedFile.category, SharedFile.name).all()
    result = []
    for f in files:
        if not f.is_image:
            continue
        result.append({
            'id': f.id,
            'name': f.name,
            'filename': f.filename,
            'category': f.category,
            'url': url_for('share.share_serve', category=f.category, filename=f.filename)
        })
    return jsonify(result)


@qr_template_bp.route('/api/icons')
def api_get_icons():
    """Return the bundled Bootstrap Icons catalogue (name + class)."""
    import os
    css_path = os.path.join(current_app.root_path, 'static', 'icons', 'bootstrap-icons.css')
    if not os.path.isfile(css_path):
        return jsonify([])
    try:
        with open(css_path, 'r', encoding='utf-8') as f:
            css_content = f.read()
        names = sorted(set(re.findall(r'\.bi-([a-z0-9\-]+):{1,2}before', css_content)))
        return jsonify([{'name': n, 'class': f'bi bi-{n}'} for n in names])
    except Exception as e:
        logger.error(f"Error reading Bootstrap Icons CSS: {e}")
        return jsonify([])



# ─────────────────────────── Item Batch QR sticker routes ───────────────────────────

def _parse_sn_ids(raw):
    """Parse a comma-separated string of SN IDs into a list of ints."""
    ids = []
    for part in (raw or '').split(','):
        part = part.strip()
        if part.isdigit():
            ids.append(int(part))
    return ids


@qr_template_bp.route('/item/<string:uuid>/batch/<int:batch_id>/qr-sticker')
@login_required
def batch_qr_sticker(uuid, batch_id):
    """View and print QR stickers for an item batch (or specific serial numbers)."""
    if not current_user.has_permission('settings_sections.qr_templates', 'print_qr'):
        abort(403)
    item = Item.query.filter_by(uuid=uuid).first_or_404()
    batch = ItemBatch.query.filter_by(id=batch_id, item_id=item.id).first_or_404()
    sn_ids = _parse_sn_ids(request.args.get('sn_ids', ''))
    templates = StickerTemplate.query.filter_by(template_type='Item Batch').all()
    return render_template('batch_qr_sticker.html',
                           item=item, batch=batch,
                           sn_ids=sn_ids,
                           templates=templates)


@qr_template_bp.route('/api/item/<string:uuid>/batch/<int:batch_id>/sticker-preview/<int:template_id>')
@login_required
def api_batch_sticker_preview(uuid, batch_id, template_id):
    """Generate SVG preview for an item batch sticker (optional ?sn_id=)."""
    if not current_user.has_permission('settings_sections.qr_templates', 'print_qr'):
        return jsonify({'error': 'Permission denied'}), 403
    item = Item.query.filter_by(uuid=uuid).first_or_404()
    batch = ItemBatch.query.filter_by(id=batch_id, item_id=item.id).first_or_404()
    template = StickerTemplate.query.get_or_404(template_id)
    if template.template_type != 'Item Batch':
        return jsonify({'error': 'Template must be Item Batch type'}), 400
    sn = None
    sn_id = request.args.get('sn_id', '')
    if sn_id.isdigit():
        sn = BatchSerialNumber.query.filter_by(id=int(sn_id), batch_id=batch.id).first()
    data = get_batch_data(batch, sn)
    svg_data = render_template_to_svg(template, data)
    return jsonify({
        'svg': svg_data,
        'width_mm': template.width_mm,
        'height_mm': template.height_mm,
        'template_name': template.name
    })


@qr_template_bp.route('/api/item/<string:uuid>/batches/sticker-print/<int:template_id>')
@login_required
def api_batch_sticker_print(uuid, template_id):
    """Multi-page PDF: one page per SN (if sn_ids given) or one page for the batch."""
    if not current_user.has_permission('settings_sections.qr_templates', 'print_qr'):
        return jsonify({'error': 'Permission denied'}), 403
    item = Item.query.filter_by(uuid=uuid).first_or_404()
    template = StickerTemplate.query.get_or_404(template_id)
    if template.template_type != 'Item Batch':
        return jsonify({'error': 'Template must be Item Batch type'}), 400
    batch_id = request.args.get('batch_id', '')
    if not batch_id.isdigit():
        return jsonify({'error': 'Invalid batch_id'}), 400
    batch = ItemBatch.query.filter_by(id=int(batch_id), item_id=item.id).first_or_404()
    sn_ids = _parse_sn_ids(request.args.get('sn_ids', ''))
    if sn_ids:
        sns = BatchSerialNumber.query.filter(
            BatchSerialNumber.id.in_(sn_ids),
            BatchSerialNumber.batch_id == batch.id
        ).all()
        records = [(batch, sn) for sn in sns]
    else:
        records = [(batch, None)]
    try:
        output = generate_batch_stickers_pdf(template, records, lambda r: get_batch_data(r[0], r[1]))
        log_audit(current_user.id, 'print', 'item', item.id,
                  f'Printed batch sticker: {template.name} batch {batch.id}')
        return send_file(output, mimetype='application/pdf', as_attachment=True,
                         download_name=f'{item.name}_{batch.get_display_label()}_sticker.pdf')
    except Exception as e:
        logger.error(f"Error generating batch sticker PDF: {e}")
        return jsonify({'error': 'Failed to generate PDF.'}), 500


@qr_template_bp.route('/api/item/<string:uuid>/batches/sticker-svg-zip/<int:template_id>')
@login_required
def api_batch_sticker_svg_zip(uuid, template_id):
    """Download SVG zip for batch stickers."""
    if not current_user.has_permission('settings_sections.qr_templates', 'print_qr'):
        return jsonify({'error': 'Permission denied'}), 403
    item = Item.query.filter_by(uuid=uuid).first_or_404()
    template = StickerTemplate.query.get_or_404(template_id)
    if template.template_type != 'Item Batch':
        return jsonify({'error': 'Template must be Item Batch type'}), 400
    batch_id = request.args.get('batch_id', '')
    if not batch_id.isdigit():
        return jsonify({'error': 'Invalid batch_id'}), 400
    batch = ItemBatch.query.filter_by(id=int(batch_id), item_id=item.id).first_or_404()
    sn_ids = _parse_sn_ids(request.args.get('sn_ids', ''))
    if sn_ids:
        sns = BatchSerialNumber.query.filter(
            BatchSerialNumber.id.in_(sn_ids),
            BatchSerialNumber.batch_id == batch.id
        ).all()
        pairs = [(f'{item.name}_{batch.get_display_label()}_sn{sn.id}', get_batch_data(batch, sn)) for sn in sns]
    else:
        pairs = [(f'{item.name}_{batch.get_display_label()}', get_batch_data(batch))]
    try:
        output = generate_svg_zip(template, pairs)
        return send_file(output, mimetype='application/zip', as_attachment=True,
                         download_name=f'{item.name}_{batch.get_display_label()}_stickers.zip')
    except Exception as e:
        logger.error(f"Error generating batch sticker SVG zip: {e}")
        return jsonify({'error': 'Failed to generate ZIP.'}), 500


@qr_template_bp.route('/api/item/<string:uuid>/batches/sticker-table-print/<int:template_id>')
@login_required
def api_batch_sticker_table_print(uuid, template_id):
    """Grid-layout PDF for batch stickers."""
    if not current_user.has_permission('settings_sections.qr_templates', 'print_qr'):
        return jsonify({'error': 'Permission denied'}), 403
    item = Item.query.filter_by(uuid=uuid).first_or_404()
    template = StickerTemplate.query.get_or_404(template_id)
    if template.template_type != 'Item Batch':
        return jsonify({'error': 'Template must be Item Batch type'}), 400
    batch_id = request.args.get('batch_id', '')
    if not batch_id.isdigit():
        return jsonify({'error': 'Invalid batch_id'}), 400
    batch = ItemBatch.query.filter_by(id=int(batch_id), item_id=item.id).first_or_404()
    sn_ids = _parse_sn_ids(request.args.get('sn_ids', ''))
    if sn_ids:
        sns = BatchSerialNumber.query.filter(
            BatchSerialNumber.id.in_(sn_ids),
            BatchSerialNumber.batch_id == batch.id
        ).all()
        records = [(batch, sn) for sn in sns]
    else:
        records = [(batch, None)]
    options = {
        'paper_w':   float(request.args.get('paper_w',  210)),
        'paper_h':   float(request.args.get('paper_h',  297)),
        'margin_t':  float(request.args.get('margin_t',  10)),
        'margin_b':  float(request.args.get('margin_b',  10)),
        'margin_l':  float(request.args.get('margin_l',  10)),
        'margin_r':  float(request.args.get('margin_r',  10)),
        'spacing_v': float(request.args.get('spacing_v',  3)),
        'spacing_h': float(request.args.get('spacing_h',  3)),
        'border':    request.args.get('border', '0') == '1',
        'border_w':  float(request.args.get('border_w',  0.3)),
        'border_color': request.args.get('border_color', '#000000'),
    }
    try:
        output = generate_table_sticker_pdf(template, records, lambda r: get_batch_data(r[0], r[1]), options)
        return send_file(output, mimetype='application/pdf', as_attachment=True,
                         download_name=f'{item.name}_{batch.get_display_label()}_table.pdf')
    except Exception as e:
        logger.error(f"Error generating batch table sticker PDF: {e}")
        return jsonify({'error': 'Failed to generate PDF.'}), 500
