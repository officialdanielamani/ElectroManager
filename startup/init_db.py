"""
Initialize Database Script
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import app, db
from models import User, Role, Setting
import json
import secrets
import string



def _generate_user_uid():
    """Generate a unique UXXXXX identifier (U + 5 uppercase alphanumeric chars)."""
    chars = string.ascii_uppercase + string.digits
    return 'U' + ''.join(secrets.choice(chars) for _ in range(5))


def _add_missing_columns():
    """Add new columns to existing tables without a migration script."""
    with db.engine.connect() as conn:
        additions = [
            ("batch_lend_records",   "lend_note",           "VARCHAR(128)"),
            ("batch_serial_numbers", "lend_note",           "VARCHAR(128)"),
            ("batch_serial_numbers", "lending_session_id",  "INTEGER"),
            ("batch_lend_records",   "lending_session_id",  "INTEGER"),
            ("users",                "user_uid",             "VARCHAR(6)"),
            ("users",                "api_enabled",          "BOOLEAN DEFAULT 0"),
            ("users",                "api_key",              "VARCHAR(64)"),
            ("users",                "api_item_search",      "BOOLEAN DEFAULT 0"),
            ("users",                "api_rack_drawer",      "BOOLEAN DEFAULT 0"),
            ("users",                "api_lending_return",   "BOOLEAN DEFAULT 0"),
        ]
        for table, col, col_type in additions:
            try:
                conn.execute(db.text(f"ALTER TABLE {table} ADD COLUMN {col} {col_type}"))
                conn.commit()
                print(f"[OK] Added column {table}.{col}")
            except Exception:
                pass  # column already exists

    # Backfill user_uid for existing users that don't have one
    users_without_uid = User.query.filter(User.user_uid == None).all()
    if users_without_uid:
        existing_uids = set(u.user_uid for u in User.query.filter(User.user_uid != None).all())
        for user in users_without_uid:
            uid = _generate_user_uid()
            while uid in existing_uids:
                uid = _generate_user_uid()
            user.user_uid = uid
            existing_uids.add(uid)
        db.session.commit()
        print(f"[OK] Backfilled user_uid for {len(users_without_uid)} existing user(s)")


def init_db():
    with app.app_context():
        print("Creating database tables...")
        db.create_all()
        _add_missing_columns()
        print("Database tables created!")

        create_default_roles()
        update_system_roles()
        
        admin_username = os.getenv('ADMIN_USERNAME', 'admin')
        admin_password = os.getenv('ADMIN_PASSWORD', 'admin123')
        admin_email = os.getenv('ADMIN_EMAIL', 'admin@example.com')
        demo_mode = os.getenv('DEMO_MODE', 'false').lower() == 'true'
        
        admin_role = Role.query.filter_by(name='Admin').first()
        if not admin_role:
            print("ERROR: Admin role not found!")
            return
        
        admin = User.query.filter_by(username=admin_username).first()
        if not admin:
            print(f"\nCreating default admin user: {admin_username}...")
            admin = User(
                username=admin_username,
                name=admin_username,
                email=admin_email,
                role_id=admin_role.id,
                is_active=True,
                is_demo_user=demo_mode
            )
            admin.set_password(admin_password)
            db.session.add(admin)
            db.session.commit()
            print("Default admin user created!")
            print("\n" + "="*50)
            print("ADMIN ACCOUNT CREATED")
            print("="*50)
            print(f"  Username: {admin_username}")
            print(f"  Email:    {admin_email}")
            if demo_mode:
                print(f"  Mode:     DEMO (User profile is locked)")
            print("="*50)
            if admin_password == 'admin123':
                print("Password: default ('admin123'). CHANGE IT IMMEDIATELY AFTER FIRST LOGIN!")
            else:
                print("Password: set from ADMIN_PASSWORD environment variable.")
            print("="*50 + "\n")
        else:
            print(f"Admin user '{admin_username}' already exists, skipping creation.")
            if demo_mode and not admin.is_demo_user:
                admin.is_demo_user = True
                db.session.commit()
                print(f"Marked '{admin_username}' as demo user")
        
        create_default_settings()
        
        print("Database initialized successfully!")

# ── Canonical permission sets for the three built-in system roles ──────────────
# These are the single source of truth.  update_system_roles() uses them to
# patch missing keys into existing roles without overwriting customised values.

_ADMIN_PERMS = {
    "items": {
        "view": True, "create": True, "delete": True,
        "view_info": True, "edit_info": True,
        "view_price": True,
        "view_lending_history": True,
        "edit_batch": True, "edit_quantity": True,
        "create_batch": True,
        "view_advance": True, "edit_advance": True, "delete_advance": True,
    },
    "lending_return": {
        "view_page": True, "only_self_lending": False, "view_log": True,
        "edit_batch": True, "delete_batch": True,
        "edit_lending": True, "delete_lending": True,
    },
    "pages": {
        "visual_storage": {"view": True, "edit": True},
        "notifications":  {"view": True, "edit": True},
        "settings":       {"view": True, "edit": True},
    },
    "projects": {
        "view": True, "create": True, "edit": True, "delete": True,
        "view_costing": True, "edit_costing": True,
    },
    "settings_sections": {
        "system_settings":    {"view": True, "edit": True},
        "reports":            {"view": True},
        "item_management":    {"view": True, "edit": True, "delete": True},
        "magic_parameters":   {"view": True, "edit": True, "delete": True},
        "location_management":{"view": True, "edit": True, "delete": True},
        "qr_templates":       {"view": True, "edit": True, "delete": True, "print_qr": True},
        "users_roles": {
            "view": True,
            "roles_create": True, "roles_edit": True, "roles_delete": True,
            "users_create": True, "users_edit": True, "users_delete": True,
        },
        "project_settings":   {"view": True, "edit": True, "delete": True},
        "backup_restore":     {"view": True, "upload_export": True, "delete": True},
        "contacts":           {"view_users": True, "view_other": True, "edit": True, "delete": True},
        "share_files":        {"view": True, "add": True, "edit": True, "delete": True},
    },
    "users_api": {"view": True, "run": True},
}

_MANAGER_PERMS = {
    "items": {
        "view": True, "create": True, "delete": True,
        "view_info": True, "edit_info": True,
        "view_price": True,
        "view_lending_history": True,
        "edit_batch": True, "edit_quantity": True,
        "create_batch": True,
        "view_advance": True, "edit_advance": True, "delete_advance": True,
    },
    "lending_return": {
        "view_page": True, "only_self_lending": False, "view_log": True,
        "edit_batch": True, "delete_batch": False,
        "edit_lending": True, "delete_lending": False,
    },
    "pages": {
        "visual_storage": {"view": True, "edit": True},
        "notifications":  {"view": True, "edit": True},
        "settings":       {"view": True, "edit": False},
    },
    "projects": {
        "view": True, "create": True, "edit": True, "delete": False,
        "view_costing": True, "edit_costing": True,
    },
    "settings_sections": {
        "system_settings":    {"view": True,  "edit": False},
        "reports":            {"view": True},
        "item_management":    {"view": True,  "edit": True,  "delete": False},
        "magic_parameters":   {"view": True,  "edit": True,  "delete": False},
        "location_management":{"view": True,  "edit": True,  "delete": False},
        "qr_templates":       {"view": True,  "edit": True,  "delete": False, "print_qr": True},
        "users_roles": {
            "view": False,
            "roles_create": False, "roles_edit": False, "roles_delete": False,
            "users_create": False, "users_edit": False, "users_delete": False,
        },
        "project_settings":   {"view": True,  "edit": True,  "delete": False},
        "backup_restore":     {"view": False, "upload_export": False, "delete": False},
        "contacts":           {"view_users": True, "view_other": True, "edit": True, "delete": False},
        "share_files":        {"view": True,  "add": True,   "edit": True,  "delete": False},
    },
    "users_api": {"view": True, "run": True},
}

_VIEWER_PERMS = {
    "items": {
        "view": True, "create": False, "delete": False,
        "view_info": True, "edit_info": False,
        "view_price": True,
        "view_lending_history": True,
        "edit_batch": False, "edit_quantity": False,
        "create_batch": False,
        "view_advance": True, "edit_advance": False, "delete_advance": False,
    },
    "lending_return": {
        "view_page": True, "only_self_lending": False, "view_log": True,
        "edit_batch": False, "delete_batch": False,
        "edit_lending": False, "delete_lending": False,
    },
    "pages": {
        "visual_storage": {"view": True,  "edit": False},
        "notifications":  {"view": True,  "edit": False},
        "settings":       {"view": False, "edit": False},
    },
    "projects": {
        "view": True, "create": False, "edit": False, "delete": False,
        "view_costing": True, "edit_costing": False,
    },
    "settings_sections": {
        "system_settings":    {"view": False, "edit": False},
        "reports":            {"view": True},
        "item_management":    {"view": True,  "edit": False, "delete": False},
        "magic_parameters":   {"view": False, "edit": False, "delete": False},
        "location_management":{"view": True,  "edit": False, "delete": False},
        "qr_templates":       {"view": True,  "edit": False, "delete": False, "print_qr": True},
        "users_roles": {
            "view": False,
            "roles_create": False, "roles_edit": False, "roles_delete": False,
            "users_create": False, "users_edit": False, "users_delete": False,
        },
        "project_settings":   {"view": False, "edit": False, "delete": False},
        "backup_restore":     {"view": False, "upload_export": False, "delete": False},
        "contacts":           {"view_users": False, "view_other": False, "edit": False, "delete": False},
        "share_files":        {"view": True,  "add": False,  "edit": False, "delete": False},
    },
    "users_api": {"view": True, "run": False},
}

# Map role name → canonical permission set (used by both create and update)
_ROLE_CANON = {
    'Admin':   _ADMIN_PERMS,
    'Manager': _MANAGER_PERMS,
    'Viewer':  _VIEWER_PERMS,
}


def _deep_merge_missing(target: dict, source: dict):
    """Recursively add keys from *source* that are absent in *target* (never overwrites)."""
    changed = False
    for key, val in source.items():
        if key not in target:
            target[key] = val
            changed = True
        elif isinstance(val, dict) and isinstance(target.get(key), dict):
            if _deep_merge_missing(target[key], val):
                changed = True
    return changed


def _deep_sync(target: dict, source: dict):
    """Recursively overwrite *target* with all values from *source*, adding missing keys too."""
    changed = False
    for key, val in source.items():
        if isinstance(val, dict):
            if not isinstance(target.get(key), dict):
                target[key] = {}
                changed = True
            if _deep_sync(target[key], val):
                changed = True
        else:
            if target.get(key) != val:
                target[key] = val
                changed = True
    return changed


def create_default_roles():
    """Create built-in system roles on first run. Skips roles that already exist."""
    role_specs = [
        ('Admin',   'Full system access with all permissions',                                 _ADMIN_PERMS),
        ('Manager', 'Can manage most resources but cannot manage users or system settings',    _MANAGER_PERMS),
        ('Viewer',  'Read-only access — can view items, projects and reports but cannot edit', _VIEWER_PERMS),
    ]
    for name, desc, perms in role_specs:
        if not Role.query.filter_by(name=name).first():
            role = Role(
                name=name,
                description=desc,
                is_system_role=True,
                permissions=json.dumps(perms),
            )
            db.session.add(role)
            print(f"Created role: {name}")
    db.session.commit()


def update_system_roles():
    """Sync permissions for ALL system roles on every startup.

    Canonical roles (those in _ROLE_CANON) are fully synced to their canonical
    dict — all values are updated, including ones previously set wrong.
    Any other system role (custom but flagged is_system_role) only receives
    False for missing keys — existing values are never overwritten.
    """
    def _false_template(d):
        return {k: (_false_template(v) if isinstance(v, dict) else False)
                for k, v in d.items()}
    fallback = _false_template(_ADMIN_PERMS)

    all_system_roles = Role.query.filter_by(is_system_role=True).all()
    for role in all_system_roles:
        perms = role.get_permissions()
        if role.name in _ROLE_CANON:
            # Fully sync canonical reference roles so every value matches the canon
            changed = _deep_sync(perms, _ROLE_CANON[role.name])
        else:
            # Unknown system roles: only fill missing keys with False
            changed = _deep_merge_missing(perms, fallback)
        if changed:
            role.set_permissions(perms)
            print(f"[OK] Synced permissions for role: {role.name}")

    db.session.commit()


def create_default_settings():
    default_settings = [
        ('company_name', 'Inventory Manager', 'Company or organization name'),
        ('signup_enabled', 'false', 'Allow user self-registration'),
        ('items_per_page', '20', 'Number of items to display per page'),
        ('low_stock_threshold', '5', 'Default low stock threshold'),
        ('allowed_extensions', 'pdf,png,jpg,jpeg,gif,txt,doc,docx', 'Allowed file extensions for uploads'),
        ('lr_lend_start_date_required', 'false', 'Lending start date is required'),
        ('lr_lend_start_time_required', 'false', 'Lending start time is required (only if date required)'),
        ('lr_lend_end_date_required', 'false', 'Lending end date is required'),
        ('lr_lend_end_time_required', 'false', 'Lending end time is required (only if date required)'),
        ('lr_lend_self_use_now', 'false', 'Only Self Lending must use current datetime for start'),
        ('lr_return_date_required', 'false', 'Return date is required'),
        ('lr_return_time_required', 'false', 'Return time is required (only if date required)'),
        ('lr_return_self_use_now', 'false', 'Only Self Lending must use current datetime for return'),
        ('lr_scan_enabled', 'false', 'Enable QR/Barcode camera scanning on In/Out page'),
        ('api_rate_limit', '5', 'API requests per second limit (1–100)'),
        ('api_item_search_enabled', 'false', 'Enable Item Search & Information API system-wide'),
        ('api_rack_drawer_enabled', 'false', 'Enable Rack & Drawer API system-wide'),
        ('api_lending_return_enabled', 'false', 'Enable Lending & Return API system-wide'),
    ]
    
    for key, value, description in default_settings:
        existing = Setting.query.filter_by(key=key).first()
        if not existing:
            setting = Setting(key=key, value=value, description=description)
            db.session.add(setting)
    
    db.session.commit()
    print("[OK] Default settings created")

if __name__ == '__main__':
    init_db()
