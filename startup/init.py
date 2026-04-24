#!/usr/bin/env python3
"""
Unified startup initialization - handles database and directory setup only.
No external downloads - all assets must be in the repository.
"""
import os
import sys
import subprocess
from pathlib import Path

# Add startup dir to path for local imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


class Startup:
    def __init__(self, verbose=True):
        self.verbose = verbose
        self.errors = []
        self.warnings = []
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
            # Custom assets (user-provided, optional)
            'static/custom/font',
            'static/custom/theme',
        ]
        for d in dirs:
            path = os.path.join(self.project_root, d)
            Path(path).mkdir(parents=True, exist_ok=True)
        self.log("Directories created", 'OK')

    def check_core_assets(self):
        """Verify that all required core assets are present in the repository."""
        self.step("Verifying core assets")

        core_files = {
            'Bootstrap CSS':         'static/lib/bootstrap.min.css',
            'Bootstrap JS':          'static/lib/bootstrap.bundle.min.js',
            'Bootstrap Icons CSS':   'static/icons/bootstrap-icons.css',
            'Bootstrap Icons font':  'static/icons/fonts/bootstrap-icons.woff2',
            'SortableJS':            'static/lib/sortable.min.js',
        }

        all_ok = True
        for label, rel_path in core_files.items():
            full = os.path.join(self.project_root, rel_path)
            if os.path.exists(full):
                self.log(f"{label} OK", 'OK')
            else:
                self.errors.append(
                    f"{label} missing ({rel_path}). "
                    "This is a required asset that must be in the repository."
                )
                all_ok = False

        return all_ok

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
            assets_ok = self.check_core_assets()
            self.detect_custom_assets()

            if assets_ok:
                self.init_database()
            else:
                print("\n[!] Skipping database init — fix missing assets first.")

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
    startup = Startup(verbose=True)
    success = startup.run()
    sys.exit(0 if success else 1)
