from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime, timezone
import json
import secrets
import string

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
        """Get setting value by key"""
        setting = Setting.query.filter_by(key=key).first()
        if setting:
            # Convert string to boolean for boolean settings
            if setting.value in ['true', 'false']:
                return setting.value == 'true'
            return setting.value
        return default
    
    @staticmethod
    def set(key, value, description=None):
        """Set setting value"""
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
    name = db.Column(db.String(100), unique=True, nullable=False)
    info = db.Column(db.String(500))
    description = db.Column(db.Text)
    picture = db.Column(db.String(200))  # filename
    color = db.Column(db.String(7), default='#6c757d')  # hex color
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
    
    # Relationships
    racks = db.relationship('Rack', backref='physical_location', lazy=True, foreign_keys='Rack.location_id')
    items = db.relationship('Item', backref='general_location', lazy=True, foreign_keys='Item.location_id')
    
    def __repr__(self):
        return f'<Location {self.name}>'


class User(UserMixin, db.Model):
    __tablename__ = 'users'
    
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(20), nullable=False, default='viewer')
    theme = db.Column(db.String(20), default='light')
    table_columns_view = db.Column(db.Text, default='["name", "category", "tags", "quantity", "total_price", "location", "status"]')  # JSON array of column names
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    is_active = db.Column(db.Boolean, default=True)
    
    def set_password(self, password):
        self.password_hash = generate_password_hash(password)
    
    def check_password(self, password):
        return check_password_hash(self.password_hash, password)
    
    def is_admin(self):
        return self.role == 'admin'
    
    def is_editor(self):
        return self.role in ['admin', 'editor']
    
    def get_table_columns(self):
        """Get user's preferred table columns as list"""
        try:
            return json.loads(self.table_columns_view)
        except (json.JSONDecodeError, TypeError):
            return ["name", "category", "tags", "quantity", "total_price", "location", "status"]
    
    def set_table_columns(self, columns):
        """Set user's preferred table columns"""
        self.table_columns_view = json.dumps(columns)
    
    def __repr__(self):
        return f'<User {self.username}>'


class Category(db.Model):
    __tablename__ = 'categories'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), unique=True, nullable=False)
    description = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    
    items = db.relationship('Item', backref='category', lazy=True)
    
    def __repr__(self):
        return f'<Category {self.name}>'


class Footprint(db.Model):
    __tablename__ = 'footprints'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), unique=True, nullable=False)
    description = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    
    items = db.relationship('Item', backref='footprint', lazy=True)
    
    def __repr__(self):
        return f'<Footprint {self.name}>'


class Tag(db.Model):
    __tablename__ = 'tags'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), unique=True, nullable=False)
    color = db.Column(db.String(7), default='#6c757d')
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    
    def __repr__(self):
        return f'<Tag {self.name}>'


class Rack(db.Model):
    __tablename__ = 'racks'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), unique=True, nullable=False)
    description = db.Column(db.Text)
    location_id = db.Column(db.Integer, db.ForeignKey('locations.id'), nullable=True)
    picture = db.Column(db.String(200))  # filename
    color = db.Column(db.String(7), default='#6c757d')  # hex color
    rows = db.Column(db.Integer, default=5)
    cols = db.Column(db.Integer, default=5)
    unavailable_drawers = db.Column(db.Text)  # JSON array of unavailable drawer IDs like ["R1-C1", "R2-C3"]
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
    
    items = db.relationship('Item', backref='rack', lazy=True)
    
    def get_unavailable_drawers(self):
        """Get list of unavailable drawer IDs"""
        if not self.unavailable_drawers:
            return []
        try:
            return json.loads(self.unavailable_drawers)
        except (json.JSONDecodeError, TypeError):
            return []
    
    def is_drawer_unavailable(self, drawer_id):
        """Check if a drawer is marked as unavailable"""
        return drawer_id in self.get_unavailable_drawers()
    
    def __repr__(self):
        return f'<Rack {self.name}>'


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
    
    lend_to = db.Column(db.String(200))
    lend_quantity = db.Column(db.Integer, default=0)
    datasheet_urls = db.Column(db.Text)
    no_stock_warning = db.Column(db.Boolean, default=True)
    
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
    created_by = db.Column(db.Integer, db.ForeignKey('users.id'))
    updated_by = db.Column(db.Integer, db.ForeignKey('users.id'))
    
    creator = db.relationship('User', foreign_keys=[created_by], backref='items_created')
    updater = db.relationship('User', foreign_keys=[updated_by], backref='items_updated')
    
    attachments = db.relationship('Attachment', backref='item', lazy=True, cascade='all, delete-orphan')
    
    def __init__(self, **kwargs):
        super(Item, self).__init__(**kwargs)
        if not self.uuid:
            chars = string.ascii_uppercase + string.digits
            self.uuid = ''.join(secrets.choice(chars) for _ in range(12))
    
    def get_full_location(self):
        if self.rack_id and self.drawer:
            rack_location = self.rack.physical_location.name if self.rack and self.rack.physical_location else ''
            return f"{self.rack.name} - {self.drawer}" + (f" ({rack_location})" if rack_location else "")
        elif self.location_id and self.general_location:
            return self.general_location.name
        return 'Not specified'
    
    def get_available_quantity(self):
        return self.quantity - (self.lend_quantity or 0)
    
    def is_low_stock(self):
        return self.get_available_quantity() <= self.min_quantity
    
    def is_no_stock(self):
        return self.no_stock_warning and self.quantity == 0
    
    def get_total_price(self):
        """Calculate total price (price per qty * quantity)"""
        return self.price * self.quantity if self.price else 0.0
    
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
    
    def __repr__(self):
        return f'<Item {self.name}>'


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


# Magic Parameter Models
class MagicParameter(db.Model):
    __tablename__ = 'magic_parameters'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), unique=True, nullable=False)
    param_type = db.Column(db.String(50), nullable=False)  # 'number', 'date', 'string'
    description = db.Column(db.Text)
    notify_enabled = db.Column(db.Boolean, default=False)  # For date type
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
    
    # Relationships
    units = db.relationship('ParameterUnit', backref='parameter', lazy=True, cascade='all, delete-orphan')
    string_options = db.relationship('ParameterStringOption', backref='parameter', lazy=True, cascade='all, delete-orphan')
    item_parameters = db.relationship('ItemParameter', backref='parameter', lazy=True, cascade='all, delete-orphan')
    
    def get_units_list(self):
        """Get list of units for number type parameters"""
        if self.param_type == 'number':
            return [unit.unit for unit in self.units]
        return []
    
    def get_string_options_list(self):
        """Get list of string options for string type parameters"""
        if self.param_type == 'string':
            return [option.value for option in self.string_options]
        return []
    
    def __repr__(self):
        return f'<MagicParameter {self.name} ({self.param_type})>'


class ParameterUnit(db.Model):
    __tablename__ = 'parameter_units'
    
    id = db.Column(db.Integer, primary_key=True)
    parameter_id = db.Column(db.Integer, db.ForeignKey('magic_parameters.id'), nullable=False)
    unit = db.Column(db.String(50), nullable=False)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    
    # Unique constraint for parameter_id and unit combination
    __table_args__ = (db.UniqueConstraint('parameter_id', 'unit', name='_parameter_unit_uc'),)
    
    def __repr__(self):
        return f'<ParameterUnit {self.unit}>'


class ParameterStringOption(db.Model):
    __tablename__ = 'parameter_string_options'
    
    id = db.Column(db.Integer, primary_key=True)
    parameter_id = db.Column(db.Integer, db.ForeignKey('magic_parameters.id'), nullable=False)
    value = db.Column(db.String(200), nullable=False)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    
    # Unique constraint for parameter_id and value combination
    __table_args__ = (db.UniqueConstraint('parameter_id', 'value', name='_parameter_value_uc'),)
    
    def __repr__(self):
        return f'<ParameterStringOption {self.value}>'


class ItemParameter(db.Model):
    __tablename__ = 'item_parameters'
    
    id = db.Column(db.Integer, primary_key=True)
    item_id = db.Column(db.Integer, db.ForeignKey('items.id'), nullable=False)
    parameter_id = db.Column(db.Integer, db.ForeignKey('magic_parameters.id'), nullable=False)
    operation = db.Column(db.String(50))  # 'min', 'max', 'value', 'range', 'start', 'end', 'duration'
    value = db.Column(db.String(200))  # For single values
    value2 = db.Column(db.String(200))  # For range/duration second value
    unit = db.Column(db.String(50))  # Unit for number type
    string_option = db.Column(db.String(200))  # Selected option for string type
    description = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
    
    # Relationship
    item = db.relationship('Item', backref='magic_parameters', lazy=True)
    
    def get_display_text(self):
        """Generate display text for the parameter"""
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
            else:  # value
                return f"VALUE: {param.name} {self.value} {self.unit or ''} {self.description or ''}".strip()
        
        elif param.param_type == 'date':
            if self.operation == 'start':
                return f"START: {param.name} on {self.value} {self.description or ''}".strip()
            elif self.operation == 'end':
                return f"END: {param.name} on {self.value} {self.description or ''}".strip()
            elif self.operation == 'duration':
                return f"DURATION: {param.name} {self.value} to {self.value2} {self.description or ''}".strip()
            else:  # value
                return f"{param.name} on {self.value} {self.description or ''}".strip()
        
        elif param.param_type == 'string':
            return f"{param.name}: {self.string_option} {self.description or ''}".strip()
        
        return "Invalid Parameter"
    
    def check_notification(self):
        """Check if this parameter should trigger a notification (for date type)"""
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
    
    # Relationships
    template_parameters = db.relationship('TemplateParameter', backref='template', lazy=True, cascade='all, delete-orphan')
    
    def __repr__(self):
        return f'<ParameterTemplate {self.name}>'


class TemplateParameter(db.Model):
    __tablename__ = 'template_parameters'
    
    id = db.Column(db.Integer, primary_key=True)
    template_id = db.Column(db.Integer, db.ForeignKey('parameter_templates.id'), nullable=False)
    parameter_id = db.Column(db.Integer, db.ForeignKey('magic_parameters.id'), nullable=False)
    operation = db.Column(db.String(50))  # 'min', 'max', 'value', 'range', 'start', 'end', 'duration'
    value = db.Column(db.String(200))  # For single values
    value2 = db.Column(db.String(200))  # For range/duration second value
    unit = db.Column(db.String(50))  # Unit for number type
    string_option = db.Column(db.String(200))  # Selected option for string type
    description = db.Column(db.Text)
    display_order = db.Column(db.Integer, default=0)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    
    # Relationship
    parameter = db.relationship('MagicParameter', backref='template_uses', lazy=True)
    
    def get_display_text(self):
        """Generate display text for the template parameter"""
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
            else:  # value
                return f"VALUE: {param.name} {self.value} {self.unit or ''} {self.description or ''}".strip()
        
        elif param.param_type == 'date':
            if self.operation == 'start':
                return f"START: {param.name} on {self.value} {self.description or ''}".strip()
            elif self.operation == 'end':
                return f"END: {param.name} on {self.value} {self.description or ''}".strip()
            elif self.operation == 'duration':
                return f"DURATION: {param.name} {self.value} to {self.value2} {self.description or ''}".strip()
            else:  # value
                return f"{param.name} on {self.value} {self.description or ''}".strip()
        
        elif param.param_type == 'string':
            return f"{param.name}: {self.string_option} {self.description or ''}".strip()
        
        return "Invalid Parameter"
    
    def __repr__(self):
        return f'<TemplateParameter {self.id} for Template {self.template_id}>'
