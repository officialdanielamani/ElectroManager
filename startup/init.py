#!/usr/bin/env python3
"""
Unified startup initialization - handles dependencies, database, and validation
"""
import os
import sys
import json
import urllib.request
import zipfile
import shutil
import subprocess
from pathlib import Path

# Add startup dir to path for local imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

class Startup:
    def __init__(self, verbose=True):
        self.verbose = verbose
        self.errors = []
        self.warnings = []
        self.config = None
        self.base_path = os.path.dirname(os.path.abspath(__file__))
        self.project_root = os.path.dirname(self.base_path)
    
    def log(self, msg, level='INFO'):
        if not self.verbose:
            return
        levels = {'INFO': '[*]', 'OK': '[OK]', 'ERROR': '[!]', 'WARN': '[!]'}
        print(f"{levels.get(level, '[*]')} {msg}")
    
    def step(self, title):
        print(f"\n[STEP] {title}")
    
    def create_dirs(self):
        self.step("Creating directories")
        dirs = [
            'uploads',
            'uploads/locations',
            'instance',
            'static/lib/bootstrap/css',
            'static/lib/bootstrap/js',
            'static/icons',
            'static/fonts/fontawesome',
            'static/css'
        ]
        for d in dirs:
            path = os.path.join(self.project_root, d)
            Path(path).mkdir(parents=True, exist_ok=True)
        self.log("Directories created", 'OK')
    
    def load_config(self):
        self.step("Loading configuration")
        config_path = os.path.join(self.project_root, 'js-requirements.json')
        
        if not os.path.exists(config_path):
            self.errors.append("js-requirements.json not found")
            return False
        
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                self.config = json.load(f)
            self.log("Configuration loaded", 'OK')
            return True
        except json.JSONDecodeError as e:
            self.errors.append(f"Invalid JSON: {str(e)}")
            return False
    
    def download_dependencies(self):
        if not self.config:
            self.errors.append("Configuration not loaded")
            return False
        
        success = True
        for dep in self.config.get('dependencies', []):
            # Skip if already installed or no URL
            if dep.get('installed') or not dep.get('url'):
                continue
            
            dep_name = dep.get('name')
            url = dep.get('url')
            dest = dep.get('dest')
            dep_type = dep.get('type', 'file')
            
            self.step(f"Downloading {dep_name}")
            
            if dep_type == 'zip':
                if self.download_and_extract(url, dest, dep_name):
                    self.log(f"{dep_name} extracted", 'OK')
                else:
                    success = False
            else:
                dest_path = os.path.join(self.project_root, dest)
                if self.download_file(url, dest_path):
                    self.log(f"{os.path.basename(dest)} downloaded", 'OK')
                else:
                    success = False
        
        return success
    
    def download_and_extract(self, url, extract_path, name):
        try:
            Path(extract_path).mkdir(parents=True, exist_ok=True)
            zip_path = os.path.join(extract_path, f'{name}.zip')
            urllib.request.urlretrieve(url, zip_path)
            
            with zipfile.ZipFile(zip_path, 'r') as zip_ref:
                for file in zip_ref.namelist():
                    if 'fonts/' in file and file.endswith(('.woff', '.woff2')):
                        zip_ref.extract(file, extract_path)
                        src = os.path.join(extract_path, file)
                        dst = os.path.join(extract_path, os.path.basename(file))
                        if src != dst and os.path.exists(src):
                            shutil.move(src, dst)
                    elif file.endswith('.css'):
                        zip_ref.extract(file, extract_path)
                        src = os.path.join(extract_path, file)
                        dst = os.path.join(extract_path, os.path.basename(file))
                        if src != dst and os.path.exists(src):
                            shutil.move(src, dst)
            
            os.remove(zip_path)
            for item in os.listdir(extract_path):
                item_path = os.path.join(extract_path, item)
                if os.path.isdir(item_path):
                    shutil.rmtree(item_path)
            
            return True
        except Exception as e:
            self.warnings.append(f"{name} download failed: {str(e)}")
            return False
    
    def download_file(self, url, dest):
        try:
            if os.path.exists(dest):
                return True
            Path(os.path.dirname(dest)).mkdir(parents=True, exist_ok=True)
            urllib.request.urlretrieve(url, dest)
            return True
        except Exception as e:
            self.warnings.append(f"Download failed: {os.path.basename(dest)}")
            return False
    
    def check_font_awesome(self):
        self.step("Checking Font Awesome")
        fonts_dir = os.path.join(self.project_root, 'static/fonts/fontawesome')
        css_file = os.path.join(self.project_root, 'static/css/fontawesome.min.css')
        
        fonts_exist = all(os.path.exists(os.path.join(fonts_dir, f)) 
                         for f in ['fa-solid-900.woff2', 'fa-regular-400.woff2', 
                                   'fa-brands-400.woff2', 'fa-v4compatibility.woff2'])
        css_exists = os.path.exists(css_file)
        
        if fonts_exist and css_exists:
            self.log("Font Awesome present", 'OK')
            return True
        
        if not fonts_exist:
            self.errors.append("Font Awesome fonts missing")
        if not css_exists:
            self.errors.append("Font Awesome CSS missing")
        return False
        self.step("Checking Font Awesome")
        fonts_dir = os.path.join(self.project_root, 'static/fonts/fontawesome')
        css_file = os.path.join(self.project_root, 'static/css/fontawesome.min.css')
        
        fonts_exist = all(os.path.exists(os.path.join(fonts_dir, f)) 
                         for f in ['fa-solid-900.woff2', 'fa-regular-400.woff2', 
                                   'fa-brands-400.woff2', 'fa-v4compatibility.woff2'])
        css_exists = os.path.exists(css_file)
        
        if fonts_exist and css_exists:
            self.log("Font Awesome present", 'OK')
            return True
        
        if not fonts_exist:
            self.errors.append("Font Awesome fonts missing")
        if not css_exists:
            self.errors.append("Font Awesome CSS missing")
        return False
    
    def init_database(self):
        self.step("Initializing database")
        db_path = os.path.join(self.project_root, 'instance/inventory.db')
        
        if os.path.exists(db_path):
            self.log("Database already exists", 'OK')
            return True
        
        try:
            result = subprocess.run(
                [sys.executable, os.path.join(os.path.dirname(__file__), 'init_db.py')],
                cwd=self.project_root,
                capture_output=True,
                timeout=30
            )
            
            if result.returncode == 0:
                self.log("Database initialized", 'OK')
                return True
            else:
                self.errors.append(f"Database init failed: {result.stderr.decode()}")
                return False
        except Exception as e:
            self.errors.append(f"Database init error: {str(e)}")
            return False
    
    def run(self):
        print("\n" + "="*60)
        print("Inventory Manager - Startup")
        print("="*60)
        
        try:
            self.create_dirs()
            self.load_config()
            self.download_dependencies()
            self.check_font_awesome()
            self.init_database()
            
            print("\n" + "="*60)
            
            if self.errors:
                print("FAILED - Critical errors:")
                for err in self.errors:
                    print(f"  - {err}")
                print("="*60)
                return False
            
            print("SUCCESS - All initialized")
            print("="*60)
            return True
        
        except KeyboardInterrupt:
            print("\n[!] Startup cancelled")
            return False
        except Exception as e:
            print(f"\n[!] Unexpected error: {str(e)}")
            return False

if __name__ == '__main__':
    startup = Startup(verbose=True)
    success = startup.run()
    sys.exit(0 if success else 1)
