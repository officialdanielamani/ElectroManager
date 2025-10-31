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
    username = StringField('Username', validators=[DataRequired(), Length(min=3, max=80)])
    email = StringField('Email', validators=[DataRequired(), Email()])
    role = SelectField('Role', choices=[('admin', 'Admin'), ('editor', 'Editor'), ('viewer', 'Viewer')], validators=[DataRequired()])
    is_active = BooleanField('Active')
    password = PasswordField('Password (leave blank to keep current)', validators=[Optional(), Length(min=6)])
    submit = SubmitField('Save User')


class CategoryForm(FlaskForm):
    name = StringField('Category Name', validators=[DataRequired(), Length(max=100)])
    description = TextAreaField('Description', validators=[Optional()])
    submit = SubmitField('Save Category')


class ItemForm(FlaskForm):
    name = StringField('Item Name', validators=[DataRequired(), Length(max=200)])
    sku = StringField('SKU', validators=[Optional(), Length(max=100)])
    info = StringField('Type / Model', validators=[Optional(), Length(max=500)])
    description = TextAreaField('Description', validators=[Optional()])
    quantity = IntegerField('Quantity', validators=[NumberRange(min=0)], default=0)
    price = FloatField('Price per Qty', validators=[Optional(), NumberRange(min=0)])
    
    location_id = SelectField('General Location', coerce=int, validators=[Optional()])
    rack_id = SelectField('Rack', coerce=int, validators=[Optional()])
    drawer = StringField('Drawer', validators=[Optional(), Length(max=50)])
    
    min_quantity = IntegerField('Minimum Quantity', validators=[Optional(), NumberRange(min=0)], default=0)
    category_id = SelectField('Category', coerce=int, validators=[Optional()])
    footprint_id = SelectField('Footprint', coerce=int, validators=[Optional()])
    
    lend_to = StringField('Lend To', validators=[Optional(), Length(max=200)])
    lend_quantity = IntegerField('Lend Quantity', validators=[Optional(), NumberRange(min=0)], default=0)
    no_stock_warning = BooleanField('No Stock Warning', default=True)
    datasheet_urls = TextAreaField('Datasheet URLs', validators=[Optional()])
    
    submit = SubmitField('Save Item')
    
    def __init__(self, *args, **kwargs):
        super(ItemForm, self).__init__(*args, **kwargs)
        from models import Rack, Footprint, Location
        self.category_id.choices = [(0, '-- Select Category --')] + [(c.id, c.name) for c in Category.query.order_by(Category.name).all()]
        self.location_id.choices = [(0, '-- Select General Location --')] + [(l.id, l.name) for l in Location.query.order_by(Location.name).all()]
        self.rack_id.choices = [(0, '-- Select Rack --')] + [(r.id, r.name) for r in Rack.query.order_by(Rack.name).all()]
        self.footprint_id.choices = [(0, '-- Select Footprint --')] + [(f.id, f.name) for f in Footprint.query.order_by(Footprint.name).all()]


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
