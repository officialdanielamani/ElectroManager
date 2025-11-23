"""
Offline library manager - Download and verify JavaScript libraries
"""
import os
import urllib.request
import zipfile
import shutil
from pathlib import Path

LIBRARIES = {
    'bootstrap': {
        'version': '5.3.0',
        'files': [
            ('https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css', 
             'static/lib/bootstrap/css/bootstrap.min.css'),
            ('https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/js/bootstrap.bundle.min.js',
             'static/lib/bootstrap/js/bootstrap.bundle.min.js')
        ]
    },
    'bootstrap-icons': {
        'version': '1.11.1',
        'url': 'https://github.com/twbs/icons/releases/download/v1.11.1/bootstrap-icons-1.11.1.zip',
        'extract_path': 'static/icons'
    },
    'sortablejs': {
        'version': '1.15.0',
        'url': 'https://cdn.jsdelivr.net/npm/sortablejs@1.15.0/Sortable.min.js',
        'dest': 'static/lib/Sortable.min.js'
    }
}

def ensure_dir(path):
    """Create directory if not exists"""
    Path(path).mkdir(parents=True, exist_ok=True)

def download_file(url, destination):
    """Download file, return True if successful or already exists"""
    if os.path.exists(destination):
        return True
    try:
        ensure_dir(os.path.dirname(destination))
        urllib.request.urlretrieve(url, destination)
        return True
    except:
        return False

def download_bootstrap(verbose=False):
    """Download Bootstrap CSS and JS"""
    if verbose:
        print("  Installing Bootstrap 5.3.0...")
    
    for url, dest in LIBRARIES['bootstrap']['files']:
        if not download_file(url, dest):
            if verbose:
                print(f"    [ERROR] Failed to download {os.path.basename(dest)}")
            return False
    
    if verbose:
        print("    OK")
    return True

def download_bootstrap_icons(verbose=False):
    """Download Bootstrap Icons with font files"""
    if verbose:
        print("  Installing Bootstrap Icons 1.11.1...")
    
    extract_path = LIBRARIES['bootstrap-icons']['extract_path']
    css_file = os.path.join(extract_path, 'bootstrap-icons.css')
    woff2_file = os.path.join(extract_path, 'bootstrap-icons.woff2')
    
    # Check if already exists
    if os.path.exists(css_file) and os.path.exists(woff2_file):
        return True
    
    ensure_dir(extract_path)
    zip_path = os.path.join(extract_path, 'bootstrap-icons.zip')
    
    try:
        url = LIBRARIES['bootstrap-icons']['url']
        urllib.request.urlretrieve(url, zip_path)
        
        with zipfile.ZipFile(zip_path, 'r') as zip_ref:
            for file in zip_ref.namelist():
                # Extract font files
                if 'fonts/' in file and file.endswith(('.woff', '.woff2', '.ttf')):
                    zip_ref.extract(file, extract_path)
                    src = os.path.join(extract_path, file)
                    dst = os.path.join(extract_path, os.path.basename(file))
                    if src != dst and os.path.exists(src):
                        shutil.move(src, dst)
                # Extract CSS
                elif file.endswith('bootstrap-icons.css'):
                    zip_ref.extract(file, extract_path)
                    src = os.path.join(extract_path, file)
                    dst = os.path.join(extract_path, 'bootstrap-icons.css')
                    if src != dst and os.path.exists(src):
                        shutil.move(src, dst)
        
        # Cleanup
        os.remove(zip_path)
        for item in os.listdir(extract_path):
            item_path = os.path.join(extract_path, item)
            if os.path.isdir(item_path):
                shutil.rmtree(item_path)
        
        if verbose:
            print("    OK")
        return True
    except Exception as e:
        if verbose:
            print(f"    [ERROR] {str(e)}")
        return False

def download_sortablejs(verbose=False):
    """Download SortableJS"""
    if verbose:
        print("  Installing SortableJS 1.15.0...")
    
    url = LIBRARIES['sortablejs']['url']
    dest = LIBRARIES['sortablejs']['dest']
    
    if download_file(url, dest):
        if verbose:
            print("    OK")
        return True
    else:
        if verbose:
            print("    [ERROR] Failed to download")
        return False

def update_icons_css():
    """No longer needed - icon paths are now dynamic via Jinja2 url_for"""
    pass

def initialize_libraries(verbose=False):
    """Download all libraries"""
    if verbose:
        print("\n" + "=" * 60)
        print("  DOWNLOADING JAVASCRIPT LIBRARIES")
        print("=" * 60)
    
    ensure_dir('static/lib/bootstrap/css')
    ensure_dir('static/lib/bootstrap/js')
    ensure_dir('static/icons')
    
    results = {
        'bootstrap': download_bootstrap(verbose),
        'bootstrap_icons': download_bootstrap_icons(verbose),
        'sortablejs': download_sortablejs(verbose)
    }
    
    update_icons_css()
    
    if verbose:
        print("\n" + "=" * 60)
        all_ok = all(results.values())
        if all_ok:
            print("  All libraries downloaded successfully")
        else:
            print("  Some libraries failed - Internet connection may be required")
        print("=" * 60 + "\n")
    
    return all(results.values())

if __name__ == '__main__':
    try:
        success = initialize_libraries(verbose=True)
        exit(0 if success else 1)
    except Exception as e:
        print(f"[ERROR] {str(e)}")
        exit(1)
