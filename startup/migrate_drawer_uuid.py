#!/usr/bin/env python3
"""
Migration script to add drawer_uuid to items with drawer locations
Run this script if you're upgrading from a version without drawer UUIDs
"""
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import app, db
from models import Item, Rack
import re

def migrate_drawer_uuids():
    """Add drawer_uuid to all items that have a drawer location"""
    with app.app_context():
        # Get all items with drawer locations
        items_with_drawer = Item.query.filter(
            Item.rack_id.isnot(None),
            Item.drawer.isnot(None)
        ).all()
        
        if not items_with_drawer:
            print("No items with drawer locations found.")
            return
        
        print(f"Found {len(items_with_drawer)} items with drawer locations")
        
        migrated = 0
        skipped = 0
        
        for item in items_with_drawer:
            try:
                # Parse drawer format: R{row}-C{col}
                match = re.match(r'R(\d+)-C(\d+)', item.drawer)
                if not match:
                    print(f"⚠️  Skipping item {item.uuid}: Invalid drawer format '{item.drawer}'")
                    skipped += 1
                    continue
                
                row = int(match.group(1))
                col = int(match.group(2))
                
                # Generate drawer UUID using rack method
                drawer_uuid = item.rack.get_drawer_uuid(row, col)
                
                # In this migration, we're just showing what would be generated
                # The actual drawer_uuid field might be added later if needed
                print(f"✓ Item {item.uuid} ({item.name}) at {item.rack.name} {item.drawer} -> {drawer_uuid}")
                migrated += 1
                
            except Exception as e:
                print(f"❌ Error processing item {item.uuid}: {e}")
                skipped += 1
        
        print(f"\nMigration complete: {migrated} processed, {skipped} skipped")

if __name__ == '__main__':
    print("=" * 60)
    print("Drawer UUID Migration Script")
    print("=" * 60)
    migrate_drawer_uuids()
    print("\nNote: This script validates drawer format and shows generated UUIDs")
    print("No database changes are made by this script.")
