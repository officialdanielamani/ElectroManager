"""Shared fixtures. The app is a module-level singleton, so its environment is set before import."""
import json
import os
import sys
import tempfile

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_TMP = tempfile.mkdtemp(prefix='electromanager-tests-')
os.environ.update(
    DATABASE_URI=f"sqlite:///{os.path.join(_TMP, 'test.db')}",
    SECRET_KEY='test-secret-key',
    UPLOAD_FOLDER=os.path.join(_TMP, 'uploads'),
    DEMO_MODE='false',
)
for path in (ROOT, os.path.join(ROOT, 'startup')):
    if path not in sys.path:
        sys.path.insert(0, path)

from app import app as flask_app  # noqa: E402
from extensions import limiter  # noqa: E402
from models import db, Item, ItemBatch, Role, User  # noqa: E402
import init_db  # noqa: E402

PASSWORD = 'correct-horse-1'


@pytest.fixture(scope='session')
def app():
    flask_app.config.update(TESTING=True, WTF_CSRF_ENABLED=False)
    limiter.enabled = False
    return flask_app


@pytest.fixture(autouse=True)
def clean_database(app):
    """Every test starts from the built-in roles and default settings, nothing else."""
    with app.app_context():
        db.session.remove()
        for table in reversed(db.metadata.sorted_tables):
            db.session.execute(table.delete())
        db.session.commit()
        init_db.create_default_roles()
        init_db.create_default_settings()
    yield
    with app.app_context():
        db.session.remove()


@pytest.fixture
def make_user(app):
    def _make(username, role='Admin', **fields):
        with app.app_context():
            user = User(username=username, name=username, email=f'{username}@example.com',
                        role_id=Role.query.filter_by(name=role).one().id, **fields)
            user.set_password(PASSWORD)
            db.session.add(user)
            db.session.commit()
            return user.id
    return _make


@pytest.fixture
def login(app):
    def _login(username, password=PASSWORD, client=None):
        client = client or app.test_client()
        response = client.post('/login', data={'username': username, 'password': password})
        assert response.status_code == 302, 'login failed'
        return client
    return _login


@pytest.fixture
def admin_client(make_user, login):
    make_user('admin')
    return login('admin')


@pytest.fixture
def make_item(app):
    def _make(name, quantity=10, price=1.0, min_quantity=0, **fields):
        with app.app_context():
            item = Item(name=name, min_quantity=min_quantity, **fields)
            db.session.add(item)
            db.session.flush()
            db.session.add(ItemBatch(item_id=item.id, batch_number=1, quantity=quantity, price_per_unit=price))
            db.session.flush()
            item.recalculate_from_batches()
            db.session.commit()
            return item.id
    return _make


def item_names(response):
    """Names of the items listed on an items page, in display order."""
    import re
    html = response.get_data(as_text=True)
    table = html.split('id="itemTable"', 1)[1].split('</table>', 1)[0] if 'id="itemTable"' in html else ''
    return re.findall(r'<a href="/item/[^"]+">([^<]+)</a>', table)


def mp(*criteria):
    return json.dumps(list(criteria))
