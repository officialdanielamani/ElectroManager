from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime, timezone
import json
import secrets
import string
import uuid

db = SQLAlchemy()

class Setting(db.Model):
    __tablename__ = 'settings'
    
    id = db.Column(db.Integer, primary_key=True)
    key = db.Column(db.String(100), unique=True, nullable=False)
    value = db.Column(db.String(500))
    description = db.Column(db.String(500))
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
    
    @staticmethod
    def get(key, default=None):
        setting = Setting.query.filter_by(key=key).first()
        if setting:
            if setting.value in ['true', 'false']:
                return setting.value == 'true'
            return setting.value
        return default
    
    @staticmethod
    def set(key, value, description=None):
        setting = Setting.query.filter_by(key=key).first()
        if setting:
            setting.value = str(value).lower() if isinstance(value, bool) else str(value)
            setting.updated_at = datetime.now(timezone.utc)
        else:
            setting = Setting(key=key, value=str(value).lower() if isinstance(value, bool) else str(value), description=description)
            db.session.add(setting)
        db.session.commit()
    
    def __repr__(self):
        return f'<Setting {self.key}={self.value}>'


class Location(db.Model):
    __tablename__ = 'locations'
    
    id = db.Column(db.Integer, primary_key=True)
    uuid = db.Column(db.String(12), unique=True, nullable=False)
    name = db.Column(db.String(100), nullable=False)
    info = db.Column(db.String(500))
    description = db.Column(db.Text)
    picture = db.Column(db.String(200))
    color = db.Column(db.String(7), default='#6c757d')
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
    
    racks = db.relationship('Rack', backref='physical_location', lazy=True, foreign_keys='Rack.location_id')
    items = db.relationship('Item', backref='general_location', lazy=True, foreign_keys='Item.location_id')
    
    def __init__(self, **kwargs):
        super(Location, self).__init__(**kwargs)
        if not self.uuid:
            chars = string.ascii_uppercase + string.digits
            self.uuid = ''.join(secrets.choice(chars) for _ in range(11)) + 'L'
    
    def __repr__(self):
        return f'<Location {self.name}>'


class Role(db.Model):
    __tablename__ = 'roles'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), unique=True, nullable=False)
    description = db.Column(db.Text)
    is_system_role = db.Column(db.Boolean, default=False)
    permissions = db.Column(db.Text, default='{}', nullable=False)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
    users = db.relationship('User', backref='user_role', lazy=True)
    
    def get_permissions(self):
        try:
            return json.loads(self.permissions) if self.permissions else {}
        except (json.JSONDecodeError, TypeError):
            return {}
    
    def set_permissions(self, perms):
        json_str = json.dumps(perms)
        self.permissions = json_str
        from sqlalchemy.orm import attributes
        attributes.flag_modified(self, 'permissions')
    
    def has_permission(self, resource, action):
        perms = self.get_permissions()
        if '.' in resource:
            parts = resource.split('.')
            current = perms
            for part in parts:
                if not isinstance(current, dict) or part not in current:
                    return False
                current = current[part]
            return current.get(action, False) if isinstance(current, dict) else False
        return perms.get(resource, {}).get(action, False)
    
    def __repr__(self):
        return f'<Role {self.name}>'


class User(UserMixin, db.Model):
    __tablename__ = 'users'
    
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    role_id = db.Column(db.Integer, db.ForeignKey('roles.id'), nullable=False)
    theme = db.Column(db.String(20), default='light')
    user_font = db.Column(db.String(50), default='system')
    table_columns_view = db.Column(db.Text, default='["name", "category", "tags", "type_model", "sku", "footprint", "quantity", "total_price", "price_per_unit", "location", "uuid", "status"]')
    project_table_columns_view = db.Column(db.Text, default='["project_name", "info", "categories", "tags", "date_start", "dateline", "total_cost", "status", "users", "group", "project_id"]')
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    is_active = db.Column(db.Boolean, default=True)
    is_demo_user = db.Column(db.Boolean, default=False)
    max_login_attempts = db.Column(db.Integer, default=0)
    allow_password_reset = db.Column(db.Boolean, default=True)
    profile_photo = db.Column(db.String(255))
    allow_profile_picture_change = db.Column(db.Boolean, default=True)
    profile_picture_source = db.Column(db.String(10), default='share')  # 'upload', 'share', 'both'
    failed_login_attempts = db.Column(db.Integer, default=0)
    account_locked_until = db.Column(db.DateTime)
    auto_unlock_enabled = db.Column(db.Boolean, default=True)
    auto_unlock_minutes = db.Column(db.Integer, default=15)
    
    def set_password(self, password):
        self.password_hash = generate_password_hash(password)
    
    def check_password(self, password):
        return check_password_hash(self.password_hash, password)
    
    def is_admin(self):
        return self.user_role and self.user_role.name == 'Admin'
    
    def is_editor(self):
        if self.is_admin():
            return True
        return self.has_permission('items', 'view') and (
            self.has_permission('items', 'create') or
            self.has_permission('items', 'edit_info') or
            self.has_permission('items', 'edit_batch') or
            self.has_permission('items', 'edit_quantity') or
            self.has_permission('items', 'edit_price') or
            self.has_permission('items', 'edit_sn') or
            self.has_permission('items', 'edit_lending') or
            self.has_permission('items', 'edit_advance')
        )
    
    def has_permission(self, resource, action):
        if self.is_admin():
            return True
        return self.user_role and self.user_role.has_permission(resource, action)
    
    def get_table_columns(self):
        try:
            return json.loads(self.table_columns_view)
        except (json.JSONDecodeError, TypeError):
            return ["name", "category", "tags", "type_model", "sku", "footprint", "quantity", "total_price", "price_per_unit", "location", "uuid", "status"]
    
    def set_table_columns(self, columns):
        self.table_columns_view = json.dumps(columns)

    def get_project_table_columns(self):
        try:
            return json.loads(self.project_table_columns_view)
        except (json.JSONDecodeError, TypeError):
            return ["project_name", "info", "categories", "tags", "date_start", "dateline", "total_cost", "status", "users", "group", "project_id"]

    def set_project_table_columns(self, columns):
        self.project_table_columns_view = json.dumps(columns)
        self.table_columns_view = json.dumps(columns)
    
    def __repr__(self):
        return f'<User {self.username}>'


class Category(db.Model):
    __tablename__ = 'categories'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), unique=True, nullable=False)
    description = db.Column(db.Text)
    color = db.Column(db.String(7), default='#6c757d')
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
    items = db.relationship('Item', backref='category', lazy=True)
    def __repr__(self):
        return f'<Category {self.name}>'


class Footprint(db.Model):
    __tablename__ = 'footprints'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), unique=True, nullable=False)
    description = db.Column(db.Text)
    color = db.Column(db.String(7), default='#6c757d')
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
    items = db.relationship('Item', backref='footprint', lazy=True)
    def __repr__(self):
        return f'<Footprint {self.name}>'


class Tag(db.Model):
    __tablename__ = 'tags'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), unique=True, nullable=False)
    description = db.Column(db.Text)
    color = db.Column(db.String(7), default='#6c757d')
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
    def __repr__(self):
        return f'<Tag {self.name}>'


class Rack(db.Model):
    __tablename__ = 'racks'
    id = db.Column(db.Integer, primary_key=True)
    uuid = db.Column(db.String(12), unique=True, nullable=False)
    name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text)
    location_id = db.Column(db.Integer, db.ForeignKey('locations.id'), nullable=True)
    picture = db.Column(db.String(200))
    color = db.Column(db.String(7), default='#6c757d')
    rows = db.Column(db.Integer, default=5)
    cols = db.Column(db.Integer, default=5)
    unavailable_drawers = db.Column(db.Text)
    merged_cells = db.Column(db.Text, default='[]')
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
    items = db.relationship('Item', backref='rack', lazy=True)

    def __init__(self, **kwargs):
        super(Rack, self).__init__(**kwargs)
        if not self.uuid:
            chars = string.ascii_uppercase + string.digits
            self.uuid = ''.join(secrets.choice(chars) for _ in range(11)) + 'R'

    def get_unavailable_drawers(self):
        if not self.unavailable_drawers:
            return []
        try:
            return json.loads(self.unavailable_drawers)
        except (json.JSONDecodeError, TypeError):
            return []

    def is_drawer_unavailable(self, drawer_id):
        return drawer_id in self.get_unavailable_drawers()

    def get_merged_cells(self):
        try:
            return json.loads(self.merged_cells or '[]')
        except (json.JSONDecodeError, TypeError):
            return []

    def get_merge_group(self, cell_id):
        for group in self.get_merged_cells():
            if cell_id in group.get('cells', []):
                return group
        return None

    def is_merged_away(self, cell_id):
        group = self.get_merge_group(cell_id)
        return group is not None and group.get('master') != cell_id

    def get_master_cell(self, cell_id):
        group = self.get_merge_group(cell_id)
        return group['master'] if group else cell_id

    def compute_merge_layout(self):
        """Return (skip_cells, cell_spans, group_cells) for template rendering.

        skip_cells:  cells not rendered (slaves of rectangular merges)
        cell_spans:  master → {rowspan, colspan} for rectangular merges
        group_cells: cell → {role, master, count} for non-rectangular merges
        """
        skip_cells = set()
        cell_spans = {}
        group_cells = {}
        for group in self.get_merged_cells():
            master = group.get('master')
            cells = group.get('cells', [])
            rows_used, cols_used = set(), set()
            for cell in cells:
                try:
                    parts = cell[1:].split('-C')
                    rows_used.add(int(parts[0]))
                    cols_used.add(int(parts[1]))
                except (ValueError, IndexError):
                    continue
            if not rows_used or not cols_used:
                continue
            is_rectangular = len(cells) == len(rows_used) * len(cols_used)
            if is_rectangular:
                cell_spans[master] = {
                    'rowspan': len(rows_used),
                    'colspan': len(cols_used),
                }
                for cell in cells:
                    if cell != master:
                        skip_cells.add(cell)
            else:
                for cell in cells:
                    group_cells[cell] = {
                        'role': 'master' if cell == master else 'slave',
                        'master': master,
                        'count': len(cells),
                    }
        return skip_cells, cell_spans, group_cells

    def get_drawer_uuid(self, row, col):
        return f"{self.uuid}{int(row):02d}{int(col):02d}"

    def __repr__(self):
        return f'<Rack {self.name}>'


item_share_files = db.Table(
    'item_share_files',
    db.Column('item_id', db.Integer, db.ForeignKey('items.id'), primary_key=True),
    db.Column('shared_file_id', db.Integer, db.ForeignKey('shared_files.id'), primary_key=True),
)

project_share_files = db.Table(
    'project_share_files',
    db.Column('project_id', db.Integer, db.ForeignKey('projects.id'), primary_key=True),
    db.Column('shared_file_id', db.Integer, db.ForeignKey('shared_files.id'), primary_key=True),
)


class Item(db.Model):
    __tablename__ = 'items'
    
    id = db.Column(db.Integer, primary_key=True)
    uuid = db.Column(db.String(16), unique=True, nullable=False)
    name = db.Column(db.String(200), nullable=False)
    sku = db.Column(db.String(100))
    info = db.Column(db.String(500))
    description = db.Column(db.Text)

    quantity = db.Column(db.Integer, default=0)
    price = db.Column(db.Float, default=0.0)

    location_id = db.Column(db.Integer, db.ForeignKey('locations.id'), nullable=True)
    rack_id = db.Column(db.Integer, db.ForeignKey('racks.id'))
    drawer = db.Column(db.String(50))
    
    min_quantity = db.Column(db.Integer, default=0)
    category_id = db.Column(db.Integer, db.ForeignKey('categories.id'))
    footprint_id = db.Column(db.Integer, db.ForeignKey('footprints.id'))
    tags = db.Column(db.Text)
    
    datasheet_urls = db.Column(db.Text)
    no_stock_warning = db.Column(db.Boolean, default=True)
    thumbnail = db.Column(db.String(300))

    sn_tracking_enabled = db.Column(db.Boolean, default=False)
    
    @property
    def has_any_tracking(self):
        """True if any batch has SN tracking enabled"""
        return any(b.sn_tracking_enabled for b in self.batches)
    
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
    created_by = db.Column(db.Integer, db.ForeignKey('users.id'))
    updated_by = db.Column(db.Integer, db.ForeignKey('users.id'))
    
    creator = db.relationship('User', foreign_keys=[created_by], backref='items_created')
    updater = db.relationship('User', foreign_keys=[updated_by], backref='items_updated')
    
    attachments = db.relationship('Attachment', backref='item', lazy=True, cascade='all, delete-orphan')
    batches = db.relationship('ItemBatch', backref='item', lazy=True, cascade='all, delete-orphan', order_by='ItemBatch.batch_number')
    linked_share_files = db.relationship('SharedFile', secondary=item_share_files, lazy='subquery', backref=db.backref('linked_items', lazy=True))
    
    def __init__(self, **kwargs):
        super(Item, self).__init__(**kwargs)
        if not self.uuid:
            chars = string.ascii_uppercase + string.digits
            self.uuid = ''.join(secrets.choice(chars) for _ in range(11)) + 'I'
    
    def get_full_location(self):
        if self.rack_id and self.drawer:
            rack_location = self.rack.physical_location.name if self.rack and self.rack.physical_location else ''
            return f"{self.rack.name} - {self.drawer}" + (f" ({rack_location})" if rack_location else "")
        elif self.location_id and self.general_location:
            return self.general_location.name
        return 'Not specified'
    
    def get_available_quantity(self):
        return sum(b.get_available_quantity() for b in self.batches)
    
    def get_total_lend_quantity(self):
        """Total lent quantity across all batches"""
        return sum(b.get_lend_quantity() for b in self.batches)

    def get_total_project_quantity(self):
        """Total quantity allocated to projects across all batches"""
        return sum(b.get_project_used_quantity() for b in self.batches)
    
    def get_overall_quantity(self):
        """Total quantity across all batches"""
        return sum(b.quantity for b in self.batches)
    
    def get_overall_total_price(self):
        """Display total price (qty=0 batches count as 1 unit for price reference)."""
        return sum(b.get_batch_total_price() for b in self.batches)

    def get_overall_total_value(self):
        """Actual stock value: sum of (price × real qty) across all batches."""
        return sum(b.get_batch_total_value() for b in self.batches)

    def get_average_price(self):
        """Average price per unit based on actual stock value."""
        total_qty = self.get_overall_quantity()
        if total_qty == 0:
            return 0.0
        return self.get_overall_total_value() / total_qty

    def recalculate_from_batches(self):
        """Sync quantity/price fields from batches using actual values."""
        self.quantity = self.get_overall_quantity()
        total = self.get_overall_total_value()
        if self.quantity > 0:
            self.price = total / self.quantity
        else:
            self.price = 0.0
    
    def is_no_stock(self):
        available = self.get_available_quantity()
        return available <= 0 and self.no_stock_warning
    
    def is_low_stock(self):
        available = self.get_available_quantity()
        if available < self.min_quantity:
            if available <= 0 and self.no_stock_warning:
                return False
            return True
        return False
    
    def is_ok_stock(self):
        return self.get_available_quantity() >= self.min_quantity
    
    def get_drawer_uuid(self):
        if not self.rack or not self.drawer:
            return None
        import re
        match = re.match(r'R(\d+)-C(\d+)', self.drawer)
        if not match:
            return None
        row = int(match.group(1))
        col = int(match.group(2))
        return self.rack.get_drawer_uuid(row, col)
    
    def get_total_price(self):
        return self.get_overall_total_price()

    def get_total_value(self):
        return self.get_overall_total_value()
    
    def get_tags_list(self):
        if not self.tags:
            return []
        try:
            tag_ids = json.loads(self.tags)
            return Tag.query.filter(Tag.id.in_(tag_ids)).all()
        except (json.JSONDecodeError, TypeError):
            return []
    
    def get_tags(self):
        return self.get_tags_list()
    
    def get_next_batch_number(self):
        max_batch = db.session.query(db.func.max(ItemBatch.batch_number)).filter_by(item_id=self.id).scalar()
        return (max_batch or 0) + 1
    
    def __repr__(self):
        return f'<Item {self.name}>'


class ItemBatch(db.Model):
    """A batch/purchase of an item"""
    __tablename__ = 'item_batches'
    
    id = db.Column(db.Integer, primary_key=True)
    item_id = db.Column(db.Integer, db.ForeignKey('items.id'), nullable=False)
    batch_number = db.Column(db.Integer, nullable=False)
    batch_label = db.Column(db.String(32))
    quantity = db.Column(db.Integer, default=0)
    price_per_unit = db.Column(db.Float, default=0.0)
    purchase_date = db.Column(db.Date)
    note = db.Column(db.String(128))
    sn_tracking_enabled = db.Column(db.Boolean, default=False)

    follow_main_location = db.Column(db.Boolean, default=True)
    location_id = db.Column(db.Integer, db.ForeignKey('locations.id'), nullable=True)
    rack_id = db.Column(db.Integer, db.ForeignKey('racks.id'), nullable=True)
    drawer = db.Column(db.String(50))

    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    batch_location = db.relationship('Location', foreign_keys=[location_id])
    batch_rack = db.relationship('Rack', foreign_keys=[rack_id])

    serial_numbers = db.relationship('BatchSerialNumber', backref='batch', lazy=True, cascade='all, delete-orphan', order_by='BatchSerialNumber.sequence_number')
    lend_records = db.relationship('BatchLendRecord', backref='batch', lazy=True, cascade='all, delete-orphan', order_by='BatchLendRecord.id')
    
    def get_effective_location_text(self):
        """Return human-readable location. Falls back to parent item when follow_main_location is True."""
        if self.follow_main_location:
            return self.item.get_full_location() if self.item else 'Not specified'
        if self.rack_id and self.drawer:
            rack_name = self.batch_rack.name if self.batch_rack else ''
            loc_name = self.batch_rack.physical_location.name if self.batch_rack and self.batch_rack.physical_location else ''
            return f"{rack_name} - {self.drawer}" + (f" ({loc_name})" if loc_name else "")
        if self.location_id and self.batch_location:
            return self.batch_location.name
        return 'Not specified'

    def get_effective_location_color(self):
        """Return the hex color of the effective location for badge styling."""
        if self.follow_main_location:
            if self.item:
                if self.item.rack_id and self.item.rack and self.item.rack.physical_location:
                    return self.item.rack.physical_location.color or '#6c757d'
                if self.item.location_id and self.item.general_location:
                    return self.item.general_location.color or '#6c757d'
            return '#6c757d'
        if self.rack_id and self.batch_rack and self.batch_rack.physical_location:
            return self.batch_rack.physical_location.color or '#6c757d'
        if self.location_id and self.batch_location:
            return self.batch_location.color or '#6c757d'
        return '#6c757d'

    def get_batch_total_price(self):
        """Display price reference: qty=0 treated as 1 so price/unit is visible when out of stock."""
        if not self.price_per_unit:
            return 0.0
        return self.price_per_unit * max(1, self.quantity)

    def get_batch_total_value(self):
        """Actual stock value: price × real quantity (0 when qty=0)."""
        return self.price_per_unit * self.quantity if self.price_per_unit else 0.0
    
    def get_display_label(self):
        if self.batch_label:
            return self.batch_label
        return f"Batch {self.batch_number}"
    
    def get_lend_quantity(self):
        """Total lend quantity across all lend records (or per-SN count for tracked batches)."""
        if self.sn_tracking_enabled:
            return sum(1 for sn in self.serial_numbers if sn.lend_to_id)
        return sum(r.quantity for r in self.lend_records)

    def get_lend_records_data(self):
        """Serialise lend records to a list of dicts for JS embedding."""
        result = []
        for r in self.lend_records:
            result.append({
                'id': r.id,
                'type': r.lend_to_type or '',
                'contact_id': r.lend_to_id,
                'label': r.get_lend_to_display(),
                'qty': r.quantity,
                'start': r.lend_start.strftime('%Y-%m-%d') if r.lend_start else '',
                'end': r.lend_end.strftime('%Y-%m-%d') if r.lend_end else '',
                'notify': r.lend_notify_enabled or False,
                'days': r.lend_notify_before_days or 3,
            })
        return result

    def get_project_used_quantity(self):
        """Get total used_quantity across all projects for this batch"""
        from models import ProjectBOMItem
        return db.session.query(db.func.coalesce(db.func.sum(ProjectBOMItem.used_quantity), 0)).filter(
            ProjectBOMItem.batch_id == self.id,
            ProjectBOMItem.used_quantity > 0
        ).scalar()

    def get_project_used_sn_ids(self):
        """Get set of serial number IDs assigned to used_quantity in projects"""
        from models import ProjectBOMItem
        bom_items = ProjectBOMItem.query.filter(
            ProjectBOMItem.batch_id == self.id,
            ProjectBOMItem.used_quantity > 0,
            ProjectBOMItem.serial_numbers.isnot(None)
        ).all()
        ids = set()
        for bom in bom_items:
            try:
                ids.update(json.loads(bom.serial_numbers))
            except (json.JSONDecodeError, TypeError):
                pass
        return ids

    def get_project_names_for_batch(self):
        """Get list of project names that have used_quantity > 0 for this batch"""
        from models import ProjectBOMItem, Project
        bom_items = ProjectBOMItem.query.filter(
            ProjectBOMItem.batch_id == self.id,
            ProjectBOMItem.used_quantity > 0
        ).all()
        names = []
        for bom in bom_items:
            if bom.project and bom.project.name not in names:
                names.append(bom.project.name)
        return names

    def get_available_quantity(self):
        return self.quantity - self.get_lend_quantity() - self.get_project_used_quantity()
    
    def generate_serial_numbers(self):
        """Generate ISN serial numbers for all units in this batch"""
        item = Item.query.get(self.item_id)
        if not item:
            return
        # Preserve existing info/lend data
        existing_data = {}
        for sn in self.serial_numbers:
            existing_data[sn.sequence_number] = {
                'serial_number': sn.serial_number,
                'info': sn.info or '',
                'lend_to_type': sn.lend_to_type or '',
                'lend_to_id': sn.lend_to_id,
                'lend_start': sn.lend_start,
                'lend_end': sn.lend_end,
                'lend_notify_enabled': sn.lend_notify_enabled or False,
                'lend_notify_before_days': sn.lend_notify_before_days or 3,
            }
        BatchSerialNumber.query.filter_by(batch_id=self.id).delete()
        qty = min(self.quantity, 100)
        date_str = self.purchase_date.strftime('%Y%m%d') if self.purchase_date else '00000000'
        label = self.batch_label or f"B{self.batch_number}"
        for i in range(1, qty + 1):
            isn = f"{item.uuid}-{date_str}-{label}-{i:03d}"
            old = existing_data.get(i, {})
            sn = BatchSerialNumber(
                batch_id=self.id,
                sequence_number=i,
                internal_serial_number=isn,
                serial_number=old.get('serial_number', ''),
                info=old.get('info', ''),
                lend_to_type=old.get('lend_to_type', ''),
                lend_to_id=old.get('lend_to_id'),
                lend_start=old.get('lend_start'),
                lend_end=old.get('lend_end'),
                lend_notify_enabled=old.get('lend_notify_enabled', False),
                lend_notify_before_days=old.get('lend_notify_before_days', 3),
            )
            db.session.add(sn)
    
    def regenerate_serial_numbers_if_enabled(self):
        if self.sn_tracking_enabled:
            self.generate_serial_numbers()
    
    def __repr__(self):
        return f'<ItemBatch #{self.batch_number} for Item {self.item_id}>'


class BatchSerialNumber(db.Model):
    """Serial number tracking for individual units in a batch"""
    __tablename__ = 'batch_serial_numbers'
    
    id = db.Column(db.Integer, primary_key=True)
    batch_id = db.Column(db.Integer, db.ForeignKey('item_batches.id'), nullable=False)
    sequence_number = db.Column(db.Integer, nullable=False)
    serial_number = db.Column(db.String(200), default='')
    internal_serial_number = db.Column(db.String(200), nullable=False)
    info = db.Column(db.String(32), default='')
    lend_to_type = db.Column(db.String(20), default='')
    lend_to_id = db.Column(db.Integer, nullable=True)
    lend_start = db.Column(db.Date, nullable=True)
    lend_end = db.Column(db.Date, nullable=True)
    lend_notify_enabled = db.Column(db.Boolean, default=False)
    lend_notify_before_days = db.Column(db.Integer, default=3)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    def get_lend_to_display(self):
        if not self.lend_to_id or not self.lend_to_type:
            return ''
        try:
            if self.lend_to_type == 'user':
                obj = User.query.get(self.lend_to_id)
                return obj.username if obj else f'User #{self.lend_to_id}'
            elif self.lend_to_type == 'person':
                obj = ContactPerson.query.get(self.lend_to_id)
                return obj.name if obj else f'Person #{self.lend_to_id}'
            elif self.lend_to_type == 'organization':
                obj = ContactOrganization.query.get(self.lend_to_id)
                return obj.name if obj else f'Org #{self.lend_to_id}'
            elif self.lend_to_type == 'group':
                obj = ContactGroup.query.get(self.lend_to_id)
                return obj.name if obj else f'Group #{self.lend_to_id}'
        except Exception:
            pass
        return ''

    def __repr__(self):
        return f'<BatchSerialNumber {self.internal_serial_number}>'


class BatchLendRecord(db.Model):
    """One lending record for a non-SN batch (supports multiple per batch)."""
    __tablename__ = 'batch_lend_records'

    id = db.Column(db.Integer, primary_key=True)
    batch_id = db.Column(db.Integer, db.ForeignKey('item_batches.id'), nullable=False)
    lend_to_type = db.Column(db.String(20), default='')
    lend_to_id = db.Column(db.Integer, nullable=True)
    quantity = db.Column(db.Integer, default=1)
    lend_start = db.Column(db.Date, nullable=True)
    lend_end = db.Column(db.Date, nullable=True)
    lend_notify_enabled = db.Column(db.Boolean, default=False)
    lend_notify_before_days = db.Column(db.Integer, default=3)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    def get_lend_to_display(self):
        if not self.lend_to_id or not self.lend_to_type:
            return ''
        try:
            if self.lend_to_type == 'user':
                obj = User.query.get(self.lend_to_id)
                return obj.username if obj else f'User #{self.lend_to_id}'
            elif self.lend_to_type == 'person':
                obj = ContactPerson.query.get(self.lend_to_id)
                return obj.name if obj else f'Person #{self.lend_to_id}'
            elif self.lend_to_type == 'organization':
                obj = ContactOrganization.query.get(self.lend_to_id)
                return obj.name if obj else f'Org #{self.lend_to_id}'
            elif self.lend_to_type == 'group':
                obj = ContactGroup.query.get(self.lend_to_id)
                return obj.name if obj else f'Group #{self.lend_to_id}'
        except Exception:
            pass
        return ''

    def __repr__(self):
        return f'<BatchLendRecord batch={self.batch_id} to={self.lend_to_type}:{self.lend_to_id}>'


class Attachment(db.Model):
    __tablename__ = 'attachments'
    id = db.Column(db.Integer, primary_key=True)
    filename = db.Column(db.String(255), nullable=False)
    original_filename = db.Column(db.String(255), nullable=False)
    file_path = db.Column(db.String(500), nullable=False)
    file_type = db.Column(db.String(50))
    file_size = db.Column(db.Integer)
    item_id = db.Column(db.Integer, db.ForeignKey('items.id'), nullable=False)
    uploaded_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    uploaded_by = db.Column(db.Integer, db.ForeignKey('users.id'))
    def __repr__(self):
        return f'<Attachment {self.original_filename}>'


class AuditLog(db.Model):
    __tablename__ = 'audit_logs'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    action = db.Column(db.String(50), nullable=False)
    entity_type = db.Column(db.String(50), nullable=False)
    entity_id = db.Column(db.Integer)
    details = db.Column(db.Text)
    timestamp = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    user = db.relationship('User', backref='audit_logs')
    def __repr__(self):
        return f'<AuditLog {self.action} {self.entity_type}>'


class MagicParameter(db.Model):
    __tablename__ = 'magic_parameters'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), unique=True, nullable=False)
    param_type = db.Column(db.String(50), nullable=False)
    description = db.Column(db.Text)
    notify_enabled = db.Column(db.Boolean, default=False)
    is_whole_number = db.Column(db.Boolean, default=True)
    number_min = db.Column(db.Float)
    number_max = db.Column(db.Float)
    number_step = db.Column(db.Float)
    number_decimal_places = db.Column(db.Integer, default=0)
    number_required = db.Column(db.Boolean, default=False)
    # String-type specific fields
    string_select_min = db.Column(db.Integer, default=0)
    string_select_max = db.Column(db.Integer, default=1)
    string_allow_custom = db.Column(db.Boolean, default=False)
    string_regex = db.Column(db.String(500))
    string_regex_info = db.Column(db.String(200))
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
    units = db.relationship('ParameterUnit', backref='parameter', lazy=True, cascade='all, delete-orphan')
    string_options = db.relationship('ParameterStringOption', backref='parameter', lazy=True, cascade='all, delete-orphan')
    item_parameters = db.relationship('ItemParameter', backref='parameter', lazy=True, cascade='all, delete-orphan')
    
    def get_units_list(self):
        if self.param_type == 'number':
            return [unit.unit for unit in self.units]
        return []
    
    def get_string_options_list(self):
        if self.param_type == 'string':
            return [option.value for option in self.string_options]
        return []

    def validate_string_selections(self, selected_values, custom_values):
        """Validate selected + custom values against min/max and regex. Returns (ok, error_msg).
        string_select_max = -1 means unlimited."""
        import re as _re
        total = len(selected_values) + len(custom_values)
        min_sel = self.string_select_min or 0
        max_sel = self.string_select_max if self.string_select_max is not None else 1
        if total < min_sel:
            return False, f"You must select at least {min_sel} option(s)"
        if max_sel != -1 and total > max_sel:
            return False, f"You can select at most {max_sel} option(s)"
        if custom_values and not self.string_allow_custom:
            return False, "Custom input is not allowed for this parameter"
        predefined_values = [opt.value for opt in self.string_options]
        for cv in custom_values:
            if cv in predefined_values:
                return False, f"'{cv}' is already a predefined option — select it from the list instead"
        if self.string_regex and custom_values:
            pattern = self.string_regex.strip()
            for val in custom_values:
                try:
                    if not _re.fullmatch(pattern, val):
                        return False, f"'{val}' does not match the required format"
                except _re.error:
                    return False, "Invalid regex pattern configured for this parameter"
        return True, None

    def validate_number_value(self, value, is_range_start=False):
        if self.param_type != 'number':
            return True, None
        try:
            num_value = float(value)
        except (ValueError, TypeError):
            return False, f"Invalid number format: {value}"
        if self.is_whole_number:
            if num_value != int(num_value):
                return False, f"Must be a whole number, got {value}"
            num_value = int(num_value)
        else:
            decimal_str = str(value).split('.')
            if len(decimal_str) > 1 and len(decimal_str[1]) > self.number_decimal_places:
                return False, f"Maximum {self.number_decimal_places} decimal places allowed"
        if self.number_min is not None:
            if num_value < self.number_min:
                return False, f"Value must be >= {self.number_min}"
        if self.number_max is not None:
            if num_value > self.number_max:
                return False, f"Value must be <= {self.number_max}"
        if self.number_step and self.number_step > 0:
            base = self.number_min if self.number_min is not None else 0
            if self.is_whole_number:
                if abs((num_value - base) % int(self.number_step)) > 0.0001:
                    return False, f"Value must be a multiple of {int(self.number_step)} from base {int(base)}"
            else:
                remainder = abs((num_value - base) % self.number_step)
                if remainder > 0.0001 and remainder < (self.number_step - 0.0001):
                    return False, f"Value must be a multiple of {self.number_step} from base {base}"
        return True, None
    
    def __repr__(self):
        return f'<MagicParameter {self.name} ({self.param_type})>'


class ParameterUnit(db.Model):
    __tablename__ = 'parameter_units'
    id = db.Column(db.Integer, primary_key=True)
    parameter_id = db.Column(db.Integer, db.ForeignKey('magic_parameters.id'), nullable=False)
    unit = db.Column(db.String(50), nullable=False)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    __table_args__ = (db.UniqueConstraint('parameter_id', 'unit', name='_parameter_unit_uc'),)
    def __repr__(self):
        return f'<ParameterUnit {self.unit}>'


class ParameterStringOption(db.Model):
    __tablename__ = 'parameter_string_options'
    id = db.Column(db.Integer, primary_key=True)
    parameter_id = db.Column(db.Integer, db.ForeignKey('magic_parameters.id'), nullable=False)
    value = db.Column(db.String(128), nullable=False)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    __table_args__ = (db.UniqueConstraint('parameter_id', 'value', name='_parameter_value_uc'),)
    def __repr__(self):
        return f'<ParameterStringOption {self.value}>'


class ItemParameterStringValue(db.Model):
    """Stores selected/custom string values for an ItemParameter (supports multi-select)."""
    __tablename__ = 'item_parameter_string_values'
    id = db.Column(db.Integer, primary_key=True)
    item_parameter_id = db.Column(db.Integer, db.ForeignKey('item_parameters.id'), nullable=False)
    value = db.Column(db.String(128), nullable=False)
    is_custom = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    def __repr__(self):
        return f'<ItemParameterStringValue {self.value} custom={self.is_custom}>'


class ItemParameter(db.Model):
    __tablename__ = 'item_parameters'
    id = db.Column(db.Integer, primary_key=True)
    item_id = db.Column(db.Integer, db.ForeignKey('items.id'), nullable=False)
    parameter_id = db.Column(db.Integer, db.ForeignKey('magic_parameters.id'), nullable=False)
    operation = db.Column(db.String(50))
    value = db.Column(db.String(200))
    value2 = db.Column(db.String(200))
    unit = db.Column(db.String(50))
    string_option = db.Column(db.String(128))
    description = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
    item = db.relationship('Item', backref=db.backref('magic_parameters', cascade='all, delete-orphan', lazy=True))
    string_values = db.relationship('ItemParameterStringValue', backref='item_parameter', lazy=True, cascade='all, delete-orphan')

    def get_selected_string_values(self):
        """Return (predefined_list, custom_list) for string-type parameters."""
        predefined = [sv.value for sv in self.string_values if not sv.is_custom]
        custom = [sv.value for sv in self.string_values if sv.is_custom]
        return predefined, custom

    def get_display_text(self):
        param = self.parameter
        if not param:
            return "Unknown Parameter"
        if param.param_type == 'number':
            if self.operation == 'min':
                return f"MIN: {param.name} {self.value} {self.unit or ''} {self.description or ''}".strip()
            elif self.operation == 'max':
                return f"MAX: {param.name} {self.value} {self.unit or ''} {self.description or ''}".strip()
            elif self.operation == 'range':
                return f"RANGE: {param.name} {self.value} {self.unit or ''} - {self.value2} {self.unit or ''} {self.description or ''}".strip()
            else:
                return f"VALUE: {param.name} {self.value} {self.unit or ''} {self.description or ''}".strip()
        elif param.param_type == 'date':
            if self.operation == 'start':
                return f"START: {param.name} on {self.value} {self.description or ''}".strip()
            elif self.operation == 'end':
                return f"END: {param.name} on {self.value} {self.description or ''}".strip()
            elif self.operation == 'duration':
                return f"DURATION: {param.name} {self.value} to {self.value2} {self.description or ''}".strip()
            else:
                return f"{param.name} on {self.value} {self.description or ''}".strip()
        elif param.param_type == 'string':
            predefined, custom = self.get_selected_string_values()
            parts = []
            if predefined:
                parts.append(', '.join(predefined))
            if custom:
                parts.append(f"Custom: {', '.join(custom)}")
            if parts:
                return f"{param.name}: {' | '.join(parts)} {self.description or ''}".strip()
            if self.string_option:
                return f"{param.name}: {self.string_option} {self.description or ''}".strip()
            return f"{param.name}: (none selected) {self.description or ''}".strip()
        return "Invalid Parameter"

    def check_notification(self):
        if self.parameter.param_type == 'date' and self.parameter.notify_enabled:
            from datetime import datetime
            try:
                if self.operation in ['value', 'start', 'end']:
                    param_date = datetime.strptime(self.value, '%Y-%m-%d')
                    today = datetime.now().date()
                    if param_date.date() == today:
                        return True
                elif self.operation == 'duration':
                    start_date = datetime.strptime(self.value, '%Y-%m-%d')
                    end_date = datetime.strptime(self.value2, '%Y-%m-%d')
                    today = datetime.now().date()
                    if start_date.date() <= today <= end_date.date():
                        return True
            except (ValueError, TypeError):
                pass
        return False
    
    def __repr__(self):
        return f'<ItemParameter {self.id} for Item {self.item_id}>'


class ParameterTemplate(db.Model):
    __tablename__ = 'parameter_templates'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), unique=True, nullable=False)
    description = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
    template_parameters = db.relationship('TemplateParameter', backref='template', lazy=True, cascade='all, delete-orphan')
    def __repr__(self):
        return f'<ParameterTemplate {self.name}>'


class TemplateParameter(db.Model):
    __tablename__ = 'template_parameters'
    id = db.Column(db.Integer, primary_key=True)
    template_id = db.Column(db.Integer, db.ForeignKey('parameter_templates.id'), nullable=False)
    parameter_id = db.Column(db.Integer, db.ForeignKey('magic_parameters.id'), nullable=False)
    operation = db.Column(db.String(50))
    value = db.Column(db.String(200))
    value2 = db.Column(db.String(200))
    unit = db.Column(db.String(50))
    string_option = db.Column(db.String(200))
    description = db.Column(db.Text)
    display_order = db.Column(db.Integer, default=0)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    parameter = db.relationship('MagicParameter', backref='template_uses', lazy=True)
    
    def get_display_text(self):
        param = self.parameter
        if not param:
            return "Unknown Parameter"
        if param.param_type == 'number':
            if self.operation == 'min':
                return f"MIN: {param.name} {self.value} {self.unit or ''} {self.description or ''}".strip()
            elif self.operation == 'max':
                return f"MAX: {param.name} {self.value} {self.unit or ''} {self.description or ''}".strip()
            elif self.operation == 'range':
                return f"RANGE: {param.name} {self.value} {self.unit or ''} - {self.value2} {self.unit or ''} {self.description or ''}".strip()
            else:
                return f"VALUE: {param.name} {self.value} {self.unit or ''} {self.description or ''}".strip()
        elif param.param_type == 'date':
            if self.operation == 'start':
                return f"START: {param.name} on {self.value} {self.description or ''}".strip()
            elif self.operation == 'end':
                return f"END: {param.name} on {self.value} {self.description or ''}".strip()
            elif self.operation == 'duration':
                return f"DURATION: {param.name} {self.value} to {self.value2} {self.description or ''}".strip()
            else:
                return f"{param.name} on {self.value} {self.description or ''}".strip()
        elif param.param_type == 'string':
            return f"{param.name}: {self.string_option} {self.description or ''}".strip()
        return "Invalid Parameter"
    
    def __repr__(self):
        return f'<TemplateParameter {self.id} for Template {self.template_id}>'


class StickerTemplate(db.Model):
    __tablename__ = 'sticker_templates'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    template_type = db.Column(db.String(20), nullable=False)
    width_mm = db.Column(db.Float, nullable=False)
    height_mm = db.Column(db.Float, nullable=False)
    layout = db.Column(db.Text, nullable=False)
    is_default = db.Column(db.Boolean, default=False)
    created_by = db.Column(db.Integer, db.ForeignKey('users.id'))
    updated_by = db.Column(db.Integer, db.ForeignKey('users.id'))
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
    creator = db.relationship('User', backref='sticker_templates', foreign_keys=[created_by])
    updater = db.relationship('User', foreign_keys=[updated_by])
    
    def get_layout(self):
        try:
            return json.loads(self.layout) if self.layout else []
        except json.JSONDecodeError:
            return []
    
    def set_layout(self, layout_data):
        self.layout = json.dumps(layout_data)
    
    def __repr__(self):
        return f'<StickerTemplate {self.name} - {self.template_type}>'


# ==================== PROJECT MODELS ====================

class ProjectCategory(db.Model):
    __tablename__ = 'project_categories'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), unique=True, nullable=False)
    description = db.Column(db.Text)
    color = db.Column(db.String(7), default='#6c757d')
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

class ProjectTag(db.Model):
    __tablename__ = 'project_tags'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), unique=True, nullable=False)
    description = db.Column(db.Text)
    color = db.Column(db.String(7), default='#6c757d')
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

class ProjectStatus(db.Model):
    __tablename__ = 'project_statuses'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), unique=True, nullable=False)
    color = db.Column(db.String(7), default='#6c757d')
    description = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

class ProjectPerson(db.Model):
    __tablename__ = 'project_persons'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), nullable=False)
    email = db.Column(db.String(200))
    organization = db.Column(db.String(200))
    tel = db.Column(db.String(50))
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

class ProjectGroup(db.Model):
    __tablename__ = 'project_groups'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), unique=True, nullable=False)
    description = db.Column(db.Text)
    color = db.Column(db.String(7), default='#6c757d')
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
    members = db.relationship('ProjectGroupMember', backref='group', lazy=True, cascade='all, delete-orphan')
    def get_users(self):
        return [m for m in self.members if m.user_id is not None]
    def get_persons(self):
        return [m for m in self.members if m.person_id is not None]

class ProjectGroupMember(db.Model):
    __tablename__ = 'project_group_members'
    id = db.Column(db.Integer, primary_key=True)
    group_id = db.Column(db.Integer, db.ForeignKey('project_groups.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    person_id = db.Column(db.Integer, db.ForeignKey('project_persons.id'), nullable=True)
    user = db.relationship('User', backref='project_group_memberships')
    person = db.relationship('ProjectPerson', backref='group_memberships')


# ==================== CONTACTS MODELS ====================

class ContactOrganization(db.Model):
    __tablename__ = 'contact_organizations'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), nullable=False)
    email = db.Column(db.String(200))
    tel = db.Column(db.String(50))
    url = db.Column(db.String(500))
    address = db.Column(db.String(256))
    zip_code = db.Column(db.String(20))
    info = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
    persons = db.relationship('ContactPerson', backref='organization', lazy=True)

class ContactPerson(db.Model):
    __tablename__ = 'contact_persons'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), nullable=False)
    email = db.Column(db.String(200))
    tel = db.Column(db.String(50))
    organization_id = db.Column(db.Integer, db.ForeignKey('contact_organizations.id'), nullable=True)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

class ContactGroup(db.Model):
    __tablename__ = 'contact_groups'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), unique=True, nullable=False)
    description = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
    members = db.relationship('ContactGroupMember', backref='group', lazy=True, cascade='all, delete-orphan')
    def get_users(self):
        return [m for m in self.members if m.user_id is not None]
    def get_persons(self):
        return [m for m in self.members if m.person_id is not None]
    def get_organizations(self):
        return [m for m in self.members if m.organization_id is not None]

class ContactGroupMember(db.Model):
    __tablename__ = 'contact_group_members'
    id = db.Column(db.Integer, primary_key=True)
    group_id = db.Column(db.Integer, db.ForeignKey('contact_groups.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    person_id = db.Column(db.Integer, db.ForeignKey('contact_persons.id'), nullable=True)
    organization_id = db.Column(db.Integer, db.ForeignKey('contact_organizations.id'), nullable=True)
    user = db.relationship('User', backref='contact_group_memberships')
    person = db.relationship('ContactPerson', backref='group_memberships')
    org = db.relationship('ContactOrganization', backref='group_memberships')

class Project(db.Model):
    __tablename__ = 'projects'
    id = db.Column(db.Integer, primary_key=True)
    project_id = db.Column(db.String(12), unique=True, nullable=False)
    name = db.Column(db.String(300), nullable=False)
    info = db.Column(db.String(500))
    description = db.Column(db.Text)
    category_id = db.Column(db.Integer, db.ForeignKey('project_categories.id'))
    tags = db.Column(db.Text)
    status_id = db.Column(db.Integer, db.ForeignKey('project_statuses.id'))
    date_start = db.Column(db.Date)
    date_end = db.Column(db.Date)
    quantity = db.Column(db.Integer, default=1)
    users = db.Column(db.Text)
    persons = db.Column(db.Text)
    organizations = db.Column(db.Text)
    enable_dateline_notification = db.Column(db.Boolean, default=False)
    notify_before_days = db.Column(db.Integer, default=3)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
    created_by = db.Column(db.Integer, db.ForeignKey('users.id'))
    updated_by = db.Column(db.Integer, db.ForeignKey('users.id'))
    category = db.relationship('ProjectCategory', backref='projects')
    status = db.relationship('ProjectStatus', backref='projects')
    creator = db.relationship('User', foreign_keys=[created_by], backref='projects_created')
    updater = db.relationship('User', foreign_keys=[updated_by], backref='projects_updated')
    bom_items = db.relationship('ProjectBOMItem', backref='project', lazy=True, cascade='all, delete-orphan')
    attachments = db.relationship('ProjectAttachment', backref='project', lazy=True, cascade='all, delete-orphan')
    urls = db.relationship('ProjectURL', backref='project', lazy=True, cascade='all, delete-orphan')
    linked_share_files = db.relationship('SharedFile', secondary=project_share_files, lazy='subquery', backref=db.backref('linked_projects', lazy=True))
    def __init__(self, **kwargs):
        super(Project, self).__init__(**kwargs)
        if not self.project_id:
            chars = string.ascii_uppercase + string.digits
            self.project_id = ''.join(secrets.choice(chars) for _ in range(11)) + 'P'
    def get_tags_list(self):
        if not self.tags: return []
        try:
            tag_ids = json.loads(self.tags)
            return ProjectTag.query.filter(ProjectTag.id.in_(tag_ids)).all()
        except (json.JSONDecodeError, TypeError): return []
    def get_users_list(self):
        if not self.users: return []
        try:
            user_ids = json.loads(self.users)
            return User.query.filter(User.id.in_(user_ids)).all()
        except (json.JSONDecodeError, TypeError): return []
    def get_persons_list(self):
        if not self.persons: return []
        try:
            ids = json.loads(self.persons)
            return ContactPerson.query.filter(ContactPerson.id.in_(ids)).all()
        except (json.JSONDecodeError, TypeError): return []
    def get_organizations_list(self):
        if not self.organizations: return []
        try:
            ids = json.loads(self.organizations)
            return ContactOrganization.query.filter(ContactOrganization.id.in_(ids)).all()
        except (json.JSONDecodeError, TypeError): return []
    def get_bom_total_cost(self):
        """Estimated BOM cost based on required_quantity"""
        return sum(b.get_total_cost() for b in self.bom_items)
    def get_bom_actual_cost(self):
        """Actual BOM cost based on used_quantity"""
        return sum(b.get_actual_cost() for b in self.bom_items)
    def get_project_total_cost(self):
        return self.get_bom_total_cost() * (self.quantity or 1)
    def get_project_actual_cost(self):
        return self.get_bom_actual_cost() * (self.quantity or 1)

class ProjectBOMItem(db.Model):
    __tablename__ = 'project_bom_items'
    id = db.Column(db.Integer, primary_key=True)
    project_id = db.Column(db.Integer, db.ForeignKey('projects.id'), nullable=False)
    item_id = db.Column(db.Integer, db.ForeignKey('items.id'), nullable=True)
    batch_id = db.Column(db.Integer, db.ForeignKey('item_batches.id'), nullable=True)
    quantity = db.Column(db.Integer, default=1)
    used_quantity = db.Column(db.Integer, default=0)
    serial_numbers = db.Column(db.Text)
    item_name_snapshot = db.Column(db.String(300))
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
    item = db.relationship('Item', backref=db.backref('bom_uses'))
    batch = db.relationship('ItemBatch', backref='bom_uses')
    @property
    def item_display_name(self):
        if self.item:
            return self.item.name
        return self.item_name_snapshot or 'Deleted Item'
    def get_serial_numbers_list(self):
        if not self.serial_numbers: return []
        try:
            sn_ids = json.loads(self.serial_numbers)
            return BatchSerialNumber.query.filter(BatchSerialNumber.id.in_(sn_ids)).all()
        except (json.JSONDecodeError, TypeError): return []
    def get_cost_per_unit(self):
        return self.batch.price_per_unit if self.batch and self.batch.price_per_unit else 0.0
    def get_total_cost(self):
        """Estimated cost based on required quantity"""
        return self.get_cost_per_unit() * (self.quantity or 0)
    def get_actual_cost(self):
        """Actual cost based on used quantity"""
        return self.get_cost_per_unit() * (self.used_quantity or 0)

class ProjectAttachment(db.Model):
    __tablename__ = 'project_attachments'
    id = db.Column(db.Integer, primary_key=True)
    project_id = db.Column(db.Integer, db.ForeignKey('projects.id'), nullable=False)
    filename = db.Column(db.String(255), nullable=False)
    original_filename = db.Column(db.String(255), nullable=False)
    file_path = db.Column(db.String(500), nullable=False)
    file_type = db.Column(db.String(50))
    file_size = db.Column(db.Integer)
    attachment_type = db.Column(db.String(50), default='document')
    uploaded_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    uploaded_by = db.Column(db.Integer, db.ForeignKey('users.id'))

class ProjectURL(db.Model):
    __tablename__ = 'project_urls'
    id = db.Column(db.Integer, primary_key=True)
    project_id = db.Column(db.Integer, db.ForeignKey('projects.id'), nullable=False)
    url = db.Column(db.String(1000), nullable=False)
    title = db.Column(db.String(300))
    description = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))


class SharedFile(db.Model):
    __tablename__ = 'shared_files'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), nullable=False)
    filename = db.Column(db.String(255), nullable=False)
    category = db.Column(db.String(20), nullable=False)  # item, profile, project, sticker
    file_size = db.Column(db.Integer, default=0)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    uploaded_by_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    uploader = db.relationship('User', backref='shared_files', foreign_keys=[uploaded_by_id])

    def size_display(self):
        """Human-readable file size."""
        b = self.file_size or 0
        for unit in ('B', 'KB', 'MB', 'GB'):
            if b < 1024:
                return f"{b:.1f} {unit}" if unit != 'B' else f"{b} B"
            b /= 1024
        return f"{b:.1f} TB"

    @property
    def ext(self):
        return self.filename.rsplit('.', 1)[1].lower() if '.' in self.filename else ''

    @property
    def is_image(self):
        return self.ext in {'png', 'jpg', 'jpeg', 'gif', 'webp', 'svg'}
