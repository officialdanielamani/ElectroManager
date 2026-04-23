"""
Initialize Database Script
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import app, db
from models import User, Role, Setting
import json

def _evolve_schema():
    """Add new columns to existing tables without full migrations."""
    from sqlalchemy import inspect, text
    inspector = inspect(db.engine)
    with db.engine.connect() as conn:
        bom_cols = {c['name'] for c in inspector.get_columns('project_bom_items')}
        if 'used_quantity' not in bom_cols:
            conn.execute(text("ALTER TABLE project_bom_items ADD COLUMN used_quantity INTEGER NOT NULL DEFAULT 0"))
            conn.commit()
            print("Schema: added project_bom_items.used_quantity")
        if 'item_name_snapshot' not in bom_cols:
            conn.execute(text("ALTER TABLE project_bom_items ADD COLUMN item_name_snapshot VARCHAR(300)"))
            conn.commit()
            print("Schema: added project_bom_items.item_name_snapshot")
        # Populate snapshot for existing rows that have a linked item
        conn.execute(text(
            "UPDATE project_bom_items SET item_name_snapshot = ("
            "  SELECT name FROM items WHERE items.id = project_bom_items.item_id"
            ") WHERE item_name_snapshot IS NULL AND item_id IS NOT NULL"
        ))
        conn.commit()

    _scrub_icon_package_from_sticker_templates()


def _scrub_icon_package_from_sticker_templates():
    """Strip the legacy icon_package field from every StickerTemplate layout.

    Custom icon packs were removed — the app now always uses Bootstrap Icons.
    Old rows still carry icon_package: 'fontawesome' etc. in their JSON
    blobs; scrub them so layouts round-trip cleanly.
    """
    from models import StickerTemplate
    try:
        templates = StickerTemplate.query.all()
    except Exception as e:
        print(f"Schema: StickerTemplate table not ready, skipping icon scrub ({e})")
        return
    scrubbed = 0
    for tpl in templates:
        try:
            layout = tpl.get_layout()
        except Exception:
            continue
        if not isinstance(layout, list):
            continue
        changed = False
        for element in layout:
            if isinstance(element, dict) and 'icon_package' in element:
                element.pop('icon_package', None)
                changed = True
        if changed:
            tpl.set_layout(layout)
            scrubbed += 1
    if scrubbed:
        db.session.commit()
        print(f"Schema: removed icon_package from {scrubbed} sticker template(s)")


def init_db():
    with app.app_context():
        print("Creating database tables...")
        db.create_all()
        print("Database tables created!")
        _evolve_schema()
        
        create_default_roles()
        
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

def create_default_roles():
    """Create default role templates: Admin, Manager, Viewer"""
    
    admin_role = Role.query.filter_by(name='Admin').first()
    if not admin_role:
        admin_perms = {
            "items": {
                "view": True, "create": True, "delete": True,
                "view_info": True, "edit_info": True,
                "view_batch": True, "edit_batch": True,
                "edit_quantity": True, "edit_price": True,
                "edit_sn": True, "edit_lending": True, "delete_batch": True,
                "view_advance": True, "edit_advance": True, "delete_advance": True,
            },
            "pages": {
                "visual_storage": {"view": True, "edit": True},
                "notifications": {"view": True, "edit": True},
                "settings": {"view": True, "edit": True}
            },
            "projects": {
                "view": True, "create": True, "edit": True, "delete": True
            },
            "settings_sections": {
                "system_settings": {"view": True, "edit": True},
                "reports": {"view": True},
                "item_management": {"view": True, "edit": True, "delete": True},
                "magic_parameters": {"view": True, "edit": True, "delete": True},
                "location_management": {"view": True, "edit": True, "delete": True},
                "qr_templates": {"view": True, "edit": True, "delete": True},
                "users_roles": {
                    "view": True,
                    "roles_create": True, "roles_edit": True, "roles_delete": True,
                    "users_create": True, "users_edit": True, "users_delete": True
                },
                "project_settings": {"view": True, "edit": True, "delete": True},
                "backup_restore": {"view": True, "upload_export": True, "delete": True}
            }
        }
        admin_role = Role(
            name='Admin',
            description='Full system access with all permissions',
            is_system_role=True,
            permissions=json.dumps(admin_perms)
        )
        db.session.add(admin_role)
        print("Created Admin role")
    
    manager_role = Role.query.filter_by(name='Manager').first()
    if not manager_role:
        manager_perms = {
            "items": {
                "view": True, "create": True, "delete": True,
                "view_info": True, "edit_info": True,
                "view_batch": True, "edit_batch": True,
                "edit_quantity": True, "edit_price": True,
                "edit_sn": True, "edit_lending": True, "delete_batch": True,
                "view_advance": True, "edit_advance": True, "delete_advance": True,
            },
            "pages": {
                "visual_storage": {"view": True, "edit": True},
                "notifications": {"view": True, "edit": True},
                "settings": {"view": True, "edit": False}
            },
            "projects": {
                "view": True, "create": True, "edit": True, "delete": False
            },
            "settings_sections": {
                "system_settings": {"view": True, "edit": False},
                "reports": {"view": True},
                "item_management": {"view": True, "edit": True, "delete": False},
                "magic_parameters": {"view": True, "edit": True, "delete": False},
                "location_management": {"view": True, "edit": True, "delete": False},
                "qr_templates": {"view": True, "edit": True, "delete": False},
                "users_roles": {
                    "view": False,
                    "roles_create": False, "roles_edit": False, "roles_delete": False,
                    "users_create": False, "users_edit": False, "users_delete": False
                },
                "project_settings": {"view": True, "edit": True, "delete": False},
                "backup_restore": {"view": False, "upload_export": False, "delete": False}
            }
        }
        manager_role = Role(
            name='Manager',
            description='Can manage inventory items and most resources but cannot manage users or system settings',
            is_system_role=True,
            permissions=json.dumps(manager_perms)
        )
        db.session.add(manager_role)
        print("Created Manager role")
    
    viewer_role = Role.query.filter_by(name='Viewer').first()
    if not viewer_role:
        viewer_perms = {
            "items": {
                "view": True, "create": False, "delete": False,
                "view_info": True, "edit_info": False,
                "view_batch": True, "edit_batch": False,
                "edit_quantity": False, "edit_price": False,
                "edit_sn": False, "edit_lending": False, "delete_batch": False,
                "view_advance": True, "edit_advance": False, "delete_advance": False,
            },
            "pages": {
                "visual_storage": {"view": True, "edit": False},
                "notifications": {"view": True, "edit": False},
                "settings": {"view": False, "edit": False}
            },
            "projects": {
                "view": True, "create": False, "edit": False, "delete": False
            },
            "settings_sections": {
                "system_settings": {"view": False, "edit": False},
                "reports": {"view": True},
                "item_management": {"view": True, "edit": False, "delete": False},
                "magic_parameters": {"view": False, "edit": False, "delete": False},
                "location_management": {"view": True, "edit": False, "delete": False},
                "qr_templates": {"view": True, "edit": False, "delete": False},
                "users_roles": {
                    "view": False,
                    "roles_create": False, "roles_edit": False, "roles_delete": False,
                    "users_create": False, "users_edit": False, "users_delete": False
                },
                "project_settings": {"view": False, "edit": False, "delete": False},
                "backup_restore": {"view": False, "upload_export": False, "delete": False}
            }
        }
        viewer_role = Role(
            name='Viewer',
            description='Read-only access to inventory items and resources',
            is_system_role=True,
            permissions=json.dumps(viewer_perms)
        )
        db.session.add(viewer_role)
        print("Created Viewer role")
    
    db.session.commit()

def create_default_settings():
    default_settings = [
        ('company_name', 'Inventory Manager', 'Company or organization name'),
        ('signup_enabled', 'false', 'Allow user self-registration'),
        ('items_per_page', '20', 'Number of items to display per page'),
        ('low_stock_threshold', '5', 'Default low stock threshold'),
        ('allowed_extensions', 'pdf,png,jpg,jpeg,gif,txt,doc,docx', 'Allowed file extensions for uploads'),
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
