"""
Upload rules and checks shared by every place files are uploaded: items, projects,
Kanban cards and the Share Files library.

The browser keeps picked files until the user saves and checks them first
(static/js/pending-uploads.js); everything is checked again here. What passes is
stored, and each rejected file is reported with its reason.
"""
import os
from dataclasses import dataclass

from flask import current_app
from werkzeug.utils import secure_filename

from models import Setting
from utils import DANGEROUS_EXTENSIONS, format_file_size, validate_mime_type

PROJECT_ATTACHMENT_TYPES = {   # type: (label, default extensions, default max MB)
    'picture':   ('Pictures',   'webp,png,svg,jpeg,jpg', '10'),
    'document':  ('Documents',  'txt,doc,docx,pdf',      '10'),
    'schematic': ('Schematics', 'pdf,zip',               '20'),
    '2d_design': ('2D Designs', 'pdf,zip',               '20'),
    '3d_design': ('3D Designs', 'pdf,zip,stl,step',      '50'),
    'program':   ('Programs',   'zip,txt,cpp,py',        '10'),
}
_DEMO_EXTENSIONS = {'jpg', 'jpeg', 'png', 'txt', 'md'}
_DEMO_MAX_MB = 1
_EXECUTABLE_EXTENSIONS = {'exe', 'dll', 'so', 'bin', 'elf', 'dmg', 'app'}
_EXECUTABLE_SIGNATURES = (b'MZ', b'\x7fELF', b'\xca\xfe\xba\xbe', b'\xfe\xed\xfa\xce', b'\xce\xfa\xed\xfe')
# Upload counts of -1 ("unlimited") or above this are treated as this many when sizing requests.
_UNLIMITED_COUNT_FOR_SIZING = 50


@dataclass
class UploadRules:
    """What one upload area accepts. max_files counts existing files too: -1 unlimited, 0 disabled."""
    allowed: frozenset
    max_bytes: int
    max_files: int
    existing: int = 0

    @property
    def remaining(self):
        if self.max_files < 0:
            return None
        return max(self.max_files - self.existing, 0)

    def for_browser(self):
        return {'allowed': sorted(self.allowed), 'maxBytes': self.max_bytes,
                'maxFiles': self.max_files, 'existing': self.existing}


def _int_setting(key, default):
    try:
        return int(Setting.get(key, default))
    except (TypeError, ValueError):
        return int(default)


def _extensions(raw):
    return frozenset(e.strip().lower().lstrip('.') for e in str(raw or '').split(',') if e.strip()) - DANGEROUS_EXTENSIONS


def item_rules(existing=0):
    if current_app.config.get('DEMO_MODE'):
        allowed, max_mb = frozenset(_DEMO_EXTENSIONS), _DEMO_MAX_MB
    else:
        allowed = _extensions(Setting.get('allowed_extensions', 'pdf,png,jpg,jpeg,gif,txt,doc,docx'))
        max_mb = _int_setting('max_file_size_mb', '10')
    return UploadRules(allowed, max_mb * 1024 * 1024, _int_setting('max_file_upload_count', '5'), existing)


def project_rules(attachment_type, existing=0):
    _, default_ext, default_mb = PROJECT_ATTACHMENT_TYPES[attachment_type]
    allowed = _extensions(Setting.get(f'project_upload_{attachment_type}_extensions', default_ext))
    max_mb = _int_setting(f'project_upload_{attachment_type}_max_size', default_mb)
    max_files = _int_setting(f'project_upload_{attachment_type}_max_files', '5')
    return UploadRules(allowed, max_mb * 1024 * 1024, max_files, existing)


def kanban_rules(existing=0):
    if current_app.config.get('DEMO_MODE'):
        return UploadRules(frozenset({'png', 'jpg', 'jpeg'}), _DEMO_MAX_MB * 1024 * 1024, 5, existing)
    allowed = _extensions(Setting.get('kanban_upload_extensions', 'png,jpg,jpeg,txt,pdf'))
    max_mb = _int_setting('kanban_upload_max_size', '10')
    return UploadRules(allowed, max_mb * 1024 * 1024, _int_setting('kanban_upload_max_files', '5'), existing)


SHARE_CATEGORIES = {   # category: (default extensions, default max MB, demo extensions)
    'item':    ('pdf,png,jpg,jpeg,gif,txt,doc,docx', '10', 'jpg,jpeg,png,txt'),
    'project': ('pdf,png,jpg,jpeg,gif,txt,doc,docx', '10', 'jpg,jpeg,png,txt'),
    'profile': ('jpg,jpeg,png',                      '1',  'jpg,jpeg,png'),
    'sticker': ('png,jpg,jpeg',                      '1',  'jpg,jpeg,png'),
    'icon':    ('png,jpg,jpeg',                      '5',  'jpg,jpeg,png'),
}


def share_rules(category, existing=0):
    """Share library rules. max_files limits how many files the category may hold in total."""
    default_ext, default_mb, demo_ext = SHARE_CATEGORIES[category]
    if category == 'profile':
        return UploadRules(_extensions(default_ext), 1024 * 1024, -1, existing)
    if current_app.config.get('DEMO_MODE'):
        return UploadRules(_extensions(demo_ext), _DEMO_MAX_MB * 1024 * 1024, -1, existing)
    allowed = _extensions(Setting.get(f'share_{category}_extensions', default_ext))
    max_mb = _int_setting(f'share_{category}_max_size', default_mb)
    return UploadRules(allowed, max_mb * 1024 * 1024, _int_setting(f'share_{category}_max_files', '100'), existing)


def _size(storage):
    storage.stream.seek(0, os.SEEK_END)
    size = storage.stream.tell()
    storage.stream.seek(0)
    return size


def rejection_reason(storage, rules):
    """Why this uploaded file may not be stored, or None if it is fine."""
    name = secure_filename(storage.filename or '')
    if not name or '.' not in name:
        return 'has no file extension'
    ext = name.rsplit('.', 1)[1].lower()
    if ext not in rules.allowed:
        allowed = ', '.join(sorted(rules.allowed)) or 'none'
        return f'.{ext} files are not permitted here (allowed: {allowed})'
    size = _size(storage)
    if size == 0:
        return 'is empty'
    if size > rules.max_bytes:
        return f'is too large ({format_file_size(size)}; the limit is {format_file_size(rules.max_bytes)})'
    header = storage.stream.read(16)
    storage.stream.seek(0)
    if ext not in _EXECUTABLE_EXTENSIONS and any(header.startswith(sig) for sig in _EXECUTABLE_SIGNATURES):
        return f'was rejected because it is a program (executable) disguised as .{ext}'
    ok, reason = validate_mime_type(storage.stream, ext)
    storage.stream.seek(0)
    if not ok:
        return f'was rejected because its content does not match .{ext} ({reason.rstrip(".")})'
    return None


def select_uploads(files, rules):
    """Split uploaded files into (accepted, rejected); rejected is [(original name, reason)]."""
    accepted, rejected = [], []
    files = [f for f in files if f and f.filename]
    if files and rules.max_files == 0:
        return [], [(f.filename, 'was not uploaded because uploads are turned off here') for f in files]
    for storage in files:
        reason = rejection_reason(storage, rules)
        if reason is None and rules.remaining is not None and len(accepted) >= rules.remaining:
            reason = f'was not uploaded because the limit of {rules.max_files} files was reached'
        if reason:
            rejected.append((storage.filename, reason))
        else:
            accepted.append(storage)
    return accepted, rejected


def describe_rejections(rejected, area=None):
    """One message line per rejected file, e.g. 'File "3.jpeg" was rejected because ...'."""
    where = f' ({area})' if area else ''
    return [f'File "{name}"{where} {reason}.' for name, reason in rejected]


def request_size_limit():
    """Largest request any upload could make with its areas full, plus room for the rest of the form."""
    def total(rules):
        count = rules.max_files if 0 <= rules.max_files <= _UNLIMITED_COUNT_FOR_SIZING else _UNLIMITED_COUNT_FOR_SIZING
        return rules.max_bytes * count

    candidates = [
        total(item_rules()),
        sum(total(project_rules(t)) for t in PROJECT_ATTACHMENT_TYPES),
        total(kanban_rules()),
        *(total(share_rules(c)) for c in SHARE_CATEGORIES),
        16 * 1024 * 1024,
    ]
    return max(candidates) + 2 * 1024 * 1024


def remove_stored_file(path, upload_folder):
    """Delete a stored upload and its thumbnail, refusing anything outside the upload folder."""
    root = os.path.realpath(upload_folder)
    full = os.path.realpath(path if os.path.isabs(path) else os.path.join(root, path))
    if os.path.commonpath([root, full]) != root:
        return
    for target in (full, os.path.join(root, 'thumbs', os.path.relpath(full, root))):
        try:
            if os.path.isfile(target):
                os.remove(target)
        except OSError:
            current_app.logger.warning('Could not remove %s', target)
