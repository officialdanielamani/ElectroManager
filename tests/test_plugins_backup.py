import io
import os

import sqlalchemy as sa

from db_migrate import current_revision, head_revision
from models import db, Plugin


def test_plugin_page_lists_discovered_plugins(app, admin_client):
    assert b'Example OAuth' in admin_client.get('/settings/plugins').data
    with app.app_context():
        assert Plugin.query.filter_by(slug='example_oauth').one().enabled is False


def test_plugin_toggle_and_config(app, admin_client):
    admin_client.get('/settings/plugins')
    admin_client.post('/settings/plugins/example_oauth/toggle')
    with app.app_context():
        assert Plugin.query.filter_by(slug='example_oauth').one().enabled is True

    form = {'client_id': 'abc', 'client_secret': 's3cret',
            'authorization_url': 'https://idp.example/auth', 'token_url': 'https://idp.example/token'}
    admin_client.post('/settings/plugins/example_oauth/config', data=form)
    # A blank password field keeps the stored secret.
    admin_client.post('/settings/plugins/example_oauth/config', data={**form, 'client_id': 'xyz', 'client_secret': ''})
    with app.app_context():
        config = Plugin.query.filter_by(slug='example_oauth').one().get_config()
    assert config['client_id'] == 'xyz' and config['client_secret'] == 's3cret'
    assert b's3cret' not in admin_client.get('/settings/plugins/example_oauth/config').data


def test_plugin_config_validation(app, admin_client):
    admin_client.get('/settings/plugins')
    response = admin_client.post('/settings/plugins/example_oauth/config', data={'client_id': ''})
    assert b'is required' in response.data
    with app.app_context():
        assert Plugin.query.filter_by(slug='example_oauth').one().get_config() == {}


def test_plugins_are_admin_only(app, make_user, login):
    make_user('viewer', role='Viewer')
    client = login('viewer')
    assert client.get('/settings/plugins').status_code == 302
    assert client.post('/settings/plugins/example_oauth/toggle').status_code == 302
    with app.app_context():
        assert Plugin.query.count() == 0


def _db_path(app):
    return app.config['SQLALCHEMY_DATABASE_URI'].replace('sqlite:///', '')


def test_restore_upgrades_an_older_backup(app, admin_client, make_item, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)  # the restore keeps a safety copy in the working directory
    old = tmp_path / 'old.db'
    engine = sa.create_engine(f'sqlite:///{old}')
    from db_migrate import upgrade_database
    upgrade_database(engine, '0001_baseline')
    with engine.begin() as conn:
        conn.execute(sa.text('DROP TABLE alembic_version'))
        conn.execute(sa.text("INSERT INTO items (id, uuid, name) VALUES (1, 'RESTOREDXXXI', 'From Backup')"))
    engine.dispose()

    make_item('Live Item')
    response = admin_client.post('/backup/restore', data={'backup': (io.BytesIO(old.read_bytes()), 'old.db')},
                                 content_type='multipart/form-data')
    assert response.status_code == 302
    with app.app_context():
        assert current_revision(db.engine) == head_revision()
        names = [r[0] for r in db.session.execute(sa.text('SELECT name FROM items'))]
    assert names == ['From Backup']
    assert os.path.exists(tmp_path / 'inventory_backup_old.db')


def test_restore_rejects_non_sqlite_upload(app, admin_client, make_item, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    make_item('Live Item')
    admin_client.post('/backup/restore', data={'backup': (io.BytesIO(b'not a database'), 'evil.db')},
                      content_type='multipart/form-data')
    with app.app_context():
        assert db.session.execute(sa.text('SELECT count(*) FROM items')).scalar() == 1


def test_restore_keeps_current_database_when_upload_is_unusable(app, admin_client, make_item, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    make_item('Live Item')
    corrupt = b'SQLite format 3\x00' + b'\x00' * 4096
    response = admin_client.post('/backup/restore', data={'backup': (io.BytesIO(corrupt), 'corrupt.db')},
                                 content_type='multipart/form-data', follow_redirects=True)
    assert b'previous database was kept' in response.data
    with app.app_context():
        assert db.session.execute(sa.text('SELECT name FROM items')).scalar() == 'Live Item'
