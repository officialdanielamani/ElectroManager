import os
import logging
from dotenv import load_dotenv

basedir = os.path.abspath(os.path.dirname(__file__))
load_dotenv(os.path.join(basedir, '.env'))

_INSECURE_DEFAULT_KEY = 'dev-secret-key-change-this'

class Config:
    _raw_secret = os.environ.get('SECRET_KEY') or _INSECURE_DEFAULT_KEY
    if _raw_secret == _INSECURE_DEFAULT_KEY:
        logging.warning(
            'SECURITY: SECRET_KEY is not set or uses the insecure default. '
            'Set a strong random SECRET_KEY environment variable before deploying to production.'
        )
    SECRET_KEY = _raw_secret

    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URI') or \
        'sqlite:///' + os.path.join(basedir, 'instance', 'inventory.db')
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    UPLOAD_FOLDER = os.path.join(basedir, os.environ.get('UPLOAD_FOLDER') or 'uploads')
    MAX_CONTENT_LENGTH = int(os.environ.get('MAX_CONTENT_LENGTH') or 16 * 1024 * 1024)  # 16MB
    ALLOWED_EXTENSIONS = {'pdf', 'png', 'jpg', 'jpeg', 'gif', 'txt', 'doc', 'docx'}
    DEMO_MODE = os.environ.get('DEMO_MODE', 'false').lower() == 'true'
    DEMO_ADMIN_USERNAME = os.environ.get('ADMIN_USERNAME', 'admin')

    # Session cookie hardening
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = 'Lax'
    REMEMBER_COOKIE_HTTPONLY = True
    REMEMBER_COOKIE_SAMESITE = 'Lax'
    # SESSION_COOKIE_SECURE and REMEMBER_COOKIE_SECURE should be set to True
    # when served over HTTPS. Enable via environment variable:
    SESSION_COOKIE_SECURE = os.environ.get('SESSION_COOKIE_SECURE', 'false').lower() == 'true'
    REMEMBER_COOKIE_SECURE = os.environ.get('SESSION_COOKIE_SECURE', 'false').lower() == 'true'

    WTF_CSRF_TIME_LIMIT = 3600  # 1 hour CSRF token lifetime
