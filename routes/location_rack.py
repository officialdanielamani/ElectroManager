"""
Location Rack Routes Blueprint
"""
from flask import Blueprint, render_template, redirect, url_for, flash, request, jsonify, send_file, abort, current_app, send_from_directory
from flask_login import login_required, current_user, login_user, logout_user
from models import db, User, Category, Item, Attachment, Rack, Footprint, Tag, Setting, Location, AuditLog, StickerTemplate, ItemBatch
from forms import (LoginForm, RegistrationForm, CategoryForm, ItemAddForm, ItemEditForm, AttachmentForm, 
                   SearchForm, UserForm, MagicParameterForm, ParameterUnitForm, ParameterStringOptionForm, ItemParameterForm)
from helpers import is_safe_url, format_currency, is_safe_file_path
from utils import save_file, log_audit, admin_required, permission_required, item_permission_required, format_file_size, allowed_file
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename, safe_join
from datetime import datetime, timezone
from urllib.parse import urlparse, urljoin
import os
import json
import re
import secrets
import string
import logging

_COLOR_RE = re.compile(r'^#[0-9A-Fa-f]{6}$')

def _sanitize_color(value, default='#6c757d'):
    """Return value if valid hex color, else default."""
    v = (value or '').strip()
    return v if _COLOR_RE.match(v) else default

def _sanitize_name(value, max_len=128):
    """Strip and truncate a name field."""
    return (value or '').strip()[:max_len]

logger = logging.getLogger(__name__)

location_rack_bp = Blueprint('location_rack', __name__)


@location_rack_bp.route('/location-management', endpoint='location_management')
@login_required
def location_management():
    """Combined location and rack management page"""
    # Check if user has view permission for location settings (not visual_storage)
    if not current_user.has_permission('settings_sections.location_management', 'view'):
        # Check if user has visual storage access and redirect there instead
        if current_user.has_permission('pages.visual_storage', 'view'):
            flash('You do not have permission to manage racks. You can only view them in Visual Storage.', 'warning')
            return redirect(url_for('visual_storage.visual_storage'))
        else:
            flash('You do not have permission to view location management settings.', 'danger')
            return redirect(url_for('settings.settings'))
    
    from models import Location
    locations = Location.query.order_by(Location.name).all()
    racks = Rack.query.order_by(Rack.name).all()
    
    can_edit = current_user.has_permission('settings_sections.location_management', 'edit')
    can_delete = current_user.has_permission('settings_sections.location_management', 'delete')
    
    return render_template('location_management.html', 
                          locations=locations,
                          racks=racks,
                          can_edit=can_edit,
                          can_delete=can_delete)



@location_rack_bp.route('/location/<string:uuid>', endpoint='location_detail')
@login_required
def location_detail(uuid):
    """View location details with items and racks"""
    from models import Location
    location = Location.query.filter_by(uuid=uuid).first_or_404()
    items = location.items
    racks = location.racks
    return render_template('location_detail.html', 
                          location=location,
                          items=items,
                          racks=racks)



@location_rack_bp.route('/location/new', endpoint='location_new', methods=['GET', 'POST'])
@login_required
@permission_required("settings_sections.location_management", "edit")
def location_new():
    """Create new location"""
    from models import Location
    from forms import LocationForm
    from werkzeug.utils import secure_filename
    
    form = LocationForm()
    
    if form.validate_on_submit():
        location = Location(
            name=form.name.data,
            info=form.info.data,
            description=form.description.data,
            color=form.color.data or '#6c757d'
        )
        
        # Add and commit location first to generate UUID
        db.session.add(location)
        db.session.commit()
        
        # Handle share icon file selection (takes priority over upload)
        share_icon = request.form.get('share_icon_file', '').strip()
        if share_icon and not form.picture.data:
            location.picture = f'share/icon/{share_icon}'
            db.session.commit()
        elif form.picture.data:
            # Handle picture upload with UUID-based path structure
            file = form.picture.data
            max_size_mb = 10
            max_size_bytes = max_size_mb * 1024 * 1024
            file.seek(0, 2)
            file_size = file.tell()
            file.seek(0)
            if file_size > max_size_bytes:
                flash('Location/rack pictures must be smaller than 10MB.', 'danger')
                db.session.delete(location)
                db.session.commit()
                return render_template('location_form.html', form=form, location=None)
            if file.filename and allowed_file(file.filename):
                ext = file.filename.rsplit('.', 1)[1].lower()
                if ext not in ['png', 'jpg', 'jpeg', 'webp']:
                    flash('Only PNG, JPEG, and WebP images are allowed.', 'danger')
                    db.session.delete(location)
                    db.session.commit()
                    return render_template('location_form.html', form=form, location=None)
                if ext == 'jpg':
                    ext = 'jpeg'
                filename = f"{location.uuid}.{ext}"
                location_dir = os.path.join(current_app.config['UPLOAD_FOLDER'], 'locations', location.uuid)
                os.makedirs(location_dir, exist_ok=True)
                for old_ext in ['png', 'jpeg', 'webp']:
                    old_f = os.path.join(location_dir, f"{location.uuid}.{old_ext}")
                    if old_f != os.path.join(location_dir, filename) and os.path.exists(old_f):
                        os.remove(old_f)
                file.save(os.path.join(location_dir, filename))
                location.picture = f"{location.uuid}/{filename}"
                db.session.commit()

        log_audit(current_user.id, 'create', 'location', location.id, f'Created location: {location.name}')
        flash(f'Location "{location.name}" created successfully!', 'success')
        return redirect(url_for('location_rack.location_management'))
    
    from models import SharedFile
    max_file_size_mb = int(Setting.get('max_file_size_mb', '10'))
    icon_share_files = SharedFile.query.filter_by(category='icon').order_by(SharedFile.created_at.desc()).all()
    return render_template('location_form.html', form=form, location=None,
                           max_file_size_mb=max_file_size_mb, icon_share_files=icon_share_files)



@location_rack_bp.route('/location/<string:uuid>/edit', endpoint='location_edit', methods=['GET', 'POST'])
@login_required
@permission_required("settings_sections.location_management", "edit")
def location_edit(uuid):
    """Edit location"""
    from models import Location
    from forms import LocationForm
    from werkzeug.utils import secure_filename
    
    location = Location.query.filter_by(uuid=uuid).first_or_404()
    form = LocationForm(obj=location)
    
    if form.validate_on_submit():
        location.name = form.name.data
        location.info = form.info.data
        location.description = form.description.data
        location.color = form.color.data or '#6c757d'
        
        # Handle picture deletion
        if request.form.get('delete_picture'):
            if location.picture and not location.picture.startswith('share/'):
                old_path = os.path.join(current_app.config['UPLOAD_FOLDER'], 'locations', location.picture)
                if is_safe_file_path(old_path) and os.path.exists(old_path):
                    os.remove(old_path)
            location.picture = None

        # Handle share icon file selection (takes priority over upload)
        share_icon = request.form.get('share_icon_file', '').strip()
        if share_icon and not form.picture.data:
            location.picture = f'share/icon/{share_icon}'
        elif form.picture.data:
            file = form.picture.data
            if hasattr(file, 'filename') and file.filename and allowed_file(file.filename):
                max_size_mb = 10
                max_size_bytes = max_size_mb * 1024 * 1024
                file.seek(0, 2)
                file_size = file.tell()
                file.seek(0)
                if file_size > max_size_bytes:
                    flash('Location/rack pictures must be smaller than 10MB.', 'danger')
                    return render_template('location_form.html', form=form, location=location)
                ext = file.filename.rsplit('.', 1)[1].lower()
                if ext not in ['png', 'jpg', 'jpeg', 'webp']:
                    flash('Only PNG, JPEG, and WebP images are allowed.', 'danger')
                    return render_template('location_form.html', form=form, location=location)
                if location.picture and not location.picture.startswith('share/'):
                    old_path = os.path.join(current_app.config['UPLOAD_FOLDER'], 'locations', location.picture)
                    if is_safe_file_path(old_path) and os.path.exists(old_path):
                        os.remove(old_path)
                if ext == 'jpg':
                    ext = 'jpeg'
                filename = f"{location.uuid}.{ext}"
                location_dir = os.path.join(current_app.config['UPLOAD_FOLDER'], 'locations', location.uuid)
                os.makedirs(location_dir, exist_ok=True)
                for old_ext in ['png', 'jpeg', 'webp']:
                    old_f = os.path.join(location_dir, f"{location.uuid}.{old_ext}")
                    if old_f != os.path.join(location_dir, filename) and os.path.exists(old_f):
                        os.remove(old_f)
                file.save(os.path.join(location_dir, filename))
                location.picture = f"{location.uuid}/{filename}"

        db.session.commit()

        log_audit(current_user.id, 'update', 'location', location.id, f'Updated location: {location.name}')
        flash(f'Location "{location.name}" updated successfully!', 'success')
        return redirect(url_for('location_rack.location_detail', uuid=location.uuid))

    from models import SharedFile
    max_file_size_mb = int(Setting.get('max_file_size_mb', '10'))
    icon_share_files = SharedFile.query.filter_by(category='icon').order_by(SharedFile.created_at.desc()).all()
    return render_template('location_form.html', form=form, location=location,
                           max_file_size_mb=max_file_size_mb, icon_share_files=icon_share_files)



@location_rack_bp.route('/location/<string:uuid>/delete', endpoint='location_delete', methods=['POST'])
@login_required
@permission_required("settings_sections.location_management", "delete")
def location_delete(uuid):
    """Delete location"""
    from models import Location
    
    location = Location.query.filter_by(uuid=uuid).first_or_404()
    
    # Check if location is in use
    if location.items or location.racks:
        flash('Cannot delete location that is in use by items or racks!', 'danger')
        return redirect(url_for('location_rack.location_management'))
    
    # Delete picture directory and all its contents
    if location.uuid:
        location_dir = os.path.join(current_app.config['UPLOAD_FOLDER'], 'locations', location.uuid)
        if os.path.exists(location_dir):
            import shutil
            try:
                shutil.rmtree(location_dir)
            except Exception as e:
                print(f"Error deleting location directory: {e}")
    
    location_name = location.name
    db.session.delete(location)
    db.session.commit()
    
    log_audit(current_user.id, 'delete', 'location', id, f'Deleted location: {location_name}')
    flash(f'Location "{location_name}" deleted successfully!', 'success')
    return redirect(url_for('location_rack.location_management'))



@location_rack_bp.route('/location-picture/<path:filepath>', endpoint='location_picture')
@login_required
def location_picture(filepath):
    """Serve location pictures.  filepath may be:
      - {location_uuid}/{filename}.ext  — uploaded file
      - share/icon/{filename}           — icon from Share Files
    """
    if filepath.startswith('share/icon/'):
        from routes.share import share_serve
        filename = filepath[len('share/icon/'):]
        return share_serve('icon', filename)
    location_dir = os.path.join(current_app.config['UPLOAD_FOLDER'], 'locations')
    safe_path = safe_join(location_dir, filepath)
    if safe_path is None or not os.path.exists(safe_path):
        abort(404)
    return send_from_directory(location_dir, filepath)


@location_rack_bp.route('/rack-picture/<path:filepath>')
@login_required
def rack_picture(filepath):
    """Serve rack pictures.  filepath may be:
      - {rack_uuid}/{filename}.ext  — uploaded file
      - share/icon/{filename}       — icon from Share Files
    """
    if filepath.startswith('share/icon/'):
        from routes.share import share_serve
        filename = filepath[len('share/icon/'):]
        return share_serve('icon', filename)
    rack_dir = os.path.join(current_app.config['UPLOAD_FOLDER'], 'racks')
    safe_path = safe_join(rack_dir, filepath)
    if safe_path is None or not os.path.exists(safe_path):
        abort(404)
    return send_from_directory(rack_dir, filepath)

# ============= RACK MANAGEMENT ROUTES =============



@location_rack_bp.route('/rack-management', endpoint='rack_management')
@login_required
@permission_required("settings_sections.location_management", "view")
def rack_management():
    """Rack management page"""
    racks = Rack.query.order_by(Rack.name).all()
    can_edit = current_user.has_permission('settings_sections.location_management', 'edit')
    can_delete = current_user.has_permission('settings_sections.location_management', 'delete')
    return render_template('rack_management.html', racks=racks, can_edit=can_edit, can_delete=can_delete)



@location_rack_bp.route('/rack/new', endpoint='rack_new', methods=['GET', 'POST'])
@login_required
@permission_required("settings_sections.location_management", "edit")
def rack_new():
    """Create new rack with form"""
    if request.method == 'POST':
        name = _sanitize_name(request.form.get('name', ''))
        if not name:
            flash('Rack name is required.', 'danger')
            return redirect(url_for('location_rack.rack_new'))

        # Allow duplicate names - UUID ensures uniqueness
        short_info = request.form.get('short_info', '')[:128] or None
        description = request.form.get('description')
        location_id = request.form.get('location_id')
        color = _sanitize_color(request.form.get('color', ''))
        rows = int(request.form.get('rows', 5))
        cols = int(request.form.get('cols', 5))

        # Validate against global max settings
        max_rows = int(Setting.get('max_drawer_rows', '10'))
        max_cols = int(Setting.get('max_drawer_cols', '10'))

        if rows < 1 or rows > max_rows:
            flash(f'Rows must be between 1 and {max_rows}!', 'danger')
            return redirect(url_for('location_rack.rack_new'))

        if cols < 1 or cols > max_cols:
            flash(f'Columns must be between 1 and {max_cols}!', 'danger')
            return redirect(url_for('location_rack.rack_new'))

        rack = Rack(
            name=name,
            short_info=short_info,
            description=description,
            location_id=int(location_id) if location_id and location_id != '0' else None,
            color=color,
            rows=rows,
            cols=cols
        )
        db.session.add(rack)
        db.session.commit()
        
        # Handle picture upload with UUID-based path structure
        # Handle share icon file selection (takes priority over upload)
        share_icon = request.form.get('share_icon_file', '').strip()
        if share_icon and not request.files.get('picture'):
            rack.picture = f'share/icon/{share_icon}'
            db.session.commit()
        elif request.files.get('picture'):
            file = request.files['picture']
            max_size_mb = 10
            max_size_bytes = max_size_mb * 1024 * 1024
            file.seek(0, 2)
            file_size = file.tell()
            file.seek(0)
            if file_size > max_size_bytes:
                flash('Location/rack pictures must be smaller than 10MB.', 'danger')
                return redirect(url_for('location_rack.rack_new'))
            if file.filename and allowed_file(file.filename):
                ext = file.filename.rsplit('.', 1)[1].lower()
                if ext not in ['png', 'jpg', 'jpeg', 'webp']:
                    flash('Only PNG, JPEG, and WebP images are allowed.', 'danger')
                    return redirect(url_for('location_rack.rack_new'))
                if ext == 'jpg':
                    ext = 'jpeg'
                filename = f"{rack.uuid}.{ext}"
                rack_dir = os.path.join(current_app.config['UPLOAD_FOLDER'], 'racks', rack.uuid)
                os.makedirs(rack_dir, exist_ok=True)
                for old_ext in ['png', 'jpeg', 'webp']:
                    old_f = os.path.join(rack_dir, f"{rack.uuid}.{old_ext}")
                    if old_f != os.path.join(rack_dir, filename) and os.path.exists(old_f):
                        os.remove(old_f)
                file.save(os.path.join(rack_dir, filename))
                rack.picture = f"{rack.uuid}/{filename}"
                db.session.commit()

        log_audit(current_user.id, 'create', 'rack', rack.id, f'Created rack: {name}')
        flash(f'Rack "{name}" created successfully!', 'success')
        return redirect(url_for('location_rack.location_management'))

    # GET - show form
    from models import SharedFile
    locations = Location.query.order_by(Location.name).all()
    max_drawer_rows = int(Setting.get('max_drawer_rows', '10'))
    max_drawer_cols = int(Setting.get('max_drawer_cols', '10'))
    max_file_size_mb = int(Setting.get('max_file_size_mb', '10'))
    icon_share_files = SharedFile.query.filter_by(category='icon').order_by(SharedFile.created_at.desc()).all()
    return render_template('rack_form.html', rack=None, locations=locations,
                         max_drawer_rows=max_drawer_rows, max_drawer_cols=max_drawer_cols,
                         max_file_size_mb=max_file_size_mb, icon_share_files=icon_share_files)



@location_rack_bp.route('/rack/<string:uuid>/edit', methods=['GET', 'POST'])
@login_required
@permission_required("settings_sections.location_management", "edit")
def rack_edit(uuid):
    """Edit rack with form"""
    rack = Rack.query.filter_by(uuid=uuid).first_or_404()
    
    if request.method == 'POST':
        new_name = _sanitize_name(request.form.get('name', ''))
        if not new_name:
            flash('Rack name is required.', 'danger')
            return redirect(url_for('location_rack.rack_edit', uuid=uuid))

        # Allow duplicate names - UUID ensures uniqueness
        rack.name = new_name
        rack.short_info = request.form.get('short_info', '')[:128] or None
        rack.description = request.form.get('description')
        rack.color = _sanitize_color(request.form.get('color', ''))
        location_id = request.form.get('location_id')
        rack.location_id = int(location_id) if location_id and location_id != '0' else None
        
        old_rows = rack.rows
        old_cols = rack.cols
        
        rows = int(request.form.get('rows', 5))
        cols = int(request.form.get('cols', 5))
        
        # Validate against global max settings
        max_rows = int(Setting.get('max_drawer_rows', '10'))
        max_cols = int(Setting.get('max_drawer_cols', '10'))
        
        if rows < 1 or rows > max_rows:
            flash(f'Rows must be between 1 and {max_rows}!', 'danger')
            return redirect(url_for('location_rack.rack_edit', uuid=uuid))
        
        if cols < 1 or cols > max_cols:
            flash(f'Columns must be between 1 and {max_cols}!', 'danger')
            return redirect(url_for('location_rack.rack_edit', uuid=uuid))
        
        rack.rows = rows
        rack.cols = cols
        
        # If rack size decreased, clear items and merges that are now out of bounds
        if rows < old_rows or cols < old_cols:
            items_cleared = 0
            items = Item.query.filter_by(rack_id=rack.id).all()

            for item in items:
                if item.drawer:
                    try:
                        parts = item.drawer.replace('R', '').replace('C', '-').split('-')
                        drawer_row = int(parts[0])
                        drawer_col = int(parts[1])
                        if drawer_row > rows or drawer_col > cols:
                            item.rack_id = None
                            item.drawer = None
                            item.location_id = None
                            items_cleared += 1
                    except Exception:
                        pass

            # Remove merge groups that contain any out-of-bounds cell
            existing_merges = rack.get_merged_cells()
            valid_merges = []
            for group in existing_merges:
                in_bounds = True
                for cell in group.get('cells', []):
                    try:
                        parts = cell.replace('R', '').replace('C', '-').split('-')
                        if int(parts[0]) > rows or int(parts[1]) > cols:
                            in_bounds = False
                            break
                    except Exception:
                        in_bounds = False
                        break
                if in_bounds:
                    valid_merges.append(group)
            rack.merged_cells = json.dumps(valid_merges)

            if items_cleared > 0:
                flash(f'Warning: {items_cleared} item(s) were removed from drawers outside new bounds. These items now have no location.', 'warning')
        
        # Handle picture deletion
        if request.form.get('delete_picture'):
            if rack.picture and not rack.picture.startswith('share/'):
                old_path = os.path.join(current_app.config['UPLOAD_FOLDER'], 'racks', rack.picture)
                if is_safe_file_path(old_path) and os.path.exists(old_path):
                    os.remove(old_path)
            rack.picture = None

        # Handle share icon file selection (takes priority over upload)
        share_icon = request.form.get('share_icon_file', '').strip()
        if share_icon and not request.files.get('picture'):
            rack.picture = f'share/icon/{share_icon}'
        elif request.files.get('picture'):
            file = request.files['picture']
            if hasattr(file, 'filename') and file.filename and allowed_file(file.filename):
                max_size_mb = 10
                max_size_bytes = max_size_mb * 1024 * 1024
                file.seek(0, 2)
                file_size = file.tell()
                file.seek(0)
                if file_size > max_size_bytes:
                    flash('Location/rack pictures must be smaller than 10MB.', 'danger')
                    return redirect(url_for('location_rack.rack_edit', uuid=uuid))
                ext = file.filename.rsplit('.', 1)[1].lower()
                if ext not in ['png', 'jpg', 'jpeg', 'webp']:
                    flash('Only PNG, JPEG, and WebP images are allowed.', 'danger')
                    return redirect(url_for('location_rack.rack_edit', uuid=uuid))
                if rack.picture and not rack.picture.startswith('share/'):
                    old_path = os.path.join(current_app.config['UPLOAD_FOLDER'], 'racks', rack.picture)
                    if is_safe_file_path(old_path) and os.path.exists(old_path):
                        os.remove(old_path)
                if ext == 'jpg':
                    ext = 'jpeg'
                filename = f"{rack.uuid}.{ext}"
                rack_dir = os.path.join(current_app.config['UPLOAD_FOLDER'], 'racks', rack.uuid)
                os.makedirs(rack_dir, exist_ok=True)
                for old_ext in ['png', 'jpeg', 'webp']:
                    old_f = os.path.join(rack_dir, f"{rack.uuid}.{old_ext}")
                    if old_f != os.path.join(rack_dir, filename) and os.path.exists(old_f):
                        os.remove(old_f)
                file.save(os.path.join(rack_dir, filename))
                rack.picture = f"{rack.uuid}/{filename}"

        db.session.commit()

        log_audit(current_user.id, 'update', 'rack', rack.id, f'Updated rack: {rack.name} (size: {rows}x{cols})')
        flash(f'Rack "{rack.name}" updated successfully!', 'success')
        return redirect(url_for('location_rack.rack_detail', uuid=rack.uuid))

    # GET - show form
    from models import SharedFile
    locations = Location.query.order_by(Location.name).all()
    max_drawer_rows = int(Setting.get('max_drawer_rows', '10'))
    max_drawer_cols = int(Setting.get('max_drawer_cols', '10'))
    max_file_size_mb = int(Setting.get('max_file_size_mb', '10'))
    icon_share_files = SharedFile.query.filter_by(category='icon').order_by(SharedFile.created_at.desc()).all()
    return render_template('rack_form.html', rack=rack, locations=locations,
                         max_drawer_rows=max_drawer_rows, max_drawer_cols=max_drawer_cols,
                         max_file_size_mb=max_file_size_mb, icon_share_files=icon_share_files)



@location_rack_bp.route('/rack/<string:uuid>/delete', methods=['POST'])
@login_required
@permission_required("settings_sections.location_management", "delete")
def rack_delete(uuid):
    """Delete rack"""
    rack = Rack.query.filter_by(uuid=uuid).first_or_404()
    rack_name = rack.name
    
    # Clear locations for items
    items = Item.query.filter_by(rack_id=rack.id).all()
    for item in items:
        item.rack_id = None
        item.drawer = None
    
    db.session.delete(rack)
    db.session.commit()
    
    log_audit(current_user.id, 'delete', 'rack', id, f'Deleted rack: {rack_name}, cleared {len(items)} item locations')
    flash(f'Rack "{rack_name}" deleted. {len(items)} item location(s) cleared.', 'success')
    return redirect(url_for('location_rack.location_management'))



@location_rack_bp.route('/rack/<string:uuid>')
@login_required
def rack_detail(uuid):
    """View rack details — includes items whose main is here and batches overriding here."""
    rack = Rack.query.filter_by(uuid=uuid).first_or_404()
    items_main = Item.query.filter_by(rack_id=rack.id).all()
    batches_here = ItemBatch.query.filter_by(rack_id=rack.id, follow_main_location=False).all()

    entries = []
    for item in items_main:
        entries.append({
            'scope': 'main',
            'drawer': item.drawer or '',
            'item': item,
            'batch': None,
        })
    for batch in batches_here:
        if batch.item is None:
            continue
        entries.append({
            'scope': 'batch',
            'drawer': batch.drawer or '',
            'item': batch.item,
            'batch': batch,
        })
    entries.sort(key=lambda e: (e['drawer'], e['item'].name.lower()))

    drawers = {}
    for e in entries:
        key = e['drawer'] or 'N/A'
        drawers.setdefault(key, []).append(e)

    return render_template(
        'rack_detail.html',
        rack=rack,
        entries=entries,
        drawers=drawers,
        item_count=len(items_main),
        batch_count=len(batches_here),
    )

# ============= VISUAL STORAGE ROUTES =============



@location_rack_bp.route('/api/location/add', methods=['POST'])
@login_required
@permission_required("settings_sections.location_management", "edit")
def api_add_location():
    """API endpoint to add location from item form"""
    try:
        data = request.get_json()
        name = data.get('name', '').strip()[:128]
        info = data.get('info', '').strip()[:128]
        description = data.get('description', '').strip()[:512]
        color = _sanitize_color(data.get('color', ''))
        
        if not name:
            return jsonify({'success': False, 'error': 'Location name is required'})
        
        # Allow duplicate names - UUID ensures uniqueness
        location = Location(name=name, info=info, description=description, color=color)
        db.session.add(location)
        db.session.commit()
        
        log_audit(current_user.id, 'create', 'location', location.id, f'Created location: {location.name}')
        
        return jsonify({
            'success': True,
            'location': {'id': location.id, 'uuid': location.uuid, 'name': location.name, 'color': location.color}
        })
    except Exception as e:
        db.session.rollback()
        logging.error(f"Error adding location: {str(e)}")
        return jsonify({'success': False, 'error': 'An error occurred while adding the location'})


# Rack management endpoints
@location_rack_bp.route('/add-rack', endpoint='add_rack', methods=['POST'])
@login_required
@permission_required("settings_sections.location_management", "edit")
def add_rack():
    """Add a new rack"""
    name = _sanitize_name(request.form.get('name', ''))
    if not name:
        flash('Rack name is required.', 'danger')
        return redirect(url_for('location_rack.rack_management'))
    short_info = request.form.get('short_info', '')[:128] or None
    description = request.form.get('description')
    location = request.form.get('location')
    rows = int(request.form.get('rows', 5))
    cols = int(request.form.get('cols', 5))

    rack = Rack(
        name=name,
        short_info=short_info,
        description=description,
        location_id=location if location else None,
        rows=rows,
        cols=cols
    )
    db.session.add(rack)
    db.session.commit()
    
    log_audit(current_user.id, 'create', 'rack', rack.id, f'Created rack: {name}')
    flash(f'Rack "{name}" created successfully!', 'success')
    return redirect(url_for('location_rack.rack_management'))


@location_rack_bp.route('/edit-rack', endpoint='edit_rack', methods=['POST'])
@login_required
@permission_required("settings_sections.location_management", "edit")
def edit_rack():
    """Edit an existing rack"""
    rack_id = request.form.get('rack_id')
    rack = Rack.query.get(rack_id)
    
    if not rack:
        flash('Rack not found', 'danger')
        return redirect(url_for('location_rack.rack_management'))
    
    new_inline_name = _sanitize_name(request.form.get('name', ''))
    rack.name = new_inline_name if new_inline_name else rack.name
    rack.short_info = request.form.get('short_info', '')[:128] or None
    rack.description = request.form.get('description', rack.description)
    rack.location_id = request.form.get('location') or None
    
    db.session.commit()
    log_audit(current_user.id, 'update', 'rack', rack.id, f'Updated rack: {rack.name}')
    flash(f'Rack "{rack.name}" updated successfully!', 'success')
    return redirect(url_for('location_rack.rack_management'))


@location_rack_bp.route('/delete-rack', endpoint='delete_rack', methods=['POST'])
@login_required
@permission_required("settings_sections.location_management", "delete")
def delete_rack():
    """Delete a rack"""
    rack_id = request.form.get('rack_id')
    rack = Rack.query.get(rack_id)
    
    if not rack:
        flash('Rack not found', 'danger')
        return redirect(url_for('location_rack.rack_management'))
    
    rack_name = rack.name
    db.session.delete(rack)
    db.session.commit()
    log_audit(current_user.id, 'delete', 'rack', rack_id, f'Deleted rack: {rack_name}')
    flash(f'Rack "{rack_name}" deleted successfully!', 'success')
    return redirect(url_for('location_rack.rack_management'))


@location_rack_bp.route('/location/<string:uuid>/qr', endpoint='location_qr_svg')
@login_required
def location_qr_svg(uuid):
    """Generate inline QR code SVG for a location (pure UUID)"""
    from models import Location
    from qr_utils import generate_qr_svg
    location = Location.query.filter_by(uuid=uuid).first_or_404()
    qr_svg = generate_qr_svg(location.uuid, 160, 160, error_correction='M')
    return qr_svg, 200, {'Content-Type': 'image/svg+xml'}


@location_rack_bp.route('/rack/<string:uuid>/qr', endpoint='rack_qr_svg')
@login_required
def rack_qr_svg(uuid):
    """Generate inline QR code SVG for a rack (pure UUID)"""
    from models import Rack
    from qr_utils import generate_qr_svg
    rack = Rack.query.filter_by(uuid=uuid).first_or_404()
    qr_svg = generate_qr_svg(rack.uuid, 160, 160, error_correction='M')
    return qr_svg, 200, {'Content-Type': 'image/svg+xml'}


@location_rack_bp.route('/location/<string:uuid>/qr-sticker', endpoint='location_qr_sticker')
@login_required
def location_qr_sticker(uuid):
    """Display QR sticker generation page for location"""
    if not current_user.is_admin() and not current_user.has_permission('settings_sections.qr_templates', 'print_qr'):
        abort(403)
    from models import Location
    from qr_utils import get_location_data
    
    location = Location.query.filter_by(uuid=uuid).first_or_404()
    templates = StickerTemplate.query.filter_by(template_type='Location').all()
    
    return render_template('location_qr_sticker.html', 
                          location=location,
                          templates=templates)


@location_rack_bp.route('/api/location/<string:uuid>/sticker-preview/<int:template_id>')
@login_required
def api_location_sticker_preview(uuid, template_id):
    """
    Generate sticker preview for a location with a specific template
    Returns: SVG image
    """
    if not current_user.is_admin() and not current_user.has_permission('settings_sections.qr_templates', 'print_qr'):
        return jsonify({'error': 'Permission denied'}), 403
    from models import Location
    from qr_utils import get_location_data, render_template_to_svg
    
    location = Location.query.filter_by(uuid=uuid).first_or_404()
    template = StickerTemplate.query.get_or_404(template_id)
    
    # Verify template is for Location type
    if template.template_type != 'Location':
        return jsonify({'error': 'Template must be for Location'}), 400
    
    # Get location data with all placeholders
    data = get_location_data(location)
    
    # Render to SVG
    svg_data = render_template_to_svg(template, data)
    
    return jsonify({
        'svg': svg_data,
        'width_mm': template.width_mm,
        'height_mm': template.height_mm,
        'template_name': template.name
    })


@location_rack_bp.route('/api/location/<string:uuid>/sticker-print/<int:template_id>')
@login_required
def api_location_sticker_print(uuid, template_id):
    """
    Generate printable sticker for a location
    Returns: PDF file download
    """
    if not current_user.is_admin() and not current_user.has_permission('settings_sections.qr_templates', 'print_qr'):
        return jsonify({'error': 'Permission denied'}), 403
    from models import Location
    from qr_utils import get_location_data, generate_single_sticker_pdf
    
    location = Location.query.filter_by(uuid=uuid).first_or_404()
    template = StickerTemplate.query.get_or_404(template_id)
    
    if template.template_type != 'Location':
        return jsonify({'error': 'Template must be for Location'}), 400
    
    data = get_location_data(location)
    
    # Generate single-sticker PDF
    output = generate_single_sticker_pdf(template, data, location.uuid)
    
    log_audit(current_user.id, 'print', 'location', location.id, 
             f'Printed sticker: {template.name}')
    
    return send_file(
        output, 
        mimetype='application/pdf',
        as_attachment=True,
        download_name=f'{template.name}_{location.uuid}.pdf'
    )


@location_rack_bp.route('/rack/<string:uuid>/qr-sticker', endpoint='rack_qr_sticker')
@login_required
def rack_qr_sticker(uuid):
    """Display QR sticker generation page for rack"""
    if not current_user.is_admin() and not current_user.has_permission('settings_sections.qr_templates', 'print_qr'):
        abort(403)
    from models import Rack
    from qr_utils import get_rack_data
    
    rack = Rack.query.filter_by(uuid=uuid).first_or_404()
    templates = StickerTemplate.query.filter_by(template_type='Racks').all()
    
    return render_template('rack_qr_sticker.html', 
                          rack=rack,
                          templates=templates)


@location_rack_bp.route('/api/rack/<string:uuid>/sticker-preview/<int:template_id>')
@login_required
def api_rack_sticker_preview(uuid, template_id):
    """
    Generate sticker preview for a rack with a specific template
    Returns: SVG image
    """
    if not current_user.is_admin() and not current_user.has_permission('settings_sections.qr_templates', 'print_qr'):
        return jsonify({'error': 'Permission denied'}), 403
    from models import Rack
    from qr_utils import get_rack_data, render_template_to_svg
    
    rack = Rack.query.filter_by(uuid=uuid).first_or_404()
    template = StickerTemplate.query.get_or_404(template_id)
    
    # Verify template is for Racks type
    if template.template_type != 'Racks':
        return jsonify({'error': 'Template must be for Racks'}), 400
    
    # Get rack data with all placeholders
    data = get_rack_data(rack)
    
    # Render to SVG
    svg_data = render_template_to_svg(template, data)
    
    return jsonify({
        'svg': svg_data,
        'width_mm': template.width_mm,
        'height_mm': template.height_mm,
        'template_name': template.name
    })


@location_rack_bp.route('/api/rack/<string:uuid>/sticker-print/<int:template_id>')
@login_required
def api_rack_sticker_print(uuid, template_id):
    """
    Generate printable sticker for a rack
    Returns: PDF file download
    """
    if not current_user.is_admin() and not current_user.has_permission('settings_sections.qr_templates', 'print_qr'):
        return jsonify({'error': 'Permission denied'}), 403
    from models import Rack
    from qr_utils import get_rack_data, generate_single_sticker_pdf
    
    rack = Rack.query.filter_by(uuid=uuid).first_or_404()
    template = StickerTemplate.query.get_or_404(template_id)
    
    if template.template_type != 'Racks':
        return jsonify({'error': 'Template must be for Racks'}), 400
    
    data = get_rack_data(rack)
    
    # Generate single-sticker PDF
    output = generate_single_sticker_pdf(template, data, rack.uuid)
    
    log_audit(current_user.id, 'print', 'rack', rack.id, 
             f'Printed sticker: {template.name}')
    
    return send_file(
        output, 
        mimetype='application/pdf',
        as_attachment=True,
        download_name=f'{template.name}_{rack.uuid}.pdf'
    )


@location_rack_bp.route('/rack/<string:uuid>/drawer/<string:drawer_id>/qr-sticker', endpoint='drawer_qr_sticker')
@login_required
def drawer_qr_sticker(uuid, drawer_id):
    """Display QR sticker page for a single rack drawer (backward compat)."""
    if not current_user.is_admin() and not current_user.has_permission('settings_sections.qr_templates', 'print_qr'):
        abort(403)
    rack = Rack.query.filter_by(uuid=uuid).first_or_404()
    templates = StickerTemplate.query.filter_by(template_type='Drawer').all()
    return render_template('drawer_qr_sticker.html',
                           rack=rack,
                           drawer_ids=[drawer_id],
                           templates=templates)


@location_rack_bp.route('/rack/<string:uuid>/drawers/qr-sticker', endpoint='drawers_qr_sticker')
@login_required
def drawers_qr_sticker(uuid):
    """Display QR sticker page for one or more rack drawers."""
    if not current_user.is_admin() and not current_user.has_permission('settings_sections.qr_templates', 'print_qr'):
        abort(403)
    rack = Rack.query.filter_by(uuid=uuid).first_or_404()
    raw = request.args.get('drawers', '')
    drawer_ids = [d.strip() for d in raw.split(',') if d.strip()]
    if not drawer_ids:
        abort(400)
    templates = StickerTemplate.query.filter_by(template_type='Drawer').all()
    return render_template('drawer_qr_sticker.html',
                           rack=rack,
                           drawer_ids=drawer_ids,
                           templates=templates)


@location_rack_bp.route('/api/rack/<string:uuid>/drawer/<string:drawer_id>/sticker-preview/<int:template_id>')
@login_required
def api_drawer_sticker_preview(uuid, drawer_id, template_id):
    """Generate sticker preview SVG for a rack drawer"""
    if not current_user.is_admin() and not current_user.has_permission('settings_sections.qr_templates', 'print_qr'):
        return jsonify({'error': 'Permission denied'}), 403
    from qr_utils import get_drawer_data, render_template_to_svg
    rack = Rack.query.filter_by(uuid=uuid).first_or_404()
    template = StickerTemplate.query.get_or_404(template_id)
    if template.template_type != 'Drawer':
        return jsonify({'error': 'Template must be Drawer type'}), 400
    data = get_drawer_data(rack, drawer_id)
    svg_data = render_template_to_svg(template, data)
    return jsonify({
        'svg': svg_data,
        'width_mm': template.width_mm,
        'height_mm': template.height_mm,
        'template_name': template.name
    })


@location_rack_bp.route('/api/rack/<string:uuid>/drawer/<string:drawer_id>/sticker-print/<int:template_id>')
@login_required
def api_drawer_sticker_print(uuid, drawer_id, template_id):
    """Generate PDF sticker for a rack drawer"""
    if not current_user.is_admin() and not current_user.has_permission('settings_sections.qr_templates', 'print_qr'):
        return jsonify({'error': 'Permission denied'}), 403
    from qr_utils import get_drawer_data, generate_single_sticker_pdf
    rack = Rack.query.filter_by(uuid=uuid).first_or_404()
    template = StickerTemplate.query.get_or_404(template_id)
    if template.template_type != 'Drawer':
        return jsonify({'error': 'Template must be Drawer type'}), 400
    data = get_drawer_data(rack, drawer_id)
    output = generate_single_sticker_pdf(template, data, f"{rack.uuid}_{drawer_id}")
    log_audit(current_user.id, 'print', 'rack', rack.id,
              f'Printed drawer sticker: {template.name} drawer {drawer_id}')
    return send_file(
        output,
        mimetype='application/pdf',
        as_attachment=True,
        download_name=f'{template.name}_{rack.uuid}_{drawer_id}.pdf'
    )


@location_rack_bp.route('/api/rack/<string:uuid>/drawers/sticker-print/<int:template_id>')
@login_required
def api_drawers_sticker_print(uuid, template_id):
    """Generate multi-page PDF for multiple rack drawers."""
    if not current_user.is_admin() and not current_user.has_permission('settings_sections.qr_templates', 'print_qr'):
        return jsonify({'error': 'Permission denied'}), 403
    from qr_utils import get_drawer_data, generate_batch_stickers_pdf
    rack = Rack.query.filter_by(uuid=uuid).first_or_404()
    template = StickerTemplate.query.get_or_404(template_id)
    if template.template_type != 'Drawer':
        return jsonify({'error': 'Template must be Drawer type'}), 400
    raw = request.args.get('drawers', '')
    drawer_ids = [d.strip() for d in raw.split(',') if d.strip()]
    if not drawer_ids:
        return jsonify({'error': 'No drawers specified'}), 400
    output = generate_batch_stickers_pdf(template, drawer_ids, lambda did: get_drawer_data(rack, did))
    log_audit(current_user.id, 'print', 'rack', rack.id,
              f'Printed drawer stickers: {template.name} drawers {",".join(drawer_ids)}')
    return send_file(output, mimetype='application/pdf', as_attachment=True,
                     download_name=f'{rack.name}_drawers_{template.name}.pdf')


@location_rack_bp.route('/api/rack/<string:uuid>/drawers/sticker-svg-zip/<int:template_id>')
@login_required
def api_drawers_sticker_svg_zip(uuid, template_id):
    """Generate a zip of SVG stickers for multiple rack drawers."""
    if not current_user.is_admin() and not current_user.has_permission('settings_sections.qr_templates', 'print_qr'):
        return jsonify({'error': 'Permission denied'}), 403
    from qr_utils import get_drawer_data, generate_svg_zip
    rack = Rack.query.filter_by(uuid=uuid).first_or_404()
    template = StickerTemplate.query.get_or_404(template_id)
    if template.template_type != 'Drawer':
        return jsonify({'error': 'Template must be Drawer type'}), 400
    raw = request.args.get('drawers', '')
    drawer_ids = [d.strip() for d in raw.split(',') if d.strip()]
    if not drawer_ids:
        return jsonify({'error': 'No drawers specified'}), 400
    safe_rack = rack.name.replace("'", "").replace(" ", "_")
    pairs = [(f"{safe_rack}_{did}", get_drawer_data(rack, did)) for did in drawer_ids]
    zip_buf = generate_svg_zip(template, pairs)
    return send_file(zip_buf, mimetype='application/zip', as_attachment=True,
                     download_name=f'{safe_rack}_drawers_svg.zip')
