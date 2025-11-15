#!/usr/bin/env python3
"""
Migration script to add UUID columns to Location and Rack tables.
Run this ONCE before starting the application with the new code.
"""

import sqlite3
import string
import secrets
import sys
from pathlib import Path

def generate_uuid():
    """Generate 12-char alphanumeric UUID (A-Z, 0-9)"""
    chars = string.ascii_uppercase + string.digits
    return ''.join(secrets.choice(chars) for _ in range(12))

def migrate():
    """Add UUID columns to Location and Rack tables"""
    
    # Find database file
    db_path = Path('instance/inventory.db')
    if not db_path.exists():
        print("❌ Database not found at instance/inventory.db")
        print("   Create the database first by running the application.")
        return False
    
    try:
        conn = sqlite3.connect(str(db_path))
        cursor = conn.cursor()
        
        print("🔄 Starting migration...")
        
        # Check if uuid column already exists in locations
        cursor.execute("PRAGMA table_info(locations)")
        columns = [col[1] for col in cursor.fetchall()]
        
        if 'uuid' in columns:
            print("✓ Locations table already has uuid column")
        else:
            print("📝 Adding uuid column to locations table...")
            cursor.execute("ALTER TABLE locations ADD COLUMN uuid VARCHAR(12) UNIQUE NOT NULL DEFAULT ''")
            
            # Generate UUIDs for existing locations
            cursor.execute("SELECT id FROM locations WHERE uuid = ''")
            location_ids = cursor.fetchall()
            for (loc_id,) in location_ids:
                uuid = generate_uuid()
                cursor.execute("UPDATE locations SET uuid = ? WHERE id = ?", (uuid, loc_id))
            print(f"   Generated UUIDs for {len(location_ids)} existing locations")
        
        # Check if uuid column already exists in racks
        cursor.execute("PRAGMA table_info(racks)")
        columns = [col[1] for col in cursor.fetchall()]
        
        if 'uuid' in columns:
            print("✓ Racks table already has uuid column")
        else:
            print("📝 Adding uuid column to racks table...")
            cursor.execute("ALTER TABLE racks ADD COLUMN uuid VARCHAR(12) UNIQUE NOT NULL DEFAULT ''")
            
            # Generate UUIDs for existing racks
            cursor.execute("SELECT id FROM racks WHERE uuid = ''")
            rack_ids = cursor.fetchall()
            for (rack_id,) in rack_ids:
                uuid = generate_uuid()
                cursor.execute("UPDATE racks SET uuid = ? WHERE id = ?", (uuid, rack_id))
            print(f"   Generated UUIDs for {len(rack_ids)} existing racks")
        
        # Remove unique constraint from location.name if it exists
        print("📝 Checking location.name constraint...")
        cursor.execute("PRAGMA index_list(locations)")
        indexes = cursor.fetchall()
        for idx in indexes:
            if 'name' in idx[1].lower():
                cursor.execute(f"DROP INDEX IF EXISTS {idx[1]}")
                print(f"   Dropped index: {idx[1]}")
        
        # Remove unique constraint from rack.name if it exists
        print("📝 Checking rack.name constraint...")
        cursor.execute("PRAGMA index_list(racks)")
        indexes = cursor.fetchall()
        for idx in indexes:
            if 'name' in idx[1].lower():
                cursor.execute(f"DROP INDEX IF EXISTS {idx[1]}")
                print(f"   Dropped index: {idx[1]}")
        
        conn.commit()
        conn.close()
        
        print("\n✅ Migration completed successfully!")
        print("   You can now start the application.")
        return True
        
    except Exception as e:
        print(f"\n❌ Migration failed: {e}")
        print("\n   If migration fails, you can:")
        print("   1. Delete instance/inventory.db")
        print("   2. Run: python init_db.py")
        print("   3. Create new admin user: python create_admin.py")
        return False

if __name__ == '__main__':
    success = migrate()
    sys.exit(0 if success else 1)
