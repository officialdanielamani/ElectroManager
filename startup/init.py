#!/usr/bin/env python3
"""
Unified startup initialization - handles dependencies, database, and validation

Asset model
-----------
Core   : Bootstrap CSS/JS, SortableJS, Bootstrap Icons.
         Downloaded on first run (or during Docker build).
         Startup verifies these exist — missing core assets are fatal.

Custom : Anything placed in static/custom/ (icon packs like Font Awesome,
         extra fonts, custom CSS themes, etc.).
         Loaded automatically at runtime; never pre-checked or required.
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
            # Runtime data
            'uploads',
            'uploads/locations',
            'instance',
            # Core static assets
            'static/lib/bootstrap/css',
            'static/lib/bootstrap/js',
            'static/icons',
            'static/css',
            'static/js',
            # Custom assets (user-provided, optional)
            'static/custom/font',
            'static/custom/theme',
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
            if dep.get('installed') or not dep.get('url'):
                continue

            dep_name = dep.get('name')
            url = dep.get('url')
            dest = dep.get('dest')
            dep_type = dep.get('type', 'file')

            if dep_type == 'zip':
                if self._zip_already_extracted(dest):
                    self.log(f"{dep_name} already present, skipping download", 'OK')
                    continue
                self.step(f"Downloading {dep_name}")
                if self.download_and_extract(url, dest, dep_name):
                    self.log(f"{dep_name} extracted", 'OK')
                else:
                    success = False
            else:
                dest_path = os.path.join(self.project_root, dest)
                if os.path.exists(dest_path):
                    self.log(f"{dep_name} already present, skipping download", 'OK')
                    continue
                self.step(f"Downloading {dep_name}")
                if self.download_file(url, dest_path):
                    self.log(f"{os.path.basename(dest)} downloaded", 'OK')
                else:
                    success = False

        return success

    def _zip_already_extracted(self, dest):
        """Return True when the key artefacts of a zip dep are already on disk."""
        dest_path = os.path.join(self.project_root, dest)
        if not os.path.isdir(dest_path):
            return False
        css_files = list(Path(dest_path).glob('*.css'))
        font_files = list(Path(dest_path).glob('*.woff2')) + list(Path(dest_path).glob('*.woff'))
        return bool(css_files) or bool(font_files)

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

    # ------------------------------------------------------------------
    # Core asset verification
    # ------------------------------------------------------------------

    def check_core_assets(self):
        """Verify that all required core assets are present after download."""
        self.step("Verifying core assets")

        core_files = {
            'Bootstrap CSS':    'static/lib/bootstrap/css/bootstrap.min.css',
            'Bootstrap JS':     'static/lib/bootstrap/js/bootstrap.bundle.min.js',
            'Bootstrap Icons':  'static/icons/bootstrap-icons.css',
            'SortableJS':       'static/lib/Sortable.min.js',
        }

        all_ok = True
        for label, rel_path in core_files.items():
            full = os.path.join(self.project_root, rel_path)
            if os.path.exists(full):
                self.log(f"{label} OK", 'OK')
            else:
                self.errors.append(
                    f"{label} missing ({rel_path}). "
                    "Run startup again with network access to download it."
                )
                all_ok = False

        return all_ok

    # ------------------------------------------------------------------
    # Custom asset detection (informational only — never fatal)
    # ------------------------------------------------------------------

    def detect_custom_assets(self):
        """Scan static/custom/ and report user-provided files (no validation)."""
        self.step("Detecting custom assets (static/custom/)")
        custom_dir = os.path.join(self.project_root, 'static', 'custom')
        Path(custom_dir).mkdir(parents=True, exist_ok=True)

        css_found   = sorted(Path(custom_dir).glob('*.css'))
        font_found  = sorted(
            list(Path(custom_dir).glob('*.woff2')) +
            list(Path(custom_dir).glob('*.woff'))  +
            list(Path(custom_dir).glob('*.ttf'))   +
            list(Path(custom_dir).glob('*.otf'))
        )

        if css_found:
            self.log(f"CSS  : {[f.name for f in css_found]}", 'OK')
        if font_found:
            self.log(f"Fonts: {[f.name for f in font_found]}", 'OK')
        if not css_found and not font_found:
            self.log(
                "No custom assets — drop .css / font files in static/custom/ to auto-load",
                'INFO'
            )

    # ------------------------------------------------------------------
    # Database
    # ------------------------------------------------------------------

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

    # ------------------------------------------------------------------
    # Entry points
    # ------------------------------------------------------------------

    def run_download_only(self):
        """Download core dependencies only — used during Docker image build."""
        print("\n" + "="*60)
        print("Inventory Manager - Downloading core dependencies (build stage)")
        print("="*60)

        try:
            self.create_dirs()
            self.load_config()
            self.download_dependencies()
            self.check_core_assets()

            print("\n" + "="*60)
            if self.warnings:
                print("WARNINGS (non-fatal):")
                for w in self.warnings:
                    print(f"  [!] {w}")

            if self.errors:
                print("FAILED - Critical errors:")
                for err in self.errors:
                    print(f"  - {err}")
                print("="*60)
                return False

            print("SUCCESS - Core dependencies ready")
            print("="*60)
            return True
        except Exception as e:
            print(f"\n[!] Unexpected error: {str(e)}")
            return False

    def run(self):
        print("\n" + "="*60)
        print("Inventory Manager - Startup")
        print("="*60)

        try:
            self.create_dirs()
            self.load_config()
            self.download_dependencies()
            self.check_core_assets()
            self.detect_custom_assets()
            self.init_database()

            print("\n" + "="*60)

            if self.warnings:
                print("WARNINGS (non-fatal):")
                for w in self.warnings:
                    print(f"  [!] {w}")

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
    download_only = '--download-only' in sys.argv
    startup = Startup(verbose=True)
    success = startup.run_download_only() if download_only else startup.run()
    sys.exit(0 if success else 1)
