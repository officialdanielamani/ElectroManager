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
from collections import defaultdict, deque
import threading
import time
import json
import logging
import re

logger = logging.getLogger(__name__)

# ── Real-time collaboration for sticker editor ────────────────────
_STICKER_PRESENCE_TTL = 12
_stk_lock = threading.Lock()
_sticker_presence: dict = defaultdict(dict)   # template_id -> {user_id: {...}}
_sticker_events: dict   = defaultdict(deque)  # template_id -> deque[(ts, event)]
_MAX_STICKER_EVENTS = 200

def _stk_push_event(template_id: int, event: dict):
    with _stk_lock:
        q = _sticker_events[template_id]
        q.append((time.time(), event))
        while len(q) > _MAX_STICKER_EVENTS:
            q.popleft()

def _stk_collect_events_since(template_id: int, since_ts: float) -> list:
    with _stk_lock:
        return [ev for ts, ev in _sticker_events[template_id] if ts > since_ts]

def _stk_collect_presence(template_id: int) -> list:
    now = time.time()
    with _stk_lock:
        stale = [uid for uid, p in _sticker_presence[template_id].items()
                 if now - p['last_seen'] > _STICKER_PRESENCE_TTL]
        for uid in stale:
            del _sticker_presence[template_id][uid]
        return list(_sticker_presence[template_id].values())

qr_template_bp = Blueprint('qr_template', __name__)

def _can_print_qr():
    """Check if current user can print QR stickers (via sticker.view_manage or legacy qr_templates.print_qr)."""
    return (current_user.has_permission('sticker', 'view_manage') or
            current_user.has_permission('settings_sections.qr_templates', 'print_qr'))



@qr_template_bp.route('/sticker', methods=['GET'], endpoint='sticker_list')
@login_required
def sticker_list():
    """Per-user sticker list — shows own + shared stickers."""
    if not current_user.has_permission('sticker', 'view_manage'):
        abort(403)
    uid = current_user.id
    # Own templates
    own = StickerTemplate.query.filter_by(owner_id=uid).all()
    # Shared with me (view or edit)
    all_templates = StickerTemplate.query.filter(StickerTemplate.owner_id != uid).all()
    shared = [t for t in all_templates if
              any(u.get('id') == uid for u in t.get_share_view_users()) or
              any(u.get('id') == uid for u in t.get_share_edit_users()) or
              t.is_public]
    can_create = current_user.has_permission('sticker', 'view_manage')
    return render_template('sticker_list.html', own_templates=own, shared_templates=shared,
                           can_create=can_create)


@qr_template_bp.route('/sticker/new', methods=['GET', 'POST'], endpoint='create_sticker')
@login_required
def create_sticker():
    """Create new sticker template (owned by current user)."""
    if not current_user.has_permission('sticker', 'view_manage'):
        abort(403)
    if request.method == 'POST':
        try:
            template_type = request.form.get('template_type')
            name = request.form.get('name')
            width_mm = float(request.form.get('width_mm', 30))
            height_mm = float(request.form.get('height_mm', 20))

            if not template_type or not name:
                flash('Template type and name are required', 'danger')
                return redirect(url_for('qr_template.create_sticker'))

            if width_mm < 5 or width_mm > 500:
                flash('Width must be between 5mm and 500mm', 'danger')
                return redirect(url_for('qr_template.create_sticker'))

            if height_mm < 5 or height_mm > 500:
                flash('Height must be between 5mm and 500mm', 'danger')
                return redirect(url_for('qr_template.create_sticker'))

            template = StickerTemplate(
                name=name,
                template_type=template_type,
                width_mm=width_mm,
                height_mm=height_mm,
                owner_id=current_user.id,
                created_by=current_user.id,
                layout=json.dumps([])
            )
            db.session.add(template)
            db.session.commit()

            flash(f'Sticker template "{name}" created!', 'success')
            return redirect(url_for('qr_template.edit_sticker', template_id=template.id))
        except ValueError:
            flash('Invalid width or height value', 'danger')
            return redirect(url_for('qr_template.create_sticker'))
        except Exception as e:
            logger.error(f"Error creating sticker template: {e}")
            flash('Error creating template', 'danger')
            return redirect(url_for('qr_template.create_sticker'))

    return render_template('qr_template_form.html', back_url=url_for('qr_template.sticker_list'))




@qr_template_bp.route('/sticker/<int:template_id>/edit', methods=['GET'], endpoint='edit_sticker')
@login_required
def edit_sticker(template_id):
    """Open canvas editor for a sticker template (owner or shared-edit or admin)."""
    template = StickerTemplate.query.get_or_404(template_id)
    if not template.can_edit(current_user):
        abort(403)
    placeholders = AVAILABLE_PLACEHOLDERS.get(template.template_type, [])
    is_owner = template.owner_id == current_user.id
    can_share = current_user.has_permission('sticker', 'share_sticker') and is_owner
    return render_template('qr_template_editor.html', template=template, placeholders=placeholders,
                           can_share=can_share, is_owner=is_owner,
                           back_url=url_for('qr_template.sticker_list'))




@qr_template_bp.route('/sticker/<int:template_id>/sharing', methods=['POST'], endpoint='sticker_sharing')
@login_required
def sticker_sharing(template_id):
    """Save sharing settings for a sticker template."""
    template = StickerTemplate.query.get_or_404(template_id)
    if template.owner_id != current_user.id:
        return jsonify({'status': 'error', 'message': 'Only the owner can change sharing settings'}), 403
    if not current_user.has_permission('sticker', 'share_sticker'):
        return jsonify({'status': 'error', 'message': 'No permission to share stickers'}), 403
    data = request.get_json()
    template.is_public = bool(data.get('is_public', False))
    view_users = data.get('share_view_users', [])
    edit_users = data.get('share_edit_users', [])
    # Limit to 20 shared users per list (same guard as Kanban)
    template.share_view_users = json.dumps(view_users[:20])
    template.share_edit_users = json.dumps(edit_users[:20])
    template.updated_at = datetime.now(timezone.utc)
    template.updated_by = current_user.id
    db.session.commit()
    log_audit(current_user.id, 'update', 'sticker_template', template_id,
              f'Updated sharing settings: public={template.is_public}')
    return jsonify({'status': 'success'})

@qr_template_bp.route('/sticker/<int:template_id>/presence', methods=['POST'], endpoint='sticker_presence')
@login_required
def sticker_presence(template_id):
    """Heartbeat: record current user's presence and which layer/field they are editing."""
    template = StickerTemplate.query.get_or_404(template_id)
    if not template.can_view(current_user):
        return jsonify({'error': 'Permission denied'}), 403
    data = request.get_json(silent=True) or {}
    name = current_user.name or current_user.username
    is_owner = template.owner_id == current_user.id
    can_edit = template.can_edit(current_user)
    access = 'edit' if can_edit else 'view'
    pic_url = ''
    if current_user.profile_photo:
        if current_user.profile_photo.startswith('share/'):
            pic_url = f"/uploads/share/profile/{current_user.profile_photo[6:]}"
        else:
            pic_url = f"/uploads/userpicture/{current_user.profile_photo}"
    with _stk_lock:
        _sticker_presence[template_id][current_user.id] = {
            'id': current_user.id,
            'name': name,
            'last_seen': time.time(),
            'editing_layer_idx': data.get('editing_layer_idx'),
            'editing_field': data.get('editing_field'),
            'access': access,
            'is_owner': is_owner,
            'pic': pic_url,
        }
    return jsonify({'ok': True})


@qr_template_bp.route('/sticker/<int:template_id>/poll', methods=['GET'], endpoint='sticker_poll')
@login_required
def sticker_poll(template_id):
    """Poll for presence and events since a given timestamp."""
    template = StickerTemplate.query.get_or_404(template_id)
    if not template.can_view(current_user):
        return jsonify({'error': 'Permission denied'}), 403
    since = request.args.get('since', type=float, default=0.0)
    return jsonify({
        'presence': _stk_collect_presence(template_id),
        'events':   _stk_collect_events_since(template_id, since),
        'ts':       time.time(),
    })


@qr_template_bp.route('/api/sticker-users', methods=['GET'])
@login_required
def api_sticker_users():
    """Return all active users for sticker sharing search (same shape as /kanban/contacts)."""
    from models import User
    users = User.query.filter_by(is_active=True).order_by(User.username).all()
    result = []
    for u in users:
        if u.id == current_user.id:
            continue
        pic = ''
        if u.profile_photo:
            if u.profile_photo.startswith('share/'):
                pic = f"/uploads/share/profile/{u.profile_photo[6:]}"
            else:
                pic = f"/uploads/userpicture/{u.profile_photo}"
        result.append({
            'id': u.id,
            'type': 'user',
            'label': u.username,
            'extra': u.name or '',
            'pic': pic,
        })
    return jsonify(result)


@qr_template_bp.route('/api/qr-template/<int:template_id>', methods=['GET', 'POST', 'PUT'])
@login_required
def api_qr_template(template_id):
    """API: Get/Update template layout"""
    template = StickerTemplate.query.get_or_404(template_id)
    if not template.can_edit(current_user):
        return jsonify({'status': 'error', 'message': 'Permission denied'}), 403
    
    if request.method == 'POST':
        try:
            data = request.get_json()
            new_layout = data.get('layout', [])
            template.set_layout(new_layout)
            template.updated_at = datetime.now(timezone.utc)
            template.updated_by = current_user.id
            db.session.commit()
            _stk_push_event(template_id, {
                'type': 'layout_saved',
                'user_id': current_user.id,
                'user_name': current_user.name or current_user.username,
                'layout': new_layout,
                'ts': time.time(),
            })
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
        if not template.can_view(current_user):
            return jsonify({'error': 'Permission denied'}), 403
        
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
    if not _can_print_qr():
        return jsonify({'error': 'Permission denied'}), 403
    item = Item.query.filter_by(uuid=uuid).first_or_404()
    template = StickerTemplate.query.get_or_404(template_id)
    if not template.can_view(current_user):
        return jsonify({'error': 'Permission denied'}), 403
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
    if not _can_print_qr():
        return jsonify({'error': 'Permission denied'}), 403
    item = Item.query.filter_by(uuid=uuid).first_or_404()
    template = StickerTemplate.query.get_or_404(template_id)
    if not template.can_view(current_user):
        return jsonify({'error': 'Permission denied'}), 403
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
    if not _can_print_qr():
        abort(403)
    item = Item.query.filter_by(uuid=uuid).first_or_404()
    all_t = StickerTemplate.query.filter_by(template_type='Items').all()
    templates = [t for t in all_t if t.can_view(current_user)]
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

@qr_template_bp.route('/sticker/<int:template_id>/delete', methods=['POST'], endpoint='delete_sticker')
@login_required
def delete_sticker(template_id):
    """Delete sticker template (owner or admin)."""
    template = StickerTemplate.query.get_or_404(template_id)
    if template.owner_id != current_user.id and not current_user.has_permission('settings_sections.qr_templates', 'delete'):
        abort(403)
    try:
        name = template.name
        db.session.delete(template)
        db.session.commit()
        log_audit(current_user.id, 'delete', 'sticker_template', template_id,
                  f'Deleted sticker template: {name}')
        flash(f'Sticker template "{name}" deleted.', 'success')
        return redirect(url_for('qr_template.sticker_list'))
    except Exception as e:
        logger.error(f"Error deleting sticker template: {e}")
        flash('Error deleting template', 'danger')
        return redirect(url_for('qr_template.sticker_list'))




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
    if not _can_print_qr():
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
    if not _can_print_qr():
        return jsonify({'error': 'Permission denied'}), 403
    item = Item.query.filter_by(uuid=uuid).first_or_404()
    batch = ItemBatch.query.filter_by(id=batch_id, item_id=item.id).first_or_404()
    template = StickerTemplate.query.get_or_404(template_id)
    if not template.can_view(current_user):
        return jsonify({'error': 'Permission denied'}), 403
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
    if not _can_print_qr():
        return jsonify({'error': 'Permission denied'}), 403
    item = Item.query.filter_by(uuid=uuid).first_or_404()
    template = StickerTemplate.query.get_or_404(template_id)
    if not template.can_view(current_user):
        return jsonify({'error': 'Permission denied'}), 403
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
    if not _can_print_qr():
        return jsonify({'error': 'Permission denied'}), 403
    item = Item.query.filter_by(uuid=uuid).first_or_404()
    template = StickerTemplate.query.get_or_404(template_id)
    if not template.can_view(current_user):
        return jsonify({'error': 'Permission denied'}), 403
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
    if not _can_print_qr():
        return jsonify({'error': 'Permission denied'}), 403
    item = Item.query.filter_by(uuid=uuid).first_or_404()
    template = StickerTemplate.query.get_or_404(template_id)
    if not template.can_view(current_user):
        return jsonify({'error': 'Permission denied'}), 403
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
