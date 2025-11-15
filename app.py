from flask import Flask, render_template, redirect, url_for, flash, request, send_from_directory, abort, jsonify
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, safe_join
from werkzeug.utils import secure_filename
from config import Config
from models import db, User, Category, Item, Attachment, Rack, Footprint, Tag, Setting, Location
from forms import LoginForm, RegistrationForm, CategoryForm, ItemAddForm, ItemEditForm, AttachmentForm, SearchForm, UserForm, MagicParameterForm, ParameterUnitForm, ParameterStringOptionForm, ItemParameterForm
from utils import save_file, log_audit, admin_required, permission_required, item_permission_required, format_file_size, allowed_file
import os
import json
import secrets
import string
import logging
from datetime import datetime, timezone
from urllib.parse import urlparse, urljoin

def is_safe_url(target):
    """
    Only allow redirects to internal relative URLs (not external sites).
    Strips backslashes and checks that scheme/netloc are empty.
    """
    # Normalize backslashes (important for browser behavior)
    target = target.replace('\\', '')
    # Only allow redirects to relative paths under this app
    res = urlparse(target)
    if not res.netloc and not res.scheme:
        return True
    return False

app = Flask(__name__)
app.config.from_object(Config)

# Initialize extensions
db.init_app(app)
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'
login_manager.login_message = 'Please log in to access this page.'

# Create upload folder
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
os.makedirs(os.path.join(app.config['UPLOAD_FOLDER'], 'userpicture'), exist_ok=True)

@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, int(user_id))

def is_safe_url(target):
    """Validate that a URL is safe for redirects (prevents open redirect attacks)"""
    if not target:
        return False

    # Parse the target URL
    ref_url = urlparse(request.host_url)
    test_url = urlparse(urljoin(request.host_url, target))

    # URL is safe if it has no scheme/netloc (relative URL) or matches our host
    return test_url.scheme in ('http', 'https') and ref_url.netloc == test_url.netloc

def is_safe_file_path(file_path, base_dir=None):
    """Validate that a file path is safe for file operations (prevents path traversal)"""
    if not file_path:
        return False

    if base_dir is None:
        base_dir = app.config['UPLOAD_FOLDER']

    try:
        # Resolve to absolute paths to handle .. and symlinks
        base_path = os.path.abspath(base_dir)
        abs_file_path = os.path.abspath(file_path)

        # Ensure the file path is within the base directory
        return abs_file_path.startswith(base_path + os.sep) or abs_file_path == base_path
    except (ValueError, OSError):
        return False

@app.template_filter('filesize')
def filesize_filter(size):
    return format_file_size(size)

@app.template_filter('markdown')
def markdown_filter(text):
    from utils import markdown_to_html
    from markupsafe import Markup
    return Markup(markdown_to_html(text))

# ============= AUTHENTICATION ROUTES =============

@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('index'))
    
    from models import Setting
    signup_enabled = Setting.get('signup_enabled', True)
    demo_mode = app.config.get('DEMO_MODE', False)
    demo_username = app.config.get('DEMO_ADMIN_USERNAME', 'admin')
    demo_password = os.getenv('ADMIN_PASSWORD', 'admin123')
    
    form = LoginForm()
    if form.validate_on_submit():
        user = User.query.filter_by(username=form.username.data).first()
        
        # Check if account is locked due to too many failed attempts
        if user and user.account_locked_until:
            from datetime import timezone as tz_module
            # Ensure both datetimes are timezone-aware (UTC)
            now_utc = datetime.now(tz_module.utc)
            locked_until = user.account_locked_until
            
            # If locked_until is timezone-naive, assume it's UTC and make it aware
            if locked_until.tzinfo is None:
                locked_until = locked_until.replace(tzinfo=tz_module.utc)
            
            if now_utc < locked_until:
                flash('Account is temporarily locked due to too many failed login attempts. Please try again later.', 'danger')
                return render_template('login.html', form=form, signup_enabled=signup_enabled, 
                                     demo_mode=demo_mode, demo_username=demo_username, 
                                     demo_password=demo_password)
            else:
                # Unlock account if lockout time has passed
                user.account_locked_until = None
                user.failed_login_attempts = 0
                db.session.commit()
        
        # Check if user exists, password correct, and account active
        if user and user.check_password(form.password.data) and user.is_active:
            # Reset failed attempts on successful login
            user.failed_login_attempts = 0
            user.account_locked_until = None
            db.session.commit()
            
            login_user(user, remember=form.remember_me.data)
            log_audit(user.id, 'login', 'user', user.id, 'User logged in')
            next_page = request.args.get('next')
            # Validate redirect URL to prevent open redirect attacks
            if next_page and is_safe_url(next_page):
                return redirect(next_page)
            # Unsafe or missing redirect target: go to the index page
            return redirect(url_for('index'))
        else:
            # Handle failed login attempt
            if user:
                # Check if max_login_attempts is set and greater than 0
                if user.max_login_attempts > 0:
                    user.failed_login_attempts += 1
                    
                    # Check if attempts exceeded
                    if user.failed_login_attempts >= user.max_login_attempts:
                        from datetime import timedelta, timezone as tz_module
                        # Lock account with configured unlock time or indefinitely
                        if user.auto_unlock_enabled:
                            user.account_locked_until = datetime.now(tz_module.utc) + timedelta(minutes=user.auto_unlock_minutes)
                            unlock_msg = f"Try again in {user.auto_unlock_minutes} minutes."
                        else:
                            user.account_locked_until = datetime.now(tz_module.utc) + timedelta(days=365*10)  # Very far future
                            unlock_msg = "Contact administrator to unlock."
                        db.session.commit()
                        log_audit(user.id, 'login_failed_locked', 'user', user.id, 
                                f'Account locked after {user.failed_login_attempts} failed attempts')
                        flash(f'Account locked due to {user.max_login_attempts} failed login attempts. {unlock_msg}', 'danger')
                        return render_template('login.html', form=form, signup_enabled=signup_enabled, 
                                             demo_mode=demo_mode, demo_username=demo_username, 
                                             demo_password=demo_password)
                    else:
                        db.session.commit()
                        remaining = user.max_login_attempts - user.failed_login_attempts
                        log_audit(user.id, 'login_failed', 'user', user.id, 
                                f'Failed login attempt {user.failed_login_attempts}/{user.max_login_attempts}')
                        flash(f'Invalid username or password. {remaining} attempt(s) remaining before account lock.', 'danger')
                else:
                    # Unlimited attempts
                    log_audit(user.id, 'login_failed', 'user', user.id, 'Failed login attempt')
                    flash('Invalid username or password, or account is inactive.', 'danger')
            else:
                flash('Invalid username or password, or account is inactive.', 'danger')
    
    return render_template('login.html', form=form, signup_enabled=signup_enabled, 
                         demo_mode=demo_mode, demo_username=demo_username, 
                         demo_password=demo_password)

@app.route('/logout')
@login_required
def logout():
    log_audit(current_user.id, 'logout', 'user', current_user.id, 'User logged out')
    logout_user()
    flash('You have been logged out.', 'info')
    return redirect(url_for('login'))

@app.route('/register', methods=['GET', 'POST'])
def register():
    from models import Setting, Role
    signup_enabled = Setting.get('signup_enabled', True)
    
    if not signup_enabled:
        flash('User registration is currently disabled.', 'warning')
        return redirect(url_for('login'))
    
    if current_user.is_authenticated:
        return redirect(url_for('index'))
    
    form = RegistrationForm()
    if form.validate_on_submit():
        # Get Viewer role as default for new registrations
        viewer_role = Role.query.filter_by(name='Viewer').first()
        if not viewer_role:
            flash('System error: Default role not found. Please contact administrator.', 'danger')
            return redirect(url_for('login'))
        
        user = User(
            username=form.username.data,
            email=form.email.data,
            role_id=viewer_role.id
        )
        user.set_password(form.password.data)
        db.session.add(user)
        db.session.commit()
        
        flash('Registration successful! Please log in.', 'success')
        return redirect(url_for('login'))
    
    return render_template('register.html', form=form)

# ============= CONTEXT PROCESSOR =============

@app.context_processor
def inject_theme():
    """Make current user's theme available to all templates"""
    if current_user.is_authenticated:
        return dict(current_theme=current_user.theme or 'light')
    return dict(current_theme='light')

@app.context_processor
def inject_settings():
    """Make system settings available to all templates"""
    from datetime import datetime
    from models import ItemParameter
    
    currency = Setting.get('currency', '$')
    max_file_size = Setting.get('max_file_size_mb', '10')
    allowed_extensions = Setting.get('allowed_extensions', 'pdf,png,jpg,jpeg,gif,txt,doc,docx')
    
    # Get notification count for logged in users
    notification_count = 0
    if current_user.is_authenticated:
        try:
            params = ItemParameter.query.join(ItemParameter.parameter).filter(
                ItemParameter.parameter.has(param_type='date'),
                ItemParameter.parameter.has(notify_enabled=True)
            ).all()
            
            today = datetime.now().date()
            for param in params:
                try:
                    if param.operation in ['value', 'start', 'end'] and param.value:
                        param_date = datetime.strptime(param.value, '%Y-%m-%d').date()
                        if param_date <= today:
                            notification_count += 1
                    elif param.operation == 'duration' and param.value and param.value2:
                        start_date = datetime.strptime(param.value, '%Y-%m-%d').date()
                        end_date = datetime.strptime(param.value2, '%Y-%m-%d').date()
                        if start_date <= today <= end_date:
                            notification_count += 1
                except:
                    pass
        except:
            pass
    
    return dict(
        currency_symbol=currency,
        max_file_size_mb=max_file_size,
        allowed_file_types=allowed_extensions,
        notification_count=notification_count,
        banner_timeout=Setting.get('banner_timeout', '5')
    )

# ============= MAIN ROUTES =============

@app.route('/')
@login_required
def index():
    search_form = SearchForm()
    
    search_query = request.args.get('search', '')
    category_id = request.args.get('category', 0, type=int)
    page = request.args.get('page', 1, type=int)
    per_page = 20
    
    query = Item.query
    
    if search_query:
        query = query.filter(
            db.or_(
                Item.name.ilike(f'%{search_query}%'),
                Item.description.ilike(f'%{search_query}%'),
                Item.sku.ilike(f'%{search_query}%')
            )
        )
    
    if category_id > 0:
        query = query.filter_by(category_id=category_id)
    
    # Default sort by updated_at descending
    pagination = query.order_by(Item.updated_at.desc()).paginate(
        page=page, per_page=per_page, error_out=False
    )
    
    items = pagination.items
    
    total_items = Item.query.count()
    low_stock_items = Item.query.filter(Item.quantity <= Item.min_quantity).count()
    total_categories = Category.query.count()
    
    # Get user's table columns preference
    user_columns = current_user.get_table_columns()
    
    return render_template('index.html', 
                         items=items,
                         pagination=pagination,
                         search_form=search_form,
                         search_query=search_query,
                         category_id=category_id,
                         total_items=total_items,
                         low_stock_items=low_stock_items,
                         total_categories=total_categories,
                         user_columns=user_columns)

# ============= ITEM ROUTES =============

def get_item_edit_permissions(user):
    """Get which item fields a user can edit"""
    perms = {
        'can_edit_name': user.has_permission('items', 'edit_name'),
        'can_edit_sku_type': user.has_permission('items', 'edit_sku_type'),
        'can_edit_description': user.has_permission('items', 'edit_description'),
        'can_edit_datasheet': user.has_permission('items', 'edit_datasheet'),
        'can_edit_upload': user.has_permission('items', 'edit_upload'),
        'can_edit_lending': user.has_permission('items', 'edit_lending'),
        'can_edit_price': user.has_permission('items', 'edit_price'),
        'can_edit_quantity': user.has_permission('items', 'edit_quantity'),
        'can_edit_location': user.has_permission('items', 'edit_location'),
        'can_edit_category': user.has_permission('items', 'edit_category'),
        'can_edit_footprint': user.has_permission('items', 'edit_footprint'),
        'can_edit_tags': user.has_permission('items', 'edit_tags'),
        'can_edit_parameters': user.has_permission('items', 'edit_parameters'),
        'can_create': user.has_permission('items', 'create'),
        'can_delete': user.has_permission('items', 'delete'),
        'is_admin': user.is_admin()
    }
    return perms

@app.route('/item/new', methods=['GET', 'POST'])
@login_required
@item_permission_required
def item_new():
    from models import Tag
    from forms import ItemAddForm
    import json
    
    # Get user permissions
    perms = get_item_edit_permissions(current_user)
    
    # Check if user has permission to create items
    if not perms.get('can_create'):
        flash('You do not have permission to create new items.', 'danger')
        return redirect(url_for('index'))
    
    # Also check if user has ANY edit permission (in case someone tries to create with form directly)
    if not (perms.get('can_edit_name') or perms.get('can_edit_sku_type') or 
            perms.get('can_edit_description') or perms.get('can_edit_datasheet') or
            perms.get('can_edit_upload') or perms.get('can_edit_lending') or
            perms.get('can_edit_price') or perms.get('can_edit_quantity') or
            perms.get('can_edit_location') or perms.get('can_edit_category') or
            perms.get('can_edit_footprint') or perms.get('can_edit_tags') or
            perms.get('can_edit_parameters')):
        flash('You do not have permission to create items.', 'danger')
        return redirect(url_for('index'))
    
    # Create form with permission-based field disabling
    form = ItemAddForm(perms=perms)
    locations = Location.query.order_by(Location.name).all()
    racks = Rack.query.order_by(Rack.name).all()
    racks_data = [{'id': r.id, 'name': r.name, 'rows': r.rows, 'cols': r.cols, 
                   'unavailable_drawers': r.get_unavailable_drawers()} for r in racks]
    all_tags = [{'id': t.id, 'name': t.name, 'color': t.color} for t in Tag.query.order_by(Tag.name).all()]
    
    prefill_rack_id = request.args.get('rack_id', type=int)
    prefill_drawer = request.args.get('drawer')
    
    if form.validate_on_submit():
        # For view-only users, check if they're trying to edit
        if not (perms.get('can_edit_name') or perms.get('can_edit_sku_type') or 
                perms.get('can_edit_description') or perms.get('can_edit_datasheet') or
                perms.get('can_edit_upload') or perms.get('can_edit_lending') or
                perms.get('can_edit_price') or perms.get('can_edit_quantity') or
                perms.get('can_edit_location') or perms.get('can_edit_category') or
                perms.get('can_edit_footprint') or perms.get('can_edit_tags') or
                perms.get('can_edit_parameters')):
            flash('You do not have permission to create items with any editable fields.', 'danger')
            return redirect(url_for('index'))
        
        # Apply default values for fields user cannot edit
        location_id = form.location_id.data if form.location_id.data and perms['can_edit_location'] else None
        rack_id = request.form.get('rack_id') if perms['can_edit_location'] else None
        drawer = request.form.get('drawer') if perms['can_edit_location'] else None
        
        # Determine location type
        if rack_id and int(rack_id) > 0:
            # Drawer storage
            location_id_value = None
            rack_id_value = int(rack_id)
            drawer_value = drawer
        else:
            # General location
            location_id_value = location_id if location_id and location_id != 0 else None
            rack_id_value = None
            drawer_value = None
        
        # Get selected tags (only if can edit tags)
        selected_tags = request.form.getlist('tags[]') if perms['can_edit_tags'] else []
        tags_json = json.dumps([int(t) for t in selected_tags if t])
        
        # Create item with role-based restrictions
        item = Item(
            name=form.name.data if perms['can_edit_name'] else 'New Item',
            sku=form.sku.data if form.sku.data and perms['can_edit_sku_type'] else None,
            info=form.info.data if perms['can_edit_sku_type'] else None,
            description=form.description.data if perms['can_edit_description'] else None,
            quantity=form.quantity.data if perms['can_edit_quantity'] else 0,
            price=form.price.data if form.price.data and perms['can_edit_price'] else 0.0,
            location_id=location_id_value,
            rack_id=rack_id_value,
            drawer=drawer_value,
            min_quantity=form.min_quantity.data if form.min_quantity.data and perms['can_edit_quantity'] else 0,
            no_stock_warning=form.no_stock_warning.data if perms['can_edit_quantity'] else True,
            category_id=form.category_id.data if form.category_id.data and form.category_id.data > 0 and perms['can_edit_category'] else None,
            footprint_id=form.footprint_id.data if form.footprint_id.data and form.footprint_id.data > 0 and perms['can_edit_footprint'] else None,
            tags=tags_json,
            lend_to=form.lend_to.data if perms['can_edit_lending'] else None,
            lend_quantity=form.lend_quantity.data if form.lend_quantity.data and perms['can_edit_lending'] else 0,
            datasheet_urls=form.datasheet_urls.data if perms['can_edit_datasheet'] else None,
            created_by=current_user.id,
            updated_by=current_user.id
        )
        db.session.add(item)
        db.session.commit()
        
        log_audit(current_user.id, 'create', 'item', item.id, f'Created item: {item.name}')
        flash(f'Item "{item.name}" created successfully!', 'success')
        return redirect(url_for('item_detail', uuid=item.uuid))
    
    return render_template('item_form.html', form=form, locations=locations, racks=racks, racks_data=racks_data, all_tags=all_tags, title='New Item',
                         prefill_rack_id=prefill_rack_id, prefill_drawer=prefill_drawer, 
                         currency=Setting.get('currency', '$'),
                         item_perms=perms)

@app.route('/item/<string:uuid>')
@login_required
def item_detail(uuid):
    item = Item.query.filter_by(uuid=uuid).first_or_404()
    
    # Check if user has view permission
    if not current_user.has_permission('items', 'view'):
        flash('You do not have permission to view items.', 'danger')
        return redirect(url_for('index'))
    
    attachment_form = AttachmentForm()
    currency_symbol = Setting.get('currency', '$')
    return render_template('item_detail.html', item=item, attachment_form=attachment_form, currency_symbol=currency_symbol)

@app.route('/item/<string:uuid>/edit', methods=['GET', 'POST'])
@login_required
@item_permission_required
def item_edit(uuid):
    from models import Tag
    from forms import ItemEditForm
    import json
    
    item = Item.query.filter_by(uuid=uuid).first_or_404()
    
    # Get user permissions for this item
    perms = get_item_edit_permissions(current_user)
    
    # Check if user has any edit permissions
    if not (perms.get('can_edit_name') or perms.get('can_edit_sku_type') or 
            perms.get('can_edit_description') or perms.get('can_edit_datasheet') or
            perms.get('can_edit_upload') or perms.get('can_edit_lending') or
            perms.get('can_edit_price') or perms.get('can_edit_quantity') or
            perms.get('can_edit_location') or perms.get('can_edit_category') or
            perms.get('can_edit_footprint') or perms.get('can_edit_tags') or
            perms.get('can_edit_parameters')):
        flash('You do not have permission to edit items.', 'danger')
        return redirect(url_for('item_detail', uuid=item.uuid))
    
    # Create form with permission-based field disabling
    form = ItemEditForm(obj=item, perms=perms)
    locations = Location.query.order_by(Location.name).all()
    racks = Rack.query.order_by(Rack.name).all()
    racks_data = [{'id': r.id, 'name': r.name, 'rows': r.rows, 'cols': r.cols, 
                   'unavailable_drawers': r.get_unavailable_drawers()} for r in racks]
    all_tags = [{'id': t.id, 'name': t.name, 'color': t.color} for t in Tag.query.order_by(Tag.name).all()]
    
    if form.validate_on_submit():
        # Check if user has permission to edit anything
        if not (perms.get('can_edit_name') or perms.get('can_edit_sku_type') or 
                perms.get('can_edit_description') or perms.get('can_edit_datasheet') or
                perms.get('can_edit_upload') or perms.get('can_edit_lending') or
                perms.get('can_edit_price') or perms.get('can_edit_quantity') or
                perms.get('can_edit_location') or perms.get('can_edit_category') or
                perms.get('can_edit_footprint') or perms.get('can_edit_tags') or
                perms.get('can_edit_parameters')):
            flash('You do not have permission to edit this item.', 'danger')
            return redirect(url_for('item_detail', uuid=item.uuid))
        
        # Only update fields user has permission for
        if perms['can_edit_name']:
            item.name = form.name.data
        
        if perms['can_edit_sku_type']:
            item.sku = form.sku.data if form.sku.data else None
            item.info = form.info.data
        
        if perms['can_edit_description']:
            item.description = form.description.data
        
        if perms['can_edit_datasheet']:
            item.datasheet_urls = form.datasheet_urls.data
        
        if perms['can_edit_lending']:
            item.lend_to = form.lend_to.data
            item.lend_quantity = form.lend_quantity.data or 0
        
        if perms['can_edit_price']:
            item.price = form.price.data
        
        if perms['can_edit_quantity']:
            item.quantity = form.quantity.data
            item.min_quantity = form.min_quantity.data
            item.no_stock_warning = form.no_stock_warning.data
        
        if perms['can_edit_location']:
            location_id = form.location_id.data if form.location_id.data else None
            rack_id = request.form.get('rack_id')
            drawer = request.form.get('drawer')
            
            # Determine location type
            if rack_id and int(rack_id) > 0:
                # Drawer storage
                item.location_id = None
                item.rack_id = int(rack_id)
                item.drawer = drawer
            else:
                # General location
                item.location_id = location_id if location_id and location_id != 0 else None
                item.rack_id = None
                item.drawer = None
        
        if perms['can_edit_category']:
            item.category_id = form.category_id.data if form.category_id.data and form.category_id.data > 0 else None
        
        if perms['can_edit_footprint']:
            item.footprint_id = form.footprint_id.data if form.footprint_id.data and form.footprint_id.data > 0 else None
        
        if perms['can_edit_tags']:
            # Get selected tags
            selected_tags = request.form.getlist('tags[]')
            tags_json = json.dumps([int(t) for t in selected_tags if t])
            item.tags = tags_json
        
        item.updated_at = datetime.now(timezone.utc)
        item.updated_by = current_user.id
        
        db.session.commit()
        
        log_audit(current_user.id, 'update', 'item', item.id, f'Updated item: {item.name}')
        flash(f'Item "{item.name}" updated successfully!', 'success')
        return redirect(url_for('item_detail', uuid=item.uuid))
    
    # Get file upload settings
    max_size_mb = int(Setting.get('max_file_size_mb', '10'))
    extensions_str = Setting.get('allowed_extensions', 'pdf,png,jpg,jpeg,gif,txt,doc,docx')
    
    return render_template('item_form.html', form=form, item=item, locations=locations, racks=racks, racks_data=racks_data, all_tags=all_tags, title='Edit Item', currency=Setting.get('currency', '$'), max_file_size_mb=max_size_mb, allowed_file_types=extensions_str, item_perms=perms)

@app.route('/item/<string:uuid>/delete', methods=['POST'])
@login_required
@item_permission_required
def item_delete(uuid):
    item = Item.query.filter_by(uuid=uuid).first_or_404()
    
    # Check if user has permission to delete items
    perms = get_item_edit_permissions(current_user)
    if not perms.get('can_delete'):
        flash('You do not have permission to delete items.', 'danger')
        return redirect(url_for('item_detail', uuid=item.uuid))
    
    item_name = item.name
    
    # Delete related attachments
    for attachment in item.attachments:
        try:
            if attachment.file_path and is_safe_file_path(attachment.file_path):
                if os.path.exists(attachment.file_path):
                    os.remove(attachment.file_path)
        except Exception as e:
            logging.error(f"Error deleting attachment file {attachment.id}: {e}")
    
    # Delete item parameters (magic parameters)
    from models import ItemParameter
    ItemParameter.query.filter_by(item_id=item.id).delete()
    
    # Delete the item
    db.session.delete(item)
    db.session.commit()
    
    log_audit(current_user.id, 'delete', 'item', item.id, f'Deleted item: {item_name}')
    flash(f'Item "{item_name}" deleted successfully!', 'success')
    return redirect(url_for('index'))

# ============= ATTACHMENT ROUTES =============

@app.route('/item/<int:item_id>/upload', methods=['POST'])
@login_required
@item_permission_required
def upload_attachment(item_id):
    item = Item.query.get_or_404(item_id)
    form = AttachmentForm()
    
    # SECURITY CHECK: Verify user has upload permission
    if not current_user.has_permission('items', 'edit_upload'):
        flash('❌ You do not have permission to upload files.', 'danger')
        log_audit(current_user.id, 'denied', 'attachment_upload', item.id, f'Unauthorized upload attempt to item: {item.name}')
        return redirect(url_for('item_detail', uuid=item.uuid))
    
    files = request.files.getlist('files')
    
    # Get dynamic settings
    max_size_mb = int(Setting.get('max_file_size_mb', '10'))
    max_size_bytes = max_size_mb * 1024 * 1024
    extensions_str = Setting.get('allowed_extensions', 'pdf,png,jpg,jpeg,gif,txt,doc,docx')
    allowed_extensions = set(ext.strip().lower() for ext in extensions_str.split(',') if ext.strip())
    
    uploaded_count = 0
    rejected_count = 0
    
    for file in files:
        if not file or not file.filename:
            continue
            
        # Check file extension
        if not allowed_file(file.filename):
            flash(f'❌ File "{file.filename}" rejected: Incompatible file type. Allowed: {extensions_str}', 'danger')
            rejected_count += 1
            continue
        
        # Check file size
        file.seek(0, 2)  # Seek to end
        file_size = file.tell()
        file.seek(0)  # Reset to beginning
        
        if file_size > max_size_bytes:
            flash(f'❌ File "{file.filename}" rejected: Too large ({format_file_size(file_size)}). Max: {max_size_mb}MB', 'danger')
            rejected_count += 1
            continue
        
        file_info = save_file(file, app.config['UPLOAD_FOLDER'], item.uuid)
        
        if file_info:
            attachment = Attachment(
                filename=file_info['filename'],
                original_filename=file_info['original_filename'],
                file_path=file_info['file_path'],
                file_type=file_info['file_type'],
                file_size=file_info['file_size'],
                item_id=item.id,
                uploaded_by=current_user.id
            )
            db.session.add(attachment)
            uploaded_count += 1
    
    if uploaded_count > 0:
        db.session.commit()
        log_audit(current_user.id, 'upload', 'attachment', item.id, f'Uploaded {uploaded_count} file(s) to item: {item.name}')
        flash(f'✅ {uploaded_count} file(s) uploaded successfully!', 'success')
    
    if rejected_count > 0 and uploaded_count == 0:
        flash(f'⚠️ All {rejected_count} file(s) were rejected. Check file types and sizes above.', 'warning')
    
    return redirect(url_for('item_detail', uuid=item.uuid))

@app.route('/attachment/<int:id>/delete', methods=['POST'])
@login_required
@item_permission_required
def delete_attachment(id):
    attachment = Attachment.query.get_or_404(id)
    item = attachment.item
    
    try:
        if attachment.file_path and is_safe_file_path(attachment.file_path):
            if os.path.exists(attachment.file_path):
                os.remove(attachment.file_path)
    except Exception as e:
        logging.error(f"Error deleting attachment file {attachment.id}: {e}")
    
    db.session.delete(attachment)
    db.session.commit()
    
    log_audit(current_user.id, 'delete', 'attachment', id, f'Deleted attachment: {attachment.original_filename}')
    flash('Attachment deleted successfully!', 'success')
    return redirect(url_for('item_edit', uuid=item.uuid))

@app.route('/attachment/<int:attachment_id>/rename', methods=['POST'])
@login_required
@item_permission_required
def rename_attachment(attachment_id):
    """Rename an attachment file"""
    attachment = Attachment.query.get_or_404(attachment_id)
    
    try:
        data = request.get_json()
        new_name = data.get('new_name', '').strip()
        
        if not new_name:
            return jsonify({'success': False, 'error': 'New name cannot be empty'}), 400
        
        # Update the original filename
        old_name = attachment.original_filename
        attachment.original_filename = new_name
        db.session.commit()
        
        log_audit(current_user.id, 'update', 'attachment', attachment_id, f'Renamed attachment from "{old_name}" to "{new_name}"')

        return jsonify({'success': True})

    except Exception as e:
        logging.error(f"Error renaming attachment {attachment_id}: {str(e)}")
        return jsonify({'success': False, 'error': 'An error occurred while renaming the attachment'}), 500


@app.route('/item/<int:item_id>/datasheets', methods=['POST'])
@login_required
@item_permission_required
def update_datasheets(item_id):
    """Update item datasheet URLs via AJAX"""
    item = Item.query.get_or_404(item_id)
    
    try:
        data = request.get_json()
        datasheets = data.get('datasheets', [])
        
        # Validate datasheets
        for ds in datasheets:
            if not isinstance(ds, dict) or 'url' not in ds:
                return jsonify({'success': False, 'error': 'Invalid datasheet format'}), 400
            if not ds['url'].strip():
                return jsonify({'success': False, 'error': 'URL cannot be empty'}), 400
        
        # Save as JSON
        import json
        item.datasheet_urls = json.dumps(datasheets)
        db.session.commit()
        
        log_audit(current_user.id, 'update', 'item', item.id, f'Updated datasheets for item: {item.name}')

        return jsonify({'success': True})

    except Exception as e:
        logging.error(f"Error updating datasheets for item {item_id}: {str(e)}")
        return jsonify({'success': False, 'error': 'An error occurred while updating datasheets'}), 500


@app.route('/uploads/<path:filename>')
@login_required
def uploaded_file(filename):
    """Serve uploaded files from uploads folder"""
    # Prevent path traversal attacks
    safe_path = safe_join(app.config['UPLOAD_FOLDER'], filename)
    if safe_path is None or not os.path.exists(safe_path):
        abort(404)
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)

# ============= CATEGORY ROUTES =============

@app.route('/manage')
@login_required
def item_management():
    """Combined management page for categories, footprints, and tags"""
    # Check if user has view permission for item settings (not item_form)
    if not current_user.has_permission('settings_sections.item_management', 'view'):
        flash('You do not have permission to view item management settings.', 'danger')
        return redirect(url_for('settings'))
    
    categories = Category.query.order_by(Category.name).all()
    footprints = Footprint.query.order_by(Footprint.name).all()
    tags = Tag.query.order_by(Tag.name).all()
    
    can_edit = current_user.has_permission('settings_sections.item_management', 'edit')
    can_delete = current_user.has_permission('settings_sections.item_management', 'delete')
    
    return render_template('item_management.html', 
                          categories=categories, 
                          footprints=footprints, 
                          tags=tags,
                          can_edit=can_edit,
                          can_delete=can_delete)

@app.route('/categories')
@login_required
def categories():
    """Redirect to unified item management page"""
    return redirect(url_for('item_management'))


@app.route('/category/new', methods=['GET', 'POST'])
@login_required
@permission_required("settings_sections.item_management", "edit")
def category_new():
    form = CategoryForm()
    
    if form.validate_on_submit():
        # Check for duplicate name
        existing = Category.query.filter_by(name=form.name.data).first()
        if existing:
            flash(f'Category "{form.name.data}" already exists!', 'danger')
            return render_template('category_form.html', form=form, title='New Category')
        
        category = Category(
            name=form.name.data,
            description=form.description.data,
            color=form.color.data or '#6c757d'
        )
        db.session.add(category)
        db.session.commit()
        
        log_audit(current_user.id, 'create', 'category', category.id, f'Created category: {category.name}')
        flash(f'Category "{category.name}" created successfully!', 'success')
        return redirect(url_for('item_management'))
    
    return render_template('category_form.html', form=form, title='New Category')

@app.route('/category/<int:id>/edit', methods=['GET', 'POST'])
@login_required
@permission_required("settings_sections.item_management", "edit")
def category_edit(id):
    category = Category.query.get_or_404(id)
    form = CategoryForm(obj=category)
    
    if form.validate_on_submit():
        category.name = form.name.data
        category.description = form.description.data
        category.color = form.color.data or '#6c757d'
        db.session.commit()
        
        log_audit(current_user.id, 'update', 'category', category.id, f'Updated category: {category.name}')
        flash(f'Category "{category.name}" updated successfully!', 'success')
        return redirect(url_for('item_management'))
    
    return render_template('category_form.html', form=form, category=category, title='Edit Category')

@app.route('/category/<int:id>/delete', methods=['POST'])
@login_required
@permission_required("settings_sections.item_management", "delete")
def category_delete(id):
    category = Category.query.get_or_404(id)
    category_name = category.name
    
    if category.items:
        flash(f'Cannot delete category "{category_name}" because it has {len(category.items)} items.', 'danger')
        return redirect(url_for('item_management'))
    
    db.session.delete(category)
    db.session.commit()
    
    log_audit(current_user.id, 'delete', 'category', id, f'Deleted category: {category_name}')
    flash(f'Category "{category_name}" deleted successfully!', 'success')
    return redirect(url_for('item_management'))

# ============= USER MANAGEMENT ROUTES =============

@app.route('/users')
@login_required
def users():
    # Check granular permission for user management
    if not current_user.has_permission('settings_sections.users_roles', 'view'):
        flash('You do not have permission to view users.', 'danger')
        return redirect(url_for('settings'))
    
    from models import Setting, Role
    users = User.query.order_by(User.username).all()
    roles = Role.query.order_by(Role.name).all()
    signup_enabled = Setting.get('signup_enabled', True)
    
    can_create_user = current_user.has_permission('settings_sections.users_roles', 'users_create')
    can_edit_user = current_user.has_permission('settings_sections.users_roles', 'users_edit')
    can_delete_user = current_user.has_permission('settings_sections.users_roles', 'users_delete')
    can_create_role = current_user.has_permission('settings_sections.users_roles', 'roles_create')
    can_edit_role = current_user.has_permission('settings_sections.users_roles', 'roles_edit')
    can_delete_role = current_user.has_permission('settings_sections.users_roles', 'roles_delete')
    
    return render_template('users.html', 
                          users=users, 
                          roles=roles, 
                          signup_enabled=signup_enabled,
                          can_create_user=can_create_user,
                          can_edit_user=can_edit_user,
                          can_delete_user=can_delete_user,
                          can_create_role=can_create_role,
                          can_edit_role=can_edit_role,
                          can_delete_role=can_delete_role)

@app.route('/toggle-signup', methods=['POST'])
@login_required
@permission_required("settings_sections.users_roles", "users_edit")
def toggle_signup():
    from models import Setting
    signup_enabled = request.form.get('signup_enabled') == 'on'
    Setting.set('signup_enabled', signup_enabled, 'Enable/disable user signup form')
    
    status = 'enabled' if signup_enabled else 'disabled'
    flash(f'User signup form has been {status}.', 'success')
    log_audit(current_user.id, 'update', 'setting', 0, f'Signup form {status}')
    return redirect(url_for('users'))

@app.route('/user/new', methods=['GET', 'POST'])
@login_required
@permission_required("settings_sections.users_roles", "users_create")
def user_new():
    form = UserForm()
    
    if form.validate_on_submit():
        # Check for duplicate username or email
        existing_username = User.query.filter_by(username=form.username.data).first()
        existing_email = User.query.filter_by(email=form.email.data).first()
        
        if existing_username:
            flash(f'Username "{form.username.data}" already exists!', 'danger')
            return render_template('user_form.html', form=form, title='New User')
        
        if existing_email:
            flash(f'Email "{form.email.data}" already registered!', 'danger')
            return render_template('user_form.html', form=form, title='New User')
        
        user = User(
            username=form.username.data,
            email=form.email.data,
            role_id=form.role_id.data,
            is_active=form.is_active.data,
            max_login_attempts=form.max_login_attempts.data or 0,
            allow_password_reset=form.allow_password_reset.data,
            auto_unlock_enabled=form.auto_unlock_enabled.data,
            auto_unlock_minutes=form.auto_unlock_minutes.data
        )
        user.set_password(form.password.data)
        
        # Handle profile photo upload
        if form.profile_photo.data:
            file = form.profile_photo.data
            if file and allowed_file(file.filename, {'png', 'jpg', 'jpeg'}):
                # Check file size (max 1MB)
                file.seek(0, os.SEEK_END)
                file_size = file.tell()
                file.seek(0)
                
                if file_size > 1024 * 1024:  # 1MB
                    flash('Profile photo must be smaller than 1MB', 'danger')
                    return render_template('user_form.html', form=form, title='New User')
                
                # Save with username as filename - sanitize extension
                ext = secure_filename(file.filename.rsplit('.', 1)[1].lower())
                filename = f"{secure_filename(form.username.data)}.{ext}"
                filepath = os.path.join(app.config['UPLOAD_FOLDER'], 'userpicture', filename)
                file.save(filepath)
                user.profile_photo = filename
        
        db.session.add(user)
        db.session.commit()
        
        log_audit(current_user.id, 'create', 'user', user.id, f'Created user: {user.username}')
        flash(f'User "{user.username}" created successfully!', 'success')
        return redirect(url_for('users'))
    
    return render_template('user_form.html', form=form, title='New User')

@app.route('/user/<int:id>/edit', methods=['GET', 'POST'])
@login_required
@permission_required("settings_sections.users_roles", "users_edit")
def user_edit(id):
    user = User.query.get_or_404(id)
    
    if user.is_demo_user and app.config.get('DEMO_MODE', False):
        flash('Cannot modify admin user profile in demo mode.', 'warning')
        return redirect(url_for('users'))
    
    form = UserForm()
    
    if form.validate_on_submit():
        # Check for action button clicks first
        action = request.form.get('action')
        
        # Handle profile photo delete (stay on form)
        if action == 'delete_photo':
            if user.profile_photo:
                filepath = os.path.join(app.config['UPLOAD_FOLDER'], 'userpicture', user.profile_photo)
                if is_safe_file_path(filepath) and os.path.exists(filepath):
                    os.remove(filepath)
                user.profile_photo = None
                log_audit(current_user.id, 'update', 'user', user.id, f'Deleted profile photo for user: {user.username}')
                db.session.commit()
                flash('Profile photo deleted successfully!', 'success')
            return redirect(url_for('user_edit', id=user.id))
        
        # Handle profile photo upload (stay on form)
        elif action == 'upload_photo':
            if form.profile_photo.data:
                file = form.profile_photo.data
                if file and allowed_file(file.filename, {'png', 'jpg', 'jpeg'}):
                    # Check file size (max 1MB)
                    file.seek(0, os.SEEK_END)
                    file_size = file.tell()
                    file.seek(0)
                    
                    if file_size > 1024 * 1024:  # 1MB
                        flash('Profile photo must be smaller than 1MB', 'danger')
                        return render_template('user_form.html', form=form, user=user, title='Edit User', config=app.config)
                    
                    # Delete old photo if exists
                    if user.profile_photo:
                        old_file = os.path.join(app.config['UPLOAD_FOLDER'], 'userpicture', user.profile_photo)
                        if is_safe_file_path(old_file) and os.path.exists(old_file):
                            os.remove(old_file)

                    # Save with username as filename - sanitize extension
                    ext = secure_filename(file.filename.rsplit('.', 1)[1].lower())
                    filename = f"{secure_filename(form.username.data)}.{ext}"
                    filepath = os.path.join(app.config['UPLOAD_FOLDER'], 'userpicture', filename)
                    file.save(filepath)
                    user.profile_photo = filename
                    log_audit(current_user.id, 'update', 'user', user.id, f'Updated profile photo for user: {user.username}')
                    db.session.commit()
                    flash('Profile photo uploaded successfully!', 'success')
                else:
                    flash('Only PNG and JPEG files are allowed.', 'danger')
            return redirect(url_for('user_edit', id=user.id))
        
        # Regular form submission (full user edit)
        user.username = form.username.data
        user.email = form.email.data
        user.role_id = form.role_id.data
        user.is_active = form.is_active.data
        user.max_login_attempts = form.max_login_attempts.data or 0
        user.allow_password_reset = form.allow_password_reset.data
        user.auto_unlock_enabled = form.auto_unlock_enabled.data
        user.auto_unlock_minutes = form.auto_unlock_minutes.data
        
        # Check if admin is unlocking the account
        unlock_account = request.form.get('unlock_account')
        if unlock_account and user.account_locked_until:
            user.account_locked_until = None
            user.failed_login_attempts = 0
            from datetime import timezone as tz_module
            timestamp = datetime.now(tz_module.utc).strftime('%Y-%m-%d %H:%M:%S UTC')
            log_audit(current_user.id, 'update', 'user', user.id, f'{current_user.username} manually unlock: {user.username} on {timestamp}')
            flash(f'Account "{user.username}" has been unlocked.', 'success')
        
        if form.password.data:
            user.set_password(form.password.data)
        
        db.session.commit()
        
        log_audit(current_user.id, 'update', 'user', user.id, f'Updated user: {user.username}')
        flash(f'User "{user.username}" updated successfully!', 'success')
        return redirect(url_for('users'))
    else:
        # Pre-populate form fields on GET request (for display)
        form.username.data = user.username
        form.email.data = user.email
        form.role_id.data = user.role_id
        form.is_active.data = user.is_active
        form.max_login_attempts.data = user.max_login_attempts
        form.allow_password_reset.data = user.allow_password_reset
        form.auto_unlock_enabled.data = user.auto_unlock_enabled
        form.auto_unlock_minutes.data = user.auto_unlock_minutes
    
    return render_template('user_form.html', form=form, user=user, title='Edit User', config=app.config)

@app.route('/user/<int:id>/delete', methods=['POST'])
@login_required
@permission_required("settings_sections.users_roles", "users_delete")
def user_delete(id):
    if id == current_user.id:
        flash('You cannot delete your own account.', 'danger')
        return redirect(url_for('users'))
    
    user = User.query.get_or_404(id)
    
    if user.is_demo_user and app.config.get('DEMO_MODE', False):
        flash('Cannot delete admin user in demo mode.', 'warning')
        return redirect(url_for('users'))
    username = user.username
    
    db.session.delete(user)
    db.session.commit()
    
    log_audit(current_user.id, 'delete', 'user', id, f'Deleted user: {username}')
    flash(f'User "{username}" deleted successfully!', 'success')
    return redirect(url_for('users'))

@app.route('/user/<int:id>/unlock', methods=['POST'])
@login_required
@permission_required("settings_sections.users_roles", "users_edit")
def user_unlock(id):
    """Unlock a locked user account"""
    user = User.query.get_or_404(id)
    
    if user.account_locked_until:
        user.account_locked_until = None
        user.failed_login_attempts = 0
        db.session.commit()
        
        from datetime import timezone as tz_module
        timestamp = datetime.now(tz_module.utc).strftime('%Y-%m-%d %H:%M:%S UTC')
        log_audit(current_user.id, 'update', 'user', user.id, f'{current_user.username} manually unlock: {user.username} on {timestamp}')
        flash(f'User "{user.username}" account unlocked successfully!', 'success')
    else:
        flash(f'User "{user.username}" account is not locked.', 'info')
    
    return redirect(url_for('users'))

# ============= ROLE MANAGEMENT =============

@app.route('/roles')
@login_required
def roles():
    """Redirect to users page - role management is now integrated there"""
    return redirect(url_for('users'))

@app.route('/role/new', methods=['GET', 'POST'])
@login_required
@permission_required("settings_sections.users_roles", "roles_create")
def role_new():
    from models import Role
    from forms import RoleForm
    form = RoleForm()
    
    if form.validate_on_submit():
        # Check for duplicate role name
        existing_role = Role.query.filter_by(name=form.name.data).first()
        if existing_role:
            flash(f'Role "{form.name.data}" already exists!', 'danger')
            return render_template('role_form.html', form=form, title='New Role', role=None)
        
        # Create new role with default permissions (all false)
        default_perms = {
            # Item Management (granular)
            "items": {
                "view": False, 
                "create": False,
                "delete": False, 
                "edit_name": False,
                "edit_sku_type": False,
                "edit_description": False,
                "edit_datasheet": False,
                "edit_upload": False,
                "edit_lending": False,
                "edit_price": False, 
                "edit_quantity": False, 
                "edit_location": False,
                "edit_category": False,
                "edit_footprint": False,
                "edit_tags": False,
                "edit_parameters": False
            },
            # Page Permissions
            "pages": {
                "visual_storage": {"view": False},
                "notifications": {"view": False}
            },
            # Settings Page Sections
            "settings_sections": {
                "system_settings": {"view": False, "edit": False},
                "reports": {"view": False},
                "item_management": {"view": False, "edit": False, "delete": False},
                "magic_parameters": {"view": False, "edit": False, "delete": False},
                "location_management": {"view": False, "edit": False, "delete": False},
                "users_roles": {
                    "view": False,
                    "roles_create": False,
                    "roles_edit": False,
                    "roles_delete": False,
                    "users_create": False,
                    "users_edit": False,
                    "users_delete": False
                },
                "backup_restore": {"view": False, "upload_export": False, "delete": False}
            }
        }
        
        role = Role(
            name=form.name.data,
            description=form.description.data,
            is_system_role=False
        )
        role.set_permissions(default_perms)
        db.session.add(role)
        db.session.commit()
        
        log_audit(current_user.id, 'create', 'role', role.id, f'Created role: {role.name}')
        flash(f'Role "{role.name}" created successfully! Now configure its permissions.', 'success')
        return redirect(url_for('role_edit', id=role.id))
    
    return render_template('role_form.html', form=form, title='New Role', role=None)

@app.route('/role/<int:id>/edit', methods=['GET', 'POST'])
@login_required
@permission_required("settings_sections.users_roles", "roles_edit")
def role_edit(id):
    from models import Role
    from forms import RoleForm
    role = Role.query.get_or_404(id)
    
    form = RoleForm(obj=role)
    
    if request.method == 'POST':
        if 'update_info' in request.form:
            # Update role name and description
            if form.validate_on_submit():
                role.name = form.name.data
                role.description = form.description.data
                db.session.commit()
                log_audit(current_user.id, 'update', 'role', role.id, f'Updated role info: {role.name}')
                flash(f'Role "{role.name}" updated successfully!', 'success')
        
        if 'update_permissions' in request.form:
            # Update permissions with new structure
            perms = {
                "items": {},
                "pages": {},
                "settings_sections": {}
            }
            
            # Items permissions (granular)
            item_actions = ['view', 'create', 'delete', 'edit_name', 'edit_sku_type', 'edit_description', 
                           'edit_datasheet', 'edit_upload', 'edit_lending', 'edit_price', 'edit_quantity', 
                           'edit_location', 'edit_category', 'edit_footprint', 'edit_tags', 'edit_parameters']
            for action in item_actions:
                checkbox_name = f'items_{action}'
                perms['items'][action] = checkbox_name in request.form
            
            # Page permissions (Settings page removed - accessible to all users)
            # Visual Storage and Notifications edit controlled by settings_sections
            perms['pages']['visual_storage'] = {
                'view': 'pages_visual_storage_view' in request.form
            }
            perms['pages']['notifications'] = {
                'view': 'pages_notifications_view' in request.form
            }
            
            # Settings sections permissions
            # System Settings
            perms['settings_sections']['system_settings'] = {
                'view': 'settings_sections_system_settings_view' in request.form,
                'edit': 'settings_sections_system_settings_edit' in request.form
            }
            
            # Reports
            perms['settings_sections']['reports'] = {
                'view': 'settings_sections_reports_view' in request.form
            }
            
            # Item Management
            perms['settings_sections']['item_management'] = {
                'view': 'settings_sections_item_management_view' in request.form,
                'edit': 'settings_sections_item_management_edit' in request.form,
                'delete': 'settings_sections_item_management_delete' in request.form
            }
            
            # Magic Parameters
            perms['settings_sections']['magic_parameters'] = {
                'view': 'settings_sections_magic_parameters_view' in request.form,
                'edit': 'settings_sections_magic_parameters_edit' in request.form,
                'delete': 'settings_sections_magic_parameters_delete' in request.form
            }
            
            # Location Management
            perms['settings_sections']['location_management'] = {
                'view': 'settings_sections_location_management_view' in request.form,
                'edit': 'settings_sections_location_management_edit' in request.form,
                'delete': 'settings_sections_location_management_delete' in request.form
            }
            
            # User & Role Management
            perms['settings_sections']['users_roles'] = {
                'view': 'settings_sections_users_roles_view' in request.form,
                'roles_create': 'settings_sections_users_roles_roles_create' in request.form,
                'roles_edit': 'settings_sections_users_roles_roles_edit' in request.form,
                'roles_delete': 'settings_sections_users_roles_roles_delete' in request.form,
                'users_create': 'settings_sections_users_roles_users_create' in request.form,
                'users_edit': 'settings_sections_users_roles_users_edit' in request.form,
                'users_delete': 'settings_sections_users_roles_users_delete' in request.form
            }
            
            # Backup & Restore
            perms['settings_sections']['backup_restore'] = {
                'view': 'settings_sections_backup_restore_view' in request.form,
                'upload_export': 'settings_sections_backup_restore_upload_export' in request.form,
                'delete': 'settings_sections_backup_restore_delete' in request.form
            }
            
            role.set_permissions(perms)
            db.session.commit()
            
            log_audit(current_user.id, 'update', 'role', role.id, f'Updated permissions for role: {role.name}')
            flash(f'Permissions for role "{role.name}" updated successfully!', 'success')
        
        if 'update_info' in request.form or 'update_permissions' in request.form:
            # Reload the role from database and re-render the form
            db.session.refresh(role)
            form = RoleForm(obj=role)
            return render_template('role_form.html', form=form, role=role, title='Edit Role')
    
    return render_template('role_form.html', form=form, role=role, title='Edit Role')

@app.route('/role/<int:id>/delete', methods=['POST'])
@login_required
@permission_required("settings_sections.users_roles", "roles_delete")
def role_delete(id):
    from models import Role
    role = Role.query.get_or_404(id)
    
    # Prevent deleting system roles
    if role.is_system_role:
        flash('Cannot delete system role templates.', 'danger')
        return redirect(url_for('roles'))
    
    # Check if any users have this role
    if role.users:
        flash(f'Cannot delete role "{role.name}" because it is assigned to {len(role.users)} user(s).', 'danger')
        return redirect(url_for('roles'))
    
    role_name = role.name
    db.session.delete(role)
    db.session.commit()
    
    log_audit(current_user.id, 'delete', 'role', id, f'Deleted role: {role_name}')
    flash(f'Role "{role_name}" deleted successfully!', 'success')
    return redirect(url_for('roles'))

@app.route('/role/<int:id>/clone', methods=['POST'])
@login_required
@permission_required("settings_sections.users_roles", "roles_create")
def role_clone(id):
    from models import Role
    source_role = Role.query.get_or_404(id)
    
    # Generate unique name for cloned role
    base_name = f"{source_role.name} (Copy)"
    new_name = base_name
    counter = 1
    while Role.query.filter_by(name=new_name).first():
        new_name = f"{base_name} {counter}"
        counter += 1
    
    # Clone the role
    new_role = Role(
        name=new_name,
        description=source_role.description,
        is_system_role=False,
        permissions=source_role.permissions
    )
    db.session.add(new_role)
    db.session.commit()
    
    log_audit(current_user.id, 'create', 'role', new_role.id, f'Cloned role from: {source_role.name}')
    flash(f'Role "{source_role.name}" cloned as "{new_name}". You can now customize it.', 'success')
    return redirect(url_for('role_edit', id=new_role.id))

# ============= REPORTS AND ANALYTICS =============

@app.route('/low-stock')
@login_required
def low_stock():
    items = Item.query.filter(Item.quantity <= Item.min_quantity).order_by(Item.quantity).all()
    return render_template('low_stock.html', items=items)

@app.route('/reports')
@login_required
def reports():
    # Check granular permission for reports
    if not current_user.has_permission('settings_sections.reports', 'view'):
        flash('You do not have permission to view reports.', 'danger')
        return redirect(url_for('settings'))
    
    total_items = Item.query.count()
    total_value = db.session.query(db.func.sum(Item.price * Item.quantity)).scalar() or 0
    low_stock_count = Item.query.filter(Item.quantity <= Item.min_quantity).count()
    
    category_stats = db.session.query(
        Category.name,
        db.func.count(Item.id).label('count')
    ).join(Item).group_by(Category.name).all()
    
    return render_template('reports.html',
                         total_items=total_items,
                         total_value=total_value,
                         low_stock_count=low_stock_count,
                         category_stats=category_stats)

# ============= LOCATION MANAGEMENT ROUTES =============

@app.route('/location-management')
@login_required
def location_management():
    """Combined location and rack management page"""
    # Check if user has view permission for location settings (not visual_storage)
    if not current_user.has_permission('settings_sections.location_management', 'view'):
        # Check if user has visual storage access and redirect there instead
        if current_user.has_permission('pages.visual_storage', 'view'):
            flash('You do not have permission to manage racks. You can only view them in Visual Storage.', 'warning')
            return redirect(url_for('visual_storage'))
        else:
            flash('You do not have permission to view location management settings.', 'danger')
            return redirect(url_for('settings'))
    
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

@app.route('/location/<int:id>')
@login_required
def location_detail(id):
    """View location details with items and racks"""
    from models import Location
    location = Location.query.get_or_404(id)
    items = location.items
    racks = location.racks
    return render_template('location_detail.html', 
                          location=location,
                          items=items,
                          racks=racks)

@app.route('/location/new', methods=['GET', 'POST'])
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
        
        # Handle picture upload with UUID-based path structure
        if form.picture.data:
            file = form.picture.data
            
            # Check file size against system settings
            max_size_mb = int(Setting.get('max_file_size_mb', '10'))
            max_size_bytes = max_size_mb * 1024 * 1024
            
            file.seek(0, 2)
            file_size = file.tell()
            file.seek(0)
            
            if file_size > max_size_bytes:
                flash(f'File size exceeds maximum allowed size of {max_size_mb}MB', 'danger')
                db.session.delete(location)
                db.session.commit()
                return render_template('location_form.html', form=form, location=None)
            
            # Only allow PNG and JPEG
            if file.filename and allowed_file(file.filename):
                ext = file.filename.rsplit('.', 1)[1].lower()
                if ext not in ['png', 'jpg', 'jpeg']:
                    flash('Only PNG and JPEG images are allowed for locations!', 'danger')
                    db.session.delete(location)
                    db.session.commit()
                    return render_template('location_form.html', form=form, location=None)
                
                # Use UUID-based directory structure: /uploads/locations/{location_uuid}/
                picture_uuid = ''.join(secrets.choice(string.ascii_uppercase + string.digits) for _ in range(12))
                
                if ext == 'jpg':
                    ext = 'jpeg'
                filename = f"{picture_uuid}.{ext}"
                
                # Create location-specific directory with UUID
                location_dir = os.path.join(app.config['UPLOAD_FOLDER'], 'locations', location.uuid)
                os.makedirs(location_dir, exist_ok=True)
                
                filepath = os.path.join(location_dir, filename)
                file.save(filepath)
                # Store path as {location_uuid}/{picture_uuid}.ext
                location.picture = f"{location.uuid}/{filename}"
                db.session.commit()
        
        log_audit(current_user.id, 'create', 'location', location.id, f'Created location: {location.name}')
        flash(f'Location "{location.name}" created successfully!', 'success')
        return redirect(url_for('location_management'))
    
    max_file_size_mb = int(Setting.get('max_file_size_mb', '10'))
    return render_template('location_form.html', form=form, location=None, max_file_size_mb=max_file_size_mb)

@app.route('/location/<int:id>/edit', methods=['GET', 'POST'])
@login_required
@permission_required("settings_sections.location_management", "edit")
def location_edit(id):
    """Edit location"""
    from models import Location
    from forms import LocationForm
    from werkzeug.utils import secure_filename
    
    location = Location.query.get_or_404(id)
    form = LocationForm(obj=location)
    
    if form.validate_on_submit():
        location.name = form.name.data
        location.info = form.info.data
        location.description = form.description.data
        location.color = form.color.data or '#6c757d'
        
        # Handle picture deletion
        if request.form.get('delete_picture'):
            if location.picture:
                # Path is {location_uuid}/{picture_uuid}.ext
                old_path = os.path.join(app.config['UPLOAD_FOLDER'], 'locations', location.picture)
                if is_safe_file_path(old_path) and os.path.exists(old_path):
                    os.remove(old_path)
                location.picture = None
        
        # Handle new picture upload
        if form.picture.data:
            file = form.picture.data
            if hasattr(file, 'filename') and file.filename and allowed_file(file.filename):
                # Check file size against system settings
                max_size_mb = int(Setting.get('max_file_size_mb', '10'))
                max_size_bytes = max_size_mb * 1024 * 1024
                
                file.seek(0, 2)
                file_size = file.tell()
                file.seek(0)
                
                if file_size > max_size_bytes:
                    flash(f'File size exceeds maximum allowed size of {max_size_mb}MB', 'danger')
                    return render_template('location_form.html', form=form, location=location)
                
                # Only allow PNG and JPEG
                ext = file.filename.rsplit('.', 1)[1].lower()
                if ext not in ['png', 'jpg', 'jpeg']:
                    flash('Only PNG and JPEG images are allowed for locations!', 'danger')
                    return render_template('location_form.html', form=form, location=location)
                
                # Delete old picture if exists
                if location.picture:
                    old_path = os.path.join(app.config['UPLOAD_FOLDER'], 'locations', location.picture)
                    if is_safe_file_path(old_path) and os.path.exists(old_path):
                        os.remove(old_path)
                
                # Use UUID-based path: /uploads/locations/{location_uuid}/{picture_uuid}.ext
                picture_uuid = ''.join(secrets.choice(string.ascii_uppercase + string.digits) for _ in range(12))
                
                if ext == 'jpg':
                    ext = 'jpeg'
                filename = f"{picture_uuid}.{ext}"
                
                location_dir = os.path.join(app.config['UPLOAD_FOLDER'], 'locations', location.uuid)
                os.makedirs(location_dir, exist_ok=True)
                
                filepath = os.path.join(location_dir, filename)
                file.save(filepath)
                # Store path as {location_uuid}/{picture_uuid}.ext
                location.picture = f"{location.uuid}/{filename}"
        
        db.session.commit()
        
        log_audit(current_user.id, 'update', 'location', location.id, f'Updated location: {location.name}')
        flash(f'Location "{location.name}" updated successfully!', 'success')
        return redirect(url_for('location_management'))
    
    max_file_size_mb = int(Setting.get('max_file_size_mb', '10'))
    return render_template('location_form.html', form=form, location=location, max_file_size_mb=max_file_size_mb)

@app.route('/location/<int:id>/delete', methods=['POST'])
@login_required
@permission_required("settings_sections.location_management", "delete")
def location_delete(id):
    """Delete location"""
    from models import Location
    
    location = Location.query.get_or_404(id)
    
    # Check if location is in use
    if location.items or location.racks:
        flash('Cannot delete location that is in use by items or racks!', 'danger')
        return redirect(url_for('location_management'))
    
    # Delete picture directory and all its contents
    if location.uuid:
        location_dir = os.path.join(app.config['UPLOAD_FOLDER'], 'locations', location.uuid)
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
    return redirect(url_for('location_management'))

@app.route('/location-picture/<path:filepath>')
@login_required
def location_picture(filepath):
    """Serve location pictures from UUID-based paths
    filepath format: {location_uuid}/{picture_uuid}.ext
    """
    location_dir = os.path.join(app.config['UPLOAD_FOLDER'], 'locations')
    # Prevent path traversal attacks
    safe_path = safe_join(location_dir, filepath)
    if safe_path is None or not os.path.exists(safe_path):
        abort(404)
    return send_from_directory(location_dir, filepath)

@app.route('/rack-picture/<path:filepath>')
@login_required
def rack_picture(filepath):
    """Serve rack pictures from UUID-based paths
    filepath format: {rack_uuid}/{picture_uuid}.ext
    """
    rack_dir = os.path.join(app.config['UPLOAD_FOLDER'], 'racks')
    # Prevent path traversal attacks
    safe_path = safe_join(rack_dir, filepath)
    if safe_path is None or not os.path.exists(safe_path):
        abort(404)
    return send_from_directory(rack_dir, filepath)

# ============= RACK MANAGEMENT ROUTES =============

@app.route('/rack-management')
@login_required
@permission_required("settings_sections.location_management", "view")
def rack_management():
    """Rack management page"""
    racks = Rack.query.order_by(Rack.name).all()
    can_edit = current_user.has_permission('settings_sections.location_management', 'edit')
    can_delete = current_user.has_permission('settings_sections.location_management', 'delete')
    return render_template('rack_management.html', racks=racks, can_edit=can_edit, can_delete=can_delete)

@app.route('/add-rack', methods=['POST'])
@login_required
@permission_required("settings_sections.location_management", "edit")
def add_rack():
    """Add a new rack"""
    name = request.form.get('name')
    description = request.form.get('description')
    location = request.form.get('location')
    rows = int(request.form.get('rows', 5))
    cols = int(request.form.get('cols', 5))
    
    rack = Rack(
        name=name,
        description=description,
        location_id=location if location else None,
        rows=rows,
        cols=cols
    )
    db.session.add(rack)
    db.session.commit()
    
    log_audit(current_user.id, 'create', 'rack', rack.id, f'Created rack: {name}')
    flash(f'Rack "{name}" created successfully!', 'success')
    return redirect(url_for('rack_management'))

@app.route('/edit-rack', methods=['POST'])
@login_required
@permission_required("settings_sections.location_management", "edit")
def edit_rack():
    """Edit rack"""
    rack_id = request.form.get('rack_id')
    rack = Rack.query.get_or_404(rack_id)
    
    rack.name = request.form.get('name')
    rack.description = request.form.get('description')
    rack.rows = int(request.form.get('rows', 5))
    rack.cols = int(request.form.get('cols', 5))
    
    db.session.commit()
    
    log_audit(current_user.id, 'update', 'rack', rack.id, f'Updated rack: {rack.name}')
    flash(f'Rack "{rack.name}" updated successfully!', 'success')
    return redirect(url_for('rack_management'))

@app.route('/delete-rack', methods=['POST'])
@login_required
@permission_required("settings_sections.location_management", "delete")
def delete_rack():
    """Delete rack and clear item locations"""
    rack_id = request.form.get('rack_id')
    rack = Rack.query.get_or_404(rack_id)
    rack_name = rack.name
    
    # Clear locations for all items in this rack
    items = Item.query.filter_by(rack_id=rack.id).all()
    for item in items:
        item.rack_id = None
        item.drawer = None
    
    db.session.delete(rack)
    db.session.commit()
    
    log_audit(current_user.id, 'delete', 'rack', rack_id, f'Deleted rack: {rack_name}, cleared {len(items)} item locations')
    flash(f'Rack "{rack_name}" deleted. {len(items)} item location(s) were cleared.', 'success')
    return redirect(url_for('rack_management'))

# REST-style rack routes for new UI
@app.route('/rack/new', methods=['GET', 'POST'])
@login_required
@permission_required("settings_sections.location_management", "edit")
def rack_new():
    """Create new rack with form"""
    if request.method == 'POST':
        name = request.form.get('name')
        
        # Allow duplicate names - UUID ensures uniqueness
        description = request.form.get('description')
        location_id = request.form.get('location_id')
        color = request.form.get('color', '#6c757d')
        rows = int(request.form.get('rows', 5))
        cols = int(request.form.get('cols', 5))
        
        # Validate against global max settings
        max_rows = int(Setting.get('max_drawer_rows', '10'))
        max_cols = int(Setting.get('max_drawer_cols', '10'))
        
        if rows < 1 or rows > max_rows:
            flash(f'Rows must be between 1 and {max_rows}!', 'danger')
            return redirect(url_for('rack_new'))
        
        if cols < 1 or cols > max_cols:
            flash(f'Columns must be between 1 and {max_cols}!', 'danger')
            return redirect(url_for('rack_new'))
        
        rack = Rack(
            name=name,
            description=description,
            location_id=int(location_id) if location_id and location_id != '0' else None,
            color=color,
            rows=rows,
            cols=cols
        )
        db.session.add(rack)
        db.session.commit()
        
        # Handle picture upload with UUID-based path structure
        if request.files.get('picture'):
            file = request.files['picture']
            
            # Check file size against system settings
            max_size_mb = int(Setting.get('max_file_size_mb', '10'))
            max_size_bytes = max_size_mb * 1024 * 1024
            
            file.seek(0, 2)
            file_size = file.tell()
            file.seek(0)
            
            if file_size > max_size_bytes:
                flash(f'File size exceeds maximum allowed size of {max_size_mb}MB', 'danger')
                return redirect(url_for('rack_new'))
            
            # Only allow PNG and JPEG
            if file.filename and allowed_file(file.filename):
                ext = file.filename.rsplit('.', 1)[1].lower()
                if ext not in ['png', 'jpg', 'jpeg']:
                    flash('Only PNG and JPEG images are allowed for racks!', 'danger')
                    return redirect(url_for('rack_new'))
                
                # Use UUID-based directory structure: /uploads/racks/{rack_uuid}/
                picture_uuid = ''.join(secrets.choice(string.ascii_uppercase + string.digits) for _ in range(12))
                
                if ext == 'jpg':
                    ext = 'jpeg'
                filename = f"{picture_uuid}.{ext}"
                
                # Create rack-specific directory with UUID
                rack_dir = os.path.join(app.config['UPLOAD_FOLDER'], 'racks', rack.uuid)
                os.makedirs(rack_dir, exist_ok=True)
                
                filepath = os.path.join(rack_dir, filename)
                file.save(filepath)
                # Store path as {rack_uuid}/{picture_uuid}.ext
                rack.picture = f"{rack.uuid}/{filename}"
                db.session.commit()
        
        log_audit(current_user.id, 'create', 'rack', rack.id, f'Created rack: {name}')
        flash(f'Rack "{name}" created successfully!', 'success')
        return redirect(url_for('location_management'))
    
    # GET - show form
    locations = Location.query.order_by(Location.name).all()
    max_drawer_rows = int(Setting.get('max_drawer_rows', '10'))
    max_drawer_cols = int(Setting.get('max_drawer_cols', '10'))
    max_file_size_mb = int(Setting.get('max_file_size_mb', '10'))
    return render_template('rack_form.html', rack=None, locations=locations, 
                         max_drawer_rows=max_drawer_rows, max_drawer_cols=max_drawer_cols,
                         max_file_size_mb=max_file_size_mb)

@app.route('/rack/<int:id>/edit', methods=['GET', 'POST'])
@login_required
@permission_required("settings_sections.location_management", "edit")
def rack_edit(id):
    """Edit rack with form"""
    rack = Rack.query.get_or_404(id)
    
    if request.method == 'POST':
        new_name = request.form.get('name')
        
        # Allow duplicate names - UUID ensures uniqueness
        rack.name = new_name
        rack.description = request.form.get('description')
        rack.color = request.form.get('color', '#6c757d')
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
            return redirect(url_for('rack_edit', id=id))
        
        if cols < 1 or cols > max_cols:
            flash(f'Columns must be between 1 and {max_cols}!', 'danger')
            return redirect(url_for('rack_edit', id=id))
        
        rack.rows = rows
        rack.cols = cols
        
        # If rack size decreased, clear items from drawers that are now out of bounds
        if rows < old_rows or cols < old_cols:
            items_cleared = 0
            items = Item.query.filter_by(rack_id=rack.id).all()
            
            for item in items:
                if item.drawer:
                    # Parse drawer ID (e.g., "R3-C5" -> row=3, col=5)
                    try:
                        parts = item.drawer.replace('R', '').replace('C', '-').split('-')
                        drawer_row = int(parts[0])
                        drawer_col = int(parts[1])
                        
                        # If drawer is now outside bounds, remove location
                        if drawer_row > rows or drawer_col > cols:
                            item.rack_id = None
                            item.drawer = None
                            item.location_id = None
                            items_cleared += 1
                    except:
                        # If parsing fails, skip this item
                        pass
            
            if items_cleared > 0:
                flash(f'Warning: {items_cleared} item(s) were removed from drawers outside new bounds. These items now have no location.', 'warning')
        
        # Handle picture deletion
        if request.form.get('delete_picture'):
            if rack.picture:
                old_path = os.path.join(app.config['UPLOAD_FOLDER'], 'racks', rack.picture)
                if is_safe_file_path(old_path) and os.path.exists(old_path):
                    os.remove(old_path)
                rack.picture = None
        
        # Handle new picture upload
        if request.files.get('picture'):
            file = request.files['picture']
            if hasattr(file, 'filename') and file.filename and allowed_file(file.filename):
                # Check file size against system settings
                max_size_mb = int(Setting.get('max_file_size_mb', '10'))
                max_size_bytes = max_size_mb * 1024 * 1024
                
                file.seek(0, 2)
                file_size = file.tell()
                file.seek(0)
                
                if file_size > max_size_bytes:
                    flash(f'File size exceeds maximum allowed size of {max_size_mb}MB', 'danger')
                    return redirect(url_for('rack_edit', id=id))
                
                # Only allow PNG and JPEG
                ext = file.filename.rsplit('.', 1)[1].lower()
                if ext not in ['png', 'jpg', 'jpeg']:
                    flash('Only PNG and JPEG images are allowed for racks!', 'danger')
                    return redirect(url_for('rack_edit', id=id))
                
                # Delete old picture if exists
                if rack.picture:
                    old_path = os.path.join(app.config['UPLOAD_FOLDER'], 'racks', rack.picture)
                    if is_safe_file_path(old_path) and os.path.exists(old_path):
                        os.remove(old_path)
                
                # Use UUID-based path: /uploads/racks/{rack_uuid}/{picture_uuid}.ext
                picture_uuid = ''.join(secrets.choice(string.ascii_uppercase + string.digits) for _ in range(12))
                
                if ext == 'jpg':
                    ext = 'jpeg'
                filename = f"{picture_uuid}.{ext}"
                
                rack_dir = os.path.join(app.config['UPLOAD_FOLDER'], 'racks', rack.uuid)
                os.makedirs(rack_dir, exist_ok=True)
                
                filepath = os.path.join(rack_dir, filename)
                file.save(filepath)
                # Store path as {rack_uuid}/{picture_uuid}.ext
                rack.picture = f"{rack.uuid}/{filename}"
        
        db.session.commit()
        
        log_audit(current_user.id, 'update', 'rack', rack.id, f'Updated rack: {rack.name} (size: {rows}x{cols})')
        flash(f'Rack "{rack.name}" updated successfully!', 'success')
        return redirect(url_for('location_management'))
    
    # GET - show form
    locations = Location.query.order_by(Location.name).all()
    max_drawer_rows = int(Setting.get('max_drawer_rows', '10'))
    max_drawer_cols = int(Setting.get('max_drawer_cols', '10'))
    max_file_size_mb = int(Setting.get('max_file_size_mb', '10'))
    return render_template('rack_form.html', rack=rack, locations=locations,
                         max_drawer_rows=max_drawer_rows, max_drawer_cols=max_drawer_cols,
                         max_file_size_mb=max_file_size_mb)

@app.route('/rack/<int:id>/delete', methods=['POST'])
@login_required
@permission_required("settings_sections.location_management", "delete")
def rack_delete(id):
    """Delete rack"""
    rack = Rack.query.get_or_404(id)
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
    return redirect(url_for('location_management'))

@app.route('/rack/<int:id>')
@login_required
def rack_detail(id):
    """View rack details"""
    rack = Rack.query.get_or_404(id)
    items = Item.query.filter_by(rack_id=rack.id).all()
    
    drawers = {}
    for item in items:
        if item.drawer:
            if item.drawer not in drawers:
                drawers[item.drawer] = []
            drawers[item.drawer].append(item)
    
    return render_template('rack_detail.html', rack=rack, items=items, drawers=drawers)

# ============= VISUAL STORAGE ROUTES =============

@app.route('/visual-storage')
@login_required
def visual_storage():
    """Display visual storage system"""
    # Check view permission
    if not current_user.has_permission('pages.visual_storage', 'view'):
        flash('You do not have permission to view visual storage.', 'danger')
        return redirect(url_for('index'))
    
    # Store edit permission in context for template
    can_edit = current_user.has_permission('pages.visual_storage', 'edit')
    
    # Check if user can access location management (for Manage Racks button)
    can_manage_racks = current_user.has_permission('settings_sections.location_management', 'view')
    
    rack_id = request.args.get('rack', type=int)
    location_id = request.args.get('location', type=int)
    
    # Get racks for display (filtered by location if selected)
    if location_id:
        # Filter by location
        location = Location.query.get_or_404(location_id)
        racks_to_display = location.racks
    else:
        # All racks
        racks_to_display = Rack.query.order_by(Rack.name).all()
    
    # Then filter by specific rack if requested
    if rack_id:
        racks_query = [r for r in racks_to_display if r.id == rack_id]
    else:
        racks_query = racks_to_display
    
    rack_data = []
    for rack in racks_query:
        items = Item.query.filter_by(rack_id=rack.id).all()
        
        drawers = {}
        for item in items:
            if item.drawer:
                if item.drawer not in drawers:
                    drawers[item.drawer] = {
                        'items': [],
                        'preview_image': None
                    }
                drawers[item.drawer]['items'].append(item)
                
                # Get first image for preview
                if not drawers[item.drawer]['preview_image'] and item.attachments:
                    for att in item.attachments:
                        if att.file_type in ['png', 'jpg', 'jpeg', 'gif']:
                            drawers[item.drawer]['preview_image'] = url_for('uploaded_file', filename=att.filename)
                            break
        
        rack_data.append({
            'id': rack.id,
            'name': rack.name,
            'description': rack.description,
            'physical_location': rack.physical_location,
            'rows': rack.rows,
            'cols': rack.cols,
            'drawers': drawers,
            'item_count': len(items),
            'unavailable_drawers': rack.get_unavailable_drawers()
        })
    
    # For the dropdown, show all racks for location selection, but filtered by current location for rack selection
    all_racks_for_dropdown = racks_to_display
    locations = Location.query.order_by(Location.name).all()
    return render_template('visual_storage.html', 
                          racks=rack_data, 
                          all_racks=all_racks_for_dropdown, 
                          locations=locations, 
                          current_location_id=location_id, 
                          current_rack_id=rack_id, 
                          can_edit_visual_storage=can_edit,
                          can_manage_racks=can_manage_racks)

@app.route('/api/drawer/<int:rack_id>/<path:drawer_id>')
@login_required
def get_drawer_contents(rack_id, drawer_id):
    """API endpoint to get drawer contents"""
    rack = Rack.query.get_or_404(rack_id)
    items = Item.query.filter_by(rack_id=rack_id, drawer=drawer_id).all()
    
    items_data = []
    for item in items:
        items_data.append({
            'id': item.id,
            'name': item.name,
            'sku': item.sku or 'N/A',
            'quantity': item.quantity,
            'available': item.get_available_quantity(),
            'uuid': item.uuid
        })
    
    return jsonify({
        'items': items_data,
        'rack': {
            'id': rack.id,
            'name': rack.name
        },
        'drawer_id': drawer_id,
        'is_unavailable': rack.is_drawer_unavailable(drawer_id)
    })

# ============= API ENDPOINTS FOR INLINE ADD =============

@app.route('/api/category/add', methods=['POST'])
@login_required
@permission_required("settings_sections.item_management", "edit")
def api_add_category():
    """API endpoint to add category from item form"""
    try:
        data = request.get_json()
        name = data.get('name', '').strip()
        description = data.get('description', '').strip()
        color = data.get('color', '#6c757d')
        
        if not name:
            return jsonify({'success': False, 'error': 'Category name is required'})
        
        # Check if exists
        existing = Category.query.filter_by(name=name).first()
        if existing:
            return jsonify({'success': False, 'error': 'Category already exists'})
        
        category = Category(name=name, description=description, color=color)
        db.session.add(category)
        db.session.commit()
        
        log_audit(current_user.id, 'create', 'category', category.id, f'Created category: {category.name}')
        
        return jsonify({
            'success': True,
            'category': {'id': category.id, 'name': category.name, 'color': category.color}
        })
    except Exception as e:
        db.session.rollback()
        logging.error(f"Error adding category: {str(e)}")
        return jsonify({'success': False, 'error': 'An error occurred while adding the category'})

@app.route('/api/footprint/add', methods=['POST'])
@login_required
@permission_required("settings_sections.item_management", "edit")
def api_add_footprint():
    """API endpoint to add footprint from item form"""
    try:
        data = request.get_json()
        name = data.get('name', '').strip()
        description = data.get('description', '').strip()
        color = data.get('color', '#6c757d')
        
        if not name:
            return jsonify({'success': False, 'error': 'Footprint name is required'})
        
        # Check if exists
        existing = Footprint.query.filter_by(name=name).first()
        if existing:
            return jsonify({'success': False, 'error': 'Footprint already exists'})
        
        footprint = Footprint(name=name, description=description, color=color)
        db.session.add(footprint)
        db.session.commit()
        
        log_audit(current_user.id, 'create', 'footprint', footprint.id, f'Created footprint: {footprint.name}')
        
        return jsonify({
            'success': True,
            'footprint': {'id': footprint.id, 'name': footprint.name, 'color': footprint.color}
        })
    except Exception as e:
        db.session.rollback()
        logging.error(f"Error adding footprint: {str(e)}")
        return jsonify({'success': False, 'error': 'An error occurred while adding the footprint'})

@app.route('/api/tag/add', methods=['POST'])
@login_required
@permission_required("settings_sections.item_management", "edit")
def api_add_tag():
    """API endpoint to add tag from item form"""
    try:
        data = request.get_json()
        name = data.get('name', '').strip()
        description = data.get('description', '').strip()
        color = data.get('color', '#6c757d')
        
        if not name:
            return jsonify({'success': False, 'error': 'Tag name is required'})
        
        # Check if exists
        existing = Tag.query.filter_by(name=name).first()
        if existing:
            return jsonify({'success': False, 'error': 'Tag already exists'})
        
        tag = Tag(name=name, description=description, color=color)
        db.session.add(tag)
        db.session.commit()
        
        log_audit(current_user.id, 'create', 'tag', tag.id, f'Created tag: {tag.name}')
        
        return jsonify({
            'success': True,
            'tag': {'id': tag.id, 'name': tag.name, 'description': tag.description, 'color': tag.color}
        })
    except Exception as e:
        db.session.rollback()
        logging.error(f"Error adding tag: {str(e)}")
        return jsonify({'success': False, 'error': 'An error occurred while adding the tag'})

@app.route('/api/location/add', methods=['POST'])
@login_required
@permission_required("settings_sections.location_management", "edit")
def api_add_location():
    """API endpoint to add location from item form"""
    try:
        data = request.get_json()
        name = data.get('name', '').strip()
        info = data.get('info', '').strip()
        description = data.get('description', '').strip()
        color = data.get('color', '#6c757d')
        
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

@app.route('/api/drawer/toggle-availability', methods=['POST'])
@login_required
@permission_required("settings_sections.location_management", "edit")
def toggle_drawer_availability():
    """Toggle drawer availability status"""
    try:
        data = request.get_json()
        rack_id = data.get('rack_id')
        drawer_id = data.get('drawer_id')
        is_unavailable = data.get('is_unavailable', False)
        
        rack = Rack.query.get_or_404(rack_id)
        unavailable = rack.get_unavailable_drawers()
        
        if is_unavailable:
            # Mark as unavailable
            if drawer_id not in unavailable:
                unavailable.append(drawer_id)
        else:
            # Mark as available
            if drawer_id in unavailable:
                unavailable.remove(drawer_id)
        
        rack.unavailable_drawers = json.dumps(unavailable)
        db.session.commit()
        
        log_audit(current_user.id, 'update', 'rack', rack.id,
                 f'Drawer {drawer_id} marked as {"unavailable" if is_unavailable else "available"}')

        return jsonify({'success': True})
    except Exception as e:
        db.session.rollback()
        logging.error(f"Error toggling drawer availability: {str(e)}")
        return jsonify({'success': False, 'error': 'An error occurred while toggling drawer availability'})

@app.route('/api/drawer/move-items', methods=['POST'])
@login_required
@permission_required("settings_sections.location_management", "edit")
def move_drawer_items():
    """Move all items from a drawer to a new location"""
    try:
        data = request.get_json()
        rack_id = data.get('rack_id')
        drawer_id = data.get('drawer_id')
        location_type = data.get('location_type')  # 'general' or 'drawer'
        
        # Get all items in the drawer
        items = Item.query.filter_by(rack_id=rack_id, drawer=drawer_id).all()
        
        if not items:
            return jsonify({'success': False, 'error': 'No items in this drawer'})
        
        # Move items based on location type
        if location_type == 'general':
            new_location_id = data.get('location_id')
            if not new_location_id or new_location_id == 0:
                return jsonify({'success': False, 'error': 'Please select a general location'})
            
            for item in items:
                item.location_id = new_location_id
                item.rack_id = None
                item.drawer = None
        else:  # drawer
            new_rack_id = data.get('new_rack_id')
            new_drawer = data.get('new_drawer')
            
            if not new_rack_id or new_rack_id == 0 or not new_drawer:
                return jsonify({'success': False, 'error': 'Please select a rack and drawer'})
            
            for item in items:
                item.location_id = None
                item.rack_id = new_rack_id
                item.drawer = new_drawer
        
        db.session.commit()
        
        log_audit(current_user.id, 'bulk_update', 'item', None,
                 f'Moved {len(items)} items from Rack {rack_id} Drawer {drawer_id}')

        return jsonify({'success': True, 'items_moved': len(items)})
    except Exception as e:
        db.session.rollback()
        logging.error(f"Error moving drawer items: {str(e)}")
        return jsonify({'success': False, 'error': 'An error occurred while moving drawer items'})

# ============= ERROR HANDLERS =============

@app.errorhandler(404)
def not_found_error(error):
    return render_template('404.html'), 404

@app.errorhandler(500)
def internal_error(error):
    db.session.rollback()

# ============= SETTINGS =============

@app.route('/settings')
@login_required
def settings():
    """Settings page hub - accessible to all users"""
    # Settings page is now accessible to all authenticated users
    # Edit capabilities for sub-sections are controlled by settings_sections permissions
    
    return render_template('settings.html')

@app.route('/settings/general')
@login_required
def settings_general():
    current_theme = current_user.theme or 'light'
    current_font = current_user.user_font or 'system'
    return render_template('settings_general.html', current_theme=current_theme, current_font=current_font)

@app.route('/save-theme', methods=['POST'])
@login_required
def save_theme():
    theme = request.form.get('theme', 'light')
    
    # Validate theme
    valid_themes = ['light', 'dark', 'blue', 'keqing']
    if theme not in valid_themes:
        theme = 'light'
    
    # Save to current user
    current_user.theme = theme
    db.session.commit()
    
    flash(f'Your theme changed to "{theme.capitalize()}"!', 'success')
    log_audit(current_user.id, 'update', 'user', current_user.id, f'Changed theme to {theme}')
    return redirect(url_for('settings_general'))

@app.route('/save-font', methods=['POST'])
@login_required
def save_font():
    user_font = request.form.get('user_font', 'system')
    
    # Validate font
    valid_fonts = ['system', 'open-dyslexic', 'courier']
    if user_font not in valid_fonts:
        user_font = 'system'
    
    # Save to current user
    current_user.user_font = user_font
    db.session.commit()
    
    font_names = {
        'system': 'System (Default)',
        'open-dyslexic': 'OpenDyslexic',
        'courier': 'Courier New'
    }
    
    flash(f'Your font changed to "{font_names.get(user_font, user_font)}"!', 'success')
    log_audit(current_user.id, 'update', 'user', current_user.id, f'Changed font to {user_font}')
    return redirect(url_for('settings_general'))

@app.route('/save-ui-preference', methods=['POST'])
@login_required
def save_ui_preference():
    """Save both theme and font together"""
    # Save theme
    theme = request.form.get('theme', 'light')
    valid_themes = ['light', 'dark', 'blue', 'keqing']
    if theme not in valid_themes:
        theme = 'light'
    
    current_user.theme = theme
    
    # Save font
    user_font = request.form.get('user_font', 'system')
    valid_fonts = ['system', 'open-dyslexic', 'courier']
    if user_font not in valid_fonts:
        user_font = 'system'
    
    current_user.user_font = user_font
    db.session.commit()
    
    flash(f'Your UI preferences have been saved!', 'success')
    log_audit(current_user.id, 'update', 'user', current_user.id, f'Changed UI preference: theme={theme}, font={user_font}')
    return redirect(url_for('settings_general'))

@app.route('/change-password', methods=['POST'])
@login_required
def change_password():
    """Change current user password"""
    if not current_user.allow_password_reset:
        flash('Password change is disabled for your account.', 'danger')
        return redirect(url_for('settings_general'))
    
    current_password = request.form.get('current_password')
    new_password = request.form.get('new_password')
    confirm_password = request.form.get('confirm_password')
    
    # Validate inputs
    if not current_password or not new_password or not confirm_password:
        flash('All password fields are required.', 'danger')
        return redirect(url_for('settings_general'))
    
    # Check current password
    if not current_user.check_password(current_password):
        flash('Current password is incorrect.', 'danger')
        return redirect(url_for('settings_general'))
    
    # Check new passwords match
    if new_password != confirm_password:
        flash('New passwords do not match.', 'danger')
        return redirect(url_for('settings_general'))
    
    # Check minimum length
    if len(new_password) < 6:
        flash('New password must be at least 6 characters.', 'danger')
        return redirect(url_for('settings_general'))
    
    # Set new password
    current_user.set_password(new_password)
    current_user.failed_login_attempts = 0  # Reset failed attempts
    current_user.account_locked_until = None
    db.session.commit()
    
    log_audit(current_user.id, 'update', 'user', current_user.id, 'Changed password')
    flash('Password changed successfully!', 'success')
    return redirect(url_for('settings_general'))

@app.route('/upload-profile-photo', methods=['POST'])
@login_required
def upload_profile_photo():
    """Upload user profile photo"""
    if 'profile_photo' not in request.files:
        flash('No file selected.', 'danger')
        return redirect(url_for('settings_general'))
    
    file = request.files['profile_photo']
    
    if file.filename == '':
        flash('No file selected.', 'danger')
        return redirect(url_for('settings_general'))
    
    if not allowed_file(file.filename, {'png', 'jpg', 'jpeg'}):
        flash('Only PNG and JPEG files are allowed.', 'danger')
        return redirect(url_for('settings_general'))
    
    # Check file size (max 1MB)
    file.seek(0, os.SEEK_END)
    file_size = file.tell()
    file.seek(0)
    
    if file_size > 1024 * 1024:  # 1MB
        flash('Profile photo must be smaller than 1MB.', 'danger')
        return redirect(url_for('settings_general'))
    
    # Delete old photo if exists
    if current_user.profile_photo:
        old_file = os.path.join(app.config['UPLOAD_FOLDER'], 'userpicture', current_user.profile_photo)
        if is_safe_file_path(old_file) and os.path.exists(old_file):
            os.remove(old_file)

    # Save with username as filename - sanitize extension
    ext = secure_filename(file.filename.rsplit('.', 1)[1].lower())
    filename = f"{secure_filename(current_user.username)}.{ext}"
    filepath = os.path.join(app.config['UPLOAD_FOLDER'], 'userpicture', filename)
    file.save(filepath)
    
    current_user.profile_photo = filename
    db.session.commit()
    
    log_audit(current_user.id, 'update', 'user', current_user.id, 'Updated profile photo')
    flash('Profile photo updated successfully!', 'success')
    return redirect(url_for('settings_general'))

@app.route('/delete-profile-photo', methods=['POST'])
@login_required
def delete_profile_photo():
    """Delete user profile photo"""
    if current_user.profile_photo:
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], 'userpicture', current_user.profile_photo)
        if is_safe_file_path(filepath) and os.path.exists(filepath):
            os.remove(filepath)
        
        current_user.profile_photo = None
        db.session.commit()
        
        log_audit(current_user.id, 'update', 'user', current_user.id, 'Deleted profile photo')
        flash('Profile photo deleted successfully!', 'success')
    
    return redirect(url_for('settings_general'))

@app.route('/save-table-columns-view', methods=['POST'])
@login_required
def save_table_columns_view():
    """Save user's preferred table columns view"""
    columns_json = request.form.get('columns', '[]')
    
    try:
        columns = json.loads(columns_json)
        
        # Validate columns
        valid_columns = ['type_model', 'sku', 'category', 'tags', 'footprint', 'quantity', 'total_price', 'price_per_unit', 'location', 'uuid', 'status']
        columns = [col for col in columns if col in valid_columns]
        
        # Save to current user
        current_user.set_table_columns(columns)
        db.session.commit()
        
        flash('Table columns view updated successfully!', 'success')
        log_audit(current_user.id, 'update', 'user', current_user.id, f'Updated table columns view')
    except Exception as e:
        logging.error(f"Error saving table columns for user {current_user.id}: {str(e)}")
        flash('Error saving table columns. Please try again.', 'danger')
    
    return redirect(url_for('settings_general'))

@app.route('/settings/system', methods=['GET', 'POST'])
@login_required
def settings_system():
    """System-wide settings"""
    # Check granular permission for system settings
    if not current_user.has_permission('settings_sections.system_settings', 'view'):
        flash('You do not have permission to view system settings.', 'danger')
        return redirect(url_for('settings'))
    
    can_edit = current_user.has_permission('settings_sections.system_settings', 'edit')
    
    if request.method == 'POST':
        if not can_edit:
            flash('You do not have permission to edit system settings.', 'danger')
            return redirect(url_for('settings_system'))
        try:
            # Currency setting
            currency = request.form.get('currency', '$').strip()
            if len(currency) > 7:
                flash('Currency symbol must be 7 characters or less!', 'danger')
                return redirect(url_for('settings_system'))
            
            # In DEMO MODE, skip file validation and use stored defaults
            if app.config.get('DEMO_MODE', False):
                # Demo mode: use fixed values, ignore form input for file settings
                allowed_extensions = 'jpg,jpeg,png,txt,md'
                max_file_size = 1
            else:
                # Production mode: validate file settings from form
                allowed_extensions = request.form.get('allowed_extensions', '').strip()
                if not allowed_extensions:
                    flash('You must specify at least one allowed file type!', 'danger')
                    return redirect(url_for('settings_system'))
                
                # Max file size validation (production mode only)
                max_file_size = request.form.get('max_file_size', '10')
                try:
                    max_file_size = int(max_file_size)
                    if max_file_size < 1 or max_file_size > 100:
                        flash('Max file size must be between 1 and 100 MB!', 'danger')
                        return redirect(url_for('settings_system'))
                except ValueError:
                    flash('Invalid max file size value!', 'danger')
                    return redirect(url_for('settings_system'))
            
            # Max drawer rows
            max_drawer_rows = request.form.get('max_drawer_rows', '10')
            try:
                max_drawer_rows = int(max_drawer_rows)
                if max_drawer_rows < 1 or max_drawer_rows > 32:
                    flash('Max drawer rows must be between 1 and 32!', 'danger')
                    return redirect(url_for('settings_system'))
            except ValueError:
                flash('Invalid max drawer rows value!', 'danger')
                return redirect(url_for('settings_system'))
            
            # Max drawer columns
            max_drawer_cols = request.form.get('max_drawer_cols', '10')
            try:
                max_drawer_cols = int(max_drawer_cols)
                if max_drawer_cols < 1 or max_drawer_cols > 32:
                    flash('Max drawer columns must be between 1 and 32!', 'danger')
                    return redirect(url_for('settings_system'))
            except ValueError:
                flash('Invalid max drawer columns value!', 'danger')
                return redirect(url_for('settings_system'))
            
            # Banner timeout
            banner_timeout = request.form.get('banner_timeout', '5')
            try:
                banner_timeout = int(banner_timeout)
                if banner_timeout < 0 or banner_timeout > 60:
                    flash('Banner timeout must be between 0 and 60 seconds!', 'danger')
                    return redirect(url_for('settings_system'))
            except ValueError:
                flash('Invalid banner timeout value!', 'danger')
                return redirect(url_for('settings_system'))
            
            # Save settings
            Setting.set('currency', currency, 'Currency symbol for prices')
            Setting.set('max_file_size_mb', max_file_size, 'Maximum file upload size in MB')
            Setting.set('allowed_extensions', allowed_extensions, 'Allowed file extensions (comma-separated)')
            Setting.set('max_drawer_rows', max_drawer_rows, 'Maximum drawer rows (1-32)')
            Setting.set('max_drawer_cols', max_drawer_cols, 'Maximum drawer columns (1-32)')
            Setting.set('banner_timeout', banner_timeout, 'Banner auto-dismiss timeout in seconds (0=permanent)')
            
            # Update app config dynamically
            app.config['MAX_CONTENT_LENGTH'] = max_file_size * 1024 * 1024
            
            flash('System settings updated successfully!', 'success')
            log_audit(current_user.id, 'update', 'settings', 0,
                     f'Updated system settings: currency={currency}, max_file_size={max_file_size}MB, drawer_size={max_drawer_rows}x{max_drawer_cols}, banner_timeout={banner_timeout}s')

        except Exception as e:
            logging.error(f"Error saving system settings: {str(e)}")
            flash('Error saving settings. Please try again.', 'danger')
        
        return redirect(url_for('settings_system'))
    
    # GET request - load current settings
    currency = Setting.get('currency', '$')
    max_file_size = Setting.get('max_file_size_mb', '10')
    allowed_extensions = Setting.get('allowed_extensions', 'pdf,png,jpg,jpeg,gif,txt,doc,docx')
    max_drawer_rows = Setting.get('max_drawer_rows', '10')
    max_drawer_cols = Setting.get('max_drawer_cols', '10')
    banner_timeout = Setting.get('banner_timeout', '5')
    
    # Read system information from verinfo file
    verinfo_content = ""
    verinfo_path = None
    for filename in ['verinfo.md', 'verinfo.txt']:
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], '..', filename)
        if os.path.exists(filepath):
            verinfo_path = filepath
            try:
                with open(filepath, 'r', encoding='utf-8') as f:
                    verinfo_content = f.read()
            except:
                verinfo_content = f"Error reading {filename}"
            break
    
    return render_template('settings_system.html', 
                          currency=currency,
                          max_file_size=max_file_size,
                          allowed_extensions=allowed_extensions,
                          max_drawer_rows=max_drawer_rows,
                          max_drawer_cols=max_drawer_cols,
                          banner_timeout=banner_timeout,
                          verinfo_content=verinfo_content,
                          demo_mode=app.config.get('DEMO_MODE', False))


# ============= FOOTPRINTS =============

@app.route('/footprints')
@login_required
def footprints():
    """Redirect to unified item management page"""
    return redirect(url_for('item_management'))


@app.route('/footprint/new', methods=['GET', 'POST'])
@login_required
@permission_required("settings_sections.item_management", "edit")
def footprint_new():
    from models import Footprint
    from forms import FootprintForm
    form = FootprintForm()
    
    if form.validate_on_submit():
        # Check for duplicate name
        existing = Footprint.query.filter_by(name=form.name.data).first()
        if existing:
            flash(f'Footprint "{form.name.data}" already exists!', 'danger')
            return render_template('footprint_form.html', form=form, title='New Footprint')
        
        footprint = Footprint(
            name=form.name.data,
            description=form.description.data,
            color=form.color.data or '#6c757d'
        )
        db.session.add(footprint)
        db.session.commit()
        log_audit(current_user.id, 'create', 'footprint', footprint.id, f'Created footprint: {footprint.name}')
        flash(f'Footprint "{footprint.name}" created successfully!', 'success')
        return redirect(url_for('item_management'))
    return render_template('footprint_form.html', form=form, title='New Footprint')

@app.route('/footprint/<int:id>/edit', methods=['GET', 'POST'])
@login_required
@permission_required("settings_sections.item_management", "edit")
def footprint_edit(id):
    from models import Footprint
    from forms import FootprintForm
    footprint = Footprint.query.get_or_404(id)
    form = FootprintForm(obj=footprint)
    
    if form.validate_on_submit():
        footprint.name = form.name.data
        footprint.description = form.description.data
        footprint.color = form.color.data or '#6c757d'
        db.session.commit()
        log_audit(current_user.id, 'update', 'footprint', footprint.id, f'Updated footprint: {footprint.name}')
        flash(f'Footprint "{footprint.name}" updated successfully!', 'success')
        return redirect(url_for('item_management'))
    return render_template('footprint_form.html', form=form, footprint=footprint, title='Edit Footprint')

@app.route('/footprint/<int:id>/delete', methods=['POST'])
@login_required
@permission_required("settings_sections.item_management", "delete")
def footprint_delete(id):
    from models import Footprint
    footprint = Footprint.query.get_or_404(id)
    name = footprint.name
    db.session.delete(footprint)
    db.session.commit()
    flash(f'Footprint "{name}" deleted!', 'success')
    return redirect(url_for('item_management'))

# ============= TAGS =============

@app.route('/tags')
@login_required
def tags():
    """Redirect to unified item management page"""
    return redirect(url_for('item_management'))


@app.route('/tag/new', methods=['GET', 'POST'])
@login_required
@permission_required("settings_sections.item_management", "edit")
def tag_new():
    from models import Tag
    from forms import TagForm
    form = TagForm()
    
    if form.validate_on_submit():
        # Check for duplicate name
        existing = Tag.query.filter_by(name=form.name.data).first()
        if existing:
            flash(f'Tag "{form.name.data}" already exists!', 'danger')
            return render_template('tag_form.html', form=form, title='New Tag')
        
        tag = Tag(
            name=form.name.data,
            description=form.description.data,
            color=form.color.data or '#6c757d'
        )
        db.session.add(tag)
        db.session.commit()
        log_audit(current_user.id, 'create', 'tag', tag.id, f'Created tag: {tag.name}')
        flash(f'Tag "{tag.name}" created successfully!', 'success')
        return redirect(url_for('item_management'))
    return render_template('tag_form.html', form=form, title='New Tag')

@app.route('/tag/<int:id>/edit', methods=['GET', 'POST'])
@login_required
@permission_required("settings_sections.item_management", "edit")
def tag_edit(id):
    from models import Tag
    from forms import TagForm
    tag = Tag.query.get_or_404(id)
    form = TagForm(obj=tag)
    
    if form.validate_on_submit():
        tag.name = form.name.data
        tag.description = form.description.data
        tag.color = form.color.data or '#6c757d'
        db.session.commit()
        log_audit(current_user.id, 'update', 'tag', tag.id, f'Updated tag: {tag.name}')
        flash(f'Tag "{tag.name}" updated successfully!', 'success')
        return redirect(url_for('item_management'))
    return render_template('tag_form.html', form=form, tag=tag, title='Edit Tag')

@app.route('/tag/<int:id>/delete', methods=['POST'])
@login_required
@permission_required("settings_sections.item_management", "delete")
def tag_delete(id):
    from models import Tag
    tag = Tag.query.get_or_404(id)
    name = tag.name
    db.session.delete(tag)
    db.session.commit()
    flash(f'Tag "{name}" deleted!', 'success')
    return redirect(url_for('item_management'))

# ============= BACKUP =============

@app.route('/backup-restore')
@login_required
def backup_restore():
    # Check permission for backup/restore
    if not current_user.has_permission('settings_sections.backup_restore', 'view'):
        flash('You do not have permission to view backups.', 'danger')
        return redirect(url_for('settings'))
    
    can_upload_export = current_user.has_permission('settings_sections.backup_restore', 'upload_export')
    can_delete = current_user.has_permission('settings_sections.backup_restore', 'delete')
    
    return render_template('backup_restore.html',
                          can_upload_export=can_upload_export,
                          can_delete=can_delete)

@app.route('/backup/download')
@login_required
@permission_required("settings_sections.backup_restore", "upload_export")
def backup_download():
    import shutil
    import os
    db_path = app.config.get('SQLALCHEMY_DATABASE_URI', 'sqlite:///inventory.db').replace('sqlite:///', '')
    if not os.path.exists(db_path):
        flash('Database file not found', 'danger')
        return redirect(url_for('backup_restore'))
    backup_path = 'inventory_backup.db'
    shutil.copy(db_path, backup_path)
    return send_from_directory('.', 'inventory_backup.db', as_attachment=True)

@app.route('/backup/restore', methods=['POST'])
@login_required
@permission_required("settings_sections.backup_restore", "upload_export")
def backup_restore_upload():
    import shutil
    import os
    if 'backup' not in request.files:
        flash('No file uploaded', 'danger')
        return redirect(url_for('backup_restore'))
    
    file = request.files['backup']
    if file.filename.endswith('.db'):
        db_path = app.config.get('SQLALCHEMY_DATABASE_URI', 'sqlite:///inventory.db').replace('sqlite:///', '')
        backup_old_path = 'inventory_backup_old.db'
        shutil.copy(db_path, backup_old_path)
        file.save(db_path)
        flash('Database restored! Please restart the app.', 'success')
    else:
        flash('Invalid file type', 'danger')
    
    return redirect(url_for('backup_restore'))

@app.route('/backup/export-selective', methods=['POST'])
@login_required
@permission_required("settings_sections.backup_restore", "upload_export")
def export_selective():
    """Export selected data types"""
    from importexport import DataExporter
    
    try:
        # Handle Magic Parameters granular options
        mp_selection = None
        if request.form.get('magic_parameters') == 'on':
            mp_selection = {
                'parameters': request.form.get('mp_parameters') == 'on',
                'templates': request.form.get('mp_templates') == 'on',
                'units': request.form.get('mp_units') == 'on',
                'options': request.form.get('mp_options') == 'on'
            }
        
        selections = {
            'magic_parameters': mp_selection,
            'locations': request.form.get('locations') == 'on',
            'racks': request.form.get('racks') == 'on',
            'categories': request.form.get('categories') == 'on',
            'footprints': request.form.get('footprints') == 'on',
            'tags': request.form.get('tags') == 'on'
        }
        
        # Check if at least one selection is made
        if not any([selections['magic_parameters'], selections['locations'], selections['racks'], 
                   selections['categories'], selections['footprints'], selections['tags']]):
            flash('Please select at least one data type to export', 'warning')
            return redirect(url_for('backup_restore'))
        
        include_item_values = request.form.get('include_item_values') == 'on'
        
        export_data = DataExporter.export_selective(selections, include_item_values)
        
        # Send as file download
        response = app.make_response(json.dumps(export_data, indent=2))
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        response.headers['Content-Disposition'] = f'attachment; filename=config_export_{timestamp}.json'
        response.headers['Content-Type'] = 'application/json'
        return response
    except Exception as e:
        logging.error(f"Export error: {str(e)}")
        flash('An error occurred during export. Please try again.', 'danger')
        return redirect(url_for('backup_restore'))


@app.route('/backup/import-selective', methods=['POST'])
@login_required
@permission_required("settings_sections.backup_restore", "upload_export")
def import_selective():
    """Import selected data types"""
    from importexport import DataImporter
    
    try:
        if 'config' not in request.files:
            flash('No file uploaded', 'danger')
            return redirect(url_for('backup_restore'))
        
        file = request.files['config']
        if not file or file.filename == '':
            flash('No file selected', 'danger')
            return redirect(url_for('backup_restore'))
        
        # Load JSON
        try:
            config_data = json.load(file.stream)
        except Exception as e:
            flash(f'Invalid JSON file: {str(e)}', 'danger')
            return redirect(url_for('backup_restore'))
        
        # Handle Magic Parameters granular options
        mp_selection = None
        if request.form.get('magic_parameters') == 'on':
            mp_selection = {
                'parameters': request.form.get('mp_parameters') == 'on',
                'templates': request.form.get('mp_templates') == 'on',
                'units': request.form.get('mp_units') == 'on',
                'options': request.form.get('mp_options') == 'on'
            }
        
        # Get selections from form
        selections = {
            'magic_parameters': mp_selection,
            'locations': request.form.get('locations') == 'on',
            'racks': request.form.get('racks') == 'on',
            'categories': request.form.get('categories') == 'on',
            'footprints': request.form.get('footprints') == 'on',
            'tags': request.form.get('tags') == 'on'
        }
        
        if not any([selections['magic_parameters'], selections['locations'], selections['racks'], 
                   selections['categories'], selections['footprints'], selections['tags']]):
            flash('Please select at least one data type to import', 'warning')
            return redirect(url_for('backup_restore'))
        
        # Import data
        importer = DataImporter()
        results = importer.import_selective(config_data, selections)
        
        # Show results
        msg = f'✓ Import complete! Imported: {results["imported"]}, Skipped: {results["skipped"]}'
        if results['errors']:
            msg += f', {len(results["errors"])} error(s)'
        flash(msg, 'success')
        
        # Show details by type
        for data_type, details in results['details'].items():
            if details.get('imported', 0) > 0 or details.get('skipped', 0) > 0:
                detail_msg = f"{data_type.replace('_', ' ').title()}: {details.get('imported', 0)} imported, {details.get('skipped', 0)} skipped"
                if 'item_parameters' in details:
                    detail_msg += f" | Item Parameters: {details['item_parameters'].get('imported', 0)} imported, {details['item_parameters'].get('skipped', 0)} skipped"
                flash(detail_msg, 'info')
        
        # Show first 3 errors
        for err in results['errors'][:3]:
            flash(f'⚠️ {err}', 'warning')
        if len(results['errors']) > 3:
            flash(f'⚠️ +{len(results["errors"])-3} more errors', 'warning')
        
        return redirect(url_for('backup_restore'))

    except Exception as e:
        db.session.rollback()
        logging.error(f"Import fatal error: {str(e)}")
        flash('A fatal error occurred during import. Please check the file and try again.', 'danger')
        return redirect(url_for('backup_restore'))

# ============= MAGIC PARAMETERS =============

@app.route('/settings/magic-parameters')
@login_required
def magic_parameters():
    """Magic Parameters settings page"""
    from models import MagicParameter, ParameterTemplate
    
    # Check view permission for magic parameter settings
    if not current_user.has_permission('settings_sections.magic_parameters', 'view'):
        flash('You do not have permission to view magic parameters.', 'danger')
        return redirect(url_for('settings'))
    
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


@app.route('/magic-parameter/new', methods=['POST'])
@login_required
@permission_required("settings_sections.magic_parameters", "edit")
def magic_parameter_new():
    from models import MagicParameter, ParameterUnit, ParameterStringOption
    
    # Get form data directly from request
    name = request.form.get('name', '').strip()
    param_type = request.form.get('param_type', '').strip()
    description = request.form.get('description', '').strip()
    unit = request.form.get('unit', '').strip()
    string_option = request.form.get('string_option', '').strip()
    notify_enabled = 'notify_enabled' in request.form
    
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
            notify_enabled=notify_enabled if param_type == 'date' else False
        )
        db.session.add(parameter)
        db.session.flush()
        
        # Add initial unit for number type
        if param_type == 'number' and unit:
            unit_obj = ParameterUnit(parameter_id=parameter.id, unit=unit)
            db.session.add(unit_obj)
        
        # Add initial option for string type
        if param_type == 'string' and string_option:
            option_obj = ParameterStringOption(parameter_id=parameter.id, value=string_option)
            db.session.add(option_obj)
        
        db.session.commit()
        
        log_audit(current_user.id, 'create', 'magic_parameter', parameter.id, f'Created parameter: {name}')
        
        return jsonify({
            'success': True,
            'parameter_id': parameter.id,
            'redirect_url': url_for('magic_parameter_manage', id=parameter.id)
        })

    except Exception as e:
        db.session.rollback()
        logging.error(f"Error creating parameter: {str(e)}")
        return jsonify({
            'success': False,
            'errors': ['An error occurred while creating the parameter']
        }), 500


@app.route('/magic-parameter/<int:id>/edit', methods=['POST'])
@login_required
@permission_required("settings_sections.magic_parameters", "edit")
def magic_parameter_edit(id):
    from models import MagicParameter, ParameterUnit, ParameterStringOption
    parameter = MagicParameter.query.get_or_404(id)
    
    parameter.name = request.form.get('name', '').strip()
    parameter.description = request.form.get('description', '').strip()
    if parameter.param_type == 'date':
        parameter.notify_enabled = 'notify_enabled' in request.form
    
    db.session.commit()
    
    log_audit(current_user.id, 'update', 'magic_parameter', parameter.id, f'Updated parameter: {parameter.name}')
    flash(f'Magic Parameter "{parameter.name}" updated successfully!', 'success')
    return redirect(url_for('magic_parameter_manage', id=parameter.id))


@app.route('/magic-parameter/<int:id>/manage')
@login_required
@permission_required("settings_sections.magic_parameters", "edit")
def magic_parameter_manage(id):
    from models import MagicParameter
    parameter = MagicParameter.query.get_or_404(id)
    return render_template('magic_parameter_manage.html', parameter=parameter)


@app.route('/magic-parameter/<int:id>/add-unit', methods=['POST'])
@login_required
@permission_required("settings_sections.magic_parameters", "edit")
def magic_parameter_add_unit(id):
    from models import MagicParameter, ParameterUnit
    parameter = MagicParameter.query.get_or_404(id)
    
    if parameter.param_type != 'number':
        flash('Units can only be added to Number type parameters!', 'danger')
        return redirect(url_for('magic_parameter_manage', id=id))
    
    unit = request.form.get('unit', '').strip()
    if not unit:
        flash('Unit cannot be empty!', 'danger')
        return redirect(url_for('magic_parameter_manage', id=id))
    
    # Check for duplicate
    existing = ParameterUnit.query.filter_by(parameter_id=id, unit=unit).first()
    if existing:
        flash(f'Unit "{unit}" already exists for this parameter!', 'danger')
        return redirect(url_for('magic_parameter_manage', id=id))
    
    new_unit = ParameterUnit(parameter_id=id, unit=unit)
    db.session.add(new_unit)
    db.session.commit()
    
    flash(f'Unit "{unit}" added successfully!', 'success')
    return redirect(url_for('magic_parameter_manage', id=id))


@app.route('/magic-parameter/<int:id>/delete-unit/<int:unit_id>', methods=['POST'])
@login_required
@permission_required("settings_sections.magic_parameters", "edit")
def magic_parameter_delete_unit(id, unit_id):
    from models import ParameterUnit, ItemParameter
    unit = ParameterUnit.query.get_or_404(unit_id)
    
    if unit.parameter_id != id:
        flash('Invalid unit!', 'danger')
        return redirect(url_for('magic_parameter_manage', id=id))
    
    # Check if any items use this unit
    items_using = ItemParameter.query.filter_by(parameter_id=id, unit=unit.unit).count()
    if items_using > 0:
        flash(f'Cannot delete unit "{unit.unit}" - it is used by {items_using} item(s)!', 'danger')
        return redirect(url_for('magic_parameter_manage', id=id))
    
    db.session.delete(unit)
    db.session.commit()
    
    flash(f'Unit "{unit.unit}" deleted successfully!', 'success')
    return redirect(url_for('magic_parameter_manage', id=id))


@app.route('/magic-parameter/<int:id>/add-option', methods=['POST'])
@login_required
@permission_required("settings_sections.magic_parameters", "edit")
def magic_parameter_add_option(id):
    from models import MagicParameter, ParameterStringOption
    parameter = MagicParameter.query.get_or_404(id)
    
    if parameter.param_type != 'string':
        flash('Options can only be added to String type parameters!', 'danger')
        return redirect(url_for('magic_parameter_manage', id=id))
    
    option = request.form.get('option', '').strip()
    if not option:
        flash('Option cannot be empty!', 'danger')
        return redirect(url_for('magic_parameter_manage', id=id))
    
    # Check for duplicate
    existing = ParameterStringOption.query.filter_by(parameter_id=id, value=option).first()
    if existing:
        flash(f'Option "{option}" already exists for this parameter!', 'danger')
        return redirect(url_for('magic_parameter_manage', id=id))
    
    new_option = ParameterStringOption(parameter_id=id, value=option)
    db.session.add(new_option)
    db.session.commit()
    
    flash(f'Option "{option}" added successfully!', 'success')
    return redirect(url_for('magic_parameter_manage', id=id))


@app.route('/magic-parameter/<int:id>/delete-option/<int:option_id>', methods=['POST'])
@login_required
@permission_required("settings_sections.magic_parameters", "edit")
def magic_parameter_delete_option(id, option_id):
    from models import ParameterStringOption, ItemParameter
    option = ParameterStringOption.query.get_or_404(option_id)
    
    if option.parameter_id != id:
        flash('Invalid option!', 'danger')
        return redirect(url_for('magic_parameter_manage', id=id))
    
    # Check if any items use this option
    items_using = ItemParameter.query.filter_by(parameter_id=id, string_option=option.value).count()
    if items_using > 0:
        flash(f'Cannot delete option "{option.value}" - it is used by {items_using} item(s)!', 'danger')
        return redirect(url_for('magic_parameter_manage', id=id))
    
    db.session.delete(option)
    db.session.commit()
    
    flash(f'Option "{option.value}" deleted successfully!', 'success')
    return redirect(url_for('magic_parameter_manage', id=id))


@app.route('/magic-parameter/<int:id>/delete', methods=['POST'])
@login_required
@permission_required("settings_sections.magic_parameters", "delete")
def magic_parameter_delete(id):
    from models import MagicParameter
    parameter = MagicParameter.query.get_or_404(id)
    parameter_name = parameter.name
    
    if parameter.item_parameters:
        flash(f'Cannot delete parameter "{parameter_name}" because it is used by {len(parameter.item_parameters)} item(s).', 'danger')
        return redirect(url_for('item_management'))
    
    db.session.delete(parameter)
    db.session.commit()
    
    log_audit(current_user.id, 'delete', 'magic_parameter', id, f'Deleted parameter: {parameter_name}')
    flash(f'Magic Parameter "{parameter_name}" deleted successfully!', 'success')
    return redirect(url_for('magic_parameters'))


@app.route('/api/magic-parameters/<type>')
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
        elif type == 'string':
            data['options'] = param.get_string_options_list()
        
        result.append(data)
    
    return jsonify(result)


# ============= PARAMETER TEMPLATES =============

@app.route('/parameter-template/new', methods=['GET', 'POST'])
@login_required
@permission_required("settings_sections.magic_parameters", "edit")
def parameter_template_new():
    from models import ParameterTemplate
    
    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        description = request.form.get('description', '').strip()
        
        if not name:
            flash('Template name is required!', 'danger')
            return redirect(url_for('magic_parameters'))
        
        # Check for duplicate name
        existing = ParameterTemplate.query.filter_by(name=name).first()
        if existing:
            flash(f'Template "{name}" already exists!', 'danger')
            return redirect(url_for('magic_parameters'))
        
        template = ParameterTemplate(
            name=name,
            description=description
        )
        db.session.add(template)
        db.session.commit()
        
        log_audit(current_user.id, 'create', 'parameter_template', template.id, f'Created template: {template.name}')
        flash(f'Parameter Template "{template.name}" created successfully!', 'success')
        return redirect(url_for('parameter_template_manage', id=template.id))
    
    return render_template('parameter_template_form.html', title='New Parameter Template')


@app.route('/parameter-template/<int:id>/manage')
@login_required
@permission_required("settings_sections.magic_parameters", "edit")
def parameter_template_manage(id):
    from models import ParameterTemplate
    template = ParameterTemplate.query.get_or_404(id)
    return render_template('parameter_template_manage.html', template=template)


@app.route('/parameter-template/<int:id>/edit', methods=['GET', 'POST'])
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
        return redirect(url_for('parameter_template_manage', id=template.id))
    
    return render_template('parameter_template_form.html', template=template, title='Edit Parameter Template')


@app.route('/parameter-template/<int:id>/add-parameter', methods=['POST'])
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
        return redirect(url_for('parameter_template_manage', id=id))
    
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
    return redirect(url_for('parameter_template_manage', id=id))


@app.route('/parameter-template/<int:template_id>/delete-parameter/<int:param_id>', methods=['POST'])
@login_required
@permission_required("settings_sections.magic_parameters", "edit")
def template_delete_parameter(template_id, param_id):
    from models import TemplateParameter
    template_param = TemplateParameter.query.get_or_404(param_id)
    
    if template_param.template_id != template_id:
        flash('Invalid parameter!', 'danger')
        return redirect(url_for('parameter_template_manage', id=template_id))
    
    db.session.delete(template_param)
    db.session.commit()
    
    flash('Parameter removed from template successfully!', 'success')
    return redirect(url_for('parameter_template_manage', id=template_id))


@app.route('/parameter-template/<int:id>/delete', methods=['POST'])
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
    return redirect(url_for('magic_parameters'))


@app.route('/api/parameter-templates')
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


@app.route('/item/<int:id>/populate-template', methods=['POST'])
@login_required
@item_permission_required
def item_populate_template(id):
    from models import ItemParameter, ParameterTemplate
    item = Item.query.get_or_404(id)
    
    # SECURITY CHECK: Verify user has parameter edit permission
    if not current_user.has_permission('items', 'edit_parameters'):
        flash('❌ You do not have permission to apply templates.', 'danger')
        log_audit(current_user.id, 'denied', 'item_template_apply', id, f'Unauthorized template apply attempt to item: {item.name}')
        return redirect(url_for('item_edit', uuid=item.uuid))
    
    template_id = int(request.form.get('template_id', 0))
    
    template = ParameterTemplate.query.get(template_id)
    if not template:
        flash('Invalid template selected!', 'danger')
        return redirect(url_for('item_edit', uuid=item.uuid))
    
    # Add all template parameters to the item
    added_count = 0
    for tp in template.template_parameters:
        item_param = ItemParameter(
            item_id=id,
            parameter_id=tp.parameter_id,
            operation=tp.operation,
            value=tp.value,
            value2=tp.value2,
            unit=tp.unit,
            string_option=tp.string_option,
            description=tp.description
        )
        db.session.add(item_param)
        added_count += 1
    
    db.session.commit()
    
    log_audit(current_user.id, 'update', 'item', id, f'Applied template "{template.name}" to item: {item.name}')
    flash(f'Added {added_count} parameters from template "{template.name}"!', 'success')
    return redirect(url_for('item_edit', uuid=item.uuid))


@app.route('/item/<int:id>/add-parameter', methods=['POST'])
@login_required
@item_permission_required
def item_add_parameter(id):
    from models import ItemParameter, MagicParameter
    item = Item.query.get_or_404(id)
    
    # SECURITY CHECK: Verify user has parameter edit permission
    if not current_user.has_permission('items', 'edit_parameters'):
        flash('❌ You do not have permission to add parameters.', 'danger')
        log_audit(current_user.id, 'denied', 'item_parameter_add', id, f'Unauthorized parameter add attempt to item: {item.name}')
        return redirect(url_for('item_edit', uuid=item.uuid))
    
    # Get form data
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
        return redirect(url_for('item_edit', uuid=item.uuid))
    
    # Create new item parameter
    item_param = ItemParameter(
        item_id=id,
        parameter_id=parameter_id,
        operation=operation if param_type in ['number', 'date'] else None,
        value=value if param_type in ['number', 'date'] else None,
        value2=value2 if operation in ['range', 'duration'] else None,
        unit=unit if param_type == 'number' else None,
        string_option=string_option if param_type == 'string' else None,
        description=description
    )
    
    db.session.add(item_param)
    db.session.commit()
    
    log_audit(current_user.id, 'update', 'item', id, f'Added parameter to item: {item.name}')
    flash('Parameter added successfully!', 'success')
    return redirect(url_for('item_edit', uuid=item.uuid))


@app.route('/item/<int:item_id>/delete-parameter/<int:param_id>', methods=['POST'])
@login_required
@item_permission_required
def item_delete_parameter(item_id, param_id):
    from models import ItemParameter
    item = Item.query.get_or_404(item_id)
    item_param = ItemParameter.query.get_or_404(param_id)
    
    # SECURITY CHECK: Verify user has parameter edit permission
    if not current_user.has_permission('items', 'edit_parameters'):
        flash('❌ You do not have permission to delete parameters.', 'danger')
        log_audit(current_user.id, 'denied', 'item_parameter_delete', item_id, f'Unauthorized parameter delete attempt to item: {item.name}')
        return redirect(url_for('item_edit', uuid=item.uuid))
    
    if item_param.item_id != item_id:
        flash('Invalid parameter!', 'danger')
        return redirect(url_for('item_edit', uuid=item.uuid))
    
    db.session.delete(item_param)
    db.session.commit()
    
    log_audit(current_user.id, 'update', 'item', item_id, f'Removed parameter from item: {item.name}')
    flash('Parameter removed successfully!', 'success')
    return redirect(url_for('item_edit', uuid=item.uuid))


@app.route('/item/<int:item_id>/edit-parameter/<int:param_id>', methods=['GET', 'POST'])
@login_required
@item_permission_required
def item_edit_parameter(item_id, param_id):
    from models import ItemParameter, MagicParameter
    item = Item.query.get_or_404(item_id)
    item_param = ItemParameter.query.get_or_404(param_id)
    
    if item_param.item_id != item_id:
        flash('Invalid parameter!', 'danger')
        return redirect(url_for('item_edit', uuid=item.uuid))
    
    if request.method == 'POST':
        # Update parameter values
        item_param.operation = request.form.get('operation')
        item_param.value = request.form.get('value', '').strip()
        item_param.value2 = request.form.get('value2', '').strip() if request.form.get('operation') in ['range', 'duration'] else None
        item_param.unit = request.form.get('unit', '').strip()
        item_param.string_option = request.form.get('string_option', '').strip()
        item_param.description = request.form.get('description', '').strip()
        
        db.session.commit()
        
        log_audit(current_user.id, 'update', 'item', item_id, f'Updated parameter for item: {item.name}')
        flash('Parameter updated successfully!', 'success')
        return redirect(url_for('item_edit', uuid=item.uuid))
    
    return render_template('item_parameter_edit.html', item=item, item_param=item_param)


@app.route('/notifications')
@login_required
def notifications():
    """Show items with date parameter notifications due"""
    from models import ItemParameter
    from datetime import datetime
    
    # Check view permission
    if not current_user.has_permission('pages.notifications', 'view'):
        flash('You do not have permission to view notifications.', 'danger')
        return redirect(url_for('index'))
    
    # Check if user can edit notifications
    can_edit = current_user.has_permission('pages.notifications', 'edit')
    
    # Get all item parameters with notifications enabled
    notifications = []
    params = ItemParameter.query.join(ItemParameter.parameter).filter(
        ItemParameter.parameter.has(param_type='date'),
        ItemParameter.parameter.has(notify_enabled=True)
    ).all()
    
    today = datetime.now().date()
    
    for param in params:
        try:
            if param.operation in ['value', 'start', 'end'] and param.value:
                param_date = datetime.strptime(param.value, '%Y-%m-%d').date()
                if param_date == today:
                    notifications.append({
                        'item': param.item,
                        'parameter': param,
                        'message': f"{param.parameter.name} is due today",
                        'type': 'due'
                    })
                elif param_date < today:
                    notifications.append({
                        'item': param.item,
                        'parameter': param,
                        'message': f"{param.parameter.name} is overdue",
                        'type': 'overdue'
                    })
            elif param.operation == 'duration' and param.value and param.value2:
                start_date = datetime.strptime(param.value, '%Y-%m-%d').date()
                end_date = datetime.strptime(param.value2, '%Y-%m-%d').date()
                if start_date <= today <= end_date:
                    notifications.append({
                        'item': param.item,
                        'parameter': param,
                        'message': f"{param.parameter.name} is active",
                        'type': 'active'
                    })
        except:
            pass
    
    return render_template('notifications.html', notifications=notifications, can_edit_notifications=can_edit)


# ============= USER PROFILE PICTURES =============

@app.route('/uploads/userpicture/<filename>')
def serve_user_picture(filename):
    """Serve user profile pictures"""
    return send_from_directory(os.path.join(app.config['UPLOAD_FOLDER'], 'userpicture'), filename)


# ============= ERROR HANDLERS =============

@app.errorhandler(404)
def not_found_error(error):
    return render_template('404.html'), 404

@app.errorhandler(500)
def internal_error(error):
    db.session.rollback()
    return render_template('500.html'), 500

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
