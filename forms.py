from flask_wtf import FlaskForm
from flask_wtf.file import FileField, FileAllowed, FileRequired
from wtforms import StringField, PasswordField, TextAreaField, IntegerField, FloatField, SelectField, SubmitField, BooleanField, MultipleFileField, HiddenField, DateField
from wtforms.validators import DataRequired, Email, EqualTo, Length, Optional, ValidationError, NumberRange
from models import User, Category


class LocationForm(FlaskForm):
    name = StringField('Location Name', validators=[DataRequired(), Length(max=100)])
    info = StringField('Info (Short)', validators=[Optional(), Length(max=500)])
    description = TextAreaField('Description', validators=[Optional()])
    color = StringField('Color', validators=[Optional(), Length(max=7)], default='#6c757d')
    picture = FileField('Picture', validators=[Optional(), FileAllowed(['png', 'jpg', 'jpeg'], 'PNG and JPEG only!')])
    submit = SubmitField('Save Location')


class LoginForm(FlaskForm):
    username = StringField('Username', validators=[DataRequired()])
    password = PasswordField('Password', validators=[DataRequired()])
    remember_me = BooleanField('Remember Me')
    submit = SubmitField('Login')


class RegistrationForm(FlaskForm):
    username = StringField('Username', validators=[DataRequired(), Length(min=3, max=80)])
    email = StringField('Email', validators=[DataRequired(), Email()])
    password = PasswordField('Password', validators=[DataRequired(), Length(min=6)])
    password2 = PasswordField('Confirm Password', validators=[DataRequired(), EqualTo('password')])
    submit = SubmitField('Register')
    
    def validate_username(self, username):
        user = User.query.filter_by(username=username.data).first()
        if user:
            raise ValidationError('Username already exists.')
    
    def validate_email(self, email):
        user = User.query.filter_by(email=email.data).first()
        if user:
            raise ValidationError('Email already registered.')


class UserForm(FlaskForm):
    # --- Basic Section ---
    username = StringField('Username', validators=[DataRequired(), Length(min=3, max=80)])
    email = StringField('Email', validators=[DataRequired(), Email()])
    password = PasswordField('Password', validators=[Optional(), Length(min=6)])
    role_id = SelectField('Roles', coerce=int, validators=[DataRequired()])
    is_active = BooleanField('Active')
    
    # --- Security Section ---
    allow_password_reset = BooleanField('Allow User to Reset Password', default=True)
    allow_profile_picture_change = BooleanField('Allow User to change Profile Picture', default=True)
    max_login_attempts = IntegerField('Max Login Attempt', validators=[Optional(), NumberRange(min=0)], default=0)
    auto_unlock_enabled = BooleanField('Unlock after Time', default=True)
    auto_unlock_minutes = SelectField('Unlock After', coerce=int, choices=[
        (1, '1 minute'),
        (5, '5 minutes'),
        (15, '15 minutes'),
        (30, '30 minutes'),
        (60, '1 hour'),
        (360, '6 hours'),
        (720, '12 hours'),
        (1440, '1 day'),
        (4320, '3 days'),
        (10080, '1 week')
    ], default=15)
    
    # --- Other ---
    profile_photo = FileField('Profile Photo (Max 1MB, JPEG/PNG)', validators=[Optional()])
    submit = SubmitField('Save User')
    
    def __init__(self, *args, **kwargs):
        super(UserForm, self).__init__(*args, **kwargs)
        from models import Role
        self.role_id.choices = [(r.id, r.name) for r in Role.query.order_by(Role.name).all()]


class CategoryForm(FlaskForm):
    name = StringField('Category Name', validators=[DataRequired(), Length(max=100)])
    description = TextAreaField('Description', validators=[Optional()])
    color = StringField('Color', validators=[Optional(), Length(max=7)], render_kw={"type": "color", "value": "#6c757d"}, default='#6c757d')
    submit = SubmitField('Save Category')


class ItemAddForm(FlaskForm):
    """Form for adding new items"""
    name = StringField('Item Name', validators=[DataRequired(), Length(max=200)], render_kw={"class": "form-control form-control-sm"})
    sku = StringField('SKU', validators=[Optional(), Length(max=100)], render_kw={"class": "form-control form-control-sm"})
    info = StringField('Type / Model', validators=[Optional(), Length(max=500)], render_kw={"class": "form-control form-control-sm"})
    description = TextAreaField('Description', validators=[Optional()], render_kw={"class": "form-control form-control-sm", "rows": "4"})
    quantity = IntegerField('Quantity', validators=[NumberRange(min=0)], default=0, render_kw={"class": "form-control form-control-sm"})
    price = FloatField('Price per Qty', validators=[Optional(), NumberRange(min=0)], render_kw={"class": "form-control form-control-sm", "placeholder": "0.00"})
    
    location_id = SelectField('General Location', coerce=int, validators=[Optional()], render_kw={"class": "form-select form-select-sm"})
    rack_id = SelectField('Rack', coerce=int, validators=[Optional()], render_kw={"class": "form-select form-select-sm"})
    drawer = StringField('Drawer', validators=[Optional(), Length(max=50)], render_kw={"class": "form-control form-control-sm"})
    
    min_quantity = IntegerField('Minimum Quantity', validators=[Optional(), NumberRange(min=0)], default=0, render_kw={"class": "form-control form-control-sm"})
    category_id = SelectField('Category', coerce=int, validators=[Optional()], render_kw={"class": "form-select form-select-sm"})
    footprint_id = SelectField('Footprint', coerce=int, validators=[Optional()], render_kw={"class": "form-select form-select-sm"})
    
    lend_to = StringField('Lend To', validators=[Optional(), Length(max=200)], render_kw={"class": "form-control form-control-sm"})
    lend_quantity = IntegerField('Lend Quantity', validators=[Optional(), NumberRange(min=0)], default=0, render_kw={"class": "form-control form-control-sm"})
    no_stock_warning = BooleanField('No Stock Warning', default=True)
    datasheet_urls = TextAreaField('Datasheet URLs', validators=[Optional()], render_kw={"class": "form-control form-control-sm"})
    
    submit = SubmitField('Create Item')
    
    def __init__(self, *args, perms=None, **kwargs):
        super(ItemAddForm, self).__init__(*args, **kwargs)
        from models import Rack, Footprint, Location
        self.category_id.choices = [(0, '-- Select Category --')] + [(c.id, c.name) for c in Category.query.order_by(Category.name).all()]
        self.location_id.choices = [(0, '-- Select General Location --')] + [(l.id, l.name) for l in Location.query.order_by(Location.name).all()]
        self.rack_id.choices = [(0, '-- Select Rack --')] + [(r.id, r.name) for r in Rack.query.order_by(Rack.name).all()]
        self.footprint_id.choices = [(0, '-- Select Footprint --')] + [(f.id, f.name) for f in Footprint.query.order_by(Footprint.name).all()]
        
        # Apply permission-based field disabling
        if perms and not perms.get('is_admin'):
            self._apply_field_permissions(perms)
    
    def _apply_field_permissions(self, perms):
        """Mark fields user doesn't have permission to edit - don't disable to allow data to be sent"""
        field_perms = {
            'name': 'can_edit_name',
            'sku': 'can_edit_sku_type',
            'info': 'can_edit_sku_type',
            'description': 'can_edit_description',
            'datasheet_urls': 'can_edit_datasheet',
            'lend_to': 'can_edit_lending',
            'lend_quantity': 'can_edit_lending',
            'price': 'can_edit_price',
            'quantity': 'can_edit_quantity',
            'min_quantity': 'can_edit_quantity',
            'no_stock_warning': 'can_edit_quantity',
            'location_id': 'can_edit_location',
            'rack_id': 'can_edit_location',
            'drawer': 'can_edit_location',
            'category_id': 'can_edit_category',
            'footprint_id': 'can_edit_footprint',
        }
        
        for field_name, perm_name in field_perms.items():
            if field_name in self._fields:
                field = self._fields[field_name]
                has_perm = perms.get(perm_name, False)
                if not has_perm:
                    # Add readonly or data attribute for CSS targeting, but don't disable
                    field.render_kw = field.render_kw or {}
                    field.render_kw['readonly'] = True if field_name not in ['location_id', 'rack_id', 'category_id', 'footprint_id'] else False
                    field.render_kw['data-restricted'] = 'true'


class ItemEditForm(FlaskForm):
    """Form for editing existing items"""
    name = StringField('Item Name', validators=[DataRequired(), Length(max=200)], render_kw={"class": "form-control form-control-sm"})
    sku = StringField('SKU', validators=[Optional(), Length(max=100)], render_kw={"class": "form-control form-control-sm"})
    info = StringField('Type / Model', validators=[Optional(), Length(max=500)], render_kw={"class": "form-control form-control-sm"})
    description = TextAreaField('Description', validators=[Optional()], render_kw={"class": "form-control form-control-sm", "rows": "4"})
    quantity = IntegerField('Quantity', validators=[NumberRange(min=0)], default=0, render_kw={"class": "form-control form-control-sm"})
    price = FloatField('Price per Qty', validators=[Optional(), NumberRange(min=0)], render_kw={"class": "form-control form-control-sm", "placeholder": "0.00"})
    
    location_id = SelectField('General Location', coerce=int, validators=[Optional()], render_kw={"class": "form-select form-select-sm"})
    rack_id = SelectField('Rack', coerce=int, validators=[Optional()], render_kw={"class": "form-select form-select-sm"})
    drawer = StringField('Drawer', validators=[Optional(), Length(max=50)], render_kw={"class": "form-control form-control-sm"})
    
    min_quantity = IntegerField('Minimum Quantity', validators=[Optional(), NumberRange(min=0)], default=0, render_kw={"class": "form-control form-control-sm"})
    category_id = SelectField('Category', coerce=int, validators=[Optional()], render_kw={"class": "form-select form-select-sm"})
    footprint_id = SelectField('Footprint', coerce=int, validators=[Optional()], render_kw={"class": "form-select form-select-sm"})
    
    lend_to = StringField('Lend To', validators=[Optional(), Length(max=200)], render_kw={"class": "form-control form-control-sm"})
    lend_quantity = IntegerField('Lend Quantity', validators=[Optional(), NumberRange(min=0)], default=0, render_kw={"class": "form-control form-control-sm"})
    no_stock_warning = BooleanField('No Stock Warning', default=True)
    datasheet_urls = TextAreaField('Datasheet URLs', validators=[Optional()], render_kw={"class": "form-control form-control-sm"})
    
    submit = SubmitField('Update Item')
    
    def __init__(self, *args, perms=None, **kwargs):
        super(ItemEditForm, self).__init__(*args, **kwargs)
        from models import Rack, Footprint, Location
        self.category_id.choices = [(0, '-- Select Category --')] + [(c.id, c.name) for c in Category.query.order_by(Category.name).all()]
        self.location_id.choices = [(0, '-- Select General Location --')] + [(l.id, l.name) for l in Location.query.order_by(Location.name).all()]
        self.rack_id.choices = [(0, '-- Select Rack --')] + [(r.id, r.name) for r in Rack.query.order_by(Rack.name).all()]
        self.footprint_id.choices = [(0, '-- Select Footprint --')] + [(f.id, f.name) for f in Footprint.query.order_by(Footprint.name).all()]
        
        # Apply permission-based field disabling
        if perms and not perms.get('is_admin'):
            self._apply_field_permissions(perms)
    
    def _apply_field_permissions(self, perms):
        """Mark fields user doesn't have permission to edit - don't disable to allow data to be sent"""
        field_perms = {
            'name': 'can_edit_name',
            'sku': 'can_edit_sku_type',
            'info': 'can_edit_sku_type',
            'description': 'can_edit_description',
            'datasheet_urls': 'can_edit_datasheet',
            'lend_to': 'can_edit_lending',
            'lend_quantity': 'can_edit_lending',
            'price': 'can_edit_price',
            'quantity': 'can_edit_quantity',
            'min_quantity': 'can_edit_quantity',
            'no_stock_warning': 'can_edit_quantity',
            'location_id': 'can_edit_location',
            'rack_id': 'can_edit_location',
            'drawer': 'can_edit_location',
            'category_id': 'can_edit_category',
            'footprint_id': 'can_edit_footprint',
        }
        
        for field_name, perm_name in field_perms.items():
            if field_name in self._fields:
                field = self._fields[field_name]
                has_perm = perms.get(perm_name, False)
                if not has_perm:
                    # Add readonly or data attribute for CSS targeting, but don't disable
                    field.render_kw = field.render_kw or {}
                    field.render_kw['readonly'] = True if field_name not in ['location_id', 'rack_id', 'category_id', 'footprint_id'] else False
                    field.render_kw['data-restricted'] = 'true'


class AttachmentForm(FlaskForm):
    files = MultipleFileField('Upload Files', validators=[FileAllowed(['pdf', 'png', 'jpg', 'jpeg', 'gif', 'txt', 'doc', 'docx'], 'Only PDF, images, and documents allowed!')])
    submit = SubmitField('Upload')


class SearchForm(FlaskForm):
    search = StringField('Search', validators=[Optional()])
    category = SelectField('Category', coerce=int, validators=[Optional()])
    
    def __init__(self, *args, **kwargs):
        super(SearchForm, self).__init__(*args, **kwargs)
        self.category.choices = [(0, 'All Categories')] + [(c.id, c.name) for c in Category.query.order_by(Category.name).all()]


class MagicParameterForm(FlaskForm):
    name = StringField('Parameter Name', validators=[DataRequired(), Length(max=200)])
    param_type = SelectField('Parameter Type', 
                            choices=[('number', 'Number'), ('date', 'Date'), ('string', 'String')],
                            validators=[DataRequired()])
    description = TextAreaField('Description', validators=[Optional()])
    notify_enabled = BooleanField('Notify me (for Date type)')
    
    # For Number type
    unit = StringField('Unit (for Number type)', validators=[Optional(), Length(max=50)])
    
    # For String type
    string_option = StringField('Option (for String type)', validators=[Optional(), Length(max=200)])
    
    submit = SubmitField('Save Parameter')


class ParameterUnitForm(FlaskForm):
    unit = StringField('Unit', validators=[DataRequired(), Length(max=50)])
    submit = SubmitField('Add Unit')


class RoleForm(FlaskForm):
    name = StringField('Role Name', validators=[DataRequired(), Length(min=2, max=50)])
    description = TextAreaField('Description', validators=[Optional()])
    submit = SubmitField('Save Role')


class ParameterStringOptionForm(FlaskForm):
    value = StringField('Option Value', validators=[DataRequired(), Length(max=200)])
    submit = SubmitField('Add Option')


class ItemParameterForm(FlaskForm):
    param_type = SelectField('Parameter Type', 
                            choices=[('', '-- Select Type --'), ('number', 'Number'), ('date', 'Date'), ('string', 'String')],
                            validators=[Optional()])
    parameter_id = SelectField('Parameter', coerce=int, validators=[DataRequired()])
    operation = SelectField('Operation', validators=[Optional()])
    value = StringField('Value', validators=[Optional(), Length(max=200)])
    value2 = StringField('Second Value (for Range/Duration)', validators=[Optional(), Length(max=200)])
    unit = SelectField('Unit', validators=[Optional()])
    string_option = SelectField('Option', validators=[Optional()])
    description = TextAreaField('Description', validators=[Optional()])
    submit = SubmitField('Add Parameter')
    
    def __init__(self, *args, **kwargs):
        super(ItemParameterForm, self).__init__(*args, **kwargs)
        from models import MagicParameter
        
        # Set parameter choices based on type
        self.parameter_id.choices = [(0, '-- Select Parameter --')]
        
        # Set operation choices for different types
        self.operation.choices = [
            ('', '-- Select Operation --'),
            ('min', 'Min'),
            ('max', 'Max'),
            ('value', 'Value'),
            ('range', 'Range')
        ]


class TagForm(FlaskForm):
    name = StringField('Tag Name', validators=[DataRequired(), Length(max=100)])
    description = TextAreaField('Description', validators=[Optional()])
    color = StringField('Color', validators=[Optional(), Length(max=7)], render_kw={"type": "color", "value": "#6c757d"}, default='#6c757d')
    submit = SubmitField('Save Tag')


class FootprintForm(FlaskForm):
    name = StringField('Footprint Name', validators=[DataRequired(), Length(max=100)])
    description = TextAreaField('Description', validators=[Optional()])
    color = StringField('Color', validators=[Optional(), Length(max=7)], render_kw={"type": "color", "value": "#6c757d"}, default='#6c757d')
    submit = SubmitField('Save Footprint')
