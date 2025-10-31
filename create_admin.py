"""
Create Admin User Script
Run this if the setup script failed to create an admin user
"""
from app import app, db
from models import User

def create_admin():
    with app.app_context():
        print("=" * 50)
        print("Create Admin User")
        print("=" * 50)
        print()
        
        username = input("Enter admin username: ")
        
        # Check if user exists
        existing_user = User.query.filter_by(username=username).first()
        if existing_user:
            print(f"Error: User '{username}' already exists!")
            return
        
        email = input("Enter admin email: ")
        
        # Check if email exists
        existing_email = User.query.filter_by(email=email).first()
        if existing_email:
            print(f"Error: Email '{email}' is already registered!")
            return
        
        password = input("Enter admin password: ")
        
        # Create admin user
        user = User(
            username=username,
            email=email,
            role='admin',
            is_active=True
        )
        user.set_password(password)
        
        try:
            db.session.add(user)
            db.session.commit()
            print()
            print(f"✓ Admin user '{username}' created successfully!")
            print()
        except Exception as e:
            print(f"Error creating user: {e}")
            db.session.rollback()

if __name__ == '__main__':
    create_admin()
