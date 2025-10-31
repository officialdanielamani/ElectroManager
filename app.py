from flask import Flask, render_template, redirect, url_for, flash, request, send_from_directory, abort, jsonify
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash
from config import Config
from models import db, User, Category, Item, Attachment, Rack, Footprint, Tag, Setting, Location
from forms import LoginForm, RegistrationForm, CategoryForm, ItemForm, AttachmentForm, SearchForm, UserForm, MagicParameterForm, ParameterUnitForm, ParameterStringOptionForm, ItemParameterForm
from utils import save_file, log_audit, admin_required, editor_required, format_file_size, allowed_file
import os
import json
from datetime import datetime, timezone

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

@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, int(user_id))

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
    
    form = LoginForm()
    if form.validate_on_submit():
        user = User.query.filter_by(username=form.username.data).first()
        if user and user.check_password(form.password.data) and user.is_active:
            login_user(user, remember=form.remember_me.data)
            log_audit(user.id, 'login', 'user', user.id, 'User logged in')
            next_page = request.args.get('next')
            return redirect(next_page or url_for('index'))
        else:
            flash('Invalid username or password, or account is inactive.', 'danger')
    
    return render_template('login.html', form=form, signup_enabled=signup_enabled)

@app.route('/logout')
@login_required
def logout():
    log_audit(current_user.id, 'logout', 'user', current_user.id, 'User logged out')
    logout_user()
    flash('You have been logged out.', 'info')
    return redirect(url_for('login'))

@app.route('/register', methods=['GET', 'POST'])
def register():
    from models import Setting
    signup_enabled = Setting.get('signup_enabled', True)
    
    if not signup_enabled:
        flash('User registration is currently disabled.', 'warning')
        return redirect(url_for('login'))
    
    if current_user.is_authenticated:
        return redirect(url_for('index'))
    
    form = RegistrationForm()
    if form.validate_on_submit():
        user = User(
            username=form.username.data,
            email=form.email.data,
            role='viewer'
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
        notification_count=notification_count
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

@app.route('/item/new', methods=['GET', 'POST'])
@login_required
@editor_required
def item_new():
    from models import Tag
    import json
    
    form = ItemForm()
    racks = Rack.query.order_by(Rack.name).all()
    racks_data = [{'id': r.id, 'name': r.name, 'rows': r.rows, 'cols': r.cols, 
                   'unavailable_drawers': r.get_unavailable_drawers()} for r in racks]
    all_tags = [{'id': t.id, 'name': t.name, 'color': t.color} for t in Tag.query.order_by(Tag.name).all()]
    
    prefill_rack_id = request.args.get('rack_id', type=int)
    prefill_drawer = request.args.get('drawer')
    
    if form.validate_on_submit():
        location_id = form.location_id.data if form.location_id.data else None
        rack_id = request.form.get('rack_id')
        drawer = request.form.get('drawer')
        
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
        
        # Get selected tags
        selected_tags = request.form.getlist('tags[]')
        tags_json = json.dumps([int(t) for t in selected_tags if t])
        
        item = Item(
            name=form.name.data,
            sku=form.sku.data if form.sku.data else None,
            info=form.info.data,
            description=form.description.data,
            quantity=form.quantity.data,
            price=form.price.data or 0.0,
            location_id=location_id_value,
            rack_id=rack_id_value,
            drawer=drawer_value,
            min_quantity=form.min_quantity.data or 0,
            category_id=form.category_id.data if form.category_id.data > 0 else None,
            footprint_id=form.footprint_id.data if form.footprint_id.data > 0 else None,
            tags=tags_json,
            lend_to=form.lend_to.data,
            lend_quantity=form.lend_quantity.data or 0,
            datasheet_urls=form.datasheet_urls.data,
            created_by=current_user.id,
            updated_by=current_user.id
        )
        db.session.add(item)
        db.session.commit()
        
        log_audit(current_user.id, 'create', 'item', item.id, f'Created item: {item.name}')
        flash(f'Item "{item.name}" created successfully!', 'success')
        return redirect(url_for('item_detail', uuid=item.uuid))
    
    return render_template('item_form.html', form=form, racks=racks, racks_data=racks_data, all_tags=all_tags, title='New Item',
                         prefill_rack_id=prefill_rack_id, prefill_drawer=prefill_drawer, 
                         currency=Setting.get('currency', '$'))

@app.route('/item/<string:uuid>')
@login_required
def item_detail(uuid):
    item = Item.query.filter_by(uuid=uuid).first_or_404()
    attachment_form = AttachmentForm()
    currency_symbol = Setting.get('currency', '$')
    return render_template('item_detail.html', item=item, attachment_form=attachment_form, currency_symbol=currency_symbol)

@app.route('/item/<string:uuid>/edit', methods=['GET', 'POST'])
@login_required
@editor_required
def item_edit(uuid):
    from models import Tag
    import json
    
    item = Item.query.filter_by(uuid=uuid).first_or_404()
    form = ItemForm(obj=item)
    racks = Rack.query.order_by(Rack.name).all()
    racks_data = [{'id': r.id, 'name': r.name, 'rows': r.rows, 'cols': r.cols, 
                   'unavailable_drawers': r.get_unavailable_drawers()} for r in racks]
    all_tags = [{'id': t.id, 'name': t.name, 'color': t.color} for t in Tag.query.order_by(Tag.name).all()]
    
    if form.validate_on_submit():
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
        
        # Get selected tags
        selected_tags = request.form.getlist('tags[]')
        tags_json = json.dumps([int(t) for t in selected_tags if t])
        
        item.name = form.name.data
        item.sku = form.sku.data if form.sku.data else None
        item.info = form.info.data
        item.description = form.description.data
        item.quantity = form.quantity.data
        item.price = form.price.data
        item.min_quantity = form.min_quantity.data
        item.category_id = form.category_id.data if form.category_id.data > 0 else None
        item.footprint_id = form.footprint_id.data if form.footprint_id.data > 0 else None
        item.tags = tags_json
        item.lend_to = form.lend_to.data
        item.lend_quantity = form.lend_quantity.data or 0
        item.datasheet_urls = form.datasheet_urls.data
        item.updated_at = datetime.now(timezone.utc)
        item.updated_by = current_user.id
        
        db.session.commit()
        
        log_audit(current_user.id, 'update', 'item', item.id, f'Updated item: {item.name}')
        flash(f'Item "{item.name}" updated successfully!', 'success')
        return redirect(url_for('item_detail', uuid=item.uuid))
    
    # Get file upload settings
    max_size_mb = int(Setting.get('max_file_size_mb', '10'))
    extensions_str = Setting.get('allowed_extensions', 'pdf,png,jpg,jpeg,gif,txt,doc,docx')
    
    return render_template('item_form.html', form=form, item=item, racks=racks, racks_data=racks_data, all_tags=all_tags, title='Edit Item', currency=Setting.get('currency', '$'), max_file_size_mb=max_size_mb, allowed_file_types=extensions_str)

@app.route('/item/<string:uuid>/delete', methods=['POST'])
@login_required
@editor_required
def item_delete(uuid):
    item = Item.query.filter_by(uuid=uuid).first_or_404()
    item_name = item.name
    
    for attachment in item.attachments:
        try:
            if os.path.exists(attachment.file_path):
                os.remove(attachment.file_path)
        except Exception as e:
            print(f"Error deleting file: {e}")
    
    db.session.delete(item)
    db.session.commit()
    
    log_audit(current_user.id, 'delete', 'item', item.id, f'Deleted item: {item_name}')
    flash(f'Item "{item_name}" deleted successfully!', 'success')
    return redirect(url_for('index'))

# ============= ATTACHMENT ROUTES =============

@app.route('/item/<int:item_id>/upload', methods=['POST'])
@login_required
@editor_required
def upload_attachment(item_id):
    item = Item.query.get_or_404(item_id)
    form = AttachmentForm()
    
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
@editor_required
def delete_attachment(id):
    attachment = Attachment.query.get_or_404(id)
    item = attachment.item
    
    try:
        if os.path.exists(attachment.file_path):
            os.remove(attachment.file_path)
    except Exception as e:
        print(f"Error deleting file: {e}")
    
    db.session.delete(attachment)
    db.session.commit()
    
    log_audit(current_user.id, 'delete', 'attachment', id, f'Deleted attachment: {attachment.original_filename}')
    flash('Attachment deleted successfully!', 'success')
    return redirect(url_for('item_edit', uuid=item.uuid))

@app.route('/attachment/<int:attachment_id>/rename', methods=['POST'])
@login_required
@editor_required
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
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/item/<int:item_id>/datasheets', methods=['POST'])
@login_required
@editor_required
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
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/uploads/<path:filename>')
@login_required
def uploaded_file(filename):
    """Serve uploaded files from uploads folder"""
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)

# ============= CATEGORY ROUTES =============

@app.route('/manage')
@login_required
def item_management():
    """Combined management page for categories, footprints, and tags"""
    categories = Category.query.order_by(Category.name).all()
    footprints = Footprint.query.order_by(Footprint.name).all()
    tags = Tag.query.order_by(Tag.name).all()
    return render_template('item_management.html', 
                          categories=categories, 
                          footprints=footprints, 
                          tags=tags)

@app.route('/categories')
@login_required
def categories():
    """Redirect to unified item management page"""
    return redirect(url_for('item_management'))


@app.route('/category/new', methods=['GET', 'POST'])
@login_required
@editor_required
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
            description=form.description.data
        )
        db.session.add(category)
        db.session.commit()
        
        log_audit(current_user.id, 'create', 'category', category.id, f'Created category: {category.name}')
        flash(f'Category "{category.name}" created successfully!', 'success')
        return redirect(url_for('item_management'))
    
    return render_template('category_form.html', form=form, title='New Category')

@app.route('/category/<int:id>/edit', methods=['GET', 'POST'])
@login_required
@editor_required
def category_edit(id):
    category = Category.query.get_or_404(id)
    form = CategoryForm(obj=category)
    
    if form.validate_on_submit():
        category.name = form.name.data
        category.description = form.description.data
        db.session.commit()
        
        log_audit(current_user.id, 'update', 'category', category.id, f'Updated category: {category.name}')
        flash(f'Category "{category.name}" updated successfully!', 'success')
        return redirect(url_for('item_management'))
    
    return render_template('category_form.html', form=form, category=category, title='Edit Category')

@app.route('/category/<int:id>/delete', methods=['POST'])
@login_required
@admin_required
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
@admin_required
def users():
    from models import Setting
    users = User.query.order_by(User.username).all()
    signup_enabled = Setting.get('signup_enabled', True)
    return render_template('users.html', users=users, signup_enabled=signup_enabled)

@app.route('/toggle-signup', methods=['POST'])
@login_required
@admin_required
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
@admin_required
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
            role=form.role.data,
            is_active=form.is_active.data
        )
        user.set_password(form.password.data)
        db.session.add(user)
        db.session.commit()
        
        log_audit(current_user.id, 'create', 'user', user.id, f'Created user: {user.username}')
        flash(f'User "{user.username}" created successfully!', 'success')
        return redirect(url_for('users'))
    
    return render_template('user_form.html', form=form, title='New User')

@app.route('/user/<int:id>/edit', methods=['GET', 'POST'])
@login_required
@admin_required
def user_edit(id):
    user = User.query.get_or_404(id)
    form = UserForm(obj=user)
    
    if form.validate_on_submit():
        user.username = form.username.data
        user.email = form.email.data
        user.role = form.role.data
        user.is_active = form.is_active.data
        
        if form.password.data:
            user.set_password(form.password.data)
        
        db.session.commit()
        
        log_audit(current_user.id, 'update', 'user', user.id, f'Updated user: {user.username}')
        flash(f'User "{user.username}" updated successfully!', 'success')
        return redirect(url_for('users'))
    
    return render_template('user_form.html', form=form, user=user, title='Edit User')

@app.route('/user/<int:id>/delete', methods=['POST'])
@login_required
@admin_required
def user_delete(id):
    if id == current_user.id:
        flash('You cannot delete your own account.', 'danger')
        return redirect(url_for('users'))
    
    user = User.query.get_or_404(id)
    username = user.username
    
    db.session.delete(user)
    db.session.commit()
    
    log_audit(current_user.id, 'delete', 'user', id, f'Deleted user: {username}')
    flash(f'User "{username}" deleted successfully!', 'success')
    return redirect(url_for('users'))

# ============= REPORTS AND ANALYTICS =============

@app.route('/low-stock')
@login_required
def low_stock():
    items = Item.query.filter(Item.quantity <= Item.min_quantity).order_by(Item.quantity).all()
    return render_template('low_stock.html', items=items)

@app.route('/reports')
@login_required
def reports():
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
    from models import Location
    locations = Location.query.order_by(Location.name).all()
    racks = Rack.query.order_by(Rack.name).all()
    return render_template('location_management.html', 
                          locations=locations,
                          racks=racks)

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
@editor_required
def location_new():
    """Create new location"""
    from models import Location
    from forms import LocationForm
    from werkzeug.utils import secure_filename
    
    form = LocationForm()
    
    if form.validate_on_submit():
        # Check for duplicate name
        existing = Location.query.filter_by(name=form.name.data).first()
        if existing:
            flash(f'Location "{form.name.data}" already exists!', 'danger')
            return render_template('location_form.html', form=form, location=None)
        
        location = Location(
            name=form.name.data,
            info=form.info.data,
            description=form.description.data,
            color=form.color.data or '#6c757d'
        )
        
        # Handle picture upload
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
                return render_template('location_form.html', form=form, location=None)
            
            # Only allow PNG and JPEG
            if file.filename and allowed_file(file.filename):
                ext = file.filename.rsplit('.', 1)[1].lower()
                if ext not in ['png', 'jpg', 'jpeg']:
                    flash('Only PNG and JPEG images are allowed for locations!', 'danger')
                    return render_template('location_form.html', form=form, location=None)
                
                # Sanitize location name for filename
                safe_name = secure_filename(form.name.data)
                if not safe_name:
                    safe_name = "location"
                
                # Use location name as filename
                if ext == 'jpg':
                    ext = 'jpeg'
                filename = f"{safe_name}.{ext}"
                
                # Create locations directory
                location_dir = os.path.join(app.config['UPLOAD_FOLDER'], 'locations')
                os.makedirs(location_dir, exist_ok=True)
                
                filepath = os.path.join(location_dir, filename)
                file.save(filepath)
                location.picture = filename
        
        db.session.add(location)
        db.session.commit()
        
        log_audit(current_user.id, 'create', 'location', location.id, f'Created location: {location.name}')
        flash(f'Location "{location.name}" created successfully!', 'success')
        return redirect(url_for('location_management'))
    
    return render_template('location_form.html', form=form, location=None)

@app.route('/location/<int:id>/edit', methods=['GET', 'POST'])
@login_required
@editor_required
def location_edit(id):
    """Edit location"""
    from models import Location
    from forms import LocationForm
    from werkzeug.utils import secure_filename
    
    location = Location.query.get_or_404(id)
    form = LocationForm(obj=location)
    
    if form.validate_on_submit():
        # Check for duplicate name (exclude current location)
        if form.name.data != location.name:
            existing = Location.query.filter_by(name=form.name.data).first()
            if existing:
                flash(f'Location "{form.name.data}" already exists!', 'danger')
                return render_template('location_form.html', form=form, location=location)
        
        old_name = location.name
        location.name = form.name.data
        location.info = form.info.data
        location.description = form.description.data
        location.color = form.color.data or '#6c757d'
        
        # Handle picture deletion
        if request.form.get('delete_picture'):
            if location.picture:
                old_path = os.path.join(app.config['UPLOAD_FOLDER'], 'locations', location.picture)
                if os.path.exists(old_path):
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
                
                # Delete old picture if name changed
                if location.picture and old_name != location.name:
                    old_path = os.path.join(app.config['UPLOAD_FOLDER'], 'locations', location.picture)
                    if os.path.exists(old_path):
                        os.remove(old_path)
                
                # Sanitize location name for filename
                safe_name = secure_filename(form.name.data)
                if not safe_name:
                    safe_name = "location"
                
                # Use location name as filename
                if ext == 'jpg':
                    ext = 'jpeg'
                filename = f"{safe_name}.{ext}"
                
                location_dir = os.path.join(app.config['UPLOAD_FOLDER'], 'locations')
                os.makedirs(location_dir, exist_ok=True)
                
                filepath = os.path.join(location_dir, filename)
                file.save(filepath)
                location.picture = filename
        elif old_name != location.name and location.picture:
            # Rename existing picture file if location name changed
            old_filename = location.picture
            old_path = os.path.join(app.config['UPLOAD_FOLDER'], 'locations', old_filename)
            
            if os.path.exists(old_path):
                ext = old_filename.rsplit('.', 1)[1].lower()
                safe_name = secure_filename(form.name.data)
                if not safe_name:
                    safe_name = "location"
                new_filename = f"{safe_name}.{ext}"
                new_path = os.path.join(app.config['UPLOAD_FOLDER'], 'locations', new_filename)
                
                os.rename(old_path, new_path)
                location.picture = new_filename
        
        db.session.commit()
        
        log_audit(current_user.id, 'update', 'location', location.id, f'Updated location: {location.name}')
        flash(f'Location "{location.name}" updated successfully!', 'success')
        return redirect(url_for('location_management'))
    
    return render_template('location_form.html', form=form, location=location)

@app.route('/location/<int:id>/delete', methods=['POST'])
@login_required
@admin_required
def location_delete(id):
    """Delete location"""
    from models import Location
    
    location = Location.query.get_or_404(id)
    
    # Check if location is in use
    if location.items or location.racks:
        flash('Cannot delete location that is in use by items or racks!', 'danger')
        return redirect(url_for('location_management'))
    
    # Delete picture file
    if location.picture:
        picture_path = os.path.join(app.config['UPLOAD_FOLDER'], 'locations', location.picture)
        if os.path.exists(picture_path):
            os.remove(picture_path)
    
    location_name = location.name
    db.session.delete(location)
    db.session.commit()
    
    log_audit(current_user.id, 'delete', 'location', id, f'Deleted location: {location_name}')
    flash(f'Location "{location_name}" deleted successfully!', 'success')
    return redirect(url_for('location_management'))

@app.route('/location-picture/<filename>')
@login_required
def location_picture(filename):
    """Serve location pictures"""
    location_dir = os.path.join(app.config['UPLOAD_FOLDER'], 'locations')
    return send_from_directory(location_dir, filename)

# ============= RACK MANAGEMENT ROUTES =============

@app.route('/rack-management')
@login_required
@admin_required
def rack_management():
    """Rack management page"""
    racks = Rack.query.order_by(Rack.name).all()
    return render_template('rack_management.html', racks=racks)

@app.route('/add-rack', methods=['POST'])
@login_required
@admin_required
def add_rack():
    """Add a new rack"""
    name = request.form.get('name')
    
    # Check for duplicate name
    existing = Rack.query.filter_by(name=name).first()
    if existing:
        flash(f'Rack "{name}" already exists!', 'danger')
        return redirect(url_for('rack_management'))
    
    description = request.form.get('description')
    location = request.form.get('location')
    rows = int(request.form.get('rows', 5))
    cols = int(request.form.get('cols', 5))
    
    rack = Rack(
        name=name,
        description=description,
        location=location,
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
@admin_required
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
@admin_required
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
@admin_required
def rack_new():
    """Create new rack with form"""
    if request.method == 'POST':
        name = request.form.get('name')
        
        # Check for duplicate
        existing = Rack.query.filter_by(name=name).first()
        if existing:
            flash(f'Rack "{name}" already exists!', 'danger')
            return redirect(url_for('rack_new'))
        
        description = request.form.get('description')
        location_id = request.form.get('location_id')
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
            rows=rows,
            cols=cols
        )
        db.session.add(rack)
        db.session.commit()
        
        log_audit(current_user.id, 'create', 'rack', rack.id, f'Created rack: {name}')
        flash(f'Rack "{name}" created successfully!', 'success')
        return redirect(url_for('location_management'))
    
    # GET - show form
    locations = Location.query.order_by(Location.name).all()
    max_drawer_rows = int(Setting.get('max_drawer_rows', '10'))
    max_drawer_cols = int(Setting.get('max_drawer_cols', '10'))
    return render_template('rack_form.html', rack=None, locations=locations, 
                         max_drawer_rows=max_drawer_rows, max_drawer_cols=max_drawer_cols)

@app.route('/rack/<int:id>/edit', methods=['GET', 'POST'])
@login_required
@admin_required
def rack_edit(id):
    """Edit rack with form"""
    rack = Rack.query.get_or_404(id)
    
    if request.method == 'POST':
        new_name = request.form.get('name')
        
        # Check for duplicate name (exclude current rack)
        if new_name != rack.name:
            existing = Rack.query.filter_by(name=new_name).first()
            if existing:
                flash(f'Rack "{new_name}" already exists!', 'danger')
                locations = Location.query.order_by(Location.name).all()
                max_drawer_rows = int(Setting.get('max_drawer_rows', '10'))
                max_drawer_cols = int(Setting.get('max_drawer_cols', '10'))
                return render_template('rack_form.html', rack=rack, locations=locations,
                                     max_drawer_rows=max_drawer_rows, max_drawer_cols=max_drawer_cols)
        
        rack.name = new_name
        rack.description = request.form.get('description')
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
        
        db.session.commit()
        
        log_audit(current_user.id, 'update', 'rack', rack.id, f'Updated rack: {rack.name} (size: {rows}x{cols})')
        flash(f'Rack "{rack.name}" updated successfully!', 'success')
        return redirect(url_for('location_management'))
    
    # GET - show form
    locations = Location.query.order_by(Location.name).all()
    max_drawer_rows = int(Setting.get('max_drawer_rows', '10'))
    max_drawer_cols = int(Setting.get('max_drawer_cols', '10'))
    return render_template('rack_form.html', rack=rack, locations=locations,
                         max_drawer_rows=max_drawer_rows, max_drawer_cols=max_drawer_cols)

@app.route('/rack/<int:id>/delete', methods=['POST'])
@login_required
@admin_required
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
    return render_template('visual_storage.html', racks=rack_data, all_racks=all_racks_for_dropdown, locations=locations, current_location_id=location_id, current_rack_id=rack_id)

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
@editor_required
def api_add_category():
    """API endpoint to add category from item form"""
    try:
        data = request.get_json()
        name = data.get('name', '').strip()
        description = data.get('description', '').strip()
        
        if not name:
            return jsonify({'success': False, 'error': 'Category name is required'})
        
        # Check if exists
        existing = Category.query.filter_by(name=name).first()
        if existing:
            return jsonify({'success': False, 'error': 'Category already exists'})
        
        category = Category(name=name, description=description)
        db.session.add(category)
        db.session.commit()
        
        log_audit(current_user.id, 'create', 'category', category.id, f'Created category: {category.name}')
        
        return jsonify({
            'success': True, 
            'category': {'id': category.id, 'name': category.name}
        })
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/footprint/add', methods=['POST'])
@login_required
@editor_required
def api_add_footprint():
    """API endpoint to add footprint from item form"""
    try:
        data = request.get_json()
        name = data.get('name', '').strip()
        description = data.get('description', '').strip()
        
        if not name:
            return jsonify({'success': False, 'error': 'Footprint name is required'})
        
        # Check if exists
        existing = Footprint.query.filter_by(name=name).first()
        if existing:
            return jsonify({'success': False, 'error': 'Footprint already exists'})
        
        footprint = Footprint(name=name, description=description)
        db.session.add(footprint)
        db.session.commit()
        
        log_audit(current_user.id, 'create', 'footprint', footprint.id, f'Created footprint: {footprint.name}')
        
        return jsonify({
            'success': True, 
            'footprint': {'id': footprint.id, 'name': footprint.name}
        })
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/tag/add', methods=['POST'])
@login_required
@editor_required
def api_add_tag():
    """API endpoint to add tag from item form"""
    try:
        data = request.get_json()
        name = data.get('name', '').strip()
        color = data.get('color', '#6c757d')
        
        if not name:
            return jsonify({'success': False, 'error': 'Tag name is required'})
        
        # Check if exists
        existing = Tag.query.filter_by(name=name).first()
        if existing:
            return jsonify({'success': False, 'error': 'Tag already exists'})
        
        tag = Tag(name=name, color=color)
        db.session.add(tag)
        db.session.commit()
        
        log_audit(current_user.id, 'create', 'tag', tag.id, f'Created tag: {tag.name}')
        
        return jsonify({
            'success': True, 
            'tag': {'id': tag.id, 'name': tag.name, 'color': tag.color}
        })
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/location/add', methods=['POST'])
@login_required
@editor_required
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
        
        # Check if exists
        existing = Location.query.filter_by(name=name).first()
        if existing:
            return jsonify({'success': False, 'error': 'Location already exists'})
        
        location = Location(name=name, info=info, description=description, color=color)
        db.session.add(location)
        db.session.commit()
        
        log_audit(current_user.id, 'create', 'location', location.id, f'Created location: {location.name}')
        
        return jsonify({
            'success': True, 
            'location': {'id': location.id, 'name': location.name, 'color': location.color}
        })
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/drawer/toggle-availability', methods=['POST'])
@login_required
@editor_required
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
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/drawer/move-items', methods=['POST'])
@login_required
@editor_required
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
        return jsonify({'success': False, 'error': str(e)})

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
    return render_template('settings.html')

@app.route('/settings/general')
@login_required
def settings_general():
    current_theme = current_user.theme or 'light'
    return render_template('settings_general.html', current_theme=current_theme)

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
        flash(f'Error saving table columns: {str(e)}', 'danger')
    
    return redirect(url_for('settings_general'))

@app.route('/settings/system', methods=['GET', 'POST'])
@login_required
@admin_required
def settings_system():
    """System-wide settings (Admin only)"""
    if request.method == 'POST':
        try:
            # Currency setting
            currency = request.form.get('currency', '$').strip()
            if len(currency) > 7:
                flash('Currency symbol must be 7 characters or less!', 'danger')
                return redirect(url_for('settings_system'))
            
            # Max file size (in MB)
            max_file_size = request.form.get('max_file_size', '10')
            try:
                max_file_size = int(max_file_size)
                if max_file_size < 1 or max_file_size > 100:
                    flash('Max file size must be between 1 and 100 MB!', 'danger')
                    return redirect(url_for('settings_system'))
            except ValueError:
                flash('Invalid max file size value!', 'danger')
                return redirect(url_for('settings_system'))
            
            # Allowed file extensions
            allowed_extensions = request.form.get('allowed_extensions', '').strip()
            if not allowed_extensions:
                flash('You must specify at least one allowed file type!', 'danger')
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
            
            # Save settings
            Setting.set('currency', currency, 'Currency symbol for prices')
            Setting.set('max_file_size_mb', max_file_size, 'Maximum file upload size in MB')
            Setting.set('allowed_extensions', allowed_extensions, 'Allowed file extensions (comma-separated)')
            Setting.set('max_drawer_rows', max_drawer_rows, 'Maximum drawer rows (1-32)')
            Setting.set('max_drawer_cols', max_drawer_cols, 'Maximum drawer columns (1-32)')
            
            # Update app config dynamically
            app.config['MAX_CONTENT_LENGTH'] = max_file_size * 1024 * 1024
            
            flash('System settings updated successfully!', 'success')
            log_audit(current_user.id, 'update', 'settings', 0, 
                     f'Updated system settings: currency={currency}, max_file_size={max_file_size}MB, drawer_size={max_drawer_rows}x{max_drawer_cols}')
            
        except Exception as e:
            flash(f'Error saving settings: {str(e)}', 'danger')
        
        return redirect(url_for('settings_system'))
    
    # GET request - load current settings
    currency = Setting.get('currency', '$')
    max_file_size = Setting.get('max_file_size_mb', '10')
    allowed_extensions = Setting.get('allowed_extensions', 'pdf,png,jpg,jpeg,gif,txt,doc,docx')
    max_drawer_rows = Setting.get('max_drawer_rows', '10')
    max_drawer_cols = Setting.get('max_drawer_cols', '10')
    
    return render_template('settings_system.html', 
                          currency=currency,
                          max_file_size=max_file_size,
                          allowed_extensions=allowed_extensions,
                          max_drawer_rows=max_drawer_rows,
                          max_drawer_cols=max_drawer_cols)


# ============= FOOTPRINTS =============

@app.route('/footprints')
@login_required
def footprints():
    """Redirect to unified item management page"""
    return redirect(url_for('item_management'))


@app.route('/footprint/new', methods=['GET', 'POST'])
@login_required
@editor_required
def footprint_new():
    from models import Footprint
    if request.method == 'POST':
        # Check for duplicate name
        existing = Footprint.query.filter_by(name=request.form.get('name')).first()
        if existing:
            flash(f'Footprint "{request.form.get("name")}" already exists!', 'danger')
            return render_template('footprint_form.html', title='New Footprint')
        
        footprint = Footprint(
            name=request.form.get('name'),
            description=request.form.get('description')
        )
        db.session.add(footprint)
        db.session.commit()
        flash(f'Footprint "{footprint.name}" created!', 'success')
        return redirect(url_for('item_management'))
    return render_template('footprint_form.html', title='New Footprint')

@app.route('/footprint/<int:id>/edit', methods=['GET', 'POST'])
@login_required
@editor_required
def footprint_edit(id):
    from models import Footprint
    footprint = Footprint.query.get_or_404(id)
    if request.method == 'POST':
        footprint.name = request.form.get('name')
        footprint.description = request.form.get('description')
        db.session.commit()
        flash(f'Footprint "{footprint.name}" updated!', 'success')
        return redirect(url_for('item_management'))
    return render_template('footprint_form.html', footprint=footprint, title='Edit Footprint')

@app.route('/footprint/<int:id>/delete', methods=['POST'])
@login_required
@admin_required
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
@editor_required
def tag_new():
    from models import Tag
    if request.method == 'POST':
        # Check for duplicate name
        existing = Tag.query.filter_by(name=request.form.get('name')).first()
        if existing:
            flash(f'Tag "{request.form.get("name")}" already exists!', 'danger')
            return render_template('tag_form.html', title='New Tag')
        
        tag = Tag(
            name=request.form.get('name'),
            color=request.form.get('color', '#6c757d')
        )
        db.session.add(tag)
        db.session.commit()
        flash(f'Tag "{tag.name}" created!', 'success')
        return redirect(url_for('item_management'))
    return render_template('tag_form.html', title='New Tag')

@app.route('/tag/<int:id>/edit', methods=['GET', 'POST'])
@login_required
@editor_required
def tag_edit(id):
    from models import Tag
    tag = Tag.query.get_or_404(id)
    if request.method == 'POST':
        tag.name = request.form.get('name')
        tag.color = request.form.get('color')
        db.session.commit()
        flash(f'Tag "{tag.name}" updated!', 'success')
        return redirect(url_for('item_management'))
    return render_template('tag_form.html', tag=tag, title='Edit Tag')

@app.route('/tag/<int:id>/delete', methods=['POST'])
@login_required
@admin_required
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
@admin_required
def backup_restore():
    return render_template('backup_restore.html')

@app.route('/backup/download')
@login_required
@admin_required
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
@admin_required
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
@admin_required
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
        flash(f'Export error: {str(e)}', 'danger')
        return redirect(url_for('backup_restore'))


@app.route('/backup/import-selective', methods=['POST'])
@login_required
@admin_required
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
        flash(f'Fatal error: {str(e)}', 'danger')
        return redirect(url_for('backup_restore'))

# ============= MAGIC PARAMETERS =============

@app.route('/settings/magic-parameters')
@login_required
def magic_parameters():
    """Magic Parameters settings page"""
    from models import MagicParameter, ParameterTemplate
    
    # Get parameters grouped by type
    number_params = MagicParameter.query.filter_by(param_type='number').order_by(MagicParameter.name).all()
    date_params = MagicParameter.query.filter_by(param_type='date').order_by(MagicParameter.name).all()
    string_params = MagicParameter.query.filter_by(param_type='string').order_by(MagicParameter.name).all()
    templates = ParameterTemplate.query.order_by(ParameterTemplate.name).all()
    
    return render_template('magic_parameters.html', 
                          number_params=number_params,
                          date_params=date_params,
                          string_params=string_params,
                          templates=templates)


@app.route('/magic-parameter/new', methods=['POST'])
@login_required
@editor_required
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
        return jsonify({
            'success': False,
            'errors': [f'Error creating parameter: {str(e)}']
        }), 500


@app.route('/magic-parameter/<int:id>/edit', methods=['POST'])
@login_required
@editor_required
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
@editor_required
def magic_parameter_manage(id):
    from models import MagicParameter
    parameter = MagicParameter.query.get_or_404(id)
    return render_template('magic_parameter_manage.html', parameter=parameter)


@app.route('/magic-parameter/<int:id>/add-unit', methods=['POST'])
@login_required
@editor_required
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
@editor_required
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
@editor_required
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
@editor_required
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
@admin_required
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
@editor_required
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
@editor_required
def parameter_template_manage(id):
    from models import ParameterTemplate
    template = ParameterTemplate.query.get_or_404(id)
    return render_template('parameter_template_manage.html', template=template)


@app.route('/parameter-template/<int:id>/edit', methods=['GET', 'POST'])
@login_required
@editor_required
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
@editor_required
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
@editor_required
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
@admin_required
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
@editor_required
def item_populate_template(id):
    from models import ItemParameter, ParameterTemplate
    item = Item.query.get_or_404(id)
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
@editor_required
def item_add_parameter(id):
    from models import ItemParameter, MagicParameter
    item = Item.query.get_or_404(id)
    
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
@editor_required
def item_delete_parameter(item_id, param_id):
    from models import ItemParameter
    item = Item.query.get_or_404(item_id)
    item_param = ItemParameter.query.get_or_404(param_id)
    
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
@editor_required
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
    
    return render_template('notifications.html', notifications=notifications)


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
