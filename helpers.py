"""
Common helper functions used across the application
"""
from flask import request
from urllib.parse import urlparse, urljoin
from models import Setting
import os


def is_safe_url(target):
    """
    Only allow redirects to internal relative URLs (not external sites).
    Strips backslashes and checks that scheme/netloc are empty.
    Also rejects targets that start with two or more slashes (e.g., '//evil.com').
    """
    # Normalize backslashes (important for browser behavior)
    target = target.replace('\\', '')
    # Reject protocol-relative or ambiguous URLs (e.g., //evil.com)
    if target.startswith('//'):
        return False
    # Only allow redirects to relative paths under this app
    res = urlparse(target)
    if not res.netloc and not res.scheme:
        return True
    return False


def is_safe_url_alt(target):
    """Validate that a URL is safe for redirects (prevents open redirect attacks)"""
    if not target:
        return False

    # Parse the target URL
    ref_url = urlparse(request.host_url)
    test_url = urlparse(urljoin(request.host_url, target))

    # URL is safe if it has no scheme/netloc (relative URL) or matches our host
    return test_url.scheme in ('http', 'https') and ref_url.netloc == test_url.netloc


def is_safe_file_path(file_path, base_dir):
    """Validate that a file path is safe for file operations (prevents path traversal)"""
    if not file_path:
        return False

    try:
        # Resolve to absolute paths to handle .. and symlinks
        base_path = os.path.abspath(base_dir)
        abs_file_path = os.path.abspath(file_path)

        # Ensure file_path stays within base_dir
        return abs_file_path.startswith(base_path)
    except (ValueError, OSError):
        return False


def format_currency(amount, currency_symbol=None, decimal_places=None):
    """
    Format amount as currency with configurable decimal places.
    
    Args:
        amount: The numeric amount to format
        currency_symbol: Currency symbol (defaults to server setting)
        decimal_places: Number of decimal places (defaults to server setting)
    
    Returns:
        Formatted string like "RM 1234.56" or "¥ 1050"
    """
    if currency_symbol is None:
        currency_symbol = Setting.get('currency', '$')
    if decimal_places is None:
        decimal_places = int(Setting.get('currency_decimal_places', '2'))
    
    if amount is None:
        return '-'
    
    format_string = f'{{:.{decimal_places}f}}'
    formatted_amount = format_string.format(float(amount))
    return f'{currency_symbol}{formatted_amount}'


def format_file_size(size_in_bytes):
    """Format file size in human readable format"""
    for unit in ['B', 'KB', 'MB', 'GB']:
        if size_in_bytes < 1024.0:
            return f"{size_in_bytes:.1f} {unit}"
        size_in_bytes /= 1024.0
    return f"{size_in_bytes:.1f} TB"


def filesize_filter(size):
    """Jinja2 filter for formatting file sizes"""
    return format_file_size(size)


def jinja_format_amount(amount, decimal_places=None):
    """
    Jinja2 filter for formatting currency amounts
    """
    return format_currency(amount, decimal_places=decimal_places)


def markdown_filter(text):
    """Jinja2 filter for rendering markdown with safe HTML"""
    from utils import markdown_to_html
    from markupsafe import Markup
    return Markup(markdown_to_html(text))
