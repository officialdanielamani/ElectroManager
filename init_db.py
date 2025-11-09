"""
Initialize Database Script
Run this to create database tables and default admin user with role system
"""
from app import app, db
from models import User, Role, Setting
import os
import json

def init_db():
    with app.app_context():
        print("Creating database tables...")
        db.create_all()
        print("✓ Database tables created!")
        
        # Create default roles
        create_default_roles()
        
        # Get admin credentials from environment variables or use defaults
        admin_username = os.getenv('ADMIN_USERNAME', 'admin')
        admin_password = os.getenv('ADMIN_PASSWORD', 'admin123')
        admin_email = os.getenv('ADMIN_EMAIL', 'admin@example.com')
        demo_mode = os.getenv('DEMO_MODE', 'false').lower() == 'true'
        
        # Get Admin role
        admin_role = Role.query.filter_by(name='Admin').first()
        if not admin_role:
            print("ERROR: Admin role not found!")
            return
        
        # Check if admin user exists
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
            print("✓ Default admin user created!")
            print("\n" + "="*50)
            print("  DEFAULT LOGIN CREDENTIALS")
            print("="*50)
            print(f"  Username: {admin_username}")
            print(f"  Password: {admin_password}")
            print(f"  Email:    {admin_email}")
            if demo_mode:
                print(f"  Mode:     DEMO (User profile is locked)")
            print("="*50)
            if admin_password == 'admin123':
                print("  ⚠️  CHANGE PASSWORD IMMEDIATELY AFTER FIRST LOGIN!")
            else:
                print("  ✓ Custom password set from environment variable")
            print("="*50 + "\n")
        else:
            print(f"✓ Admin user '{admin_username}' already exists, skipping creation.")
            if demo_mode and not admin.is_demo_user:
                admin.is_demo_user = True
                db.session.commit()
                print(f"✓ Marked '{admin_username}' as demo user")
        
        # Create default settings
        create_default_settings()
        
        print("✓ Database initialized successfully!")

def create_default_roles():
    """Create default role templates: Admin, Manager, Viewer"""
    
    # Admin Role - Full permissions
    admin_role = Role.query.filter_by(name='Admin').first()
    if not admin_role:
        admin_perms = {
            # Item Management (granular)
            "items": {
                "view": True, 
                "create": True,
                "delete": True, 
                "edit_name": True,
                "edit_sku_type": True,
                "edit_description": True,
                "edit_datasheet": True,
                "edit_upload": True,
                "edit_lending": True,
                "edit_price": True, 
                "edit_quantity": True, 
                "edit_location": True,
                "edit_category": True,
                "edit_footprint": True,
                "edit_tags": True,
                "edit_parameters": True
            },
            # Page Permissions
            "pages": {
                "visual_storage": {"view": True, "edit": True},
                "notifications": {"view": True, "edit": True},
                "settings": {"view": True, "edit": True}
            },
            # Settings Page Sections
            "settings_sections": {
                "system_settings": {"view": True, "edit": True},
                "reports": {"view": True},
                "item_management": {"view": True, "edit": True, "delete": True},
                "magic_parameters": {"view": True, "edit": True, "delete": True},
                "location_management": {"view": True, "edit": True, "delete": True},
                "users_roles": {
                    "view": True,
                    "roles_create": True,
                    "roles_edit": True,
                    "roles_delete": True,
                    "users_create": True,
                    "users_edit": True,
                    "users_delete": True
                },
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
        print("✓ Created Admin role")
    
    # Manager Role - Can edit most things except users and settings
    manager_role = Role.query.filter_by(name='Manager').first()
    if not manager_role:
        manager_perms = {
            # Item Management (granular)
            "items": {
                "view": True, 
                "create": True,
                "delete": True, 
                "edit_name": True,
                "edit_sku_type": True,
                "edit_description": True,
                "edit_datasheet": True,
                "edit_upload": True,
                "edit_lending": True,
                "edit_price": True, 
                "edit_quantity": True, 
                "edit_location": True,
                "edit_category": True,
                "edit_footprint": True,
                "edit_tags": True,
                "edit_parameters": True
            },
            # Page Permissions
            "pages": {
                "visual_storage": {"view": True, "edit": True},
                "notifications": {"view": True, "edit": True},
                "settings": {"view": True, "edit": False}
            },
            # Settings Page Sections
            "settings_sections": {
                "system_settings": {"view": True, "edit": False},
                "reports": {"view": True},
                "item_management": {"view": True, "edit": True, "delete": False},
                "magic_parameters": {"view": True, "edit": True, "delete": False},
                "location_management": {"view": True, "edit": True, "delete": False},
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
        manager_role = Role(
            name='Manager',
            description='Can manage inventory items and most resources but cannot manage users or system settings',
            is_system_role=True,
            permissions=json.dumps(manager_perms)
        )
        db.session.add(manager_role)
        print("✓ Created Manager role")
    
    # Viewer Role - Read-only access
    viewer_role = Role.query.filter_by(name='Viewer').first()
    if not viewer_role:
        viewer_perms = {
            # Item Management (granular)
            "items": {
                "view": True, 
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
                "visual_storage": {"view": True, "edit": False},
                "notifications": {"view": True, "edit": False},
                "settings": {"view": False, "edit": False}
            },
            # Settings Page Sections
            "settings_sections": {
                "system_settings": {"view": False, "edit": False},
                "reports": {"view": True},
                "item_management": {"view": True, "edit": False, "delete": False},
                "magic_parameters": {"view": False, "edit": False, "delete": False},
                "location_management": {"view": True, "edit": False, "delete": False},
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
        viewer_role = Role(
            name='Viewer',
            description='Read-only access to inventory items and resources',
            is_system_role=True,
            permissions=json.dumps(viewer_perms)
        )
        db.session.add(viewer_role)
        print("✓ Created Viewer role")
    
    db.session.commit()

def create_default_settings():
    """Create default system settings"""
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
    print("✓ Default settings created")

if __name__ == '__main__':
    init_db()
