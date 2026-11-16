import re

import pyotp

from conftest import PASSWORD
from models import db, Setting, User


def _field(html, name):
    return re.search(rf'name="{name}" value="([^"]+)"', html).group(1)


def _enable_mfa(client):
    """Walk through 2FA setup; returns (secret, backup_codes)."""
    secret = _field(client.get('/settings/mfa/setup').get_data(as_text=True), 'mfa_secret')
    response = client.post('/settings/mfa/setup',
                           data={'mfa_secret': secret, 'totp_code': pyotp.TOTP(secret).now()})
    codes = re.findall(r'>([A-Z0-9]{4})-([A-Z0-9]{4})<', response.get_data(as_text=True))
    return secret, [a + b for a, b in codes]


def test_pages_require_login(app):
    response = app.test_client().get('/items')
    assert response.status_code == 302
    assert '/login' in response.headers['Location']


def test_login_and_logout(make_user, login):
    make_user('alice')
    client = login('alice')
    assert client.get('/items').status_code == 200
    client.get('/logout')
    assert client.get('/items').status_code == 302


def test_wrong_password_is_rejected(app, make_user):
    make_user('alice')
    client = app.test_client()
    response = client.post('/login', data={'username': 'alice', 'password': 'nope'})
    assert response.status_code == 200
    assert client.get('/items').status_code == 302


def test_inactive_user_cannot_log_in(app, make_user):
    make_user('alice', is_active=False)
    client = app.test_client()
    client.post('/login', data={'username': 'alice', 'password': PASSWORD})
    assert client.get('/items').status_code == 302


def test_account_locks_after_max_failed_attempts(app, make_user):
    make_user('alice', max_login_attempts=2)
    client = app.test_client()
    for _ in range(2):
        client.post('/login', data={'username': 'alice', 'password': 'nope'})
    response = client.post('/login', data={'username': 'alice', 'password': PASSWORD})
    assert response.status_code == 200
    assert b'temporarily locked' in response.data
    assert client.get('/items').status_code == 302


def test_login_only_redirects_to_known_pages(app, make_user):
    make_user('alice')
    client = app.test_client()
    response = client.post('/login?next=https://evil.example/', data={'username': 'alice', 'password': PASSWORD})
    assert response.headers['Location'] == '/'


def test_registration_respects_signup_setting(app):
    client = app.test_client()
    form = {'username': 'newbie', 'email': 'newbie@example.com',
            'password': 'Passw0rd-123', 'confirm_password': 'Passw0rd-123', 'password2': 'Passw0rd-123'}
    client.post('/register', data=form)
    with app.app_context():
        assert User.query.filter_by(username='newbie').first() is None
        Setting.set('signup_enabled', True)
    client.post('/register', data=form)
    with app.app_context():
        created = User.query.filter_by(username='newbie').one()
        assert created.user_role.name == 'Viewer'


def test_verify_password(admin_client):
    assert admin_client.post('/verify-password', json={'password': PASSWORD}).status_code == 200
    assert admin_client.post('/verify-password', json={'password': 'nope'}).status_code == 401


def test_mfa_setup_rejects_wrong_code(app, admin_client):
    secret = _field(admin_client.get('/settings/mfa/setup').get_data(as_text=True), 'mfa_secret')
    admin_client.post('/settings/mfa/setup', data={'mfa_secret': secret, 'totp_code': '000000'})
    with app.app_context():
        assert not User.query.filter_by(username='admin').one().mfa_enabled


def test_mfa_login_needs_second_factor(app, admin_client):
    secret, codes = _enable_mfa(admin_client)
    assert len(codes) == 8
    admin_client.get('/logout')

    client = app.test_client()
    response = client.post('/login', data={'username': 'admin', 'password': PASSWORD})
    assert response.headers['Location'].endswith('/login/mfa')
    assert client.get('/items').status_code == 302, 'password alone must not log in'

    assert client.post('/login/mfa', data={'totp_code': '000000'}).status_code == 200
    assert client.get('/items').status_code == 302

    assert client.post('/login/mfa', data={'totp_code': pyotp.TOTP(secret).now()}).status_code == 302
    assert client.get('/items').status_code == 200


def test_mfa_backup_code_works_once(app, admin_client):
    _, codes = _enable_mfa(admin_client)
    admin_client.get('/logout')

    for expected_status in (200, 302):  # first use logs in, second is refused
        client = app.test_client()
        client.post('/login', data={'username': 'admin', 'password': PASSWORD})
        client.post('/login/mfa', data={'totp_code': f'{codes[0][:4]}-{codes[0][4:]}'})
        assert client.get('/items').status_code == expected_status


def test_mfa_page_needs_password_step_first(app):
    response = app.test_client().get('/login/mfa')
    assert response.status_code == 302 and '/login' in response.headers['Location']


def test_mfa_disable_needs_password(app, admin_client):
    _enable_mfa(admin_client)
    admin_client.post('/settings/mfa/disable', data={'password': 'nope'})
    with app.app_context():
        assert User.query.filter_by(username='admin').one().mfa_enabled
    admin_client.post('/settings/mfa/disable', data={'password': PASSWORD})
    with app.app_context():
        user = User.query.filter_by(username='admin').one()
        assert not user.mfa_enabled and user.mfa_secret is None


def test_security_headers(app):
    headers = app.test_client().get('/login').headers
    assert "object-src 'none'" in headers['Content-Security-Policy']
    assert headers['X-Content-Type-Options'] == 'nosniff'


def test_session_expires_after_configured_lifetime(app, make_user):
    from datetime import datetime, timedelta, timezone
    from email.utils import parsedate_to_datetime
    make_user('alice')
    response = app.test_client().post('/login', data={'username': 'alice', 'password': PASSWORD})
    cookie = next(h for h in response.headers.getlist('Set-Cookie') if h.startswith('session='))
    expires = parsedate_to_datetime(re.search(r'Expires=([^;]+)', cookie).group(1))
    remaining = expires - datetime.now(timezone.utc)
    assert timedelta(hours=7, minutes=55) < remaining <= app.config['PERMANENT_SESSION_LIFETIME'] == timedelta(hours=8)
