"""Baseline schema.

Creates every table on a new database. On a database that predates Alembic it
creates only the tables that are missing and adds the columns the old startup
code used to patch in, so both end up at the same revision.

Revision ID: 0001_baseline
Revises:
"""
import secrets
import string

import sqlalchemy as sa
from alembic import op

revision = '0001_baseline'
down_revision = None
branch_labels = None
depends_on = None

# Columns added over time by the pre-Alembic startup code: (table, column, DDL type).
LEGACY_COLUMNS = [
    ("batch_lend_records",   "lend_note",           "VARCHAR(128)"),
    ("batch_serial_numbers", "lend_note",           "VARCHAR(128)"),
    ("batch_serial_numbers", "lending_session_id",  "INTEGER"),
    ("batch_lend_records",   "lending_session_id",  "INTEGER"),
    ("batch_lend_records",   "returned_at",         "DATETIME"),
    ("batch_lend_records",   "return_session_id",    "INTEGER"),
    ("batch_serial_numbers", "return_session_id",    "INTEGER"),
    ("batch_serial_numbers", "returned_at",          "DATETIME"),
    ("batch_serial_numbers", "returned_from_label",  "VARCHAR(128)"),
    ("users",                "allow_change_name",    "BOOLEAN DEFAULT 1"),
    ("item_batches",         "lend_disabled",        "BOOLEAN DEFAULT 0"),
    ("racks",                "drawer_icons",         "TEXT DEFAULT NULL"),
    ("racks",                "rack_icon",            "TEXT DEFAULT NULL"),
    ("projects",             "thumbnail",            "VARCHAR(300)"),
    ("project_bom_items",    "sort_order",           "INTEGER DEFAULT 0"),
    ("users",                "user_uid",             "VARCHAR(6)"),
    ("lending_sessions",     "is_api",               "BOOLEAN DEFAULT 0"),
    ("users",                "api_key_hash",         "VARCHAR(64)"),
    ("users",                "api_key_prefix",       "VARCHAR(16)"),
    ("kanban_tasks",         "start_date",           "DATE"),
    ("kanban_boards",        "notify_start_enabled", "BOOLEAN DEFAULT 0"),
    ("kanban_boards",        "notify_start_days",    "INTEGER DEFAULT 1"),
    ("kanban_boards",        "notify_due_enabled",   "BOOLEAN DEFAULT 0"),
    ("kanban_boards",        "notify_due_days",      "INTEGER DEFAULT 1"),
    ("kanban_cards",         "category_id",          "INTEGER"),
    ("kanban_boards",        "board_icon",            "VARCHAR(48) DEFAULT 'bi-kanban'"),
    ("kanban_boards",        "board_color",           "VARCHAR(7) DEFAULT '#6b7280'"),
    ("kanban_boards",        "board_status",          "VARCHAR(10) DEFAULT 'shown'"),
    ("kanban_boards",        "board_uuid",            "VARCHAR(12)"),
    ("kanban_boards",        "is_public",             "BOOLEAN DEFAULT 0"),
    ("kanban_boards",        "share_view_users",      "TEXT"),
    ("kanban_boards",        "share_edit_users",      "TEXT"),
    ("kanban_boards",        "created_at",            "DATETIME"),
    ("kanban_boards",        "updated_at",            "DATETIME"),
    ("kanban_cards",         "created_at",            "DATETIME"),
    ("kanban_cards",         "updated_at",            "DATETIME"),
    ("kanban_cards",         "created_by_id",         "INTEGER"),
    ("kanban_cards",         "updated_by_id",         "INTEGER"),
    ("kanban_board_user_states", "notify_start_enabled", "BOOLEAN DEFAULT 0"),
    ("kanban_board_user_states", "notify_start_days",    "INTEGER DEFAULT 1"),
    ("kanban_board_user_states", "notify_due_enabled",   "BOOLEAN DEFAULT 0"),
    ("kanban_board_user_states", "notify_due_days",      "INTEGER DEFAULT 1"),
    ("kanban_boards", "last_transfer_from_id",   "INTEGER"),
    ("kanban_boards", "last_transfer_from_name", "VARCHAR(128)"),
    ("kanban_boards", "last_transfer_at",        "DATETIME"),
    ("sticker_templates", "owner_id",          "INTEGER"),
    ("sticker_templates", "is_public",         "BOOLEAN DEFAULT 0"),
    ("sticker_templates", "share_view_users",  "TEXT"),
    ("sticker_templates", "share_edit_users",  "TEXT"),
    ("users",             "navbar_config",      "TEXT"),
    ("kanban_cards",      "card_icon",           "VARCHAR(48)"),
    ("users",             "mfa_secret",          "VARCHAR(64)"),
    ("users",             "mfa_enabled",         "BOOLEAN DEFAULT 0"),
    ("users",             "mfa_backup_codes",    "TEXT"),
]

TABLES = ['categories', 'contact_groups', 'contact_organizations', 'footprints', 'groups', 'locations', 'magic_parameters', 'parameter_templates', 'persons', 'plugins', 'project_categories', 'project_statuses', 'project_tags', 'roles', 'settings', 'tags', 'contact_persons', 'parameter_string_options', 'parameter_units', 'racks', 'template_parameters', 'users', 'audit_logs', 'contact_group_members', 'group_members', 'items', 'kanban_boards', 'lending_sessions', 'projects', 'shared_files', 'sticker_templates', 'attachments', 'item_batches', 'item_parameters', 'item_share_files', 'kanban_board_user_states', 'kanban_categories', 'kanban_columns', 'project_attachments', 'project_cost_items', 'project_parameters', 'project_share_files', 'project_urls', 'batch_lend_records', 'batch_serial_numbers', 'item_parameter_string_values', 'kanban_cards', 'project_bom_items', 'project_parameter_string_values', 'kanban_attachments', 'kanban_card_share_files', 'kanban_tasks']

_existing = set()


def _create_table(name, *columns, **kw):
    if name not in _existing:
        op.create_table(name, *columns, **kw)


def _add_legacy_columns(bind):
    inspector = sa.inspect(bind)
    for table, column, ddl_type in LEGACY_COLUMNS:
        if table not in _existing:
            continue
        if column not in {c['name'] for c in inspector.get_columns(table)}:
            op.execute(sa.text(f'ALTER TABLE {table} ADD COLUMN {column} {ddl_type}'))


def _backfill(bind, table, column, generate):
    rows = bind.execute(sa.text(f'SELECT id FROM {table} WHERE {column} IS NULL')).fetchall()
    if not rows:
        return
    taken = {r[0] for r in bind.execute(sa.text(f'SELECT {column} FROM {table} WHERE {column} IS NOT NULL'))}
    for (row_id,) in rows:
        value = generate()
        while value in taken:
            value = generate()
        taken.add(value)
        bind.execute(sa.text(f'UPDATE {table} SET {column} = :value WHERE id = :id'),
                     {'value': value, 'id': row_id})


def _random(length):
    chars = string.ascii_uppercase + string.digits
    return ''.join(secrets.choice(chars) for _ in range(length))


def upgrade():
    bind = op.get_bind()
    _existing.clear()
    _existing.update(sa.inspect(bind).get_table_names())

    _create_table('categories',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('name', sa.String(length=128), nullable=False),
    sa.Column('description', sa.String(length=512), nullable=True),
    sa.Column('color', sa.String(length=7), nullable=True),
    sa.Column('created_at', sa.DateTime(), nullable=True),
    sa.Column('updated_at', sa.DateTime(), nullable=True),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('name')
    )
    _create_table('contact_groups',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('name', sa.String(length=256), nullable=False),
    sa.Column('description', sa.String(length=512), nullable=True),
    sa.Column('created_at', sa.DateTime(), nullable=True),
    sa.Column('updated_at', sa.DateTime(), nullable=True),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('name')
    )
    _create_table('contact_organizations',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('name', sa.String(length=256), nullable=False),
    sa.Column('email', sa.String(length=256), nullable=True),
    sa.Column('tel', sa.String(length=64), nullable=True),
    sa.Column('url', sa.String(length=512), nullable=True),
    sa.Column('address', sa.String(length=256), nullable=True),
    sa.Column('zip_code', sa.String(length=16), nullable=True),
    sa.Column('info', sa.String(length=128), nullable=True),
    sa.Column('created_at', sa.DateTime(), nullable=True),
    sa.Column('updated_at', sa.DateTime(), nullable=True),
    sa.PrimaryKeyConstraint('id')
    )
    _create_table('footprints',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('name', sa.String(length=128), nullable=False),
    sa.Column('description', sa.String(length=512), nullable=True),
    sa.Column('color', sa.String(length=7), nullable=True),
    sa.Column('created_at', sa.DateTime(), nullable=True),
    sa.Column('updated_at', sa.DateTime(), nullable=True),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('name')
    )
    _create_table('groups',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('name', sa.String(length=200), nullable=False),
    sa.Column('description', sa.Text(), nullable=True),
    sa.Column('color', sa.String(length=7), nullable=True),
    sa.Column('created_at', sa.DateTime(), nullable=True),
    sa.Column('updated_at', sa.DateTime(), nullable=True),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('name')
    )
    _create_table('locations',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('uuid', sa.String(length=12), nullable=False),
    sa.Column('name', sa.String(length=128), nullable=False),
    sa.Column('info', sa.String(length=128), nullable=True),
    sa.Column('description', sa.String(length=512), nullable=True),
    sa.Column('picture', sa.String(length=200), nullable=True),
    sa.Column('color', sa.String(length=7), nullable=True),
    sa.Column('created_at', sa.DateTime(), nullable=True),
    sa.Column('updated_at', sa.DateTime(), nullable=True),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('uuid')
    )
    _create_table('magic_parameters',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('name', sa.String(length=256), nullable=False),
    sa.Column('param_type', sa.String(length=50), nullable=False),
    sa.Column('description', sa.String(length=512), nullable=True),
    sa.Column('notify_enabled', sa.Boolean(), nullable=True),
    sa.Column('is_whole_number', sa.Boolean(), nullable=True),
    sa.Column('number_min', sa.Float(), nullable=True),
    sa.Column('number_max', sa.Float(), nullable=True),
    sa.Column('number_step', sa.Float(), nullable=True),
    sa.Column('number_decimal_places', sa.Integer(), nullable=True),
    sa.Column('number_required', sa.Boolean(), nullable=True),
    sa.Column('string_select_min', sa.Integer(), nullable=True),
    sa.Column('string_select_max', sa.Integer(), nullable=True),
    sa.Column('string_allow_custom', sa.Boolean(), nullable=True),
    sa.Column('string_regex', sa.String(length=500), nullable=True),
    sa.Column('string_regex_info', sa.String(length=200), nullable=True),
    sa.Column('created_at', sa.DateTime(), nullable=True),
    sa.Column('updated_at', sa.DateTime(), nullable=True),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('name')
    )
    _create_table('parameter_templates',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('name', sa.String(length=256), nullable=False),
    sa.Column('description', sa.String(length=512), nullable=True),
    sa.Column('created_at', sa.DateTime(), nullable=True),
    sa.Column('updated_at', sa.DateTime(), nullable=True),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('name')
    )
    _create_table('persons',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('name', sa.String(length=200), nullable=False),
    sa.Column('email', sa.String(length=200), nullable=True),
    sa.Column('organization', sa.String(length=200), nullable=True),
    sa.Column('tel', sa.String(length=50), nullable=True),
    sa.Column('created_at', sa.DateTime(), nullable=True),
    sa.Column('updated_at', sa.DateTime(), nullable=True),
    sa.PrimaryKeyConstraint('id')
    )
    _create_table('plugins',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('slug', sa.String(length=64), nullable=False),
    sa.Column('name', sa.String(length=128), nullable=False),
    sa.Column('description', sa.String(length=512), nullable=True),
    sa.Column('version', sa.String(length=32), nullable=True),
    sa.Column('plugin_type', sa.String(length=32), nullable=True),
    sa.Column('enabled', sa.Boolean(), nullable=True),
    sa.Column('config', sa.Text(), nullable=True),
    sa.Column('created_at', sa.DateTime(), nullable=True),
    sa.Column('updated_at', sa.DateTime(), nullable=True),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('slug')
    )
    _create_table('project_categories',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('name', sa.String(length=128), nullable=False),
    sa.Column('description', sa.String(length=512), nullable=True),
    sa.Column('color', sa.String(length=7), nullable=True),
    sa.Column('created_at', sa.DateTime(), nullable=True),
    sa.Column('updated_at', sa.DateTime(), nullable=True),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('name')
    )
    _create_table('project_statuses',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('name', sa.String(length=128), nullable=False),
    sa.Column('color', sa.String(length=7), nullable=True),
    sa.Column('description', sa.String(length=512), nullable=True),
    sa.Column('created_at', sa.DateTime(), nullable=True),
    sa.Column('updated_at', sa.DateTime(), nullable=True),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('name')
    )
    _create_table('project_tags',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('name', sa.String(length=128), nullable=False),
    sa.Column('description', sa.String(length=512), nullable=True),
    sa.Column('color', sa.String(length=7), nullable=True),
    sa.Column('created_at', sa.DateTime(), nullable=True),
    sa.Column('updated_at', sa.DateTime(), nullable=True),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('name')
    )
    _create_table('roles',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('name', sa.String(length=64), nullable=False),
    sa.Column('description', sa.String(length=512), nullable=True),
    sa.Column('is_system_role', sa.Boolean(), nullable=True),
    sa.Column('permissions', sa.Text(), nullable=False),
    sa.Column('created_at', sa.DateTime(), nullable=True),
    sa.Column('updated_at', sa.DateTime(), nullable=True),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('name')
    )
    _create_table('settings',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('key', sa.String(length=100), nullable=False),
    sa.Column('value', sa.String(length=500), nullable=True),
    sa.Column('description', sa.String(length=500), nullable=True),
    sa.Column('created_at', sa.DateTime(), nullable=True),
    sa.Column('updated_at', sa.DateTime(), nullable=True),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('key')
    )
    _create_table('tags',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('name', sa.String(length=128), nullable=False),
    sa.Column('description', sa.String(length=512), nullable=True),
    sa.Column('color', sa.String(length=7), nullable=True),
    sa.Column('created_at', sa.DateTime(), nullable=True),
    sa.Column('updated_at', sa.DateTime(), nullable=True),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('name')
    )
    _create_table('contact_persons',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('name', sa.String(length=256), nullable=False),
    sa.Column('email', sa.String(length=256), nullable=True),
    sa.Column('tel', sa.String(length=64), nullable=True),
    sa.Column('organization_id', sa.Integer(), nullable=True),
    sa.Column('created_at', sa.DateTime(), nullable=True),
    sa.Column('updated_at', sa.DateTime(), nullable=True),
    sa.ForeignKeyConstraint(['organization_id'], ['contact_organizations.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    _create_table('parameter_string_options',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('parameter_id', sa.Integer(), nullable=False),
    sa.Column('value', sa.String(length=128), nullable=False),
    sa.Column('created_at', sa.DateTime(), nullable=True),
    sa.ForeignKeyConstraint(['parameter_id'], ['magic_parameters.id'], ),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('parameter_id', 'value', name='_parameter_value_uc')
    )
    _create_table('parameter_units',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('parameter_id', sa.Integer(), nullable=False),
    sa.Column('unit', sa.String(length=50), nullable=False),
    sa.Column('created_at', sa.DateTime(), nullable=True),
    sa.ForeignKeyConstraint(['parameter_id'], ['magic_parameters.id'], ),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('parameter_id', 'unit', name='_parameter_unit_uc')
    )
    _create_table('racks',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('uuid', sa.String(length=12), nullable=False),
    sa.Column('name', sa.String(length=128), nullable=False),
    sa.Column('short_info', sa.String(length=128), nullable=True),
    sa.Column('description', sa.String(length=512), nullable=True),
    sa.Column('location_id', sa.Integer(), nullable=True),
    sa.Column('picture', sa.String(length=200), nullable=True),
    sa.Column('color', sa.String(length=7), nullable=True),
    sa.Column('rows', sa.Integer(), nullable=True),
    sa.Column('cols', sa.Integer(), nullable=True),
    sa.Column('unavailable_drawers', sa.Text(), nullable=True),
    sa.Column('merged_cells', sa.Text(), nullable=True),
    sa.Column('drawer_info', sa.Text(), nullable=True),
    sa.Column('drawer_icons', sa.Text(), nullable=True),
    sa.Column('rack_icon', sa.Text(), nullable=True),
    sa.Column('created_at', sa.DateTime(), nullable=True),
    sa.Column('updated_at', sa.DateTime(), nullable=True),
    sa.ForeignKeyConstraint(['location_id'], ['locations.id'], ),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('uuid')
    )
    _create_table('template_parameters',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('template_id', sa.Integer(), nullable=False),
    sa.Column('parameter_id', sa.Integer(), nullable=False),
    sa.Column('operation', sa.String(length=50), nullable=True),
    sa.Column('value', sa.String(length=200), nullable=True),
    sa.Column('value2', sa.String(length=200), nullable=True),
    sa.Column('unit', sa.String(length=50), nullable=True),
    sa.Column('string_option', sa.String(length=200), nullable=True),
    sa.Column('description', sa.Text(), nullable=True),
    sa.Column('display_order', sa.Integer(), nullable=True),
    sa.Column('created_at', sa.DateTime(), nullable=True),
    sa.ForeignKeyConstraint(['parameter_id'], ['magic_parameters.id'], ),
    sa.ForeignKeyConstraint(['template_id'], ['parameter_templates.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    _create_table('users',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('user_uid', sa.String(length=6), nullable=True),
    sa.Column('username', sa.String(length=80), nullable=False),
    sa.Column('email', sa.String(length=120), nullable=False),
    sa.Column('password_hash', sa.String(length=255), nullable=False),
    sa.Column('name', sa.String(length=64), nullable=True),
    sa.Column('short_info', sa.String(length=128), nullable=True),
    sa.Column('role_id', sa.Integer(), nullable=False),
    sa.Column('theme', sa.String(length=20), nullable=True),
    sa.Column('user_font', sa.String(length=50), nullable=True),
    sa.Column('table_columns_view', sa.Text(), nullable=True),
    sa.Column('project_table_columns_view', sa.Text(), nullable=True),
    sa.Column('navbar_config', sa.Text(), nullable=True),
    sa.Column('created_at', sa.DateTime(), nullable=True),
    sa.Column('is_active', sa.Boolean(), nullable=True),
    sa.Column('is_demo_user', sa.Boolean(), nullable=True),
    sa.Column('max_login_attempts', sa.Integer(), nullable=True),
    sa.Column('allow_password_reset', sa.Boolean(), nullable=True),
    sa.Column('profile_photo', sa.String(length=255), nullable=True),
    sa.Column('allow_profile_picture_change', sa.Boolean(), nullable=True),
    sa.Column('allow_change_name', sa.Boolean(), nullable=True),
    sa.Column('allow_change_short_info', sa.Boolean(), nullable=True),
    sa.Column('profile_picture_source', sa.String(length=10), nullable=True),
    sa.Column('failed_login_attempts', sa.Integer(), nullable=True),
    sa.Column('account_locked_until', sa.DateTime(), nullable=True),
    sa.Column('auto_unlock_enabled', sa.Boolean(), nullable=True),
    sa.Column('auto_unlock_minutes', sa.Integer(), nullable=True),
    sa.Column('api_enabled', sa.Boolean(), nullable=True),
    sa.Column('api_key_hash', sa.String(length=64), nullable=True),
    sa.Column('api_key_prefix', sa.String(length=16), nullable=True),
    sa.Column('api_item_search', sa.Boolean(), nullable=True),
    sa.Column('api_rack_drawer', sa.Boolean(), nullable=True),
    sa.Column('api_lending_return', sa.Boolean(), nullable=True),
    sa.Column('mfa_secret', sa.String(length=64), nullable=True),
    sa.Column('mfa_enabled', sa.Boolean(), nullable=True),
    sa.Column('mfa_backup_codes', sa.Text(), nullable=True),
    sa.ForeignKeyConstraint(['role_id'], ['roles.id'], ),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('email'),
    sa.UniqueConstraint('user_uid'),
    sa.UniqueConstraint('username')
    )
    _create_table('audit_logs',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('user_id', sa.Integer(), nullable=True),
    sa.Column('action', sa.String(length=50), nullable=False),
    sa.Column('entity_type', sa.String(length=50), nullable=False),
    sa.Column('entity_id', sa.Integer(), nullable=True),
    sa.Column('details', sa.Text(), nullable=True),
    sa.Column('timestamp', sa.DateTime(), nullable=True),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    _create_table('contact_group_members',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('group_id', sa.Integer(), nullable=False),
    sa.Column('user_id', sa.Integer(), nullable=True),
    sa.Column('person_id', sa.Integer(), nullable=True),
    sa.Column('organization_id', sa.Integer(), nullable=True),
    sa.ForeignKeyConstraint(['group_id'], ['contact_groups.id'], ),
    sa.ForeignKeyConstraint(['organization_id'], ['contact_organizations.id'], ),
    sa.ForeignKeyConstraint(['person_id'], ['contact_persons.id'], ),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    _create_table('group_members',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('group_id', sa.Integer(), nullable=False),
    sa.Column('user_id', sa.Integer(), nullable=True),
    sa.Column('person_id', sa.Integer(), nullable=True),
    sa.ForeignKeyConstraint(['group_id'], ['groups.id'], ),
    sa.ForeignKeyConstraint(['person_id'], ['persons.id'], ),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    _create_table('items',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('uuid', sa.String(length=16), nullable=False),
    sa.Column('name', sa.String(length=200), nullable=False),
    sa.Column('sku', sa.String(length=100), nullable=True),
    sa.Column('short_info', sa.String(length=128), nullable=True),
    sa.Column('info', sa.String(length=128), nullable=True),
    sa.Column('description', sa.Text(), nullable=True),
    sa.Column('quantity', sa.Integer(), nullable=True),
    sa.Column('price', sa.Float(), nullable=True),
    sa.Column('location_id', sa.Integer(), nullable=True),
    sa.Column('rack_id', sa.Integer(), nullable=True),
    sa.Column('drawer', sa.String(length=50), nullable=True),
    sa.Column('min_quantity', sa.Integer(), nullable=True),
    sa.Column('category_id', sa.Integer(), nullable=True),
    sa.Column('footprint_id', sa.Integer(), nullable=True),
    sa.Column('tags', sa.Text(), nullable=True),
    sa.Column('datasheet_urls', sa.String(length=2048), nullable=True),
    sa.Column('no_stock_warning', sa.Boolean(), nullable=True),
    sa.Column('thumbnail', sa.String(length=300), nullable=True),
    sa.Column('sn_tracking_enabled', sa.Boolean(), nullable=True),
    sa.Column('created_at', sa.DateTime(), nullable=True),
    sa.Column('updated_at', sa.DateTime(), nullable=True),
    sa.Column('created_by', sa.Integer(), nullable=True),
    sa.Column('updated_by', sa.Integer(), nullable=True),
    sa.ForeignKeyConstraint(['category_id'], ['categories.id'], ),
    sa.ForeignKeyConstraint(['created_by'], ['users.id'], ),
    sa.ForeignKeyConstraint(['footprint_id'], ['footprints.id'], ),
    sa.ForeignKeyConstraint(['location_id'], ['locations.id'], ),
    sa.ForeignKeyConstraint(['rack_id'], ['racks.id'], ),
    sa.ForeignKeyConstraint(['updated_by'], ['users.id'], ),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('uuid')
    )
    _create_table('kanban_boards',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('user_id', sa.Integer(), nullable=False),
    sa.Column('name', sa.String(length=128), nullable=False),
    sa.Column('board_uuid', sa.String(length=12), nullable=True),
    sa.Column('position', sa.Integer(), nullable=True),
    sa.Column('board_icon', sa.String(length=48), nullable=True),
    sa.Column('board_color', sa.String(length=7), nullable=True),
    sa.Column('board_status', sa.String(length=10), nullable=True),
    sa.Column('is_public', sa.Boolean(), nullable=True),
    sa.Column('share_view_users', sa.Text(), nullable=True),
    sa.Column('share_edit_users', sa.Text(), nullable=True),
    sa.Column('notify_start_enabled', sa.Boolean(), nullable=True),
    sa.Column('notify_start_days', sa.Integer(), nullable=True),
    sa.Column('notify_due_enabled', sa.Boolean(), nullable=True),
    sa.Column('notify_due_days', sa.Integer(), nullable=True),
    sa.Column('last_transfer_from_id', sa.Integer(), nullable=True),
    sa.Column('last_transfer_from_name', sa.String(length=128), nullable=True),
    sa.Column('last_transfer_at', sa.DateTime(), nullable=True),
    sa.Column('created_at', sa.DateTime(), nullable=True),
    sa.Column('updated_at', sa.DateTime(), nullable=True),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('board_uuid')
    )
    _create_table('lending_sessions',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('lending_id', sa.String(length=20), nullable=False),
    sa.Column('mode', sa.String(length=16), nullable=False),
    sa.Column('created_by_id', sa.Integer(), nullable=True),
    sa.Column('created_at', sa.DateTime(), nullable=True),
    sa.Column('lend_to_type', sa.String(length=32), nullable=True),
    sa.Column('lend_to_id', sa.Integer(), nullable=True),
    sa.Column('lend_start', sa.DateTime(), nullable=True),
    sa.Column('lend_end', sa.DateTime(), nullable=True),
    sa.Column('notes', sa.String(length=256), nullable=True),
    sa.Column('is_api', sa.Boolean(), nullable=False),
    sa.ForeignKeyConstraint(['created_by_id'], ['users.id'], ),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('lending_id')
    )
    _create_table('projects',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('project_id', sa.String(length=12), nullable=False),
    sa.Column('name', sa.String(length=512), nullable=False),
    sa.Column('info', sa.String(length=128), nullable=True),
    sa.Column('description', sa.Text(), nullable=True),
    sa.Column('category_id', sa.Integer(), nullable=True),
    sa.Column('tags', sa.Text(), nullable=True),
    sa.Column('status_id', sa.Integer(), nullable=True),
    sa.Column('date_start', sa.Date(), nullable=True),
    sa.Column('date_end', sa.Date(), nullable=True),
    sa.Column('quantity', sa.Integer(), nullable=True),
    sa.Column('users', sa.Text(), nullable=True),
    sa.Column('persons', sa.Text(), nullable=True),
    sa.Column('organizations', sa.Text(), nullable=True),
    sa.Column('thumbnail', sa.String(length=300), nullable=True),
    sa.Column('enable_dateline_notification', sa.Boolean(), nullable=True),
    sa.Column('notify_before_days', sa.Integer(), nullable=True),
    sa.Column('created_at', sa.DateTime(), nullable=True),
    sa.Column('updated_at', sa.DateTime(), nullable=True),
    sa.Column('created_by', sa.Integer(), nullable=True),
    sa.Column('updated_by', sa.Integer(), nullable=True),
    sa.ForeignKeyConstraint(['category_id'], ['project_categories.id'], ),
    sa.ForeignKeyConstraint(['created_by'], ['users.id'], ),
    sa.ForeignKeyConstraint(['status_id'], ['project_statuses.id'], ),
    sa.ForeignKeyConstraint(['updated_by'], ['users.id'], ),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('project_id')
    )
    _create_table('shared_files',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('name', sa.String(length=200), nullable=False),
    sa.Column('filename', sa.String(length=255), nullable=False),
    sa.Column('category', sa.String(length=20), nullable=False),
    sa.Column('file_size', sa.Integer(), nullable=True),
    sa.Column('created_at', sa.DateTime(), nullable=True),
    sa.Column('uploaded_by_id', sa.Integer(), nullable=True),
    sa.ForeignKeyConstraint(['uploaded_by_id'], ['users.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    _create_table('sticker_templates',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('name', sa.String(length=100), nullable=False),
    sa.Column('template_type', sa.String(length=20), nullable=False),
    sa.Column('width_mm', sa.Float(), nullable=False),
    sa.Column('height_mm', sa.Float(), nullable=False),
    sa.Column('layout', sa.Text(), nullable=False),
    sa.Column('is_default', sa.Boolean(), nullable=True),
    sa.Column('owner_id', sa.Integer(), nullable=True),
    sa.Column('is_public', sa.Boolean(), nullable=True),
    sa.Column('share_view_users', sa.Text(), nullable=True),
    sa.Column('share_edit_users', sa.Text(), nullable=True),
    sa.Column('created_by', sa.Integer(), nullable=True),
    sa.Column('updated_by', sa.Integer(), nullable=True),
    sa.Column('created_at', sa.DateTime(), nullable=True),
    sa.Column('updated_at', sa.DateTime(), nullable=True),
    sa.ForeignKeyConstraint(['created_by'], ['users.id'], ),
    sa.ForeignKeyConstraint(['owner_id'], ['users.id'], ),
    sa.ForeignKeyConstraint(['updated_by'], ['users.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    _create_table('attachments',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('filename', sa.String(length=255), nullable=False),
    sa.Column('original_filename', sa.String(length=255), nullable=False),
    sa.Column('file_path', sa.String(length=500), nullable=False),
    sa.Column('file_type', sa.String(length=50), nullable=True),
    sa.Column('file_size', sa.Integer(), nullable=True),
    sa.Column('item_id', sa.Integer(), nullable=False),
    sa.Column('uploaded_at', sa.DateTime(), nullable=True),
    sa.Column('uploaded_by', sa.Integer(), nullable=True),
    sa.ForeignKeyConstraint(['item_id'], ['items.id'], ),
    sa.ForeignKeyConstraint(['uploaded_by'], ['users.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    _create_table('item_batches',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('item_id', sa.Integer(), nullable=False),
    sa.Column('batch_number', sa.Integer(), nullable=False),
    sa.Column('batch_label', sa.String(length=32), nullable=True),
    sa.Column('manufacturer', sa.String(length=128), nullable=True),
    sa.Column('quantity', sa.Integer(), nullable=True),
    sa.Column('price_per_unit', sa.Float(), nullable=True),
    sa.Column('purchase_date', sa.Date(), nullable=True),
    sa.Column('note', sa.String(length=128), nullable=True),
    sa.Column('sn_tracking_enabled', sa.Boolean(), nullable=True),
    sa.Column('lend_disabled', sa.Boolean(), nullable=True),
    sa.Column('follow_main_location', sa.Boolean(), nullable=True),
    sa.Column('location_id', sa.Integer(), nullable=True),
    sa.Column('rack_id', sa.Integer(), nullable=True),
    sa.Column('drawer', sa.String(length=50), nullable=True),
    sa.Column('created_at', sa.DateTime(), nullable=True),
    sa.Column('updated_at', sa.DateTime(), nullable=True),
    sa.ForeignKeyConstraint(['item_id'], ['items.id'], ),
    sa.ForeignKeyConstraint(['location_id'], ['locations.id'], ),
    sa.ForeignKeyConstraint(['rack_id'], ['racks.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    _create_table('item_parameters',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('item_id', sa.Integer(), nullable=False),
    sa.Column('parameter_id', sa.Integer(), nullable=False),
    sa.Column('operation', sa.String(length=50), nullable=True),
    sa.Column('value', sa.String(length=200), nullable=True),
    sa.Column('value2', sa.String(length=200), nullable=True),
    sa.Column('unit', sa.String(length=50), nullable=True),
    sa.Column('string_option', sa.String(length=128), nullable=True),
    sa.Column('description', sa.String(length=512), nullable=True),
    sa.Column('created_at', sa.DateTime(), nullable=True),
    sa.Column('updated_at', sa.DateTime(), nullable=True),
    sa.ForeignKeyConstraint(['item_id'], ['items.id'], ),
    sa.ForeignKeyConstraint(['parameter_id'], ['magic_parameters.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    _create_table('item_share_files',
    sa.Column('item_id', sa.Integer(), nullable=False),
    sa.Column('shared_file_id', sa.Integer(), nullable=False),
    sa.ForeignKeyConstraint(['item_id'], ['items.id'], ),
    sa.ForeignKeyConstraint(['shared_file_id'], ['shared_files.id'], ),
    sa.PrimaryKeyConstraint('item_id', 'shared_file_id')
    )
    _create_table('kanban_board_user_states',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('board_id', sa.Integer(), nullable=False),
    sa.Column('user_id', sa.Integer(), nullable=False),
    sa.Column('status', sa.String(length=10), nullable=True),
    sa.Column('position', sa.Integer(), nullable=True),
    sa.Column('notify_start_enabled', sa.Boolean(), nullable=True),
    sa.Column('notify_start_days', sa.Integer(), nullable=True),
    sa.Column('notify_due_enabled', sa.Boolean(), nullable=True),
    sa.Column('notify_due_days', sa.Integer(), nullable=True),
    sa.ForeignKeyConstraint(['board_id'], ['kanban_boards.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('board_id', 'user_id', name='uq_kanban_board_user')
    )
    _create_table('kanban_categories',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('board_id', sa.Integer(), nullable=False),
    sa.Column('name', sa.String(length=64), nullable=False),
    sa.Column('position', sa.Integer(), nullable=True),
    sa.Column('created_at', sa.DateTime(), nullable=True),
    sa.ForeignKeyConstraint(['board_id'], ['kanban_boards.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    _create_table('kanban_columns',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('board_id', sa.Integer(), nullable=False),
    sa.Column('name', sa.String(length=64), nullable=False),
    sa.Column('color', sa.String(length=7), nullable=True),
    sa.Column('icon', sa.String(length=32), nullable=True),
    sa.Column('position', sa.Integer(), nullable=True),
    sa.ForeignKeyConstraint(['board_id'], ['kanban_boards.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    _create_table('project_attachments',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('project_id', sa.Integer(), nullable=False),
    sa.Column('filename', sa.String(length=255), nullable=False),
    sa.Column('original_filename', sa.String(length=255), nullable=False),
    sa.Column('file_path', sa.String(length=500), nullable=False),
    sa.Column('file_type', sa.String(length=50), nullable=True),
    sa.Column('file_size', sa.Integer(), nullable=True),
    sa.Column('attachment_type', sa.String(length=50), nullable=True),
    sa.Column('uploaded_at', sa.DateTime(), nullable=True),
    sa.Column('uploaded_by', sa.Integer(), nullable=True),
    sa.ForeignKeyConstraint(['project_id'], ['projects.id'], ),
    sa.ForeignKeyConstraint(['uploaded_by'], ['users.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    _create_table('project_cost_items',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('project_id', sa.Integer(), nullable=False),
    sa.Column('cost_type', sa.String(length=20), nullable=False),
    sa.Column('name', sa.String(length=255), nullable=False),
    sa.Column('description', sa.String(length=255), nullable=True),
    sa.Column('price', sa.Float(), nullable=True),
    sa.Column('unit_label', sa.String(length=50), nullable=True),
    sa.Column('quantity', sa.Float(), nullable=True),
    sa.Column('sort_order', sa.Integer(), nullable=True),
    sa.Column('created_at', sa.DateTime(), nullable=True),
    sa.ForeignKeyConstraint(['project_id'], ['projects.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    _create_table('project_parameters',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('project_id', sa.Integer(), nullable=False),
    sa.Column('parameter_id', sa.Integer(), nullable=False),
    sa.Column('operation', sa.String(length=50), nullable=True),
    sa.Column('value', sa.String(length=200), nullable=True),
    sa.Column('value2', sa.String(length=200), nullable=True),
    sa.Column('unit', sa.String(length=50), nullable=True),
    sa.Column('description', sa.String(length=512), nullable=True),
    sa.Column('created_at', sa.DateTime(), nullable=True),
    sa.Column('updated_at', sa.DateTime(), nullable=True),
    sa.ForeignKeyConstraint(['parameter_id'], ['magic_parameters.id'], ),
    sa.ForeignKeyConstraint(['project_id'], ['projects.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    _create_table('project_share_files',
    sa.Column('project_id', sa.Integer(), nullable=False),
    sa.Column('shared_file_id', sa.Integer(), nullable=False),
    sa.ForeignKeyConstraint(['project_id'], ['projects.id'], ),
    sa.ForeignKeyConstraint(['shared_file_id'], ['shared_files.id'], ),
    sa.PrimaryKeyConstraint('project_id', 'shared_file_id')
    )
    _create_table('project_urls',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('project_id', sa.Integer(), nullable=False),
    sa.Column('url', sa.String(length=1000), nullable=False),
    sa.Column('title', sa.String(length=300), nullable=True),
    sa.Column('description', sa.Text(), nullable=True),
    sa.Column('created_at', sa.DateTime(), nullable=True),
    sa.ForeignKeyConstraint(['project_id'], ['projects.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    _create_table('batch_lend_records',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('batch_id', sa.Integer(), nullable=False),
    sa.Column('lend_to_type', sa.String(length=32), nullable=True),
    sa.Column('lend_to_id', sa.Integer(), nullable=True),
    sa.Column('quantity', sa.Integer(), nullable=True),
    sa.Column('lend_start', sa.DateTime(), nullable=True),
    sa.Column('lend_end', sa.DateTime(), nullable=True),
    sa.Column('lend_notify_enabled', sa.Boolean(), nullable=True),
    sa.Column('lend_notify_before_days', sa.Integer(), nullable=True),
    sa.Column('lend_note', sa.String(length=128), nullable=True),
    sa.Column('lending_session_id', sa.Integer(), nullable=True),
    sa.Column('return_session_id', sa.Integer(), nullable=True),
    sa.Column('returned_at', sa.DateTime(), nullable=True),
    sa.Column('created_at', sa.DateTime(), nullable=True),
    sa.ForeignKeyConstraint(['batch_id'], ['item_batches.id'], ),
    sa.ForeignKeyConstraint(['lending_session_id'], ['lending_sessions.id'], ),
    sa.ForeignKeyConstraint(['return_session_id'], ['lending_sessions.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    _create_table('batch_serial_numbers',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('batch_id', sa.Integer(), nullable=False),
    sa.Column('sequence_number', sa.Integer(), nullable=False),
    sa.Column('serial_number', sa.String(length=200), nullable=True),
    sa.Column('internal_serial_number', sa.String(length=200), nullable=False),
    sa.Column('info', sa.String(length=32), nullable=True),
    sa.Column('lend_to_type', sa.String(length=32), nullable=True),
    sa.Column('lend_to_id', sa.Integer(), nullable=True),
    sa.Column('lend_start', sa.DateTime(), nullable=True),
    sa.Column('lend_end', sa.DateTime(), nullable=True),
    sa.Column('lend_notify_enabled', sa.Boolean(), nullable=True),
    sa.Column('lend_notify_before_days', sa.Integer(), nullable=True),
    sa.Column('lend_note', sa.String(length=128), nullable=True),
    sa.Column('lending_session_id', sa.Integer(), nullable=True),
    sa.Column('return_session_id', sa.Integer(), nullable=True),
    sa.Column('returned_at', sa.DateTime(), nullable=True),
    sa.Column('returned_from_label', sa.String(length=128), nullable=True),
    sa.Column('is_deleted', sa.Boolean(), nullable=True),
    sa.Column('deleted_by_id', sa.Integer(), nullable=True),
    sa.Column('deleted_at', sa.DateTime(), nullable=True),
    sa.Column('deleted_reason', sa.String(length=256), nullable=True),
    sa.Column('created_at', sa.DateTime(), nullable=True),
    sa.ForeignKeyConstraint(['batch_id'], ['item_batches.id'], ),
    sa.ForeignKeyConstraint(['deleted_by_id'], ['users.id'], ),
    sa.ForeignKeyConstraint(['lending_session_id'], ['lending_sessions.id'], ),
    sa.ForeignKeyConstraint(['return_session_id'], ['lending_sessions.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    _create_table('item_parameter_string_values',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('item_parameter_id', sa.Integer(), nullable=False),
    sa.Column('value', sa.String(length=128), nullable=False),
    sa.Column('is_custom', sa.Boolean(), nullable=True),
    sa.Column('created_at', sa.DateTime(), nullable=True),
    sa.ForeignKeyConstraint(['item_parameter_id'], ['item_parameters.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    _create_table('kanban_cards',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('uuid', sa.String(length=12), nullable=False),
    sa.Column('board_id', sa.Integer(), nullable=False),
    sa.Column('column_id', sa.Integer(), nullable=False),
    sa.Column('title', sa.String(length=256), nullable=False),
    sa.Column('description', sa.Text(), nullable=True),
    sa.Column('priority', sa.Integer(), nullable=True),
    sa.Column('label_color', sa.String(length=7), nullable=True),
    sa.Column('label_name', sa.String(length=64), nullable=True),
    sa.Column('category_id', sa.Integer(), nullable=True),
    sa.Column('key_persons', sa.Text(), nullable=True),
    sa.Column('card_icon', sa.String(length=48), nullable=True),
    sa.Column('start_date', sa.Date(), nullable=True),
    sa.Column('due_date', sa.Date(), nullable=True),
    sa.Column('completed_at', sa.DateTime(), nullable=True),
    sa.Column('position', sa.Integer(), nullable=True),
    sa.Column('created_at', sa.DateTime(), nullable=True),
    sa.Column('updated_at', sa.DateTime(), nullable=True),
    sa.Column('created_by_id', sa.Integer(), nullable=True),
    sa.Column('updated_by_id', sa.Integer(), nullable=True),
    sa.ForeignKeyConstraint(['board_id'], ['kanban_boards.id'], ),
    sa.ForeignKeyConstraint(['category_id'], ['kanban_categories.id'], ),
    sa.ForeignKeyConstraint(['column_id'], ['kanban_columns.id'], ),
    sa.ForeignKeyConstraint(['created_by_id'], ['users.id'], ),
    sa.ForeignKeyConstraint(['updated_by_id'], ['users.id'], ),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('uuid')
    )
    _create_table('project_bom_items',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('project_id', sa.Integer(), nullable=False),
    sa.Column('item_id', sa.Integer(), nullable=True),
    sa.Column('batch_id', sa.Integer(), nullable=True),
    sa.Column('quantity', sa.Integer(), nullable=True),
    sa.Column('used_quantity', sa.Integer(), nullable=True),
    sa.Column('serial_numbers', sa.Text(), nullable=True),
    sa.Column('item_name_snapshot', sa.String(length=300), nullable=True),
    sa.Column('sort_order', sa.Integer(), nullable=True),
    sa.Column('created_at', sa.DateTime(), nullable=True),
    sa.Column('updated_at', sa.DateTime(), nullable=True),
    sa.ForeignKeyConstraint(['batch_id'], ['item_batches.id'], ),
    sa.ForeignKeyConstraint(['item_id'], ['items.id'], ),
    sa.ForeignKeyConstraint(['project_id'], ['projects.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    _create_table('project_parameter_string_values',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('project_parameter_id', sa.Integer(), nullable=False),
    sa.Column('value', sa.String(length=128), nullable=False),
    sa.Column('is_custom', sa.Boolean(), nullable=True),
    sa.Column('created_at', sa.DateTime(), nullable=True),
    sa.ForeignKeyConstraint(['project_parameter_id'], ['project_parameters.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    _create_table('kanban_attachments',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('card_id', sa.Integer(), nullable=False),
    sa.Column('filename', sa.String(length=255), nullable=False),
    sa.Column('original_filename', sa.String(length=255), nullable=False),
    sa.Column('file_path', sa.String(length=500), nullable=False),
    sa.Column('file_type', sa.String(length=50), nullable=True),
    sa.Column('file_size', sa.Integer(), nullable=True),
    sa.Column('uploaded_at', sa.DateTime(), nullable=True),
    sa.Column('uploaded_by', sa.Integer(), nullable=True),
    sa.ForeignKeyConstraint(['card_id'], ['kanban_cards.id'], ),
    sa.ForeignKeyConstraint(['uploaded_by'], ['users.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    _create_table('kanban_card_share_files',
    sa.Column('card_id', sa.Integer(), nullable=False),
    sa.Column('shared_file_id', sa.Integer(), nullable=False),
    sa.ForeignKeyConstraint(['card_id'], ['kanban_cards.id'], ),
    sa.ForeignKeyConstraint(['shared_file_id'], ['shared_files.id'], ),
    sa.PrimaryKeyConstraint('card_id', 'shared_file_id')
    )
    _create_table('kanban_tasks',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('card_id', sa.Integer(), nullable=False),
    sa.Column('title', sa.String(length=256), nullable=False),
    sa.Column('completed', sa.Boolean(), nullable=True),
    sa.Column('start_date', sa.Date(), nullable=True),
    sa.Column('due_date', sa.Date(), nullable=True),
    sa.Column('position', sa.Integer(), nullable=True),
    sa.Column('created_at', sa.DateTime(), nullable=True),
    sa.ForeignKeyConstraint(['card_id'], ['kanban_cards.id'], ),
    sa.PrimaryKeyConstraint('id')
    )

    if 'users' in _existing:
        _add_legacy_columns(bind)
        _backfill(bind, 'users', 'user_uid', lambda: 'U' + _random(5))
        if 'kanban_boards' in _existing:
            _backfill(bind, 'kanban_boards', 'board_uuid', lambda: _random(11) + 'K')
        if 'sticker_templates' in _existing:
            # Templates from before per-user ownership have no owner and cannot be shown.
            bind.execute(sa.text('DELETE FROM sticker_templates WHERE owner_id IS NULL'))


def downgrade():
    for table in reversed(TABLES):
        op.drop_table(table)
