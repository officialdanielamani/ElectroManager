# Visual Storage System Routes
# Add these routes to your app.py

from flask import jsonify
import json
import os

# Initialize storage config file
STORAGE_CONFIG_FILE = 'storage_config.json'

def get_storage_config():
    """Load storage configuration"""
    if os.path.exists(STORAGE_CONFIG_FILE):
        with open(STORAGE_CONFIG_FILE, 'r') as f:
            return json.load(f)
    return {
        'Rack A': {'rows': 5, 'cols': 5},
        'Rack B': {'rows': 4, 'cols': 6},
        'Electronics Cabinet': {'rows': 3, 'cols': 4}
    }

def save_storage_config(config):
    """Save storage configuration"""
    with open(STORAGE_CONFIG_FILE, 'w') as f:
        json.dump(config, f, indent=2)

def organize_items_by_location(items):
    """Organize items into rack/drawer structure"""
    config = get_storage_config()
    racks = {}
    
    for rack_name, rack_config in config.items():
        racks[rack_name] = {
            'rows': rack_config['rows'],
            'cols': rack_config['cols'],
            'drawers': {},
            'items': []
        }
    
    # Organize items by location
    for item in items:
        if item.location:
            # Check if location matches a drawer format (e.g., "Rack A-R1-C1")
            for rack_name in racks.keys():
                if item.location.startswith(rack_name):
                    racks[rack_name]['items'].append(item)
                    if item.location not in racks[rack_name]['drawers']:
                        racks[rack_name]['drawers'][item.location] = []
                    racks[rack_name]['drawers'][item.location].append(item)
                    break
    
    return racks

@app.route('/visual-storage')
@login_required
def visual_storage():
    """Display visual storage system"""
    items = Item.query.all()
    racks = organize_items_by_location(items)
    locations = list(get_storage_config().keys())
    
    return render_template('visual_storage.html', racks=racks, locations=locations)

@app.route('/api/drawer/<path:drawer_id>')
@login_required
def get_drawer_contents(drawer_id):
    """API endpoint to get drawer contents"""
    items = Item.query.filter_by(location=drawer_id).all()
    
    items_data = []
    for item in items:
        image_url = None
        if item.attachments:
            for att in item.attachments:
                if att.file_type in ['png', 'jpg', 'jpeg', 'gif']:
                    image_url = url_for('uploaded_file', filename=att.filename)
                    break
        
        items_data.append({
            'id': item.id,
            'name': item.name,
            'sku': item.sku,
            'quantity': item.quantity,
            'unit': item.unit,
            'image': image_url
        })
    
    return jsonify({'items': items_data})

@app.route('/add-rack', methods=['POST'])
@login_required
@permission_required("settings_sections.location_management", "edit")
def add_rack():
    """Add a new rack to the storage system"""
    rack_name = request.form.get('rack_name')
    rows = int(request.form.get('rows', 5))
    cols = int(request.form.get('cols', 5))
    
    config = get_storage_config()
    config[rack_name] = {'rows': rows, 'cols': cols}
    save_storage_config(config)
    
    log_audit(current_user.id, 'create', 'rack', None, f'Created rack: {rack_name}')
    flash(f'Rack "{rack_name}" created successfully!', 'success')
    return redirect(url_for('visual_storage'))
