"""
Initialize Database Script
Run this to create database tables and default admin user
"""
from app import app, db
from models import User
import os

def init_db():
    with app.app_context():
        print("Creating database tables...")
        db.create_all()
        print("✓ Database tables created!")
        
        # Get admin credentials from environment variables or use defaults
        admin_username = os.getenv('ADMIN_USERNAME', 'admin')
        admin_password = os.getenv('ADMIN_PASSWORD', 'admin123')
        admin_email = os.getenv('ADMIN_EMAIL', 'admin@example.com')
        demo_mode = os.getenv('DEMO_MODE', 'false').lower() == 'true'
        
        # Check if admin user exists
        admin = User.query.filter_by(username=admin_username).first()
        if not admin:
            print(f"\nCreating default admin user: {admin_username}...")
            admin = User(
                username=admin_username,
                email=admin_email,
                role='admin',
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
        
        print("✓ Database initialized successfully!")

if __name__ == '__main__':
    init_db()
